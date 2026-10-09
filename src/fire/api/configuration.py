import os
from pathlib import Path
import getpass
from configparser import ConfigParser


RC_NAME = "fire.ini"

HOME = Path(os.environ.get("HOME", ""))
ETC = Path("/etc")
USERS = Path("C:\\Users")
APPDATADIR = Path("C:\\Users\\Default\\AppData\\Local\\fire")

RC_PATHS = (
    lambda: HOME / RC_NAME,
    lambda: HOME / ("." + RC_NAME),
    lambda: ETC / RC_NAME,
    lambda: USERS / getpass.getuser() / RC_NAME,
    lambda: APPDATADIR / RC_NAME,
)

RC_DEFAULTS = {
    "general": {
        "default_connection": "prod",
        "niv_open_files": "true",
        "monochrome": "false",
    },
}


def get_config_path() -> Path:
    """Returnér første eksisterende konfigurationsfil"""
    for get_fname in RC_PATHS:
        fname = get_fname()
        if fname.is_file():
            return fname
    else:
        raise EnvironmentError("Konfigurationsfil ikke fundet!")


def get_configuration() -> ConfigParser:
    """Returnér parser instans med bruger- og standardvalg til indstillingerne."""
    parser = ConfigParser()
    parser.read_dict(RC_DEFAULTS)
    parser.read(get_config_path())
    return parser
