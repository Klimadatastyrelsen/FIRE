"""This module contains functions for geodetic correction of height differences/levelling observations."""

from pathlib import Path

import pandas as pd

from fire.api.geodetic_levelling.tidal_transformation import (
    apply_tidal_corrections_to_height_diff,
)

from fire.api.geodetic_levelling.time_propagation import (
    propagate_height_diff_from_epoch_to_epoch,
)

from fire.api.geodetic_levelling.metric_to_gpu_transformation import (
    convert_metric_height_diff_to_geopotential_height_diff,
)

from fire.api.niv.datatyper import (
    NivObservation,
    NivKote,
    HeightDiffCorrections,
)


def apply_geodetic_corrections_to_height_diff(
    height_diff: float,
    point_from_lat: float,
    point_from_long: float,
    point_to_lat: float,
    point_to_long: float,
    epoch_obs: pd.Timestamp,
    height_diff_unit: str = "metric",
    epoch_target: pd.Timestamp = None,
    tidal_system: str = None,
    use_approx_tidal_formulas: bool = False,
    grid_inputfolder: Path = None,
    deformationmodel: str = None,
    gravitymodel: str = None,
) -> tuple[float, HeightDiffCorrections]:
    """Apply geodetic corrections to a metric height difference.

    Applies various geodetic corrections to a metric height difference.

    The metric height difference is tidally corrected if and only if the function is called
    with an argument for parameter tidal_system.

    The metric height difference is propagated to a target epoch if and only if
    the function is called with arguments for all three parameters epoch_target, deformationmodel
    and grid_inputfolder.

    The metric height difference is converted to geopotential units if and only
    if the function is called with argument "gpu" for parameter height_diff_unit and with arguments
    for both parameter gravitymodel and grid_inputfolder.

    Args:
    height_diff: float, metric height difference to be corrected/converted
    point_from_lat: float, latitude of from point in units of degrees
    point_from_long: float, longitude of from point in units of degrees
    point_to_lat: float, latitiude of to point in units of degrees
    point_to_long: float, longitude of to point in units of degrees
    epoch_obs: pd.Timestamp, epoch/time of observation (format: yyyy-mm-dd hh:mm:ss)
    height_diff_unit: str = "metric", optional parameter, determines whether or not metric
    input height difference is converted to geopotential units, "metric" for no conversion,
    "gpu" for conversion to gpu, default value is "metric"
    epoch_target: pd.Timestamp = None, optional parameter, target epoch for propagation
    of metric height difference (format: yyyy-mm-dd hh:mm:ss)
    tidal_system: str = None, optional parameter, system for tidal corrections of metric height
    difference, "non", "mean" or "zero" for non-tidal, mean tide or zero tide
    use_approx_tidal_formulas: bool = False, optional parameter, determines whether approx or
    rigorous formulas are used for tidal transformation of input height difference and gravity.
    By default rigorous formulas are used.
    grid_inputfolder: Path = None, optional parameter, folder for input grid, i.e. deformation model
    and/or gravity model
    deformationmodel: str = None, optional parameter, deformation model used for the propagation
    of input height difference, must be in GeoTIFF or GTX file format, e.g. "NKG2016_lev.tif"
    gravitymodel: str = None, optional parameter, gravity model used for the conversion of input
    metric height difference to gpu, must be in GeoTIFF or GTX file format,
    e.g. "dk-g-direkte-fra-gri-thokn.tif"

    Returns:
    tuple[float, HeightDiffCorrections], a tuple containing the corrected/converted
    height difference and a HeightDiffCorrections object with the applied corrections.

    Raises:
    ? Hvis input mappe eller filer ikke findes, hvis der mangler punkter i points?
    """
    # Allowable arguments for parameter height_diff_unit
    allowed_height_diff_units = ["metric", "gpu"]
    if not height_diff_unit in allowed_height_diff_units:
        raise ValueError(
            f"Function apply_geodetic_corrections_to_height_diff: The argument for parameter\n\
            height_diff_unit must be one of {', '.join(allowed_height_diff_units)}"
        )

    # If the height difference is to be propagated to a target epoch the function must be called with
    # relevant arguments for parameters grid_inputfolder and deformationmodel
    if (epoch_target is not None) and (
        (deformationmodel is None) or (grid_inputfolder is None)
    ):
        raise ValueError(
            f"Function apply_geodetic_corrections_to_height_diff: Wrong arguments for\n\
        parameter deformationmodel and/or grid_inputfolder."
        )

    # If the height difference is to be converted to geopotential units the function must be called with
    # relevant arguments for parameters grid_inputfolder and gravitymodel
    if height_diff_unit == "gpu" and (
        (gravitymodel is None) or (grid_inputfolder is None)
    ):
        raise ValueError(
            f"Function apply_geodetic_corrections_to_height_diff: Wrong arguments for\n\
        parameter gravitymodel and/or grid_inputfolder."
        )

    corrections = HeightDiffCorrections()

    # Tidal correction of metric height difference
    if tidal_system is not None:
        (height_diff, tidal_corr) = apply_tidal_corrections_to_height_diff(
            height_diff,
            point_from_lat,
            point_from_long,
            point_to_lat,
            point_to_long,
            epoch_obs,
            tidal_system,
            use_approx_tidal_formulas,
            grid_inputfolder=grid_inputfolder,
            gravitymodel=gravitymodel,
        )

        corrections.tidal_corr = tidal_corr

    # Propagation of metric height difference to a target epoch
    if epoch_target is not None:
        (height_diff, epoch_corr) = propagate_height_diff_from_epoch_to_epoch(
            height_diff,
            point_from_lat,
            point_from_long,
            point_to_lat,
            point_to_long,
            epoch_obs,
            epoch_target,
            grid_inputfolder,
            deformationmodel,
        )

        corrections.epoch_corr = epoch_corr

    # Conversion of metric height difference to geopotential units
    if height_diff_unit == "gpu":
        (height_diff, m2gpu_factor) = (
            convert_metric_height_diff_to_geopotential_height_diff(
                height_diff,
                point_from_lat,
                point_from_long,
                point_to_lat,
                point_to_long,
                grid_inputfolder,
                gravitymodel,
                tidal_system,
                use_approx_tidal_formulas,
            )
        )

        corrections.m2gpu_factor = m2gpu_factor

    return (height_diff, corrections)


def apply_geodetic_corrections_to_height_diff_objects(
    height_diff_objects: dict[str, NivObservation],
    height_objects: dict[str, NivKote],
    height_diff_unit: str = "metric",
    epoch_target: pd.Timestamp = None,
    tidal_system: str = None,
    use_approx_tidal_formulas: bool = False,
    grid_inputfolder: Path = None,
    deformationmodel: str = None,
    gravitymodel: str = None,
) -> tuple[dict[str, NivObservation], pd.DataFrame]:
    """Apply geodetic corrections to the metric height differences in a dict of NivObservation objects.

    Applies various geodetic corrections to the metric height differences in a dict of
    NivObservation objects.

    The metric height differences are tidally corrected if and only if the function is called
    with an argument for parameter tidal_system.

    The metric height differences are propagated to a target epoch if and only if
    the function is called with arguments for all three parameters epoch_target, deformationmodel
    and grid_inputfolder.

    The metric height differences are converted to geopotential units if and only
    if the function is called with argument "gpu" for parameter height_diff_unit and with arguments
    for both parameter gravitymodel and grid_inputfolder.

    Args:
    height_diff_objects: dict[str, NivObservation], dict of NivObservation objects with metric
    height differences to be corrected/converted
    height_objects: dict[str, NivKote], dict of NivKote objects with geographic coordinates of from/to points
    height_diff_unit: str = "metric", optional parameter, determines whether or not metric
    input height differences are converted to geopotential units, "metric" for no conversion,
    "gpu" for conversion to gpu, default value is "metric"
    epoch_target: pd.Timestamp = None, optional parameter, target epoch for propagation
    of metric height differences (format: yyyy-mm-dd hh:mm:ss)
    tidal_system: str = None, optional parameter, system for tidal corrections of metric height
    differences, "non", "mean" or "zero" for non-tidal, mean tide or zero tide
    use_approx_tidal_formulas: bool = False, optional parameter, determines whether approx or
    rigorous formulas are used for tidal transformation of height differences and gravity.
    By default rigorous formulas are used.
    grid_inputfolder: Path = None, optional parameter, folder for input grid, i.e. deformation model
    and/or gravity model
    deformationmodel: str = None, optional parameter, deformation model used for the propagation
    of input height differences, must be in GeoTIFF or GTX file format, e.g. "NKG2016_lev.tif"
    gravitymodel: str = None, optional parameter, gravity model used for the conversion of input
    height differences to gpu, must be in GeoTIFF or GTX file format,
    e.g. "dk-g-direkte-fra-gri-thokn.tif"

    Returns:
    tuple[dict[str, NivObservation], pd.DataFrame], a tuple containing a dict of NivObservation
    objects with converted height differences and a DataFrame with the applied corrections.

    Raises:
    ? Hvis input mappe eller filer ikke findes, hvis der mangler punkter i points?
    """
    from_points = []
    to_points = []
    tidal_corrections = []
    epoch_corrections = []
    m2gpu_factors = []

    for idx, height_diff_object in height_diff_objects.items():
        height_diff, corrections = apply_geodetic_corrections_to_height_diff(
            height_diff_object.deltaH,
            height_objects[height_diff_object.fra].nord,
            height_objects[height_diff_object.fra].øst,
            height_objects[height_diff_object.til].nord,
            height_objects[height_diff_object.til].øst,
            height_diff_object.dato,
            height_diff_unit,
            epoch_target,
            tidal_system,
            use_approx_tidal_formulas,
            grid_inputfolder,
            deformationmodel,
            gravitymodel,
        )

        # Update of height_diff_object with corrected/converted height difference
        height_diff_objects[idx].deltaH = height_diff

        # Save values for output Dataframe
        from_points.append(height_diff_object.fra)
        to_points.append(height_diff_object.til)
        tidal_corrections.append(corrections.tidal_corr)
        epoch_corrections.append(corrections.epoch_corr)
        m2gpu_factors.append(corrections.m2gpu_factor)

    # Generation of output Dataframe
    data = {
        "From point": from_points,
        "To point": to_points,
        f"ΔH tidal correction (tidal system: {tidal_system}) [m]": tidal_corrections,
        f"ΔH epoch correction (target epoch: {epoch_target}) [m]": epoch_corrections,
        f"ΔH m2gpu multiplication factor (tidal system: {tidal_system}) [10 m/s^2]": m2gpu_factors,
    }
    corrections_df = pd.DataFrame(
        data=data,
    )

    return (height_diff_objects, corrections_df)
