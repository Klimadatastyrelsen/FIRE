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


def apply_geodetic_corrections_to_height_diffs(
    fire_project: str,
    excel_inputfolder: Path,
    outputfolder: Path,
    grid_inputfolder: Path = None,
    height_diff_unit: str = "metric",
    tidal_system: str = None,
    epoch_target: pd.Timestamp = None,
    deformationmodel: str = None,
    gravitymodel: str = None,
) -> None:
    """Apply various geodetic corrections to the height differences of a FIRE project.

    Applies various geodetic corrections to the height differences of a FIRE project.

    The metric height differences of a FIRE project are tidally corrected if and only if
    the function is called with an argument for parameter tidal_system.

    The metric height differences of a FIRE project are propagated to a target epoch if and only if
    the function is called with arguments for all three parameters epoch_target, deformationmodel
    and grid_inputfolder.

    The metric height differences of a FIRE project are converted to geopotential units if and only
    if the function is called with argument "gpu" for parameter height_diff_unit and with arguments
    for both parameter gravitymodel and grid_inputfolder.

    Args:
    fire_project: str, name of fire project with metric height differences to be corrected/converted,
    e.g. "asmei_temp"
    excel_inputfolder: Path, folder containing fire project/excel file
    outputfolder: Path, folder for output fire project/excel file with corrected/converted height differences
    grid_inputfolder: Path = None, optional parameter, folder for input grid, i.e. deformation model
    and/or gravity model
    height_diff_unit: str = "metric", optional parameter, determines whether or not metric
    input height differences are converted to geopotential units, "metric" for no conversion,
    "gpu" for conversion to gpu, default value is "metric"
    tidal_system: str = None, optional parameter, system for tidal corrections of metric height
    differences, "non", "mean" or "zero" for non-tidal, mean tide or zero tide
    epoch_target: pd.Timestamp = None, optional parameter, target epoch for the propagation
    of metric height differences (format: yyyy-mm-dd hh:mm:ss)
    deformationmodel: str = None, optional parameter, deformation model used for the propagation
    of metric height differences, must be in GeoTIFF or GTX file format, e.g. "NKG2016_lev.tif"
    gravitymodel: str = None, optional parameter, gravity model used for the conversion of metric
    height differences to gpu, must be in GeoTIFF or GTX file format, e.g. "dk-g-direkte-fra-gri-thokn.tif"

    Returns:
    None

    Raises:
    ? Hvis input mapper eller filer ikke findes

    Input file:
    FIRE project/excel-file with height differences to be corrected/converted, e.g. "asmei_temp.xlsx"

    Output file:
    Fire project/excel file with corrected/converted height differences

    TO DO: Samle "underparametre" i en eller flere dicts, fx tidal_parameters: dict = {},
    """
    # Make sure that the output folder exists
    outputfolder.mkdir(parents=True, exist_ok=True)

    excel_inputfile = excel_inputfolder / f"{fire_project}.xlsx"

    observations_df = pd.read_excel(excel_inputfile, sheet_name="Observationer")
    points_df = pd.read_excel(excel_inputfile, sheet_name="Punktoversigt")

    # TO DO: Flyt if-sætningerne, der kontrollerer hvilke korrektioner der foretages,
    # foran for-loopet over observations_df.index og loop i stedet op til 3 gange over
    # observations_df.index?

    for index in observations_df.index:
        height_diff = observations_df.at[index, "ΔH"]
        point_from = observations_df.at[index, "Fra"]
        point_to = observations_df.at[index, "Til"]
        epoch_obs = observations_df.at[index, "Hvornår"]

        # Geographic coordinates of point_from and point_to
        # If no information on geographic coordinates is available the observation is skipped
        try:
            # fmt: off
            point_from_lat = points_df.loc[points_df["Punkt"] == point_from, "Nord"].values[0]
            point_from_long = points_df.loc[points_df["Punkt"] == point_from, "Øst"].values[0]
            point_to_lat = points_df.loc[points_df["Punkt"] == point_to, "Nord"].values[0]
            point_to_long = points_df.loc[points_df["Punkt"] == point_to, "Øst"].values[0]
            # fmt: on

        except IndexError:
            observations_df.at[index, "Sluk"] = "x"

            print(
                "index:",
                index,
                "\n",
                "point_from:",
                point_from,
                "\n",
                "point_to:",
                point_to,
                "\n",
                "The geographic coordinates of point_from and/or point_to are missing.\n",
                "The observation is skipped.",
            )

            continue

        # The metric height differences of a FIRE project are tidally corrected if the
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

            observations_df.at[
                index, f"ΔH tidal correction (tidal system: {tidal_system}) [m]"
            ] = tidal_corr

        # The metric height differences of a FIRE project are propagated to a target epoch if
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

            observations_df.at[
                index, f"ΔH epoch correction (target epoch: {epoch_target}) [m]"
            ] = epoch_corr

        # The metric height differences of a FIRE project are converted to geopotential units if
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

            observations_df.at[
                index,
                f"ΔH m2gpu multiplication factor (tidal system: {tidal_system}) [m/s^2]",
            ] = m2gpu_factor

        elif height_diff_unit == "metric":
            pass

        else:
            exit(
                "Function apply_geodetic_corrections_to_height_diffs: Wrong arguments for\n\
            parameter height_diff_unit and/or gravitymodel and/or grid_inputfolder."
            )

        # Update of observations_df with corrected height difference
        observations_df.at[index, "ΔH"] = height_diff

    # DataFrame with parameters of output fire project
    parameters_df = pd.read_excel(excel_inputfile, sheet_name="Parametre")

    parameters_new_df = pd.DataFrame(
        {
            "Navn": [
                "Tidal system",
                "Target epoch",
                "Unit of height differences",
                "Deformationmodel",
                "Gravitymodel",
            ],
            "Værdi": [
                tidal_system,
                epoch_target,
                height_diff_unit,
                deformationmodel,
                gravitymodel,
            ],
        },
    )

    parameters_df = pd.concat([parameters_df, parameters_new_df], ignore_index=True)

    # Generation of output fire project/excel file with corrected/converted height differences
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
        observations_df.to_excel(writer, "Observationer", index=False)
        points_df.to_excel(writer, "Punktoversigt", index=False)
        parameters_df.to_excel(writer, "Parametre", index=False)
