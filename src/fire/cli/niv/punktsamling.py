import getpass

import click
import pandas as pd
from sqlalchemy.exc import (
    NoResultFound,
)

from fire import uuid
from fire.api.model import (
    Punkt,
    PunktSamling,
    Koordinat,
    Tidsserie,
    HøjdeTidsserie,
    Srid,
)
import fire.cli
from fire.cli.niv import (
    bekræft,
    find_faneblad,
    find_sag,
    find_sagsgang,
    niv,
    skriv_ark,
    er_projekt_okay,
    udled_jessenpunkt_fra_punktoversigt,
    afbryd_hvis_ugyldigt_jessenpunkt,
)
from fire.cli.exceptions import (
    AfbrydFejl,
    IntetAtGøre,
    advarsel,
    YndefuldeFejl,
)
import fire.io.dataframe as frame
from fire.io.regneark import arkdef
from fire.io.formattering import forkort


@niv.command()
@fire.cli.default_options()
@click.argument(
    "projektnavn",
    nargs=1,
    type=str,
)
@click.option(
    "--sagsbehandler",
    default=getpass.getuser(),
    type=str,
    help="Angiv andet brugernavn end den aktuelt indloggede",
)
@click.option(
    "--punktsamlingsid",
    type=str,
    help="Angiv punktsamlingens objektid",
)
@click.option(
    "--ident",
    type=str,
    help="Angiv punktet ident",
)
def fjern_punkt_fra_punktsamling(
    projektnavn: str,
    sagsbehandler: str,
    punktsamlingsid: str,
    ident: list,
    **kwargs,
) -> None:
    """Fjern et punkt fra en punktsamling

    Bemærk at denne handling, i modsætning til langt de fleste andre FIRE-handlinger,
    ikke er historik-styret. Dvs. at man ikke umiddelbart kan bringe Punktsamlingen
    tilbage til tilstanden før denne kommando blev kørt. Brug den derfor varsomt!

    I tilfælde af at man utilsigtet har fjernet et punkt kan det dog tilføjes igen ved at
    kalde ``fire niv udtræk-punktsamling``, tilføje punktet i sags-regnearket, og lægge
    punktet i databasen med ``fire niv ilæg-punktsamling``. Databasen giver ingen hjælp
    til at huske hvilket punkt man har fjernet så det skal man selv kunne huske.

    For at kunne fjerne et punkt fra punktsamlingen, forudsættes det at punktet ikke har
    nogle tidsserier tilknyttet. Tidsserier kan lukkes med ``fire luk tidsserie``.
    Man kan desuden ikke fjerne punktsamlingens jessenpunkt.

    Punktet angives med ``ident`` og punktsamlingen angives med ``punktsamlingsid``
    hvilket svarer til punktsamlinges objektid. Denne skal findes med opslag i databasen,
    fx. ved udtræk som følgende:

    \b

    .. code-block:: console

        SELECT ps.*
        FROM PUNKTSAMLING ps
        JOIN PUNKTINFO pi ON
            ps.JESSENPUNKTID = pi.PUNKTID AND pi.INFOTYPEID = 346 -- joiner landsnumre på
        JOIN PUNKTSAMLING_PUNKT psp ON
            ps.OBJEKTID = psp.PUNKTSAMLINGSID
        JOIN PUNKTINFO pi2 ON
            psp.PUNKTID = pi2.PUNKTID AND pi2.INFOTYPEID = 346 -- joiner landsnumre på
        WHERE pi.TEKST = '123-07-09059' -- jessenpunktet til punktsamlingen
                AND pi2.TEKST = '123-07-09034' -- punktet som skal fjernes

    """
    db = fire.cli.firedb

    er_projekt_okay(projektnavn)
    sag = find_sag(projektnavn)
    sagsgang = find_sagsgang(projektnavn)

    fire.cli.print(f"Sags/projekt-navn: {projektnavn}  ({sag.id})")
    fire.cli.print(f"Sagsbehandler:     {sagsbehandler}")

    punkt = db.hent_punkt(ident)

    with YndefuldeFejl(
        NoResultFound,
        f"Punktsamling med objektid {punktsamlingsid} ikke fundet!",
    ):
        punktsamling = (
            db.session.query(PunktSamling)
            .filter(
                PunktSamling.objektid == punktsamlingsid,
                PunktSamling._registreringtil == None,
            )  # NOQA
            .one()
        )

    if punktsamling.jessenpunkt == punkt:
        raise AfbrydFejl(f"Må ikke fjerne punktsamlingens jessenpunkt!")

    # Tidsserier som skal lukkes først!
    tidsserier = [
        ts.navn
        for ts in punktsamling.tidsserier
        if ts.punkt == punkt and ts.registreringtil is None
    ]

    if tidsserier:
        raise AfbrydFejl(
            f"Må ikke fjerne et punkt fra en punktsamling hvor der ligger aktive tidsserier ({tidsserier})!",
            f"Anvend 'fire luk tidsserie' for at lukke tidsserierne først.",
        )

    punktsamling.fjern_punkter([punkt])

    sagsevent = sag.ny_sagsevent(
        punktsamlinger=[punktsamling],
        beskrivelse=f"fire niv fjern-punkt-fra-punktsamling: Fjernet punkt {ident} fra punktsamling {punktsamling.navn}",
    )
    fire.cli.firedb.indset_sagsevent(sagsevent, commit=False)

    fejltekst = f"Punkt {punkt.ident} IKKE slettet fra '{punktsamling.navn}'"
    with YndefuldeFejl(Exception, fejltekst, med_årsag=True):
        # Indsæt alle objekter i denne session
        fire.cli.firedb.session.flush()

    # Generer dokumentation til fanebladet "Sagsgang"
    sagsgangslinje = {
        "Dato": sagsevent.registreringfra,
        "Hvem": sagsbehandler,
        "Hændelse": "Punktsamling modificeret",
        "Tekst": sagsevent.sagseventinfos[0].beskrivelse,
        "uuid": sagsevent.id,
    }
    sagsgang = frame.append(sagsgang, sagsgangslinje)

    fjern_tekst = f"- fjerne punktet {ident} fra punktsamlingen {punktsamling.navn}?"
    fire.cli.print("")
    fire.cli.print("-" * 50)
    fire.cli.print("Punktsamling færdigbehandlet, klar til at")
    fire.cli.print(fjern_tekst)

    spørgsmål = click.style(
        f"Er du sikker på du vil indsætte ovenstående i ", fg="white", bg="red"
    )
    spørgsmål += click.style(f"{fire.cli.firedb.db}", fg="white", bg="red", bold=True)
    spørgsmål += click.style("-databasen?", fg="white", bg="red")

    if bekræft(spørgsmål):
        # Bordet fanger!
        fire.cli.firedb.session.commit()
        # Skriver opdateret sagsgang til excel-ark
        resultater = {"Sagsgang": sagsgang}
        if skriv_ark(projektnavn, resultater):
            fire.cli.print(f"Punktsamlinger registreret.")
    else:
        fire.cli.firedb.session.rollback()

    return


@niv.command()
@fire.cli.default_options()
@click.argument(
    "projektnavn",
    nargs=1,
    type=str,
)
@click.option(
    "--jessenpunkt",
    "jessenpunkt_ident",
    type=str,
    help="Angiv Jessenpunktet for punktsamlingen",
)
@click.option(
    "--punktsamlingsnavn",
    default="",
    type=str,
    help="Angiv punktsamlingens navn",
)
@click.option(
    "--punkter",
    default="",
    type=str,
    help="Angiv kommasepareret liste over punkter som skal indgå i punktsamlingen",
)
@click.option(
    "--punktoversigt",
    "anvend_punktoversigt",
    default=False,
    type=bool,
    is_flag=True,
    help="Angiver om punktoversigten skal anvendes til at indlæse punkter i punktsamlingen",
)
def opret_punktsamling(
    jessenpunkt_ident: str,
    projektnavn: str,
    punktsamlingsnavn: str,
    punkter: str,
    anvend_punktoversigt: bool,
    **kwargs,
) -> None:
    """
    Opretter et Punktsamlings-ark på sagen, som efterfølgende kan redigeres.

    Det primære formål med denne funktion er at oprette en ny punktsamling og tilhørende
    tidsserier. Oplysningerne kan efterfølgen redigeres, og man kan tilføje punkter og
    tidsserier til punktsamlingen. Bemærk, at "Formål"-kolonnerne ikke må være tomme.

    Resultatet skrives til et eksisterende projekt-regneark i fanerne "Punktgruppe" og
    "Højdetidsserier". Fanerne overskrives ikke, så man kan køre denne funktion flere
    gange, for at oprette flere punktsamlinger samtidig i samme regneark.

    Programmet skal vide hvilket Jessenpunkt det skal bruge. Dette angives lettest med
    ``--jessenpunkt``, som skal være jessenpunktets IDENT. Fx::

        fire niv opret-punktsamling SAG --jessenpunkt 81022

    Alternativt kan man med flaget ``--punktoversigt`` bede programmet om at bruge
    "Punktoversigt"-fanens fastholdte punkt til at udlede jessenpunktet. Hertil kræves
    det, at "Punktoversigt"-fanen er til stede i sags-regnearket, samt at der kun er
    netop ét fastholdt punkt. Eks::

        fire niv opret-punktsamling SAG --punktoversigt

    Det er nødvendigt at anvende enten ``--jessenpunkt`` eller ``--punktoversigt``. Angives
    begge, bliver ``--jessenpunkt`` brugt.

    Punktsamlingens navn angives med ``--punktsamlingsnavn``. Udelades denne, anvendes
    default-navnet "PUNKTSAMLING_[JESSENNR]".

    Nye punktsamlinger oprettes altid med Jessenkoten 0, og dette bliver således
    også referencekoten for nye tidsserier som kobles til punktsamlingen.

    Jessenpunktet indsættes altid i arket som medlem af punktsamlingen. Derudover kan man, for at
    lette opgaven med at tilføje flere punkter og tidsserier til arket, angive en kommasepareret
    liste af punkter med ``--punkter`` som programmet automatisk indsætter i arket.
    Punkterne indsættes da med default tidsserienavne og formål. Eks::

        fire niv opret-punktsamling SAG --jessenpunkt 81022 --punkter "SKEJ,RDIO,RDO1"

    Alternativt kan man igen anvende ``--punktoversigt``, som fortæller programmet at det
    skal udvide listen af punkter valgt med ``--punkter``, med punkterne i
    "Punktoversigt"-fanen. Eks::

        fire niv opret-punktsamling SAG --jessenpunkt 81022 --punkter "SKEJ,RDIO,RDO1" --punktoversigt

    Efter endt redigering kan oplysningerne ilægges databasen med ``ilæg-punktsamling`` og
    ``ilæg-tidsserie``.
    """
    er_projekt_okay(projektnavn)

    # fjern whitespace og split streng op i liste
    if punkter == "":
        punkter = []
    else:
        punkter = "".join(punkter.split()).split(",")

    punktsamling_ark = find_faneblad(
        projektnavn, "Punktgruppe", arkdef.PUNKTGRUPPE, ignore_failure=True
    )
    højdetidsserie_ark = find_faneblad(
        projektnavn, "Højdetidsserier", arkdef.HØJDETIDSSERIE, ignore_failure=True
    )

    resultater = {}

    # Hent Punktoversigten, hvis den er tilvalgt
    if anvend_punktoversigt:
        punktoversigt = find_faneblad(
            projektnavn, "Punktoversigt", arkdef.PUNKTOVERSIGT
        )
    else:
        punktoversigt = None

    # Find Jessenpunkt.
    #   Gøres enten fra angivet ident, eller udledes fra Punktoversigten
    if jessenpunkt_ident:
        # Prioritér punkter som matcher på Jessennummer da dette er mest intuitivt.
        jessenpunkt = fire.cli.firedb.hent_punkt(jessenpunkt_ident)
    elif punktoversigt is not None:
        # Find jessenpunktet ud fra oplysningerne i Punktoversigt-arket
        jessenpunkt_kote, jessenpunkt = udled_jessenpunkt_fra_punktoversigt(
            punktoversigt
        )
    else:
        # Hverken Punktoversigt eller jessenpunktets ident er givet.
        raise IntetAtGøre(
            "Intet Jessenpunkt angivet, og kan ikke udlede Jessenpunkt fra Punktoversigten, da den er fravalgt."
        )

    afbryd_hvis_ugyldigt_jessenpunkt(jessenpunkt)

    # Find Punkter.
    if punktoversigt is not None:
        # Udvid brugerspecificeret liste af punkter med punkter fra Punktoversigten.
        punkter.extend(list(punktoversigt["Punkt"]))

    # Hent punkter fra FIRE
    punkter = fire.cli.firedb.hent_punkt_liste(punkter, ignorer_ukendte=False)

    # Opret en ny Punktsamling
    ps = opret_ny_punktsamling(jessenpunkt, punkter, punktsamlingsnavn)
    ps_data, hts_data = generer_arkdata(ps)

    # Opret ark som skal gemmes.
    punktsamling_ark = frame.append(
        punktsamling_ark,
        pd.DataFrame.from_records(data=ps_data, columns=arkdef.PUNKTGRUPPE),
    )

    højdetidsserie_ark = frame.append(
        højdetidsserie_ark,
        pd.DataFrame.from_records(data=hts_data, columns=arkdef.HØJDETIDSSERIE),
    )
    # Sorter højdetidsserie-arket
    højdetidsserie_ark = højdetidsserie_ark.sort_values(
        by=["Punktgruppenavn", "Er Jessenpunkt", "Tidsserienavn", "Punkt"],
        ascending=[True, False, False, True],
    )

    resultater.update(
        {"Punktgruppe": punktsamling_ark, "Højdetidsserier": højdetidsserie_ark}
    )

    if skriv_ark(projektnavn, resultater):
        fire.cli.print(
            f"Punktsamlinger oprettet. Rediger nu Navne og Formål og tilføj Punkter og Tidsserier"
        )
        fire.cli.åbn_fil(f"{projektnavn}.xlsx")

    return


@niv.command()
@fire.cli.default_options()
@click.argument(
    "projektnavn",
    nargs=1,
    type=str,
)
@click.option(
    "--jessenpunkt",
    "jessenpunkt_ident",
    type=str,
    help="Angiv Jessenpunktet for punktsamlingen",
)
@click.option(
    "--punktsamlingsnavn",
    default="",
    type=str,
    help="Angiv punktsamlingens navn",
)
@click.option(
    "--punkter",
    default="",
    type=str,
    help="Angiv kommasepareret liste over punkter som skal tilføjes til punktsamlingen",
)
@click.option(
    "--punktoversigt",
    "anvend_punktoversigt",
    default=False,
    type=bool,
    is_flag=True,
    help="Angiver om punktoversigten skal anvendes til at indlæse punkter i punktsamlingen",
)
def udtræk_punktsamling(
    jessenpunkt_ident: str,
    projektnavn: str,
    punktsamlingsnavn: str,
    punkter: str,
    anvend_punktoversigt: bool,
    **kwargs,
) -> None:
    """
    Udtræk en eller flere punktsamlinger fra databasen

    Det primære formål med denne funktion er at udtrække oplysninger om en eksisterende
    punktsamling og de tilhørende tidsserier. Oplysningerne kan redigeres, og man kan
    tilføje punkter og tidsserier til punktsamlingen.

    Resultatet skrives til et eksisterende projekt-regneark i fanerne "Punktgruppe" og
    "Højdetidsserier". Fanerne overskrives ikke, så man kan køre denne funktion flere
    gange, for at udtrække og redigere flere punktsamlinger samtidig i samme regneark.

    Oplysningerne udtrækkes ved at angive enten navnet på punktsamlingen::

        fire niv udtræk-punktsamling SAG --punktsamlingsnavn PUNKTSAMLING_81066

    eller punktsamlingens jessenpunkt::

        fire niv udtræk-punktsamling SAG --jessenpunkt 81066

    Hvis der findes flere punktsamlinger med samme jessenpunkt, trækkes alle
    punktsamlingerne ud. Det er nødvendigt at angive enten ``--punktsamlingsnavn`` eller
    ``--jessenpunkt``. Angives begge, ignoreres ``--jessenpunkt``.

    For at lette opgaven med at tilføje punkter og tidsserier til punktsamlingen, kan man
    angive en kommasepareret liste af punkter med ``--punkter`` som programmet automatisk
    indsætter i arket. Punkterne indsættes da med default tidsserienavne og formål. Eks::

        fire niv udtræk-punktsamling SAG --punktsamlingsnavn PUNKTSAMLING_81066 --punkter "SKEJ,RDIO,RDO1"

    Derudover kan man anvende ``--punktoversigt``, der ligesom ``--punkter`` fortæller
    programmet at det skal udvide listen af punkter med punkterne i "Punktoversigt"-fanen.
    Eks::

        fire niv udtræk-punktsamling SAG --punktsamlingsnavn PUNKTSAMLING_81066 --punktoversigt

    I tilfælde af at man har trukket flere punktsamlinger ud på én gang, bliver punkterne
    tilføjet til alle punktsamlingerne.

    Efter endt redigering kan ændringerne ilægges databasen med ``ilæg-punktsamling`` og
    ``ilæg-tidsserie``.
    """
    er_projekt_okay(projektnavn)

    # fjern whitespace og split streng op i liste
    if punkter == "":
        punkter = []
    else:
        punkter = "".join(punkter.split()).split(",")

    punktsamling_ark = find_faneblad(
        projektnavn, "Punktgruppe", arkdef.PUNKTGRUPPE, ignore_failure=True
    )
    højdetidsserie_ark = find_faneblad(
        projektnavn, "Højdetidsserier", arkdef.HØJDETIDSSERIE, ignore_failure=True
    )

    resultater = {}

    # Find Punktsamling(en/erne)
    if punktsamlingsnavn:
        # Find den valgte punktsamling. Hvis brugeren har valgt et jessenpunkt, ignoreres det
        with YndefuldeFejl(
            NoResultFound, f"Punktsamling {punktsamlingsnavn} ikke fundet!"
        ):
            punktsamlinger = [fire.cli.firedb.hent_punktsamling(punktsamlingsnavn)]

    elif jessenpunkt_ident:
        # Udtræk alle punktsamlinger som har det valgte Jessenpunkt
        with YndefuldeFejl(
            NoResultFound, f"Jessenpunkt {jessenpunkt_ident} ikke fundet!"
        ):
            jessenpunkt = fire.cli.firedb.hent_punkt(jessenpunkt_ident)

        afbryd_hvis_ugyldigt_jessenpunkt(jessenpunkt)
        punktsamlinger = [
            ps for ps in jessenpunkt.punktsamlinger if ps.jessenpunkt == jessenpunkt
        ]
    else:
        raise IntetAtGøre(
            f"Hverken Jessenpunkt eller Punktsamling angivet. Afbryder..."
        )

    # Hent Punktoversigten, hvis den er tilvalgt, og udvid punktlisten.
    if anvend_punktoversigt:
        punktoversigt = find_faneblad(
            projektnavn, "Punktoversigt", arkdef.PUNKTOVERSIGT
        )

        # Udvid brugerspecificeret liste af punkter med punkter fra Punktoversigten.
        punkter.extend(list(punktoversigt["Punkt"]))

    punkter = fire.cli.firedb.hent_punkt_liste(punkter, ignorer_ukendte=False)

    # Generer data som skal skrives til excel-ark
    ps_data, hts_data = [], []
    for ps in punktsamlinger:
        # Tilføj punkter til punktsamlingerne, hvis angivet af brugeren og hvis punktet ikke allerede er en del af punktsamlingen
        tidsserier = [
            opret_ny_tidsserie(punkt, ps)
            for punkt in punkter
            if punkt not in ps.punkter
        ]

        psd, htsd = generer_arkdata(ps)
        ps_data.extend(psd)
        hts_data.extend(htsd)

    # Opret ark som skal gemmes.
    punktsamling_ark = frame.append(
        punktsamling_ark,
        pd.DataFrame.from_records(data=ps_data, columns=arkdef.PUNKTGRUPPE),
    )

    højdetidsserie_ark = frame.append(
        højdetidsserie_ark,
        pd.DataFrame.from_records(data=hts_data, columns=arkdef.HØJDETIDSSERIE),
    )
    # Sorter højdetidsserie-arket
    højdetidsserie_ark = højdetidsserie_ark.sort_values(
        by=["Punktgruppenavn", "Er Jessenpunkt", "Tidsserienavn", "Punkt"],
        ascending=[True, False, False, True],
    )

    resultater.update(
        {"Punktgruppe": punktsamling_ark, "Højdetidsserier": højdetidsserie_ark}
    )

    if skriv_ark(projektnavn, resultater):
        fire.cli.print(
            f"Punktsamlinger udtrukket. Rediger nu Formål og tilføj Tidsserier, "
            f"eller kontrollér at oplysningerne er korrekte."
        )
        fire.cli.åbn_fil(f"{projektnavn}.xlsx")

    return


@niv.command()
@fire.cli.default_options()
@click.argument(
    "projektnavn",
    nargs=1,
    type=str,
)
@click.option(
    "--sagsbehandler",
    default=getpass.getuser(),
    type=str,
    help="Angiv andet brugernavn end den aktuelt indloggede",
)
def ilæg_punktsamling(
    projektnavn: str,
    sagsbehandler: str,
    **kwargs,
) -> None:
    """
    Registrer nye eller redigerede punktsamlinger i databasen.

    Ændringer til sagsregnearkets Punktsamlinger, oprettet med ``fire niv
    opret-punktsamling`` eller udtrukket med ``fire niv udtræk-punktsamling``, lægges i
    databasen med dette program.

    Under fanen "Punktgruppe" gennemgår programmet alle punktsamlingerne som
    optræder i kolonnen "Punktgruppenavn" og gør følgende:

        - Hvis der ikke findes en punktsamling med pågældende navn, oprettes en ny
          punktsamling i databasen med alle de oplysninger som er givet i rækken

        - Hvis punktsamlingen findes i forvejen, bliver databasen synkroniseret med
          kolonnen "Formål"

        - Finder alle rækker under fanen "Højdetidsserier", som matcher på kolonnen
          "Punktgruppenavn"

        - Tilføjer alle de tilsvarende punkter i kolonnen "Punkt", som ikke allerede er
          medlem af punktsamlingen

    For hver af de oprettede eller redigerede punktsamlinger ("A") tjekker programmet inden ilægning, om "A" vil
    komme til at ligne en anden punktsamling ("B"). Brugeren advares om følgende:

        1. Er A lig med B
        2. Er A en delmængde af B (Er A et "subset" af B)
        3. Er B en delmængde af A (Er A et "superset" af B)

    Brugeren har derefter mulighed for at fortsætte eller afbryde ilægningen af den
    enkelte punktsamling. Dette fungerer som et sanity-check, så man ikke utilsigtet får
    oprettet en samling af punkter som allerede eksisterer i databasen under et andet
    navn.

    Bemærk at dette program ignorerer "Højdetidsserier"-fanens kolonner "Er Jessenpunkt",
    "Tidsserienavn", "Formål" og "System". Indholdet af disse kolonner ilægges databasen
    med ``fire niv ilæg-tidsserier``.

    Bemærk desuden at dette program ikke kan fjerne punkter fra en punktsamling. Til dette
    bruges ``fire niv fjern-punkt-fra-punktsamling``.
    """
    er_projekt_okay(projektnavn)
    sag = find_sag(projektnavn)
    sagsgang = find_sagsgang(projektnavn)

    fire.cli.print(f"Sags/projekt-navn: {projektnavn}  ({sag.id})")
    fire.cli.print(f"Sagsbehandler:     {sagsbehandler}")

    # Læs arkene
    punktgruppe_ark = find_faneblad(projektnavn, "Punktgruppe", arkdef.PUNKTGRUPPE)
    hts_ark = find_faneblad(projektnavn, "Højdetidsserier", arkdef.HØJDETIDSSERIE)

    # hent kotesystem. Lige nu understøttes kun jessen-system.
    # Mest pga. kolonnenavne i database (jessenkoordinat/kote).
    # Kunne ellers godt have punktsamlinger i andre kotesystemer
    kotesystem = fire.cli.firedb.hent_srid("TS:jessen")

    # Initialisér variable som bruges til logning
    koord_til_oprettelse = []
    pktsamling_til_redigering = []
    pktsamling_til_oprettelse = []
    antal_punkter_i_pktsamling_til_oprettelse = 0
    antal_punkter_i_pktsamling_til_redigering = 0

    for index, punktgruppedata in punktgruppe_ark.iterrows():

        # ================= 1. INDLEDENDE HENTNING AF DATA FRA ARK OG DATABASE =================

        punktgruppenavn = punktgruppedata["Punktgruppenavn"]
        angivet_jessenkote = punktgruppedata["Jessenkote"]
        formål = punktgruppedata["Formål"].strip()

        fire.cli.print(f"Behandler punktgruppe {punktgruppenavn}")

        if pd.isna(formål) or formål == "":
            raise AfbrydFejl(f"Formål for punktsamling {punktgruppenavn} ikke angivet!")

        jessenpunkt = fire.cli.firedb.hent_punkt(punktgruppedata["Jessenpunkt"])
        afbryd_hvis_ugyldigt_jessenpunkt(jessenpunkt)

        # Opdater arkets Jessennummer, i tilfælde af at brugeren har ændret jessenpunktet
        punktgruppe_ark.loc[index, "Jessennummer"] = jessenpunkt.jessennummer

        punktliste = list(
            hts_ark["Punkt"][hts_ark["Punktgruppenavn"] == punktgruppenavn]
        )
        punkter_i_punktgruppe = fire.cli.firedb.hent_punkt_liste(punktliste)

        # ================= 2A. REDIGER EKSISTERENDE PUNKTGRUPPE =================

        try:
            eksisterende_punktsamling = find_punktsamling(jessenpunkt, punktgruppenavn)
        except NoResultFound:
            # Gør ikke noget. Gå videre til 2B for at oprette ny
            pass
        else:
            # Læs punkter og opdater listen.
            punkter_i_eksisterende_punktsamling = set(eksisterende_punktsamling.punkter)

            punkter_til_tilføjelse = (
                set(punkter_i_punktgruppe) - punkter_i_eksisterende_punktsamling
            )

            # Opdaterer eksisterende punktsamling med nyt formål og nye punkter
            if (
                eksisterende_punktsamling.formål != formål
                or len(punkter_til_tilføjelse) > 0
            ):
                pktsamling_til_redigering.append(eksisterende_punktsamling)

            eksisterende_punktsamling.formål = formål
            antal_punkter_i_pktsamling_til_redigering += len(punkter_til_tilføjelse)
            eksisterende_punktsamling.tilføj_punkter(punkter_til_tilføjelse)

            continue

        # ================= 2B. OPRET NY PUNKTGRUPPE =================
        ny_punktsamling = PunktSamling(
            navn=punktgruppenavn,
            jessenpunkt=jessenpunkt,
            # jessenkoordinat = [], # Nyoprettede punktsamlinger har ikke nogen jessekote, hvilket skal tolkes som 0!
            # tidsserier = [], # Tidsserier oprettes med ilæg-tidsserier
            formål=formål,
            punkter=punkter_i_punktgruppe,
        )

        # Opret ny jessenkote
        # TODO: Der er mulighed for at oprette ny jessenkote automatisk, men for nu er det udkommenteret.
        # TODO: Dvs. at alle punktsamlinger oprettes med "0" som jessenkote.
        # ny_punktsamling.jessenkoordinat = find_eller_opret_jessenkote(jessenpunkt, angivet_jessenkote, kotesystem)
        # if fire.cli.firedb._is_new_object(ny_punktsamling.jessenkoordinat):
        # hvis jessenkoordinaten er nyoprettet gemmer vi den så vi kan give brugeren besked senere
        # koord_til_oprettelse.append(ny_punktsamling.jessenkoordinat)

        pktsamling_til_oprettelse.append(ny_punktsamling)
        antal_punkter_i_pktsamling_til_oprettelse += len(punkter_i_punktgruppe)

    # Tjek om punktsamlingerne er unikke:
    pktsamlinger_til_ilæggelse = pktsamling_til_oprettelse + pktsamling_til_redigering
    for pktsamling in pktsamlinger_til_ilæggelse:

        # Sammenlign med de andre punktsamlinger som er på vej til at blive lagt i db
        ligmed, subset, superset = er_punktsamling_unik(
            pktsamling, pktsamlinger_til_ilæggelse
        )

        # Sammenlign med alle andre punktsamlinger
        ligmed_alle, subset_alle, superset_alle = er_punktsamling_unik(pktsamling)

        ligmed.update(ligmed_alle)
        subset.update(subset_alle)
        superset.update(superset_alle)

        if ligmed:
            ligmed = ", ".join(ligmed)
            advarsel(f"{pktsamling.navn} indeholder de samme punkter som: {ligmed}")

        if superset:
            superset = ", ".join(superset)
            advarsel(f"Punkterne i {pktsamling.navn} er et superset af: {superset}")

        if subset:
            subset = ", ".join(subset)
            advarsel(f"Punkterne i {pktsamling.navn} er en delmængde af: {subset}")

        if not (ligmed or superset or subset):
            continue

        spørgsmål = click.style(
            f"Er du sikker på at du vil ilægge {pktsamling.navn}?", fg="white", bg="red"
        )

        if not bekræft(spørgsmål, gentag=False):
            # Hvis brugeren siger Nej, så fjerner vi punktsamlingen fra de tidligere oprettede lister
            for liste in (
                pktsamling_til_oprettelse,
                pktsamling_til_redigering,
                pktsamlinger_til_ilæggelse,
            ):
                try:
                    liste.remove(pktsamling)
                except ValueError:
                    pass

    if not (
        koord_til_oprettelse or pktsamling_til_redigering or pktsamling_til_oprettelse
    ):
        raise IntetAtGøre(f"Ingen punktsamlinger at oprette eller redigere. Afbryder!")

    # ================= 3A. SAGSEVENT REDIGER PUNKTSAMLING =================

    if pktsamling_til_redigering:
        psnavne = "'" + "', '".join([ps.navn for ps in pktsamling_til_redigering]) + "'"
        sagsevent_rediger_punktsamlinger = sag.ny_sagsevent(
            id=uuid(),
            beskrivelse=f"Redigering af punktsamlingerne {psnavne}",
            punktsamlinger=pktsamling_til_redigering,
        )
        fire.cli.firedb.indset_sagsevent(sagsevent_rediger_punktsamlinger, commit=False)
        with YndefuldeFejl(Exception, med_årsag=True):
            fire.cli.firedb.session.flush()

        # Generer dokumentation til fanebladet "Sagsgang"
        sagsgangslinje = {
            "Dato": sagsevent_rediger_punktsamlinger.registreringfra,
            "Hvem": sagsbehandler,
            "Hændelse": "Punktsamling modificeret",
            "Tekst": sagsevent_rediger_punktsamlinger.sagseventinfos[0].beskrivelse,
            "uuid": sagsevent_rediger_punktsamlinger.id,
        }
        sagsgang = frame.append(sagsgang, sagsgangslinje)

    # ================= 3B. SAGSEVENT OPRET PUNKTSAMLING =================
    # === DEL 3B.1: Opret Jessenkoordinat som ikke findes i forvejen ===
    if koord_til_oprettelse:

        jessenpunkter = (
            "'" + "', '".join([k.punkt.ident for k in koord_til_oprettelse]) + "'"
        )
        sagsevent_nye_jessenkoter = sag.ny_sagsevent(
            id=uuid(),
            beskrivelse=f"Indsættelse af ny {kotesystem.kortnavn or kotesystem.name}-kote for punkterne {jessenpunkter}",
            koordinater=koord_til_oprettelse,
        )
        fire.cli.firedb.indset_sagsevent(sagsevent_nye_jessenkoter, commit=False)
        with YndefuldeFejl(Exception, med_årsag=True):
            fire.cli.firedb.session.flush()

        # Generer dokumentation til fanebladet "Sagsgang"
        sagsgangslinje = {
            "Dato": sagsevent_nye_jessenkoter.registreringfra,
            "Hvem": sagsbehandler,
            "Hændelse": "Jessenkote(r) indsat",
            "Tekst": sagsevent_nye_jessenkoter.sagseventinfos[0].beskrivelse,
            "uuid": sagsevent_nye_jessenkoter.id,
        }
        sagsgang = frame.append(sagsgang, sagsgangslinje)

    if pktsamling_til_oprettelse:
        # === DEL 3B.2: Opret Punktsamlingen ===
        psnavne = "'" + "', '".join([ps.navn for ps in pktsamling_til_oprettelse]) + "'"
        sagsevent_opret_punktsamlinger = sag.ny_sagsevent(
            id=uuid(),
            beskrivelse=f"Oprettelse af punktsamlingerne {psnavne}",
            punktsamlinger=pktsamling_til_oprettelse,
        )
        fire.cli.firedb.indset_sagsevent(sagsevent_opret_punktsamlinger, commit=False)
        with YndefuldeFejl(Exception, med_årsag=True):
            fire.cli.firedb.session.flush()

        # Generer dokumentation til fanebladet "Sagsgang"
        sagsgangslinje = {
            "Dato": sagsevent_opret_punktsamlinger.registreringfra,
            "Hvem": sagsbehandler,
            "Hændelse": "Punktsamling(er) oprettet",
            "Tekst": sagsevent_opret_punktsamlinger.sagseventinfos[0].beskrivelse,
            "uuid": sagsevent_opret_punktsamlinger.id,
        }
        sagsgang = frame.append(sagsgang, sagsgangslinje)

    indsæt_kote_tekst = (
        f"- indsætte {len(koord_til_oprettelse)} {kotesystem.name}-kote(r)"
    )
    opret_tekst = f"- oprette {len(pktsamling_til_oprettelse)} nye punktsamlinger med i alt {antal_punkter_i_pktsamling_til_oprettelse} punkter"
    tilføj_tekst = f"- tilføje {antal_punkter_i_pktsamling_til_redigering} punkter fordelt på {len(pktsamling_til_redigering)} eksisterende punktsamlinger"
    # ret_tekst = f"- rette {len(nye_lokationer)} formålsbeskrivelse"

    fire.cli.print("")
    fire.cli.print("-" * 50)
    fire.cli.print("Punktsamlinger færdigbehandlet, klar til at")
    fire.cli.print(indsæt_kote_tekst)
    fire.cli.print(opret_tekst)
    fire.cli.print(tilføj_tekst)

    spørgsmål = click.style(
        f"Er du sikker på du vil indsætte ovenstående i ", fg="white", bg="red"
    )
    spørgsmål += click.style(f"{fire.cli.firedb.db}", fg="white", bg="red", bold=True)
    spørgsmål += click.style("-databasen?", fg="white", bg="red")

    if bekræft(spørgsmål):
        # Bordet fanger!
        fire.cli.firedb.session.commit()

        # Skriver opdateret sagsgang til excel-ark
        resultater = {
            "Sagsgang": sagsgang,
            "Punktgruppe": punktgruppe_ark,
        }
        if skriv_ark(projektnavn, resultater):
            fire.cli.print(f"Punktsamlinger registreret.")
    else:
        fire.cli.firedb.session.rollback()

    return


@niv.command()
@fire.cli.default_options()
@click.argument(
    "projektnavn",
    nargs=1,
    type=str,
)
@click.option(
    "--sagsbehandler",
    default=getpass.getuser(),
    type=str,
    help="Angiv andet brugernavn end den aktuelt indloggede",
)
def ilæg_tidsserie(
    projektnavn: str,
    sagsbehandler: str,
    **kwargs,
) -> None:
    """
    Registrer nye eller redigerede højdetidsserier i databasen.

    Ændringer til sagsregnearkets Højdetidsserier, oprettet med ``fire niv
    opret-punktsamling`` eller udtrukket med ``fire niv udtræk-punktsamling``, lægges i
    databasen med dette program.

    **Bemærk at denne funktion IKKE bruges til at tilføje tidsserie-koter til tidsserierne.**
    Se nedenfor for info om hvordan koter knyttes til en tidsserie.

    Under fanen "Højdetidsserier" gennemgår programmet alle tidsserier og gør følgende:

        - Hvis der ikke findes en tidsserie med pågældende navn, oprettes en ny
          Højdetidsserie i databasen med alle de oplysninger som er givet i rækken

        - Ellers, hvis tidsserien findes i forvejen, bliver databasen synkroniseret med
          kolonnen "Formål"

    **Bemærk at højdetidsserierne bliver oprettet uden tilknyttede koter.**

    For at føje nyberegnede koter, som ikke er ilagt databasen, til en tidsserie, kan
    ``fire niv ilæg-nye-koter`` bruges til både at ilægge de nye koter og knytte dem til
    tidsserien.
    """

    er_projekt_okay(projektnavn)
    sag = find_sag(projektnavn)
    sagsgang = find_sagsgang(projektnavn)

    fire.cli.print(f"Sags/projekt-navn: {projektnavn}  ({sag.id})")
    fire.cli.print(f"Sagsbehandler:     {sagsbehandler}")

    # Læs arkene
    # punktgruppe_ark = find_faneblad(projektnavn, "Punktgruppe", arkdef.PUNKTGRUPPE)
    hts_ark = find_faneblad(projektnavn, "Højdetidsserier", arkdef.HØJDETIDSSERIE)

    # hent kotesystem. Lige nu understøttes kun jessen-system.
    # Mest pga. kolonnenavne i database (jessenkoordinat/kote).
    # Kunne ellers godt have punktsamlinger i andre kotesystemer
    kotesystem = fire.cli.firedb.hent_srid("TS:jessen")

    ts_til_redigering = []
    ts_til_oprettelse = []
    for index, row in hts_ark.iterrows():
        tidsserienavn = row["Tidsserienavn"]
        formål = row["Formål"].strip()

        if pd.isna(formål) or formål == "":
            raise AfbrydFejl(f"Formål for tidsserie {tidsserienavn} ikke angivet!")

        try:
            ts = fire.cli.firedb.hent_tidsserie(tidsserienavn)
        except NoResultFound:
            fire.cli.print(
                f"Kunne ikke finde tidsserie: {tidsserienavn}. Opretter ny tidsserie."
            )

            # Her smides fejl hvis punkt eller punktgruppe ikke kan findes!
            punkt = fire.cli.firedb.hent_punkt(row["Punkt"])
            ps = fire.cli.firedb.hent_punktsamling(row["Punktgruppenavn"])

            ts = HøjdeTidsserie(
                navn=tidsserienavn,
                punkt=punkt,
                punktsamling=ps,
                formål=formål,
                srid=kotesystem,
            )

            # Hvis punktet er jessenpunkt, så oprettes tidsserien med punktsamlingens
            # jessenkote. Ellers er tidsserien bare tom
            # Dog oprettes nye punktsamlinger uden jessenkote, så jessenpunktets
            # tidsserie vil også være tom..
            if ps.jessenpunkt == punkt and ps.jessenkoordinat is not None:
                ts.koordinater = [ps.jessenkoordinat]

            ts_til_oprettelse.append(ts)

        else:
            # Hvis vi fandt en tidsserie så redigerer vi formålet
            if ts.formål == formål:
                continue
            ts.formål = formål
            ts_til_redigering.append(ts)

    # ================= 3A. SAGSEVENT REDIGER TIDSSERIE =================
    if ts_til_redigering:
        tsnavne = forkort([f"'{ts.navn}'" for ts in ts_til_redigering])
        sagsevent_rediger_tidsserier = sag.ny_sagsevent(
            id=uuid(),
            beskrivelse=f"Redigering af tidsserierne {', '.join(tsnavne)}",
            tidsserier=ts_til_redigering,
        )
        fire.cli.firedb.indset_sagsevent(sagsevent_rediger_tidsserier, commit=False)
        with YndefuldeFejl(Exception, med_årsag=True):
            fire.cli.firedb.session.flush(
                [
                    sagsevent_rediger_tidsserier,
                ]
            )

        # Generer dokumentation til fanebladet "Sagsgang"
        sagsgangslinje = {
            "Dato": sagsevent_rediger_tidsserier.registreringfra,
            "Hvem": sagsbehandler,
            "Hændelse": "Tidsserie modificeret",
            "Tekst": sagsevent_rediger_tidsserier.sagseventinfos[0].beskrivelse,
            "uuid": sagsevent_rediger_tidsserier.id,
        }
        sagsgang = frame.append(sagsgang, sagsgangslinje)

    # ================= 3B. SAGSEVENT OPRET TIDSSERIE =================
    if ts_til_oprettelse:
        tsnavne = forkort([f"'{ts.navn}'" for ts in ts_til_oprettelse])
        sagsevent_opret_tidsserier = sag.ny_sagsevent(
            id=uuid(),
            beskrivelse=f"Oprettelse af tidsserierne {', '.join(tsnavne)}",
            tidsserier=ts_til_oprettelse,
        )
        fire.cli.firedb.indset_sagsevent(sagsevent_opret_tidsserier, commit=False)
        with YndefuldeFejl(Exception, med_årsag=True):
            fire.cli.firedb.session.flush()

        # Generer dokumentation til fanebladet "Sagsgang"
        sagsgangslinje = {
            "Dato": sagsevent_opret_tidsserier.registreringfra,
            "Hvem": sagsbehandler,
            "Hændelse": "Tidsserie oprettet",
            "Tekst": sagsevent_opret_tidsserier.sagseventinfos[0].beskrivelse,
            "uuid": sagsevent_opret_tidsserier.id,
        }
        sagsgang = frame.append(sagsgang, sagsgangslinje)

    # indsæt_kote_tekst = f"- indsætte {len(koord_til_oprettelse)} {kotesystem.name}-kote(r)"
    opret_tekst = f"- oprette {len(ts_til_oprettelse)} nye højdetidsserier"
    ret_tekst = f"- rette formål på {len(ts_til_redigering)} højdetidsserier"

    fire.cli.print("")
    fire.cli.print("-" * 50)
    fire.cli.print("Tidsserier færdigbehandlet, klar til at")
    fire.cli.print(opret_tekst)
    fire.cli.print(ret_tekst)

    spørgsmål = click.style(
        f"Er du sikker på du vil indsætte ovenstående i ", fg="white", bg="red"
    )
    spørgsmål += click.style(f"{fire.cli.firedb.db}", fg="white", bg="red", bold=True)
    spørgsmål += click.style("-databasen?", fg="white", bg="red")

    if bekræft(spørgsmål):
        # Bordet fanger!
        fire.cli.firedb.session.commit()

        # Skriver opdateret sagsgang til excel-ark
        resultater = {"Sagsgang": sagsgang}
        if skriv_ark(projektnavn, resultater):
            fire.cli.print(f"Tidsserier registreret.")
    else:
        fire.cli.firedb.session.rollback()

    return


def find_eller_opret_jessenkote(
    jessenpunkt: Punkt, jessenkote: float, kotesystem: Srid
) -> Koordinat:
    """
    Finder et Koordinat-objekt i databasen med givet punkt, jessenkote, og kotesystem

    Hvis der findes mere end ét Koordinat så returneres det først fundne. Hvis der ikke
    eksisterer et sådant Koordinat, så oprettes og returneres et nyoprettet koordinat, som
    man sidenhen kan vælge at lægge i databasen.

    Bemærk at denne funktion er tiltænkt situationer hvor en punktsamling forsøges ilagt
    databasen med en jessenkote som ikke findes. Dog kan den også bruges til at finde
    eller oprette arbitrære Koordinater.
    """
    try:
        # Filterer med vilje ikke på RegistreringTil = None, idet jessenpunktet godt
        # kan have tidsserier i andre punktsamlinger, hvis tidsserie-koordinater også
        # har SRID'en TS:jessen.
        # RegistreringTil = None vil kun finde det nyeste koord. som altså kan ændre
        # kote.
        # Der forventes kun ét resultat, men søgningen kan i edge-cases returnere
        # flere koordinater med identisk z-værdi, hvorfor der bare tages den først
        # fundne, som også burde være den første i tid.
        jessenkoordinat = [
            k
            for k in jessenpunkt.koordinater
            if k.srid == kotesystem and k.z == jessenkote
        ][0]
    except IndexError:

        fire.cli.print(
            f"BEMÆRK: Jessenkote ikke fundet i databasen. \n"
            f"Opretter nyt Jessenkoordinat med koten {jessenkote} [m]",
            fg="black",
            bg="yellow",
        )

        jessenkoordinat = Koordinat(
            punkt=jessenpunkt,
            srid=kotesystem,
            # hvilket tidspunkt skal den nye jessenkote gælde fra?
            # default er "current_timestamp"
            # t=None,
            z=jessenkote,
            sz=0,
        )

    return jessenkoordinat


def find_punktsamling(
    jessenpunkt: Punkt,
    punktsamlingsnavn: str = "",
) -> PunktSamling:
    """Finder en punktsamling ud fra angivet navn og jessenpunkt."""

    punktsamling = fire.cli.firedb.hent_punktsamling(punktsamlingsnavn)

    # Sikr at den fundne Punktsamling også har korrekt Jessenpunkt
    if punktsamling.jessenpunkt != jessenpunkt:
        raise AfbrydFejl(
            f"Jessenpunktet '{punktsamling.jessenpunkt.ident}' for punktsamlingen '{punktsamlingsnavn}' "
            f"er ikke det samme som det angivne Jessenpunkt '{jessenpunkt.ident}'",
        )

    return punktsamling


def er_punktsamling_unik(
    punktsamling_A: PunktSamling, punktsamlinger: list[PunktSamling] = []
) -> tuple[set[str], set[str], set[str]]:
    """
    Undersøg om en Punktsamling A udgør en unik samling af punkter.

    Givet Punktsamling A (herved forstås mængden af punkter i punktsamlingen) undersøges
    der for alle andre Punktsamlinger B flg:
        1. Er A lig med B
        2. Er A en delmængde af B (Er A et "subset" af B)
        3. Er B en delmængde af A (Er A et "superset" af B)

    Returnerer for hvert af de ovenstående tilfælde, en mængde af navne på punktsamlinger
    der falder inden for de 3 kategorier.
    """
    if not isinstance(punktsamling_A, PunktSamling):
        raise AfbrydFejl("'punktsamling' er ikke en instans af PunktSamling")

    # Mængde af punkter i Punktsamling A
    punkter_A = {pkt.ident for pkt in punktsamling_A.punkter}

    if not punktsamlinger:
        punktsamlinger = fire.cli.firedb.hent_alle_punktsamlinger()

    # Initialiser lister
    ligmed, subset, superset = set(), set(), set()
    for punktsamling_B in punktsamlinger:

        # Lad være med at sammenligne Punktsamlingen med sig selv
        if punktsamling_A.navn == punktsamling_B.navn:
            continue

        # Mængde af punkter i Punktsamling B
        punkter_B = {pkt.ident for pkt in punktsamling_B.punkter}

        if punkter_A == punkter_B:
            ligmed.add(punktsamling_B.navn)
        elif punkter_A.issubset(punkter_B):
            subset.add(punktsamling_B.navn)
        elif punkter_A.issuperset(punkter_B):
            superset.add(punktsamling_B.navn)

    return ligmed, subset, superset


def opret_ny_tidsserie(
    punkt: Punkt, punktsamling: PunktSamling, tidsserienavn: str = None
) -> Tidsserie:
    """
    Opretter ny højdetidsserie

    Hvis intet tidsserienavn angives, så bruges default-navnet: [IDENT]_HTS_[JESSENNR]. Hvis der findes
    en tidsserie med samme navn i forvejen, vil funktionen fejle.
    """
    if not tidsserienavn:
        tidsserienavn = (
            f"{punkt.ident}_HTS_{punktsamling.jessenpunkt.jessennummer}"  # Default navn
        )

    try:
        tidsserie = fire.cli.firedb.hent_tidsserie(tidsserienavn)
    except NoResultFound:
        pass
    else:
        raise AfbrydFejl(f"Tidsserien '{tidsserienavn}' eksisterer allerede.")

    if punkt not in punktsamling.punkter:
        punktsamling.tilføj_punkter([punkt])

    tidsserie = HøjdeTidsserie(
        punkt=punkt,
        punktsamling=punktsamling,
        navn=tidsserienavn,
        formål=f"",
    )

    return tidsserie


def opret_ny_punktsamling(
    jessenpunkt: Punkt, punkter: list[Punkt], punktsamlingsnavn: str = None
) -> PunktSamling:
    """
    Opretter ny punktsamling og tilhørende højdetidsserier

    Hvis intet punktsamlingsnavn angives, så bruges default-navnet PUNKTSAMLING_[JESSENNR].
    Hvis der findes en punktsamling med samme navn i forvejen, vil funktionen fejle.

    Punkter som skal indgå i punktsamling angives med "punkter". Der oprettes også
    højdetidsserier for alle disse punkter. Tidsserierne oprettes med default-navne.
    """
    if not punktsamlingsnavn:
        punktsamlingsnavn = f"PUNKTSAMLING_{jessenpunkt.jessennummer}"  # Default navn

    try:
        punktsamling = fire.cli.firedb.hent_punktsamling(punktsamlingsnavn)
    except NoResultFound:
        pass
    else:
        raise AfbrydFejl(
            f"Punktsamlingen '{punktsamlingsnavn}' eksisterer allerede. ",
            f"Anvend 'fire niv udtræk-punktsamling' for at udtrække og redigere i eksisterende punktsamlinger.",
        )

    # fjern dubletter med list(set( ... ))
    punkter = list(set([jessenpunkt] + punkter))
    punktsamling = PunktSamling(
        navn=punktsamlingsnavn,
        formål="",
        jessenpunkt=jessenpunkt,
        jessenkoordinat=None,  # Nye punktsamlinger får ikke nogen jessenkote
        punkter=punkter,
    )

    # Opret tidsserier for alle de nye punkter
    tidsserier = [opret_ny_tidsserie(punkt, punktsamling) for punkt in punkter]

    return punktsamling


def generer_arkdata(punktsamling: PunktSamling) -> tuple[list, list]:
    """Genererer data ud fra en Punktsamling, til indsættelse i punktsamlings- og højdetidsseriearkene"""
    ps_data = [
        (
            punktsamling.navn,
            punktsamling.jessenpunkt.ident,
            punktsamling.jessenpunkt.jessennummer,
            punktsamling.jessenkote,
            punktsamling.formål,
        )
    ]

    # Finder først punktsamlingens tidsserier
    hts_data = [
        (
            punktsamling.navn,
            hts.punkt.ident,
            ("x" if hts.punkt == punktsamling.jessenpunkt else ""),
            hts.navn,
            hts.formål,
            "Jessen",
        )
        for hts in punktsamling.tidsserier
        if hts.registreringtil is None
    ]

    # Dernæst finder vi punktsamlingens punkter, som ikke har nogen tidsserier
    hts_data += [
        (
            punktsamling.navn,
            punkt.ident,
            ("x" if punkt == punktsamling.jessenpunkt else ""),
            "",
            "",
            "Jessen",
        )
        for punkt in punktsamling.punkter
        if punkt
        not in [
            hts.punkt for hts in punktsamling.tidsserier if hts.registreringtil is None
        ]
    ]

    return ps_data, hts_data
