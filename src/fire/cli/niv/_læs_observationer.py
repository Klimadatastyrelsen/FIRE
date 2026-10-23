import json
import re
from datetime import datetime
from typing import Dict, Tuple

import click
import pandas as pd
from sqlalchemy.orm.exc import NoResultFound

from fire.api.model.geometry import (
    normaliser_lokationskoordinat,
)
from fire.io.regneark import (
    nyt_ark,
    arkdef,
)
from fire.io.geojson import (
    skriv_punkter_geojson,
    skriv_observationer_geojson,
)

import fire.io.dataframe as frame
import fire.cli

from fire.cli.niv import (
    find_faneblad,
    niv,
    skriv_ark,
    er_projekt_okay,
    KOTESYSTEMER,
)
from fire.cli.exceptions import (
    AfbrydFejl,
    advarsel,
    YndefuldeFejl,
)


@niv.command()
@fire.cli.default_options()
@click.argument(
    "projektnavn",
    nargs=1,
    type=str,
)
@click.option(
    "--kotesystem",
    default="DVR90",
    type=click.Choice(KOTESYSTEMER.keys()),
    help="Angiv andet kotesystem end DVR90",
)
def læs_observationer(projektnavn: str, kotesystem: str, **kwargs) -> None:
    """Importer data fra observationsfiler og opbyg punktoversigt.

    Observationsfiler fra målebilernes instrumenter tilknyttes projektet ved at
    registrere dem i sagsregnearkets "Filoversigt"-faneblad. Fanebladet har fire
    kolonner, "Filnavn", "Type", "σ" og "δ", der alle skal udfyldes for at kunne
    indlæse observationerne i regnearket til videre bearbejdelse.

    \f
    =======  ===========================================
    Kolonne  Beskrivelse
    =======  ===========================================
    Filnavn  Observationsfilens sti og navn.
    Type     Nivellementstype, enten "mgl" eller "mtl".
    σ        A priori spredning. Enheden er mm/sqrt(km).
    δ        Centreringsfejl. Enheden er mm.
    =======  ===========================================

    For hver observationsfil laves en række med ovenstående felter udfyldt. I
    tabellen herunder ses spredningsværdier der typisk bruges til forskellige
    kvalitetskrav for henholdsvis geometetrisk og trigonometrisk nivellement.

    =============  ========  ========
    Krav \\ Metode    MGL       MTL
    =============  ========  ========
    Præcision      0.6       1.5
    Kvalitet       1.0       2.0
    Detail         1.5       3.0
    =============  ========  ========


    Herefter kan observationer læses med::

        fire niv læs-observationer SAG

    Når programmet er kørt færdigt er der tilføjet to nye faneblade til regnearket:
    "Observationer" og "Punktoversigt". Herudover er der lavet to nye GeoJSON-filer
    med henholdsvis observationer og punkter, som kan indlæses i et GIS-program for
    at skabe overblik over det net af punkter der er målt i. Disse filer kan opdateres
    af de andre :program:`fire niv` programmer, fx efter koter er beregnet på baggrund
    af de indlæste observationer.

    """
    resultater = {}
    er_projekt_okay(projektnavn)
    # Opbyg oversigt over nyetablerede punkter
    nyetablerede = find_faneblad(
        projektnavn, "Nyetablerede punkter", arkdef.NYETABLEREDE_PUNKTER
    )

    if any(nyetablerede["Landsnummer"] == ""):
        fire.cli.print("Der mangler landsnumre til nyetablerede punkter.")
        fire.cli.print("Har du husket at lægge dem i databasen?")
        fire.cli.print("Fortsætter beregningen med brug af de foreløbige navne")

    # Initialiser ny kolonne i dataframe til kanoniske identer
    nyetablerede["Kanonisk ident"] = None
    for idx, row in nyetablerede.iterrows():
        try:
            punkt = fire.cli.firedb.hent_punkt(row["Landsnummer"])
        except NoResultFound:
            # Hvis vi ikke kan finde landsnummeret, så bruger vi det foreløbige navn
            nyetablerede.at[idx, "Kanonisk ident"] = row["Foreløbigt navn"]
        else:
            # Ellers så bruger vi den kanoniske ident (hvilket nok er landsnummeret, men ikke altid!)
            nyetablerede.at[idx, "Kanonisk ident"] = punkt.ident

    nyetablerede = nyetablerede.set_index("Kanonisk ident")
    nye_punkter = set(nyetablerede.index)

    # Opbyg oversigt over alle observationer
    observationer = importer_observationer(projektnavn)
    resultater["Observationer"] = observationer
    observerede_punkter = set(list(observationer["Fra"]) + list(observationer["Til"]))
    gamle_punkter = observerede_punkter - nye_punkter

    # Vi vil gerne have de nye punkter først i punktoversigten,
    # så vi sorterer gamle og nye hver for sig
    nye_punkter = tuple(sorted(nye_punkter))
    alle_punkter = nye_punkter + tuple(sorted(gamle_punkter))

    # Opbyg oversigt over alle punkter m. kote og lokation
    punktoversigt = opbyg_punktoversigt(
        projektnavn, nyetablerede, alle_punkter, kotesystem
    )
    resultater["Punktoversigt"] = punktoversigt
    skriv_ark(projektnavn, resultater)
    fire.cli.print(
        f"Dataindlæsning afsluttet. Vælg nu fastholdte punkter i punktoversigten."
    )

    skriv_punkter_geojson(projektnavn, punktoversigt)
    skriv_observationer_geojson(
        projektnavn, punktoversigt.set_index("Punkt"), observationer
    )


# ------------------------------------------------------------------------------
def importer_observationer(projektnavn: str) -> pd.DataFrame:
    """Opbyg dataframe med observationer importeret fra rådatafil"""
    fire.cli.print("Importerer observationer")
    observationer = læs_observationsstrenge(find_inputfiler(projektnavn))

    # Sorter efter journalside, så frem- og tilbageobservationer følges ad.
    # Den sære index-gymnastik sikrer at vi har fortløbende nummerering
    # også efter sorteringen.
    observationer = observationer.sort_values(by="Journal")
    observationer = observationer.reset_index(drop=True)

    # Oversæt alle anvendte identer til kanonisk form
    fra = tuple(observationer["Fra"])
    til = tuple(observationer["Til"])
    observerede_punkter = sorted(tuple(set(fra + til)))
    kanonisk_ident = {}

    n_tabte = 0
    for punktnavn in observerede_punkter:
        with YndefuldeFejl(NoResultFound, f"Ukendt punkt: '{punktnavn}'"):
            punkt = fire.cli.firedb.hent_punkt(punktnavn)

        ident = punkt.ident
        if punkt.tabtgået:
            fire.cli.print(
                f"{punkt.ident} er tabtgået",
                fg="black",
                bg="yellow",
            )
            n_tabte += 1
        else:
            fire.cli.print(f"Fandt {ident}", fg="green")
        kanonisk_ident[punktnavn] = ident

    fra = tuple(kanonisk_ident[ident] for ident in fra)
    til = tuple(kanonisk_ident[ident] for ident in til)

    observationer["Fra"] = fra
    observationer["Til"] = til

    fire.cli.print(
        f"Fandt {n_tabte} tabte punkter blandt {len(observerede_punkter)} observerede punkter."
    )

    # Check journalsiders konsistens:

    # Vi starter med en dict med en tom mængde for hver strækning
    journalsider = dict((tuple(sorted(p)), set()) for p in zip(fra, til))
    # ...så føjer vi hovedjournalsidenummeret til for hver observation
    for i, par in enumerate(zip(fra, til)):
        strækning = tuple(sorted(par))
        hovedside = observationer["Journal"][i].split(":")[0]
        journalsider[strækning].add(hovedside)
    # ...og advarer hvis der er strækninger med flere hovedjournalsidenumre
    for strækning in journalsider:
        if len(journalsider[strækning]) > 1:
            advarsel(
                "Flere hovedjournalsider til samme strækning:\n"
                f"{strækning}: {sorted(journalsider[strækning])}"
            )

    # Check at vi har returmålinger for alle strækninger.
    par = set([tuple(p) for p in zip(fra, til)])
    for p in par:
        if tuple(reversed(p)) not in par:
            advarsel(f"Der mangler returmåling for {p}")

    return observationer


# ------------------------------------------------------------------------------
def opbyg_punktoversigt(
    navn: str,
    nyetablerede: pd.DataFrame,
    alle_punkter: Tuple[str, ...],
    kotesystem: str = "DVR90",
) -> pd.DataFrame:
    punktoversigt = nyt_ark(arkdef.PUNKTOVERSIGT)
    fire.cli.print("Opbygger punktoversigt")

    # Forlæng punktoversigt, så der er plads til alle punkter
    punktoversigt = punktoversigt.reindex(range(len(alle_punkter)))
    punktoversigt["Punkt"] = alle_punkter
    # Geninstaller 'punkt'-søjlen som indexsøjle
    punktoversigt = punktoversigt.set_index("Punkt")

    nye_punkter = tuple(sorted(set(nyetablerede.index)))

    fejltekst = f"{kotesystem} ({KOTESYSTEMER[kotesystem]}) ikke fundet i srid-tabel"
    with YndefuldeFejl(NoResultFound, fejltekst):
        srid = fire.cli.firedb.hent_srid(KOTESYSTEMER[kotesystem])

    for punkt in alle_punkter:
        if not pd.isna(punktoversigt.at[punkt, "Kote"]):
            continue
        if punkt in nye_punkter:
            continue

        fire.cli.print(f"Finder kote for {punkt}", fg="green")
        pkt = fire.cli.firedb.hent_punkt(punkt)

        # Grav aktuel kote frem
        kote = None
        for koord in pkt.koordinater:
            if koord.srid != srid:
                continue
            if koord.registreringtil is None:
                kote = koord
                break

        punktoversigt.at[punkt, "Fasthold"] = ""
        punktoversigt.at[punkt, "System"] = kotesystem
        punktoversigt.at[punkt, "uuid"] = ""
        punktoversigt.at[punkt, "Udelad publikation"] = ""

        if kote is None:
            fire.cli.print(
                f"Ingen aktuel {kotesystem}-kote fundet for {punkt}",
                bg="red",
                fg="white",
                err=True,
            )
            punktoversigt.at[punkt, "Kote"] = None
            punktoversigt.at[punkt, "σ"] = None
            punktoversigt.at[punkt, "Hvornår"] = None

        else:
            punktoversigt.at[punkt, "Kote"] = kote.z
            punktoversigt.at[punkt, "σ"] = kote.sz
            punktoversigt.at[punkt, "Hvornår"] = kote.t

        if pd.isna(punktoversigt.at[punkt, "Nord"]):
            punktoversigt.at[punkt, "Nord"] = pkt.geometri.koordinater[1]
            punktoversigt.at[punkt, "Øst"] = pkt.geometri.koordinater[0]

    # Nyetablerede punkter er ikke i databasen, så hent eventuelle manglende
    # koter og lokationskoordinater i fanebladet 'Nyetablerede punkter'
    for punkt in nye_punkter:
        if pd.isna(punktoversigt.at[punkt, "Kote"]):
            punktoversigt.at[punkt, "Kote"] = None
        if pd.isna(punktoversigt.at[punkt, "System"]):
            punktoversigt.at[punkt, "System"] = kotesystem
        if pd.isna(punktoversigt.at[punkt, "Nord"]):
            punktoversigt.at[punkt, "Nord"] = nyetablerede.at[punkt, "Nord"]
        if pd.isna(punktoversigt.at[punkt, "Øst"]):
            punktoversigt.at[punkt, "Øst"] = nyetablerede.at[punkt, "Øst"]

    # Check op på lokationskoordinaterne
    for punkt in alle_punkter:
        λ, φ = normaliser_lokationskoordinat(
            punktoversigt.at[punkt, "Øst"], punktoversigt.at[punkt, "Nord"]
        )
        punktoversigt.at[punkt, "Nord"] = φ
        punktoversigt.at[punkt, "Øst"] = λ

    # Reformater datarammen så den egner sig til output
    return punktoversigt.reset_index()


# ------------------------------------------------------------------------------
def læs_observationsstrenge(
    filinfo: pd.DataFrame, verbose: bool = False
) -> pd.DataFrame:
    """Pil observationsstrengene ud fra en række råfiler"""

    observationer = nyt_ark(arkdef.OBSERVATIONER)
    for fil in filinfo.itertuples(index=False):
        if fil.Type.upper() not in ["MGL", "MTL", "NUL"]:
            continue
        if verbose:
            fire.cli.print(f"Læser {fil.Filnavn} med σ={fil.σ} og δ={fil.δ}")

        # Det hænder at der er fejl ved læsning af observationsfiler.
        # Nogle gange er filen UTF-8 andre gange er den latin-1 og
        # muligvis er det af og til en kombination af begge (typisk ved brug
        # af æøå). Herunder tager vi hånd om de to første scenarier og
        # lader koden fejle ved det sidste scenarie for at undgå
        # efterfølgende bivirkninger.
        obsfil = open(fil.Filnavn, "rt", encoding="utf-8")
        try:
            # check for unicode læsefejl
            obsfil.readlines()
            # hvis ingen fejl mødes spoles filen tilbage til start
            obsfil.seek(0)
        except UnicodeDecodeError:
            obsfil = open(fil.Filnavn, "rt", encoding="latin-1")
        try:
            for line in obsfil:
                if "#" != line[0]:
                    continue
                # Fjern luft i begge ender, havelågen i starten og kollaps gentagen luft
                line = re.sub(r"[ \t]+", " ", line.lstrip("# ").strip())

                # Check at observationen er i et af de kendte formater
                tokens = line.split(" ", 13)
                if len(tokens) not in (9, 13, 14):
                    raise AfbrydFejl(f"Deform input linje: {line} i fil: {fil.Filnavn}")

                # Bring observationen på kanonisk 14-feltform.
                for _ in range(len(tokens), 13):
                    tokens.append(0)
                # Tilføj tom kommentar hvis der ikke er nogen med indhold
                if len(tokens) < 14:
                    tokens.append('""')
                # Befri kommentar for anførelsestegn og overflødige mellemrum
                tokens[13] = tokens[13].lstrip('"').strip().rstrip('"')

                # Korriger de rædsomme dato/tidsformater
                tid = " ".join((tokens[2], tokens[3]))
                with YndefuldeFejl(
                    ValueError,
                    f"Ikke-understøttet datoformat: '{tid}' i fil: '{fil.Filnavn}'",
                ):
                    isotid = datetime.strptime(tid, "%d.%m.%Y %H.%M")

                # Opbyg række-som-dict: Omsæt numeriske data fra strengrepræsentation til tal
                obs = {
                    "Fra": tokens[0],
                    "Til": tokens[1],
                    "L": float(tokens[4]),
                    "ΔH": float(tokens[5]),
                    # Undgå journalside fortolkes som tal: Erstat decimalseparator
                    "Journal": tokens[6].replace(".", ":"),
                    "T": float(tokens[7]),
                    "Opst": int(tokens[8]),
                    "Sky": int(tokens[9]),
                    "Sol": int(tokens[10]),
                    "Vind": int(tokens[11]),
                    "Sigt": int(tokens[12]),
                    "σ": fil.σ,
                    "δ": fil.δ,
                    "Kommentar": tokens[13],
                    "Sluk": "",
                    "Hvornår": isotid,
                    "Kilde": fil.Filnavn,
                    "Type": fil.Type.upper(),
                    "uuid": "",
                }
                observationer = frame.append(observationer, obs)
        except FileNotFoundError:
            fire.cli.print(f"Kunne ikke læse filen '{fil.Filnavn}'")
        finally:
            obsfil.close()

    return observationer


# ------------------------------------------------------------------------------
def find_inputfiler(navn: str) -> pd.DataFrame:
    """Opbyg oversigt over alle input-filnavne og deres tilhørende spredning og centreringsfejl"""
    inputfiler = find_faneblad(navn, "Filoversigt", arkdef.FILOVERSIGT)
    return inputfiler[inputfiler["Filnavn"].notnull()]  # Fjern blanklinjer
