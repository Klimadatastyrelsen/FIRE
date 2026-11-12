.. _kommandolinjeprogrammer_niv:

fire niv
##############

Arbejdsflow, beregning og analyse i forbindelse med nivellement.

Et almindeligt opmålingsprojekt er i :program:`fire niv` kommandogruppen
overordnet set brudt ned i følgende arbejdsskridt, givet ved
underkommandoerne::

    opret-sag
    udtræk-revision
    ilæg-revision
    ilæg-nye-punkter
    læs-observationer
    regn
    ilæg-observationer
    ilæg-nye-koter
    luk-sag

:program:`fire niv opret-sag` registrerer sagen (projektet) i databasen og skriver det regneark,
som bruges til at holde styr på arbejdet.

:program:`fire niv udtræk-revision` udtrækker oversigt over eksisterende punkter i et område,
til brug for punktrevision (herunder registrering af tabtgåede punkter).

:program:`fire niv ilæg-revision` lægger opdaterede og nye punktattributter i databasen
efter revision.

:program:`fire niv ilæg-nye-punkter` lægger oplysninger om nyoprettede punkter i databasen,
og tildeler bl.a. landsnumre til punkterne.

:program:`fire niv læs-observationer` læser råfilerne og skriver observationerne til regnearket
så de er klar til brug i beregninger.

:program:`fire niv udtræk-observationer` henter observationer ud af databasen på baggrund af
udvalgte søgekriterier og skrives til regnearket, så de kan bruges i beregninger.

:program:`fire niv regn` beregner nye koter til alle punkter, og genererer rapporter og
visualiseringsmateriale.

:program:`fire niv ilæg-observationer` lægger nye observationer i databasen.

:program:`fire niv ilæg-nye-koter` lægger nyberegnede koter i databasen.

:program:`fire niv luk-sag` arkiverer det afsluttende regneark og sætter sagens status til inaktiv.

:program:`fire niv åbn-sag` genåbner en ellers lukket sag.

Alle programmerne under :program:`fire niv` er bygget op om en "sag". En sag udgøres
i al sin enkelhed af et Excel-regneark. Dette regneark, som har samme navn som sagen,
registrerer al relevant information om en opmålingsopgave. Regnearket inddeles i
faneblade for at skabe et nemt overblik over de registrerede data, fx placeres
nivellementsobservationer i faneblandet "Observationer". I takt med at de forskellige
kommandoer afvikles udvides regnearket med flere faneblade med plads til information
om det enkelte trin i arbejdsgangen. Fanebladene beskrives i flere detaljer i
beskrivelse af :program:`fire niv`-kommandoerne herunder.

.. note::

    Til beregning af eksisterende observationer, findes en alternativ underkommando
    til :program:`fire niv læs-observationer`, kaldet :program:`fire niv udtræk-observationer`.
    En arbejdsgang med denne kommando kan se ud på følgende måde::

        opret-sag
        udtræk-observationer
        regn
        luk-sag

**Eksempel**

Her ses et eksempel på de kommandoer der typisk køres for en komplet
kommunal vedligeholdsopgave.

.. code-block:: console

    > fire niv opret-sag andeby_2020 "Vedligehold Andeby"
    > fire niv udtræk-revision andeby_2020 K-99 102-08
    > fire niv ilæg-revision andeby_2020
    > fire niv ilæg-nye-punkter andeby_2020
    > fire niv læs-observationer andeby_2020
    > fire niv regn andeby_2020
    > fire niv regn andeby_2020
    > fire niv ilæg-observationer andeby_2020
    > fire niv ilæg-nye-koter andeby_2020
    > fire niv luk-sag andeby_2020


.. note::

  Det er ikke nødvendigt at køre alle kommandoerne i forbindelse med en sag. Man kan
  for eksempel nøjes med at bruge revisionskommandoerne hvis der kun er behov for at
  ændre eller tilføje en attribut til et punkt. Se :ref:`tabsmelding` for et
  detaljeret eksempel.

.. note::
  Se :ref:`punktsamlinger` for hvordan du arbejde med tidsserier og punktsamlinger. For nærmere info om hvordan punktsamlinger og tidsserier hænger
  sammen på databaseniveau, se :ref:`tidsserier_og_punktsamlinger`.

.. click:: fire.cli.niv:opret_sag
  :prog: fire niv opret-sag
  :nested: full

.. _udtræk_revision:
.. click:: fire.cli.niv:udtræk_revision
  :prog: fire niv udtræk-revision
  :nested: full

.. _ilæg_revision:
.. click:: fire.cli.niv:ilæg_revision
  :prog: fire niv ilæg-revision
  :nested: full

.. _ilæg_nye_punkter:
.. click:: fire.cli.niv:ilæg_nye_punkter
  :prog: fire niv ilæg-nye-punkter
  :nested: full

.. click:: fire.cli.niv:læs_observationer
  :prog: fire niv læs-observationer
  :nested: full

.. click:: fire.cli.niv:udtræk_observationer
  :prog: fire niv udtræk-observationer
  :nested: full

.. click:: fire.cli.niv:regn
  :prog: fire niv regn
  :nested: full

.. click:: fire.cli.niv:netoversigt
  :prog: fire niv netoversigt
  :nested: full

.. click:: fire.cli.niv:ilæg_observationer
  :prog: fire niv ilæg-observationer
  :nested: full

.. click:: fire.cli.niv:ilæg_nye_koter
  :prog: fire niv ilæg-nye-koter
  :nested: full

.. click:: fire.cli.niv:luk_sag
  :prog: fire niv luk-sag
  :nested: full

.. click:: fire.cli.niv:åbn_sag
  :prog: fire niv åbn-sag
  :nested: full

.. click:: fire.cli.niv:opret_punktsamling
  :prog: fire niv opret-punktsamling
  :nested: full

.. click:: fire.cli.niv:udtræk_punktsamling
  :prog: fire niv udtræk-punktsamling
  :nested: full

.. click:: fire.cli.niv:ilæg_punktsamling
  :prog: fire niv ilæg-punktsamling
  :nested: full

.. click:: fire.cli.niv:ilæg_tidsserie
  :prog: fire niv ilæg-tidsserie
  :nested: full

.. click:: fire.cli.niv:fjern_punkt_fra_punktsamling
  :prog: fire niv fjern-punkt-fra-punktsamling
  :nested: full
