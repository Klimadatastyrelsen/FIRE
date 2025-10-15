"""This module contains functions for generation of histograms visualizing
the temporal distribution of levelling observations in a FIRE project.
"""

from pathlib import Path
import datetime

from astropy.time import Time
from matplotlib.ticker import MaxNLocator
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def datetime_to_decimalyear(datetime: datetime.datetime | pd.Timestamp) -> np.float64:
    """Convert a datetime to decimal year.

    Converts a datetime to decimal year.

    Args:
    datetime: datetime.datetime | pd.Timestamp, input datetime or Timestamp to be converted

    Returns:
    np.float64, input datetime converted to decimal year

    Raises:
    ?
    """
    return Time(datetime, format="datetime").decimalyear


def generate_histogram_temporal_distr_levelling_obs(
    fire_project: str,
    excel_inputfolder: Path,
    outputfolder: Path,
    bins: list[int | float] = None,
) -> None:
    """Generate histogram visualizing the temporal distribution of levelling observations
    in a FIRE project.

    Generates histogram visualizing the temporal distribution of levelling observations
    in a FIRE project.

    Args:
    fire_project: str, name of FIRE project with levelling observations, e.g. "3prs"
    excel_inputfolder: Path, folder containing FIRE project/excel file
    outputfolder: Path, folder for output histogram
    bins: list[int | float] = None, optional parameter, list defining bins for histogram

    Returns:
    None

    Raises:
    ?

    Input file:
    FIRE project/excel file with levelling observations, e.g. "3prs.xlsx"

    Output file:
    Png file with histogram
    """
    # Make sure that the output folder exists
    outputfolder.mkdir(parents=True, exist_ok=True)

    excel_inputfile = excel_inputfolder / f"{fire_project}.xlsx"

    observationer_df = pd.read_excel(excel_inputfile, sheet_name="Observationer")

    # Observation epochs (date and time) in a Series
    observation_epochs = observationer_df["Hvornår"].dropna()

    # Conversion of observation epochs to decimal year
    observation_epochs = observation_epochs.apply(datetime_to_decimalyear)

    fig, ax = plt.subplots(1, 1, sharey=True, tight_layout=True)
    str = f"mean = {observation_epochs.mean():4.2f}"
    ax.hist(observation_epochs, bins=bins, color="red")
    plt.axvline(
        observation_epochs.mean(), color="k", linestyle="dashed", linewidth=1, label=str
    )
    fig.suptitle(
        f"Observation epochs {fire_project}",
        fontsize=16,
    )
    ax.set(
        xlabel="Observation epochs [year]",
        ylabel="#Observations",
        title="Observation epochs",
    )
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(
        loc="upper right",
        fontsize=8,
        fancybox=False,
        framealpha=1,
        edgecolor="black",
    )
    fig.savefig(
        outputfolder / f"Histogram_observation_epochs_{fire_project}.png",
        dpi=400,
    )
    plt.close(fig)
