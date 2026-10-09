import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table
from rich.style import Style

from fire.cli import _get_monochrome


def klargør_celle(input):
    if isinstance(input, datetime) or isinstance(input, int):
        return str(input)
    if isinstance(input, float):
        return f"{input:.4f}"
    if not input:
        return ""
    return str(input)


def print_tabel(
    tabel: Table,
    console: Console = None,
    align: str = "right",
):
    """
    Print en rich.Table til konsollen

    Alle kolonner højrejusteres for at gøre visuel inspektion af decimalpladser lettere.
    Hertil antages at float-kolonner er afrundet til samme antal decimaler.
    """
    if console is None:
        monokrom = _get_monochrome()
        console = Console(color_system="auto" if not monokrom else None)
    # Align kolonner til højre
    for c in tabel.columns:
        c.justify = align

    console.print(tabel)


def generer_tabel(
    overskrifter: list[str],
    data: list[list],
    format: str = "row",
) -> Table:
    """
    Generer en simpelt formateret rich.Table

    Data antages at være givet som en liste med rækker i tabellen.
    Celleindeholdet konverteres først til `str`, og floats afrundes forinden til 4
    decimaler.

    Er data givet som lister med kolonner, kan dette angives med `format='col'`, hvorefter
    data transponeres til række-format før videre behandling.

    Uanset format, antages det at alle de indre lister har samme længde. Desuden skal antallet
    af kolonner altid være lig antallet af overskrifter.
    """
    if not format in ("row", "col"):
        raise ValueError("Format skal være 'row' eller 'col'")

    # Erstat "[" med "\\[" så console.Print ikke opfatter det der står inde i [parentesen]
    # som et "markup tag", se https://rich.readthedocs.io/en/latest/markup.html#
    # Tiltænkt steder hvor kolonnen fx hedder "Kote [m]" eller "sz [mm]"
    overskrifter = [re.sub(r"\[(?=.*\])", "\\[", o) for o in overskrifter]

    tabel = Table(*overskrifter, box=box.SIMPLE, header_style="")

    rækker = data
    # Hvis liste af kolonner er givet, transponeres de til liste af rækker
    if format == "col":
        rækker = list(zip(*data))

    for række in rækker:
        tabel.add_row(
            *[klargør_celle(celle) if celle is not None else "" for celle in række]
        )

    return tabel


def generer_rapporttabel(
    *kolonnenavne,
    title,
    title_justify: str = "left",
    title_style: str | Style = "",
    box: box.Box = box.SIMPLE,
    show_header: bool = True,
    header_style: str | Style = "",
    padding: int | tuple[int] = (0, 1, 0, 0),
    rows_styles: list[tuple[list, str | Style]] = [],
    **kwargs,
) -> Table:
    """
    Generér en rapport-tabel til brug i `info`-kommandogruppen

    Fungerer som en wrapper om `rich.Table` der genererer standardopsætning af tabeller
    til brug i `fire info`.

    Rækker kan tilføjes med det samme via `rows_styles` som indholder en tuple for hver
    tabelrække med tilhørende stilarter. Rækker kan også tilføjes bagefter via
    `Table.add_row` metoden.

    Sættes `show_header=False` vises kolonnenavne ikke.
    **kwargs gives videre til `rich.Table`.
    """
    tbl = Table(
        *kolonnenavne,
        title=title,
        title_justify=title_justify,
        title_style=title_style,
        box=box,
        show_header=show_header,
        header_style=header_style,
        padding=padding,
        **kwargs,
    )

    if rows_styles:
        for row, style in rows_styles:
            # Der kan være tomme rækker, som derfor springes over
            if not row:
                continue
            tbl.add_row(*row, style=style)

    return tbl


def gem_til_excel(
    overskrifter: list[str],
    data: list[list],
    fil: Path,
    format: str = "row",
):
    """
    Gem data til excel

    Er data givet som lister med kolonner, kan dette angives med `format='col'`, hvorefter
    data transponeres til række-format før videre behandling.
    """
    if not format in ("row", "col"):
        raise ValueError("Format skal være 'row' eller 'col'")

    rækker = data
    # Hvis liste af kolonner er givet, transponeres de til liste af rækker
    if format == "col":
        rækker = list(zip(*data))

    rækker = [[klargør_celle(celle) for celle in række] for række in rækker]

    df = pd.DataFrame.from_records(rækker, columns=overskrifter)
    df.to_excel(fil, index=False)


def gem_til_html(
    tabel: Table,
    fil: Path,
):
    """
    Gem en pænt formatteret rich.Table som html
    """
    # Vi er kun interesseret i at gemme tabellen som html og ikke printe den.
    # Men kan kun gemme til html, hvis det også printes til terminalen.
    # Derfor benyttes dette trick der sørger for at der printes til devnull
    # istedet for til stdout. Se
    # https://github.com/Textualize/rich/discussions/1183#discussioncomment-649420
    monokrom = _get_monochrome()
    console = Console(
        record=True,
        file=open(os.devnull, "wt"),
        color_system="auto" if not monokrom else None,
    )

    # "Print" tabellen til devnull
    print_tabel(tabel, console)

    # ... og nu kan vi så gemme det som blev "printet"
    console.save_html(fil)
