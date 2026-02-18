"""This module contains functions for tidal correction and transformation of gravity and height etc."""

from math import cos, sin, pi
from pathlib import Path

from astropy import constants as const
from astropy.coordinates import AltAz, solar_system_ephemeris, EarthLocation, get_body
from astropy.time import Time
import astropy.units as u
import pandas as pd
import pyproj

import fire.api.geodetic_levelling.geophysical_parameters as geo_p


def apply_tidal_corrections_to_height_diff(
    height_diff: float,
    point_from_lat: float,
    point_from_long: float,
    point_to_lat: float,
    point_to_long: float,
    epoch_obs: pd.Timestamp,
    tidal_system: str,
    use_approx_tidal_formulas: bool = False,
    grid_inputfolder: Path = None,
    gravitymodel: str = None,
) -> tuple[float, float]:
    """Apply tidal corrections to a metric height difference.

    Applies tidal corrections to a metric height difference and returns the corrected
    height difference and the correction itself in a tuple.

    The application of tidal corrections to a metric height difference implies that all periodic
    tidal effects are removed, whereas the permanent tidal effects are removed or retained
    (in whole or in part) depending on the specified tidal system.

    Reference:
    Klaus Schmidt, The Danish height system DVR90, pp. app 15-16.
    National Survey and Cadastre, 2000

    Args:
    height_diff: float, metric height difference to be tidally corrected
    point_from_lat: float, latitude of from point in units of degrees
    point_from_long: float, longitude of from point in units of degrees
    point_to_lat: float, latitiude of to point in units of degrees
    point_to_long: float, longitude of to point in units of degrees
    epoch_obs: pd.Timestamp, epoch/time of observation (format: yyyy-mm-dd hh:mm:ss)
    tidal_system: str, tidal system of output height difference, "non", "mean" or "zero"
    for non-tidal, mean tide or zero tide
    use_approx_tidal_formulas: bool = False, optional parameter, determines whether approx or
    rigorous formulas are used for tidal transformation of a height difference/gravity.
    Only relevant if tidal system is mean tide or zero tide. By default rigorous formulas are used
    grid_inputfolder: Path = None, optional parameter, folder for input grid, i.e. gravity model,
    only relevant if rigorous tidal formulas are used and tidal system is mean tide or zero tide
    gravitymodel: str = None, optional parameter, grid-based model providing gravity in units of
    mGal (1 mGal = 10^-5 m/s^2), must be in GeoTIFF or GTX file format, only relevant if
    rigorous tidal formulas are used and tidal system is mean tide or zero tide

    Returns:
    tuple[float, float], a tuple containing the corrected height difference and
    the correction itself in units of meters

    Raises:
    ?

    TO DO: Højere grad af konsistens fsva. vinkelmål deg/rad?
    TO DO: Split op i mindre underfunktioner
    TO DO: Take daylight saving time into account
    TO DO: Handling of small inconsistence regarding tilt factor/diminution coefficient (0.7 vs. 0.68)
    """
    allowed_tidal_systems = ["non", "mean", "zero"]
    if not tidal_system in allowed_tidal_systems:
        raise ValueError(
            f"Function apply_tidal_corrections_to_height_diff: The argument for parameter tidal_system\n\
            must be one of {', '.join(allowed_tidal_systems)}"
        )

    if (
        tidal_system != "non"
        and not use_approx_tidal_formulas
        and ((gravitymodel is None) or (grid_inputfolder is None))
    ):
        exit(
            "Function apply_tidal_corrections_to_height_diff: Wrong arguments for\n\
            parameter use_approx_tidal_formulas and/or gravitymodel and/or grid_inputfolder."
        )

    # Calculation of levelling section length and azimuth
    # Azimuth is calculated clockwise from north; interval of azimuth: [-180 deg; 180 deg]
    geod = pyproj.Geod(ellps="GRS80")
    azimuth_forward, azimuth_back, section_length = geod.inv(
        point_from_long, point_from_lat, point_to_long, point_to_lat
    )

    # Conversion of levelling section azimuth to radians
    azimuth_forward = azimuth_forward * 2 * (pi / 360)

    # Observation epoch in UTC
    # Daylight saving time is not taken into account
    epoch_obs = epoch_obs + pd.Timedelta(hours=-1)
    t = Time(epoch_obs, scale="utc")

    # Mean geographic coordinates
    mean_lat = (point_from_lat + point_to_lat) / 2
    mean_long = (point_from_long + point_to_long) / 2

    # Conversion of mean geographic coordinates to cartesian ITRS coordinates
    loc = EarthLocation(lat=mean_lat * u.deg, lon=mean_long * u.deg, height=0 * u.m)

    # Apparent positions (ra, dec, dist) of the Moon and Sun in GCRS
    with solar_system_ephemeris.set("jpl"):
        moon = get_body("moon", t, loc)
        sun = get_body("sun", t, loc)

    # Altitude and azimuth of the Moon and Sun without refraction effects
    # Interval of altitude: [-pi/2; pi/2]
    # Azimuth is calculated clockwise from north; interval of azimuth: [0; 2*pi]
    altazframe = AltAz(obstime=t, location=loc, pressure=0)
    moon_altaz = moon.transform_to(altazframe)
    sun_altaz = sun.transform_to(altazframe)
    altitude_moon = moon_altaz.alt.radian
    azimuth_moon = moon_altaz.az.radian
    altitude_sun = sun_altaz.alt.radian
    azimuth_sun = sun_altaz.az.radian

    # Conversion of altitude to zenith distance
    zenith_dist_moon = (pi / 2) - altitude_moon
    zenith_dist_sun = (pi / 2) - altitude_sun

    # Calculation of tidal corrections due to the Moon and Sun in units of 1e-8 m
    tidal_corr_moon = (
        section_length
        * 8.5
        * sin(2 * zenith_dist_moon)
        * cos(azimuth_moon - azimuth_forward)
    )
    tidal_corr_sun = (
        section_length
        * 3.9
        * sin(2 * zenith_dist_sun)
        * cos(azimuth_sun - azimuth_forward)
    )
    # Tidal correction of height_diff (0.7 is diminution coefficient corresponding to a yielding
    # Earth). This correction removes all tidals effects caused by the Moon and Sun, i.e. both
    # periodic and permanent tidal effects and both direct and indirect effects (caused by
    # a yielding/deforming Earth). Consequently, the corrected height difference is in
    # non-tidal system
    tidal_corr = (tidal_corr_moon + tidal_corr_sun) * 0.7 * 1e-8
    height_diff_corrected = height_diff + tidal_corr

    if tidal_system == "non":
        return (height_diff_corrected, tidal_corr)

    # If the specified tidal system is mean tide or zero tide, the corrected height difference
    # is transformed from non-tidal to the tidal system specified
    elif tidal_system == "mean":
        transformation = "non_to_mean"

    elif tidal_system == "zero":
        transformation = "non_to_zero"

    height_diff_corrected = transform_height_diff_from_tidal_system_to_tidal_system(
        height_diff_corrected,
        transformation,
        point_from_lat,
        point_to_lat,
        point_from_long,
        point_to_long,
        use_approx_tidal_formulas,
        grid_inputfolder,
        gravitymodel,
    )

    tidal_corr = height_diff_corrected - height_diff

    return (height_diff_corrected, tidal_corr)


def calculate_perm_tidal_gravitation(
    latitude: float,
    celestial_body: str,
) -> float:
    """Calculate the permanent tidal gravitation assuming a rigid Earth.

    Calculates the permanent tidal gravitation caused by the Moon or the Sun assuming a rigid Earth
    and returns the result as a float.

    Reference:
    Martin Ekman, The impact of geodynamic phenomena on systems for height and gravity,
    p. 120, eq. (8). Nordic Geodetic Commission, 1988

    Args:
    latitude: float, latitude for which the permanent tidal gravitation is calculated,
    in units of degrees
    celestial_body: str, celestial body for which the permanent tidal gravitation is calculated,
    "moon" or "sun"

    Returns:
    float, the permanent tidal gravitation in units of m/s^2

    Raises:
    ?
    """
    # The permanent tidal gravitation is given by -dW/dr, i.e.
    # minus the partial derivative of the permanent tidal potential wrt Earth radius
    perm_tidal_gravitation = -(2 / geo_p.radius_earth) * calculate_perm_tidal_potential(
        latitude, celestial_body
    )

    return perm_tidal_gravitation


def calculate_perm_tidal_potential(
    latitude: float,
    celestial_body: str,
) -> float:
    """Calculate the permanent tidal potential assuming a rigid Earth.

    Calculates the permanent tidal potential caused by the Moon or the Sun assuming a rigid Earth
    and returns the result as a float.

    Reference:
    Martin Ekman, The impact of geodynamic phenomena on systems for height and gravity,
    p. 119, eq. (5). Nordic Geodetic Commission, 1988

    Args:
    latitude: float, latitude for which the permanent tidal potential is calculated,
    in units of degrees
    celestial_body: str, celestial body for which the permanent tidal potential is calculated,
    "moon" or "sun"

    Returns:
    float, the permanent tidal potential in units of m^2/s^2

    Raises:
    ?
    """
    # Conversion of latitude to radians
    latitude = (latitude / 360) * 2 * pi

    # Inclination dependent term
    inclination_term = (3 / 2) * (sin(geo_p.epsilon)) ** 2 - 1

    # Latitude dependent term
    latitude_term = 3 * (sin(latitude)) ** 2 - 1

    if celestial_body == "moon":

        perm_tidal_potential = (
            (
                (const.G.value * geo_p.moon_mass * geo_p.radius_earth**2)
                / (4 * geo_p.moon_dist**3)
            )
            * inclination_term
            * latitude_term
        )

    if celestial_body == "sun":

        perm_tidal_potential = (
            (
                (const.G.value * const.M_sun.value * geo_p.radius_earth**2)
                / (4 * const.au.value**3)
            )
            * inclination_term
            * latitude_term
        )

    return perm_tidal_potential


def calculate_perm_tidal_deformation_geoid(
    latitude: float,
    longitude: float,
    celestial_body: str,
    grid_inputfolder: Path,
    gravitymodel: str,
) -> float:
    """Calculate the permanent tidal deformation of the geoid assuming a rigid Earth.

    Calculates the permanent tidal deformation of the geoid caused by the Moon or the Sun
    assuming a rigid Earth and returns the result as a float.

    References:
    Martin Ekman, The impact of geodynamic phenomena on systems for height and gravity,
    p. 120, eq. (6). Nordic Geodetic Commission, 1988

    Markku Heikkinen, On the tide-generating forces, pp. 8-9, Publications of the Finnish Geodetic
    Institute No. 85, 1978

    The gravity model used for calculating the permanent tidal deformation of the geoid is assumed
    to be in zero tide system as this is the conventional tide system for gravity.

    According to Bruns' formula the permanent tidal deformation of the geoid can be found as
    N = T / g, where T is the permanent tidal potential (the disturbing potential) and g is the
    magnitude of the gradient of the Earths undisturbed potential (i.e. non-tidal gravity).
    Therefore, the gravity interpolated from the gravity model is transformed from the zero tide
    system to non-tidal system, although the effect on a tidally corrected height difference
    is very small.

    Args:
    latitude: float, latitude for which the permanent tidal deformation of the geoid is calculated,
    in units of degrees
    longitude: float, longitude for which the permanent tidal deformation of the geoid is calculated,
    in units of degrees
    celestial_body: str, celestial body for which the permanent tidal deformation of the geoid
    is calculated, "moon" or "sun"
    grid_inputfolder: Path, folder for input grid, i.e. gravity model
    gravitymodel: str, grid-based model providing gravity in units of mGal (1 mGal = 10^-5 m/s^2),
    must be in GeoTIFF or GTX file format, e.g. "dk-g-direkte-fra-gri-thokn.tif"

    Returns:
    float, the permanent tidal deformation of the geoid in units of m

    Raises:
    ?

    TO DO: Hvad sker der, hvis man i stedet bruger normaltyngder eller en konstant værdi for tyngden?
    Hvad er gjort ifm. udledningen af Ekmans approksimative formler?
    """
    gravity = interpolate_gravity(latitude, longitude, grid_inputfolder, gravitymodel)

    # Gravity is transformed from zero tide to non-tidal
    gravity = transform_gravity_from_tidal_system_to_tidal_system(
        gravity,
        latitude,
        "zero_to_non",
        use_approx_tidal_formulas=False,
    )

    # Permanent tidal potential
    perm_tidal_potential = calculate_perm_tidal_potential(latitude, celestial_body)

    # Permanent tidal deformation of the geoid
    perm_tidal_deformation_geoid = perm_tidal_potential / gravity

    return perm_tidal_deformation_geoid


def transform_gravity_from_tidal_system_to_tidal_system(
    gravity: float,
    latitude: float,
    transformation: str,
    use_approx_tidal_formulas: bool = False,
) -> float:
    """Transform gravity from one tidal system to another tidal system.

    Transforms gravity from one tidal system to another tidal system and returns the
    result as a float.

    Reference:
    Martin Ekman, The impact of geodynamic phenomena on systems for height and gravity,
    pp. 124-128, eq. (19), (20), (22). Nordic Geodetic Commission, 1988

    Args:
    gravity: float, gravity to be transformed from one tidal system to another, in units of m/s^2
    latitude: float, latitude at which the input gravity is measured, in units of degrees
    transformation: str, specification of source and target tidal system, e.g. "non_to_mean"
    use_approx_tidal_formulas: bool = False, optional parameter, determines whether approx or
    rigorous formulas are used for tidal transformation of gravity. By default rigorous formulas
    are used

    Returns:
    float, the transformed gravity in units of m/s^2

    Raises:
    ?
    """
    # Transformation of gravity using approx formula
    if use_approx_tidal_formulas:
        gravity_transformed = (
            approx_transform_gravity_from_tidal_system_to_tidal_system(
                gravity, latitude, transformation
            )
        )

        return gravity_transformed

    # Transformation of gravity using rigorous formulas
    # The permanent tidal gravitation assuming a rigid Earth in units of m/s^2
    perm_tidal_gravitation = (calculate_perm_tidal_gravitation(latitude, "moon")) + (
        calculate_perm_tidal_gravitation(latitude, "sun")
    )

    # The permanent tidal gravitation for a deformable Earth in units of m/s^2
    perm_tidal_gravitation_deform = geo_p.delta * perm_tidal_gravitation

    if transformation == "non_to_mean":
        gravity_transformed = gravity + perm_tidal_gravitation_deform

    elif transformation == "non_to_zero":
        gravity_transformed = (
            gravity + perm_tidal_gravitation_deform - perm_tidal_gravitation
        )

    elif transformation == "mean_to_non":
        gravity_transformed = gravity - perm_tidal_gravitation_deform

    elif transformation == "mean_to_zero":
        gravity_transformed = gravity - perm_tidal_gravitation

    elif transformation == "zero_to_non":
        gravity_transformed = (
            gravity - perm_tidal_gravitation_deform + perm_tidal_gravitation
        )

    elif transformation == "zero_to_mean":
        gravity_transformed = gravity + perm_tidal_gravitation

    return gravity_transformed


def approx_transform_gravity_from_tidal_system_to_tidal_system(
    gravity: float,
    latitude: float,
    transformation: str,
) -> float:
    """Transform gravity from one tidal system to another tidal system using approx formula.

    Transforms gravity from one tidal system to another tidal system using approx formula
    and returns the result as a float.

    Reference:
    Martin Ekman, The impact of geodynamic phenomena on systems for height and gravity,
    p. 130, eq. (26), (27), (28). Nordic Geodetic Commission, 1988

    Args:
    gravity: float, gravity to be transformed from one tidal system to another, in units of m/s^2
    latitude: float, latitude at which the input gravity is measured, in units of degrees
    transformation: str, specification of source and target tidal system, e.g. "non_to_mean"

    Returns:
    float, the transformed gravity in units of m/s^2

    Raises:
    ?
    """
    # Conversion of latitude to radians
    latitude = (latitude / 360) * 2 * pi

    # Nedenstående skal tjekkes yderligere
    latitude_dependent_term = (-30.4 + 91.2 * (sin(latitude) ** 2)) * 1e-8

    if transformation == "non_to_mean":
        gravity_transformed = gravity + geo_p.delta * latitude_dependent_term

    elif transformation == "non_to_zero":
        gravity_transformed = gravity + (geo_p.delta - 1) * latitude_dependent_term

    elif transformation == "mean_to_non":
        gravity_transformed = gravity - geo_p.delta * latitude_dependent_term

    elif transformation == "mean_to_zero":
        gravity_transformed = gravity - latitude_dependent_term

    elif transformation == "zero_to_non":
        gravity_transformed = gravity - (geo_p.delta - 1) * latitude_dependent_term

    elif transformation == "zero_to_mean":
        gravity_transformed = gravity + latitude_dependent_term

    return gravity_transformed


def transform_height_from_tidal_system_to_tidal_system(
    height: float,
    latitude: float,
    longitude: float,
    transformation: str,
    grid_inputfolder: Path,
    gravitymodel: str,
) -> float:
    """Transform a geophysical height from one tidal system to another tidal system.

    Transforms a geophysical height above the geoid (e.g. a levelled height) from one tidal system
    to another tidal system and returns the result as a float.

    The height to be transformed is assumed to have been tidally corrected
    (i.e. referred to a specific tidal system) before being transformed to another tidal system
    using this function.

    Reference:
    Martin Ekman, The impact of geodynamic phenomena on systems for height and gravity,
    p. 128-129, eq. (24), (25). Nordic Geodetic Commission, 1988

    Args:
    height: float, height to be transformed from one tidal system to another, in units of m
    latitude: float, latitude of input height, in units of degrees
    longitude: float, longitude of input height, in units of degrees
    transformation: str, specification of source and target tidal system, e.g. "non_to_mean"
    grid_inputfolder: Path, folder for input grid, i.e. gravity model
    gravitymodel: str, grid-based model providing gravity in units of mGal (1 mGal = 10^-5 m/s^2),
    must be in GeoTIFF or GTX file format, e.g. "dk-g-direkte-fra-gri-thokn.tif"

    Returns:
    float, the transformed height in units of m

    Raises:
    ?

    NB: Hvilken rolle spiller det om højden er Helmert-højde, normalhøjde? Nok ingen?
    """
    # The permanent tidal deformation of the geoid assuming a rigid Earth in units of m
    perm_tidal_deformation_geoid_moon = calculate_perm_tidal_deformation_geoid(
        latitude,
        longitude,
        "moon",
        grid_inputfolder,
        gravitymodel,
    )

    perm_tidal_deformation_geoid_sun = calculate_perm_tidal_deformation_geoid(
        latitude,
        longitude,
        "sun",
        grid_inputfolder,
        gravitymodel,
    )

    perm_tidal_deformation_geoid = (
        perm_tidal_deformation_geoid_moon + perm_tidal_deformation_geoid_sun
    )

    # Nedentående skal verificeres
    # The permanent tidal deformation of the geoid for a deformable Earth in units of m
    perm_tidal_deformation_geoid_deform = geo_p.delta * perm_tidal_deformation_geoid

    if transformation == "non_to_mean":
        height_transformed = height + perm_tidal_deformation_geoid_deform

    elif transformation == "non_to_zero":
        height_transformed = (
            height + perm_tidal_deformation_geoid_deform - perm_tidal_deformation_geoid
        )

    elif transformation == "mean_to_non":
        height_transformed = height - perm_tidal_deformation_geoid_deform

    elif transformation == "mean_to_zero":
        height_transformed = height - perm_tidal_deformation_geoid

    elif transformation == "zero_to_non":
        height_transformed = (
            height - perm_tidal_deformation_geoid_deform + perm_tidal_deformation_geoid
        )

    elif transformation == "zero_to_mean":
        height_transformed = height + perm_tidal_deformation_geoid

    return height_transformed


def transform_height_diff_from_tidal_system_to_tidal_system(
    height_diff: float,
    transformation: str,
    point_from_lat: float,
    point_to_lat: float,
    point_from_long: float = None,
    point_to_long: float = None,
    use_approx_tidal_formulas: bool = False,
    grid_inputfolder: Path = None,
    gravitymodel: str = None,
) -> float:
    """Transform a geophysical height difference from one tidal system to another tidal system.

    Transforms a geophysical height difference above the geoid (e.g. a levelled height) from one
    tidal system to another tidal system and returns the result as a float.

    The height difference to be transformed is assumed to have been tidally corrected
    (i.e. referred to a specific tidal system) before being transformed to another tidal system
    using this function.

    Reference:
    Martin Ekman, The impact of geodynamic phenomena on systems for height and gravity,
    pp. 128-129, eq. (24), (25). Nordic Geodetic Commission, 1988

    Args:
    height_diff: float, geophysical height difference to be transformed from one tidal system
    to another, in units of m
    transformation: str, specification of source and target tidal system, e.g. "non_to_mean"
    point_from_lat: float, latitude of from point in units of degrees
    point_to_lat: float, latitiude of to point in units of degrees
    point_from_long: float = None, optional parameter, longitude of from point in units of degrees,
    only relevant if rigorous tidal formulas are used
    point_to_long: float = None, optional parameter, longitude of to point in units of degrees,
    only relevant if rigorous tidal formulas are used
    use_approx_tidal_formulas: bool = False, optional parameter, determines whether approx or
    rigorous formulas are used for tidal transformation of a height difference/gravity. By default
    rigorous formulas are used
    grid_inputfolder: Path = None, optional parameter, folder for input grid, i.e. gravity model,
    only relevant if rigorous tidal formulas are used
    gravitymodel: str = None, optional parameter, grid-based model providing gravity in units of
    mGal (1 mGal = 10^-5 m/s^2), must be in GeoTIFF or GTX file format, only relevant if
    rigorous tidal formulas are used

    Returns:
    float, the transformed height difference in units of m

    Raises:
    ?

    NB: Hvor meget betyder højden af højdeforskellens fra-/til-punkter? Nok ikke ret meget
    eftersom de numeriske/approksimative formler ikke tager højde herfor
    """
    # Transformation of height difference using approx formula
    if use_approx_tidal_formulas:
        height_diff_transformed = (
            approx_transform_height_diff_from_tidal_system_to_tidal_system(
                height_diff,
                point_from_lat,
                point_to_lat,
                transformation,
            )
        )

        return height_diff_transformed

    # Transformation of height difference using rigorous formulas
    height_diff_transformed = (
        height_diff
        + transform_height_from_tidal_system_to_tidal_system(
            0,
            point_to_lat,
            point_to_long,
            transformation,
            grid_inputfolder,
            gravitymodel,
        )
        - transform_height_from_tidal_system_to_tidal_system(
            0,
            point_from_lat,
            point_from_long,
            transformation,
            grid_inputfolder,
            gravitymodel,
        )
    )

    return height_diff_transformed


def approx_transform_height_diff_from_tidal_system_to_tidal_system(
    height_diff: float,
    point_from_lat: float,
    point_to_lat: float,
    transformation: str,
) -> float:
    """Transform a geophysical height difference from one tidal system to another tidal system
    using approx formula.

    Transforms a geophysical height difference above the geoid (e.g. a levelled height difference)
    from one tidal system to another tidal system using approx formula and returns the result
    as a float.

    The height difference to be transformed is assumed to have been tidally corrected
    (i.e. referred to a specific tidal system) before being transformed to another tidal system
    using this function.

    Reference:
    Martin Ekman, The impact of geodynamic phenomena on systems for height and gravity,
    p. 131, eq. (29), (30), (31). Nordic Geodetic Commission, 1988

    Args:
    height_diff: float, geophysical height difference to be transformed from one tidal system
    to another, in units of m
    point_from_lat: float, latitude of from point in units of degrees
    point_to_lat: float, latitiude of to point in units of degrees
    transformation: str, specification of source and target tidal system, e.g. "non_to_mean"

    Returns:
    float, the transformed height difference in units of m

    Raises:
    ?
    """
    # Conversion of latitudes to radians
    point_from_lat = (point_from_lat / 360) * 2 * pi
    point_to_lat = (point_to_lat / 360) * 2 * pi

    # Nedenstående skal tjekkes yderligere, herunder at formlerne virker over alt på Jorden
    # (det gør de vist)
    latitude_dependent_term = (
        29.6 * (sin(point_from_lat) ** 2 - sin(point_to_lat) ** 2) * 1e-2
    )

    if transformation == "non_to_mean":
        height_diff_transformed = height_diff + geo_p.gamma * latitude_dependent_term

    elif transformation == "non_to_zero":
        height_diff_transformed = (
            height_diff + (geo_p.gamma - 1) * latitude_dependent_term
        )

    elif transformation == "mean_to_non":
        height_diff_transformed = height_diff - geo_p.gamma * latitude_dependent_term

    elif transformation == "mean_to_zero":
        height_diff_transformed = height_diff - latitude_dependent_term

    elif transformation == "zero_to_non":
        height_diff_transformed = (
            height_diff - (geo_p.gamma - 1) * latitude_dependent_term
        )

    elif transformation == "zero_to_mean":
        height_diff_transformed = height_diff + latitude_dependent_term

    return height_diff_transformed


from fire.api.geodetic_levelling.metric_to_gpu_transformation import (
    interpolate_gravity,
)
