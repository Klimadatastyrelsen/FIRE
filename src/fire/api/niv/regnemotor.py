from abc import ABC, abstractmethod
from dataclasses import astuple
from datetime import datetime
from functools import cached_property
from math import (
    ceil,
    hypot,
    sqrt,
    isnan,
)
import os
from pathlib import Path
import subprocess
from typing import Self
import xmltodict

import networkx as nx
import numpy as np
import pandas as pd
from rich.console import Console

from fire import uuid
from fire.api.niv.datatyper import (
    PunktNavn,
    NivNet,
    NivSubnet,
    NivKote,
    NivObservation,
)
from fire.api.niv.lukkesum import (
    LukkesumStats,
    find_polygoner,
    aggreger_multidigraf,
    lukkesum_af_polygon,
)
from fire.api.statistik import (
    WeightedLeastSquares,
    Ttest,
    visualize_matrices,
    visualize_residuals,
)
from fire.cli.pretty_tables import (
    generer_rapporttabel,
    print_tabel,
    klargør_celle,
    SIMPLE_ASCII_BOX,
)


class UdjævningFejl(Exception):
    """Der gik noget galt under udjævningen"""

    pass


class ValideringFejl(Exception):
    """Input til regnemotoren er forkert"""

    pass


class FastholdtIkkeObserveret(ValideringFejl):
    def __init__(self, uobserverede_fastholdte_punkter: list[PunktNavn] = None):
        self.uobserverede_fastholdte_punkter = uobserverede_fastholdte_punkter


class RegneMotor(ABC):
    """
    Øverste led i RegneMotor-hierarkiet til udjævning af nivellementsobservationer

    En RegneMotor fungerer som en "adapter", som gør det muligt at arbejde med forskellige
    repræsentationer af nivellementobservationer og koter på en ensartet måde.

    En RegneMotor består basalt set af et sæt af observationer til et sæt fikspunkter,samt
    ét eller flere fastholdte punkter. Disse er hver defineret som lister af dataklasserne
    ``NivObservation`` hhv. ``NivKote``. Disse klasser indeholder de basale attributter
    nødvendige for nivellementberegninger.

    **Instantiering**

    Der er defineret forskellige metoder til instantiering::

        fra_dataframe  : Start RegneMotor ud fra pandas DataFrames som anvendes i det
                         almindelige fire niv-workflow

    **Udjævning**

    Udjævning af observationer foretages med `udjævn` som forventes at være implementeret
    i alle nedarvende klasser. Udjævningsresultaterne er tilgængelige i ``self.nye_koter``
    som ``list[NivKote]``.

    **Grafanalyse**

    Observationerne i et nivellementprojekt danner et netværk af punkter (knuder) som
    forbindes af observationslinjerne (kanter). Tilsammen kaldes dette en graf. RegneMotor
    anvender derfor værktøjer kendt fra grafteori til at beregne størrelser som man
    normalt er interesseret i ifm. et nivellementprojekt.

    Der kan bl.a. undersøges, om netværket består af flere usammenhængende grafer
    (subnet), samt, for hver af disse subnet, om det indeholder mindst ét fastholdt punkt.
    Hvis ikke, vil det ikke være muligt at gennemføre udjævningen for punkterne i
    pågældende subnet.

    Almindeligvis er man ved nivellementberegninger også interesseret i at identificere
    lukkede "polygoner", bestående af observationslinjerne, også kaldet en "kreds".
    Analyseres de observerede højdeforskelle langs kanterne i en kreds er det muligt at
    beregne polygonens lukkesum for frem- og tilbagenivellement samt forskellen
    herimellem, som kaldes "summa rho".

    **Resultater**

    RegneMotor attributterne ``self.gamle_koter`` og ``self.nye_koter`` kan bruges til at
    vise udjævningsresultaterne i forskellige formater.
    ``til_dataframe`` genererer en dataframe i samme format som inputtet i
    ``fra_dataframe``

    """

    def __init__(
        self,
        observationer: list[NivObservation],
        gamle_koter: list[NivKote],
        projektnavn: str = "fire",
    ):
        # observationerne refereres internt med et unikt id som kan bruges i forskellige sammenhænge
        self._observationer = {uuid(): o for o in observationer}
        self._gamle_koter = {gk.punkt: gk for gk in gamle_koter}
        self.nye_koter: list[NivKote] = []
        self.projektnavn = projektnavn

    def valider_fastholdte(self):
        if 0 == len(self.fastholdte):
            raise ValideringFejl("Der skal fastholdes mindst et punkt i en beregning")

        if any([v for v in self.fastholdte.values() if isnan(v)]):
            raise ValideringFejl(
                "Der skal angives koter for alle fastholdte punkter i en beregning"
            )

        uobserverede_fastholdte_punkter = [
            pkt for pkt in self.fastholdte.keys() if pkt not in self.observerede_punkter
        ]
        if len(uobserverede_fastholdte_punkter) > 0:
            raise FastholdtIkkeObserveret(
                f"Observation(er) for fastholdte punkter: {', '.join(uobserverede_fastholdte_punkter)} er slukket eller mangler"
            )

    @property
    def observationer(self):
        return self._observationer.values()

    @property
    def gamle_koter(self):
        return self._gamle_koter.values()

    @classmethod
    def fra_dataframe(
        cls,
        observationer_df: pd.DataFrame,
        punkter_df: pd.DataFrame,
        **kwargs,
    ) -> Self:
        """Oversæt fra regneark til internt format"""
        observationer = []
        for i, obs in observationer_df.iterrows():
            # først beregn spredning
            spredning = _spredning(
                obs["Type"], obs["L"], obs["Opst"], obs["σ"], obs["δ"]
            )

            observationer.append(
                NivObservation(
                    fra=obs["Fra"],
                    til=obs["Til"],
                    dato=obs["Hvornår"].to_pydatetime(),
                    multiplicitet=obs["Opst"],
                    afstand=obs["L"],
                    deltaH=obs["ΔH"],
                    spredning=spredning,
                    id=obs["Journal"],
                )
            )

        gamle_koter = []
        for i, pkt in punkter_df.iterrows():
            gamle_koter.append(
                NivKote(
                    punkt=pkt["Punkt"],
                    fasthold=(True if pkt["Fasthold"] else False),
                    dato=pkt["Hvornår"].to_pydatetime(),
                    H=pkt["Kote"],
                    spredning=pkt["σ"],
                    nord=pkt["Nord"],
                    øst=pkt["Øst"],
                )
            )

        return cls(observationer=observationer, gamle_koter=gamle_koter, **kwargs)

    def til_dataframe(self) -> pd.DataFrame:
        """
        Oversætter udjævningsresultater fra det interne format til dataframe

        Den returnerede dataframe har samme kolonnenavne som "Punktoversigt"-
        arkdefinitionen. Der bruges kun den delmængde af kolonnerne som er relevante for
        nye koter.
        Dvs. at der ignoreres kolonnerne "uuid", "System" og "Udelad publikation". Disse
        kolonner skal man selv udfylde bagefter.
        """

        df_nye = pd.DataFrame(
            [astuple(x) for x in self.nye_koter],
            columns=("Punkt", "Ny kote", "Hvornår", "Ny σ", "Fasthold", "Nord", "Øst"),
        )

        df_gamle = pd.DataFrame(
            [astuple(x) for x in self.gamle_koter],
            columns=("Punkt", "Kote", "Hvornår", "σ", "Fasthold", "Nord", "Øst"),
        )
        df_nye = df_nye.set_index("Punkt")
        df_gamle = df_gamle.set_index("Punkt")

        # Beregn tid gået i antal år
        dt = (df_nye["Hvornår"] - df_gamle["Hvornår"]).apply(
            lambda t: t.total_seconds()
        ) / (365.25 * 86400)

        # Fjern rækker hvor dt = 0. Dette gør så Opløft-kolonnen længere nede bliver NaN istedet for inf.
        dt = dt[dt != 0]

        # Beregn ændring i millimeter...
        Delta = (df_nye["Ny kote"] - df_gamle["Kote"]) * 1000.0

        # ...men vi ignorerer ændringer under mikrometerniveau
        Delta[abs(Delta) < 0.001] = 0

        # Konstruer ny dataframe. Index og kolonner er foreningsmængden af de to dataframes.
        # NULL værdier i df_nye udfyldes med værdier fra df_gamle (dvs Fasthold, Kote, σ, Nord, Øst)
        df_out = df_nye.combine_first(df_gamle)

        df_out["Fasthold"] = df_out["Fasthold"].replace(False, "")
        df_out["Fasthold"] = df_out["Fasthold"].replace(True, "x")

        # Opdater felter i arbejdssættet
        df_out["Δ-kote [mm]"] = Delta
        df_out["Opløft [mm/år]"] = Delta.div(dt)

        return df_out

    @cached_property
    def fastholdte(self) -> dict[PunktNavn, float]:
        """Find fastholdte punkter og koter til en beregning"""
        return {pkt.punkt: pkt.H for pkt in self.gamle_koter if pkt.fasthold}

    @cached_property
    def gyldighedstidspunkt(self) -> datetime:
        """Tid for sidste observation der har været brugt i beregningen"""
        return max([obs.dato for obs in self.observationer])

    @cached_property
    def opstillingspunkter(self) -> set[PunktNavn]:
        """Alle opstillingspunkter"""
        return {obs.fra for obs in self.observationer}

    @cached_property
    def sigtepunkter(self) -> set[PunktNavn]:
        """Alle sigtepunkter"""
        return {obs.til for obs in self.observationer}

    @cached_property
    def observerede_punkter(self) -> set[PunktNavn]:
        """Foreningsmængden af opstillings- og sigtepunkter"""
        return self.opstillingspunkter.union(self.sigtepunkter)

    @cached_property
    def multidigraf(self) -> nx.MultiDiGraph:
        """
        Byg en digraf ud fra observationerne

        Returnerer et networkx MultiDiGraph objekt som kan indeholde flere parallelle
        (deraf Multi), rettede (deraf Di(rectional)) linjer (kanter) mellem hvert punkt
        (knude). Hver kant i grafen har en nøgle som refererer til en ``NivObservation``.
        """
        multidigraf = nx.MultiDiGraph()
        multidigraf.add_nodes_from(self.observerede_punkter)
        for k, obs in self._observationer.items():
            multidigraf.add_edge(obs.fra, obs.til, key=k, data=obs)
        return multidigraf

    def netanalyse(self) -> tuple[NivNet, list[NivSubnet], list[PunktNavn]]:
        """
        Konstruér netgraf og find ensomme punkter

        Nettet reduceres for de ensomme punkter, da ensomme punkter ikke kan estimeres i
        udjævningen.
        """

        # Find subnet
        # weakly connected er at "lade som om" grafen er undirected, og så finde connectede subnet.
        # På formelt grafsprog er component=subnet
        subnet = [set(c) for c in nx.weakly_connected_components(self.multidigraf)]

        # For hvert subnet undersøger vi om der findes et fastholdt punkt
        ensomme_subnet = [
            list(subn)
            for subn in subnet
            if set(self.fastholdte.keys()).isdisjoint(subn)
        ]

        # Punkterne i de ensomme subnet skal ikke med i netgrafen
        ensomme_punkter = set().union(*ensomme_subnet)
        net_uden_ensomme = self.multidigraf.copy()
        net_uden_ensomme.remove_nodes_from(ensomme_punkter)

        # Det behøves faktisk ikke at konvertere her da byg_netgeometri_og_singulære
        # faktisk virker med networkx Graph objektet, da Graph objekterne opfører sig som dicts
        net_uden_ensomme = nx.to_dict_of_lists(net_uden_ensomme)

        # Estimerbare punkter er dem som er observerede, men ikke ensomme eller fastholdte.
        estimerbare_punkter = list(
            set(net_uden_ensomme.keys()).difference(self.fastholdte.keys())
        )

        # Gem de estimerbare punkter så de kan bruges af motoren senere.
        self.estimerbare_punkter = estimerbare_punkter

        return net_uden_ensomme, ensomme_subnet, estimerbare_punkter

    def beregn_lukkesummer(
        self, min_længde=3, metode: str = None, **kwargs
    ) -> dict[tuple[PunktNavn], LukkesumStats]:
        """
        Finder polygoner i nivellementnettet og beregner lukkesummer

        Returnerer en dict hvor nøglerne er selve polygonerne, givet ved `kredse`, og
        værdierne er de beregnde statistiske parametre, herunder lukkesummer, pakket ind i
        dataklassen `LukkesumStats`.

        Ønsker man at beregne lukkesummen af en bestemt polygon kan man bruge
        `lukkesum_af_polygon` direkte.
        """
        # Hvis metode ikke er eksplicit sat, så bruger vi simpelt tjek for at vælge
        # metoden. Hvis der er mange observationer, så kan antallet af polygoner nemlig
        # eksplodere, og det er derfor nødvendigt med en anden metode.
        if metode is None:
            metode = "mcb"
            if len(self.observationer) > 1000:
                metode = "cb"

        polygoner = find_polygoner(
            self.multidigraf, min_længde=min_længde, metode=metode, **kwargs
        )

        # Præaggreger observationer
        digraf = aggreger_multidigraf(self.multidigraf)

        lukkesummer = {
            tuple(kreds): lukkesum_af_polygon(
                digraf, kreds, lukket=True
            ).omregn_til_mm()
            for kreds in polygoner
        }

        return lukkesummer

    @abstractmethod
    def udjævn(self):
        """Udjævn observationer"""
        pass

    @property
    @abstractmethod
    def filer(self) -> list:
        """En liste af filnavne som motoren producerer"""
        pass


class GamaRegn(RegneMotor):
    """
    Regnemotor som bruger GNU Gama til at lave nivellementberegninger.
    """

    def __init__(
        self,
        *,
        xml_in: str = None,
        xml_out: str = None,
        html_out: str = None,
        **kwargs,
    ):
        # Sætter først self.projektnavn
        super().__init__(**kwargs)

        # Hvis gama filnavne ikke er sat bruges projektnavnet
        self.xml_in = xml_in or f"{self.projektnavn}.xml"
        self.xml_out = xml_out or f"{self.projektnavn}-resultat.xml"
        self.html_out = html_out or f"{self.projektnavn}-resultat.html"

    @property
    def filer(self) -> list:
        """En liste af filer som Gama producerer"""
        return [self.xml_in, self.xml_out, self.html_out]

    @filer.setter
    def filer(self, nye_filnavne):
        """Sæt nye filnavne"""
        self.xml_in, self.xml_out, self.html_out = nye_filnavne

    def skriv_gama_inputfil(self):
        """
        Skriv gama-inputfil i XML-format
        """
        with open(self.xml_in, "wt") as gamafil:
            # Preambel
            gamafil.write(
                f"<?xml version='1.0' ?><gama-local>\n"
                f"<network angles='left-handed' axes-xy='en' epoch='0.0'>\n"
                f"<parameters\n"
                f"    algorithm='gso' angles='400' conf-pr='0.95'\n"
                f"    cov-band='0' ellipsoid='grs80' latitude='55.7' sigma-act='aposteriori'\n"
                f"    sigma-apr='1.0' tol-abs='1000.0'\n"
                f"/>\n\n"
                f"<description>\n"
                f"    Nivellementsprojekt {ascii(self.projektnavn)}\n"  # Gama kaster op over Windows-1252 tegn > 127
                f"</description>\n"
                f"<points-observations>\n\n"
            )

            # Fastholdte punkter
            gamafil.write("\n\n<!-- Fixed -->\n\n")
            for punkt, kote in self.fastholdte.items():
                gamafil.write(f"<point fix='Z' id='{punkt}' z='{kote}'/>\n")

            # Vi sorterer punkter til udjævning, så de ser pæne ud i Gama inputfilen.
            estimerede_punkter = sorted(self.estimerbare_punkter)
            gamafil.write("\n\n<!-- Adjusted -->\n\n")
            for punkt in estimerede_punkter:
                gamafil.write(f"<point adj='z' id='{punkt}'/>\n")

            # Observationer
            gamafil.write("<height-differences>\n")
            for obs in self.observationer:
                gamafil.write(
                    f"<dh from='{obs.fra}' to='{obs.til}' "
                    f"val='{obs.deltaH:+.6f}' "
                    f"dist='{obs.afstand:.5f}' stdev='{obs.spredning:.5f}' "
                    f"extern='{obs.id}'/>\n"
                )

            # Postambel
            gamafil.write(
                "</height-differences>\n"
                "</points-observations>\n"
                "</network>\n"
                "</gama-local>\n"
            )

    def kald_gama(self):
        """Udjævning via gama"""

        ret = subprocess.run(
            [
                "gama-local",
                self.xml_in,
                "--xml",
                self.xml_out,
                "--html",
                self.html_out,
            ]
        )

        if ret.returncode:
            if not Path(self.xml_out).is_file():
                raise UdjævningFejl(
                    """Beregning ikke gennemført. Kontroller om nettet er sammenhængende, og ved flere net om der mangler fastholdte punkter."""
                )
            # Hvis filen findes så bed bruger om at checke den.
            raise UdjævningFejl(f"Beregning ikke gennemført. Check {self.html_out}")

    def læs_gama_outputfil(self) -> list[NivKote]:
        """
        Læser output fra GNU Gama og returnerer relevante parametre til at skrive xlsx fil
        """
        with open(self.xml_out) as resultat:
            doc = xmltodict.parse(resultat.read())

        # Sammenhængen mellem rækkefølgen af elementer i Gamas punktliste (koteliste
        # herunder) og varianserne i covariansmatricens diagonal er uklart beskrevet:
        # I Gamas xml-resultatfil antydes at der skal foretages en ombytning.
        # Men rækkefølgen anvendt her passer sammen med det Gama præsenterer i
        # html-rapportudgaven af beregningsresultatet.
        koteliste = doc["gama-local-adjustment"]["coordinates"]["adjusted"]["point"]
        varliste = doc["gama-local-adjustment"]["coordinates"]["cov-mat"]["flt"]

        # Konverter til liste i tilfælde af der kun er blevet udjævnet ét punkt.
        if not isinstance(koteliste, list):
            koteliste = [koteliste]
        if not isinstance(varliste, list):
            varliste = [varliste]

        assert len(koteliste) == len(
            varliste
        ), "Mismatch mellem antal koter og varianser"

        nye_koter = []
        for punkt, var in zip(koteliste, varliste):
            nye_koter.append(
                NivKote(
                    punkt=punkt["id"],
                    dato=self.gyldighedstidspunkt,
                    H=float(punkt["z"]),
                    spredning=sqrt(float(var)),
                )
            )

        return nye_koter

    def udjævn(self):
        """Skriver gama input, kalder gama og læser gama output."""

        self.skriv_gama_inputfil()
        self.kald_gama()
        self.nye_koter = self.læs_gama_outputfil()


class DumRegn(RegneMotor):
    """Eksempel på en alternativ regnemotor"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filer = []

    def udjævn(self):
        self.nye_koter = self.gamle_koter

    @property
    def filer(self) -> list:
        """DumRegn producerer ingen filer, returnerer altid den samme tomme liste."""
        return self._filer

    @filer.setter
    def filer(self, _):
        """En dum setter, der ikke ændrer noget."""


class SmartRegn(RegneMotor):
    """Regnemotor der anvender `WeightedLeastSquares`

    Observationsligningerne opstilles på matrixform som inverteres
    i klassen `WeightedLeastSquares`.

    Resultaterne opsummeres som html-rapport i stil med output fra gama-local.

    Performance vs gama-local:

    Gentagne benchmark-test med samtlige historiske nivellementkampagner har vist, at
    motoren er væsentligt hurtigere end gama når det kommer til selve udjævningen af
    observationerne, ofte op mod 100 gange eller mere. Dog tager det relativt lang tid at
    generere den efterfølgende html-rapport.

    Alt i alt er gama derfor 1.5-4 gange hurtigere ved "mellemstore" niv-sager, hvor der
    udjævnes mellem 20-300 punkter.

    For små kampagner, samt meget store kampagner er SmartRegn hurtigst.
    Guldstandarden - udjævning af 3. præc - tager 5-10 min for SmartRegn og 10-20 timer
    for GamaRegn, hvilket vil sige ca. en faktor 100 gange hurtigere.

    Validering af resulater:

    Korrektheden af resultaterne er ligeledes verificeret ved gentagne benchmark-tests og
    sammenligning med gama.
    Det er vist at resulaterne er identiske ned til numerisk præcision, både hvad angår de
    udjævnede koter og deres estimerede spredninger.
    Dog håndteres særtilfældet hvor der findes "self-loops" (observationer fra og til
    samme punkt) forskellig ift. gama, som gør at resulaterne i dette tilfælde kan
    afvige op til 0.5 mm på de udjævnede koter.

    Elimination af grovfejl:

    Desuden fjerner gama på forhånd grovfejl, ved at estimere en approximativ løsning
    først, hvilket også kan give anledning til afvigelser mellem Smart og Gama. Ulempen
    ved denne fremgangsmåde er dog, at det i uheldige tilfælde kan ødelægge
    netværksgeometrien, og gøre problemet uløseligt. (Fx hvis der er grovfejl på alle
    observationer til det fastholdte punkt).
    Med Smart, vil grovfejl fremtræde som store outliers efter endt udjævning, og det er
    op til operatøren at opdage og slukke outlieren, og foretage en ny udjævning.
    """

    def __init__(
        self,
        *args,
        opt_plot: bool = False,
        skip_self_loops: bool = False,
        skip_fastholdte_obs: bool = False,
        **kwargs,
    ):
        self.opt_plot = opt_plot
        self.skip_self_loops = skip_self_loops
        self.skip_fastholdte_obs = skip_fastholdte_obs

        super().__init__(*args, **kwargs)
        self.html_out = f"{self.projektnavn}-smart-resultat.html"

    def opstil_ligningssystem(
        self,
        skip_self_loops: bool = False,
        skip_fastholdte_obs: bool = False,
    ):
        """
        Opstil ligningssystem ud fra nivellementobservationer

        Sættes `skip_selfloops=True` springes observationer over hvor fra- og til-punkt
        er det samme.
        Sættes `skip_fastholdte_obs=True` springes observationer over som er gjort imellem
        to fastholdte punkter.

        Ingen af disse to typer observationer har nogen indflydelse på de udjævnede koter.
        Dog bidrager de til den estimerede spredning. Særligt `skip_fastholdte_obs` kan
        have stor indflydelse på spredningsestimatet, da man ofte fastholder alle punkter
        i en gammel punktgruppe, selvom de kan have bevæget sig indbyrdes. Dette kan
        resultere i meget store residualer for observationer mellem fastholdte punkter.

        For at efterligne gama-local, er begge som default sat til `False`. Opdages der
        store residualer mellem fastholdte punkter, bør man tage stilling til, om
        observationen skal slukkes, eller om man skal undlade at fastholdte ét eller flere
        af punkterne.

        Der løses N grundlæggende observationsligninger:

            Hᵢ - Hⱼ = ΔHᵢⱼ

        hvor Hᵢ er koten for punkt i. Der er M ubekendte koter, dvs. 1 ≤ i,j ≤ M.
        Fastholdte punkter håndteres ved direkte substitution i de relevante ligninger. Er
        fx højden af punkt j fastholdt med værdien Hⱼ = k, substitueres dette ind så
        observationsligningen bliver:

            Hᵢ = ΔHᵢⱼ + k

        På matrixform formuleres problemet som X·θ =  Y , hvor X er systemmatricen med M
        rækker og N kolonner (N⨯M), θ (M⨯1) er de M ubekendte koter Hᵢ, og Y (N⨯1) er de
        observerede koteforskelle.

        Som eksempel tages et simpelt nivellementsnet som dette (hvor der kun er
        observationer i frem-retningen)

            1 ──────> 2
            ^         │
            │         │
            │         v
            4 <────── 3

        De 4 ligninger er:

            H₂ - H₁ = ΔH₂₁
            H₃ - H₂ = ΔH₃₂
            H₄ - H₃ = ΔH₄₃
            H₁ - H₄ = ΔH₁₄

        De ubekendte er:

            θ = [H₁  H₂  H₃  H₄]ᵀ

        Systemmatricen er:

            X = [-1  1   0   0
                 0  -1   1   0
                 0   0  -1   1
                 1   0   0  -1]

        og observationsmatricen er:

            Y = [ΔH₂₁  ΔH₃₂  ΔH₄₃  ΔH₁₄]ᵀ

        Når vi løser for koterne direkte på denne måde kræves der mindst ét fastholdt
        punkt, pr. sammenhængende net af observationer. Fastsættes fx punkt 1 med højden
        H₁ = k, falder denne ud som ubekendt:

            X = [1   0   0
                -1   1   0
                 0  -1   1
                 0   0  -1]

            Y = [ΔH₂₁ + k
                 ΔH₃₂
                 ΔH₄₃
                 ΔH₁₄ - k]

            θ = [H₂  H₃  H₄]ᵀ

        """
        estimerbare = tuple(sorted(self.estimerbare_punkter))
        faste = tuple(self.fastholdte.keys())
        alle_punkter = estimerbare + faste

        def _loop_over_graf():
            """Hjælpefunktion der sparer 2 indrykningsniveauer"""
            for fra in self.multidigraf:
                if not fra in alle_punkter:
                    continue
                for til in self.multidigraf[fra]:
                    # Skip observationer i subnet uden fastholdte
                    if not (fra in alle_punkter and til in alle_punkter):
                        continue

                    # Skip kalibrerings-observationer som er gjort fra-til samme punkt
                    if skip_self_loops and fra == til:
                        continue

                    # Skip observationer imellem fastholdte punkter
                    if skip_fastholdte_obs and (
                        fra in self.fastholdte and til in self.fastholdte
                    ):
                        continue

                    # Nu gennemgås alle observationer
                    for obskey in self.multidigraf[fra][til]:
                        yield (fra, til), obskey

        index_to_obs_mapper = {}
        index_to_pkt_mapper = {}
        fra_til_multipliers = (-1, 1)

        # Initialisér de 3 matricer der repræsenterer Systemet, Observationerne og Vægtene.
        N = len(self.observationer)
        M = len(self.estimerbare_punkter)
        X = np.zeros((N, M))
        Y = np.zeros((N))
        W = np.zeros((N, N))

        # Opbyg de 3 matricer ved at loope over niv-grafen
        for i, (fra_til, obskey) in enumerate(_loop_over_graf()):
            obs = self._observationer[obskey]

            # Nedskriv observationsnøglen og indexet i matricen
            index_to_obs_mapper[i] = obskey

            # Opdatér observationsvektor og vægte
            Y[i] = obs.deltaH
            W[i, i] = (1 / (obs.spredning)) ** 2

            for multiplier, pkt in zip(fra_til_multipliers, fra_til):
                # Hvis pkt er fastholdt, trækkes den fastholdte værdi
                # fra observationsvektoren Y
                Y[i] -= multiplier * self.fastholdte.get(pkt, 0)

                if not pkt in estimerbare:
                    continue
                j = estimerbare.index(pkt)
                index_to_pkt_mapper[j] = pkt

                # Hvis fra == til, så vil vi først sige X[i,j] += -1, derefter
                # X[i,j] += 1, hvilket resulterer i X[i,j]=0 som forventet.
                X[i, j] += multiplier

        self.index_to_pkt_mapper = index_to_pkt_mapper
        self.index_to_obs_mapper = index_to_obs_mapper

        # drop nul-rækker.
        # X,Y,W initieres med antal rækker svarende til det totale antal observationer.
        # Da dette inkluderer ikke-forbundne subnet, samt at der nogle gange skippes
        # observationer, jf. de 3 betingelser ovenfor, kan de sidste rækker være 0 hele
        # vejen igennem. Hvis rækkerne ikke droppes vil N være kunstigt højt hvilket
        # påvirker antallet af frihedsgrader og dermed varians-estimaterne.
        N = i + 1
        X = X[:N, :]
        Y = Y[:N]
        W = W[:N, :N]

        return X, Y, W

    def løs_ligningssystem(self, X: np.ndarray, y: np.ndarray, W: np.ndarray):
        """Løs det lineære ligningssystem

        Systemet løses via `WeightedLeastSquares.solve()`
        """
        # Observationer konverteres til mm. Estimerede højder bliver derved også i mm
        self.stats = WeightedLeastSquares(
            X=X,
            W=W,
            y=y * 1e3,
        )

        udjævnede_koter, residualer = self.stats.solve()

        # Gem til NivKote object
        nye_koter = []
        for j, punkt in self.index_to_pkt_mapper.items():

            nye_koter.append(
                NivKote(
                    punkt=punkt,
                    dato=self.gyldighedstidspunkt,
                    H=udjævnede_koter[j] * 1e-3,  # konverter tilbage til m
                    spredning=self.stats.std_theta[j],
                )
            )

        return nye_koter

    @property
    def filer(self) -> list:
        """En liste af filer som SmartRegn producerer"""
        return [self.html_out]

    @filer.setter
    def filer(self, nye_filnavne: list):
        """Sæt nye filnavne"""
        (self.html_out,) = nye_filnavne

    def generer_statistik(self):
        """Generér tabeller der opsummerer udjævningsresulaterne"""
        n_udjævnede = len(self.estimerbare_punkter)
        n_fastholdte = len(self.fastholdte)
        n_total = n_udjævnede + n_fastholdte

        # Nogle observationer bliver ikke anvendt.
        # Fx. self-loops og observationer mellem fastholdte punkter.
        n_observationer = len(self.observationer)
        n_anvendte_observationer = self.stats.N
        dof = self.stats.dof

        r2 = self.stats.R2
        mse = self.stats.MSE
        std_posterior = self.stats.std0_hat  # "spredning på vægtenheden"

        # Beregn sandsynlighed for at std_prior == std_posterior via T-test
        alpha = 0.05
        ttest = Ttest(std_est=1, H0=std_posterior, dof=dof - 1, alpha=alpha)
        critical_value = ttest.critical_value

        # Tabel med overblik over udjævningsresultatet
        def _overbliktabel():
            tbl = generer_rapporttabel(
                title="Overblik",
                title_style="bold",
                show_header=False,
                box=SIMPLE_ASCII_BOX,
            )

            section1 = [
                ("Punkter estimeret", n_udjævnede),
                ("Punkter fastholdt", n_fastholdte),
                ("Punkter i alt", n_total),
            ]
            section2 = [
                ("Obs i alt", n_observationer),
                ("Obs anvendte", n_anvendte_observationer),
                ("Obs outliers", n_outliers),
                ("Frihedsgrader", dof),
            ]
            section3 = [
                ("R2", r2),
                ("MSE (mm²)", mse),
                ("Sigma 0 (mm)", std_posterior),  # spredning på vægtenhed
                ("Kritisk værdi", critical_value),
            ]
            for row in section1:
                tbl.add_row(*[klargør_celle(c) for c in row])
            tbl.add_section()
            for row in section2:
                tbl.add_row(*[klargør_celle(c) for c in row])
            tbl.add_section()
            for row in section3:
                tbl.add_row(*[klargør_celle(c) for c in row])
            return tbl

        # Tabel over fastholdte
        def _faste_tabel():
            fixed_hdr = ["Punkt", "Kote (m)"]
            fixed_rows = [[pkt, kote] for pkt, kote in self.fastholdte.items()]
            return generer_rapporttabel(
                *fixed_hdr,
                title="Faste",
                title_style="bold",
                box=SIMPLE_ASCII_BOX,
                rows=sorted(fixed_rows, key=(lambda x: x[0])),
            )

        # Statistik for udjævnede koter
        def _kotetabel():
            kote_table_hdr = ["Punkt", "Kote (m)", "Sigma (mm)"]
            kote_table_rows = [[nk.punkt, nk.H, nk.spredning] for nk in self.nye_koter]
            return generer_rapporttabel(
                *kote_table_hdr,
                title="Udjævnede",
                title_style="bold",
                box=SIMPLE_ASCII_BOX,
                rows=sorted(kote_table_rows, key=lambda x: x[0]),
            )

        # Statistik for observationer og outliers
        def _obstabel():
            obs_hdr = [
                "Fra",
                "Til",
                "dH\n(m)",
                "dH udjævnet\n(m)",
                "Sigma\n(mm)",
                "Residual\n(mm)",
                "Normaliseret\nresidual",
                "Status",
            ]
            obs_rows = []
            obs_styles = []

            # std. afvigelsen for "ukontrollerede" observationer er 0, men
            # bliver sommetider nan, pga numerisk impræcision. Af samme
            # grund bliver normaliseret residual enten til inf eller nan.
            # Håndteres her, så de får ensartet udtryk i tabellen.
            def _handle_nan(array, sub_værdi):
                return [
                    sub_værdi if (np.isinf(abs(e)) or np.isnan(e)) else e for e in array
                ]

            res = self.stats.residuals
            norm_res = _handle_nan(self.stats.normalized_residuals, np.nan)
            std_res = _handle_nan(self.stats.std_residuals, 0.0)
            yhat = self.stats.yhat * 1e-3

            for i, obskey in self.index_to_obs_mapper.items():
                obs = self._observationer[obskey]

                # Tilbage-substituér fastholdte højder så de observerede højdeforskelle i
                # tabellen kan sammenlignes med de "estimerede" højdeforskelle til
                # fastholdte punkter. Gøres ved at "rekonstruére" den udjævnede
                # højdeforskel ud fra residualerne
                yhati = yhat[i]
                if obs.fra in self.fastholdte or obs.til in self.fastholdte:
                    yhati = obs.deltaH - res[i] * 1e-3

                ukontrolleret = "U" if np.isclose(self.stats.leverage[i], 1) else ""
                outlying = "O" if abs(norm_res[i]) > critical_value else ""
                selfloop = "SL" if obs.fra == obs.til else ""
                fast = (
                    "F"
                    if obs.fra in self.fastholdte and obs.til in self.fastholdte
                    else ""
                )
                status = ",".join(
                    filter(None, [ukontrolleret, outlying, selfloop, fast])
                )

                obs_rows.append(
                    [
                        f"{obs.fra}",
                        f"{obs.til}",
                        f"{obs.deltaH:.5f}",
                        f"{yhati:.5f}",
                        f"{std_res[i]:.3f}",
                        f"{res[i]:.3f}",
                        f"{norm_res[i]:.3f}",
                        f"{status}",
                    ]
                )

            # Sortering så frem- og tilbage observationer grupperes
            obs_rows.sort(key=lambda x: (sorted((x[0], x[1])), x[0]))

            # Outliers farves røde
            obs_styles = ["red" if "O" in r[7] else "" for r in obs_rows]

            obs_tabel = generer_rapporttabel(
                *obs_hdr,
                title="Observationer",
                title_style="bold",
                box=SIMPLE_ASCII_BOX,
                rows=obs_rows,
                styles=obs_styles,
            )
            obs_tabel.caption = """Statusforklaring:

    O  = Outlier. Normaliseret residual er større end den kritiske værdi
    F  = Fastholdt. Observation mellem to fastholdte punkter
    SL = Self-loop. Fra og til er det samme punkt
    U  = Ukontrolleret. Observation er ikke "kontrolleret" af andre
         observationer.

Resultater er meget følsomme over for selv små fejl på Ukontrollerede observationer.
Omvendt, så har Fastholdte og Self-Loops ingen indflydelse på de udjævnede koter.
"""
            obs_tabel.caption_style = ""
            obs_tabel.caption_justify = "left"

            outlier_rows = [row for row in obs_rows if "O" in row[7]]
            outlier_tabel = generer_rapporttabel(
                *obs_hdr,
                title="Outliers",
                title_style="bold",
                box=SIMPLE_ASCII_BOX,
                rows=outlier_rows,
                styles="red",
            )

            return obs_tabel, outlier_tabel, len(outlier_rows)

        faste_tabel = _faste_tabel()
        kote_tabel = _kotetabel()
        obs_tabel, outlier_tabel, n_outliers = _obstabel()
        overblik_tabel = _overbliktabel()

        console = Console(
            record=True,
            file=open(os.devnull, "wt"),
            color_system="truecolor",
        )

        # Det er by far printningen af tabellerne der tager længst tid.
        print_tabel(overblik_tabel, console)
        print_tabel(faste_tabel, console)
        print_tabel(kote_tabel, console)
        print_tabel(obs_tabel, console)
        if n_outliers:
            print_tabel(outlier_tabel, console)

        self.console = console

    def gem_udjævningsrapport(self):
        """Gem udjævningsrapporten"""
        self.console.save_html(self.html_out)

    def udjævn(self):
        X, y, W = self.opstil_ligningssystem(
            skip_self_loops=self.skip_self_loops,
            skip_fastholdte_obs=self.skip_fastholdte_obs,
        )
        self.nye_koter = self.løs_ligningssystem(X, y, W)

        if self.opt_plot:
            visualize_residuals(self.stats)
            visualize_matrices(self.stats)

        self.generer_statistik()
        self.gem_udjævningsrapport()

def _spredning(

    observationstype: str,
    afstand_i_m: float,
    antal_opstillinger: float,
    afstandsafhængig_spredning_i_mm: float,
    centreringsspredning_i_mm: float,
) -> float:
    """Apriorispredning for nivellementsobservation

    Fx.  MTL: spredning("mtl", 500, 3, 2, 0.5) = 1.25
         MGL: spredning("MGL", 500, 3, 0.6, 0.01) = 0.4243
         NUL: spredning("NUL", .....) = 0

    Rejser ValueError ved ukendt observationstype eller
    (via math.sqrt) ved negativ afstand_i_m.

    Negative afstandsafhængig- eller centreringsspredninger
    behandles som positive.

    Observationstypen NUL benyttes til at sammenbinde disjunkte
    undernet - det er en observation med forsvindende apriorifejl,
    der eksakt reproducerer koteforskellen mellem to fastholdte
    punkter
    """

    if "NUL" == observationstype.upper():
        return 0

    # I tilfælde af 0 antal opstillinger, sjusser vi os til antallet ved brug af
    # gennemsnitlig længde pr. opstilling på 75 m, beregnet ved:
    #
    # SELECT MEDIAN(value2/value3), AVG(value2/value3)
    # FROM OBSERVATION o
    # WHERE value3 > 0 -- mindst 1 opstilling
    # 	AND OBSERVATIONSTYPEID = 1 -- MGL
    # 	AND REGISTRERINGTIL IS NULL
    #
    # Se også beskrivelsen her: https://github.com/SDFIdk/FIRE/issues/852

    if antal_opstillinger == 0:
        antal_opstillinger = ceil(afstand_i_m / 75)

    opstillingsafhængig = sqrt(antal_opstillinger * (centreringsspredning_i_mm**2))

    if "MTL" == observationstype.upper():
        afstandsafhængig = afstandsafhængig_spredning_i_mm * afstand_i_m / 1000
        return hypot(afstandsafhængig, opstillingsafhængig)

    if "MGL" == observationstype.upper():
        afstandsafhængig = afstandsafhængig_spredning_i_mm * sqrt(afstand_i_m / 1000)
        return hypot(afstandsafhængig, opstillingsafhængig)

    raise ValueError(f"Ukendt observationstype: {observationstype}")
