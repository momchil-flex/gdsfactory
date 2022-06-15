import gdsfactory as gf

c = gf.components.via_corner(cross_section=((functools.partial(<cyfunction cross_section at 0x7f0a48561930>, layer='M2', width=10.0, port_names=('e1', 'e2'), port_types=('electrical', 'electrical')), (0, 180)), (functools.partial(<cyfunction cross_section at 0x7f0a48561930>, layer='M3', width=10.0, port_names=('e1', 'e2'), port_types=('electrical', 'electrical')), (90, 270))), layers_labels=('m2', 'm3'))
c.plot()