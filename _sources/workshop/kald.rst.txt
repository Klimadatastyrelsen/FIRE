.. _kald:

Generelle kommandokald i linjen
-----------------------------------------------------

Navigation i terminalen
+++++++++++++++++++++++++

Her følger en kort liste over hvordan man i Windows navigerer rundt på sin pc
vha. en terminal (fx miniconda eller Cmder) og kommandoer på linjen her.

====================  ===========================================  ===========================================
**Kommando**          **Beskrivelse**                              **Eksempel på brug**
--------------------  -------------------------------------------  -------------------------------------------
``dir``               Oplist mapper og filer med detaljer          ``dir``
``cd <dir>``          Skift mappe (change directory)               ``cd Users\b031422\Desktop``
``cd ..``             Skift mappe et niveau op                     ``cd ..``
``cd\``               Hop til roden af server                      ``cd\``
``<Drev>:``           Skift drev (uafh. af aktuel placering)       ``F:``
``md <dir>``          Opret ny mappe (make directory)              ``md TEST``
``vim <fil>``         Opret ny asciifil (her vist med vim)         ``vim TEST\test``
``cp <fil1> <fil2>``  Kopier (copy) en given *fil1* til *fil2*     ``cp test ..\testkopi``
``mv <fil1> <fil2>``  Flyt (move) en given *fil1* til *fil2*       ``mv test ..\.``
``rm <fil>``          Slet (remove) en given *fil*                 ``rm test``
``rmdir <dir>``       Slet tom mappe (remove directory)            ``rmdir TEST``
``*``                 Indikerer *alt*                              ``rm TEST\*``
``.``                 Indikerer den aktuelle placering             ``cp TEST\test .``
``|`` eller ``>``     Information pipes videre i kommandokaldet    ``cat test1 test2 > testsamlet``
====================  ===========================================  ===========================================

I flere terminaler kan unix-kommandoer også genkendes, fx. ``ls`` (``dir`` i Windows), ``mkdir`` (``md`` i Windows)
osv., dog husk at man på unix benytter slash, ``/``, mens man på Windows benytter backslash, ``\``.

Hvis en sti er skrevet helt ud med ``/``, kan Windows dog godt genkende og oversætte
til ``\``, men autocomplete funktionen *tab* fungerer ikke.
Det skyldes, at Windows læser ``/`` som en "escape character"-funktion, som man kan
sætte foran specielle tegn eller mellemrum, så karakteren læses korrekt, og ikke
fx som et mellemrum i kommandolinjen.

I de fleste terminaler (fx PuTTY, UltraEdit, miniconda...) fungerer *tab* som en
autocomplete. Dvs. man kan starte på at skrive et mappenavn eller filnavn, og
derefter trykke på tab. Terminalen vil da liste eller cykle igennem de givne
muligheder man har. Det er meget praktisk ved især lange fil- og mappenavne.

Øvelse
^^^^^^^^^^^^^^^^^^^

Prøv selv at navigér rundt i terminalen og forsøg fx:

1. at lave to mapper
2. at oprette filer
3. at flytte filer rundt mellem mapper
4. at rydde op efter jer selv ved at slette filer og mapper
5. at kopier en hel mappe og dens undermapper med indhold over et andet sted på
   drevet (hint: ``/s`` er et eksempel på en parameter, der kan tilføjes kommandolinjen.
   Søg selv videre på nettet)


Diverse programmer
+++++++++++++++++++++++++++++++++++++++

Nedenfor følger en liste over brugbare standardprogrammers anvendelse i terminalen. Det kræver dog, at
programmerne er installeret i dit environment, før du kan bruge dem. Til det kan man bruge ``conda search``,
og derefter ``conda install``

.. code-block::

   (fire) C:\FIRE> conda install -c <channel> <package>

=============  ==========================================================  ===========================================
**Program**    **Beskrivelse**                                             **Eksempel på brug**
-------------  ----------------------------------------------------------  -------------------------------------------
``echo``       Gentag input på skærmen, som kan pipes videre, fx til proj  ``echo 12.4 55.8 36 | cct +proj=cart``
``grep``       Søg efter bestemte udtryk i asciitekst og print til skærm   ``grep -n DK test1``
``less``       Vis indholdet i en ascii-fil (ikke til redigering)          ``less test1``
``type``       Sammensæt flere filer til en                                ``type test1 test2>test3``
``vim``        Tekstbehandlingsprogram, som notesblok, Notepad++ osv.      ``vim test1``
=============  ==========================================================  ===========================================

Alle programmer kan yderligere udforskes ved at bruge parameteren ``--help``, fx

.. code-block::

   (fire) C:\FIRE> grep --help
