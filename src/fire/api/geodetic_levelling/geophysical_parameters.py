"""This module contains various geophysical parameters and constants required
for tidal correction and transformation of gravity and height etc.
"""

from math import pi

# Inclination of the ecliptic/the lunar orbit in radians
epsilon = (23 + (27 / 60)) * (1 / 360) * 2 * pi

# Geocentric distance to the Moon in units of m
moon_dist = 3.84399 * 1e8

# Mass of the Moon in units of kg
moon_mass = 7.346 * 1e22

# Mean radius of the Earth in units of m
radius_earth = 6371000

# Love numbers
h = 0.62
k = 0.30

# Tilt factor
gamma = 1 + k - h

# Gravimetric factor
delta = 1 + h - (3 / 2) * k

# Defining constants for Geodetic Reference System 1980 (GRS80)
# Major semi-axis of the reference ellipsoid in units of m
a_GRS80 = 6378137

# Gravitational mass constant of the Earth in units of m^3/s^2
GM_GRS80 = 3986005 * 1e8

# Dynamic form factor
J2_GRS80 = 108263 * 1e-8

# Angular velocity of the Earth’s rotation in units of rad/s
omega_GRS80 = 7292115 * 1e-11

# Derived constants for Geodetic Reference System 1980 (GRS80)
# Minor semi-axis of the reference ellipsoid in units of m
b_GRS80 = 6356752.3141

# Flattening of the reference ellipsoid
f_GRS80 = 0.00335281068118

# m = (normal_gravity^2*a^2*b)/(G*M)
m_GRS80 = 0.00344978600308

# Normal gravity at equator in units of m/s^2
normal_gravity_equator_GRS80 = 9.7803267715
