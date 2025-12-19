from pathlib import Path
import webbrowser

import click
from pandas import DataFrame

from fire.api.model import (
    HøjdeTidsserie,
    Koordinat,
)
from fire.api.niv.regnemotor import (
    RegneMotor,
    GamaRegn,
    GeodætiskRegn,
    DVR90Regn,
    DumRegn,
    ValideringFejl,
    UdjævningFejl,
)

from fire.io.regneark import arkdef
from fire.io.geojson import (
    skriv_punkter_geojson,
    skriv_observationer_geojson,
)
import fire.cli

from fire.cli.ts.plot_ts import (
    plot_tidsserier,
)

from fire.cli.niv import (
    find_faneblad,
    niv,
    skriv_ark,
    er_projekt_okay,
    hent_relevante_tidsserier,
    udled_jessenpunkt_fra_punktoversigt,
)

from fire.cli.niv._netoversigt import byg_netgeometri_og_singulære

motorvælger = {
    "gama": GamaRegn,
    "geod": GeodætiskRegn,
    "dvr90": DVR90Regn,
    "DVR90": DVR90Regn,
    "dum": DumRegn,
}


@niv.command()
@fire.cli.default_options()
@click.argument("projektnavn", nargs=1, type=str)
@click.option(
    "-M",
    "--motor",
    "MotorKlasse",
    type=click.Choice(motorvælger.keys(), case_sensitive=False),
    callback=lambda ctx, param, val: motorvælger[val],
    default="gama",
    help="Angiv regnemotor. Som standard anvendes GNU Gama.",
)
@click.option(
    "-r",
    "--regneparameter",
    "regneparametre",
    multiple=True,
    help="Regnemotorspecifikke parametre. Sættes på formen 'parameter=værdi'. Flere parametre kan sættes i samme kommando.",
)
@click.option(
    "-P",
    "--plot",
    type=bool,
    is_flag=True,
    default=False,
    help="Angiv om beregnede koter skal plottes som forlængelse af en tidsserie",
)
def regn(
    projektnavn: str,
    plot: bool,
    MotorKlasse: type[RegneMotor],
    regneparametre: tuple[str],
    **kwargs,
) -> None:
    """Beregn nye koter.

    Forudsat nivellementsobservationer allerede er indlæst i sagsregnearket
    kan der beregnes nye koter på baggrund af disse observationer. Beregning
    af koter med dette program er en totrinsprocedure. Først udføres en
    kontrolberegning med et minimum af fastholdte punkter, med henblik på at
    kvaliteteskontrollere det tilgængelige observationsmateriale. Er der ingen
    åbenlyse fejl i observationerne kan der fortsættes til den endelige beregning.

    \f
    I den endelige beregning bør det overvejes mere grundigt hvilke punkter der
    fastholdes, samt om det kan være fordelagtigt at vægte nogle observationer
    højere eller lavere end andre.

    Hver kørsel af :program:`fire niv regn` starter med en analyse af det aktuelle
    nivellementsnet. Det er muligt at de indlæste observationer og punkter tilsammen
    udgør mere end et selvstændigt nivellementsnet, i så fald udgøres den samlede
    beregning af flere subnet. Udjævning i hvert subnet forudsætter mindst et
    fastholdt punkt. Når netanalysen er kørt vil programmet gøre opmærksom på hvis
    der er flere subnet og komme med forslag til et punkt i hvert subnet som kan
    fastholdes. Er der ingen fastholdte punkter afsluttes programmet med det samme.
    Netanalysen gemmes i sagsregnearket i fanebladene "Netgeometri" og "Singulære".
    Sidstnævnte er en oversigt over punkter der ikke er knyttet til resten af det
    målte net. "Netgeometri" beskriver hvordan nettet er opbygget ved at angive
    hvert punkts nabopunkter. Dette er blot en oversigt og bør ikke ændres af brugeren.

    Første gang :program:`fire niv regn` køres udføres kontrolberegningen. Den har
    til formål at sikre at opmålingsarbejdet er forløbet korrekt, herunder at

        1. der er målt til de rigtige punkter
        2. observationerne ikke helt er i skoven

    I fanebladet "Punktoversigt" angives hvilke punkter der skal fastholdes i
    kontrolberegningen. Sæt et "x" i kolonnen "Fasthold" for de relevante punkter.
    Typisk fastholdes kun et punkt pr subnet. Når beregningen er udført tilføjes
    fanebladet "Kontrolberegning" til sagsregnearket. Dette faneblad har samme opbygning
    som punktoversigten, dog nu med indhold i kolonnerne "Ny kote", "Ny σ", "Δ-kote"
    og "Opløft", der udgør beregningsresultatet.

    Den endelig beregning udføres ved at køre :program:`fire niv regn` igen. Hvis
    fanebladet "Kontrolberegning" er i sagsregnearket ved programmet det skal lave
    den endelige beregning. Er der behov for en ny kontrolberegning kan dette faneblad
    slettes og :program:`fire niv regn` køres på ny.
    I den endelige beregning finjusteres resultaterne fra kontrolberegningen. Formålet
    er, at producere de bedst mulige koter ud fra de tilgængelige observationer.
    Det *kan* indebære at fastholde andre punkter, eller måske flere end et.
    Det kan også være nødvendigt at vægte udvalgte observationer fra eller helt at
    udelukke dem fra udjævningen.
    Fastholdelse af punkter i den endelige beregning foretages i fanebladet "Kontrolberegning".
    Som udgangspunkt er de fastholdte punkter fra kontrolberegningen også markeret fastholdte
    i den endelige beregning. Er der behov for flere fastholdte punkter bør de angives med "e",
    så det er tydeligt hvilke fastholdte punkter der er forskellige fra kontrolberegningen.
    Vægten på de enkelte observationer kan justeres ved at ændre σ-værdien i fanebladet
    "Observationer" for den pågældende observation. Når den endelige beregning er udført
    findes resultatet i fanebladet "Endelig beregning".

    Udover beregningsresultaterne i sagsregnearket dannes der efter en beregning en række
    filer som placeres i samme mappe som sagsregnearket. Det drejer sig om beregningsrapporter
    m.m. fra udjævningsprogrammet GNU Gama og en række GIS-filer der indeholder et overblik
    over punkter og observationer, der indgår i udjævningen.

    Følgende filer relaterer sig til GNU Gama

    ==========================  =============================================================
    Filnavn                     Beskrivelse
    ==========================  =============================================================
    SAG.xml                     Input fil til gama, lavet ud fra data i regneark
    SAG-resultat.xml            Output fil fra gama, læses af fire og oversættes til regneark
    SAG-resultat-kontrol.html   Beregningsrapport for kontrolberegning
    SAG-resultat-endelig.html   Beregningsrapport for endelige beregning
    ==========================  =============================================================

    Input og output filer til Gama overskrives for hver beregning der udføres,
    men beregningsrapporten gemmes særskilt for kontrol og endelig beregning.

    De genererede GIS-filer er

    ==============================  ==============================================
    Filnavn                         Beskrivelse
    ==============================  ==============================================
    SAG-kon-punkter.geojson         Punkter brugt i kontrolberegningen
    SAG-kon-observationer.geojson   Observationer brugt i kontrolberegningen
    SAG-punkter.geojson             Punkter brugt i den endelige beregning
    SAG-observationer.geojson       Observationer brugt i den endelige beregning
    ==============================  ==============================================

    Formatet på GIS-filerne er GeoJSON, der let kan indlæses i QGIS for at danne et
    bedre overblik over nivellementsnettet der regnes på.
    """
    er_projekt_okay(projektnavn)

    # Hvis der ikke allerede findes et kontrolberegningsfaneblad, så er det en
    # kontrolberegning vi skal i gang med.
    kontrol = (
        find_faneblad(projektnavn, "Kontrolberegning", arkdef.PUNKTOVERSIGT, True)
        is None
    )

    # ...og så kan vi vælge den korrekte fanebladsprogression
    if kontrol:
        aktuelt_faneblad = "Punktoversigt"
        næste_faneblad = "Kontrolberegning"
        infiks = "-kon"
        beregningstype = "kontrol"
    else:
        aktuelt_faneblad = "Kontrolberegning"
        næste_faneblad = "Endelig beregning"
        infiks = ""
        beregningstype = "endelig"

    # Håndter fastholdte punkter og slukkede observationer.
    observationer = find_faneblad(projektnavn, "Observationer", arkdef.OBSERVATIONER)
    punktoversigt = find_faneblad(projektnavn, "Punktoversigt", arkdef.PUNKTOVERSIGT)
    arbejdssæt = find_faneblad(projektnavn, aktuelt_faneblad, arkdef.PUNKTOVERSIGT)
    parametre = find_faneblad(projektnavn, "Parametre", arkdef.PARAM)

    # Til den endelige beregning skal vi bruge de oprindelige observationsdatoer
    if not kontrol:
        arbejdssæt["Hvornår"] = punktoversigt["Hvornår"]

    # Inden regnemotoren sættes i gang tages der højde for slukkede observationer
    observationer_uden_slukkede = observationer[observationer["Sluk"] != "x"]

    # Tjek om der er parametre til regnemotoren. Parametre der ikke kan læses
    # springes over.
    motorkwargs = {}
    for regneparameter in regneparametre:
        try:
            parameter, værdi = regneparameter.split("=")
        except ValueError:
            fire.cli.print(
                (
                    f"ADVARSEL: regneparameteren '{regneparameter} kan ikke tolkes. "
                    "Skal være på formen 'parameter=værdi'."
                ),
                bold=True,
                bg="yellow",
            )
            continue

        # konverter til float hvis der er givet en talværdi
        try:
            værdi = float(værdi)
        except ValueError:
            pass

        motorkwargs[parameter] = værdi

    # Start regnemotoren!
    try:
        motor = MotorKlasse.fra_dataframe(
            observationer_uden_slukkede,
            arbejdssæt,
            projektnavn=projektnavn,
            **motorkwargs,
        )
    except TypeError as error:
        # Fejlbeskeden vi kan få er på formen:
        #
        # TypeError: RegneMotor.__init__() got an unexpected keyword argument 'param'
        #
        # ... og derfor kan vi slippe afsted med at splitte stringen på '
        parameter_navn = str(error).split("'")[1]
        fire.cli.print(
            f"FEJL: regneparameteren '{parameter_navn}' er ukendt.",
            bold=True,
            bg="red",
        )
        raise SystemExit

    # opdater Parametre i regneark (er vi kommet her til er alle angivne parametre gyldige)
    beregningsparametre = {"regnemotor": MotorKlasse.__name__}
    beregningsparametre.update(motor.parametre)
    for parameter, værdi in beregningsparametre.items():
        # Værdi for beregningsparameter omsættes til en streng
        if værdi is None:
            værdi = ""
        else:
            værdi = str(værdi)

        # findes parameter allerede i regnearket?
        findes_parameter = parameter in list(parametre["Navn"])
        if not kontrol:
            # kontrolværdi = find_parameter(projektnavn, parameter)
            if not findes_parameter:
                fire.cli.print(
                    (
                        f"ADVARSEL: {parameter}={værdi} sat i endelig beregning, "
                        "kontrolberegning udført uden denne regneparameter!"
                    ),
                    bold=True,
                    bg="yellow",
                )
            else:
                kontrolværdi = parametre.loc[parametre["Navn"] == parameter][
                    "Værdi"
                ].to_string(index=False)

                if kontrolværdi != værdi:
                    fire.cli.print(
                        (
                            "ADVARSEL: Kontrolberegning udført med regneparameter "
                            f"{parameter}={kontrolværdi}, {parameter}={værdi} sat i "
                            "endelig beregning!"
                        ),
                        bold=True,
                        bg="yellow",
                    )
        # parametre sættes as-is, brugeren må reagere på advarslen ovenfor hvis forskel
        # i parametre er utilsigtet
        if parametre[parametre["Navn"] == parameter].empty:
            parametre.loc[len(parametre)] = [parameter, værdi]
        else:
            parametre.loc[parametre["Navn"] == parameter, "Værdi"] = værdi

    # Tilføj "-kontrol" eller "-endelig" til alle filnavne
    motor.filer = [
        str(Path(fn).with_stem(f"{Path(fn).stem}-{beregningstype}"))
        for fn in motor.filer
    ]

    fire.cli.print("Så regner vi")

    try:
        motor.valider_fastholdte()
    except ValideringFejl as fejl:
        fire.cli.print(f"FEJL: {fejl}", bg="red", fg="white")
        raise SystemExit(1)

    # Analyser net
    net_uden_ensomme, ensomme_subnet, estimerbare_punkter = motor.netanalyse()
    if ensomme_subnet:
        fire.cli.print(
            f"ADVARSEL: Manglende fastholdt punkt i mindst et subnet! Forslag til fastholdte punkter i hvert subnet:",
            bg="yellow",
            fg="black",
        )
        for i, subn in enumerate(ensomme_subnet):
            fire.cli.print(f"  Subnet {i}: {subn[0]}", fg="red")
    resultater = byg_netgeometri_og_singulære(net_uden_ensomme, ensomme_subnet)

    # Beregn nye koter for de ikke-fastholdte punkter...
    fire.cli.print(
        f"Fastholder {len(motor.fastholdte)} og beregner nye koter for {len(estimerbare_punkter)} punkter"
    )

    try:
        motor.udjævn()
    except UdjævningFejl as fejl:
        fire.cli.print(
            f"FEJL: {fejl}",
            bg="red",
            fg="white",
        )
        raise SystemExit(1)

    # Generer ny dataframe med resultaterne.
    nye_punkter_df = motor.til_dataframe()

    # Opdater arbejdssæt med udjævningsresultat
    beregning = opdater_arbejdssæt(arbejdssæt, nye_punkter_df)
    beregning = beregning.reset_index()
    resultater[næste_faneblad] = beregning

    # Plot tidsserier forlænget med de nyberegnede koter.
    if plot == True:
        kotesystem = fire.cli.firedb.hent_srid(beregning["System"][0])

        # Hvis kotesystemet er Jessen, så skal Højdetidsserierne være angivet i Højdetidsserie-fanen.
        # Samme logik som i ilæg_nye_koter
        if kotesystem.name == "TS:jessen":
            fastholdt_kote, fastholdt_punkt = udled_jessenpunkt_fra_punktoversigt(
                beregning
            )
            hts_ark = find_faneblad(
                projektnavn,
                "Højdetidsserier",
                arkdef.HØJDETIDSSERIE,
                ignore_failure=False,
            )
            plot_titel = f"Højdetidsserier for jessenpunkt {fastholdt_punkt.jessennummer or fastholdt_punkt.ident}"
        else:
            plot_titel = f"Ad hoc {kotesystem.kortnavn or kotesystem.name}-tidsserier"

        tidsserier = []
        # Gennemgå alle punkter i beregningen, find eller konstruér tidsserier til plotting, og tilføj nyberegnede koter til dem
        for index, punktdata in beregning.iterrows():
            # Spring fastholdt punkt(er) over
            if punktdata["Fasthold"] != "":
                continue

            punkt = fire.cli.firedb.hent_punkt(punktdata["Punkt"])

            ny_kote = Koordinat(
                punkt=punkt,
                srid=kotesystem,
                z=punktdata["Ny kote"],
                sz=punktdata["Ny σ"],
                t=punktdata["Hvornår"],
            )

            # Find relevante tidsserier til plotting
            if kotesystem.name == "TS:jessen":
                relevante_tidsserier = hent_relevante_tidsserier(
                    hts_ark, punkt, fastholdt_punkt, fastholdt_kote
                )
                for ts in relevante_tidsserier:
                    ts.koordinater.append(ny_kote)

                tidsserier.extend(relevante_tidsserier)
            else:
                # Hvis kotesystemet ikke er Jessen, så laver vi en ad hoc tidsserie bestående af alle
                # koordinater tilhørende kotesystemet.
                koords = [
                    k
                    for k in punkt.koordinater
                    if k.srid == kotesystem and k.fejlmeldt == False
                ]
                tidsserie = HøjdeTidsserie(
                    punkt=punkt,
                    navn=f"{punkt.ident}_ADHOC_HTS_{kotesystem.kortnavn or kotesystem.name}",
                    formål=f"",
                    koordinater=koords,
                )

                tidsserier.append(tidsserie)
                tidsserie.koordinater.append(ny_kote)

        plot_tidsserier(plot_titel, tidsserier, fremhæv_nyeste_punkt=True)

    # ...og beret om resultaterne
    skriv_punkter_geojson(projektnavn, resultater[næste_faneblad], infiks=infiks)

    skriv_observationer_geojson(
        projektnavn,
        resultater[næste_faneblad].set_index("Punkt"),
        observationer,
        infiks=infiks,
    )
    skriv_ark(projektnavn, resultater | {"Parametre": parametre})
    if fire.cli.firedb.config.getboolean("general", "niv_open_files"):
        # åbn html output hvis motoren producerer et
        if hasattr(motor, "html_out"):
            webbrowser.open_new_tab(motor.html_out)
        fire.cli.print("Færdig! - åbner regneark og resultatrapport for check.")
        fire.cli.åbn_fil(f"{projektnavn}.xlsx")


def opdater_arbejdssæt(arbejdssæt: DataFrame, nye_koter: DataFrame):
    """
    Opdater arbejdssæt med resultater fra en udjævning.

    Overskriver kun visse kolonner med udjævningsresultaterne. De andre kolonner i
    arbejdssættet beholdes.
    """
    # Sæt Punkt til index, og tilføj nyberegnede punkter til indexet.
    # NB: Dette er kun i tilfælde af at der er beregnede punkter, som ikke oprindeligt
    # var i arbejdssættet.
    arbejdssæt = arbejdssæt.set_index("Punkt")
    arbejdssæt = arbejdssæt.reindex(nye_koter.index.union(arbejdssæt.index))

    # "=" operatoren joiner de to dataframes på index'et og opdaterer arbejdsættet hvor der er match
    arbejdssæt["Hvornår"] = nye_koter["Hvornår"]
    arbejdssæt["Ny kote"] = nye_koter["Ny kote"]
    arbejdssæt["Ny σ"] = nye_koter["Ny σ"]
    arbejdssæt["Δ-kote [mm]"] = nye_koter["Δ-kote [mm]"]
    arbejdssæt["Opløft [mm/år]"] = nye_koter["Opløft [mm/år]"]

    return arbejdssæt
