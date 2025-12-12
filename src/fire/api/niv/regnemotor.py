from abc import ABC, abstractmethod
from dataclasses import astuple
from datetime import datetime
from functools import cached_property
import networkx as nx
from math import (
    ceil,
    hypot,
    sqrt,
    isnan,
)
from pathlib import Path
import subprocess
from typing import Self
import xmltodict

import pandas as pd

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

from fire.api.geodetic_levelling.geodetic_correction_levelling_obs import (
    apply_geodetic_corrections_to_height_diffs,
)
from fire.api.geodetic_levelling.metric_to_gpu_transformation import (
    convert_geopotential_heights_to_metric_heights,
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
        self.observationer = observationer
        self.gamle_koter = gamle_koter
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
        return list(self._observationer.values())

    @observationer.setter
    def observationer(self, observationer):
        self._observationer = {uuid(): o for o in observationer}

    @property
    def gamle_koter(self):
        return list(self._gamle_koter.values())

    @gamle_koter.setter
    def gamle_koter(self, gamle_koter):
        self._gamle_koter = {gk.punkt: gk for gk in gamle_koter}

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

    @property
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

    @filer.setter
    @abstractmethod
    def filer(self, val):
        """Sæt nye filnavne"""
        pass

    @property
    @abstractmethod
    def parametre(self) -> dict:
        """En dict af parametre brugt af motoren"""
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

    @property
    def parametre(self) -> dict:
        """En dict af parametre brugt i gama-local"""
        return dict()

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
        if isinstance(koteliste, dict):
            koteliste = [koteliste]
        if isinstance(varliste, dict):
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

    @property
    def parametre(self) -> dict:
        """En dict af parametre brugt i DumRegn"""
        return dict()


class GeodætiskRegn(GamaRegn):
    """
    En geodætisk regnemotor
    TO DO: Dokumentér hvad GeodætiskRegn kan (i stil med det som
    er lavet for den overordnede RegneMotor).
    """

    def __init__(
        self,
        tidal_system: str = None,
        epoch_target: pd.Timestamp = None,
        height_diff_unit: str = "metric",
        output_height: str = None,
        deformationmodel: str = None,
        gravitymodel: str = None,
        grid_inputfolder: Path = None,
        filnavn_korrektioner: str = None,
        **kwargs,
    ):
        # intitialiser parametre
        self.tidal_system = tidal_system
        if epoch_target is None:
            self.epoch_target = epoch_target
        else:
            self.epoch_target = datetime(int(epoch_target), 1, 1)
        self.height_diff_unit = height_diff_unit
        self.output_height = output_height
        self.deformationmodel = deformationmodel
        self.gravitymodel = gravitymodel
        if grid_inputfolder is None:
            self.grid_inputfolder = grid_inputfolder
        else:
            self.grid_inputfolder = Path(grid_inputfolder)

        # initialiserer nedarvede parametre
        super().__init__(**kwargs)

        # initialiserer parameter vedr. output-fil med geodætiske korrektioner
        self.filnavn_korrektioner = (
            filnavn_korrektioner or f"{self.projektnavn}-korrektioner.xlsx"
        )

    @property
    def filer(self) -> list:
        """En liste af filer som GeodætiskRegn producerer"""
        return [self.xml_in, self.xml_out, self.html_out, self.filnavn_korrektioner]

    @filer.setter
    def filer(self, nye_filnavne):
        """Sæt nye filnavne"""
        self.xml_in, self.xml_out, self.html_out, self.filnavn_korrektioner = (
            nye_filnavne
        )

    @property
    def parametre(self) -> dict:

        return dict(
            tidal_system=self.tidal_system,
            epoch_target=self.epoch_target,
            height_diff_unit=self.height_diff_unit,
            output_height=self.output_height,
            deformationmodel=self.deformationmodel,
            gravitymodel=self.gravitymodel,
            grid_inputfolder=self.grid_inputfolder,
        )

    def korriger_observationer(self):
        """Korrigér observationer."""
        if (
            self.tidal_system is not None
            or self.epoch_target is not None
            or self.height_diff_unit == "gpu"
        ):
            print("Højdeforskelle påføres geodætiske korrektioner inden udjævning")

            (self.observationer, self.korrektioner_obs) = (
                apply_geodetic_corrections_to_height_diffs(
                    self.observationer,
                    self.gamle_koter,
                    self.height_diff_unit,
                    self.epoch_target,
                    self.tidal_system,
                    self.grid_inputfolder,
                    self.deformationmodel,
                    self.gravitymodel,
                )
            )

    def konverter_gamle_højder_til_gpu(self):
        """Helmert-højder fra databasen konverteres til geopotentielle højder."""
        if self.height_diff_unit == "gpu":
            print(
                "Højder konverteres fra Helmert-højder til geopotentielle højder inden udjævning"
            )

            # Helmert-højderne fra databasen gemmes inden konvertering til geopotentielle højder
            self.gamle_koter_db = self.gamle_koter

            (self.gamle_koter, self.tyngder_konvertering_til_gpu) = (
                convert_geopotential_heights_to_metric_heights(
                    self.gamle_koter,
                    "helmert_to_geopot",
                    self.grid_inputfolder,
                    self.gravitymodel,
                    self.tidal_system,
                    iterate=True,
                )
            )

    def konverter_nye_højder_til_meter(self):
        """Geopotentielle højder fra udjævningen konverteres til Helmert- eller normalhøjder."""
        if self.height_diff_unit == "gpu" and (
            self.output_height == "helmert" or self.output_height == "normal"
        ):
            deskriptor = {"helmert": "Helmert-højder", "normal": "normalhøjder"}

            print(
                f"Højder konverteres fra geopotentielle højder til {deskriptor[self.output_height]} efter udjævning"
            )

            # er alle punkter med i self.nye_koter? Kun ikke fastholdte?

            # Konvertering til Helmert- eller normalhøjder afhænger af geografisk position
            for ny_kote in self.nye_koter:
                punktnr = ny_kote.punkt

                (ny_kote.nord, ny_kote.øst) = [
                    (gammel_kote.nord, gammel_kote.øst)
                    for gammel_kote in self.gamle_koter
                    if gammel_kote.punkt == punktnr
                ][0]

            (self.nye_koter, self.tyngder_konvertering_til_meter) = (
                convert_geopotential_heights_to_metric_heights(
                    self.nye_koter,
                    f"geopot_to_{self.output_height}",
                    self.grid_inputfolder,
                    self.gravitymodel,
                    self.tidal_system,
                    iterate=True,
                )
            )

    def gendan_gamle_højder(self):
        """Helmert-højder fra databasen gendannes."""
        if self.height_diff_unit == "gpu":
            self.gamle_koter = self.gamle_koter_db

    def skriv_korrektioner(self):
        """Skriv excel-fil med anvendte korrektioner/tyngder og beregningsparametre."""
        beregningsparametre = {"regnemotor": type(self).__name__}
        beregningsparametre.update(self.parametre)

        beregningsparametre = pd.DataFrame.from_dict(
            beregningsparametre, orient="index"
        ).reset_index()

        beregningsparametre.columns = ["Name", "Value"]

        with pd.ExcelWriter(
            self.filnavn_korrektioner
        ) as writer:  # pylint: disable=abstract-class-instantiated
            beregningsparametre.to_excel(writer, sheet_name="Parameters", index=False)
            self.korrektioner_obs.to_excel(
                writer, sheet_name="Corrections levelling", index=False
            )
            self.tyngder_konvertering_til_gpu.to_excel(
                writer, sheet_name="Helmert heights > gpu", index=False
            )
            self.tyngder_konvertering_til_meter.to_excel(
                writer,
                sheet_name="gpu heights > Helmert|normal",
                index=False,
            )

    def udjævn(self):
        """Korrigerer observationer, konverterer gamle højder, skriver gama input, kalder gama,
        læser gama output, konverterer nye højder og skriver excel-fil med korrektioner.
        """
        self.korriger_observationer()
        self.konverter_gamle_højder_til_gpu()
        self.skriv_gama_inputfil()
        self.kald_gama()
        self.nye_koter = self.læs_gama_outputfil()
        self.konverter_nye_højder_til_meter()
        self.gendan_gamle_højder()
        self.skriv_korrektioner()


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
