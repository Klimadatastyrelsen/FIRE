"""This module contains functions for time propagation of height differences."""

from pathlib import Path

import pandas as pd
import pyproj


def propagate_height_diff_from_epoch_to_epoch(
    height_diff: float,
    point_from_lat: float,
    point_from_long: float,
    point_to_lat: float,
    point_to_long: float,
    epoch_source: pd.Timestamp,
    epoch_target: pd.Timestamp,
    grid_inputfolder: Path,
    deformationmodel: str,
) -> tuple[float, float]:
    """Propagate a metric height difference from one epoch to another.

    Propagates a metric height difference from one epoch to another and returns the propagated
    height difference and the correction itself in a tuple.

    Args:
    height_diff: float, metric height difference to be propagated
    point_from_lat: float, latitude of from point in units of degrees
    point_from_long: float, longitude of from point in units of degrees
    point_to_lat: float, latitiude of to point in units of degrees
    point_to_long: float, longitude of to point in units of degrees
    epoch_source: pd.Timestamp, source epoch, e.g. epoch of observation (format: yyyy-mm-dd hh:mm:ss)
    epoch_target: pd.Timestamp, target epoch (format: yyyy-mm-dd hh:mm:ss)
    grid_inputfolder: Path, folder for input grid, i.e. deformation model
    deformationmodel: str, deformation model used for the propagation of height differences,
    must be in GeoTIFF or GTX file format, e.g. "NKG2016_lev.tif"

    Returns:
    tuple[float, float], a tuple containing the propagated height difference and
    the correction itself in units of meters

    Raises:
    ?
    """
    pyproj.datadir.append_data_dir(grid_inputfolder)

    # Up velocities of point_from and point_to in units of mm/yr
    # Flyt til overfunktionen height_diff_corr?
    transformer = pyproj.Transformer.from_pipeline(
        f"+proj=vgridshift +grids={deformationmodel}"
    )

    point_from_velocity_up = (
        transformer.transform(point_from_long, point_from_lat, 0)[2] * -1
    )

    point_to_velocity_up = transformer.transform(point_to_long, point_to_lat, 0)[2] * -1

    # Difference in up velocities in units of mm/yr
    velocity_up_diff = point_to_velocity_up - point_from_velocity_up

    # Difference in epochs in units of years
    epoch_diff = (epoch_target - epoch_source).days / 365.2425

    # Propagation of height_diff to epoch_target
    epoch_corr = velocity_up_diff * epoch_diff * 0.001
    height_diff = height_diff + epoch_corr

    return (height_diff, epoch_corr)
