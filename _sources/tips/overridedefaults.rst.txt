.. _overridedefaults:

Angivelse af nye default værdier
--------------------------------

.. note::

    *Bemærk, at for at vælge default databaseforbindelse, skal* :ref:`konfigurationsfilen
    <konfigurationsfil>` *anvendes.*


FIRE-kommandoerne har mange parametre som kan slås til eller fra. Hvis man er utilfreds
med de gængse default-værdier for parametrene, er det muligt at overskrive dem ved at
sætte en miljøvariabel for den givne parameter.

Angivelse af nye defaults er fx nyttigt, hvis man generelt gerne vil have alt tilgængelig
information om et fikspunkt ud. Normalt kræver det at man skriver flg. hver gang:

.. code-block:: none

    fire info punkt -DHO alle -K ts,alle <IDENT>

I stedet kan man nu sætte:

.. code-block:: none

    set FIRE_INFO_PUNKT_DETALJERET=True
    set FIRE_INFO_PUNKT_HISTORIK=True
    set FIRE_INFO_PUNKT_OBS=alle
    set FIRE_INFO_PUNKT_KOORD=ts,alle

Herefter vil alle kald til ``fire info punkt`` have disse parameterværdier sat som
default. Som det fremgår, så angives booleanske værdier med ``True / False``.

Miljøvariablens navn følger det samme mønster for alle kommandoer; Kommandoens navn (med
underscore ``_`` imellem), efterfulgt at den valgte parameters navn. Bindestreg i
kommando-navne erstattes af underscore. Dvs. at ``fire ts plot-gnss`` bliver til
``FIRE_TS_PLOT_GNSS_<PARAMETERNAVN>``.

.. note::

    Bemærk at det skal være parameterens "lange" navn der bruges. I ovenstående eksempel
    er det altså ``DETALJERET`` der skal bruges og ikke det korte navn ``D``. Alle kommandoer har
    en ``--help`` parameter der viser en liste over mulige parametre, inkl. deres lange og
    korte navne.

.. note::

    Bemærk også, at parametre indstilles pr. kommando, så kommandoer med identiske
    parametre skal sættes hver for sig. Fx findes parameteren ``--plottype`` på både
    ``fire ts plot-gnss`` og ``fire ts plot-hts``, som altså skal sættes hver for sig:

    .. code-block:: none

        set FIRE_TS_PLOT_GNSS_PLOTTYPE=fit
        set FIRE_TS_PLOT_HTS_PLOTTYPE=fit

Miljøvariablerne vil imidlertid blive glemt når man lukker sit terminalvindue. Derfor kan
det være en fordel at knytte denne opsætning til sit FIRE-miljø. Dette gøres med:

.. code-block:: none

    mamba activate fire
    mamba env config vars set FIRE_INFO_PUNKT_DETALJERET=True
    mamba env config vars set FIRE_INFO_PUNKT_HISTORIK=True
    mamba env config vars set FIRE_INFO_PUNKT_OBS=alle
    mamba env config vars set FIRE_INFO_PUNKT_KOORD=ts,alle
    mamba deactivate
    mamba activate fire

Hver gang man aktiverer sit FIRE-miljø, vil de viste miljøvariable nu være sat. For at få vist de
aktuelt satte miljøvariable og deres værdier skrives:

.. code-block:: none

    mamba env config vars list

Ønsker man at gå tilbage til de oprindelige defaults, kan de fjernes fra miljøet med:

.. code-block:: none

    mamba activate fire
    mamba env config vars unset FIRE_INFO_PUNKT_DETALJERET
    mamba env config vars unset FIRE_INFO_PUNKT_HISTORIK
    mamba env config vars unset FIRE_INFO_PUNKT_OBS
    mamba env config vars unset FIRE_INFO_PUNKT_KOORD
    mamba deactivate
    mamba activate fire
