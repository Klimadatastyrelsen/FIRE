import click
import pandas as pd

from fire.io.regneark import arkdef
import fire.cli
from fire.api.niv.regnemotor import (
    RegneMotor,
    GamaRegn,
)
from fire.api.niv.lukkesum import (
    LinjeStats,
    aggreger_multidigraf,
)
from fire.io.geojson import (
    skriv_polygoner_geojson,
    skriv_netoversigt_linjer_geojson,
)
from fire.cli.niv import (
    find_faneblad,
    niv,
    skriv_ark,
    er_projekt_okay,
)
from fire.cli.exceptions import (
    advarsel,
)


@niv.command()
@fire.cli.default_options()
@click.argument(
    "projektnavn",
    nargs=1,
    type=str,
)
def netoversigt(projektnavn: str, **kwargs) -> None:
    """
    Opbyg netoversigt og beregn lukkesummer

    Læser fanebladet Observationer og udfører netanalyse der undersøger om observationerne
    er sammenhængede og identificerer singulære punkter. Netanalysen gemmes i
    sagsregnearket i fanebladene "Netgeometri" og "Singulære".

    For hver nivellementslinje beregnes diskrepansen ϱ (rho), imellem frem- og
    tilbagenivellement. Derudover identificeres lukkede polygoner i nettet, for hvilke der
    beregnes lukkesummer. En polygon er kun gyldig hvis der findes både frem- og
    tilbage-nivellement imellem alle punkter i polygonen. For hver polygon beregnes
    lukkesum, summa rho, og samlet sigtelængde. Lukkesum og summa rho normaliseres desuden
    med kvadratrod af sigtelængden.
    Se nedenfor for de fulde lister af beregnede størrelser.

    For hver polygon beregnes følgende størrelser::

    \b
    Størrelse [Enhed]        Beskrivelse
    =======================  ====================================================================
    Σϱ        [mm]           "Summa rho", samlet diskrepans imellem frem- og tilbage nivellement
    (Σϱ)'     [mm/sqrt(km)]  "Summa rho mærke", normaliseret samlet diskrepans
    ε         [mm]           Lukkesum for alle observationer langs polygonen
    ε_frem    [mm]           Lukkesum for frem-observationer
    ε_tilbage [mm]           Lukkesum for tilbage-observationer
    ε'        [mm/sqrt(km)]  Lukkesum normaliseret efter samlet sigtelængde.
    ε_frem'   [mm/sqrt(km)]  Frem-lukkesum normaliseret efter samlet frem-sigtelængde
    ε_tilbage'[mm/sqrt(km)]  Tilbage-lukkesum normaliseret efter samlet tilbage-sigtelængde
    L         [m]            Gennemsnit af samlet frem- og tilbage-sigtelængder.
    L_frem    [m]            Sum af frem-sigtelængder
    L_tilbage [m]            Sum af tilbage-sigtelængder

    Resultaterne af lukkesumsberegningen gemmes som geojson, der kan åbnes i
    et GIS-program.

    For hver nivellementslinje beregnes der foruden diskrepansen ϱ, også gennemsnit af
    frem- hhv. tilbage-observationer. Dette gøres i tilfælde af, at der findes mere end én
    observation i hver retning::

    \b
    Størrelse [Enhed]         Beskrivelse
    ========================  ====================================================================
    ΔH         [m]            Gennemsnitlig "frem"-ΔH, af både frem- og tilbage observationer
    ΔH_frem    [m]            Gennemsnit af frem-observationer
    ΔH_tilbage [m]            Gennemsnit af tilbage-observationer
    ϱ          [mm]           "rho", diskrepans imellem frem- og tilbage nivellement
    ϱ'         [mm/sqrt(km)]  "rho mærke", normaliseret diskrepans
    l          [m]            Gennemsnit af samlet frem- og tilbage-sigtelængder.
    l_frem     [m]            Gennemsnit af frem-sigtelængder
    l_tilbage  [m]            Gennemsnit af tilbage-sigtelængder
    n_frem                    Antal frem-observationer
    n_tilbage                 Antal tilbage-observationer

    Resultaterne gemmes i en geojson-fil, som kan videreanalyseres bagefter i et
    GIS-program. Ud fra disse tal er det muligt, fx at beregne Σϱ for en vilkårlig gruppe
    af linjer eller lukkesum for andre polygoner, som dette program ikke har identificeret.

    \b
    Filnavn                                Beskrivelse
    =====================================  =========================================
    SAG-netoversigt-polygoner.geojson      Lukkesummer for alle fundne polygoner
    SAG-netoversigt-linjer.geojson         Statistik for de enkelte linjer
    """
    er_projekt_okay(projektnavn)
    fire.cli.print("Så kører vi")

    observationer = find_faneblad(projektnavn, "Observationer", arkdef.OBSERVATIONER)
    punktoversigt = find_faneblad(projektnavn, "Punktoversigt", arkdef.PUNKTOVERSIGT)

    # Fjern slukkede observationer
    observationer = observationer[observationer["Sluk"] != "x"]
    observationer = observationer.reset_index(drop=True)

    motor = GamaRegn.fra_dataframe(
        observationer, punktoversigt, projektnavn=projektnavn
    )

    # Analyser net
    net_uden_ensomme, ensomme_subnet, estimerbare_punkter = motor.netanalyse()
    if ensomme_subnet:
        advarseltekst = "Manglende fastholdt punkt i mindst et subnet! Forslag til fastholdte punkter i hvert subnet:"
        advarsel(advarseltekst)

        for i, forslag in enumerate(ensomme_subnet):
            fire.cli.print(f"  Subnet {i}: {forslag}", fg="red")

    resultater = byg_netgeometri_og_singulære(net_uden_ensomme, ensomme_subnet)

    # Lukkesumsberegning
    polygoner = motor.beregn_lukkesummer()
    if len(polygoner) != 0:
        filnavn = f"{projektnavn}-netoversigt-polygoner.geojson"
        fire.cli.print(f"Skriver '{filnavn}'")
        skriv_polygoner_geojson(filnavn, motor._gamle_koter, polygoner)

    digraf = aggreger_multidigraf(motor.multidigraf)

    # Hver linje ligger teknisk set dobbelt, hvor frem- og tilbage linjerne har omvendt fortegn.
    # Så vi looper over den simple version af grafen for kun at få hver linje med én gang
    # og hiver den pågældende linjestatistik ud.
    graf = digraf.to_undirected(reciprocal=True)
    linjer: list[LinjeStats] = [
        digraf[fra][til]["linjestats"] for fra, til in graf.edges
    ]
    linjer = [l.omregn_til_mm() for l in linjer]

    filnavn = f"{projektnavn}-netoversigt-linjer.geojson"
    fire.cli.print(f"Skriver '{filnavn}'")
    skriv_netoversigt_linjer_geojson(filnavn, motor._gamle_koter, linjer)

    skriv_ark(projektnavn, resultater, "-netoversigt")

    singulære_punkter = tuple(sorted(resultater["Singulære"]["Punkt"]))
    fire.cli.print(f"Fandt {len(singulære_punkter)} singulære punkter.")
    fire.cli.print(f"Fandt {len(polygoner)} polygoner.")


def byg_netgeometri_og_singulære(
    net_uden_ensomme: dict[str, list], ensomme_subnet: list
) -> dict[pd.DataFrame]:
    """Omsætter en netværksgraf og dens ensomme punkter til dataframes"""
    # Nu kommer der noget grimt...
    # Tving alle rækker til at være lige lange, så vi kan lave en dataframe af dem

    # Undgå ValueError pga max([]) hvis ingen fastholdte punkter.
    max_antal_naboer = 0
    if net_uden_ensomme:
        max_antal_naboer = max([len(net_uden_ensomme[e]) for e in net_uden_ensomme])

    nyt = {}
    for punkt in net_uden_ensomme:
        naboer = list(sorted(net_uden_ensomme[punkt])) + max_antal_naboer * [""]
        nyt[punkt] = tuple(naboer[0:max_antal_naboer])

    # Ombyg og omdøb søjler med smart "add_prefix"-trick fra
    # @piRSquared, https://stackoverflow.com/users/2336654/pirsquared
    # Se https://stackoverflow.com/questions/46078034/python-dict-with-values-as-tuples-to-pandas-dataframe
    netf = pd.DataFrame(nyt).T.rename_axis("Punkt").add_prefix("Nabo ").reset_index()
    netf = netf.sort_values(by="Punkt")
    netf = netf.reset_index(drop=True)

    ensomme_punkter = set().union(*ensomme_subnet)
    ensomme = pd.DataFrame(sorted(ensomme_punkter), columns=["Punkt"])

    return {"Netgeometri": netf, "Singulære": ensomme}
