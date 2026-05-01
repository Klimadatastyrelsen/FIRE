from enum import Enum
from dataclasses import dataclass
from datetime import datetime


# Type hints som bruges i api.niv undermodulerne
PunktNavn = str
# NivSubnet er en forsimplet udgave af et rigtigt net, som bare indeholder navnene på punkter som indgår
NivSubnet = list[PunktNavn]
NivNet = dict[PunktNavn, set[PunktNavn]]


class NivMetode(Enum):
    MGL = 1
    MotoriseretGeometriskNivellement = 1
    MTL = 2
    MotoriseretTrigonometriskNivellement = 2


class Nøjagtighed(Enum):
    P = 1
    Præcision = 1
    K = 2
    Kvalitet = 2
    D = 3
    Detail = 3
    U = 9
    Ukendt = 9


@dataclass
class NivObservation:
    """Almindelige nivellementosbservationer"""

    fra: PunktNavn
    til: PunktNavn
    dato: datetime
    multiplicitet: int
    afstand: float
    deltaH: float
    spredning: float
    id: str  # kan bruges til journalnummeret, eller observations-id fra FIRE


@dataclass
class NivKote:
    """Koter som enten indgår som input eller output til en beregning"""

    punkt: PunktNavn  # kan både bruge ident, database id, eller uuid.
    H: float
    dato: datetime
    spredning: float
    fasthold: bool = False
    nord: float = float("nan")
    øst: float = float("nan")


@dataclass
class HeightDiffCorrections:
    """Geodetic corrections of a height difference/levelling observation."""

    tidal_corr: float = 0  # Tidal correction in units of meters
    epoch_corr: float = 0  # Epoch correction in units of meters
    m2gpu_factor: float = 1  # m2gpu multiplication factor in units of m/s^2
