"""This module contains functions for transformation of metric heights or height differences
to geopotential units or vice versa.
"""

from math import isnan
from pathlib import Path
import copy

import pandas as pd

from fire.api.geodetic_levelling.gravity import (
    interpolate_gravity,
    calculate_average_normal_gravity,
)

from fire.api.geodetic_levelling.tidal_transformation import (
    transform_gravity_from_tidal_system_to_tidal_system,
)

from fire.api.niv.datatyper import (
    NivKote,
)


def convert_metric_height_diff_to_geopotential_height_diff(
    height_diff: float,
    point_from_lat: float,
    point_from_long: float,
    point_to_lat: float,
    point_to_long: float,
    grid_inputfolder: Path,
    gravitymodel: str,
    tidal_system: str | None,
    use_approx_tidal_formulas: bool = False,
) -> tuple[float, float]:
    """Convert a metric height difference to a geopotential height difference.

    Converts a metric height difference to a geopotential height difference (in units of gpu)
    and returns the converted height difference and the m2gpu multiplication factor in a tuple.

    The gravity model used for the conversion is assumed to be in zero tide system as this is
    the conventional tide system for gravity.

    If the input height difference is in the zero tide system, the gravity interpolated from the
    gravity model is not tidally transformed.

    If the input height difference is in non-tidal or mean tide system, the gravity interpolated
    from the gravity model is transformed from the zero tide system to the tidal system of the
    input height difference.

    If the input height difference is not corrected for tidal effects, the gravity interpolated
    from the gravity model is transformed from the zero tide system to the mean tide system.

    Args:
    height_diff: float, metric height difference to be converted to gpu
    point_from_lat: float, latitude of from point in units of degrees
    point_from_long: float, longitude of from point in units of degrees
    point_to_lat: float, latitiude of to point in units of degrees
    point_to_long: float, longitude of to point in units of degrees
    grid_inputfolder: Path, folder for input grid, i.e. gravity model
    gravitymodel: str, gravity model used for the conversion of a height difference to gpu,
    must be in GeoTIFF or GTX file format, e.g. "dk-g-direkte-fra-gri-thokn.tif"
    tidal_system: str|None, tidal system of input height difference, i.e. "non", "mean" or "zero"
    for non-tidal, mean tide or zero tide or None if the input height difference is not corrected
    for tidal effects
    use_approx_tidal_formulas: bool = False, optional parameter, determines whether approx or
    rigorous formulas are used for tidal transformation of gravity. By default rigorous formulas
    are used

    Returns:
    tuple[float, float], a tuple containing the converted height difference
    in units of gpu (1 gpu = 10 m^2/s^2) and the m2gpu multiplication factor in units of m/s^2

    Raises:
    ?
    """
    # Point_from and point_to gravity in units of m/s^2
    point_from_gravity = interpolate_gravity(
        point_from_lat,
        point_from_long,
        grid_inputfolder,
        gravitymodel,
    )

    point_to_gravity = interpolate_gravity(
        point_to_lat,
        point_to_long,
        grid_inputfolder,
        gravitymodel,
    )

    # Interpolated gravity is tidally transformed if tidal system of input height difference
    # is different than zero tide
    if tidal_system != "zero":
        if tidal_system == "non":
            transformation = "zero_to_non"

        elif tidal_system == "mean" or tidal_system is None:
            transformation = "zero_to_mean"

        point_from_gravity = transform_gravity_from_tidal_system_to_tidal_system(
            point_from_gravity,
            point_from_lat,
            transformation,
            use_approx_tidal_formulas,
        )

        point_to_gravity = transform_gravity_from_tidal_system_to_tidal_system(
            point_to_gravity, point_to_lat, transformation, use_approx_tidal_formulas
        )

    # Mean gravity in units of m/s^2
    mean_gravity = (point_from_gravity + point_to_gravity) / 2

    # Conversion of height_diff to geopotential units (1 gpu = 10 m^2/s^2)
    m2gpu_factor = mean_gravity * 0.1
    height_diff = height_diff * m2gpu_factor

    return (height_diff, m2gpu_factor)


def convert_geopotential_height_to_normal_height(
    height: float,
    latitude: float,
    conversion: str,
    approx_normal_height: float = 0,
    iterate: bool = True,
) -> tuple[float, float]:
    """Convert a geopotential height to normal height or vice versa.

    Converts a geopotential height to GRS80 normal height or vice versa.

    References:
    Johannes Ihde et al., Conventions for the Definition and Realization of a
    European Vertical Reference System (EVRS) - EVRS Conventions 2007. EUREF, 2019

    H. Moritz, GEODETIC REFERENCE SYSTEM 1980

    If a geopotential height is to be converted to normal height, an a priori
    normal height is required. If no argument is passed for the parameter approx_normal_height,
    a default value of zero will be used as a priori normal height. By default, the
    normal height is calculated iteratively until the difference between the current and previous
    iteration step is less than 0.01 mm. If the normal height is calculated in only one step using
    the default a priori normal height, an error of several millimeters can occur. Therefore,
    it is recommended to calculate the normal height iteratively if no a priori normal height is
    passed.

    TO DO: Handling of tidal corrections/systems?
    TO DO: Change the condition for iteration to a looser one, based on the formulae for normal height

    Args:
    height: float, input/source height to be converted, in units of gpu (1 gpu = 10 m^2/s^2) if a
    geopotential height or in units of m if a normal height
    latitude: float, latitude of input/source height, in units of degrees
    conversion: str, specification of source and target height, "geopot_to_normal" or
    "normal_to_geopot"
    approx_normal_height: float = 0, optional parameter, approx normal height in units of m,
    only relevant if a geopotential height is to be converted to normal height, default value is 0
    iterate: bool = True, optional parameter, determines whether or not the output/target
    normal height is calculated iteratively, default value is True

    Returns:
    tuple[float, float], a tuple containing the converted height (in units of gpu
    (1 gpu = 10 m^2/s^2) if a geopotential height or in units of m if a normal height)
    and the average normal gravity (in units of 10 m/s^2)

    Raises:
    ?
    """
    if not conversion in ["geopot_to_normal", "normal_to_geopot"]:
        raise ValueError(
            "Function convert_geopotential_height_to_normal_height: Wrong argument for parameter conversion."
        )

    # Conversion of a geopotential height to normal height
    if conversion == "geopot_to_normal":
        # Calculation of average normal gravity in units of 10 m/s^2
        average_normal_gravity = (
            calculate_average_normal_gravity(latitude, approx_normal_height) * 0.1
        )

        # Normal height in units of meters
        height_converted = height / average_normal_gravity

        # Iterative calculation of normal height
        # The iteration is started if height_converted is not nan
        if iterate == True and isnan(height_converted) == False:
            while not (
                -0.00001 <= (height_converted - approx_normal_height) <= 0.00001
            ):
                approx_normal_height = height_converted

                # Calculation of average normal gravity in units of 10 m/s^2
                average_normal_gravity = (
                    calculate_average_normal_gravity(latitude, approx_normal_height)
                    * 0.1
                )

                # Normal height in units of meters
                height_converted = height / average_normal_gravity

    # Conversion of a normal height to geopotential height
    elif conversion == "normal_to_geopot":
        # Calculation of average normal gravity in units of 10 m/s^2
        average_normal_gravity = (
            calculate_average_normal_gravity(latitude, height) * 0.1
        )

        # Geopotential height in units of gpu (1 gpu = 10 m^2/s^2)
        height_converted = height * average_normal_gravity

    return (height_converted, average_normal_gravity)


def convert_geopotential_height_to_helmert_height(
    height: float,
    latitude: float,
    longitude: float,
    grid_inputfolder: Path,
    gravitymodel: str,
    conversion: str,
    tidal_system: str = None,
    use_approx_tidal_formulas: bool = False,
    approx_helmert_height: float = 0,
    iterate: bool = True,
) -> tuple[float, float]:
    """Convert a geopotential height to Helmert height or vice versa.

    Converts a geopotential height to Helmert height or vice versa.

    Reference:
    Klaus Schmidt, The Danish height system DVR90, pp. app 14-15.
    National Survey and Cadastre, 2000

    If a geopotential height is to be converted to Helmert height, an a priori
    Helmert height is required. If no argument is passed for the parameter approx_helmert_height,
    a default value of zero will be used as a priori Helmert height. By default, the
    Helmert height is calculated iteratively until the difference between the current and previous
    iteration step is less than 0.01 mm. If the Helmert height is calculated in only one step using
    the default a priori Helmert height, an error of several millimeters can occur. Therefore,
    it is recommended to calculate the Helmert height iteratively if no a priori Helmert height is
    passed.

    The gravity model used for the conversion of a geopotential height to Helmert height
    (or vice versa) is assumed to be in zero tide system as this is the conventional tide system
    for gravity.

    If the input height is given in the zero tide system, the gravity value interpolated from the
    gravity model is not tidally transformed.

    If the input height is given in the non-tidal or mean tide system, the gravity value interpolated
    from the gravity model is transformed from the zero tide system to the tidal system of the
    input height.

    If the input height is not corrected for tidal effects, the gravity value interpolated
    from the gravity model is transformed from the zero tide system to the mean tide system.

    TO DO: Change the condition for iteration to a looser one, based on the formulae for Helmert height
    TO DO: Udskil beregning af conversion_factor/middeltyngde i en selvstændig funktion i gravity.py

    Args:
    height: float, input/source height to be converted, in units of gpu (1 gpu = 10 m^2/s^2) if a
    geopotential height or in units of m if a Helmert height
    latitude: float, latitude of input/source height, in units of degrees
    longitude: float, longitude of input/source height, in units of degrees
    grid_inputfolder: Path, folder for input grid, i.e. gravity model
    gravitymodel: str, gravity model used for the height conversion, must be in GeoTIFF
    or GTX file format, e.g. "dk-g-direkte-fra-gri-thokn.tif"
    conversion: str, specification of source and target height, "geopot_to_helmert" or
    "helmert_to_geopot"
    tidal_system: str = None, optional parameter, tidal system of input height, i.e. "non", "mean"
    or "zero" for non-tidal, mean tide or zero tide. If no argument is passed it is assumed that
    the input height is not corrected for tidal effects
    use_approx_tidal_formulas: bool = False, optional parameter, determines whether approx or
    rigorous formulas are used for tidal transformation of gravity. By default rigorous formulas
    are used
    approx_helmert_height: float = 0, optional parameter, approx Helmert height in units of m,
    only relevant if a geopotential height is to be converted to Helmert height, default value is 0
    iterate: bool = True, optional parameter, determines whether or not the output/target
    Helmert height is calculated iteratively, default value is True

    Returns:
    tuple[float, float], a tuple containing the converted height (in units of gpu
    (1 gpu = 10 m^2/s^2) if a geopotential height or in units of m if a Helmert height)
    and the conversion factor (Helmert height to geopotential height) in units of 10 m/s^2

    Raises:
    ?
    """
    if not conversion in ["geopot_to_helmert", "helmert_to_geopot"]:
        raise ValueError(
            "Function convert_geopotential_height_to_helmert_height: Wrong argument for parameter conversion."
        )

    # Interpolated gravity in units of m/s^2
    gravity = interpolate_gravity(
        latitude,
        longitude,
        grid_inputfolder,
        gravitymodel,
    )

    # Interpolated gravity is tidally transformed if tidal system of input height
    # is different than zero tide
    if tidal_system != "zero":
        if tidal_system == "non":
            transformation = "zero_to_non"

        elif tidal_system == "mean" or tidal_system is None:
            transformation = "zero_to_mean"

        gravity = transform_gravity_from_tidal_system_to_tidal_system(
            gravity, latitude, transformation, use_approx_tidal_formulas
        )

    # Conversion of a geopotential height to Helmert height
    if conversion == "geopot_to_helmert":
        # Conversion factor (metric Helmert height to geopotential height) in units of 10 m/s^2
        conversion_factor = (gravity * 0.1) + (0.07045 * 1e-6 * approx_helmert_height)

        # Helmert height in units of meters
        height_converted = height / conversion_factor

        # Iterative calculation of Helmert height
        # The iteration is started if height_converted is not nan
        if iterate == True and isnan(height_converted) == False:
            while not (
                -0.00001 <= (height_converted - approx_helmert_height) <= 0.00001
            ):
                approx_helmert_height = height_converted

                # Conversion factor (metric Helmert height to geopotential height) in units of 10 m/s^2
                conversion_factor = (gravity * 0.1) + (
                    0.07045 * 1e-6 * approx_helmert_height
                )

                # Helmert height in units of meters
                height_converted = height / conversion_factor

    # Conversion of a Helmert height to geopotential height
    elif conversion == "helmert_to_geopot":
        # Conversion factor (metric Helmert height to geopotential height) in units of 10 m/s^2
        conversion_factor = (gravity * 0.1) + (0.07045 * 1e-6 * height)

        # Geopotential height in units of gpu (1 gpu = 10 m^2/s^2)
        height_converted = height * conversion_factor

    return (height_converted, conversion_factor)


def convert_geopotential_heights_to_metric_heights(
    height_objects: list[NivKote],
    conversion: str,
    grid_inputfolder: Path = None,
    gravitymodel: str = None,
    tidal_system: str = None,
    use_approx_tidal_formulas: bool = False,
    iterate: bool = True,
) -> tuple[list[NivKote], pd.DataFrame]:
    """Convert geopotential heights to metric heights or vice versa.

    Converts the geopotential heights in a list of NivKote objects to metric heights
    or vice versa.

    The conversion of geopotential heights to metric heights (Helmert heights or normal heights)
    requires a priori metric heights, for which purpose a default value of zero is used. Therefore,
    it is recommended to calculate the metric heights iteratively, as otherwise errors of several
    millimeters can occur.

    Args:
    height_objects: list[NivKote], list of NivKote objects with geopotential heights
    or metric heights to be converted
    conversion: str, specification of source and target height, "geopot_to_helmert",
    "helmert_to_geopot", "geopot_to_normal" or "normal_to_geopot"
    grid_inputfolder: Path = None, optional parameter, folder for input grid, i.e. gravity model,
    only relevant if geopotential heights are to be converted to Helmert heights or vice versa
    gravitymodel: str = None, optional parameter, gravity model used for the conversion of heights,
    must be in GeoTIFF or GTX file format, only relevant if geopotential heights are to be
    converted to Helmert heights or vice versa
    tidal_system: str = None, optional parameter, tidal system of input heights, i.e. "non", "mean"
    or "zero" for non-tidal, mean tide or zero tide. If no argument is passed it is assumed that
    the input heights are not corrected for tidal effects, only relevant if geopotential heights
    are to be converted to Helmert heights or vice versa
    use_approx_tidal_formulas: bool = False, optional parameter, determines whether approx or
    rigorous formulas are used for tidal transformation of gravity, only relevant if geopotential
    heights are to be converted to Helmert heights or vice versa. By default rigorous formulas
    are used
    iterate: bool = True, optional parameter, determines whether or not output/target
    metric heights are calculated iteratively, default value is True

    Returns:
    tuple[list[NivKote], pd.DataFrame], a tuple containing a list of NivKote objects
    with converted heights (generated from deep copies of the inputted NivKote objects)
    and a DataFrame with the conversion factors or average normal gravity values used for
    height conversion

    Raises:
    ? Hvis grid_inputfolder ikke findes, hvis grid-fil ikke findes,

    TO DO: apriori_heights: list[InternKote]=[]?, try...?
    TO DO: Håndtering manglende a priori værdi?
    TO DO: Håndtering manglende inputhøjde?
    TO DO: Specificer input/output enheder
    """
    allowed_conversions = [
        "geopot_to_normal",
        "normal_to_geopot",
        "geopot_to_helmert",
        "helmert_to_geopot",
    ]
    if not conversion in allowed_conversions:
        raise ValueError(
            f"Function convert_geopotential_heights_to_metric_heights: The argument for parameter conversion\n\
            must be one of {', '.join(allowed_conversions)}."
        )

    if (conversion == "geopot_to_helmert" or conversion == "helmert_to_geopot") and (
        (gravitymodel is None) or (grid_inputfolder is None)
    ):
        exit(
            "Function convert_geopotential_heights_to_metric_heights: Wrong arguments for\n\
            parameter grid_inputfolder and/or gravitymodel."
        )

    # Output list for converted heights
    height_objects_converted = []

    # Output DataFrame for conversion factors/average normal gravity values
    index = []

    for height_object in height_objects:
        index.append(height_object.punkt)

    conversion_factors_df = pd.DataFrame(
        index=index,
    )

    for height_object in height_objects:
        height = height_object.H
        latitude = height_object.nord
        longitude = height_object.øst

        if conversion == "geopot_to_normal" or conversion == "normal_to_geopot":
            (height_converted, average_normal_gravity) = (
                convert_geopotential_height_to_normal_height(
                    height,
                    latitude,
                    conversion,
                    iterate=iterate,
                )
            )

            conversion_factors_df.at[
                height_object.punkt,
                "Average normal gravity [10 m/s^2]",
            ] = average_normal_gravity

        elif conversion == "geopot_to_helmert" or conversion == "helmert_to_geopot":
            (height_converted, conversion_factor) = (
                convert_geopotential_height_to_helmert_height(
                    height,
                    latitude,
                    longitude,
                    grid_inputfolder,
                    gravitymodel,
                    conversion,
                    tidal_system=tidal_system,
                    use_approx_tidal_formulas=use_approx_tidal_formulas,
                    iterate=iterate,
                )
            )

            conversion_factors_df.at[
                height_object.punkt,
                f"Conversion factor (tidal system: {tidal_system}) [10 m/s^2]",
            ] = conversion_factor

        # Update of height_object_converted and height_objects_converted
        height_object_converted = copy.deepcopy(height_object)
        height_object_converted.H = height_converted
        height_objects_converted.append(height_object_converted)

    conversion_factors_df = conversion_factors_df.reset_index().rename(
        columns={"index": "Point"}
    )

    return (height_objects_converted, conversion_factors_df)
