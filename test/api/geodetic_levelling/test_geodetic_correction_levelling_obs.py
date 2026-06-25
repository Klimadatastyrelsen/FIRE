from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fire.api.geodetic_levelling.geodetic_correction_levelling_obs import (
    apply_geodetic_corrections_to_height_diff,
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

# Actual observation corrected, reference for test
# height_diff_unit="gpu", epoch_target=1990, tidal_system="non"
# 'f99756fe-4f19-4ff5-b0bb-b54006b699ba': NivObservation(fra='G.I.1654', til='G.I.2320',
# dato=datetime.datetime(2024, 3, 12, 11, 35), multiplicitet=5, afstand=331.59,
# deltaH=np.float64(2.4840159939125797), spredning=0.5453364449814444, id='268324:1'),
height_diff_corrected_ref = np.float64(2.4840159939125797)

# Grid inputfolder, deformation model and gravity model
grid_inputfolder = Path("C:/FIRE-DEV/src/fire/data")
deformationmodel = "DKup24geo_DTU2024_PK.tif"
gravitymodel = "dk-g-direkte-fra-gri-thokn.tif"


@pytest.mark.parametrize(
    "height_diff_unit, epoch_target, tidal_system, expected",
    [
        ("metric", None, None, height_diff),
        (
            "gpu",
            pd.Timestamp(year=1990, month=1, day=1),
            "non",
            height_diff_corrected_ref,
        ),
    ],
)
def test_apply_geodetic_corrections_to_height_diff(
    height_diff_unit, epoch_target, tidal_system, expected
):
    height_diff_corrected, corrections = apply_geodetic_corrections_to_height_diff(
        height_diff,
        point_from_lat,
        point_from_long,
        point_to_lat,
        point_to_long,
        epoch_obs,
        height_diff_unit=height_diff_unit,
        epoch_target=epoch_target,
        tidal_system=tidal_system,
        grid_inputfolder=grid_inputfolder,
        deformationmodel=deformationmodel,
        gravitymodel=gravitymodel,
    )

    assert np.isclose(height_diff_corrected, expected, rtol=0.000000001)
