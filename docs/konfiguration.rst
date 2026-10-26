.. _konfigurationsfil:

Konfigurationsfil
=================

Konfigurationsfilen er en INI fil, der er struktureret på følgende
måde:


.. code-block:: ini

    [general]
    default_connection = prod
    niv_open_files = true
    monochrome = false

    [prod_connection]
    password = <adgangskode>
    username = <brugernavn>
    hostname = <netværksadresse>
    method = <database|service>
    database = <databasenavn>
    service = <servicenavn>
    schema = <schema>

    [test_connection]
    password = <adgangskode>
    username = <brugernavn>
    hostname = <netværksadresse>
    method = <database|service>
    database = <databasenavn>
    service = <servicenavn>
    schema = <schema>


Under Windows placeres konfigurationsfilen i en af følgende stier::

    C:\Users\<brugernavn>\fire.ini
    C:\Users\Default\AppData\Local\fire\fire.ini

og på et UNIX-baseret system placeres filen et af følgende steder::

    home/<brugernavn>/fire.ini
    home/<brugernavn>/.fire.ini
    /etc/fire.ini
