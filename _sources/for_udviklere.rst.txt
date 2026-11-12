.. _for_udviklere:

Udviklingsguide
=======================

Denne side indeholder alverdens information der er relevant for dem der arbejder
på kildekoden bag FIRE.

Opsætning
----------

.. note::

    Alt herunder forudsætter at det foretages i en Conda terminal og at
    Oracle Instantclient er installeret. Se
    :ref:`installationsvejledningen <installation>` for mere om Conda og
    Oracle Instantclient.

Start med at clone git repositoriet::

    > git clone https://github.com/Kortforsyningen/FIRE.git

Et godt udviklingsmiljø at tage udgangspunkt i er `environment-dev.yaml`, som nemt
installeres med Conda. Fra fire git-repositoriet køres::

    > conda env create --file environment-dev.yml
    > conda activate fire-dev

Herefter burde alle de essentielle programmer og biblioteker være til rådighed.

Installer en udviklingsversion af fire med::

    > pip install -e .

og installer git hooks::

    > pre-commit install


.. note::

    ``pre-commit`` bruges til at afvikle forskellige "hooks"  inden et git commit.
    ``pre-commit`` *kan* blive forvirret over SIT's noget aparte valg af ``%HOME%``
    på ``H:\`` hvorfor det anbefales at sætte ``%PRE_COMMIT_HOME%`` som en global
    miljøvariabel der peger på ``C:\Users\bxxxxx\.cache\pre-commit``. Søg efter
    "Rediger miljøvariabler for din konto" i startmenuen.



Test-suiten køres med::

    > pytest

.. warning::

    Test-suiten kræver adgang til en Oracle database hvor DDL og testdata er
    indlæst. Normalvis er det ikke tilfældet på SIT arbejdsstationer hvorfor
    tests som udgangspunkt ikke kan afvikles lokalt. Test-suiten kører automatisk
    på pull requests mod https://github.com/Kortforsyningen/FIRE.

    Se :ref:`testlokalt` for mere om hvordan et testmiljø kan sættes op lokalt.

For at test-suiten kører korrekt skal der i ``fire.ini`` indsættes en ``[test_connection]``
sektion::

    [test_connection]
    password = <adgangskode>
    username = <brugernavn>
    hostname = <netværksadresse>
    database = <databasenavn>
    service = <servicenavn>

På maskiner der både arbejder op mod produktions- og testdatabase er det vigtigt at
``[test_connection]`` er forskellig fra ``[connection]``, da det ellers risikeres at der
indsættes ugyldigt data i produktionsdatabasen.

Kodestil
--------

`fire` kommandoen taler dansk til brugeren. Dokumentation
skrives ligeledes på dansk. Det er tilladt at skrive kommentarer, funktions- og
variabelnavne på engelsk. git commits bør så vidt muligt skrives på dansk.

Al kode i fire repositoriet skal køres automatisk gennem ``black`` via et git
pre-commit hook inden det committes. Dette gøres for at skabe et ensartet udtryk
på tværs af hele kodebasen. Desuden har black den bivirking at forstyrrende,
overflødige ændringer typisk forsvinder fra diffs mellem to commits, hvilket gør
det væsentligt nemmere at lave review af kodeændringer.

Underkommandoernes modulnavne starter med `_` for at undgå navnekonflikter med
click-kommando-objekter.

Eksempel: Det betyder, at man for entydigt at kunne kende forskel på modulet
``fire.cli.niv._opret-sag`` og Click-kommandoobjektet ``fire.cli.niv.opret-sag``
skal have ovennævnte præfiks i modulnavnet, så funktionen (og dermed Click-
kommandoen) i modulet kan få det ønskede navn.


Dokumentation
-------------

HTML dokumentation kan genereres lokalt ved hjælp af følgende kommando::

    sphinx-build -b html ./docs ./docs/_build -E

hvorefter dokumentationen vil være at finde i ``docs/_build``.

Det er muligt at Sphinx ikke kan finde `graphviz` (fx relevant på :ref:`datamodel`), i så
fald kan placeringen til denne angives som følger::

    sphinx-build -b html -D graphviz_dot=C:\Users\<USERNAME>\AppData\Local\Continuum\miniconda3\envs\fire-dev\Library\bin\graphviz\dot.exe ./docs ./docs/_build

Når der tilføjes eller fjernes moduler til API koden skal dokumentationen
opdateres (filer i ``docs/api``). Dette kan gøres med::

    sphinx-apidoc -E -d 3 -o docs\api fire

Samspil mellem Click og Sphinx
+++++++++++++++++++++++++++++++

Sphinx er sat op til at bruge modulet ``sphinx_click``, der gør det muligt at
auto-genere dokumentation af click kommandolinje programmer. Dette udnyttes i
høj grad i FIRE programmerne. Brugen af ``sphinx_click`` gør det muligt skrive
et programs dokumentation udelukkende i docstring af programmets click entry-point
funktion. Se fx ``fire.cli.niv:regn``. Et par forhold er værd at notere sig når
sphinx-dokumentationen skrives direkte i docstring:

1. Alt efter ``\f`` medtages ikke i hjælpteksten på kommandolinjen
2. Man kan bruge ``\b`` til at undgå at click omformatere tekst i hjælpteksten på kommandolinjen
3. Man kan sagtens benytte sig af alle formateringsmulighederne i Sphinx, dog vil nogle elementer
   kun virke hvis de kommer efter ``\f``. Formodentligt fordi click ellers ombryder teksten.
4. Undlad almindelige RST-overskrifter i docstrings, da de forplumrer indholdsfortegnelsen.
   Underoverskrifter kan laves med ``**fed**`` i stedet.

GitHub og Continuous Integration
---------------------------------

Fire repositoriet håndteres på GitHub, hvor der er sat en række Continous
Integration (CI) services op. Disse benyttes blandt andet til at afvikle test
suiten og til at generere HTML dokumentation efter hvert commit.

GitHub er konfigureret sådan at man ikke kan lave ``git push`` direkte til ``master``.
For at inkludere kode i ``master`` kræves det at man laver et pull request med mindst
et godkendt review fra en kollega, samt at alle CI tests gennemføres successfuldt.


.. _testlokalt:

Lokalt testmiljø
----------------

Forudsat du har Docker og nogle Oracle-værktøjer (instaclient og SQLplus) installeret
er det muligt at sætte en lokal testdatabase op. Fra roden af repositoryet
køres::

    > ./scripts/init-db.sh

Først gang kommandoen køres downloades en række Docker images. Det tager sin tid, så
vær tålmodig.

Kopier `ci`-opsætningen fra filen ``test/ci/fire.ini`` til din lokale `fire.ini` i din
:envvar:`HOME`-mappe. Hvis Docker-billedet afvikles på en server skal `hostname` rettes
til i under `ci`-opsætningen. Herefter burde det være muligt at køre test-suiten.
