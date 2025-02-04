"""You can define a path as list of points.
To create a component you need to extrude the path with a cross-section.
"""
import inspect
import sys
from collections.abc import Iterable
from functools import partial
from inspect import getmembers
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pydantic
from pydantic import BaseModel, Field

from gdsfactory.add_pins import add_bbox_siepic, add_pins_siepic_optical_2nm
from gdsfactory.tech import TECH, Section

LAYER = TECH.layer
Layer = Tuple[int, int]
Layers = Tuple[Layer, ...]

LayerSpec = Union[Layer, int, str, None]
LayerSpecs = List[LayerSpec]
Floats = Tuple[float, ...]
port_names_electrical = ("e1", "e2")
port_types_electrical = ("electrical", "electrical")
cladding_layers_optical = ((68, 0),)  # for SiEPIC verification
cladding_offsets_optical = (0,)  # for SiEPIC verification


class CrossSection(BaseModel):
    """Waveguide information to extrude a path.

    cladding_layers follow path shape, while bbox_layers are rectangular.

    Attributes:
        layer: main Section layer. Main section name = '_default'.
        width: main Section width (um) or function parameterized from 0 to 1.
            the width at t==0 is the width at the beginning of the Path.
            the width at t==1 is the width at the end.
        offset: main Section center offset (um) or function from 0 to 1.
             the offset at t==0 is the offset at the beginning of the Path.
             the offset at t==1 is the offset at the end.
        radius: main Section bend radius (um).
        width_wide: wide waveguides width (um) for low loss routing.
        auto_widen: taper to wide waveguides for low loss routing.
        auto_widen_minimum_length: minimum straight length for auto_widen.
        taper_length: taper_length for auto_widen.
        bbox_layers: list of layers for rectangular bounding box.
        bbox_offsets: list of bounding box offsets.
        cladding_layers: list of layers to extrude.
        cladding_offsets: list of offset from main Section edge.
        sections: list of Sections(width, offset, layer, ports).
        port_names: for input and output ('o1', 'o2').
        port_types: for input and output: electrical, optical, vertical_te ...
        min_length: defaults to 1nm = 10e-3um for routing.
        start_straight_length: straight length at the beginning of the route.
        end_straight_length: end length at the beginning of the route.
        snap_to_grid: can snap points to grid when extruding the path.
        aliases: dict of cross_section aliases.
        decorator: function when extruding component. For example add_pins.
        info: dict with extra settings or useful information.
        name: cross_section name.
    """

    layer: LayerSpec
    width: Union[float, Callable]
    offset: Union[float, Callable] = 0
    radius: Optional[float] = None
    width_wide: Optional[float] = None
    auto_widen: bool = False
    auto_widen_minimum_length: float = 200.0
    taper_length: float = 10.0
    bbox_layers: List[LayerSpec] = Field(default_factory=list)
    bbox_offsets: List[float] = Field(default_factory=list)
    cladding_layers: Optional[LayerSpecs] = None
    cladding_offsets: Optional[Floats] = None
    sections: List[Section] = Field(default_factory=list)
    port_names: Tuple[str, str] = ("o1", "o2")
    port_types: Tuple[str, str] = ("optical", "optical")
    min_length: float = 10e-3
    start_straight_length: float = 10e-3
    end_straight_length: float = 10e-3
    snap_to_grid: Optional[float] = None
    decorator: Optional[Callable] = None
    add_pins: Optional[Callable] = None
    add_bbox: Optional[Callable] = None
    info: Dict[str, Any] = Field(default_factory=dict)
    name: Optional[str] = None

    class Config:
        extra = "forbid"
        fields = {
            "decorator": {"exclude": True},
            "add_pins": {"exclude": True},
            "add_bbox": {"exclude": True},
        }

    def copy(self, width: Optional[float] = None):
        xs = super().copy()
        xs.decorator = self.decorator
        xs.add_pins = self.add_pins
        xs.add_bbox = self.add_bbox

        if width:
            xs.width = width
        return xs

    @property
    def aliases(self) -> Dict[str, Section]:
        s = dict(
            _default=Section(
                width=self.width,
                offset=self.offset,
                layer=self.layer,
                port_names=self.port_names,
                port_types=self.port_types,
                name="_default",
            )
        )
        sections = self.sections or []
        for section in sections:
            if section.name:
                s[section.name] = section
        return s

    def add_bbox_layers(
        self,
        component,
        top: Optional[float] = None,
        bottom: Optional[float] = None,
        right: Optional[float] = None,
        left: Optional[float] = None,
    ):
        """Add bounding box layers to a component.

        Args:
            component: to add layers.
            top: top padding.
            bottom: bottom padding.
            right: right padding.
            left: left padding.
        """

        from gdsfactory.add_padding import get_padding_points

        c = component
        x = self
        if x.bbox_layers and x.bbox_offsets:
            padding = []
            for layer, offset in zip(x.bbox_layers, x.bbox_offsets):
                points = get_padding_points(
                    component=c,
                    default=0,
                    top=top or offset,
                    bottom=bottom or offset,
                    left=left or offset,
                    right=right or offset,
                )
                padding.append(points)

            for layer, points in zip(x.bbox_layers, padding):
                c.add_polygon(points, layer=layer)
        return c


class Transition(CrossSection):
    cross_section1: CrossSection
    cross_section2: CrossSection
    width_type: str = "sine"
    sections: List[Section]
    layer: Optional[LayerSpec] = None
    width: Optional[Union[float, Callable]] = None


@pydantic.validate_arguments
def cross_section(
    width: Union[Callable, float] = 0.5,
    offset: Union[float, Callable] = 0,
    layer: LayerSpec = "WG",
    width_wide: Optional[float] = None,
    auto_widen: bool = False,
    auto_widen_minimum_length: float = 200.0,
    taper_length: float = 10.0,
    radius: Optional[float] = 10.0,
    sections: Optional[Tuple[Section, ...]] = None,
    port_names: Tuple[str, str] = ("o1", "o2"),
    port_types: Tuple[str, str] = ("optical", "optical"),
    min_length: float = 10e-3,
    start_straight_length: float = 10e-3,
    end_straight_length: float = 10e-3,
    snap_to_grid: Optional[float] = None,
    bbox_layers: Optional[List[LayerSpec]] = None,
    bbox_offsets: Optional[List[float]] = None,
    cladding_layers: Optional[LayerSpecs] = None,
    cladding_offsets: Optional[Floats] = None,
    info: Optional[Dict[str, Any]] = None,
    decorator: Optional[Callable] = None,
    add_pins: Optional[Callable] = None,
    add_bbox: Optional[Callable] = None,
) -> CrossSection:
    """Return CrossSection.

    Args:
        width: main Section width (um) or function parameterized from 0 to 1.
            the width at t==0 is the width at the beginning of the Path.
            the width at t==1 is the width at the end.
        offset: main Section center offset (um) or function from 0 to 1.
             the offset at t==0 is the offset at the beginning of the Path.
             the offset at t==1 is the offset at the end.
        layer: main section layer.
        width_wide: wide waveguides width (um) for low loss routing.
        auto_widen: taper to wide waveguides for low loss routing.
        auto_widen_minimum_length: minimum straight length for auto_widen.
        taper_length: taper_length for auto_widen.
        radius: bend radius (um)..
        sections: list of Sections(width, offset, layer, ports).
        port_names: for input and output ('o1', 'o2').
        port_types: for input and output: electrical, optical, vertical_te ...
        min_length: defaults to 1nm = 10e-3um for routing.
        start_straight_length: straight length at the beginning of the route.
        end_straight_length: end length at the beginning of the route.
        snap_to_grid: can snap points to grid when extruding the path.
        bbox_layers: list of layers for rectangular bounding box.
        bbox_offsets: list of bounding box offsets.
        cladding_layers: list of layers to extrude.
        cladding_offsets: list of offset from main Section edge.
        info: settings info.
        decorator: funcion to run when converting path to component.
        add_pins: optional function to add pins to component.
        add_bbox: optional funcion to add bounding box to component.
    """

    return CrossSection(
        width=width,
        offset=offset,
        layer=layer,
        width_wide=width_wide,
        auto_widen=auto_widen,
        auto_widen_minimum_length=auto_widen_minimum_length,
        taper_length=taper_length,
        radius=radius,
        bbox_layers=bbox_layers or [],
        bbox_offsets=bbox_offsets or [],
        cladding_layers=cladding_layers,
        cladding_offsets=cladding_offsets,
        sections=sections or (),
        min_length=min_length,
        start_straight_length=start_straight_length,
        end_straight_length=end_straight_length,
        snap_to_grid=snap_to_grid,
        port_types=port_types,
        port_names=port_names,
        info=info or {},
        decorator=decorator,
        add_bbox=add_bbox,
        add_pins=add_pins,
    )


strip = partial(
    cross_section,
    add_pins=add_pins_siepic_optical_2nm,
    add_bbox=add_bbox_siepic,
    cladding_layers=("DEVREC",),  # for SiEPIC verification
    cladding_offsets=(0,),  # for SiEPIC verification
)
strip_auto_widen = partial(strip, width_wide=0.9, auto_widen=True)

# Rib with rectangular slab
rib = partial(
    strip,
    bbox_layers=["SLAB90"],
    bbox_offsets=[3],
)

# Rib with with slab that follows the waveguide core
rib_conformal = partial(
    strip,
    sections=(Section(width=6, layer="SLAB90", name="slab"),),
)
nitride = partial(strip, layer="WGN", width=1.0)
strip_rib_tip = partial(
    strip, sections=(Section(width=0.2, layer="SLAB90", name="slab"),)
)

metal1 = partial(
    cross_section,
    layer="M1",
    width=10.0,
    port_names=port_names_electrical,
    port_types=port_types_electrical,
)
metal2 = partial(
    metal1,
    layer="M2",
)
metal3 = partial(
    metal1,
    layer="M3",
)


@pydantic.validate_arguments
def heater_metal(
    width: float = 2.5,
    layer: LayerSpec = "HEATER",
    **kwargs,
) -> CrossSection:
    """Returns metal heater cross_section.

    dimensions from https://doi.org/10.1364/OE.18.020298

    Args:
        width: metal width.
        layer: heater layer.

    Keyword Args:
        offset: main Section center offset (um) or function from 0 to 1.
             the offset at t==0 is the offset at the beginning of the Path.
             the offset at t==1 is the offset at the end.
        radius: main Section bend radius (um).
        width_wide: wide waveguides width (um) for low loss routing.
        auto_widen: taper to wide waveguides for low loss routing.
        auto_widen_minimum_length: minimum straight length for auto_widen.
        taper_length: taper_length for auto_widen.
        bbox_layers: list of layers for rectangular bounding box.
        bbox_offsets: list of bounding box offsets.
        cladding_layers: list of layers to extrude.
        cladding_offsets: list of offset from main Section edge.
        sections: list of Sections(width, offset, layer, ports).
        port_names: for input and output ('o1', 'o2').
        port_types: for input and output: electrical, optical, vertical_te ...
        min_length: defaults to 1nm = 10e-3um for routing.
        start_straight_length: straight length at the beginning of the route.
        end_straight_length: end length at the beginning of the route.
        snap_to_grid: can snap points to grid when extruding the path.
        aliases: dict of cross_section aliases.
        decorator: function when extruding component. For example add_pins.
        info: dict with extra settings or useful information.
        name: cross_section name.


    """
    return cross_section(
        width=width,
        layer=layer,
        **kwargs,
    )


@pydantic.validate_arguments
def pin(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    layer_slab: LayerSpec = "SLAB90",
    layers_via_stack1: LayerSpecs = ("PPP",),
    layers_via_stack2: LayerSpecs = ("NPP",),
    bbox_offsets_via_stack1: Tuple[float, ...] = (0, -0.2),
    bbox_offsets_via_stack2: Tuple[float, ...] = (0, -0.2),
    via_stack_width: float = 9.0,
    via_stack_gap: float = 0.55,
    slab_gap: float = -0.2,
    layer_via: LayerSpec = None,
    via_width: float = 1,
    via_offsets: Optional[Tuple[float, ...]] = None,
    **kwargs,
) -> CrossSection:
    """Rib PIN doped cross_section.

    Args:
        width: ridge width.
        layer: ridge layer.
        layer_slab: slab layer.
        layers_via_stack1: P++ layer.
        layers_via_stack2: N++ layer.
        bbox_offsets_via_stack1: for via left.
        bbox_offsets_via_stack2: for via right.
        via_stack_width: in um.
        via_stack_gap: offset from via_stack to ridge edge.
        slab_gap: extra slab gap (negative: via_stack goes beyond slab).
        layer_via:
        via_width:
        via_offsets:
        kwargs: other cross_section settings.

    https://doi.org/10.1364/OE.26.029983

    .. code::

                                      layer
                                |<----width--->|
                                 _______________ via_stack_gap           slab_gap
                                |              |<----------->|             <-->
        ___ ____________________|              |__________________________|___
       |   |         |                                       |            |   |
       |   |    P++  |         undoped silicon               |     N++    |   |
       |___|_________|_______________________________________|____________|___|
                                                              <----------->
                                                              via_stack_width
       <---------------------------------------------------------------------->
                                   slab_width
    """
    slab_width = width + 2 * via_stack_gap + 2 * via_stack_width - 2 * slab_gap
    via_stack_offset = width / 2 + via_stack_gap + via_stack_width / 2

    sections = [Section(width=slab_width, layer=layer_slab, name="slab")]
    sections += [
        Section(
            layer=layer,
            width=via_stack_width + 2 * cladding_offset,
            offset=+via_stack_offset,
        )
        for layer, cladding_offset in zip(layers_via_stack1, bbox_offsets_via_stack1)
    ]
    sections += [
        Section(
            layer=layer,
            width=via_stack_width + 2 * cladding_offset,
            offset=-via_stack_offset,
        )
        for layer, cladding_offset in zip(layers_via_stack2, bbox_offsets_via_stack2)
    ]

    if layer_via and via_width and via_offsets:
        sections += [
            Section(
                layer=layer_via,
                width=via_width,
                offset=offset,
            )
            for offset in via_offsets
        ]
    info = dict(
        width=width,
        layer=layer,
        layer_slab=layer_slab,
        layers_via_stack1=layers_via_stack1,
        layers_via_stack2=layers_via_stack2,
        bbox_offsets_via_stack1=bbox_offsets_via_stack1,
        bbox_offsets_via_stack2=bbox_offsets_via_stack2,
        via_stack_width=via_stack_width,
        via_stack_gap=via_stack_gap,
        slab_gap=slab_gap,
        layer_via=layer_via,
        via_width=via_width,
        via_offsets=via_offsets,
        **kwargs,
    )

    return strip(
        width=width,
        layer=layer,
        sections=tuple(sections),
        info=info,
        **kwargs,
    )


@pydantic.validate_arguments
def pn(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    layer_slab: LayerSpec = "SLAB90",
    gap_low_doping: float = 0.0,
    gap_medium_doping: Optional[float] = 0.5,
    gap_high_doping: Optional[float] = 1.0,
    width_doping: float = 8.0,
    width_slab: float = 7.0,
    layer_p: LayerSpec = "P",
    layer_pp: LayerSpec = "PP",
    layer_ppp: LayerSpec = "PPP",
    layer_n: LayerSpec = "N",
    layer_np: LayerSpec = "NP",
    layer_npp: LayerSpec = "NPP",
    port_names: Tuple[str, str] = ("o1", "o2"),
    bbox_layers: Optional[List[Layer]] = None,
    bbox_offsets: Optional[List[float]] = None,
    cladding_layers: Optional[Layers] = cladding_layers_optical,
    cladding_offsets: Optional[Floats] = cladding_offsets_optical,
) -> CrossSection:
    """Rib PN doped cross_section.

    Args:
        width: width of the ridge in um.
        layer: ridge layer.
        layer_slab: slab layer.
        gap_low_doping: from waveguide center to low doping.
        gap_medium_doping: from waveguide center to medium doping.
            None removes medium doping.
        gap_high_doping: from center to high doping. None removes it.
        width_doping: in um.
        width_slab: in um.
        layer_p: p doping layer.
        layer_pp: p+ doping layer.
        layer_ppp: p++ doping layer.
        layer_n: n doping layer.
        layer_np: n+ doping layer.
        layer_npp: n++ doping layer.
        bbox_layers: list of layers for rectangular bounding box.
        bbox_offsets: list of bounding box offsets.
        port_names: for input and output ('o1', 'o2').
        bbox_layers: list of layers for rectangular bounding box.
        bbox_offsets: list of bounding box offsets.


    .. code::

                                   layer
                           |<------width------>|
                            ____________________
                           |     |       |     |
        ___________________|     |       |     |__________________________|
                    P            |       |              N                 |
                 width_p         |       |           width_n              |
        <----------------------->|       |<------------------------------>|
                                     |<->|
                                     gap_low_doping
                                     |         |        N+                |
                                     |         |     width_np             |
                                     |         |<------------------------>|
                                     |<------->|
                                           gap_medium_doping

    """
    slab = Section(width=width_slab, offset=0, layer=layer_slab)
    sections = [slab]
    offset_low_doping = width_doping / 2 + gap_low_doping
    width_low_doping = width_doping - gap_low_doping

    n = Section(width=width_low_doping, offset=+offset_low_doping, layer=layer_n)
    p = Section(width=width_low_doping, offset=-offset_low_doping, layer=layer_p)
    sections.append(n)
    sections.append(p)

    if gap_medium_doping is not None:
        width_medium_doping = width_doping - gap_medium_doping
        offset_medium_doping = width_medium_doping / 2 + gap_medium_doping

        np = Section(
            width=width_medium_doping,
            offset=+offset_medium_doping,
            layer=layer_np,
        )
        pp = Section(
            width=width_medium_doping,
            offset=-offset_medium_doping,
            layer=layer_pp,
        )
        sections.append(np)
        sections.append(pp)

    if gap_high_doping is not None:
        width_high_doping = width_doping - gap_high_doping
        offset_high_doping = width_high_doping / 2 + gap_high_doping
        npp = Section(
            width=width_high_doping, offset=+offset_high_doping, layer=layer_npp
        )
        ppp = Section(
            width=width_high_doping, offset=-offset_high_doping, layer=layer_ppp
        )
        sections.append(npp)
        sections.append(ppp)

    bbox_layers = bbox_layers or []
    bbox_offsets = bbox_offsets or []
    for layer_cladding, cladding_offset in zip(bbox_layers, bbox_offsets):
        s = Section(
            width=width_slab + 2 * cladding_offset, offset=0, layer=layer_cladding
        )
        sections.append(s)

    info = dict(
        width=width,
        layer=layer,
        bbox_layers=bbox_layers,
        bbox_offsets=bbox_offsets,
        gap_low_doping=gap_low_doping,
        gap_medium_doping=gap_medium_doping,
        gap_high_doping=gap_high_doping,
        width_doping=width_doping,
        width_slab=width_slab,
    )
    return CrossSection(
        width=width,
        offset=0,
        layer=layer,
        port_names=port_names,
        info=info,
        sections=sections,
        cladding_offsets=cladding_offsets,
        cladding_layers=cladding_layers,
    )


@pydantic.validate_arguments
def strip_heater_metal_undercut(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    heater_width: float = 2.5,
    trench_width: float = 6.5,
    trench_gap: float = 2.0,
    layer_heater: LayerSpec = "HEATER",
    layer_trench: LayerSpec = "DEEPTRENCH",
    **kwargs,
) -> CrossSection:
    """Returns strip cross_section with top metal and undercut trenches on both sides.
    dimensions from https://doi.org/10.1364/OE.18.020298

    Args:
        width: waveguide width.
        layer: waveguide layer.
        heater_width: of metal heater.
        trench_width: in um.
        trench_gap: from waveguide edge to trench edge.
        layer_heater: heater layer.
        layer_trench: tench layer.
        kwargs: cross_section settings.


    .. code::

              |<-------heater_width--------->|
               ______________________________
              |                              |
              |         layer_heater         |
              |______________________________|

                   |<------width------>|
                    ____________________ trench_gap
                   |                   |<----------->|              |
                   |                   |             |   undercut   |
                   |       width       |             |              |
                   |                   |             |<------------>|
                   |___________________|             | trench_width |
                                                     |              |
                                                     |              |

    """
    trench_offset = trench_gap + trench_width / 2 + width / 2
    info = dict(
        width=width,
        layer=layer,
        heater_width=heater_width,
        trench_width=trench_width,
        trench_gap=trench_gap,
        layer_heater=layer_heater,
        layer_trench=layer_trench,
        **kwargs,
    )
    return strip(
        width=width,
        layer=layer,
        sections=(
            Section(
                layer=layer_heater,
                width=heater_width,
                port_names=port_names_electrical,
                port_types=port_types_electrical,
            ),
            Section(layer=layer_trench, width=trench_width, offset=+trench_offset),
            Section(layer=layer_trench, width=trench_width, offset=-trench_offset),
        ),
        info=info,
        **kwargs,
    )


@pydantic.validate_arguments
def strip_heater_metal(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    heater_width: float = 2.5,
    layer_heater: LayerSpec = "HEATER",
    **kwargs,
) -> CrossSection:
    """Returns strip cross_section with top heater metal.

    dimensions from https://doi.org/10.1364/OE.18.020298

    Args:
        width: waveguide width (um).
        layer: waveguide layer.
        heater_width: of metal heater.
        layer_heater: for the metal.

    """
    info = dict(
        width=width,
        layer=layer,
        heater_width=heater_width,
        layer_heater=layer_heater,
        **kwargs,
    )

    return strip(
        width=width,
        layer=layer,
        sections=(
            Section(
                layer=layer_heater,
                width=heater_width,
                port_names=port_names_electrical,
                port_types=port_types_electrical,
            ),
        ),
        info=info,
        **kwargs,
    )


@pydantic.validate_arguments
def strip_heater_doped(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    heater_width: float = 2.0,
    heater_gap: float = 0.8,
    layers_heater: LayerSpecs = ("WG", "NPP"),
    bbox_offsets_heater: Tuple[float, ...] = (0, 0.1),
    **kwargs,
) -> CrossSection:
    """Returns strip cross_section with N++ doped heaters on both sides.

    .. code::

                                  |<------width------>|
          ____________             ___________________               ______________
         |            |           |     undoped Si    |             |              |
         |layer_heater|           |  intrinsic region |<----------->| layer_heater |
         |____________|           |___________________|             |______________|
                                                                     <------------>
                                                        heater_gap     heater_width
    """
    heater_offset = width / 2 + heater_gap + heater_width / 2

    sections = [
        Section(
            layer=layer,
            width=heater_width + 2 * cladding_offset,
            offset=+heater_offset,
        )
        for layer, cladding_offset in zip(layers_heater, bbox_offsets_heater)
    ]

    sections += [
        Section(
            layer=layer,
            width=heater_width + 2 * cladding_offset,
            offset=-heater_offset,
        )
        for layer, cladding_offset in zip(layers_heater, bbox_offsets_heater)
    ]

    return strip(
        width=width,
        layer=layer,
        sections=tuple(sections),
        **kwargs,
    )


strip_heater_doped_via_stack = partial(
    strip_heater_doped,
    layers_heater=(LAYER.WG, LAYER.NPP, LAYER.VIAC),
    bbox_offsets_heater=(0, 0.1, -0.2),
)


@pydantic.validate_arguments
def rib_heater_doped(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    heater_width: float = 2.0,
    heater_gap: float = 0.8,
    layer_heater: LayerSpec = "NPP",
    layer_slab: LayerSpec = "SLAB90",
    slab_gap: float = 0.2,
    with_top_heater: bool = True,
    with_bot_heater: bool = True,
    **kwargs,
) -> CrossSection:
    """Returns rib cross_section with N++ doped heaters on both sides.
    dimensions from https://doi.org/10.1364/OE.27.010456

    .. code::


                                    |<------width------>|
                                     ____________________  heater_gap           slab_gap
                                    |                   |<----------->|             <-->
         ___ _______________________|                   |__________________________|___
        |   |            |                undoped Si                  |            |   |
        |   |layer_heater|                intrinsic region            |layer_heater|   |
        |___|____________|____________________________________________|____________|___|
                                                                       <---------->
                                                                        heater_width
        <------------------------------------------------------------------------------>
                                        slab_width
    """
    heater_offset = width / 2 + heater_gap + heater_width / 2

    if with_bot_heater and with_top_heater:
        slab_width = width + 2 * heater_gap + 2 * heater_width + 2 * slab_gap
        slab_offset = 0
    elif with_top_heater:
        slab_width = width + heater_gap + heater_width + slab_gap
        slab_offset = -slab_width / 2
    elif with_bot_heater:
        slab_width = width + heater_gap + heater_width + slab_gap
        slab_offset = +slab_width / 2

    sections = []

    if with_bot_heater:
        sections += [
            Section(layer=layer_heater, width=heater_width, offset=+heater_offset)
        ]
    if with_top_heater:
        sections += [
            Section(layer=layer_heater, width=heater_width, offset=-heater_offset)
        ]
    sections += [
        Section(width=slab_width, layer=layer_slab, offset=slab_offset, name="slab")
    ]
    return strip(
        width=width,
        layer=layer,
        sections=tuple(sections),
        **kwargs,
    )


@pydantic.validate_arguments
def rib_heater_doped_via_stack(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    heater_width: float = 1.0,
    heater_gap: float = 0.8,
    layer_slab: LayerSpec = "SLAB90",
    layer_heater: LayerSpec = "NPP",
    via_stack_width: float = 2.0,
    via_stack_gap: float = 0.8,
    layers_via_stack: LayerSpecs = ("NPP", "VIAC"),
    bbox_offsets_via_stack: Tuple[float, ...] = (0, -0.2),
    slab_gap: float = 0.2,
    slab_offset: float = 0,
    with_top_heater: bool = True,
    with_bot_heater: bool = True,
    **kwargs,
) -> CrossSection:
    """Returns rib cross_section with N++ doped heaters on both sides.
    dimensions from https://doi.org/10.1364/OE.27.010456

    Args:
        width: in um.
        layer: for main waveguide section.
        heater_width: in um.
        heater_gap: in um.
        layer_slab: for pedestal.
        layer_heater: for doped heater.
        via_stack_width: for the contact.
        via_stack_gap: in um.
        layers_via_stack: for the contact.
        bbox_offsets_via_stack: for the contact.
        slab_gap: from heater edge.
        slab_offset: over the center of the slab.
        with_top_heater: adds top/left heater.
        with_bot_heater: adds bottom/right heater.

    .. code::

                                   |<----width------>|
       slab_gap                     __________________ via_stack_gap     via_stack width
       <-->                        |                 |<------------>|<--------------->
                                   |                 | heater_gap |
                                   |                 |<---------->|
        ___ _______________________|                 |___________________________ ____
       |   |            |              undoped Si                 |              |    |
       |   |layer_heater|              intrinsic region           |layer_heater  |    |
       |___|____________|_________________________________________|______________|____|
                                                                   <------------>
                                                                    heater_width
       <------------------------------------------------------------------------------>
                                       slab_width

    """
    if with_bot_heater and with_top_heater:
        slab_width = width + 2 * heater_gap + 2 * heater_width + 2 * slab_gap
    elif with_top_heater:
        slab_width = width + heater_gap + heater_width + slab_gap
        slab_offset -= slab_width / 2
    elif with_bot_heater:
        slab_width = width + heater_gap + heater_width + slab_gap
        slab_offset += slab_width / 2

    heater_offset = width / 2 + heater_gap + heater_width / 2
    via_stack_offset = width / 2 + via_stack_gap + via_stack_width / 2
    sections = [
        Section(width=slab_width, layer=layer_slab, offset=slab_offset, name="slab"),
    ]
    if with_bot_heater:
        sections += [
            Section(
                layer=layer_heater,
                width=heater_width,
                offset=+heater_offset,
            )
        ]

    if with_top_heater:
        sections += [
            Section(
                layer=layer_heater,
                width=heater_width,
                offset=-heater_offset,
            )
        ]

    if with_bot_heater:
        sections += [
            Section(
                layer=layer,
                width=heater_width + 2 * cladding_offset,
                offset=+via_stack_offset,
            )
            for layer, cladding_offset in zip(layers_via_stack, bbox_offsets_via_stack)
        ]

    if with_top_heater:
        sections += [
            Section(
                layer=layer,
                width=heater_width + 2 * cladding_offset,
                offset=-via_stack_offset,
            )
            for layer, cladding_offset in zip(layers_via_stack, bbox_offsets_via_stack)
        ]

    return strip(
        sections=tuple(sections),
        width=width,
        layer=layer,
        **kwargs,
    )


CrossSectionFactory = Callable[..., CrossSection]


def get_cross_section_factories(
    modules, verbose: bool = False
) -> Dict[str, CrossSectionFactory]:
    """Returns cross_section factories from a module or list of modules.

    Args:
        modules: module or iterable of modules.
        verbose: prints in case any errors occur.
    """

    modules = modules if isinstance(modules, Iterable) else [modules]

    xs = {}
    for module in modules:
        for t in getmembers(module):
            if callable(t[1]) and t[0] != "partial":
                try:
                    r = inspect.signature(t[1]).return_annotation
                    if r == CrossSection:
                        xs[t[0]] = t[1]
                except ValueError:
                    if verbose:
                        print(f"error in {t[0]}")
    return xs


cross_sections = get_cross_section_factories(sys.modules[__name__])


def test_copy():
    import gdsfactory as gf

    p = gf.path.straight()
    copied_cs = gf.cross_section.strip().copy()
    gf.path.extrude(p, cross_section=copied_cs)


if __name__ == "__main__":
    import gdsfactory as gf

    p = gf.path.straight()
    copied_cs = gf.cross_section.strip().copy()
    c = gf.path.extrude(p, cross_section=copied_cs)
    c.show()

    # p = gf.path.straight()
    # x = CrossSection(name="strip", layer=(1, 0), width=0.5)
    # x = x.copy(width=3)
    # c = p.extrude(x)
    # c.show()

    # P = gf.path.euler(radius=10, use_eff=True)
    # P = euler()
    # P = gf.Path()
    # P.append(gf.path.straight(length=5))
    # P.append(gf.path.arc(radius=10, angle=90))
    # P.append(gf.path.spiral())

    # Create a blank CrossSection

    # X = pin(width=0.5, width_i=0.5)
    # x = strip(width=0.5)

    # X = strip_heater_metal_undercut()
    # X = metal1()
    # X = pin(layer_via=LAYER.VIAC, via_offsets=(-2, 2))
    # X = pin()
    # X = strip_heater_doped()

    # x1 = strip_rib_tip()
    # x2 = rib_heater_doped_via_stack()
    # X = gf.path.transition(x1, x2)
    # P = gf.path.straight(npoints=100, length=10)

    # X = CrossSection()

    # X = rib_heater_doped(with_bot_heater=False, decorator=add_pins_siepic_optical)
    # P = gf.path.straight(npoints=100, length=10)
    # c = gf.path.extrude(P, X)

    # print(x1.to_dict())
    # print(x1.name)
    # c = gf.path.component(P, strip(width=2, layer=LAYER.WG, cladding_offset=3))
    # c = gf.add_pins(c)
    # c << gf.components.bend_euler(radius=10)
    # c << gf.components.bend_circular(radius=10)
    # c.pprint_ports()
    # c.show(show_ports=False)
