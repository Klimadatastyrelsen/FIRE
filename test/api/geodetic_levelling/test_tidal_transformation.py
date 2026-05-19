from pathlib import Path

import numpy as np
import pytest

from fire.api.geodetic_levelling.tidal_transformation import (
    transform_gravity_from_tidal_system_to_tidal_system,
    transform_height_from_tidal_system_to_tidal_system,
    transform_height_diff_from_tidal_system_to_tidal_system,
)

# Dummy values for gravity, height, height difference and geographic coordinates
# NB: the dummy values for latitude shuold not be close to +/-35.267 deg, as the permanent
# tide vanishes around these latitudes
gravity = 9.81
height = 12.127
height_diff = 1.083
point_from_lat = 56.62
point_from_long = 12.94
point_to_lat = 56.621
point_to_long = 12.94

# Grid inputfolder and gravity model
grid_inputfolder = Path("C:/FIRE-DEV/src/fire/data")
gravitymodel = "dk-g-direkte-fra-gri-thokn.tif"


@pytest.mark.parametrize(
    "transformation_forward, transformation_backward",
    [
        ("zero_to_non", "non_to_zero"),
        ("zero_to_mean", "mean_to_zero"),
        ("non_to_mean", "mean_to_non"),
    ],
)
def test_transform_gravity_from_tidal_system_to_tidal_system(
    transformation_forward, transformation_backward
):
    # Forward transformation of gravity
    gravity_transformed_forward = transform_gravity_from_tidal_system_to_tidal_system(
        gravity, point_from_lat, transformation_forward
    )
    # Backward transformation of gravity
    gravity_transformed_backward = transform_gravity_from_tidal_system_to_tidal_system(
        gravity_transformed_forward, point_from_lat, transformation_backward
    )

    assert not np.isclose(gravity, gravity_transformed_forward, rtol=0.000000001)
    assert np.isclose(gravity, gravity_transformed_backward, rtol=0.000000001)


@pytest.mark.parametrize(
    "transformation_forward, transformation_backward",
    [
        ("zero_to_non", "non_to_zero"),
        ("zero_to_mean", "mean_to_zero"),
        ("non_to_mean", "mean_to_non"),
    ],
)
def test_transform_height_from_tidal_system_to_tidal_system(
    transformation_forward, transformation_backward
):
    # Forward transformation of height
    height_transformed_forward = transform_height_from_tidal_system_to_tidal_system(
        height,
        point_from_lat,
        point_from_long,
        transformation_forward,
        grid_inputfolder,
        gravitymodel,
    )
    # Backward transformation of height
    height_transformed_backward = transform_height_from_tidal_system_to_tidal_system(
        height_transformed_forward,
        point_from_lat,
        point_from_long,
        transformation_backward,
        grid_inputfolder,
        gravitymodel,
    )

    assert not np.isclose(height, height_transformed_forward, rtol=0.000000001)
    assert np.isclose(height, height_transformed_backward, rtol=0.000000001)


@pytest.mark.parametrize(
    "transformation_forward, transformation_backward",
    [
        ("zero_to_non", "non_to_zero"),
        ("zero_to_mean", "mean_to_zero"),
        ("non_to_mean", "mean_to_non"),
    ],
)
def test_transform_height_diff_from_tidal_system_to_tidal_system(
    transformation_forward, transformation_backward
):
    # Forward transformation of height difference
    height_diff_transformed_forward = (
        transform_height_diff_from_tidal_system_to_tidal_system(
            height_diff,
            transformation_forward,
            point_from_lat,
            point_to_lat,
            point_from_long,
            point_to_long,
            grid_inputfolder,
            gravitymodel,
        )
    )
    # Backward transformation of height difference
    height_diff_transformed_backward = (
        transform_height_diff_from_tidal_system_to_tidal_system(
            height_diff_transformed_forward,
            transformation_backward,
            point_from_lat,
            point_to_lat,
            point_from_long,
            point_to_long,
            grid_inputfolder,
            gravitymodel,
        )
    )

    assert not np.isclose(
        height_diff, height_diff_transformed_forward, rtol=0.000000001
    )
    assert np.isclose(height_diff, height_diff_transformed_backward, rtol=0.000000001)
