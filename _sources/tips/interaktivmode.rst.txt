.. _interaktivmode:

Anvendelse af interaktiv mode
-----------------------------

FIRE kan desværre være lidt sløv til at starte op, hvilket skyldes den efterhånden
store kodebase som skal initieres på ny — vel at mærke hver gang en kommando køres.

Som et forsøg på at afhjælpe dette, er der lavet mulighed for at starte en hvilken som
helst FIRE-kommando op i en "interaktiv" session.

Dette har dén fordel, at kodebasen kun skal initieres én gang når den interaktive session
startes op. Derefter kan kommandoen køres gentagne gange uden at FIRE skal initieres hver
gang.

Den primære use-case for dette er, hvis man sidder og kører den samme kommando mange gange
i træk. Eksempelvis ved gentage punktopslag med ``fire info punkt``.

En anden nyttig ting dette tillader er også, at man (*endelig!*) kan lave visse former for
shell-scripting med FIRE-kommandoer. Eksempel på dette er udtræk af punktinfo for en liste
af punkter som man har i en tekstfil.

Interaktiv mode slås til med flaget ``--interaktiv`` eller ``-I`` og kan bruges på alle
FIRE-kommandoer. Man forlader den interaktive session med ``CTRL+C`` eller ``CTRL+Z+ENTER``.

Almindelig brug af interaktiv mode
==================================

Man mødes af en prompt med kommandoens almindelige signatur allerede
udfyldt, fx:

.. code-block:: none

    >>fire info punkt -I

    Starter interaktiv session for 'fire info punkt'

    Afbryd med CTRL+C eller CTRL+Z+ENTER

    fire info punkt [IDENT]
        ... alm. punktinfo

    fire info punkt [IDENT -H]
        ... punktinfo med historik

hvor teksten inden for [*parentesen*] er brugerens input til prompten. Kommandoen tager
imod de samme options som den normale, ikke-interaktive version.

Man kan fastholde kommandoens øvrige parametre i den interaktive session ved at angive dem
ved opstart. De fastholdte værdier kan altid ændres ved angivelse af andre værdier senere i
sessionen:

.. code-block:: none

    >>fire info punkt --db prod -H -I

    Starter interaktiv session for 'fire info punkt'
    med flg. fastsatte argumenter:
    db=prod
    historik=True

    Afbryd med CTRL+C eller CTRL+Z+ENTER

    fire info punkt [IDENT]
        ... punktinfo med historik, trukket fra prod

    fire info punkt [IDENT --db test]
        ... punktinfo med historik, trukket fra test

    fire info punkt [IDENT -O alle]
        ... punktinfo med historik og observationer, trukket fra prod

.. note::

    Det er vigtigt, at interaktiv-flaget ``-I`` vælges som det sidste på kommandolinjen.
    Options som kommer bagefter, vil ikke blive registreret som fastholdte. Fx

    .. code-block:: none

        fire info punkt --db prod -I -H

        Starter interaktiv session for 'fire info punkt'
        med flg. fastsatte argumenter:
        db=prod

        Afbryd med CTRL+C eller CTRL+Z+ENTER

    vil kun fastholde ``db=prod``, mens historik-flaget ``-H`` vil blive ignoreret.

Shell-scripting ved brug af interaktiv mode
===========================================

Interaktiv mode kan også bruges til at lave fancy shell-scripting hvor fx en tekstfil
pipes ind i en FIRE-kommando. Dette kan bruges til fx at trække mange punktinfos ud på een
gang.

Havelåge ("#") kan anvendes som kommentar-tegn i inputfil, både i starten af linjen og
in-line. Eksempelvis (ved brug af windows-terminal)

.. code-block:: none

    # Klargør en fil med identer der skal søges på
    echo GM901 >> punkter.txt
    echo GM902 >> punkter.txt
    echo # GM902 en linje der helt springes over >> punkter.txt
    echo RDIO # en in-line kommentar >> punkter.txt

    # Smid filen ind i fire info punkt og skriv resultat til terminalen
    fire info punkt --db prod -I < punkter.txt

    # Træk også historik og detaljer ud, og gem i stedet resultaterne i en fil
    fire info punkt --db prod -I < punkter.txt > infopunkt_out.txt

    # Ryd op
    rm punkter.txt infopunkt_out.txt
