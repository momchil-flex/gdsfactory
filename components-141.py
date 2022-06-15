import gdsfactory as gf

c = gf.components.spiral(port_spacing=500.0, length=10000.0, parity=1, port=(0, 0), direction='WEST', layer='WG', layer_cladding='WGCLAD', cladding_offset=3.0, wg_width=0.5, radius=10.0)
c.plot()