"""This module contains functions for geodetic correction of height differences/levelling observations."""

from pathlib import Path
import copy

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
)


def apply_geodetic_corrections_to_height_diffs(
    height_diff_objects: list[NivObservation],
    height_objects: list[NivKote],
    height_diff_unit: str = "metric",
    epoch_target: pd.Timestamp = None,
    tidal_system: str = None,
    grid_inputfolder: Path = None,
    deformationmodel: str = None,
    gravitymodel: str = None,
) -> tuple[list[NivObservation], pd.DataFrame]:
    """Apply geodetic corrections to metric height differences.

    Applies various geodetic corrections to the metric height differences in a list of
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
    height_diff_objects: list[NivObservation], list of NivObservation objects with
    metric height differences to be corrected/converted
    height_objects: list[NivKote], list of NivKote objects with geographic coordinates of from/to points
    height_diff_unit: str = "metric", optional parameter, determines whether or not metric
    input height differences are converted to geopotential units, "metric" for no conversion,
    "gpu" for conversion to gpu, default value is "metric"
    epoch_target: pd.Timestamp = None, optional parameter, target epoch for the propagation
    of metric height differences (format: yyyy-mm-dd hh:mm:ss)
    tidal_system: str = None, optional parameter, system for tidal corrections of metric height
    differences, "non", "mean" or "zero" for non-tidal, mean tide or zero tide
    grid_inputfolder: Path = None, optional parameter, folder for input grid, i.e. deformation model
    and/or gravity model
    deformationmodel: str = None, optional parameter, deformation model used for the propagation
    of metric height differences, must be in GeoTIFF or GTX file format, e.g. "NKG2016_lev.tif"
    gravitymodel: str = None, optional parameter, gravity model used for the conversion of metric
    height differences to gpu, must be in GeoTIFF or GTX file format, e.g. "dk-g-direkte-fra-gri-thokn.tif"

    Returns:
    tuple[list[NivObservation], pd.DataFrame], a tuple containing a list of NivObservation
    objects with corrected/converted height differences (generated from deep copies of the
    inputted NivObservation objects) and a DataFrame with the corrections themselves.

    Raises:
    ? Hvis input mappe eller filer ikke findes, hvis der mangler punkter i points?
    """
    # Output list for corrected/converted height differences
    height_diff_objects_corrected = []

    # Output DataFrame for applied corrections
    index = []

    for height_diff_object in height_diff_objects:
        index.append(height_diff_object.id)

    corrections_df = pd.DataFrame(
        columns=[
            f"ΔH tidal correction (tidal system: {tidal_system}) [m]",
            f"ΔH epoch correction (target epoch: {epoch_target}) [m]",
            f"ΔH m2gpu multiplication factor (tidal system: {tidal_system}) [m/s^2]",
        ],
        index=index,
    )

    for height_diff_object in height_diff_objects:
        height_diff = height_diff_object.deltaH
        point_from = height_diff_object.fra
        point_to = height_diff_object.til
        epoch_obs = height_diff_object.dato

        # Geographic coordinates of point_from and point_to
        (point_from_lat, point_from_long) = [
            (height_object.nord, height_object.øst)
            for height_object in height_objects
            if height_object.punkt == point_from
        ][0]
        (point_to_lat, point_to_long) = [
            (height_object.nord, height_object.øst)
            for height_object in height_objects
            if height_object.punkt == point_to
        ][0]

        # The metric height differences are tidally corrected if the
        # function apply_geodetic_corrections_to_height_diffs is called with an argument for
        # parameter tidal_system
        if tidal_system is not None:
            (height_diff, tidal_corr) = apply_tidal_corrections_to_height_diff(
                height_diff,
                point_from_lat,
                point_from_long,
                point_to_lat,
                point_to_long,
                epoch_obs,
                tidal_system,
                grid_inputfolder=grid_inputfolder,
                gravitymodel=gravitymodel,
            )

            corrections_df.at[
                height_diff_object.id,
                f"ΔH tidal correction (tidal system: {tidal_system}) [m]",
            ] = tidal_corr

        # The metric height differences are propagated to a target epoch if
        # the function apply_geodetic_corrections_to_height_diffs is called with arguments for
        # all three parameters epoch_target, deformationmodel and grid_inputfolder
        if (
            (epoch_target is not None)
            and (deformationmodel is not None)
            and (grid_inputfolder is not None)
        ):
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

            corrections_df.at[
                height_diff_object.id,
                f"ΔH epoch correction (target epoch: {epoch_target}) [m]",
            ] = epoch_corr

        # The metric height differences are converted to geopotential units if
        # the function apply_geodetic_corrections_to_height_diffs is called with argument "gpu"
        # for parameter height_diff_unit and with arguments for both parameter gravitymodel
        # and grid_inputfolder
        if (
            height_diff_unit == "gpu"
            and (gravitymodel is not None)
            and (grid_inputfolder is not None)
        ):
            (height_diff, m2gpu_factor) = (
                convert_metric_height_diff_to_geopotential_height_diff(
                    height_diff,
                    point_from_lat,
                    point_from_long,
                    point_to_lat,
                    point_to_long,
                    tidal_system,
                    grid_inputfolder,
                    gravitymodel,
                )
            )

            corrections_df.at[
                height_diff_object.id,
                f"ΔH m2gpu multiplication factor (tidal system: {tidal_system}) [m/s^2]",
            ] = m2gpu_factor

        elif height_diff_unit == "metric":
            pass

        else:
            exit(
                "Function apply_geodetic_corrections_to_height_diffs: Wrong arguments for\n\
            parameter height_diff_unit and/or gravitymodel and/or grid_inputfolder."
            )

        # Update of height_diff_object_corrected and height_diff_objects_corrected
        height_diff_object_corrected = copy.deepcopy(height_diff_object)
        height_diff_object_corrected.deltaH = height_diff
        height_diff_objects_corrected.append(height_diff_object_corrected)

    return (height_diff_objects_corrected, corrections_df)
