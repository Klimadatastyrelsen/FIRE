import pytest
from click.testing import CliRunner

from fire.cli.main import (
    fire_cmd,
)

help = "--help"
enkelt_punkt = "RDIO"
ekstra_parms = '"GL  RDO1" -Kts,alle --monokrom'
multlinje_fil = """
RDIO
"GL  RDO1" -Kts,alle --monokrom
BLABLABLA
"""
med_kommentarer = """
RDIO
BLABLABLA
#Kommentarlinje
SKEJ -Oalle # -Kts,alle # udkommenteret tilvalg
"""

inputs = [
    help,
    enkelt_punkt,
    ekstra_parms,
    multlinje_fil,
    med_kommentarer,
]

obs_header = "--- Observationer ---"
koord_header = "--- Koordinater ---"
outputs = [
    ["Usage:", "Options:"],
    ["PUNKT RDIO"],
    ["PUNKT GL  RDO1", koord_header],
    ["Kunne ikke finde BLABLABLA"],
    ["PUNKT SKEJ", obs_header],
]
not_outputs =[
    [],
    [obs_header, koord_header],
    [obs_header],
    [],
    [koord_header],
]

@pytest.mark.parametrize(
    argnames="input, outputs, not_outputs",
    argvalues=list(zip(inputs, outputs, not_outputs)),
)
def test_interaktiv_fil_input(input: str, outputs: list[str], not_outputs: list[str]):
    """
    Test at interaktiv session kan modtage en fil der pipes ind
    """

    runner = CliRunner()

    result = runner.invoke(fire_cmd, ["info", "punkt", "-Kingen", "--interaktiv"], input=input)
    print(result.output)

    for out in outputs:
        assert out in result.output

    for not_out in not_outputs:
        assert not_out not in result.output

    # Forventer altid exit_code=1.
    # Når input slutter kommer en EOF som resulterer i at click printer "Aborted!" til stderr
    assert result.exit_code == 1
    assert result.stderr.strip() == "Aborted!"