from pathlib import Path

import numpy as np
import pandas as pd

from fire.api.geodetic_levelling.time_propagation import (
    propagate_height_diff_from_epoch_to_epoch,
)

# Actual observation
# 268324:1 G.I.1654 G.I.2320 2.53053 331.59 5 1.5 0.1 2024-03-12 11:35:00 15 8 2 1 1000 obs_mtl MTL
# a2e595c1-66a9-4f8b-a392-249b1261abad
height_diff = 2.53053
point_from_lat = 56.0857493027544
point_from_long = 12.4744820001955
point_to_lat = 56.08357879
point_to_long = 12.47348167
epoch_obs = pd.Timestamp(year=2024, month=3, day=12, hour=11, minute=35)

# Epoch target
epoch_target = pd.Timestamp(year=2000, month=1, day=1)

# Grid inputfolder and deformation model
grid_inputfolder = Path("C:/FIRE-DEV/src/fire/data")
deformationmodel = "DKup24geo_DTU2024_PK.tif"


def test_propagate_height_diff_from_epoch_to_epoch():
    # Null propagation of height difference
    height_diff_propagated_null, epoch_corr = propagate_height_diff_from_epoch_to_epoch(
        height_diff,
        point_from_lat,
        point_from_long,
        point_to_lat,
        point_to_long,
        epoch_obs,
        epoch_obs,
        grid_inputfolder,
        deformationmodel,
    )
    # Backward propagation of height difference
    height_diff_propagated_backward, epoch_corr = (
        propagate_height_diff_from_epoch_to_epoch(
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
    )
    # Forward propagation of height difference
    height_diff_propagated_forward, epoch_corr = (
        propagate_height_diff_from_epoch_to_epoch(
            height_diff_propagated_backward,
            point_from_lat,
            point_from_long,
            point_to_lat,
            point_to_long,
            epoch_target,
            epoch_obs,
            grid_inputfolder,
            deformationmodel,
        )
    )

    assert np.isclose(height_diff, height_diff_propagated_null, rtol=0.000000001)
    assert not np.isclose(
        height_diff, height_diff_propagated_backward, rtol=0.000000001
    )
    assert np.isclose(height_diff, height_diff_propagated_forward, rtol=0.000000001)
