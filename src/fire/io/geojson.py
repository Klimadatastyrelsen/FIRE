"""
Modul til håndtering af læsning og skrivning geojson-filer
"""

from dataclasses import asdict
import json
import math

import pandas as pd
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import DatabaseError

from fire.api.model import (
    Punkt,
)
from fire.ident import kan_være_gi_nummer
from fire.cli import firedb
from fire.api.niv.datatyper import (
    PunktNavn,
    NivKote,
)
from fire.api.niv.lukkesum import (
    LinjeStats,
    LukkesumStats,
)


def _geojson_filnavn(projektnavn: str, infiks: str, variant: str):
    """Generer filnavn på geojson-fil"""
    return f"{projektnavn}{infiks}-{variant}.geojson"


def punkt_feature(punkter: pd.DataFrame) -> dict[str, str]:
    """Omsæt punktinformationer til JSON-egnet dict"""

    def _none_eller_nan(værdi: float) -> bool:
        """
        Check om værdi er None eller NaN.

        Vi checker både for None og NaN, da Pandas og Numpy kan være lidt
        drilske på dette område, og har udvist skiftende adfærd gennem tiden.
        """
        return værdi is None or math.isnan(værdi)

    for i in range(punkter.shape[0]):
        # Nye punkter har hverken ny eller gammel kote.
        # Vi rammer ind i denne situation ved læsning af observationer til nye punkter,
        # der endnu ikke er regnet en kote for.
        if _none_eller_nan(punkter.at[i, "Kote"]) and _none_eller_nan(
            punkter.at[i, "Ny kote"]
        ):
            fastholdt = False
            delta = None
            kote = None
            sigma = None

        # Fastholdte punkter har ingen ny kote, så vi viser den gamle
        elif punkter.at[i, "Fasthold"] != "" and not pd.isna(punkter.at[i, "Fasthold"]):
            fastholdt = True
            delta = 0.0
            kote = float(punkter.at[i, "Kote"])
            sigma = float(punkter.at[i, "σ"])

        # Gamle punkter med nye koter er "standardtilfældet"
        else:
            fastholdt = False
            delta = float(punkter.at[i, "Δ-kote [mm]"])
            kote = float(punkter.at[i, "Ny kote"])
            sigma = float(punkter.at[i, "Ny σ"])

        # Ignorerede ændringer (under 1 um)
        if _none_eller_nan(delta):
            delta = None

        # Forbered punktnumre til attributtabellen. Hvis muligt finder vi information
        # i databasen og bruger punktets landsnummer som ID, ellers bruges strengen
        # der kommer fra Dataframe'n.
        try:
            punkt = firedb.hent_punkt(punkter.at[i, "Punkt"])
            landsnr = punkt.landsnummer
            gi_nummer = punkt.ident if kan_være_gi_nummer(punkt.ident) else None
        except (NoResultFound, DatabaseError):
            landsnr = punkter.at[i, "Punkt"]
            gi_nummer = None

        feature = {
            "type": "Feature",
            "properties": {
                "id": landsnr,
                "GI": gi_nummer,
                "H": kote,
                "sH": sigma,
                "Δ": delta,
                "fastholdt": fastholdt,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [punkter.at[i, "Øst"], punkter.at[i, "Nord"]],
            },
        }
        yield feature


def punkter_geojson(
    punkter: pd.DataFrame,
) -> str:
    """Returner punkter/koordinater som geojson-streng"""
    til_json = {
        "type": "FeatureCollection",
        "Features": list(punkt_feature(punkter)),
    }
    return json.dumps(til_json, indent=4)


def skriv_punkter_geojson(projektnavn: str, punkter: pd.DataFrame, infiks: str = ""):
    """Skriv geojson-fil med punktdata til disk"""
    geojson = punkter_geojson(punkter)
    filnavn = _geojson_filnavn(projektnavn, infiks, "punkter")
    with open(filnavn, "wt") as punktfil:
        punktfil.write(geojson)


def obs_feature(
    punkter: pd.DataFrame, observationer: pd.DataFrame, antal_målinger: dict[tuple, int]
) -> dict[str, str]:
    """Omsæt observationsinformationer til JSON-egnet dict"""
    for i in range(observationer.shape[0]):
        fra = observationer.at[i, "Fra"]
        til = observationer.at[i, "Til"]
        feature = {
            "type": "Feature",
            "properties": {
                "Fra": fra,
                "Til": til,
                "Målinger": antal_målinger[tuple(sorted([fra, til]))],
                "Afstand": observationer.at[i, "L"],
                "ΔH": observationer.at[i, "ΔH"],
                "Observationstidspunkt": str(observationer.at[i, "Hvornår"]),
                # konvertering, da json.dump ikke uderstøtter int64
                "Opstillinger": int(observationer.at[i, "Opst"]),
                "Journal": observationer.at[i, "Journal"],
                "Type": observationer.at[i, "Type"],
                "Slukket": observationer.at[i, "Sluk"],
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [punkter.at[fra, "Øst"], punkter.at[fra, "Nord"]],
                    [punkter.at[til, "Øst"], punkter.at[til, "Nord"]],
                ],
            },
        }
        yield feature


def observationer_geojson(
    punkter: pd.DataFrame,
    observationer: pd.DataFrame,
) -> None:
    """Skriv observationer til geojson-fil"""

    fra = observationer["Fra"]
    til = observationer["Til"]

    # Optæl antal frem-og/eller-tilbagemålinger pr. strækning: Vi starter
    # med en dict med et nul for hver strækning
    par = [tuple(p) for p in zip(fra, til)]
    antal_målinger = dict((tuple(sorted(p)), 0) for p in par)
    # ...og så tæller vi det relevante element op for hver observation
    for p in par:
        # Indeksering med tuple(sorted(p)) da set(p) ikke kan hashes
        antal_målinger[tuple(sorted(p))] += 1

    til_json = {
        "type": "FeatureCollection",
        "Features": list(obs_feature(punkter, observationer, antal_målinger)),
    }

    return json.dumps(til_json, indent=4)


def skriv_observationer_geojson(
    projektnavn: str,
    punkter: pd.DataFrame,
    observationer: pd.DataFrame,
    infiks: str = "",
) -> None:
    """Skriv geojson-fil med observationsdata til disk"""
    filnavn = _geojson_filnavn(projektnavn, infiks, "observationer")
    geojson = observationer_geojson(punkter, observationer)
    with open(filnavn, "wt") as obsfil:
        obsfil.write(geojson)


def skriv_sagsrapport_geojson(filnavn: str, punkter: list[Punkt], attributter: dict):
    """
    Skriv geojson-fil med sagsstatistik for punkter til disk

    Er en hjælpefunktion til ``fire info sag``

    Punkternes attributter forventes indeholdt i en dict med attributternes navne som
    nøgle og lister af punkt-uuider. Eksempelvis:

    attributter = {
        tabtgået     = [UUID_A, UUID_B, UUID_C],
        oprettet     = [UUID_D, UUID_E, UUID_F],
        observeret   = [UUID_A, UUID_B],
        min_attribut = [UUID_X, UUID_Y],
    }

    """

    def _punkt_feature(punkter: list[Punkt], attributter: dict):
        for pkt in punkter:
            properties = dict(id=str(pkt.landsnummer))
            properties |= {
                attribut: (pkt.id in punkter_med_attribut)
                for attribut, punkter_med_attribut in attributter.items()
            }

            feature = {
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        pkt.geometri.koordinater[0],
                        pkt.geometri.koordinater[1],
                    ],
                },
            }
            yield feature

    til_json = {
        "type": "FeatureCollection",
        "Features": list(_punkt_feature(punkter, attributter)),
    }
    geojson = json.dumps(til_json, indent=4)

    with open(filnavn, "wt") as punktfil:
        punktfil.write(geojson)


def polygon_feature(
    punkter: dict[str, NivKote],
    polygoner: dict[tuple[PunktNavn], LukkesumStats | dict],
):
    """
    For hver polygon laves en feature som indeholder de givne attributter.

    Det antages mere eller mindre at `polygoner`, er output fra
    `RegneMotor.beregn_lukkesummer`, og dermed at polygonerne er lukkede.
    """
    for polygon, attributter in polygoner.items():
        try:
            # Antag at "attributter" er en dataklasse der kan laves om til en dict
            attrs = asdict(attributter)
            attrs.pop("linjer")  # vi skal ikke have alle linjerne med i geojsonen
        except TypeError:
            # Ellers antager vi at det allerede en dict, som kan gemmes i json format.
            pass

        feature = {
            "type": "Feature",
            "properties": attrs,
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [punkter[pkt].øst, punkter[pkt].nord]
                        for pkt in polygon + polygon[:1]
                    ]
                ],
            },
        }

        yield feature


def skriv_polygoner_geojson(
    filnavn: str,
    punkter: dict[PunktNavn, NivKote],
    polygoner: dict[tuple[PunktNavn], LukkesumStats],
):
    til_json = {
        "type": "FeatureCollection",
        "Features": list(polygon_feature(punkter, polygoner)),
    }
    geojson = json.dumps(til_json, indent=4)

    with open(filnavn, "wt") as polygonfil:
        polygonfil.write(geojson)


def netoversigt_linjer_feature(
    punkter: dict[str, NivKote],
    linjer: list[LinjeStats],
):
    """
    For hver linje laves en feature som indeholder de givne `LinjeStats`.
    """
    for linje in linjer:
        fra, til = linje.fra, linje.til
        # Lav en LinjeStats dataklasse om til en dict
        attrs = asdict(linje)

        feature = {
            "type": "Feature",
            "properties": attrs,
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [punkter[fra].øst, punkter[fra].nord],
                    [punkter[til].øst, punkter[til].nord],
                ],
            },
        }

        yield feature


def skriv_netoversigt_linjer_geojson(
    filnavn: str, punkter: dict[PunktNavn, NivKote], linjer: list[LinjeStats]
):

    til_json = {
        "type": "FeatureCollection",
        "Features": list(netoversigt_linjer_feature(punkter, linjer)),
    }
    geojson = json.dumps(til_json, indent=4)

    with open(filnavn, "wt") as obsfil:
        obsfil.write(geojson)
