"""This module contains functions for transformation of metric heights or height differences
to geopotential units or vice versa.
"""

from math import sin, pi, isnan
from pathlib import Path

import pandas as pd
import pyproj

from fire.api.geodetic_levelling.tidal_transformation import (
    transform_gravity_from_tidal_system_to_tidal_system,
)

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


def convert_metric_height_diff_to_geopotential_height_diff(
    height_diff: float,
    point_from_lat: float,
    point_from_long: float,
    point_to_lat: float,
    point_to_long: float,
    tidal_system: str | None,
    grid_inputfolder: Path,
    gravitymodel: str,
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
    tidal_system: str|None, tidal system of input height difference, i.e. "non", "mean" or "zero"
    for non-tidal, mean tide or zero tide or None if the input height difference is not corrected
    for tidal effects
    grid_inputfolder: Path, folder for input grid, i.e. gravity model
    gravitymodel: str, gravity model used for the conversion of a height difference to gpu,
    must be in GeoTIFF or GTX file format, e.g. "dk-g-direkte-fra-gri-thokn.tif"

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
    if tidal_system == "zero":
        pass

    elif tidal_system == "non":
        point_from_gravity = transform_gravity_from_tidal_system_to_tidal_system(
            point_from_gravity, point_from_lat, "zero_to_non"
        )

        point_to_gravity = transform_gravity_from_tidal_system_to_tidal_system(
            point_to_gravity, point_to_lat, "zero_to_non"
        )

    elif tidal_system == "mean" or tidal_system == None:
        point_from_gravity = transform_gravity_from_tidal_system_to_tidal_system(
            point_from_gravity, point_from_lat, "zero_to_mean"
        )

        point_to_gravity = transform_gravity_from_tidal_system_to_tidal_system(
            point_to_gravity, point_to_lat, "zero_to_mean"
        )

    # Mean gravity in units of m/s^2
    mean_gravity = (point_from_gravity + point_to_gravity) / 2

    # Conversion of height_diff to geopotential units (1 gpu = 10 m^2/s^2)
    m2gpu_factor = mean_gravity * 0.1
    height_diff = height_diff * m2gpu_factor

    return (height_diff, m2gpu_factor)


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

    else:
        exit(
            "Function convert_geopotential_height_to_normal_height: Wrong argument for\n\
        parameter conversion."
        )

    return (height_converted, average_normal_gravity)


def convert_geopotential_height_to_helmert_height(
    height: float,
    latitude: float,
    longitude: float,
    grid_inputfolder: Path,
    gravitymodel: str,
    conversion: str,
    tidal_system: str = None,
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
    # Interpolated gravity in units of m/s^2
    gravity = interpolate_gravity(
        latitude,
        longitude,
        grid_inputfolder,
        gravitymodel,
    )

    # Interpolated gravity is tidally transformed if tidal system of input height
    # is different than zero tide
    if tidal_system == "zero":
        pass

    elif tidal_system == "non":
        gravity = transform_gravity_from_tidal_system_to_tidal_system(
            gravity, latitude, "zero_to_non"
        )

    elif tidal_system == "mean" or tidal_system == None:
        gravity = transform_gravity_from_tidal_system_to_tidal_system(
            gravity, latitude, "zero_to_mean"
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

    else:
        exit(
            "Function convert_geopotential_height_to_helmert_height: Wrong argument for\n\
        parameter conversion."
        )

    return (height_converted, conversion_factor)


def convert_geopotential_heights_to_metric_heights(
    fire_project: str,
    excel_inputfolder: Path,
    outputfolder: Path,
    conversion: str,
    grid_inputfolder: Path = None,
    gravitymodel: str = None,
    tidal_system: str = None,
    iterate: bool = True,
) -> None:
    """Convert geopotential heights to metric heights or vice versa.

    Converts geopotential heights of a FIRE project to metric heights or vice versa.

    If geopotential heights are to be converted to metric heights (Helmert heights or
    normal heights) the input heights are taken from column "Ny kote" in the sheet
    "Kontrolberegning" in the input excel-file and the converted heights are written to
    column "Ny kote" in the sheet "Kontrolberegning" in the output excel-file.

    The conversion of geopotential heights to metric heights (Helmert heights or
    normal heights) requires a priori metric heights, which are taken from column "Kote"
    in the sheet "Kontrolberegning" in the input excel-file.

    If Helmert heights or normal heights are to be converted to geopotential heights
    the input heights are taken from column "Kote" in the sheet "Kontrolberegning" in the
    input excel-file and the converted heights are written to column "Ny kote" in the
    sheet "Kontrolberegning" in the output excel-file.

    Args:
    fire_project: str, name of FIRE project with heights to be converted, must be in accordance
    with the name of the input excel-file, e.g. "asmei_temp"
    excel_inputfolder: Path, folder with input FIRE project/excel-file with heights to be converted
    outputfolder: Path, folder for output FIRE project/excel-file with converted heights
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
    iterate: bool = True, optional parameter, determines whether or not output/target
    metric heights are calculated iteratively, default value is True

    Returns:
    None

    Raises:
    ? Hvis grid_inputfolder ikke findes, hvis grid-fil ikke findes, hvis input excel-fil ikke findes

    Input file:
    FIRE project/excel-file with heights to be converted, e.g. "asmei_temp.xlsx"

    Output file:
    Excel-file with converted heights. This file contains the converted heights in column "Ny kote"
    as well as the conversion factors or average normal gravity values used for height conversion.
    Except for that the file is identical to the input excel-file.

    TO DO: Håndtering manglende a priori værdi?
    TO DO: Håndtering manglende inputhøjde?
    """
    # Make sure that the output folder exists
    outputfolder.mkdir(parents=True, exist_ok=True)

    excel_inputfile = excel_inputfolder / f"{fire_project}.xlsx"

    # DataFrame with heights etc. from input fire project
    points_df = pd.read_excel(excel_inputfile, sheet_name="Kontrolberegning")

    if conversion == "geopot_to_normal":
        for index in points_df.index:
            h_adjusted = points_df.at[index, "Ny kote"]
            h_db = points_df.at[index, "Kote"]
            latitude = points_df.at[index, "Nord"]

            (height_converted, average_normal_gravity) = (
                convert_geopotential_height_to_normal_height(
                    h_adjusted,
                    latitude,
                    "geopot_to_normal",
                    approx_normal_height=h_db,
                    iterate=iterate,
                )
            )
            points_df.at[index, "Ny kote"] = height_converted
            points_df.at[index, "Average normal gravity [10 m/s^2]"] = (
                average_normal_gravity
            )

    elif conversion == "normal_to_geopot":
        for index in points_df.index:
            h_db = points_df.at[index, "Kote"]
            latitude = points_df.at[index, "Nord"]

            (height_converted, average_normal_gravity) = (
                convert_geopotential_height_to_normal_height(
                    h_db,
                    latitude,
                    "normal_to_geopot",
                )
            )
            points_df.at[index, "Ny kote"] = height_converted
            points_df.at[index, "Average normal gravity [10 m/s^2]"] = (
                average_normal_gravity
            )

    elif (
        conversion == "geopot_to_helmert"
        and (grid_inputfolder is not None)
        and (gravitymodel is not None)
    ):
        for index in points_df.index:
            h_adjusted = points_df.at[index, "Ny kote"]
            h_db = points_df.at[index, "Kote"]
            latitude = points_df.at[index, "Nord"]
            longitude = points_df.at[index, "Øst"]

            (height_converted, conversion_factor) = (
                convert_geopotential_height_to_helmert_height(
                    h_adjusted,
                    latitude,
                    longitude,
                    grid_inputfolder,
                    gravitymodel,
                    "geopot_to_helmert",
                    tidal_system=tidal_system,
                    approx_helmert_height=h_db,
                    iterate=iterate,
                )
            )
            points_df.at[index, "Ny kote"] = height_converted
            points_df.at[index, "Conversion factor [10 m/s^2]"] = conversion_factor

    elif (
        conversion == "helmert_to_geopot"
        and (grid_inputfolder is not None)
        and (gravitymodel is not None)
    ):
        for index in points_df.index:
            h_db = points_df.at[index, "Kote"]
            latitude = points_df.at[index, "Nord"]
            longitude = points_df.at[index, "Øst"]

            (height_converted, conversion_factor) = (
                convert_geopotential_height_to_helmert_height(
                    h_db,
                    latitude,
                    longitude,
                    grid_inputfolder,
                    gravitymodel,
                    "helmert_to_geopot",
                    tidal_system=tidal_system,
                )
            )
            points_df.at[index, "Ny kote"] = height_converted
            points_df.at[index, "Conversion factor [10 m/s^2]"] = conversion_factor

    else:
        exit(
            "Function convert_geopotential_heights_to_metric_heights: Wrong arguments for\n\
        parameter conversion and/or grid_inputfolder and/or gravitymodel."
        )

    # DataFrame with parameters of output fire project
    parameters_df = pd.read_excel(excel_inputfile, sheet_name="Parametre")

    if conversion == "geopot_to_normal" or conversion == "normal_to_geopot":
        parameters_new_df = pd.DataFrame(
            {
                "Navn": [
                    "Conversion of heights",
                ],
                "Værdi": [conversion],
            },
        )

    if conversion == "geopot_to_helmert" or conversion == "helmert_to_geopot":
        parameters_new_df = pd.DataFrame(
            {
                "Navn": [
                    "Conversion of heights",
                    "Gravitymodel for conversion of heights",
                ],
                "Værdi": [conversion, gravitymodel],
            },
        )

    parameters_df = pd.concat([parameters_df, parameters_new_df], ignore_index=True)

    # Generation of output fire project/excel file with converted heights
    with pd.ExcelWriter(
        outputfolder / f"{fire_project}.xlsx"
    ) as writer:  # pylint: disable=abstract-class-instantiated
        pd.read_excel(excel_inputfile, sheet_name="Projektforside").to_excel(
            writer, "Projektforside", index=False
        )
        pd.read_excel(excel_inputfile, sheet_name="Sagsgang").to_excel(
            writer, "Sagsgang", index=False
        )
        pd.read_excel(excel_inputfile, sheet_name="Nyetablerede punkter").to_excel(
            writer, "Nyetablerede punkter", index=False
        )
        pd.read_excel(excel_inputfile, sheet_name="Notater").to_excel(
            writer, "Notater", index=False
        )
        pd.read_excel(excel_inputfile, sheet_name="Filoversigt").to_excel(
            writer, "Filoversigt", index=False
        )
        pd.read_excel(excel_inputfile, sheet_name="Observationer").to_excel(
            writer, "Observationer", index=False
        )
        pd.read_excel(excel_inputfile, sheet_name="Punktoversigt").to_excel(
            writer, "Punktoversigt", index=False
        )
        points_df.to_excel(writer, "Kontrolberegning", index=False)
        parameters_df.to_excel(writer, "Parametre", index=False)
