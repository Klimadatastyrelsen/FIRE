.. _genfundet:

Genfinding af tabtgået fikspunkt
---------------------------------

Hvis et punkt der er meldt tabtgået genfindes er det muligt at fjernet
``ATTR:tabtgået`` attributten fra punktet. Det gøres som følger.

.. code-block:: none

    > fire niv opret-sag <sagsnavn> "<sagsbeskrivelse>"
    > fire niv udtræk-revision <sagsnavn> <fikspunkt>

Åben regneark og sæt ``x`` i linje med ATTR:tabtgået attribut for det genfundne punkt.
Gem og luk regnetarket.

.. code-block:: none

    > fire niv ilæg-revision <sagsnavn>
    > fire niv luk-sag <sagsnavn>

Når der sættes ``x`` i sluk-kolonnen så fjerner du den attribut.
