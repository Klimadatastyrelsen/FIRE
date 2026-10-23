from __future__ import annotations
import enum
from typing import List, Union
import functools
import mimetypes
from pathlib import Path

from sqlalchemy import (
    Table,
    Column,
    String,
    Integer,
    Float,
    ForeignKey,
    Enum,
    LargeBinary,
    func,
)
from sqlalchemy.orm import relationship, reconstructor
from sqlalchemy.dialects.oracle import TIMESTAMP


import fire
from fire.api.model import (
    IntEnum,
    StringEnum,
    RegisteringTidObjekt,
    DeclarativeBase,
    columntypes,
    Boolean,
)

__all__ = [
    "FikspunktregisterObjekt",
    "Punkt",
    "PunktSamling",
    "Koordinat",
    "Artskode",
    "GeometriObjekt",
    "Beregning",
    "PunktInformation",
    "PunktInformationType",
    "PunktInformationTypeAnvendelse",
    "Srid",
    "Boolean",
    "Ident",
    "FikspunktsType",
    "Grafik",
    "GrafikType",
    "beregning_observation",
    "tidsserie_koordinat",
]


class PunktInformationTypeAnvendelse(enum.Enum):
    FLAG = "FLAG"
    TAL = "TAL"
    TEKST = "TEKST"


class Artskode(enum.Enum):
    """
    Uddybende beskrivelser fra REFGEO:

    artskode = 1 control point in fundamental network, first order.
    artskode = 2 control point in superior plane network.
    artskode = 2 control point in superior height network.
    artskode = 3 control point in network of high quality.
    artskode = 4 control point in network of lower or unknown quality.
    artskode = 5 coordinate computed on just a few measurements.
    artskode = 6 coordinate transformed from local or an not valid coordinate system.
    artskode = 7 coordinate computed on an not valid coordinate system, or system of unknown origin.
    artskode = 8 coordinate computed on few measurements, and on an not valid coordinate system.
    artskode = 9 location coordinate or location height.
    """

    FUNDAMENTAL_PUNKT = 1
    NETVAERK_AF_GOD_KVALITET = 2
    NETVAERK_AF_HOEJ_KVALITET = 3
    NETVAERK_AF_LAV_KVALITET = 4
    BESTEMT_FRA_FAA_OBSERVATIONER = 5
    TRANSFORMERET = 6
    UKENDT_KOORDINATSYSTEM = 7
    FAA_OBS_OG_UKENDT_KOORDINATSYSTEM = 8
    LOKATIONSKOORDINAT = 9
    NULL = None


class FikspunktsType(enum.Enum):
    GI = 1
    MV = 2
    HØJDE = 3
    JESSEN = 4
    HJÆLPEPUNKT = 5
    VANDSTANDSBRÆT = 6


class GrafikType(enum.Enum):
    SKITSE = "skitse"
    FOTO = "foto"


beregning_koordinat = Table(
    "beregning_koordinat",
    DeclarativeBase.metadata,
    Column("beregningobjektid", Integer, ForeignKey("beregning.objektid")),
    Column("koordinatobjektid", Integer, ForeignKey("koordinat.objektid")),
)


beregning_observation = Table(
    "beregning_observation",
    DeclarativeBase.metadata,
    Column("beregningobjektid", Integer, ForeignKey("beregning.objektid")),
    Column("observationobjektid", Integer, ForeignKey("observation.objektid")),
)

punktsamling_punkt = Table(
    "punktsamling_punkt",
    DeclarativeBase.metadata,
    Column("punktsamlingsid", Integer, ForeignKey("punktsamling.objektid")),
    Column("punktid", String, ForeignKey("punkt.id")),
)

tidsserie_koordinat = Table(
    "tidsserie_koordinat",
    DeclarativeBase.metadata,
    Column("tidsserieobjektid", Integer, ForeignKey("tidsserie.objektid")),
    Column("koordinatobjektid", Integer, ForeignKey("koordinat.objektid")),
)


class FikspunktregisterObjekt(RegisteringTidObjekt):
    __abstract__ = True


@functools.total_ordering
class Punkt(FikspunktregisterObjekt):
    __tablename__ = "punkt"
    id = Column(String, nullable=False, unique=True, default=fire.uuid)
    sagseventfraid = Column(String, ForeignKey("sagsevent.id"), nullable=False)
    sagsevent = relationship(
        "Sagsevent", foreign_keys=[sagseventfraid], back_populates="punkter"
    )
    sagseventtilid = Column(String, ForeignKey("sagsevent.id"), nullable=True)
    slettet = relationship(
        "Sagsevent", foreign_keys=[sagseventtilid], back_populates="punkter_slettede"
    )
    punktsamlinger = relationship(
        "PunktSamling",
        secondary=punktsamling_punkt,
        order_by="PunktSamling.objektid",
        viewonly=True,
    )
    koordinater = relationship(
        "Koordinat", order_by="Koordinat.objektid", back_populates="punkt"
    )
    tidsserier = relationship(
        "Tidsserie",
        order_by="Tidsserie.objektid",
        viewonly=True,
    )
    geometriobjekter = relationship(
        "GeometriObjekt",
        order_by="GeometriObjekt.objektid",
        back_populates="punkt",
    )
    punktinformationer = relationship(
        "PunktInformation",
        order_by="PunktInformation.objektid",
        back_populates="punkt",
        lazy="joined",
    )
    observationer_fra = relationship(
        "Observation",
        order_by="Observation.opstillingspunktid",
        back_populates="opstillingspunkt",
        foreign_keys="Observation.opstillingspunktid",
    )
    observationer_til = relationship(
        "Observation",
        order_by="Observation.sigtepunktid",
        back_populates="sigtepunkt",
        foreign_keys="Observation.sigtepunktid",
    )
    grafikker = relationship(
        "Grafik", order_by="Grafik.objektid", back_populates="punkt"
    )

    @reconstructor
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._identer: list[Ident] = []

    def _populer_identer(self):
        """
        Skab liste med ident-punktinformationer tilhørende punktet.
        """
        if not self._identer:
            temp = []
            for punktinfo in self.punktinformationer:
                if punktinfo.registreringtil:
                    continue
                if punktinfo.infotype.name.startswith("IDENT:") and punktinfo.tekst:
                    temp.append(Ident(punktinfo))

            # Tilføj kort uuid som bagstopper-ident
            if self.id:
                temp.append(Ident(self.id[0:8]))

            self._identer = sorted(temp)

    @property
    def geometri(self):
        try:
            return self.geometriobjekter[-1]
        except IndexError:
            return None

    @property
    def identer(self) -> List[str]:
        """
        Returner liste over alle identer der er tilknyttet Punktet
        """
        self._populer_identer()
        if self._identer:
            return [str(ident) for ident in self._identer if ident]
        return []

    @property
    def ident(self) -> str:
        """
        Udtræk det geodætisk mest læsbare ident.

        I nævnte rækkefølge:
            - IDENT:GI
            - IDENT:GNSS,
            - IDENT:landsr
            - IDENT:jessen
            - IDENT:station
            - IDENT:ekstern
            - IDENT:diverse
            - IDENT:refgeo_id.

        Hvis et punkt overhovedet ikke har noget ident returneres uuiden
        uforandret.
        """
        self._populer_identer()

        try:
            return str(self._identer[0])
        except (IndexError, TypeError):
            if self.id:
                return self.id[0:8]
            else:
                return None

    @property
    def tabtgået(self) -> bool:
        for punktinfo in self.punktinformationer:
            if (
                punktinfo.infotype.name == "ATTR:tabtgået"
                and punktinfo.registreringtil is None
            ):
                return True
        return False

    def _hent_ident_af_type(self, identtype: Ident.IdentType) -> str:
        self._populer_identer()
        numre = [ident.tekst for ident in self._identer if ident._type == identtype]

        if numre:
            return sorted(numre)[0]

        return None

    def gældende_koordinat(self, srid: str) -> Koordinat:
        """Hent gældende koordinat af typen ``srid``"""
        koordinatsæt = [
            k
            for k in self.koordinater
            if k.registreringtil is None
            and (k.srid.name == srid or k.srid.kortnavn == srid)
        ]
        if not koordinatsæt:
            return None

        return koordinatsæt[0]

    @property
    def landsnummer(self) -> str:
        _landsnummer = self._hent_ident_af_type(Ident.IdentType.LANDSNR)

        if _landsnummer:
            return _landsnummer

        return self.ident

    @property
    def gnss_navn(self) -> str:
        return self._hent_ident_af_type(Ident.IdentType.GNSS)

    @property
    def jessennummer(self) -> str:
        return self._hent_ident_af_type(Ident.IdentType.JESSEN)

    def __lt__(self, other: Punkt) -> bool:
        return self.landsnummer < other.landsnummer

    def __eq__(self, other: Punkt) -> bool:
        return self.landsnummer == other.landsnummer

    def __hash__(self) -> int:
        return hash(self.id)


class PunktSamling(FikspunktregisterObjekt):
    __tablename__ = "punktsamling"
    sagseventfraid = Column(String, ForeignKey("sagsevent.id"), nullable=False)
    sagsevent = relationship(
        "Sagsevent", foreign_keys=[sagseventfraid], back_populates="punktsamlinger"
    )
    sagseventtilid = Column(String, ForeignKey("sagsevent.id"), nullable=True)
    slettet = relationship(
        "Sagsevent",
        foreign_keys=[sagseventtilid],
        back_populates="punktsamlinger_slettede",
    )
    jessenpunktid = Column(String(36), ForeignKey("punkt.id"))
    jessenpunkt = relationship("Punkt")

    jessenkoordinatid = Column(Integer, ForeignKey("koordinat.objektid"))
    jessenkoordinat = relationship("Koordinat")

    navn = Column(String, nullable=False)
    formål = Column("formaal", String, nullable=False)

    punkter = relationship(
        "Punkt", secondary=punktsamling_punkt, back_populates="punktsamlinger"
    )

    tidsserier = relationship("Tidsserie", back_populates="punktsamling")

    @property
    def jessenkote(self) -> float:
        """
        Referencekoten for tidsserier tilknyttet punktsamlingen.

        Koten for en tilknyttet tidsserie fratrukket jessenkoten giver højden over
        jessenpunktet.
        Punktsamlinger som ikke har et jessenkoordinat, antages at have jessenkoten 0.
        """
        return self.jessenkoordinat.z if self.jessenkoordinat is not None else 0

    def tilføj_punkter(self, punkter: list[Punkt]) -> None:
        """
        Føj punkter til punktsamlingen.

        Ændrer punktsamlingens liste af punkter in-place. Hvis et eller flere punkter
        findes i punktsamlingen i forvejen udsendes en ValueError.
        """
        fællesmængde = set(punkter) & set(self.punkter)

        if len(fællesmængde) != 0:
            raise ValueError(
                f"Kan ikke tilføje et eller flere af de angivne punkter til Punktsamling '{self.navn}' da de allerede er indeholdt!"
            )
        self.punkter.extend(punkter)

    def fjern_punkter(self, punkter: list[Punkt]) -> None:
        """
        Fjern punkter fra punktsamlingen.

        Ændrer punktsamlingens liste af punkter in-place. Hvis et eller flere punkter ikke
        findes i punktsamlingen i forvejen udsendes en ValueError.
        """
        if self.jessenpunkt in punkter:
            raise ValueError(f"Kan ikke fjerne en punktsamlings jessenpunkt!")

        for p in punkter:
            self.punkter.remove(p)


class PunktInformation(FikspunktregisterObjekt):
    __tablename__ = "punktinfo"
    sagseventfraid = Column(String, ForeignKey("sagsevent.id"), nullable=False)
    sagsevent = relationship(
        "Sagsevent", foreign_keys=[sagseventfraid], back_populates="punktinformationer"
    )
    sagseventtilid = Column(String, ForeignKey("sagsevent.id"), nullable=True)
    slettet = relationship(
        "Sagsevent",
        foreign_keys=[sagseventtilid],
        back_populates="punktinformationer_slettede",
    )
    infotypeid = Column(Integer, ForeignKey("punktinfotype.infotypeid"), nullable=False)
    infotype = relationship("PunktInformationType", lazy="joined")
    tal = Column(Float)
    tekst = Column(String(4000))
    punktid = Column(String(36), ForeignKey("punkt.id"), nullable=False)
    punkt = relationship("Punkt", back_populates="punktinformationer")


@functools.total_ordering
class Ident:
    class IdentType(enum.Enum):
        GI = 1
        GNSS = 2
        LANDSNR = 3
        JESSEN = 4
        STATION = 5
        EKSTERN = 6
        DIVERSE = 7
        REFGEO = 8
        UKENDT = 9
        KORTUUID = 10

    def __init__(self, punktinfo: Union[PunktInformation, str]):
        if isinstance(punktinfo, PunktInformation):
            if not punktinfo.infotype.name.startswith("IDENT:"):
                raise ValueError("punktinfo indeholder ikke en ident")

            self.variant = punktinfo.infotype.name
            self.tekst = punktinfo.tekst
        else:
            # Vi antager der er spyttet et kort uuid ind
            self.variant = "kortuuid"
            self.tekst = punktinfo

    def __lt__(self, other: Ident):
        """
        Bruges til at sortere identer med sorted().

        IdentType definerer rangordenen blandt de forskellige typer identer.
        """
        # jo lavere værdi, des bedre ident
        if self._type.value == other._type.value:
            # hvis samme type, sammenligner vi på selve identen istedet
            if self.tekst < other.tekst:
                return True
            else:
                return False

        if self._type.value < other._type.value:
            return True
        else:
            return False

    def __eq__(self, other: Ident):
        return self.tekst == str(other)

    def __str__(self):
        return self.tekst

    def __repr__(self):
        return f"{self.__class__.__name__}<{self.variant}: {self.tekst}>"

    @property
    def _type(self) -> IdentType:
        if self.variant == "IDENT:GI":
            return self.IdentType.GI
        if self.variant == "IDENT:GNSS":
            return self.IdentType.GNSS
        if self.variant == "IDENT:landsnr":
            return self.IdentType.LANDSNR
        if self.variant == "IDENT:jessen":
            return self.IdentType.JESSEN
        if self.variant == "IDENT:station":
            return self.IdentType.STATION
        if self.variant == "IDENT:ekstern":
            return self.IdentType.EKSTERN
        if self.variant == "IDENT:diverse":
            return self.IdentType.DIVERSE
        if self.variant == "IDENT:refgeo_id":
            return self.IdentType.REFGEO
        if self.variant == "kortuuid":
            return self.IdentType.KORTUUID

        return self.IdentType.UKENDT


class PunktInformationType(DeclarativeBase):
    __tablename__ = "punktinfotype"
    objektid = Column(Integer, primary_key=True)
    infotypeid = Column(Integer, unique=True, nullable=False)
    name = Column("infotype", String(4000), nullable=False)
    anvendelse = Column(Enum(PunktInformationTypeAnvendelse), nullable=False)
    beskrivelse = Column(String(4000), nullable=False)


class Koordinat(FikspunktregisterObjekt):
    __tablename__ = "koordinat"
    sridid = Column(Integer, ForeignKey("sridtype.sridid"), nullable=False)
    srid = relationship("Srid", lazy="selectin")
    sx = Column(Float)
    sy = Column(Float)
    sz = Column(Float)
    t = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    transformeret = Column(StringEnum(Boolean), nullable=False, default=Boolean.FALSE)
    _fejlmeldt = Column(
        "fejlmeldt", StringEnum(Boolean), nullable=False, default=Boolean.FALSE
    )
    artskode = Column(IntEnum(Artskode), nullable=True, default=Artskode.NULL)
    x = Column(Float)
    y = Column(Float)
    z = Column(Float)
    sagseventfraid = Column(String, ForeignKey("sagsevent.id"), nullable=False)
    sagsevent = relationship(
        "Sagsevent", foreign_keys=[sagseventfraid], back_populates="koordinater"
    )
    sagseventtilid = Column(String, ForeignKey("sagsevent.id"), nullable=True)
    slettet = relationship(
        "Sagsevent",
        foreign_keys=[sagseventtilid],
        back_populates="koordinater_slettede",
    )

    punktid = Column(String(36), ForeignKey("punkt.id"), nullable=False)
    punkt = relationship("Punkt", back_populates="koordinater")
    beregninger = relationship(
        "Beregning", secondary=beregning_koordinat, back_populates="koordinater"
    )

    tidsserier = relationship(
        "Tidsserie",
        order_by="Tidsserie.objektid",
        viewonly=True,
        secondary=tidsserie_koordinat,
    )

    @property
    def fejlmeldt(self):
        return self._fejlmeldt == Boolean.TRUE

    @fejlmeldt.setter
    def fejlmeldt(self, value: Boolean):
        if value:
            self._fejlmeldt = Boolean.TRUE
        else:
            self._fejlmeldt = Boolean.FALSE

    @property
    def beregning(self):
        """Returner beregning der ligger til grund for koordinaten."""

        # En koordinat kan ikke skabes ud fra flere beregninger så vi antager
        # at den første i listen er den rigtige (og at der ikke er flere)
        try:
            return self.beregninger[0]
        except IndexError:
            return None

    @functools.cached_property
    def observationer(self):
        """Returner alle observationer der direkte har bidraget til en koordinat."""
        return [
            obs
            for obs in self.beregning.observationer
            if obs.opstillingspunktid == self.punktid
            or obs.sigtepunktid == self.punktid
        ]


class GeometriObjekt(FikspunktregisterObjekt):
    __tablename__ = "geometriobjekt"
    geometri = Column(columntypes.Point(2, 4326), nullable=False)
    sagseventfraid = Column(String, ForeignKey("sagsevent.id"), nullable=False)
    sagsevent = relationship(
        "Sagsevent", foreign_keys=[sagseventfraid], back_populates="geometriobjekter"
    )
    sagseventtilid = Column(String, ForeignKey("sagsevent.id"), nullable=True)
    slettet = relationship(
        "Sagsevent",
        foreign_keys=[sagseventtilid],
        back_populates="geometriobjekter_slettede",
    )
    punktid = Column(String(36), ForeignKey("punkt.id"), nullable=False)
    punkt = relationship("Punkt", back_populates="geometriobjekter")

    @property
    def koordinater(self):
        return self.geometri.__geo_interface__["coordinates"]


class Beregning(FikspunktregisterObjekt):
    __tablename__ = "beregning"
    objektid = Column(Integer, primary_key=True)
    sagseventfraid = Column(String, ForeignKey("sagsevent.id"), nullable=False)
    sagsevent = relationship(
        "Sagsevent", foreign_keys=[sagseventfraid], back_populates="beregninger"
    )
    sagseventtilid = Column(String, ForeignKey("sagsevent.id"), nullable=True)
    slettet = relationship(
        "Sagsevent",
        foreign_keys=[sagseventtilid],
        back_populates="beregninger_slettede",
    )
    koordinater = relationship(
        "Koordinat", secondary=beregning_koordinat, back_populates="beregninger"
    )
    observationer = relationship(
        "Observation", secondary=beregning_observation, back_populates="beregninger"
    )


class Srid(DeclarativeBase):
    __tablename__ = "sridtype"
    objektid = Column(Integer, primary_key=True)
    sridid = Column(Integer, unique=True, nullable=False)
    name = Column("srid", String(36), nullable=False, unique=True)
    kortnavn = Column("kortnavn", String(36), nullable=True, unique=False)
    beskrivelse = Column(String(4000))
    x = Column(String(4000))
    y = Column(String(4000))
    z = Column(String(4000))


class Grafik(FikspunktregisterObjekt):
    __tablename__ = "grafik"
    sagseventfraid = Column(String, ForeignKey("sagsevent.id"), nullable=False)
    sagsevent = relationship(
        "Sagsevent", foreign_keys=[sagseventfraid], back_populates="grafikker"
    )
    sagseventtilid = Column(String, ForeignKey("sagsevent.id"), nullable=True)
    slettet = relationship(
        "Sagsevent",
        foreign_keys=[sagseventtilid],
        back_populates="grafikker_slettede",
    )

    objektid = Column(Integer, primary_key=True)
    grafik = Column(LargeBinary, nullable=False)
    type = Column(StringEnum(GrafikType), nullable=False)
    mimetype = Column(String(3), nullable=False)
    filnavn = Column(String(100), nullable=False)
    punktid = Column(String(36), ForeignKey("punkt.id"), nullable=False)
    punkt = relationship("Punkt", back_populates="grafikker")

    @classmethod
    def fra_fil(cls, punkt: Punkt, sti: Path):
        """Opret Grafik ud fra en billedfil."""
        with open(sti, "rb") as f:
            blob = f.read()

        (mimetype, _) = mimetypes.guess_type(sti)
        if mimetype not in ("image/png", "image/jpeg"):
            raise ValueError(
                f"Filen {sti} kan ikke læses, forkert MIME type: {mimetype}"
            )
        # antag at en png-fil er en skitse
        if mimetype == "image/png":
            grafiktype = GrafikType.SKITSE.value
        else:
            grafiktype = GrafikType.FOTO.value

        filnavn = sti.name

        return cls(
            punkt=punkt,
            grafik=blob,
            type=grafiktype,
            mimetype=mimetype,
            filnavn=filnavn,
        )
