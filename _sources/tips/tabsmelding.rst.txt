.. _tabsmelding:

Tabsmelding af fikspunkter
---------------------------

Her vises hvordan et eller flere punkter tabsmeldes. Tabsmelding af fikspunkter gøres ved
brug af de samme værktøjer som bruges til revision af fikspunkter. Herunder beskrives
hvordan både i en hurtig version for den øvede bruger og en mere detaljeret version til
den knap så rutinerede bruger.

Den hurtige version
....................

.. code-block:: none

    > fire niv opret-sag <sagsnavn> "<sagsbeskrivelse>"
    > fire niv udtræk-revision <sagsnavn> <fikspunkt1> <fikspunkt2> ...

    # Åben regneark og tilføj linje med ATTR:tabtgået attribut for hvert tabtgået punkt

    > fire niv ilæg-revision <sagsnavn>
    > fire niv luk-sag <sagsnavn>

Den detaljerede version
........................

Start med at oprette en sag med ``fire niv opret-sag``. Giv den et passende navn og
en beskrivelse.

.. code-block:: none

    > fire niv opret-sag tabsmelding "Sag til tabsmelding af fikspunkter"
    Sags/projekt-navn: tabsmelding  (43c80625-3b73-4fc2-bf6b-8c658bf03321)
    Sagsbehandler:     b012349
    Beskrivelse:       Sag til tabsmelding af fikspunkter
    Opretter ny sag i test-databasen - er du sikker?  (ja/NEJ):
    ja
   Gentag svar for at bekræfte (ja/NEJ)
    ja
    Sag 'tabsmelding' oprettet
    Skriver sagsregneark 'tabsmelding.xlsx'
    Filen 'tabsmelding.xlsx' findes ikke.
    Skriver: {'Projektforside', 'Notater', 'Parametre', 'Nyetablerede punkter', 'Filoversigt', 'Sagsgang'}
    Til filen 'tabsmelding.xlsx'
    Færdig! - åbner regneark for check.

Udtræk punkter med ``fire niv udtræk-revision``.

.. code-block:: none

    >fire niv udtræk-revision tabsmelding 47-08-00813 47-08-00814
    Punkt: 47-08-00813
    Punkt: 47-08-00814
    Filen 'tabsmelding-revision.xlsx' findes ikke.
    Skriver: {'Revision'}
    Til filen 'tabsmelding-revision.xlsx'
    Færdig!

Vi har nu skabt revisionsarket ``tabsmelding-revision.xlsx``:

.. image:: images/tabsmelding1.png
    :alt: Revisionsark for punkterne 47-08-00813 47-08-00814

Tilføj en ``ATTR:tabtgået``-linje for hvert punkt der skal tabsmeldes:

.. image:: images/tabsmelding2.png
    :alt: Revisionsark med ``ATTR:tabtgået`` for begge punkter i arket

Gem og luk regnearket. Herefter kan ændringer lægges i databasen med
``fire niv ilæg-revision``:

.. code-block:: none

    > fire niv ilæg-revision tabsmelding
    Sags/projekt-navn: tabsmelding  (43c80625-3b73-4fc2-bf6b-8c658bf03321)
    Sagsbehandler:     b012349


    Behandler 2 punkter
    47-08-00813
        Opretter nyt punktinfo-element: ATTR:tabtgået
    47-08-00814
        Opretter nyt punktinfo-element: ATTR:tabtgået

    --------------------------------------------------
    Punkter færdigbehandlet, klar til at
    - oprette 2 attributter fordelt på 2 punkter
    - slukke for 0 attributter fordelt på 0 punkter
    - rette 0 attributter fordelt på 0 punkter
    - rette 0 lokationskoordinater
    Er du sikker på du vil indsætte ovenstående i prod-databasen (ja/NEJ):
    ja
    Gentag svar for at bekræfte (ja/NEJ)
    ja

Husk at lukke sagen igen med ``fire niv luk-sag``:

.. code-block:: none

    >fire niv luk-sag tabsmelding
    Er du sikker på at du vil lukke sagen tabsmelding? (ja/NEJ):
    ja
    Gentag svar for at bekræfte (ja/NEJ)
    ja
    Sag 43c80625-3b73-4fc2-bf6b-8c658bf03321 for 'tabsmelding' lukket!


.. tip::

    Hvis du ofte tabsmelder punkter kan du med fordel undlade at lukke sagen og genbruge
    den næste gang du har et punkt der skal meldes tabtgået.