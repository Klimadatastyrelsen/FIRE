from pathlib import Path

import numpy as np
import pytest

from fire.api.geodetic_levelling.metric_to_gpu_transformation import (
    convert_metric_height_diff_to_geopotential_height_diff,
    convert_geopotential_height_to_normal_height,
    convert_geopotential_height_to_helmert_height,
)

# Dummy values for height and geographic coordinates
height = 12.127
point_from_lat = 56.62
point_from_long = 12.94
point_to_lat = 56.621
point_to_long = 12.94

# Grid inputfolder and gravity model
grid_inputfolder = Path("C:/FIRE-DEV/src/fire/data")
gravitymodel = "dk-g-direkte-fra-gri-thokn.tif"


@pytest.mark.parametrize(
    "height_diff, tidal_system, expected",
    [
        (0, None, 0),
    ],
)
def test_convert_metric_height_diff_to_geopotential_height_diff(
    height_diff, tidal_system, expected
):
    height_diff_converted, m2gpu_factor = (
        convert_metric_height_diff_to_geopotential_height_diff(
            height_diff,
            point_from_lat,
            point_from_long,
            point_to_lat,
            point_to_long,
            grid_inputfolder,
            gravitymodel,
            tidal_system,
        )
    )

    assert np.isclose(height_diff_converted, expected, rtol=0.000000001)


def test_convert_geopotential_height_to_normal_height():
    # Conversion of zero height
    height_zero_converted, average_normal_gravity = (
        convert_geopotential_height_to_normal_height(
            0,
            point_from_lat,
            "geopot_to_normal",
            approx_normal_height=0,
            iterate=True,
        )
    )
    # Forward conversion of height
    height_converted_forward, average_normal_gravity = (
        convert_geopotential_height_to_normal_height(
            height,
            point_from_lat,
            "normal_to_geopot",
        )
    )
    # Backward conversion of height
    height_converted_backward, average_normal_gravity = (
        convert_geopotential_height_to_normal_height(
            height_converted_forward,
            point_from_lat,
            "geopot_to_normal",
            approx_normal_height=0,
            iterate=True,
        )
    )

    assert np.isclose(0, height_zero_converted, rtol=0.000000001)
    assert np.isclose(height, height_converted_backward, rtol=0.000000001)


def test_convert_geopotential_height_to_helmert_height():
    # Conversion of zero height
    height_zero_converted, conversion_factor = (
        convert_geopotential_height_to_helmert_height(
            0,
            point_from_lat,
            point_from_long,
            grid_inputfolder,
            gravitymodel,
            "geopot_to_helmert",
            tidal_system="non",
            use_approx_tidal_formulas=False,
            approx_helmert_height=0,
            iterate=True,
        )
    )
    # Forward conversion of height
    height_converted_forward, conversion_factor = (
        convert_geopotential_height_to_helmert_height(
            height,
            point_from_lat,
            point_from_long,
            grid_inputfolder,
            gravitymodel,
            "helmert_to_geopot",
            tidal_system="non",
            use_approx_tidal_formulas=False,
        )
    )
    # Backward conversion of height
    height_converted_backward, conversion_factor = (
        convert_geopotential_height_to_helmert_height(
            height_converted_forward,
            point_from_lat,
            point_from_long,
            grid_inputfolder,
            gravitymodel,
            "geopot_to_helmert",
            tidal_system="non",
            use_approx_tidal_formulas=False,
            approx_helmert_height=0,
            iterate=True,
        )
    )

    assert np.isclose(0, height_zero_converted, rtol=0.000000001)
    assert np.isclose(height, height_converted_backward, rtol=0.000000001)
