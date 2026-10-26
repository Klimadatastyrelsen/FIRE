from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.dialects.oracle import TIMESTAMP

import fire
from fire.api.model import (
    StringEnum,
    Boolean,
    DeclarativeBase,
    FikspunktregisterObjekt,
    beregning_observation,
)


__all__ = [
    "ObservationsType",
    "Observation",
    "ObservationstypeID",
    "GeometriskKoteforskel",
    "TrigonometriskKoteforskel",
    "Retning",
    "Horisontalafstand",
    "Skråafstand",
    "Zenitvinkel",
    "Vektor",
    "Nulobservation",
    "ObservationsLængde",
    "KoordinatKovarians",
    "ResidualKovarians",
]


class ObservationsType(DeclarativeBase):
    __tablename__ = "observationstype"
    objektid = Column(Integer, primary_key=True)
    observationstypeid = Column(Integer, unique=True, nullable=False)
    name = Column("observationstype", String(4000), nullable=False)
    beskrivelse = Column(String(4000), nullable=False)
    value1 = Column(String, nullable=False)
    value2 = Column(String)
    value3 = Column(String)
    value4 = Column(String)
    value5 = Column(String)
    value6 = Column(String)
    value7 = Column(String)
    value8 = Column(String)
    value9 = Column(String)
    value10 = Column(String)
    value11 = Column(String)
    value12 = Column(String)
    value13 = Column(String)
    value14 = Column(String)
    value15 = Column(String)
    sigtepunkt = Column(StringEnum(Boolean), nullable=False, default=Boolean.FALSE)
    observationer = relationship(
        "Observation",
        order_by="Observation.objektid",
        back_populates="observationstype",
    )


class ObservationstypeID:
    """
    ID for eksisterende observationstyper i FIREDB-databasen.

    Notes
    -----
    ID'erne er fastsat i DDL-filerne for databasen og kan derfor fastsættes her.

    """

    geometrisk_koteforskel = 1
    trigonometrisk_koteforskel = 2
    retning = 3
    horisontalafstand = 4
    skråafstand = 5
    zenitvinkel = 6
    vektor = 7
    nulobservation = 8
    observationslængde = 9
    koordinat_kovarians = 10
    residual_kovarians = 11


# Her bruger vi SQLAlchemy's Single Inheritance-funktionalitet:
#
# En instans af `Observation` har kolonnerne `value1..15`, hvor indholdets betydning
# er defineret af observationstypen givet ved informationerne i entiteten
# `Observationstype`.
#
# Med ovennævnte funktionalitet kan man nedarve fra en entitet, her `Observation`, og
# angive meningsfulde navne for de pågældende kolonner. Ved hjælp af
# `__mapper_args__`-indgangene `polymorphic_on` og `polymorphic_identity` kan man skelne
# mellem observationstyperne med hver sin observationsklasse---eksempelvis
# `GeometriskKoteforskel`, når `polymorphic_identity` er 1, da 1 er det faste ID i
# `ObservationstypeID`, der angiver en geometrisk koteforskel.
#
# Endelig løsning, erfaringer og rationale:
#
# Med kun én nedarvning (observationsklasse), eksempelvis `GeometriskKoteforskel`,
# fungerer nedarvningen fint. Man kan lave en simpel mapping med en linie som
# følgende i den nedarvede klasse:
#
#     class GeometriskKoteforskel(Observation):
#         __mapper_args__ = {
#             "polymorphic_identity": ObservationstypeID.geometrisk_koteforskel,
#         }
#
#         koteforskel = Column('value1', Float, nullable=False)
#         "Koteforskel / [m]"
#
#         nivlængde = Column('value2', Float)
#         "Nivellementslængde / [m]"
#
#         (...)
#
# Men med to eller flere nedarvninger af `Observation`, e.g med klassen
# `TrigonometriskKoteforskel`, kommer der sammenstød mellem attribut-navnene.
#
# Ifølge [SQLAlchemy: Single Table Inheritance, same column in childs][single-table-inheritance],
# hvis svar er skrevet af zzzeek, der er vedligeholder på SQLAlchemy, er løsningen,
# at man bruger SQLAlchemy's class decorator `declared_attr` og laver en form for
# property for hver kolonne, der skal være i den nedarvede klasse.
#
# [single-table-inheritance]: https://stackoverflow.com/a/17140952
#
# Følger man dette svar får man dog problemer, der ligner dét, der skulle løses, her
# ved at `TrigonometriskKoteforskel` definerer et felt, her `koteforskel`, der allerede
# er defineret på Observation (ja, Observation, ikke klassen GeometriskKoteforskel).
#
# Vi håbede, at man med Single Inheritance kunne fjerne attributerne `value1..15`
# fra `Observation`. Beholde man dem, forsvinder problemet, hvor to eller flere
# nedarvende klasser, her `GeometriskKoteforskel` og `TrigonometriskKoteforskel`,
# begge anvender eksempelvis `value1` på entiteten til en attribut `koteforskel`.
#
# I løsningen fra SO er det tilsyneladende muligt ikke at have en komplet mapping
# i moder-klassen og samtidig have flere nedarvende klasser lave en attribut
# med samme navn og samme kolonne i entiteten. Det virker bare ikke.
#
# To fremgangsmåder løser altså problemet:
#
# 1. Fortsæt med at lade klasserne nedarve fra samme moderklasse, og behold
#    attributterne `value1..15`. Dette virker, og man kan falde tilbage til
#    moderklassen som standard observationsklasse.
#
#    En ulempe ved denne fremgangsmåde er, at man får alle `value1..15`
#    attributter med i hvert objekt, hvilket kan være kostbart i hukommelse.
#
# 2. Efter definition af klassen `GeometriskKoteforskel` kan denne bruges i
#    eksempelvis `TrigonomiskKoteforskel` istedet for Observation, når man
#    definerer sine properties.
#
#    Eksempel:
#
#        class GeometriskKoteforskel(Observation):
#            (...)
#            @declared_attr
#            def koteforskel(cls):
#                # Virker kun for den første nedarvende klasse.
#                # På SO viser løsningen, at det skulle fungere for alle andre
#                # nedarvende klasser.
#                return Observation.__table__.c.get('value1', Column(Float))
#
#
#        class TrigonometriskKoteforskel(Observation):  # Brug fortsat Observation
#            (...)
#
#            @declared_attr
#            def koteforskel(cls):
#                # Dette virker for os.
#                return GeometriskKoteforskel.__table__.c.get('value1', Column(Float))
#
# Vælger vi mulighed 2, bliver koden for besværlig at vedligeholde, fordi
# de enkelte observationsklasser afhænger af hinanden i en lang kæde fra
# modeklassen `Observation`.
#
# Mulighed 1 er simplere at vedligeholde:
#
# * man kan fjerne en underklasse uden at det ødelægger funktionaliteten
#   af en underklasse, defineret efter denne.
#
# * man kan stadig bruge moderklassen `Observation`, da alle kolonnerne
#   i entiteten er tilgængelige fra denne klasse, selvom de ikke har
#   forklarende navne.
#
# Derfor bruger vi fremgangsmåde 1.
#


class Observation(FikspunktregisterObjekt):
    __tablename__ = "observation"
    id = Column(String, nullable=False, unique=True, default=fire.uuid)
    value1 = Column(Float, nullable=False)
    value2 = Column(Float)
    value3 = Column(Float)
    value4 = Column(Float)
    value5 = Column(Float)
    value6 = Column(Float)
    value7 = Column(Float)
    value8 = Column(Float)
    value9 = Column(Float)
    value10 = Column(Float)
    value11 = Column(Float)
    value12 = Column(Float)
    value13 = Column(Float)
    value14 = Column(Float)
    value15 = Column(Float)
    _fejlmeldt = Column(
        "fejlmeldt", StringEnum(Boolean), nullable=False, default=Boolean.FALSE
    )
    sagseventfraid = Column(String, ForeignKey("sagsevent.id"), nullable=False)
    sagsevent = relationship(
        "Sagsevent", foreign_keys=[sagseventfraid], back_populates="observationer"
    )
    sagseventtilid = Column(String, ForeignKey("sagsevent.id"), nullable=True)
    slettet = relationship(
        "Sagsevent",
        foreign_keys=[sagseventtilid],
        back_populates="observationer_slettede",
    )
    observationstidspunkt = Column(TIMESTAMP(timezone=True), nullable=False)
    antal = Column(Integer, nullable=False, default=1)
    gruppe = Column(Integer)
    observationstypeid = Column(
        Integer, ForeignKey("observationstype.observationstypeid")
    )
    observationstype = relationship(
        "ObservationsType", back_populates="observationer", lazy="selectin"
    )
    sigtepunktid = Column(String(36), ForeignKey("punkt.id"))
    sigtepunkt = relationship("Punkt", foreign_keys=[sigtepunktid])
    opstillingspunktid = Column(String(36), ForeignKey("punkt.id"))
    opstillingspunkt = relationship("Punkt", foreign_keys=[opstillingspunktid])
    beregninger = relationship(
        "Beregning", secondary=beregning_observation, back_populates="observationer"
    )

    __mapper_args__ = {
        "polymorphic_identity": "observation",
        "polymorphic_on": observationstypeid,
    }

    @property
    def fejlmeldt(self):
        return self._fejlmeldt == Boolean.TRUE

    @fejlmeldt.setter
    def fejlmeldt(self, value: Boolean):
        if value:
            self._fejlmeldt = Boolean.TRUE
        else:
            self._fejlmeldt = Boolean.FALSE


class GeometriskKoteforskel(Observation):
    """
    Observation foretaget ved Motoriseret Geometrisk Nivellement (MGL)

    """

    __mapper_args__ = {
        "polymorphic_identity": ObservationstypeID.geometrisk_koteforskel,
    }

    @declared_attr
    def koteforskel(cls):
        """Koteforskel / [m]"""
        return Observation.__table__.c.get("value1", Column(Float, nullable=False))

    @declared_attr
    def nivlængde(cls):
        """Nivellementslængde / [m]"""
        return Observation.__table__.c.get("value2", Column(Float))

    @declared_attr
    def opstillinger(cls):
        """Antal opstillinger"""
        return Observation.__table__.c.get("value3", Column(Integer))

    @declared_attr
    def eta_l(cls):
        """Variabel vedr. eta_1 (refraktion) / [m^3]"""
        return Observation.__table__.c.get("value4", Column(Float))

    @declared_attr
    def spredning_afstand(cls):
        """Empirisk spredning pr. afstandsenhed / [mm/sqrt(km)]"""
        return Observation.__table__.c.get("value5", Column(Float))

    @declared_attr
    def spredning_centrering(cls):
        """Empirisk centreringsfejl pr. opstilling / [mm]"""
        return Observation.__table__.c.get("value6", Column(Float))

    @declared_attr
    def præcisionsnivellement(cls):
        """Præcisionsnivellement [0, 1, 2, 3]"""
        return Observation.__table__.c.get("value7", Column(Integer))


class TrigonometriskKoteforskel(Observation):
    """
    Observation foretaget ved Motoriseret Trigonometrisk Nivellement (MTL)

    """

    __mapper_args__ = {
        "polymorphic_identity": ObservationstypeID.trigonometrisk_koteforskel
    }

    @declared_attr
    def koteforskel(cls):
        """Koteforskel / [m]"""
        return Observation.__table__.c.get("value1", Column(Float, nullable=False))

    @declared_attr
    def nivlængde(cls):
        """Nivellementslængde / [m]"""
        return Observation.__table__.c.get("value2", Column(Float))

    @declared_attr
    def opstillinger(cls):
        """Antal opstillinger"""
        return Observation.__table__.c.get("value3", Column(Integer))

    @declared_attr
    def spredning_afstand(cls):
        """Empirisk spredning pr. afstandsenhed / [mm/sqrt(km)]"""
        return Observation.__table__.c.get("value4", Column(Float))

    @declared_attr
    def spredning_centrering(cls):
        """Empirisk centreringsfejl pr. opstilling / [mm]"""
        return Observation.__table__.c.get("value5", Column(Float))


class Retning(Observation):
    """
    Horisontal retning med uret fra opstilling til sigtepunkt (reduceret til
    ellipsoiden)

    """

    __mapper_args__ = {"polymorphic_identity": ObservationstypeID.retning}

    @declared_attr
    def retning(cls):
        """Retning / [m]"""
        return Observation.__table__.c.get("value1", Column(Float, nullable=False))

    @declared_attr
    def varians_retning(cls):
        """Varians [for] retning hidrørende fra instrument, pr. sats / [rad^2]"""
        return Observation.__table__.c.get("value2", Column(Float))

    @declared_attr
    def varians_samlet(cls):
        """Samlet centreringsvarians for instrumentprisme / [m^2]"""
        return Observation.__table__.c.get("value3", Column(Integer))


class Horisontalafstand(Observation):
    """
    Horisontal afstand mellem opstilling og sigtepunkt (reduceret til ellipsoiden)

    """

    __mapper_args__ = {"polymorphic_identity": ObservationstypeID.horisontalafstand}

    @declared_attr
    def afstand(cls):
        """Afstand / [m]"""
        return Observation.__table__.c.get("value1", Column(Float, nullable=False))

    @declared_attr
    def varians_afstand(cls):
        """Afstandsafhængig varians afstandsmåler / [m^2 / m^2]"""
        return Observation.__table__.c.get("value2", Column(Float))

    @declared_attr
    def varians_samlet(cls):
        """
        Samlet varians for centrering af instrument og prisme, samt grundfejl på
        afstandsmåler / [m^2]
        """
        return Observation.__table__.c.get("value3", Column(Integer))


class Skråafstand(Observation):
    """
    Skråafstand mellem opstilling og sigtepunkt

    """

    __mapper_args__ = {"polymorphic_identity": ObservationstypeID.skråafstand}

    @declared_attr
    def afstand(cls):
        """Afstand / [m]"""
        return Observation.__table__.c.get("value1", Column(Float, nullable=False))

    @declared_attr
    def varians_afstand(cls):
        """Afstandsafhængig varians afstandsmåler pr. måling / [m^2/m^2]"""
        return Observation.__table__.c.get("value2", Column(Float))

    @declared_attr
    def varians_samlet(cls):
        """
        Samlet varians for centrering af instrument og prisme, samt grundfejl på
        afstandsmåler pr. måling / [m^2]
        """
        return Observation.__table__.c.get("value3", Column(Integer))


class Zenitvinkel(Observation):
    """
    Zenitvinkel mellem opstilling og sigtepunkt

    """

    __mapper_args__ = {"polymorphic_identity": ObservationstypeID.zenitvinkel}

    @declared_attr
    def vinkel(cls):
        """Zenitvinkel / [rad]"""
        return Observation.__table__.c.get("value1", Column(Float, nullable=False))

    @declared_attr
    def højde_instrument(cls):
        """Instrumenthøjde / [m]"""
        return Observation.__table__.c.get("value2", Column(Float))

    @declared_attr
    def højde_sigtepunkt(cls):
        """Højde sigtepunkt / [m]"""
        return Observation.__table__.c.get("value3", Column(Integer))

    @declared_attr
    def varians_vinkel(cls):
        """Varians zenitvinkel hidrørende fra instrument, pr. sats / [rad^2]"""
        return Observation.__table__.c.get("value4", Column(Float))

    @declared_attr
    def varians_samlet(cls):
        """Samlet varians instrumenthøjde/højde sigtepunkt / [m^2]"""
        return Observation.__table__.c.get("value5", Column(Integer))


class Vektor(Observation):
    """
    Vektor der beskriver koordinatforskellen fra punkt 1 til punkt 2 (v2-v1)

    """

    __mapper_args__ = {"polymorphic_identity": ObservationstypeID.vektor}

    @declared_attr
    def dx(cls):
        """dx [m]"""
        return Observation.__table__.c.get("value1", Column(Float, nullable=False))

    @declared_attr
    def dy(cls):
        """dy [m]"""
        return Observation.__table__.c.get("value2", Column(Float))

    @declared_attr
    def dz(cls):
        """dz [m]"""
        return Observation.__table__.c.get("value3", Column(Integer))

    @declared_attr
    def varians_afstand(cls):
        """Afstandsafhængig varians [m^2/m^2]"""
        return Observation.__table__.c.get("value4", Column(Float))

    @declared_attr
    def varians_samlet(cls):
        """Samlet varians for centrering af antenner [m^2]"""
        return Observation.__table__.c.get("value5", Column(Integer))

    @declared_attr
    def v_dx(cls):
        """Varians dx [m^2]"""
        return Observation.__table__.c.get("value6", Column(Float, nullable=False))

    @declared_attr
    def v_dy(cls):
        """Varians dy [m^2]"""
        return Observation.__table__.c.get("value7", Column(Float))

    @declared_attr
    def v_dz(cls):
        """Varians dz [m^2]"""
        return Observation.__table__.c.get("value8", Column(Integer))

    @declared_attr
    def cov_dxdy(cls):
        """Covarians dx, dy [m^2]"""
        return Observation.__table__.c.get("value9", Column(Float))

    @declared_attr
    def cov_dxdz(cls):
        """Covarians dx, dz [m^2]"""
        return Observation.__table__.c.get("value10", Column(Integer))

    @declared_attr
    def cov_dydz(cls):
        """Covarians dy, dz [m^2]"""
        return Observation.__table__.c.get("value11", Column(Integer))


class Nulobservation(Observation):
    """
    Observation nummer nul, indlagt fra start i observationstabellen,
    så der kan refereres til den i de mange beregningsevents der fører
    til population af koordinattabellen

    """

    __mapper_args__ = {"polymorphic_identity": ObservationstypeID.nulobservation}


class ObservationsLængde(Observation):
    """
    Observationslængden af en GNSS-måling.

    Bemærk at observationstidspunktet angiver starten af observationsperioden.
    Ved hjælp af observationvarigheden kan både sluttidspunktet og
    "middelobservationstidspunktet" beregnes.
    """

    __mapper_args__ = {"polymorphic_identity": ObservationstypeID.observationslængde}

    def _get_varighed(self):
        # return Observation.__table__.c.get("value1", Column(Float, nullable=False))
        return self.value1

    def _set_varighed(self, værdi):
        self.value1 = værdi

    @declared_attr
    def varighed(cls):
        """Varighed [timer]"""
        return synonym(
            "value1", descriptor=property(cls._get_varighed, cls._set_varighed)
        )


class KoordinatKovarians(Observation):
    """
    Kovariansmatrix for tidsseriekoordinat.

    Genereret i forbindelse med kombination af daglige koordinatløsninger til
    samlet koordinatløsning (= tidsseriekoordinaterne).

    Kovariansmatricen repræsenterer et estimat for varianser/kovarianser af
    den samlede koordinatløsning, dvs. af tidsseriekoordinaterne registreret
    i FIRE.

    Kovarianserne er baseret på geocentriske koordinater.
    """

    __mapper_args__ = {"polymorphic_identity": ObservationstypeID.koordinat_kovarians}

    def _get_xx(self):
        return self.value1

    def _set_xx(self, værdi):
        self.value1 = værdi

    @declared_attr
    def xx(cls):
        """Varians af koordinatens x-komponent [m^2]"""
        return synonym("value1", descriptor=property(cls._get_xx, cls._set_xx))

    def _get_xy(self):
        return self.value2

    def _set_xy(self, værdi):
        self.value2 = værdi

    @declared_attr
    def xy(cls):
        """Kovarians mellem koordinatens x- og y-komponent [m^2]"""
        return synonym("valu2", descriptor=property(cls._get_xy, cls._set_xy))

    def _get_xz(self):
        return self.value3

    def _set_xz(self, værdi):
        self.value3 = værdi

    @declared_attr
    def xz(cls):
        """Kovarians mellem koordinatens x- og z-komponent [m^2]"""
        return synonym("value3", descriptor=property(cls._get_xz, cls._set_xz))

    def _get_yy(self):
        return self.value4

    def _set_yy(self, værdi):
        self.value4 = værdi

    @declared_attr
    def yy(cls):
        """Varians af koordinatens y-komponent [m^2]"""
        return synonym("value4", descriptor=property(cls._get_yy, cls._set_yy))

    def _get_yz(self):
        return self.value5

    def _set_yz(self, værdi):
        self.value5 = værdi

    @declared_attr
    def yz(cls):
        """Kovarians mellem koordinatens y- og z-komponent [m^2]"""
        return synonym("value5", descriptor=property(cls._get_yz, cls._set_yz))

    def _get_zz(self):
        return self.value6

    def _set_zz(self, værdi):
        self.value6 = værdi

    @declared_attr
    def zz(cls):
        """Varians af koordinatens z-komponent [m^2]"""
        return synonym("value6", descriptor=property(cls._get_zz, cls._set_zz))


class ResidualKovarians(Observation):
    """
    Empirisk kovariansmatrix for daglige koordinatløsninger indgået i beregning
    af tidsseriekoordinater.

    Kovariansmatrix beregnet ud fra residualerne i mellem den samlede koordinatløsning
    (= tidsseriekoordinaterne) og de daglige koordinatløsninger, der er indgået i
    bestemmelsen af den samlede koordinatløsning. Ovennævnte residualer er genereret
    i forbindelse med kombination af daglige koordinatløsninger til samlet
    koordinatløsning. Kovariansmatricen repræsenterer et estimat for varians/kovarianser
    af de daglige koordinatløsninger.

    Kovarianserne er baseret på topocentriske koordinatresidualer.
    """

    __mapper_args__ = {"polymorphic_identity": ObservationstypeID.residual_kovarians}

    def _get_xx(self):
        # return Observation.__table__.c.get("value1", Column(Float, nullable=False))
        return self.value1

    def _set_xx(self, værdi):
        self.value1 = værdi

    @declared_attr
    def xx(cls):
        """Varians af residualer af daglige løsningerns x-komponenter [mm^2]"""
        return synonym("value1", descriptor=property(cls._get_xx, cls._set_xx))

    def _get_xy(self):
        return self.value2

    def _set_xy(self, værdi):
        self.value2 = værdi

    @declared_attr
    def xy(cls):
        """Kovarians mellem residualer af daglige løsningers x- og y-komponenter [mm^2]"""
        return synonym("valu2", descriptor=property(cls._get_xy, cls._set_xy))

    def _get_xz(self):
        return self.value3

    def _set_xz(self, værdi):
        self.value3 = værdi

    @declared_attr
    def xz(cls):
        """Kovarians mellem residualer af daglige løsningers x- og z-komponenter [mm^2]"""
        return synonym("value3", descriptor=property(cls._get_xz, cls._set_xz))

    def _get_yy(self):
        return self.value4

    def _set_yy(self, værdi):
        self.value4 = værdi

    @declared_attr
    def yy(cls):
        """Varians af residualer af daglige løsningerns y-komponenter [mm^2]"""
        return synonym("value4", descriptor=property(cls._get_yy, cls._set_yy))

    def _get_yz(self):
        return self.value5

    def _set_yz(self, værdi):
        self.value5 = værdi

    @declared_attr
    def yz(cls):
        """Kovarians mellem residualer af daglige løsningers y- og z-komponenter [mm^2]"""
        return synonym("value5", descriptor=property(cls._get_yz, cls._set_yz))

    def _get_zz(self):
        return self.value6

    def _set_zz(self, værdi):
        self.value6 = værdi

    @declared_attr
    def zz(cls):
        """Varians af residualer af daglige løsningers z-komponenter[mm^2]"""
        return synonym("value6", descriptor=property(cls._get_zz, cls._set_zz))
