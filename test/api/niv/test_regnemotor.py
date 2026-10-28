from datetime import datetime
from pathlib import Path

import numpy as np

from fire.api.niv.regnemotor import (
    RegneMotor,
    GamaRegn,
    StandardRegn,
)
from fire.cli.niv import (
    find_faneblad,
)
from fire.api.niv.datatyper import (
    NivKote,
    NivObservation,
)
from fire.io.regneark import arkdef


def test_fra_dataframe(tmp_path: Path):
    """Tester at man kan instantiere et RegneMotor objekt via dataframes"""

    filename = "test_regn.xlsx"
    projektnavn = tmp_path / Path("test_regn")

    with open(Path(__file__).resolve().parents[2] / "niv" / filename, "rb") as f:
        filedata = f.read()

    # kopier filer til isoleret filsystem
    with open(tmp_path / filename, "wb") as f:
        f.write(filedata)

    observationer = find_faneblad(projektnavn, "Observationer", arkdef.OBSERVATIONER)
    punktoversigt = find_faneblad(projektnavn, "Punktoversigt", arkdef.PUNKTOVERSIGT)

    # Test at en regnemotor kan instantieres ud fra en dataframe
    motor = GamaRegn.fra_dataframe(
        observationer, punktoversigt, projektnavn=projektnavn
    )

    assert isinstance(motor, RegneMotor)

    # Test motorens forskellige attributter
    assert len(motor.observationer) == len(observationer)
    assert len(motor.gamle_koter) == len(punktoversigt)
    assert len(motor.fastholdte) == sum(punktoversigt["Fasthold"] != "")


def test_StandardRegn():
    """Test metoderne i StandardRegn

    Som testdatasæt opstilles et nivellement-netværk som dette:

    A ------ B ------ E ------ F
    |        |
    |        |
    D ------ C

    hvor punkt A og D begge er fastholdte, og der er self-loops
    ved punkt C og E.
    """

    almindelige_observationer = [
        ["A", "B", 1.1],
        ["B", "A", -1.0],
        ["B", "C", 2.1],
        ["C", "B", -2.0],
        ["C", "D", 3.1],
        ["D", "C", -3.0],
        ["B", "E", 2.5],
        ["E", "B", -2.4],
        ["E", "F", 1.3],
        ["F", "E", -1.2],
    ]

    self_loops = [
        ["C", "C", 0.01],
        ["E", "E", -0.02],
    ]

    fastholdte_observationer = [
        ["D", "A", -6],
        ["A", "D", 5.7],
    ]

    fastholdte = [
        NivKote("A", 0, None, 0.005, True),
        NivKote("D", -5.8, None, 0.005, True),
    ]

    # Opret observationer
    observationer = [
        NivObservation(
            o[0],  # fra
            o[1],  # til
            datetime(2026, 1, 1),
            None,
            1,  # afstand
            o[2],  # delta H
            1,  # spredning
            None,
        )
        for o in almindelige_observationer + self_loops + fastholdte_observationer
    ]

    # start regnemotor
    motor = StandardRegn(observationer=observationer, gamle_koter=fastholdte)

    # Kør netanalysen, som er påkrævet inden man kan komme videre
    net_uden_ensomme, ensomme_subnet, estimerbare_punkter = motor.netanalyse()

    X, Y, W = motor._opstil_ligningssystem(
        skip_self_loops=False,
        skip_fastholdte_obs=False,
    )

    # Alle observationer skulle gerne være inkluderet
    assert len(Y) == len(observationer)

    # Observationers spredning er 1, så vægtmatricen skal gerne være lig identitetsmatricen
    assert (W.shape[0] == W.shape[1]) and (W == np.eye(W.shape[0])).all()

    # Kontrollér at systemmatricen er opstillet korrekt ved at tjekke summen af rækkerne,
    # idet de fleste burde se ud som fx [0  0  -1  1]  og dermed summe til 0.
    # Det er kun de 4 observationer mellem A-B og C-D hvor summen ikke burde være 0.
    rækkesummer = X.sum(axis=1)

    assert sum(rækkesummer == 0) == len(observationer) - 4
    assert sum(rækkesummer == -1) == 2
    assert sum(rækkesummer == 1) == 2

    # Alle punkter brugt lige mange gange som opstillings- og sigtepunkt.
    # Derfor bør alle kolonnesummerne være 0.
    kolonnesummer = X.sum(axis=0)
    assert all(kolonnesummer == 0)

    # Opstil ligningssystem hvor de 2 selfloops skippes.
    X, Y, W = motor._opstil_ligningssystem(
        skip_self_loops=True,
        skip_fastholdte_obs=False,
    )
    assert len(Y) == len(observationer) - 2

    # Opstil ligningssystem hvor både de 2 selfloops og de 2 fastholdte observationer skippes.
    X, Y, W = motor._opstil_ligningssystem(
        skip_self_loops=True,
        skip_fastholdte_obs=True,
    )
    assert len(Y) == len(observationer) - 4

    # Udjævn
    nye_koter = motor._løs_ligningssystem(X, Y, W)

    # Tjek at der er nye koter for de 4 punkter B,C,E,F
    assert len(nye_koter) == 4
    assert {nk.punkt for nk in nye_koter} == {"B", "C", "E", "F"}

    # Tjek at statistiktabeller kan genereres uden fejl.
    motor._generer_statistik()
