"""
Kommandoliniebrugergrænsefladen (en command-line interface, CLI) til FIREs API.

"""

import sys
import os
import signal

import click
import rich.traceback
import sqlalchemy

from fire.api import FireDb

# Pæne tracebacks med relevant debug info. Udelader output fra pakker
# spytter exceptionelt meget (irrellevant) output ud ved fejl
rich.traceback.install(show_locals=True, suppress=[click, sqlalchemy])


# Undgå enorme, ubrugelige tracebacks når programmet afbrydes med CTRL+C
def luk_pænt_ved_ctrl_c(signal, frame):
    raise SystemExit


signal.signal(signal.SIGINT, luk_pænt_ved_ctrl_c)


firedb = FireDb()
_show_colors = True


def _get_monochrome():
    """Hent konfigurationsindstilling for monokrom"""
    return firedb.config.getboolean("general", "monochrome")


def _set_monochrome(ctx, param, value):
    """
    Anvend værdien af --monokrom og sæt den globale værdi af _show_colors.
    """
    if value is not None:
        global _show_colors
        _show_colors = not value

        # Sæt også databasekonfigurationens monokrom-indstilling, så den
        # kan tilgås uden for dette modul (pretty_tables).
        # Dette overskriver værdien af monokrom der evt. måtte være sat i
        # konfigurationsfilen (fire.ini)
        firedb.config.set("general", "monochrome", str(value))

    return value


def _set_debug(ctx, param, value):
    """
    Ændrer debug tilstand på firedb object vha --debug.
    """
    if value is not None:
        firedb.engine.echo = value

    return value


def _set_database(ctx, param, value):
    """
    Vælg en specifik databaseforbindelse.
    """
    if value is not None:
        new_firedb = FireDb(db=str(value).lower())
        override_firedb(new_firedb)
    return value


def _start_interactive_mode(ctx: click.Context, param, value):
    """
    Start interaktiv udgave af den givne click.Context

    Brugeren mødes af en prompt med kommandoens almindelige signatur allerede
    udfyldt, fx:

            >>fire info punkt -I
            fire info punkt [IDENT]
                ... alm. punktinfo
            fire info punkt [IDENT -H]
                ... punktinfo med historik

    hvor teksten inden for [...] er brugerens input til prompten
    Kommandoen tager imod de samme options som den normale, ikke-interaktive
    version.

    Der kan fastholdes options til kommandoen ved at angive dem ved det første kald til
    kommandoen. De fastholdte værdier kan altid ændres ved angivelse af andre værdier::

        >>fire info punkt --db prod -H -I
        fire info punkt [IDENT]
            ... punktinfo med historik, trukket fra prod
        fire info punkt [IDENT --db test]
            ... punktinfo med historik, trukket fra test

    Det er vigtigt, at interaktiv-optionen vælges som det sidste på kommandolinjen.
    Options som kommer bagefter, vil ikke blive registreret som fastholdte. Fx

        fire info punkt --db prod -I -H

    vil kun fastholde db=prod.

    Årsagen er, at vi her anvender den aktive click Context's parametre, og at click parser
    options i den rækkefølge de er givet. Dermed vil `interaktiv` optionens callback
    (denne funktion) blive kaldt før `historik` optionen er blevet parset og føjet til den
    aktive click Context.

    Interaktiv mode kan også bruges til at lave fancy shell-scripting hvor fx en tekstfil
    pipes ind i en FIRE-kommando. Havelåge ("#") kan anvendes som kommentar-tegn i
    inputfil, både i starten af linjen og in-line.

        # Klargør en fil med identer der skal søges på
        echo GM901 >> pkter
        echo GM902 >> pkter
        echo #GM902 en linje der helt springes over >> pkter
        echo RDIO # en in-line kommentar >> pkter

        # Smid hver linje ind i fire info punkt og skriv til terminalen
        fire info punkt --db prod -I < pkter

        # Gem i stedet resultaterne i en fil
        fire info punkt --db prod -I < pkter > infopunkt_out

        # Ryd op
        rm pkter infopunkt_out
    """
    import shlex

    if value is False:
        return value

    kommando = ctx.command
    kommandovej = ctx.command_path

    # Her tilgås de parametre som allerede er blevet parset i den nuværende context.
    # Alternativt, kan `is_eager=True` sættes på alle andre parametre på alle kommandoer,
    # for at tvinge dem til at blive evalueret før `--interaktiv` flaget, men det bliver
    # hurtigt meget omfattende.
    faste_args = ctx.params
    faste_args_lst = [f"{opt}={val}" for opt, val in ctx.params.items()]
    print(f"\nStarter interaktiv session for '{kommandovej}'")
    if faste_args_lst:
        print(f"med flg. fastsatte argumenter: \n  {'\n  '.join(faste_args_lst)}")
    print(f"\nAfbryd med CTRL+C eller CTRL+Z+ENTER\n")

    while True:

        brugerinput = click.prompt(f"{kommandovej} ", prompt_suffix="", type=str)

        # split på # for at muliggøre kommentarer i en fil der pipes ind
        brugerinput = brugerinput.split("#")[0]
        if not brugerinput or brugerinput.strip()[0] in ("#"):
            continue

        # Brugerinput splittes med shlex der respekterer at strenge kan
        # indeholde mellemrum hvis de er wrapped med "".
        args = shlex.split(brugerinput, " ")

        # make_context parser alle options og kalder deres callbacks.
        # default_map bruges til at override de almindelige defaults med de fastholdte
        # parametre
        # der oprettes med vilje en separat kontekst uden "parentkontekst". Den nye
        # kontekst har så ikke "auto_envvar_prefix" sat, hvilket så gør at eventuelle
        # defaults sat med miljøvariable ignoreres.
        # Den tekniske årsag er, at miljøvariable tager præcedens over "default_map", som
        # vi her bruger til at fastsætte parametre, så derfor ville en parameter i
        # "default_map" aldrig blive brugt hvis den tilsvarende miljøvariabel var sat.
        try:
            ny_ctx = kommando.make_context(
                info_name=f"Interaktiv version af {kommandovej}",
                args=args,
                # parent=ctx, # vi nedarver med vilje ikke context settings fra parent
                default_map=faste_args,
            )

            ny_ctx.command.callback(**ny_ctx.params)
        except (Exception, SystemExit) as exc:
            # SystemExits, smidt igennem AfbrydFejl bliver også fanget og printet (inkl
            # click formattering). Hvis exit code er 0 printes ikke
            if str(exc) != "0":
                print(exc)


_default_options = [
    click.option(
        "--db",
        type=click.Choice(["prod", "test"]),
        default=None,
        callback=_set_database,
        is_eager=True,
        help="Vælg en specifik databaseforbindelse - default_connection i fire.ini bruges hvis intet vælges.",
    ),
    click.option(
        "-m",
        "--monokrom",
        is_flag=True,
        default=None,
        callback=_set_monochrome,
        help="Vis ikke farver i terminalen",
    ),
    click.option(
        "--debug",
        is_flag=True,
        default=None,
        callback=_set_debug,
        help="Vis debug output fra FIRE-databasen.",
    ),
    click.option(
        "-I",
        "--interaktiv",
        is_flag=True,
        default=False,
        callback=_start_interactive_mode,
        help="Slå interaktiv mode til.",
    ),
    click.help_option(help="Vis denne hjælpetekst"),
]


def default_options(**kwargs):
    """Create decorator that handles all default options"""

    def _add_options(func):
        # Click-produced help text shows arguments and options
        # in the order they were added.
        # Reversing the order to have it shown in same order in
        # the help text as items were defined in the list.
        for option in reversed(_default_options):
            func = option(func)
        return func

    return _add_options


def farvelæg(tekst: str, farve: str):
    """
    Farvelæg en tekst der udskrives via Click.
    """
    # Undgå ANSI farvekoder i Sphinx HTML docs
    if "sphinx" in sys.modules:
        return tekst

    if not _show_colors:
        return tekst

    return click.style(tekst, fg=farve)


def grøn(tekst: str):
    """
    Farv en tekst der udskrives via Click grøn.
    """
    return farvelæg(tekst, "green")


def rød(tekst: str):
    """
    Farv en tekst der udskrives via Click rød.
    """
    return farvelæg(tekst, "red")


def print(*args, **kwargs):
    """
    FIRE-specifik print funktion baseret på click.secho.

    Tilsidesætter farven når --monokrom parameteren anvendes i
    kommandolinjekald.
    """

    kwargs["color"] = _show_colors
    click.secho(*args, **kwargs)


def override_firedb(new_firedb: FireDb):
    """
    Tillad at bruge en anden firedb end den der oprettes automatisk af
    fire.cli.
    """
    global firedb
    firedb = new_firedb


def åbn_fil(fil: str) -> None:
    """
    Åben en fil med et passende program.

    Wrapperfunktion til os.startfile, der gør det muligt at undlade filåbning
    ved hjælp af indstilling i konfigurationsfil (`niv_open_files`).
    """
    if "startfile" in dir(os) and firedb.config.getboolean("general", "niv_open_files"):
        os.startfile(fil)
