.. _datamodel:

FIREs Datamodel
==================

Introduktion
-------------

Datamodellen i FIRE består af to lag: Et datalag og et metadatalag. Datalaget
indeholder de egentlige geodætisk relevante data, og metadatalaget indeholder
historikken af disse data. Tilsammen består de to lag af en række objekter
som har indbyrdes relationer. Et objekt i denne sammenhæng kan løseligt forstås
som en række i en relationel database.

Datamodellen er udviklet efter princippet om at det skal være muligt at genskabe
indholdet i databasen som det så ud på en vilkårlig dag tilbage i tiden. Dette
følger god forvaltningsskik i staten, samt understøtter inkrementelle opdateringer
af en tilknyttet udstillingsmodel.

For at kunne bestemme indholdet af databasen på et givent tidspunkt er det
en forudsætning at intet data slettes. Hvis data først er landet i databasen,
må det altså ikke forsvinde igen. Dette gælder også for fejlbehæftede data.
Det forhindrer dog ikke at fejl rettes, det betyder bare at istedet for at
fjerne data, erstattes det af nyt så man kan følge udviklingen over tid.
Til dette bruges "Fikspunktregisterobjekter". Alle de geodætiske data i FIRE
er Fikspunktsregisterobjekter, fx Punkter, Koordinater og Observationer (markeret
med blåt i figurerne herunder). At et objekt er et Fikspunktsregisterobjekt
betyder at det har fire attributter tilknyttet sig: ``registreringfra``,
``registreringtil``, ``sagseventidfra`` og ``sagseventidtil``. Tilsammen giver
disse fire attributter muligheden for at holde styr på historikken i databasen.

.. graphviz::
    :name: Fikspunktregisterobjekt
    :caption: Fikspunktregisterobjektet - det grundliggende object i FIRE
    :align: center

        digraph "Fikspunktregisterobjekt" {
            node [shape=record, fontname="Verdana", fontsize="12"];
            graph [splines=ortho];

            Fikspunktregisterobjekt [
                fillcolor = lightskyblue
                style = filled
                label = "{Fikspunktregisterobjekt|\l
                        + registreringfra : Datetime\l
                        + registreringtil : Datetime\l
                        + sagseventidfra : UUID\l
                        + sagseventidtil : UUID\l
                }"
            ]
        }

I praksis holdes der styr på data ved at registrere hvornår det er indsat i
databasen (``registreringfra``). Når et objekt, fx en koordinat, erstattes af
en nyere, angives det på det tidligere objekt hvornår det er blevet erstattet
(``registreringtil``). Tilsvarende, hvis et objekt skal "slettes" sættes
``registreringtil`` til det tidspunkt hvor det er besluttet, at objektet
ikke længere er i brug. Den slags ændringer i objekter kaldes hændelser. En
gruppe af logisk sammenhængende hændelser udgør en Sag.

I databasen er hændelserne navngivet "Sagsevents" (og ikke "Sagshændelser", da danske tegn fungerer dårligt i
databasen). Ved hver hændelse indsættes der et Sagsevent i databasen.
Disse kan identificeres ved ID'er. Det er disse ID'er Fikspunktsregisterobjekter
benytter i attributterne ``sagseventidfra`` og ``sagseventidtil``. Det vil sige
at hver gang et objekt registreres eller ændres i databasen, er der tilknyttet
metadata til hændelsen. Håndtering af Sager og Sagsevents beskrives yderligere i
afsnittet :ref:`sager_og_historik`.

Grundliggende objekter
------------------------

Alt i FIRE er bygget op omkring Punkter. Punktet er det mest simple objekt
i FIRE, da dets primære funktion er at være bindeled til andre objekter og derfor
i praksis kun består af en nøgle andre objekter kan henvise til. Der findes fem objekter
der direkte kan knyttes til et punkt: Koordinat, Observation, Punktinformation,
Geometriobjekt og Grafik. De indbyrdes forhold ses på figuren herunder og omtales yderligere
i separate afsnit længere nede i teksten.

.. graphviz::
    :name: Grundobjekter
    :caption: Grundliggende dataobjekter i FIRE
    :align: center

     digraph "Grundobjekter" {
         node [shape=record, fontname="Verdana", fontsize="12"];
         graph [splines=ortho];


        Punkt [
            label = "{Punkt|\l
                    + objektid : Integer\l
                    + id : UUID\l
            }"
            fillcolor = lightskyblue
            style = filled
        ]

        Geometriobjekt [
            label = "{Geometriobjekt|\l
                    + objektid : Integer\l
                    + punktid : UUID\l
                    + geometri : Geometry\l
            }"
            fillcolor = lightskyblue
            style = filled
        ]

        Punktinformation [
            label = "{Punktinformation|\l
                    + objektid : Integer\l
                    + punktid : UUID\l
                    + infotypeid : Integer\l
                    + tal : Boolean\l
                    + tekst : String\l
            }"
            fillcolor = lightskyblue
            style = filled
        ]

        Koordinat [
            label = "{Koordinat|\l
                    + objektid : Integer\l
                    + punktid : UUID\l
                    + sridid : Integer\l
                    + t : Datetime\l
                    + x : Float\l
                    + y : Float\l
                    + z : Float\l
                    + sx : Float\l
                    + sy : Float\l
                    + sz : Float\l
                    + transformeret : Boolean\l
                    + artskode : Integer\l
                    + fejlmeldt : Boolean\l

            }"
            fillcolor = lightskyblue
            style = filled
        ]

        Observation [
            label = "{Observation|\l
                    + objektid : Integer\l
                    + id : UUID\l
                    + observationstypeid : Integer\l
                    + antal : Integer\l
                    + gruppe : Integer\l
                    + observationstidspunkt : Datetime\l
                    + opstillingspunktid : UUID\l
                    + sigtepunktsid : UUID\l
                    + value1 : Float\l
                    + value2 : Float\l
                    ...\l
                    + value15 : Float\l
                    + fejlmeldt : Boolean\l
            }"
            fillcolor = lightskyblue
            style = filled
        ]

        Grafik [
            label = "{Grafik|\l
                    + objektid : Integer\l
                    + punktid : UUID\l
                    + grafik : BLOB\l
                    + type : String\l
                    + mimetype : String\l
                    + filnavn : String\l
            }"
            fillcolor = lightskyblue
            style = filled
        ]

        Geometriobjekt -> Punkt [constraint=false];
        Punktinformation -> Punkt [constraint=false];
        Koordinat -> Punkt [constraint=false];
        Observation -> Punkt [constraint=true];
        Grafik -> Punkt [constraint=true];

     }

Da der kan være mange forskellige typer Koordinater, Observationer
og Punktinformationer, findes der for hver af de tre objekter typer
som bruges til at bestemme hvilke egenskaber et givent objekt har.
På figuren herunder ses skematisk hvordan typerne for hver af de
tre objekter er bygget op.

.. graphviz::
    :name: Typer
    :caption: Typer
    :align: center

        digraph "Typer" {
            node [shape=record, fontname="Verdana", fontsize="12"];
            graph [splines=ortho];

            Observationstype [
                fillcolor = palegreen
                style = filled
                label = "{Observationstype|\l
                        + objektid : Integer\l
                        + id : Integer\l
                        + observationstype: String\l
                        + beskrivelse: String\l
                        + sigtepunkt: Boolean\l
                        + value1 : String\l
                        + value2 : String\l
                        ...\l
                        + value15 : String\l
                }"
            ]

            SRIDType [
                fillcolor = palegreen
                style = filled
                label = "{SRIDType|\l
                        + objektid : Integer\l
                        + id : Integer\l
                        + SRID: String\l
                        + kortnavn: String\l
                        + beskrivelse: String\l
                        + x : String\l
                        + y : String\l
                        + z : String\l
                }"
            ]

            Punktinfotype [
                fillcolor = palegreen
                style = filled
                label = "{Punktinfotype|\l
                        + objektid : Integer\l
                        + id : Integer\l
                        + infotype: String\l
                        + beskrivelse: String\l
                        + anvendelse : String\l
                }"
            ]

            Punktinformation [
                fillcolor = lightskyblue
                style = filled
            ]

            Koordinat [
                fillcolor = lightskyblue
                style = filled
            ]

            Observation [
                fillcolor = lightskyblue
                style = filled
            ]

            Punkt [
                fillcolor = lightskyblue
                style = filled
            ]

                Punktinfotype -> Punktinformation;
                SRIDType -> Koordinat;
                Observationstype -> Observation;

                Punktinformation -> Punkt;
                Koordinat -> Punkt;
                Observation -> Punkt;
        }

Punktinformationer og Punktinformationstyper
++++++++++++++++++++++++++++++++++++++++++++++


Punktinformationer er, som navnet antyder, information om et punkt. Punktinformation
dækker over mange aspekter af et punkter: Identer, afmærkningstyper, attributter,
skitser, geografisk område og så videre. Hver af disse aspekter er registreret som
en separat Punktinformationstype, der identificeres ud fra en nøgle på formen:
<kategori>:<attribut>. Eksempler på Punktinformationstyper er *IDENT:landsnr*, *NET:10KM* og
*AFM:højde_over_terræn*.

Tabellen herunder viser hvilke punktinformationskategorier der findes.

============  =================================
**Kategori**  **Beskrivelse**
------------  ---------------------------------
AFM           Afmærkningstyper
ATTR          Attributter
IDENT         Identer
NET           Netforhold
REGION        Geografisk region
SKITSE        Information vedr. punktskitser
============  =================================

Overordnet set kan Punktinformationer bruges på tre måder: Tekst, tal og markering.
Eksempler på tekst er *IDENT:GNSS*, *ATTR:bemærkning* og *SKITSE:sti*. Punktinformationer
der indeholder tal er *AFM:højde_over_dæksel* og *AFM:højde_over_jordoverfladen*.
Markeringer er "enten/eller"-attributter. Hvis en markering er angivet, er attributten aktuel
for det givne punkt. Eksempler herpå er *ATTR:tabtgået*, *NET:5D* og *REGION:DK*.

Mere information om en bestemt Punktinformationstype kan fås ved hjælp af kommandoen::

    fire info infotype <punktinfotype>


Koordinater og koordinatsystemer
++++++++++++++++++++++++++++++++

Koordinater og koordinatsystemer går hånd i hånd. Derfor har enhver koordinat
i FIRE et koordinatsystem, eller en SRID [#f1]_, tilknyttet sig. Det er SRID'en
der definerer hvilke dimensioner en given koordinat har. Fx en DVR90-kote der kun
består af et enkelt koordinatelement vinkelret på geoiden. En SRID kan være både
et-, to- eller tre-dimensionel. Dertil kommer at *alle* Koordinater i FIRE også har
en tidslig dimension. Tidspunktet for Koordinatens skabelses registreres altid
sammen med koordinaten i feltet ``t``. Afhængig af formålet vil ``t`` være angivet
enten til beregningstidspunktet eller opmålingstidspunktet.

Der kan knyttes mange Koordinater til et Punkt, men for hvert koordinatsytem
kan der kun være en gældende koordinat per punkt. Når en ny Koordinat tilføjes et
Punkt afregistreres dens forgænger automatisk.

Ligesom Punktinformationstyperne er SRID'er opdelt efter kategori. Som udgangspunkt
benyttes EPSG-koder for de systemer der er registreret i EPSG-databasen. De resterende
er navngivet efter region eller særligt formål. Se en oversigt over kategorierne i
tabellen herunder.

============  =============================================
**Kategori**  **Beskrivelse**
------------  ---------------------------------------------
EPSG          Koordinatsystemer registreret i EPSG-databasen
DK            Danske koordinatsystemer
GL            Grønlandske koordinatsystemer
TS            Lokale tidsseriekoordinatsystemer, fx på
              Jessen-punkter
============  =============================================

Mere information om et bestemt koordinatsystem kan fås ved hjælp af kommandoen::

    fire info srid <SRID>


Observationer og observationstyper
++++++++++++++++++++++++++++++++++

Ligesom for Punktinformation og Koordinater defineres forskellige typer af Observationer.
Der kan knyttes op til 15 værdier til en Observation; præcist hvor mange og deres betydning
defineres i Observationstypen. Der findes væsentligt færre observationstyper end der findes
SRID'er og Punktinformationstyper hvorfor de ikke organiseres under forskellige kategorier.
De tilgængelige Observationstyper vises i tabellen herunder.

===============================  ========================================================================
**Type**                         **Beskrivelse**
-------------------------------  ------------------------------------------------------------------------
``geometrisk_koteforskel``       Koteforskel fra fikspunkt1 til fikspunkt2 (h2-h1) opmålt geometrisk
``trigonometrisk_koteforskel``	 Koteforskel fra fikspunkt1 til fikspunkt2 (h2-h1) opmålt trigonometrisk
``retning``                      Horisontal retning med uret fra opstilling til sigtepunkt (reduceret
                                 til ellipsoiden)
``horisontalafstand``            Horisontal afstand mellem opstilling og sigtepunkt (reduceret til
                                 ellipsoiden)
``skråafstand``	                 Skråafstand mellem opstilling og sigtepunkt
``zenitvinkel``	                 Zenitvinkel mellem opstilling og sigtepunkt
``vektor``                       Vektor der beskriver koordinatforskellen fra punkt 1 til punkt 2 (v2-v1)
``absolut_tyngde``               Absolut gravimetrisk observation
``nulobservation``               Observation nummer nul, indlagt fra start i observationstabellen,
                                 så der kan refereres til den i de mange beregningsevents der fører til
                                 population af koordinattabellen
===============================  ========================================================================

Observationer foretages i de fleste tilfælde mellem to punkter: Et opstillingspunkt og et
sigtepunkt. Observationstypen afgør om der er behov for både et opstillingspunkt og et
sigtepunkt eller om der kun er brug for et opstillingspunkt. Der kan knyttes mange Observationer
til et Punkt eller et sæt af Punkter.

Mere information om en bestemt observationstype kan fås ved hjælp af kommandoen::

    fire info obstype <type>

Geometriobjekt
++++++++++++++

Et Geometriobjekt indeholder et Punkts omtrentlige placering i form af en GIS-læsbar
punktgeometri. Et Punkt kan kun have ét aktivt Geometriobjekt knyttet til sig ad
gangen. Geometriobjekter bruges fx i forbindelse med udstilling af fikspunkter i
Valdemar. Koordinater i Geometriobjekter er angivet som WGS84-koordinater, da det
er det mest gængse koordinatsystem i diverse GIS-applikationer, især webapplikationer
som Valdemar.

Et Punkts Geometriobjekt kan ses i form af en WKT-geometri ved at kalde::

    fire info punkt <ident>


Grafik
++++++++++++

Et Grafik objekt bruges til at registrere fikspunktsskitser og fotos af relevans
for et givent fikspunkt eller geodætisk station. Et Grafik objekt er karakteriseret
ved en billedefil i enten PNG eller JPEG, hvilket eksplicit registreres i felterne
``grafik``, ``mimetype`` og ``filnavn``. ``grafik`` indeholder selve det binære data
der udgør billedefilen, ``mimetype`` og ``filnavn`` holder rede på filens type og navn.

Herudover er grafikkens type også registreret i et felt i tabellen. Der skælnes mellem
to typer: skitse og foto.

Det gælder for grafikobjekterne at filnavnet er unikt, så det er ikke muligt at lægge
to billeder ind med samme navn. Dette princip er indført for at gøre det simplere at
eksportere fikspunktskitser til fx Valdemar.

Beregninger
++++++++++++

I FIRE kobles koordinater til Observationer ved hjælp af Beregninger. Herunder
ses skematisk hvordan forholdet mellem de tre objekter er. Bemærk de to
krydsreferencetabeller ``Beregning_koordinat`` og ``Beregning_observation``, der
gør det muligt at tilknytte et vilkårligt antal Koordinater til et vilkårligt
antal Observationer. Ved hjælp af Beregninger er det altså muligt at bestemme
præcist hvilke observationer der ligger til grund for en bestemt Koordinat.

.. graphviz::
    :name: Beregning
    :caption: Beregninger
    :align: center

        digraph "Punktinformationer" {
            node [shape=record, fontname="Verdana", fontsize="12"];
            graph [splines=ortho];

            Beregning [
                fillcolor = lightskyblue
                style = filled
                label = "{Beregning|\l
                        + objektid : Integer\l
                }"
            ]

            Beregning_koordinat [
                fillcolor = yellow
                style = filled
                label = "{Beregning_koordinat|\l
                        + beregningobjektid : Integer\l
                        + koordinatobjektid : Integer\l
                }"
            ]

            Beregning_observation [
                fillcolor = yellow
                style = filled
                label = "{Beregning_observation|\l
                        + beregningobjektid : Integer\l
                        + observationobjektid : Integer\l
                }"
            ]

            Koordinat [
                fillcolor = lightskyblue
                style = filled
                label = "{Koordinat|\l
                        + objektid : Integer\l
                }"
            ]

            Observation [
                fillcolor = lightskyblue
                style = filled
                label = "{Observation|\l
                    + objektid : Integer\l

                }"
            ]

            Beregning -> Beregning_observation -> Observation:n;
            Beregning -> Beregning_koordinat -> Koordinat:n;

        }

.. _tidsserier_og_punktsamlinger:

Tidsserier og PunktSamlinger
------------------------------

Til understøttelse af tidsserieanalyser findes der i FIRE objekterne Tidsserie
og PunktSamling. En tidsserie kan stå alene eller flere tidsserier kan grupperes
ved hjælp af en PunktSamling. Funktionaliteten af de to objekter forklares nemmest
med afsæt i to forskellige slags tidsserieanalyser: GNSS og Nivellement. En GNSS-
tidsserie er relativt simpel, da den udelukkende består af en række koordinater knyttet
til samme Punkt. Nivellementstidsserien derimod vil involvere flere punkter, hvoraf et
er udpeget som Jessenpunkt hvis stabilitet analyseres. Det vil sige at vi for hvert
punkt i PunktSamlingen har en Tidsserie bestående af koter relative til Jessenpunktet.
Herunder ses sammenhængene mellem tabellerne der ligger til grund for Tidsserie- og
Punktsamlingobjekterne.

.. graphviz::
    :name: Tidsserie
    :caption: Tidsserier og PunktSamlinger
    :align: center

        digraph "Tidsserier" {
            node [shape=record, fontname="Verdana", fontsize="12"];
            graph [splines=ortho];

            Tidsserie [
                fillcolor = lightskyblue
                style = filled
                label = "{Tidsserie|\l
                        + objektid : Integer\l
                        + punktid : UUID\l
                        + punktsamlingsid : Integer\l
                        + navn : String\l
                        + formaal : String\l
                        + sridid : Integer
                }"
            ]

            Tidsserie_koordinat [
                fillcolor = yellow
                style = filled
                label = "{Tidsserie_koordinat|\l
                        + tidsserieobjektid : Integer\l
                        + koordinatobjektid : Integer\l
                }"
            ]

            Koordinat [
                fillcolor = lightskyblue
                style = filled
                label = "{Koordinat|\l
                        + objektid : Integer\l
                }"
            ]

            PunktSamling [
                fillcolor = lightskyblue
                style = filled
                label = "{PunktSamling|\l
                    + objektid : Integer\l
                    + jessenpunktid : UUID\l
                    + jessenkoordinatid : Integer\l
                    + navn : String\l
                    + formaal : String\l

                }"
            ]

            Punkt [
                fillcolor = lightskyblue
                style = filled
                label = "{Punkt|\l
                    + id : UUID\l

                }"
            ]

            Punktsamling_punkt [
                fillcolor = yellow
                style = filled
                label = "{Punktsamling_punkt|\l
                        + punktsamlingobjektid : Integer\l
                        + punktid : UUID\l
                }"
            ]

            Tidsserie -> Tidsserie_koordinat;
            Tidsserie_koordinat -> Koordinat;
            PunktSamling -> Punktsamling_punkt -> Punkt:n;
            PunktSamling -> Punkt
            PunktSamling -> Koordinat
            Tidsserie -> PunktSamling [taillabel = "0..1"]

        }

.. _sager_og_historik:

Sager og historik
------------------

I FIRE findes der to overordnede objekter der bruges til at håndtere historik
i databasen: Sager og Sagsevents. En Sag bruges til at gruppere beslægtede
indsættelser i databasen. Typisk vil en Sag følge en opmålingskampagne fra
opmåling til beregning af koordinater, en sådan kampagne kunne fx bestå af en
række hændelser: Oprettelse af nye fikspunkter, opdatering af skitser, opmåling,
og beregning. Hver af disse hændelser afføder indsættelse af nye data i databasen.
Disse hændelser kaldes i FIRE-terminologi Sagsevents.

En Sag er, ligesom et Punkt, et meget simpelt objekt hvis primære funktion er at
knytte andre objekter sammen. For Sagens vedkommende er det Sagsevents der knyttes
sammen.

Som det kan ses på figuren herunder, findes der "info"-objekter til både Sager og
Sagsevents. Disse gør det muligt at ændre på status af en Sag og lave ændringer i
den tilknyttede beskrivelse på en måde hvor kravet om ikke at slette indformation
fra databasen overholdes. For Sagsevents giver det også muligheden for at tilknytte
materiale til Sagen. Et eksempel her på kunne være en beregningsrapport i forbindelse
med indsættelse af nye koordinater. Eller et notat der forklarer hvorfor et punkt
er nedlagt.

.. graphviz::
    :name: Sager
    :caption: Sagsobjekter i FIRE
    :align: center

        digraph "Sager" {
            node [shape=record, fontname="Verdana", fontsize="12"];
            graph [splines=ortho];

            Fikspunktregisterobjekt [
                fillcolor = lightskyblue
                style = filled
            ]

            Sag [
                fillcolor = salmon
                style = filled
                label = "{Sag|\l
                        + objektid : Integer\l
                        + id : UUID\l
                        + registreringfra : Datetime\l
                }"
            ]

            Sagsinfo [
                fillcolor = lightpink
                style = filled
                label = "{Sagsinfo|\l
                        + objektid : Integer\l
                        + sagsid : UUID\l
                        + aktiv : Boolean\l
                        + registreringfra : Datetime\l
                        + registreringtil : Datetime\l
                        + journalnummer : String\l
                        + behandler : String\l
                        + beskrivelse : String\l
                }"
            ]

            Sagsevent [
                fillcolor = salmon
                style = filled
                label = "{Sagsevent|\l
                        + objektid : Integer\l
                        + id : UUID\l
                        + sagsid : UUID\l
                        + registreringfra : Datetime\l
                        + eventtypeid : Integer\l

                }"
            ]

            Sagseventinfo [
                fillcolor = lightpink
                style = filled
                label = "{Sagseventinfo|\l
                        + objektid : Integer\l
                        + sagseventid : UUID\l
                        + registreringfra : Datetime\l
                        + registreringtil : Datetime\l
                        + beskrivelse : String\l
                }"
            ]

            Sagseventinfo_html [
                fillcolor = lightpink
                style = filled
                label = "{Sagseventinfo_html|\l
                        + objektid : Integer\l
                        + html : String\l
                        + sagseventinfoid : Integer\l
                }"
            ]

            Sagseventinfo_materiale [
                fillcolor = lightpink
                style = filled
                label = "{Sagseventinfo_materiale|\l
                        + objektid : Integer\l
                        + sti : String\l
                        + md5sum : String\l
                        + sagseventinfoid : Integer\l
                }"
            ]

            Eventtype [
                fillcolor = palegreen
                style = filled
                label = "{Eventtype|\l
                        + objektid : Integer\l
                        + beskrivelse : String\l
                        + event : String\l
                        + eventtypeid : Integer\l
                }"
            ]

            Sagsevent -> Sag;
            Sagsevent -> Fikspunktregisterobjekt;
            Sagsinfo -> Sag;
            Sagseventinfo -> Sagsevent;
            Sagseventinfo_html -> Sagseventinfo;
            Sagseventinfo_materiale -> Sagseventinfo;
            Eventtype -> Sagsevent;
        }

Der findes en række sagsevents i FIRE. I tabellen herunder er de alle kort beskrevet.

=========================  ============================================================================
**Type**                   **Beskrivelse**
-------------------------  ----------------------------------------------------------------------------
``koordinat_beregnet``     Bruges når koordinater indsættes efter en beregning. Vil typisk resulterere
                           i indsættelse af *n* koordinater og 1 beregning
``koordinat_nedlagt``      Bruges når en koordinat nedlægges
``observation_indsat``     Indsættelse af en eller flere observationer
``observation_nedlagt``    Bruges når en observation aflyses, fordi den er fejlbehæftet
``punktinfo_tilføjet``     Bruges når der tilføjes Punktinfo til et eller flere punkter
``punktinfo_fjernet``      Bruges når Punktinfo fjernes fra et eller flere punkter
``punkt_oprettet``         Bruges når et punkt og tilhørende geometri oprettes
``punkt_nedlagt``          Bruges når et punkt og tilhørende geometri nedlægges. Bemærk at når et punkt
                           nedlægges, afregistreres desuden alle tilknyttede koordinater, observationer
                           og punktinformationer, da disse ikke længere har et tilhørsforhold
``kommentar``              Bruges til at tilføje fritekst-kommentarer til sagen i tilfælde af at der er
                           behov for at påhæfte sagen yderligere information, som ikke passer i andre
                           hændelser. Bruges fx også til påhæftning af materiale på sagen
``grafik_indsat``	       Bruges når en grafik indsættes eller opdateres i databasen
``grafik_nedlagt``	       Bruges når en grafik nedlægges
=========================  ============================================================================

Eksempel på en sag
++++++++++++++++++

Hvis man ser på en hel sag for fx en simpel kommunal vedligeholdsopgave, så vil det gå nogenlunde sådan
her i databasen:

* Opret Sag (+ Sagsinfo)
* Opret Sagsevent af typen ``punkt_oprettet`` (+ Sagseventinfo)
* Indsæt Punkter og Geometriobjekter, henvis til Sagsevent fra linjen ovenfor
* Opret Sagsevent af typen ``punktinfo_tilføjet`` (+Sagseventinfo)
* Indsæt Punktinformationer (fx ``ATTR:tabtgået``), henvis til Sagsevent fra linjen ovenfor
* Opret Sagsevent af typen ``observation_indsat`` (+ Sagseventinfo)
* Indsæt Observationer, henvis til Sagsevent på linjen ovenfor
* Opret Sagsevent af typen ``koordinat_beregnet`` (+ Sagseventinfo, beregningsrapport vedlægges).
* Indsæt Koordinater og Beregning, henvis til Sagsevent på linjen ovenfor
* Opdater aktiv-feltet til "false" på Sagens Sagsinfo.

Der tilføjes beskrivelser af Sag og Sagsevent i forbindelse med at de oprettes. Beskrivelse for Sag kan fx lyde noget i stil med "Kommunal vedligehold Vejle 2020" og for Sagsevents fx "Indsættelse af observationer" og "Indsættelse af koordinater". Tilsammen gør det det muligt at få et hurtigt overblik over hvad der er
sket på en Sag.

Ovenstående eksempel er meget databasenært. Brugere af FIRE skal ikke forholde sig aktivt til Sagsevent
i samme grad som beskrevet ovenfor.

.. rubric:: Footnotes

.. [#f1] Spatial Reference ID, eksempelvis EPSG:25832.
