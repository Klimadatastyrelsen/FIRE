"""This module contains functions for the generation of contour plots showing
3rd precision levelling recalculated vs. DVR90
"""

from pathlib import Path

from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import cartopy
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.tri as tri
import numpy as np
import pandas as pd


def extract_heights_from_fire_project(
    fire_project: str,
    excel_inputfolder: Path,
) -> pd.DataFrame:
    """Extract heights from a FIRE project.

    Extracts adjusted heights and database heights from a FIRE project and returns the
    extracted heights and corresponding height differences in a DataFrame.

    Note that only the heights of DVR90 defining points are extracted from the FIRE project.

    Args:
    fire_project: str, name of FIRE project with adjusted heights and database heights,
    e.g. "3prs"
    excel_inputfolder: Path, folder containing FIRE project/excel file

    Returns:
    pd.DataFrame, a DataFrame with extracted heights and height differences

    Raises:
    ? Hvis input mapper eller filer ikke findes

    Input file:
    FIRE project/excel file with adjusted heights and database heights, e.g. "3prs.xlsx"
    """
    excel_inputfile = excel_inputfolder / f"{fire_project}.xlsx"

    punktoversigt_df = pd.read_excel(excel_inputfile, sheet_name="Punktoversigt")
    kontrolberegning_df = pd.read_excel(excel_inputfile, sheet_name="Kontrolberegning")

    # DataFrame with DVR90 defining points in sheet "Punktoversigt"
    # (i.e. all G.I. or G.M. points with a database height calculated 2000-02-11 13:30:00)
    punktoversigt_df = punktoversigt_df[
        (punktoversigt_df["Hvornår"] == "2000-02-11 13:30:00")
        & (
            punktoversigt_df["Punkt"].str.startswith("G.I.")
            | punktoversigt_df["Punkt"].str.startswith("G.M.")
        )
    ]

    # DataFrame with point id, database height and latitude/longitude of DVR90 defining points
    punktoversigt_df = punktoversigt_df[["Punkt", "Kote", "Nord", "Øst"]]

    # DataFrame with point id and adjusted heights of all points in sheet "Kontrolberegning"
    kontrolberegning_df = kontrolberegning_df[["Punkt", "Ny kote"]]

    kontrolberegning_df = kontrolberegning_df.set_index("Punkt")

    # DataFrame with point id, database height, adjusted height and latitude/longitude of
    # DVR90 defining points
    points_df = punktoversigt_df.join(kontrolberegning_df, on="Punkt", how="inner")

    # Add column with height differences (adjusted height - database height) to DataFrame
    points_df["Diff"] = points_df["Ny kote"] - points_df["Kote"]

    return points_df


def contour_plot_recalc_vs_dvr90(
    fire_project: str,
    excel_inputfolder: Path,
    outputfolder: Path,
) -> None:
    """Generate contour plot showing 3rd precision levelling recalculated vs. DVR90.

    Generates contour plot showing 3rd precision levelling recalculated vs. DVR90
    (recalculated height - DVR90 height).

    Args:
    fire_project: str, name of fire project with recalculated/adjusted heights and
    DVR90/database heights, e.g. "3prs"
    excel_inputfolder: Path, folder containing FIRE project/excel file
    outputfolder: Path, folder for output contour plot

    Returns:
    None

    Raises:
    ?

    Input file:
    FIRE project/excel file with adjusted heights and database heights, e.g. "3prs.xlsx"

    Output file:
    Png file with contour plot
    """
    # Make sure that the output folder exists
    outputfolder.mkdir(parents=True, exist_ok=True)

    # DataFrame with height differences of DVR90 defining points
    # (adjusted heights - database heights)
    points_df = extract_heights_from_fire_project(fire_project, excel_inputfolder)

    # Generation of contour plot
    fig = plt.figure(figsize=(7, 4), dpi=500)
    crs = ccrs.PlateCarree()
    ax = plt.axes(projection=crs)

    ax.set_title("3rd precision levelling recalculated vs. DVR90")
    ax.add_feature(cartopy.feature.OCEAN, zorder=0)
    ax.add_feature(cartopy.feature.LAND, zorder=0, edgecolor="black")
    ax.add_feature(cartopy.feature.COASTLINE)

    # Levels for contour plot
    min_level = np.floor(points_df["Diff"].min() * 1000)
    max_level = np.ceil(points_df["Diff"].max() * 1000)
    levels = np.arange(min_level, max_level + 1)

    triangulation = tri.Triangulation(points_df["Øst"], points_df["Nord"])
    triangles = triangulation.triangles

    # Mask off unwanted triangles across the Great Belt
    east_tri = points_df.Øst.values[triangles] - np.roll(
        points_df.Øst.values[triangles], 1, axis=1
    )
    north_tri = points_df.Nord.values[triangles] - np.roll(
        points_df.Nord.values[triangles], 1, axis=1
    )
    maxi = np.max(np.sqrt(east_tri**2 + north_tri**2), axis=1)

    triangulation.set_mask(maxi > 0.80)

    ax.tricontour(
        triangulation,
        points_df["Diff"] * 1000,
        levels,
        linewidths=0.5,
        colors="k",
        transform=crs,
    )

    contour_regions = ax.tricontourf(
        triangulation,
        points_df["Diff"] * 1000,
        levels,
        transform=crs,
    )

    ax.plot(points_df["Øst"], points_df["Nord"], "ko", ms=2, transform=crs)

    fig.colorbar(contour_regions, ax=ax, label=r"$\Delta$H [mm] (recalculated - DVR90)")

    gl = ax.gridlines(crs=crs, draw_labels=True)
    gl.top_labels = False
    gl.right_labels = False
    gl.xlocator = mticker.FixedLocator([8, 9, 10, 11, 12, 13, 14])
    gl.ylocator = mticker.FixedLocator([55, 56, 57, 58, 59])
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER

    ax.set_xlim([7.9, 13.1])
    ax.set_ylim([54.3, 58.1])

    plt.savefig(outputfolder / f"{fire_project}.png")
    plt.close()
