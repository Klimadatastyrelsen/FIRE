.. _workshop:



Præsentation af FIRE
---------------------
FIRE indeholder alt den relevante information, som refgeo gør. Der er punktnumre,
identer, skitser, koordinater, tidsserier, beskrivelse, afmærkningstyper osv. osv.
Strukturen er dog en helt anden og meget mere overskuelig og vedligeholdelsesvenlig
nede i maven på databasen, hvilket gør FIRE til en markant forbedring af et af
vores vigtigste dataarkiver.

Dog er alt vores nuværende udjævnings- og datahåndteringssoftware (fx. ADJ,
``valde`` og ``vedl.pl``) tilpasset refgeo og det famøse KMS-format, hvilket ikke kan
bruges i det nye setup.
Derfor har vi udviklet adskillige kommandolinjekald, som har til formål at lade
brugeren se ned i databasen, udtrække det data der er relevant, putte ny data
ned i databasen osv.
Det er en løbende opgave, hvor der bliver udviklet den funktionalitet, som viser
sig nødvendig og brugbar til et gentagent formål.

Hvis nogen havde håbet på en lækkert designet brugergrænseflade med søgebokse og
kasser, der kan hakkes af og en knap med *beregn* til til at lave en udjævning,
som derefter bliver vist i QGIS, så må vi skuffe.
Det er ikke der vi er; vi er slet ikke nok folk til at kunne retfærdiggøre at
bruge tid og penge på at udvikle sådan noget, og desuden vil det være et hejs at
vedligeholde og videreudvikle kode til, hvilket vi helst vil gøre selv.
Derfor er det altså stadig kommandolinjekald, som er vejen frem! Men dermed bliver
overgangen til ny database og beregningssoftware nok ikke så slem alligevel.

Nedenfor uddybes de funktionaliteter vi på nuværende tidspunkt har udviklet. Det er
alle underprogrammer (og under-underprogrammer) under ``fire`` og køres derfor ved
først at kalde ``fire`` efterfulgt af underkommandoens navn.

fire info
++++++++++++++++++++

En grundliggende funktionalitet er at kunne se hvilken data, der ligger i databasen,
altså hvilken info man har i arkivet. Til det er der udviklet et kommandolinjeprogram
kaldet ``fire info``. Man kan se hvad programmet indeholder ved at afvikle kommandoen
``fire info --help``:

.. command-output:: fire info --help

Herfra ses fem forskellige kommandoer man kan bruge:

- ``infotype``
- ``obstype``
- ``punkt``
- ``sag``
- ``srid``

Hvis man ønsker at fremsøge et punkt og se hvilke oplysninger, der knytter sig
til det (som man før kunne med ``valde``, eller Valdemar i tjenesten), kan man
fx taste ``fire info punkt gi2010``. I udtrækket plottes diverse oplysninger om
punktet direkte på skærmen, som ses herunder:

.. code-block::

    (fire-dev) C:\dev\fire\docs>fire info punkt gi2010

    --------------------------------------------------------------------------------
    PUNKT G.I.2010
    --------------------------------------------------------------------------------
      Lokation                    POINT (11.1425084856365 55.3252167385718)
      Oprettelsesdato             1985-03-19 01:11:00
     -AFM:4999                    Ukendt.
     -AFM:1700                    Præcisionsnivellementspunkt.
      AFM:1704                    Messingbolt i granitpostament.
     -AFM:horisontal
      AFM:horisontal
      AFM:højde_over_terræn       -1.4
      ATTR:restricted
     -ATTR:beskrivelse            G.I.2010
     -ATTR:beskrivelse            G.I.2010
                                  Korsør By.
                                  Kjærsvej 2.
                                  Punkt i S. del af kirkegårdens planteskole.
     -ATTR:beskrivelse            G.I.2010.
                                  Korsør By.
                                  Kjærsvej 2.
                                  Punkt i brønd med dæksel, i S. del
                                  af kirkegårdens materialplads.
                                  Dæksel til terræn.
      ATTR:beskrivelse            G.I.2010.
                                  Korsør Kirkegård.
                                  Punkt i brønd med dæksel,
                                  i lille jordstykke til planteopdræt.
                                  Dæksel til terræn.
      ATTR:højdefikspunkt
      ATTR:tinglysningsnr         Sagsnummer fra Tingbogen ikke tilgængeligt. Opdatering udestår.
     -ATTR:bemærkning             Punkt oprettet
     -ATTR:bemærkning             Rev. beskr. uge 31 2003 Ole E.
     -ATTR:bemærkning             Rev. 1971 af Stæhr Madsen.
      ATTR:bemærkning             Rev. uge 18 2017 PN.
      NET:jessen
      REGION:DK
      SKITSE:png_sti              skitser_png/K-11-09263_1.png
      SKITSE:png_md5              61c0d3e31274e889b4c627d455bee5d8
      SKITSE:master_sti           skitser_master/K-11-09263_1.cgm
      SKITSE:master_md5           49d8bc56b63d71122a9f1cfc95975ffb
      NET:DVR90
      IDENT:refgeo_id             11122
      IDENT:landsnr               K-11-09263
      IDENT:GI                    G.I.2010
      IDENT:ekstern               9904/14510
      IDENT:jessen                81041

    --- KOORDINATER ---
    * 2000-02-11 14:30  EPSG:5799       n 8.49270 (4)
    * 2011-12-24 01:00  EPSG:4258       n 11.1424517702, 55.3252437011 (200, 200)
    * 2000-02-11 14:30  DK:HPOT_DVR90   n 8.33590 (4)
    * 1999-04-29 16:00  DK:GI44         n 8.56610 (5)

.. note:: Det er ligegyldigt om der skrives med stort eller småt eller om der
   benyttes punktummer eller ej i argumentet. Dog skal der være bindestreg
   mellem herred, sogn og løbenummer.

Udtrækket viser den formodede relevante information, der ligger på punktet fra
attribut-tabellerne og fra koordinattabellerne.
I eksemplet ses det fx, at punktet

- er oprettet i databasen 19/3 1985,
- også hedder K-11-09263,
- i øvrigt er et Jessenpunkt til en tidsserie,
- har en DVR90-kote fra 3. præcisionsnivellement indikeret ved EPSG-kode 5799
  og beregningstidspunkt 11/2-2000 kl. 13:30,
- har en plankoordinat fra 2011 (med EPSG-koden 4258) og to andre
  koordinater i andre net.
  **Stjerne (eller farven grøn) indikerer at koordinaten er den gældende for det pågældende net.**

På samme måde kan andre elementer slås op i databasen, bl.a. oplysninger om historiske
koter med parameteren ``-K``, observationer med parameteren ``-O`` og andre detaljer med
parameteren ``-D``.

Øvelse
^^^^^^^^^^^^^^^^^^^^

Prøv selv at fremsøge mere info, fx:

1. alle observationer fra et givent punkt
2. alle historiske koordinater for et punkt
3. tekstbeskrivelsen på attributten AFM:2701
4. alle aktive sager i databasen


fire niv
++++++++++++++++++++++++++++++++
Der er blevet udviklet et kommandolinjeprogram til udjævningsberegning kaldet ``niv``.
Læs om hvordan programmet kaldes :ref:`her <kommandolinjeprogrammer_niv>`

Med dette program kan hele produktionslinjen køres; fra dataudtræk, revision, beregning,
til ilægning af resultat og generering af afsluttende rapport til kunde. Se mere ved
at køre kommandoen ``fire niv --help``:

.. command-output:: fire niv --help

Alt datahåndtering foregår på Windows og i Excel-regneark med diverse faneblade.
Vi vil nedenfor gennemgå processen.

.. note:: Sørg for at bruge små bogstaver. Kald og parametre genkendes ikke med versaler.
   Undtagelsen er ved punktnumre; her kan både store og små bogstaver benyttes.

I de følgende afsnit beskrives de enkelte delprogrammer under `fire niv`. De vises i
en idealiseret rækkefølge, der følger arbejdsgangene i forbindelse med revision af
kommunale fikspunkter. I praksis kan programmerne afvikles i forskellig rækkefølge,
eller helt udelades, alt efter behov.

Først gennemgås det klassiske forløb, dernæst kommer et eksempel på udtræk af
eksisterende observationer med ``udtræk-observationer``.


Trin 1) opret-sag
^^^^^^^^^^^^^^^^^^^^^^^^

I ``fire`` har vi valgt at knytte al beregning og fikspunkthåndtering op på såkaldte
*sagsevents*. Det vil sige at når man går igang med et nyt projekt, fx. en opgave
omhandlende opmåling og beregning af lokal vandstand i Havnebyen, så opretter man
en sag til denne opgave, hvori alt ens dataudtræk, observationer, beregninger og
endelige resultater bliver registreret på. Kaldet, der skal køres under ``fire niv``
for at oprette en ny sag, hedder, passende nok, ``opret-sag``. Lad os prøve at få
mere hjælp:

  .. command-output:: fire niv opret-sag --help

Her kommer en beskrivelse af hvad der forventes af input:

- Options: Valgfrit. Valgmuligheder ses i hjælpeteksten.
- Projektnavn: Obligatorisk. Kan fx være ``Fjernkontrol_af_SULD``. Dette bliver navnet
  på dit regneark.
- Beskrivelse: Valgfrit, men en god idé at beskrive nærmere hvad sagen indeholder,
  fx "Nivellement af skruepløkke samt lodrette bolte ved SULD samt fjernkontrol til
  5D-punktet GRAV. Antenne IKKE opført."

.. note:: Hvis input består af flere ord, fx i projektnavn eller beskrivelse, skal
   disse indkaples i citationstegn (\" \"). Det anbefales dog IKKE at lave mellemrum
   i projektnavne.

I terminalen vil det se ud som dette, når der oprettes en sag:

.. code-block::

    (fire) C:\>fire niv opret-sag Fjernkontrol_af_SULD "Nivellement af skruepløkke og lodrette bolte ved SULD samt fjernkontrol til 4D-punktet GRAV. Antenne IKKE opført"
    Sags/projekt-navn: Fjernkontrol_af_SULD  (aef7ae59-e2fd-4c5d-9bc1-99bc7ad82bb9)
    Sagsbehandler:     B012349
    Beskrivelse:       Nivellement af skruepløkke og lodrette bolte ved SULD samt fjernkontrol til 4D-punktet GRAV. Antenne IKKE opført
    Opretter ny sag i test-databasen - er du sikker?  (ja/NEJ):
    ja
    Gentag svar for at bekræfte (ja/NEJ)
    ja
    Sag 'Fjernkontrol_af_SULD' oprettet
    Skriver sagsregneark 'Fjernkontrol_af_SULD.xlsx'
    Filen 'Fjernkontrol_af_SULD.xlsx' findes ikke.
    Skriver: {'Notater', 'Filoversigt', 'Sagsgang', 'Projektforside', 'Nyetablerede punkter', 'Parametre'}
    Til filen 'Fjernkontrol_af_SULD.xlsx'
    Færdig! - åbner regneark for check.

Det ses, at der kommer en advarsel op. Da alt hvad der oprettes i databasen ikke
kan slettes, er det en god idé at dobbelttjekke alt info man skriver til databasen.
Hvis man er sikker på sit input, kan man svare *"ja"* til spørgsmålet. Hvis der svares
alt andet, vil der ikke blive oprettet en sag i databasen.

Skrives der alt andet end *"ja"*, får man valget om der alligevel skal oprettes
sagsregneark (også kaldet projektfil). Hertil kan der svares *"ja"*, og et excel-ark
med filnavn som projektnavn oprettes i den mappe man kører kaldet i.

.. code-block::

    (fire) C:\>fire niv opret-sag Fjernkontrol_af_SULD2
    Sags/projekt-navn: Fjernkontrol_af_SULD2  (b87e15e0-b0db-4388-9476-09d496ec0906)
    Sagsbehandler:     B012349
    Beskrivelse:
    Opretter ny sag i test-databasen - er du sikker?  (ja/NEJ):
    nej
    Opretter IKKE sag
    Opret sagsregneark alligevel? (ja/NEJ):
    ja
    Skriver sagsregneark 'Fjernkontrol_af_SULD2.xlsx'
    Filen 'Fjernkontrol_af_SULD2.xlsx' findes ikke.
    Skriver: {'Projektforside', 'Parametre', 'Filoversigt', 'Nyetablerede punkter', 'Notater', 'Sagsgang'}
    Til filen 'Fjernkontrol_af_SULD2.xlsx'
    Færdig! - åbner regneark for check.

Excel-arket åbnes, og der ses seks faneblade:

- Projektside: Her kan man løbende indtaste relevant info for projektet.
- Sagsgang: Her vil sagens hændelser fremgå, efterhånden som de forekommer.
- Nyetablerede punkter: Her kan man indtaste de nye punkter, som er oprettet til
  projektet.
- Notater
- Filoversigt: Her kan man indtaste filnavnene på opmålingsfilerne. husk at definere
  stien, hvis ikke filen ligger samme sted som projektfilen.
- Parametre

Hvert faneblad kan nu redigeres til det formål man ønsker.

.. note:: Når man laver sit kommandokald, skal man sikre sig der ikke eksisterer et
   projekt med det navn allerede, ellers vil ``fire`` brokke sig. ``fire`` kan ligeledes
   ikke skrive til et allerede åbent excel-ark.

Herfra kan man nu vælge at fortsætte til Trin 2 og foretage revisions-arbejde med
nye data, eller gå til Trin 5a, hvor man udtrækker eksisterende observationer til
regnearket baseret på en række søgekriterier, geometrifiler eller identer.


Trin 2) udtræk-revision
^^^^^^^^^^^^^^^^^^^^^^^^
.. note::

    Dette trin kan springes over, såfremt man kun skal lave en beregning.

Når vi er ude at tilse punkter, fx ifm. den kommunale punktrevision, kontrolleres det
at punktets attributter (beskrivelse, lokation, bolttype osv.) er korrekt; hvis ikke
skal de rettes til.
Til det formål kan man kalde en kommando, der hedder ``udtræk-revision`` under
``fire niv``:

.. command-output:: fire niv udtræk-revision --help

Det ses man skal definere to parametre:

- Projektnavn: Som defineret i ``opret-sag``. Indkapslet i \" \"
- Kriterier: Enten ident eller opmålingsmålingsdistrikt. Her kan man fx. skrive 61-07 61-03 G.I.902 BUDP

I terminalen vil det se ud som følger:

.. code-block::

    (fire) C:\>fire niv udtræk-revision Fjernkontrol_af_SULD 61-07 61-03 63-10
    Punkt: 61-01-00008
    Punkt: 61-03-00001
    Punkt: 61-03-00002
    Punkt: 61-03-00003
    Punkt: 61-03-00010
    Punkt: 61-03-00801
    ...
    Punkt: 63-10-09081
    Punkt: 63-10-09082
    Punkt: 63-10-09084
    Skriver: {'Revision'}
    Til filen 'Fjernkontrol_af_SULD-revision.xlsx'
    Overskriver fanebladene {'Revision'}
        med opdaterede versioner.
    Foregående versioner beholdes i 'ex'-filen 'Fjernkontrol_af_SULD-revision-ex.xlsx'
    Færdig!

hvorefter punkterne udtrækkes og lægges i en ny excel-fil navngivet med
"projektnavn"-revision.xlsx. Format er som vist nedenfor:

.. image:: figures/firenivudtrækrevision.PNG
  :width: 800
  :alt: Udtræk data til punktrevision, excelvisning

I dette ark kan man nu rette attributterne til efter behov. Nedenfor er vist:

1. ændring i lokationskoordinaten (*LOKATION*)
2. rettelser for punkt 61-01-00008 i attributterne *ATTR:beskrivelse*,
   *AFM:højde_over_terræn* og *ATTR:bemærkning*.
3. at punktet nu er et restricted punkt (*ATTR:restricted*) og dens GNSS-egnethed (*ATTR:gnss_egnet*)
4. at punktet er besøgt ved at fjerne kryds i kolonnen *Ikke besøgt*

.. image:: figures/firenivudtrækrevision2.PNG
  :width: 800
  :alt: Udtræk data til punktrevision, excelvisning

.. note:: Attributter MED id indikerer at oplysningen er gemt og udtrukket fra
   databasen. Attributter UDEN id er endnu ikke oprettet i databasen.

Ved revision af mange punkter, er der oprettet en overblikskolonne, *Ikke besøgt*.
Denne er født med et kryds ud for punktbeskrivelsen, da man derved kan tilføje excels
filterfunktion, og filtrere de rækker væk uden et kryds. Pas på med ikke at *sortere*,
da rækkerne så vil blive blandet. Efter filtrering kan man let se hvilke punkter man
endnu ikke har været forbi... såfremt man husker at slette krydset fra de punkter man
allerede HAR besøgt.


Trin 3) ilæg-revision
^^^^^^^^^^^^^^^^^^^^^^^^
.. note::

    Dette trin kan springes over, såfremt man kun skal lave en beregning.

Ændringer lavet i revisionsregnearket i trin 3 ovenfor lægges i databasen
med kommandoen `fire niv ilæg-revision`.

.. command-output:: fire niv ilæg-revision --help

Herunder vises et eksempel på hvordan en revision indlæses i databasen:

.. code-block::

    (fire-dev) C:\>fire niv ilæg-revision Fjernkontrol_af_SULD
    Sags/projekt-navn: Fjernkontrol_af_SULD  (aef7ae59-e2fd-4c5d-9bc1-99bc7ad82bb9)
    Sagsbehandler:     B012349


    Behandler 134 punkter
    61-01-00008
        Retter punktinfo-element: ATTR:beskrivelse
        Retter punktinfo-element: AFM:højde_over_jordoverfladen
        Retter punktinfo-element: ATTR:bemærkning
        Opretter nyt punktinfo-element: ATTR:restricted
        Opretter nyt punktinfo-element: ATTR:gnss_egnet
    61-03-00001
    61-03-00002
    61-03-00003
    61-03-00010
    ...
    63-10-09079
    63-10-09080
    63-10-09081
    63-10-09082
    63-10-09084

    --------------------------------------------------
    Punkter færdigbehandlet, klar til at
    - oprette 2 attributter fordelt på 1 punkter
    - slukke for 0 attributter fordelt på 0 punkter
    - rette 3 attributter fordelt på 1 punkter
    - rette 1 lokationskoordinater
    Er du sikker på du vil indsætte ovenstående i prod-databasen (ja/NEJ):

Tast "ja" til ovenståede og bekræft med endnu et "ja" for at indsætte i databasen.

Det kan ske at der er blevet indtastet ugyldige værdier i regnearket. I så fald
vil programmet skrive advarsler ud på skærmen og afslutningsvis komme med en
fejlmelding der kan være lidt svær at forstå:

.. code-block::

    61-01-00008
        Retter punktinfo-element: ATTR:beskrivelse
        Retter punktinfo-element: AFM:højde_over_jordoverfladen
        FEJL: AFM:højde_over_jordoverfladen forventer numerisk værdi [could not convert string to float: '0,1'].
        Opretter nyt punktinfo-element: ATTR:restricted
        BEMÆRK: ATTR:restricted er et flag. Ny værdi 'fejl' ignoreres
        Opretter nyt punktinfo-element: ATTR:gnss_egnet
    61-03-00001

I langt de fleste tilfælde er
løsningen at bladre tilbage i programmets output, finde advarslerne og rette dem
i regnearket. Herefter køres ilægningskommandoen igen.


.. _trin4:

Trin 4) ilæg-nye-punkter
^^^^^^^^^^^^^^^^^^^^^^^^

.. note::

    Dette trin kan springes over hvis ingen nye punkter er tilføjet


Nye punkter tilføjes i fanebladet "Nyetablerede punkter" i projektregnearket. Punkterne
indlæses i databasen med kommandoen ``fire niv ilæg-nye-punkter``. Programmet muligheder
ses herunder:

.. command-output:: fire niv ilæg-nye-punkter --help

Et typisk kald vil være::

    fire niv ilæg-nye-punkter projektnavn

Under faneblandet "Nyetablerede punkter" findes et antal kolonner hvor information om
de nye punkter indtastes. En linje pr. nyt punkt. For at tilføje et punkt *skal*
følgende kolonner være udfyldt:

1. Et foreløbigt navn
2. En længdegrad/Y, Nord (UTM eller grader)
3. En breddegrad/X, Øst (UTM eller grader)
4. En angivelse af fikspunktets type (vælg mellem GI, MV, HØJDE, JESSEN og VANDSTANDSBRÆT)

.. image:: figures/firenivilægpunkter.PNG
  :width: 800
  :alt: Opret nye punkter, excel-visning

De resterende kolonner må meget gerne også fyldes ud, men den videre proces er ikke
afhængig af dem. Det man ikke kan udfylde, er *Landsnummer* og *uuid*, da det først
genereres det øjeblik punktet lægges i databasen.

Fikspunktstypen afgør hvilket interval landsnummerets løbenummer placeres i. Hvis
et punkt angives som værende et GI-punkt får det tildelt både et landsnummer og
et GI-nummer. Det næste ledige GI-nummer vælges automatisk.

.. note:: Koordinater kan skrives både med UTM-format og med gradetal. ``fire`` genkender
   selv formatet og transformerer til geografiske koordinater, som er standard i ``fire``.

Under afmærkning kan følgende typer indtastes:

1. ukendt
2. bolt
3. lodret bolt
4. skruepløk
5. ingen

Ved oprettelse af punktet indsættes automatisk en `ATTR:bemærkning` med info om
nyetablering i indeværende år af den givne sagsbehandler. Sidstnævnte fremstår som
brugerens B-nummer medmindre andet er angivet med `--sagsbehandler` når kommandoen
kaldes.

.. _trin5:

Trin 5) læs-observationer
^^^^^^^^^^^^^^^^^^^^^^^^^^

Når man har lavet sin opmåling færdig, ender man med en råfil eller mere, som skal
beregnes. Disse filnavne (og tilhørende sti) skal tastes ind i excel-arket under
fanen *Filoversigt* med en opmålingstype (mgl eller mtl), en apriori-spredning (:math:`\sigma`)
og centreringsfejl(:math:`\delta`).

Herefter **GEMMES EXCEL-ARKET** og man vender tilbage til terminalen for
at lave kaldet ``læs-observationer`` (man behøver ikke at lukke sin projektfil,
da der ikke skrives til denne i kaldet, men blot læses herfra). Lad os se hvilke
parametre det har brug for:

.. command-output:: fire niv læs-observationer --help

Her vises at den obligatoriske parameter er *Projektnavn*, hvilket i vores eksempel
vil se således ud:

.. code-block::

    (fire-dev) C:\>fire niv læs-observationer Fjernkontrol_af_SULD
    Importerer observationer
    Fandt 61-10-00009
    Fandt SUL4
    Fandt SUL1
    Fandt SUL2
    Fandt SUL3
    Fandt 61-10-09023
    Fandt 61-10-09024
    Fandt 61-10-09025
    Fandt 0 tabte punkter blandt 8 observerede punkter.
    Opbygger punktoversigt
    Finder kote for 61-10-00009
    Finder kote for 61-10-09023
    Finder kote for 61-10-09024
    Finder kote for 61-10-09025
    Finder kote for SUL1
    Finder kote for SUL2
    Finder kote for SUL3
    Finder kote for SUL4
    Skriver: {'Observationer', 'Punktoversigt'}
    Til filen 'Fjernkontrol_af_SULD.xlsx'
    Dataindlæsning afsluttet. Vælg nu fastholdte punkter i punktoversigten.

Efter kaldet er færdigkørt, vil der være dannet tre nye filer;

- en *projektnavn*-resultat.xlsx
- en *projektnavn*-observationer.geojson samt
- en *projektnavn*-punkter.geojson

De to .geojson-filer er til indlæsning i QGIS til visualisering af nettet. Se
:ref:`her <visualiseringQGIS>` for mere.

Når resultatfilen åbnes, ses to faneblade; et med observationerne og et med en
punktoversigt:

.. image:: figures/firenivlæsobservationer.PNG
  :width: 800
  :alt: Observationsliste

Bemærk kolonnen *Sluk*, som indikerer en mulighed for at udelade enkelte observationer
i den videre beregning.

.. image:: figures/firenivlæsobservationer2.PNG
  :width: 800
  :alt: Punktoversigt

Bemærk også at nyetablerede punkter fra faneblad i projektfil fremgår med *År* lig 1800,
*Kote* lig 0 og *Middelfejl* lig 1000000. I tilfældet her er et punkt etableret, men
findes ikke i observationsfilen (Hjortholmvej 19), og det fremgår så også uden
yderligere information.

Slutteligt står der i terminalen hvad man skal gøre som det næste:
*Dataindlæsning afsluttet. Vælg nu fastholdte punkter i punktoversigten.*
Så det gør vi!

Trin 5a) Udtræk eksisterende observationer til beregning
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Som nævnt er det muligt at gå direkte fra sagsoprettelse til udtræk af observationer
fra fire-databasen. Nedenfor er et eksempel på, hvordan dette kan gøres.

Når du har oprettet en sag som i Trin 1 ovenfor, kan du trække eksisterende
observationer ud med kommandoen ``fire niv udtræk-observationer``.

.. command-output:: fire niv udtræk-observationer --help

Herefter kan du fortsætte med resten af trinene i sagsforløbet fra Trin 6.


.. _trin6:

Trin 6) regn
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Vi skal nu til at beregne nye koter til de observerede punkter.
Det sker i tre skridt:

1. *Observationsindlæsning*
2. *Kontrolberegning* og
3. *Endelig beregning*

Første skridt har vi allerede udført i afsnittet :ref:`læs-observationer <trin5>`, ovenfor,
som bl.a. gav os fanebladet "Punktoversigt". Det er her, i fanebladets søjle "Fasthold" at
man markerer hvilke punkter der skal fastholdes i kontrolberegningen: Sæt et *x* ud for de
punkter du vil fastholde, gem regnearket, vend tilbage til terminalen og kør ``fire niv regn``:

.. command-output:: fire niv regn --help

Herfra ses at man igen skal bruge *Projektnavn* som parameter. Programmet afgør selv
hvilken type beregning vi har med at gøre: Første beregning
udføres som kontrolberegning, efterfølgende beregninger betragtes som den endelige
beregning.

I terminalen vil det se således ud:

.. code-block::

  (fire-dev) C:\>fire niv regn Fjernkontrol_af_SULD
  Så regner vi
  Analyserer net
  Fastholder 2 og beregner nye koter for 6 punkter
  Skriver: {'Singulære', 'Netgeometri', 'Kontrolberegning'}
  Til filen 'Fjernkontrol_af_SULD.xlsx'
  Overskriver fanebladene {'Singulære', 'Netgeometri'}
      med opdaterede versioner.
  Foregående versioner beholdes i 'ex'-filen 'Fjernkontrol_af_SULD-ex.xlsx'
  Færdig! - åbner regneark og resultatrapport for check.


Det ses at der er valgt to punkter som fastholdt. Hvis der er subnet
uden fastholdte punkter advarer FIRE om dette og foreslår et punkt
til fastholdelse i hvert subnet.

Udover beregningsresultatet i projektregnearket genereres
flere resultatfiler, bl.a.

- *projektnavn*-resultat.xml (til intern brug for ``fire``)
- *projektnavn*-resultat.html
- *projektnavn*-kon-observationer.geojson
- *projektnavn*-kon-punkter.geojson

I .html-filen findes diverse statistik over udjævningsberegningen, som det underliggende
kode (GNU Gama) genererer. Filen åbnes også default efter kørslen. De to geojson-filer
kan bruges til at visualisere beregningen i fx QGIS.

I resultatfilen er der nu tre nye faner;

- *Netgeometri*,
- *Singulære* og
- *Kontrolberegning*

Netgeometrien viser hvilke punkter er naboer til hvilke punkter, og man kan herfra
se om der er blinde linjer (punkter med kun én nabo). Singulære punkter er punkter, som
ikke er forbundet med de(t) fastholdte punkt(er), og der derfor ikke kan beregnes en kote
til.

Kontrolberegningen viser det egentlige beregningsresultat. Kolonner er nu fyldt ud med
nyberegnede koter, middelfejl og differencen fra gældende kote, og man kan lave sin
endelige vurdering af beregningen. Er man ikke tilfreds med kontrolberegningen kan man
slette fanebladet, rette de fastholdte punkter til i fanebladet *Punktoversigt*, og
køre beregningen endnu en gang.

Fanebladet *Kontrolberegning* er indrettet på samme måde som *Punktoversigt*, og benyttes
på samme måde - nu til at udvælge de punkter, der skal fastholdes i den endelige beregning.

På forhånd er de fastholdte punkter fra kontrolberegningen afmærket med *x*.
Ved den endelige beregning fastholdes alle de punkter der har et **vilkårligt tegn** i
"Fasthold"-søjlen i fanebladet *Kontrolberegning*. Dvs. alle dem, der allerede har et *x*
fra kontrolberegningen, *og derudover* alle dem man selv tilføjer inden den endelige beregning
udføres.

For at kunne skelne mellem de to klasser af fastholdte punkter anbefales det at benytte
markeringen *e* (for *endelig*) for de yderligere punkter man vil fastholde i den endelige
beregning. Derefter køres ``fire niv regn`` igen.

Denne gang vil resultatfanebladet hedde *Endelig beregning*. Er man ikke tilfreds med den
kan man slette (eller omdøbe) fanebladet, tilpasse sine fastholdte punkter i fanebladet
*Kontrolberegning*, og køre beregningen en gang til.

Efter den endelige beregning opdateres de to geojson-filer der blev genereret med
`fire niv læs-observationer`, så beregningsresultatet også fremgår af disse. Det
drejer sig om filerne:

- *projektnavn*-observationer.geojson
- *projektnavn*-punkter.geojson


Trin 7) ilæg-observationer
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Observationer lægges i databasen med kommandoen ``fire niv ilæg-observationer``:

.. command-output:: fire niv ilæg-observationer --help



Trin 8) ilæg-nye-koter
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. command-output:: fire niv ilæg-nye-koter --help

Punktoversigten fra resultatarket indeholder den info, som skal lægges i databasen:
Koter, middelfejl osv. Hvis der er punkter, som man ikke ønsker skal have ny kote,
kan man sætte *x* i kolonnen *Udelad publikation*, som vist nedenfor:

.. image:: figures/firenivilægkoter2.PNG
  :width: 800
  :alt: Ilæg nye koter i database

På den måde fremgår punktet stadig i projektfilen og det er tydeligt at punktet
er valgt fra ved koteopdateringen.

.. code-block::

    (fire-dev) C:\>fire niv ilæg-nye-koter Fjernkontrol_af_SULD
    Sags/projekt-navn: Fjernkontrol_af_SULD  (aef7ae59-e2fd-4c5d-9bc1-99bc7ad82bb9)
    Sagsbehandler:     B012349
    Opdatering af DVR90 kote til 61-10-09023, 61-10-09024, 61-10-09025, SUL1, SUL3, SUL4
    Ialt 6 koter
    Du indsætter nu 6 kote(r) i prod-databasen - er du sikker? (ja/NEJ):


Trin 9) luk-sag
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Når en sag er afsluttet skal den lukkes med ``fire niv luk-sag``.
Det er simpelt og mønsteret fra de andre ``fire niv``-programmer følges:

.. command-output:: fire niv luk-sag --help

I praksis ser det ud som følger:

.. code-block::

  (fire-dev) C:\>fire niv luk-sag Fjernkontrol_af_SULD
  Er du sikker på at du vil lukke sagen {projektnavn}? (ja/NEJ):
  ja
  Gentag svar for at bekræfte (ja/NEJ)
  ja
  Sag aef7ae59-e2fd-4c5d-9bc1-99bc7ad82bb9 for 'Fjernkontrol_af_SULD' lukket!


.. _visualiseringQGIS:

Visualisering i QGIS
------------------------

For at få en grafisk visning af sit opmålte net, bruges QGIS. Man kan åbne QGIS enten
via startmenuen i Windows eller ved at taste

	> qgis

i sin terminal (såfremt det miljø man arbejder i har QGIS tilknyttet).

I :ref:`trin 5) <trin5>` blev der genereret to .geojson-filer, en punktfil og en
observationslinjefil. Disse to kan direkte indlæses i QGIS, fx vha. *drag-and-drop*.
Nedenfor ses hvordan nettet i eksemplet ovenfor ser ud. Der er en række punkter
der er målt imellem, samt et singulært punkt; det nyetablerede ved Hjortholmvej 19.

.. image:: figures/QGIS.PNG
  :width: 800
  :alt: Netopbygning vist i QGIS
