import gdsfactory as gf

c = gf.components.grating_coupler_circular(taper_angle=30.0, taper_length=10.0, length=30.0, period=1.0, fill_factor=0.7, n_periods=30, bias_gap=0, port=(0.0, 0.0), layer_cladding='WGCLAD', direction='EAST', polarization='te', wavelength=1.55, fiber_marker_width=11.0, fiber_marker_layer='TE', cladding_offset=2.0, cross_section='strip')
c.plot()