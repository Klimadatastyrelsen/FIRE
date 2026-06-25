import datetime
import os
import os.path
from pathlib import Path
from typing import (
    Dict,
    Tuple,
)

import click
import pandas as pd
import pandas.io.formats.style
from sqlalchemy.orm.exc import NoResultFound
from openpyxl.worksheet.worksheet import Worksheet
import packaging.version

from fire.api.model import (
    Punkt,
    PunktInformation,
    Sag,
    Tidsserie,
    HøjdeTidsserie,
)
from fire.io.regneark import arkdef
import fire.cli
from fire.cli import firedb, grøn

# Kotesystemer som understøttes i niv-modulet
KOTESYSTEMER = {
    "DVR90": "EPSG:5799",
    "Jessen": "TS:jessen",
    "LRL": "TS:LRL",
}

# ------------------------------------------------------------------------------
niv_help = f"""Nivellement: Arbejdsflow, beregning og analyse

Underkommandoerne:

\b
    opret-sag
    udtræk-revision
    ilæg-revision
    ilæg-nye-punkter
    læs-observationer
    regn
    ilæg-observationer
    ilæg-nye-koter
    luk-sag

definerer, i den anførte rækkefølge, nogenlunde arbejdsskridtene i et
almindeligt opmålingsprojekt.

Til beregning af eksisterende observationer, findes en alternativ underkommando
til `læs-observationer`, kaldet `udtræk-observationer`. En arbejdsgang med denne
kommando kan se ud på følgende måde:

\b
    opret-sag
    udtræk-observationer
    regn
    luk-sag
\b
Underkommandoer
---------------

OPRET-SAG registrerer sagen (projektet) i databasen og skriver det regneark,
som bruges til at holde styr på arbejdet.

UDTRÆK-REVISION udtrækker oversigt over eksisterende punkter i et område,
til brug for punktrevision (herunder registrering af tabtgåede punkter).

ILÆG-REVISION lægger opdaterede og nye punktattributter i databasen efter revision.

ILÆG-NYE-PUNKTER lægger oplysninger om nyoprettede punkter i databasen, og tildeler
bl.a. landsnumre til punkterne.

LÆS-OBSERVATIONER læser råfilerne og skriver observationerne til regnearket så de
er klar til brug i beregninger.

UDTRÆK-OBSERVATIONER henter observationer ud af databasen på baggrund af udvalgte
søgekriterier og skrives til regnearket, så de kan bruges i beregninger.

REGN beregner nye koter til alle punkter, og genererer rapporter og
visualiseringsmateriale.

ILÆG-OBSERVATIONER lægger nye observationer i databasen.

ILÆG-NYE-KOTER lægger nyberegnede koter i databasen.

LUK-SAG arkiverer det afsluttende regneark og sætter sagens status til inaktiv.

\b
Eksempel
--------

    {grøn('fire niv opret-sag andeby_2020 "Vedligehold Andeby"')}

    {grøn('fire niv udtræk-revision andeby_2020 K-99 102-08')}

    {grøn('fire niv ilæg-revision andeby_2020')}

    {grøn('fire niv ilæg-nye-punkter andeby_2020')}

    {grøn('fire niv læs-observationer andeby_2020')}

    {grøn('fire niv regn andeby_2020')}     <- kontrolberegning

    {grøn('fire niv regn andeby_2020')}     <- endelig beregning

    {grøn('fire niv ilæg-observationer andeby_2020')}

    {grøn('fire niv ilæg-nye-koter andeby_2020')}

    {grøn('fire niv luk-sag andeby_2020')}
"""


@click.group(help=niv_help)
def niv():
    pass


# ------------------------------------------------------------------------------
# Hjælpefunktioner
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
def anvendte(arkdef: Dict) -> str:
    """Anvendte søjler for given arkdef"""
    n = len(arkdef)
    if (n < 1) or (n > 26):
        return ""
    return "A:" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[n - 1]


def påfør_df_style(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """
    Påfør en style til en dataframe inden den gemmes som excel

    Efter pandas 3 er alt styling som default fjernet når en DataFrame gemmes som Excel.
    Vi sætter derfor her eksplicit style til den tidligere default, som var at kolonnenavne
    gemmes med fed skrift og fuldt optrukne cellekanter.

    For mere info se: https://pandas.pydata.org/docs/user_guide/io.html#style-and-formatting
    """
    # Hvis dataframen ikke har nogen kolonner, som fx. fanebladet "Projektforside", så går
    # der ged i den
    if len(df.columns) == 0:
        return df

    css = "border: 1px solid black; font-weight: bold;"
    return df.style.map_index(lambda x: css, axis=1)


def juster_kolonnebredder(faneblad: Worksheet):
    """Juster fanebladets kolonnebredder

    For hver kolonne sættes bredden lig længden af den længste celle + 1.
    For at begrænse bredden ved meget lange tekstfelter som fx. fikspunktbeskrivelser,
    anvendes en maximal bredde på 40.
    """
    max_bredde = 40
    for kolonne in faneblad.columns:
        kolonnebredde = min(
            max([len(str(row.value)) for row in kolonne]) + 1, max_bredde
        )
        faneblad.column_dimensions[kolonne[0].column_letter].width = kolonnebredde


# -----------------------------------------------------------------------------
def skriv_ark(
    projektnavn: str, nye_faneblade: Dict[str, pd.DataFrame], suffix: str = ""
) -> bool:
    """Skriv resultater til excel-fil

    Basalt en temmeligt simpel operation, men virkemåden er næsten overskygget af
    kontroller af at filoperationer gik godt. Det er et vilkår ved interaktioner
    med filsystemer, så for overblikkets skyld kommer her en kort prosabeskrivelse.

    1. Flyt projektnavn.xlsx til projektnavn-ex.xlsx
    2. Læs dict gamle_faneblade fra projektnavn-ex.xlsx
    3. Fjern elementer fra gamle_faneblade hvis navnet også findes i nye_faneblade
    4. Skriv nye_faneblade til projektnavn.xlsx
    5. Skriv gamle_faneblade til projektnavn.xlsx

    Trin 4 kommer før trin 5 for at sikre at de nye faneblade er umiddelbart
    synlige når man åbner projektnavn.xlsx

    Eller mere direkte sagt:

    ```
    fil = Path(f"{projektnavn}{suffix}.xlsx")
    exfil = Path(f"{projektnavn}{suffix}-ex.xlsx")
    fil.replace(exfil)

    gamle_faneblade = pd.read_excel(exfil, sheet_name=None)
    for fanebladnavn in set(gamle_faneblade).intersection(nye_faneblade):
        gamle_faneblade.pop(fanebladnavn)

    with pd.ExcelWriter(fil) as writer:
        skriv nye_faneblade
        skriv gamle_faneblade
    ```

    Hvilket er i omegnen af en faktor 10 mindre end den implementerede
    version - men *it's a jungle out there*...
    """

    fil = Path(f"{projektnavn}{suffix}.xlsx")
    exfil = Path(f"{projektnavn}{suffix}-ex.xlsx")
    nye_navne = set(nye_faneblade)

    # Gå med seler og livrem: Læs fanebladsnavne fra originalfilen,
    #  så vi kan checke at alt kom helskindet med over i exfilen.
    #
    # NB: man kan læse en excelfil selv om den er åben. Derfor er
    # læsefejl her ikke tegn på at filen er åben (eller af anden
    # årsag låst), men på at filen ikke eksisterer.
    try:
        gamle_navne = set(pd.read_excel(fil, sheet_name=None))
    except Exception as ex:
        fire.cli.print(f"Filen '{fil}' findes ikke.")
        gamle_navne = set()

    fire.cli.print(f"Skriver: {nye_navne}")
    fire.cli.print(f"Til filen '{fil}'")

    # Størstedelen af "det der skal gøres" skal kun gøres hvis
    # vi skriver til en allerede eksisterende fil
    if gamle_navne:
        if len(gamle_navne.intersection(nye_navne)) > 0:
            fire.cli.print(
                f"Overskriver fanebladene {gamle_navne.intersection(nye_navne)}"
            )
            fire.cli.print(f"    med opdaterede versioner.")
            fire.cli.print(f"Foregående versioner beholdes i 'ex'-filen '{exfil}'")

        # Vi starter med at omdøbe fil.xlsx til fil-ex.xlsx - det giver sikkerhed
        # for på at ingen af filerne er i brug
        while True:
            try:
                fil.replace(exfil)
                break
            except Exception as ex:
                fire.cli.print(
                    f"Kan ikke håndtere '{fil}' - måske fordi den eller '{exfil}' er åben.",
                    fg="yellow",
                    bold=True,
                )
                fire.cli.print(f"Anden mulig årsag: {ex}")
                if input("Luk fil og prøv igen ([j]/n)? ") in ["j", "J", "ja", ""]:
                    continue
                fire.cli.print("Dropper skrivning")
                return False

        # Så læser vi de eksisterende faneblade.
        #
        # NB: Her er der risiko for en race condition (da konkurrence-tilstand?):
        # Vi holder ikke en lås på exfilen når den opstår ved omdøbning af
        # projektfilen, så den kan overskrives af eksterne processer *efter* at vi har
        # omdøbt projektfilen og *inden* vi når videre hertil.
        #
        # Så her, og formodentlig overalt i FIRE, bortset fra databaseadgang, antager vi
        # at benspænd fra eksterne processer er sjældne og ignorable.
        #
        # Langt de fleste tænkelige benspænd af den slags vil enten fanges af
        # undtagelseshåndteringen, eller af "seler og livrem"-mekanismen omtalt ovenfor.
        try:
            gamle_faneblade = pd.read_excel(exfil, sheet_name=None)
        except Exception as ex:
            fire.cli.print(
                f"Kan ikke læse '{exfil}' - dropper skrivning af '{nye_navne}'.",
                fg="yellow",
                bold=True,
            )
            fire.cli.print(f"Systemfejlmeddelelse: {ex}")
            return False

        # Afslut seler og livrem: Check at fanebladnavnene stemmer
        if set(gamle_faneblade) != gamle_navne:
            fire.cli.print(
                f"Noget gik galt ved flytning af '{fil}' til '{exfil}'.",
                fg="yellow",
                bold=True,
            )
            fire.cli.print(f"    Dropper skrivning af '{nye_navne}'.")
            return False

        # Fjern gamle faneblade hvis der findes et nyt med samme navn
        for fanebladnavn in gamle_navne.intersection(nye_faneblade):
            gamle_faneblade.pop(fanebladnavn)
    else:
        gamle_faneblade = dict()

    # Skriv de nye faneblade, efterfulgt af de resterende gamle til den
    # opdaterede fil.
    # Derved bliver de nye faneblade umiddelbart synlige, når arket åbnes.
    try:
        with pd.ExcelWriter(fil) as writer:
            for navn, df in nye_faneblade.items():
                stylet_df = påfør_df_style(df)
                stylet_df.to_excel(writer, sheet_name=navn, index=False)
                juster_kolonnebredder(writer.sheets[navn])

            for navn, df in gamle_faneblade.items():
                stylet_df = påfør_df_style(df)
                stylet_df.to_excel(writer, sheet_name=navn, index=False)
                juster_kolonnebredder(writer.sheets[navn])

    except Exception as ex:
        fire.cli.print(f"Kan ikke skrive opdateret '{fil}'!")
        if gamle_navne:
            fire.cli.print(f"Gammel version er stadig tilgængelig som '{exfil}'.")
        fire.cli.print(f"Systemfejlmeddelelse: {ex}")
        return False
    return True


# ------------------------------------------------------------------------------
def find_faneblad(
    projektnavn: str, faneblad: str, arkdef: Dict, ignore_failure: bool = False
) -> pd.DataFrame:
    try:
        raw = pd.read_excel(
            f"{projektnavn}.xlsx",
            sheet_name=faneblad,
            usecols=anvendte(arkdef),
        ).dropna(how="all")

        if set(raw.columns) ^ set(arkdef):
            fire.cli.print(
                f"Kolonnenavne i fanebladet '{faneblad}' matcher ikke arkdefinitionens\n\n    {list(arkdef.keys())}\n"
            )
            fire.cli.print(f"Undersøg eventuelt, om der er dubletter i kolonnenavnene.")
            fire.cli.print(
                "(Er der to kolonner med samme navn, bliver kun den sidste kolonne indlæst.)"
            )
            raise SystemExit(1)

        raw = raw.astype(arkdef)
        raw[raw.select_dtypes(str).columns] = raw.select_dtypes(str).fillna("")

        return raw

    except Exception as ex:
        if ignore_failure:
            return None
        fire.cli.print(f"Kan ikke læse {faneblad} fra '{projektnavn}.xlsx'")
        fire.cli.print(f"Mulig årsag: {ex}")
        raise SystemExit(1)


# ------------------------------------------------------------------------------
def gyldighedstidspunkt(projektnavn: str) -> datetime.datetime:
    """Tid for sidste observation der har været brugt i beregningen"""
    obs = find_faneblad(projektnavn, "Observationer", arkdef.OBSERVATIONER)
    obs = obs[obs["Sluk"] != "x"]
    return max(obs["Hvornår"])


def find_parameter(projektnavn: str, parameter: str) -> str:
    """Find parameter fra et projektregneark"""
    param = find_faneblad(projektnavn, "Parametre", arkdef.PARAM)
    if parameter not in list(param["Navn"]):
        fire.cli.print(f"FEJL: '{parameter}' ikke angivet under fanebladet 'Parametre'")
        raise SystemExit(1)

    return param.loc[param["Navn"] == f"{parameter}"]["Værdi"].to_string(index=False)


# -----------------------------------------------------------------------------
def find_sag(projektnavn: str, accepter_inaktiv=False) -> Sag:
    """Bomb hvis sag for projektnavn ikke er oprettet. Ellers returnér sagen"""
    if not os.path.isfile(f"{projektnavn}.xlsx"):
        fire.cli.print(
            f"FEJL: Filen '{projektnavn}.xlsx' ikke fundet - står du i den rigtige folder?",
            bold=True,
            bg="red",
        )
        raise SystemExit(1)

    sagsgang = find_sagsgang(projektnavn)
    sagsid = find_sagsid(sagsgang)
    try:
        sag = fire.cli.firedb.hent_sag(sagsid)
    except:
        fire.cli.print(
            f" Sag for {projektnavn} er endnu ikke oprettet - brug fire niv opret-sag! ",
            bold=True,
            bg="red",
        )
        raise SystemExit(1)
    if not accepter_inaktiv and not sag.aktiv:
        fire.cli.print(
            f"Sag {sagsid} for {projektnavn} er markeret inaktiv. Genåbn for at gå videre."
        )
        raise SystemExit(1)
    return sag


# ------------------------------------------------------------------------------
def find_sagsgang(projektnavn: str) -> pd.DataFrame:
    """Udtræk sagsgangsregneark fra Excelmappe"""
    return pd.read_excel(f"{projektnavn}.xlsx", sheet_name="Sagsgang")


# ------------------------------------------------------------------------------
def find_sagsid(sagsgang: pd.DataFrame) -> str:
    sag = sagsgang.index[sagsgang["Hændelse"] == "sagsoprettelse"].tolist()
    assert (
        len(sag) == 1
    ), "Der skal være præcis 1 hændelse af type sagsoprettelse i arket"
    i = sag[0]
    if not pd.isna(sagsgang.uuid[i]):
        return str(sagsgang.uuid[i])
    return ""


def bekræft(spørgsmål: str, gentag=True) -> bool:
    """
    Anmod bruger om at tage stilling til spørgsmålet.
    """
    fire.cli.print(f"{spørgsmål} (ja/NEJ):")

    if input().strip().lower() != "ja":
        return False

    if not gentag:
        return True

    return input("Gentag svar for at bekræfte (ja/NEJ)\n").strip().lower() == "ja"


def opret_region_punktinfo(punkt: Punkt) -> PunktInformation:
    """Opret regionspunktinfo for et nyt punkt"""

    e = punkt.geometri.koordinater[0]

    # Regionen kan detekteres alene ud fra længdegraden, hvis vi holder os til
    # {DK, EE, FO, GL}. EE er dog ikke understøttet her: Hvis man forsøger at
    # oprette nye estiske punkter vil de blive tildelt region DK
    if e > 0:
        region = "REGION:DK"
    elif e < -11:
        region = "REGION:GL"
    else:
        region = "REGION:FO"

    # indsæt region
    pit = fire.cli.firedb.hent_punktinformationtype(region)
    if pit is None:
        fire.cli.print(f"Kan ikke finde region '{region}'")
        raise SystemExit(1)

    return PunktInformation(infotype=pit, punkt=punkt)


def er_projekt_okay(projektnavn: str) -> None:
    """
    Kontroller om det er okay at bruge et givet projekt.

    Afbryder programmet og udskriver en fejl, hvis ikke projektet er okay.

    Ellers gøres intet.
    """
    projekt_db = find_parameter(projektnavn, "Database")
    if projekt_db != fire.cli.firedb.db:
        fire.cli.print(
            f"FEJL: '{projektnavn}' er oprettet i {projekt_db}-databasen - du forbinder til {fire.cli.firedb.db}-databasen!",
            bold=True,
            bg="red",
        )
        raise SystemExit(1)

    fil_version = packaging.version.parse(find_parameter(projektnavn, "Version"))
    fire_version = packaging.version.parse(fire.__version__)
    if fil_version.major != fire_version.major:
        fire.cli.print(
            f"FEJL: '{projektnavn}' er oprettet med version {fil_version} - du har version {fire_version} installeret!",
            bold=True,
            bg="red",
        )
        raise SystemExit(1)

    if fil_version.minor > fire_version.minor:
        fire.cli.print(
            f"ADVARSEL: '{projektnavn}' er oprettet med version {fil_version} - du har version {fire_version} installeret!",
            bold=True,
            bg="yellow",
        )
        return


def udled_jessenpunkt_fra_punktoversigt(
    punktoversigt: pd.DataFrame,
) -> tuple[float, Punkt]:
    """
    Udleder Jessenpunktet ud fra oplysningerne i Punktoversigten.

    Returnerer oplysninger om det validerede jessenpunkt.
    """

    # Tjek om der er anvendt Jessen-system
    # Denne er et sanity-tjek -- Man skal ville det hvis man vil oprette punktsamlinger!
    if len(set(punktoversigt["System"])) > 1:
        fire.cli.print(
            "FEJL: Flere forskellige højdereferencesystemer er angivet i Punktoversigt!",
            fg="white",
            bg="red",
            bold=True,
        )
        raise SystemExit(1)

    kotesystem = punktoversigt["System"].iloc[0]
    if kotesystem != "Jessen":
        fire.cli.print(
            "FEJL: Kotesystem skal være 'Jessen'",
            fg="white",
            bg="red",
            bold=True,
        )
        raise SystemExit(1)

    # Tjek om der kun er ét fastholdt punkt, og gør brugeren opmærksom på hvis punktet
    # ikke har et Jessennummer.
    fastholdte_punkter = punktoversigt["Punkt"][punktoversigt["Fasthold"] != ""]
    fastholdte_koter = punktoversigt["Kote"][punktoversigt["Fasthold"] != ""]

    if len(fastholdte_punkter) != 1:
        fire.cli.print(
            "FEJL: Punktsamlinger kræver netop ét fastholdt Jessenpunkt.",
            fg="white",
            bg="red",
            bold=True,
        )
        raise SystemExit(1)

    if pd.isna(fastholdte_koter).any():
        fire.cli.print(
            "FEJL: Fastholdt punkt har ikke nogen fastholdt kote!",
            fg="white",
            bg="red",
            bold=True,
        )
        raise SystemExit(1)

    jessenpunkt_ident = fastholdte_punkter.iloc[0]
    jessenpunkt_kote = fastholdte_koter.iloc[0]

    try:
        jessenpunkt = fire.cli.firedb.hent_punkt(jessenpunkt_ident)
    except NoResultFound:
        fire.cli.print(
            f"FEJL: Kunne ikke finde Jessenpunktet {jessenpunkt_ident} i databasen!",
            fg="white",
            bg="red",
            bold=True,
        )
        raise SystemExit(1)

    return jessenpunkt_kote, jessenpunkt


def afbryd_hvis_ugyldigt_jessenpunkt(jessenpunkt: Punkt) -> None:
    """Smid fejl hvis valgt jessenpunkt ikke er et registreret jessenpunkt"""
    if not jessenpunkt.jessennummer:
        fire.cli.print(
            f"FEJL: Jessenpunktet {jessenpunkt.ident} har intet Jessennummer. "
            "Jessennummer kan oprettes igennem Punktrevision ved indsættelse af IDENT:jessen og NET:jessen.",
            fg="black",
            bg="yellow",
        )
        raise SystemExit(1)


def hent_relevante_tidsserier(
    hts_ark: pd.DataFrame, punkt: Punkt, fastholdt_punkt: Punkt, fastholdt_kote: float
) -> list[Tidsserie]:
    """
    Henter de relevante tidsserier fra Højdetidsserier-arket

    Med "relevante" skal forstås tidsserier der har ``punkt`` som punkt, og som hører
    under en punktsamling der har ``fastholdt_punkt`` og ``fastholdt_kote`` som fastholdt
    punkt hhv. kote.

    Derudover kontrolleres oplysningerne i Højdetidsserier-fanen. Hvis de er forkerte
    udsendes fejlmeddelelser.
    """
    # Gå igennem alle punktets tidsserier i arket
    tidsserier = []
    for index, htsdata in hts_ark[hts_ark["Punkt"] == punkt.ident].iterrows():

        # Den her fejler hvis man opgiver en tidsserie i HTS-fanen som ikke findes!
        tidsserie = fire.cli.firedb.hent_tidsserie(htsdata["Tidsserienavn"])

        # Den her fejler hvis den fundne tidsserie ikke har punkt som punkt
        # Vil kun ske hvis man manuelt har tastet noget mærkeligt ind i arket.
        if tidsserie.punkt != punkt:
            fire.cli.print(
                f"FEJL: Mismatch mellem punkt {punkt.ident} og tidsserie {tidsserie.navn}!",
                fg="white",
                bg="red",
                bold=True,
            )
            raise SystemExit(1)

        # Samme som ovenstående, men for Punktgruppenavn
        if tidsserie.punktsamling.navn != htsdata["Punktgruppenavn"]:
            fire.cli.print(
                f"FEJL: Mismatch mellem punktgruppe {htsdata['Punktgruppenavn']} og tidsserie {tidsserie.navn}!",
                fg="white",
                bg="red",
                bold=True,
            )
            raise SystemExit(1)

        if (
            tidsserie.punktsamling.jessenpunkt != fastholdt_punkt
            or tidsserie.punktsamling.jessenkote != fastholdt_kote
        ):
            # Spring tidsserier over som ikke matcher det fastholdte punkt/kote
            # Brugeren bliver nødt til at angive hvilke tidsserier der skal have opdateret
            # koten.
            continue

        tidsserier.append(tidsserie)

    if not tidsserier:
        fire.cli.print(f"Fandt ingen relevante tidsserier for {punkt.ident}")

    return tidsserier


"""
Modulnavne starter med `_` for at undgå konflikter,
der i visse tilfælde kan opstå.

Med nedenstående kan man entydigt kende forskel på modulet

    fire.cli.niv._opret-sag

og Click-kommandoobjektet

    fire.cli.niv.opret-sag

. Uden præfix kan der ikke skelnes mellem de to.

"""
from fire.cli.niv._ilæg_nye_koter import ilæg_nye_koter
from fire.cli.niv._ilæg_nye_punkter import ilæg_nye_punkter
from fire.cli.niv._ilæg_observationer import ilæg_observationer
from fire.cli.niv._ilæg_revision import ilæg_revision
from fire.cli.niv._luk_sag import luk_sag
from fire.cli.niv._læs_observationer import læs_observationer
from fire.cli.niv._netoversigt import netoversigt
from fire.cli.niv._opret_sag import opret_sag
from fire.cli.niv._regn import regn
from fire.cli.niv._udtræk_observationer import udtræk_observationer
from fire.cli.niv._udtræk_revision import udtræk_revision
from fire.cli.niv.punktsamling import (
    opret_punktsamling,
    udtræk_punktsamling,
    ilæg_punktsamling,
    ilæg_tidsserie,
    fjern_punkt_fra_punktsamling,
)
from fire.cli.niv._åbn_sag import åbn_sag
