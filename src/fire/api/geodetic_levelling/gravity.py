"""This module contains functions for interpolation and calculation of gravity etc."""

from math import sin, pi
from pathlib import Path

import pyproj

import fire.api.geodetic_levelling.geophysical_parameters as geo_p


def interpolate_gravity(
    latitude: float,
    longitude: float,
    grid_inputfolder: Path,
    gravitymodel: str,
) -> float:
    """Interpolate in gravity model.

    Interpolates bilinearly in a grid-based gravity model and returns the result as a float.

    Args:
    latitude: float, latitude for which gravity is interpolated, in units of degrees
    longitude: float, longitude for which gravity is interpolated, in units of degrees
    grid_inputfolder: Path, folder for input grid, i.e. gravity model
    gravitymodel: str, grid-based model providing gravity in units of mGal (1 mGal = 10^-5 m/s^2),
    must be in GeoTIFF or GTX file format, e.g. "dk-g-direkte-fra-gri-thokn.tif"

    Returns:
    float, interpolated gravity in units of m/s^2

    Raises:
    ?

    TO DO: Lav seperat funktion create_pyproj_transformer, således at Transformer-objektet
    ikke oprettes hver gang der interpoleres i grid-modellen? transformer: pyproj.Transformer
    """
    pyproj.datadir.append_data_dir(grid_inputfolder)

    # Transformer object for interpolation in gravity model
    transformer = pyproj.Transformer.from_pipeline(
        f"+proj=vgridshift +grids={gravitymodel}"
    )

    # Interpolated gravity in units of m/s^2
    gravity = transformer.transform(longitude, latitude, 0)[2] * 1e-5 * -1

    return gravity


def calculate_normal_gravity(
    latitude: float,
) -> float:
    """Calculate normal gravity at the GRS80 ellipsoid.

    Calculates normal gravity at the GRS80 ellipsoid.

    Reference:
    Johannes Ihde et al., Conventions for the Definition and Realization of a
    European Vertical Reference System (EVRS) - EVRS Conventions 2007, p. 10, eq. (A-1).
    EUREF, 2019

    H. Moritz, GEODETIC REFERENCE SYSTEM 1980

    TO DO: Tidal system of calculated normal gravity?

    Args:
    latitude: float, latitude for which normal gravity is calculated, in units of degrees

    Returns:
    float, calculated normal gravity in units of m/s^2

    Raises:
    ?
    """
    # Conversion of latitude to radians
    latitude = (latitude / 360) * 2 * pi

    # Coefficients of series expansion for calculation of normal gravity
    a = 0.0052790414
    b = 0.0000232718
    c = 0.0000001262
    d = 0.0000000007

    normal_gravity = geo_p.normal_gravity_equator_GRS80 * (
        1
        + a * sin(latitude) ** 2
        + b * sin(latitude) ** 4
        + c * sin(latitude) ** 6
        + d * sin(latitude) ** 8
    )

    return normal_gravity


def calculate_average_normal_gravity(
    latitude: float,
    normal_height: float,
) -> float:
    """Calculate average normal gravity.

    Calculates the average normal gravity along the normal plumb line between
    the GRS80 ellipsoid and the telluroid.

    Reference:
    Johannes Ihde et al., Conventions for the Definition and Realization of a
    European Vertical Reference System (EVRS) - EVRS Conventions 2007, p. 10, eq. (A-2).
    EUREF, 2019

    H. Moritz, GEODETIC REFERENCE SYSTEM 1980

    Args:
    latitude: float, latitude for which average normal gravity is calculated, in units of degrees
    normal_height: float, approximate normal height, in units of meters

    Returns:
    float, calculated average normal gravity in units of m/s^2

    Raises:
    ?

    TO DO: Handling of tidal system?, Tidal system of calculated average normal gravity?
    """
    # Calculation of normal gravity at the ellipsoid
    normal_gravity = calculate_normal_gravity(latitude)

    # Conversion of latitude to radians
    latitude = (latitude / 360) * 2 * pi

    # Calculation of average normal gravity
    r = 1 + geo_p.f_GRS80 + geo_p.m_GRS80 - 2 * geo_p.f_GRS80 * sin(latitude) ** 2
    s = normal_height / geo_p.a_GRS80

    average_normal_gravity = normal_gravity * (1 - r * s + s**2)

    return average_normal_gravity
