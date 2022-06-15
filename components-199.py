import gdsfactory as gf

c = gf.components.wire_straight(length=10.0, npoints=2, with_bbox=False, cross_section='metal3')
c.plot()