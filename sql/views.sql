-- OM VIEWS I FIRE
-- ---------------
--
-- En række materialized views er oprettet i FIRE-databasen med henblik på at
-- gøre databasens indhold lettere tilgængeligt i et GIS-program. For at
-- databasens geometrier er praktisk anvendelige, er det nødvendigt at bygge et
-- spatialt index over dem. Det lader sig i Oracle kun gøre på materialized
-- views. Materialized views opdateres ikke automatisk på samme måde som
-- almindelige views. For at holde informationerne relativt friske opdateres de
-- materialiserede views en gang i døgnet.


-- ÆNDRING AF VIEWS
-------------------
-- Ved ændring af queries i views er det nødvendigt først at
-- fjerne det
--
--   DROP MATERIALIZED VIEW v_view;
--
-- og dernæst oprette det med nyt indhold
--
--   CREATE MATERIALIZED VIEW v_view ...
--
-- Når viewet er oprettet igen skal der desuden tilføjes et
-- nyt spatialt index, eksempelvis
--
--   CREATE INDEX v_view_geometri_idx
--	 ON v_view (geometri)
-- 	 INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

-- DEBUGGING
------------
-- Ved debugging af views kan følgende queries være nyttige.
--
-- Oversigt over materialized views og deres status
--
--		SELECT * FROM user_mviews ORDER BY mview_name;
--
-- Oversigt over registrerede tabeller og views med geometrier
--
-- 		SELECT * FROM user_sdo_geom_metadata;
--
-- Oversigt over spatiale index på tabeller og views
--
--		SELECT * FROM user_sdo_index_info;


-- V_FIKSPUNKTER_DK
--
-- Danske fikspunkter til brug i den kommunale vedligehold etc
CREATE MATERIALIZED VIEW v_fikspunkter_dk
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
  landsnr AS (
    SELECT infotypeid id
    FROM punktinfotype
    WHERE infotype = 'IDENT:landsnr'
  ),
  landsnumre AS (
    SELECT
      pi.punktid punktid,
	  -- I tilfælde af flere landsnumre er registret. De *bør* der ikke være,
	  -- men det kan ske og derfor er det smart med en safe-guard
      MIN(tekst) KEEP (DENSE_RANK FIRST ORDER BY tekst) landsnummer
    FROM punktinfo pi, landsnr
    WHERE
        pi.infotypeid = landsnr.id
      AND
        pi.registreringtil IS NULL
    GROUP BY pi.punktid
  ),
  gi_ident AS (
	SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
	JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
	WHERE pit.infotype='IDENT:GI' AND pi.registreringtil IS NULL
  ),
  -- punkter med følgende attributter er uønskede (listen bør korrespondere med "fire niv udtræk-revision")
  irrelevantpkt AS (
    SELECT infotypeid id
    FROM punktinfotype
    WHERE infotype IN (
    	'ATTR:MV_punkt',
    	'ATTR:hjælpepunkt',
    	'ATTR:teknikpunkt',
    	'ATTR:tabtgået',
    	'REGION:EE',
    	'REGION:FO',
    	'REGION:GL',
    	'REGION:SE',
    	'REGION:SJ'
    )
  ),
  irrelevantepunkter AS (
    SELECT pi.punktid
    FROM punktinfo pi, irrelevantpkt
    WHERE
        pi.infotypeid IN irrelevantpkt.id
      AND
        pi.registreringtil IS NULL
    ),
  -- geometrier
  geometrier AS (
    SELECT go.geometri, go.punktid
    FROM geometriobjekt go
    WHERE go.registreringtil IS NULL
  ),
  -- koordinater
  dvr90 AS (
    SELECT sridid id
    FROM sridtype
    WHERE sridtype.srid = 'EPSG:5799'
  ),
  koter AS (
    SELECT k.z, k.sz, k.t, k.transformeret, k.punktid
    FROM koordinat k, dvr90
    WHERE
        k.registreringtil IS NULL
      AND
        k.sridid = dvr90.id
  ),
  beskrivelser AS (
	SELECT pi.punktid, pi.tekst FROM punktinfo pi
	JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
	WHERE pit.infotype='ATTR:beskrivelse' AND pi.registreringtil IS NULL
  ),
  afmaerkning AS (
	SELECT pi.punktid, LISTAGG(pi.tekst, '; ') WITHIN GROUP(ORDER BY pi.tekst) tekst
	FROM punktinfo pi
	JOIN punktinfotype pit ON pit.infotypeid = pi.infotypeid
	WHERE
			pit.infotype LIKE 'AFM:%'
		AND
			pit.anvendelse = 'TEKST'
		AND
			pi.registreringtil IS NULL
	GROUP BY pi.punktid
  ),
  terraenhoejde AS (
	SELECT pi.punktid, pi.tal h
	FROM punktinfo pi
	JOIN punktinfotype pit ON pit.infotypeid = pi.infotypeid
	WHERE
		pit.infotype = 'AFM:højde_over_terræn'
	AND
		pi.registreringtil IS NULL
  ),
  restricted AS (
	SELECT pi.punktid, 'TRUE' AS restricted
	FROM punktinfo pi
	JOIN punktinfotype pit ON pit.infotypeid = pi.infotypeid
	WHERE
		pit.infotype = 'ATTR:restricted'
	AND
		pi.registreringtil IS NULL
  )
SELECT
  geometrier.geometri geometri,
  p.id punktid,
  p.registreringfra as oprettelsesdato,
  landsnumre.landsnummer landsnr,
  gi_ident.ident gi_nr,
  koter.z dvr90_kote,
  koter.t dvr90_t,
  koter.sz kotespredning,
  koter.transformeret transformeret,
  beskrivelser.tekst beskrivelse,
  afmaerkning.tekst afmaerkning,
  terraenhoejde.h terraenhoejde,
  restricted.restricted restricted
FROM punkt p
JOIN landsnumre ON landsnumre.punktid = p.id
JOIN geometrier ON geometrier.punktid = p.id
-- ikke alle punkter har beskrivelse m.m.
LEFT JOIN gi_ident ON gi_ident.punktid = p.id
LEFT JOIN beskrivelser ON beskrivelser.punktid = p.id
LEFT JOIN afmaerkning ON afmaerkning.punktid = p.id
LEFT JOIN terraenhoejde ON terraenhoejde.punktid = p.id
LEFT JOIN restricted ON restricted.punktid = p.id
LEFT JOIN koter ON koter.punktid = p.id
LEFT JOIN irrelevantepunkter ON irrelevantepunkter.punktid = p.id
WHERE
    p.registreringtil IS NULL
  AND
    irrelevantepunkter.punktid IS NULL -- vi sorterer irrelevante punkter fra
  AND
    SDO_INSIDE(
      geometrier.geometri,
      SDO_GEOMETRY(
        2003,
        4326,
        NULL,
        MDSYS.SDO_ELEM_INFO_ARRAY(1,1003,3),
        SDO_ORDINATE_ARRAY(3,54,16,59) -- cirka bounding box for Danmark
      )
    ) = 'TRUE'
;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_FIKSPUNKTER_DK',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', -180.0000, 180.0000, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', -90.0000, 90.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_fikspunkter_dk_geometri_idx
ON v_fikspunkter_dk (geometri)
INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

-- V_CORS_DK
--
-- Danske CORS stationer (NET:CORS), inklusiv
--  ETRS89 koordinater
--  DVR90 koter
CREATE MATERIALIZED VIEW v_cors_dk
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
    punkter AS (
        SELECT pi.punktid FROM punktinfo pi
        JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
        WHERE pit.infotype='NET:CORS' AND pi.registreringtil IS NULL
    ),
    gnss_ident AS (
        SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
        JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
        WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
    ),
    landsnr AS (
        SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
        JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
        WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
    ),
    etrs89 AS (
        SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
        JOIN sridtype st ON k.sridid=st.sridid
        WHERE st.srid = 'EPSG:4937' AND k.registreringtil IS NULL
    ),
    dvr90 AS (
        SELECT k.punktid, k.t, k.z FROM koordinat k
        JOIN sridtype st ON k.sridid=st.sridid
        WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
    ),
    geometrier AS (
        SELECT geometri, punktid FROM geometriobjekt go
        WHERE go.registreringtil IS NULL
    ),
    tabtgaaet AS (
        SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
        JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
        WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
    ),
    klasse_a AS (
        SELECT pi.punktid, 'TRUE' AS klasse_a FROM punktinfo pi
        JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
        WHERE pit.infotype='ATTR:CORSKlasseA' AND pi.registreringtil IS NULL
    )
SELECT
    geometrier.geometri,
    gnss_ident.ident GNSS_NAVN,
    landsnr.ident LANDSNR,
    klasse_a.klasse_a KLASSE_A,
    etrs89.t  ETRS89_T,
    etrs89.x  ETRS89_LON,
    etrs89.y  ETRS89_LAT,
    etrs89.z  ETRS89_ELLPSH,
    dvr90.t   DVR90_T,
    dvr90.z   DVR90_KOTE
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN etrs89 ON punkter.punktid=etrs89.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
LEFT JOIN klasse_a ON punkter.punktid=klasse_a.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_CORS_DK',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_cors_dk_geometri_idx ON v_cors_dk (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

-- TAPAS PUNKTER
CREATE MATERIALIZED VIEW v_tapas
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:TAPAS' AND pi.registreringtil IS NULL
	),
	gnss_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	etrs89 AS (
		SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:4937' AND k.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	gnss_ident.ident GNSS_NAVN,
	landsnr.ident LANDSNR,
	etrs89.t  ETRS89_T,
	etrs89.x  ETRS89_LON,
	etrs89.y  ETRS89_LAT,
	etrs89.z  ETRS89_ELLPSH,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN etrs89 ON punkter.punktid=etrs89.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_TAPAS',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_tapas_geometri_idx ON v_tapas (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

-- 5D PUNKTER
CREATE MATERIALIZED VIEW v_5d_punkter
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:5D' AND pi.registreringtil IS NULL
	),
	gnss_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	etrs89 AS (
		SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:4937' AND k.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	gnss_ident.ident GNSS_NAVN,
	landsnr.ident LANDSNR,
	etrs89.t  ETRS89_T,
	etrs89.x  ETRS89_LON,
	etrs89.y  ETRS89_LAT,
	etrs89.z  ETRS89_ELLPSH,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN etrs89 ON punkter.punktid=etrs89.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_5D_PUNKTER',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_5d_punkter_geometri_idx ON v_5d_punkter (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');


-- 10KM PUNKTER
CREATE MATERIALIZED VIEW v_10km_punkter
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:10KM' AND pi.registreringtil IS NULL
	),
	gnss_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	etrs89 AS (
		SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:4937' AND k.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	gnss_ident.ident GNSS_NAVN,
	landsnr.ident LANDSNR,
	etrs89.t  ETRS89_T,
	etrs89.x  ETRS89_LON,
	etrs89.y  ETRS89_LAT,
	etrs89.z  ETRS89_ELLPSH,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN etrs89 ON punkter.punktid=etrs89.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_10KM_PUNKTER',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_10km_punkter_geometri_idx ON v_10km_punkter (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');


-- DMI Vandstandsmålere
CREATE MATERIALIZED VIEW v_dmi_vandstandsmaalere
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:DMI' AND pi.registreringtil IS NULL
	),
	gnss_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	etrs89 AS (
		SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:4937' AND k.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	landsnr.ident LANDSNR,
	gnss_ident.ident GNSS_NAVN,
	etrs89.t  ETRS89_T,
	etrs89.x  ETRS89_LON,
	etrs89.y  ETRS89_LAT,
	etrs89.z  ETRS89_ELLPSH,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN etrs89 ON punkter.punktid=etrs89.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_DMI_VANDSTANDSMAALERE',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_dmi_vandstandsmaalere_geometri_idx ON v_dmi_vandstandsmaalere (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

-- KDI vandstandsmålere
CREATE MATERIALIZED VIEW v_kdi_vandstandsmaalere
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:KDI' AND pi.registreringtil IS NULL
	),
	gnss_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	etrs89 AS (
		SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:4937' AND k.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	landsnr.ident LANDSNR,
	gnss_ident.ident GNSS_NAVN,
	etrs89.t  ETRS89_T,
	etrs89.x  ETRS89_LON,
	etrs89.y  ETRS89_LAT,
	etrs89.z  ETRS89_ELLPSH,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN etrs89 ON punkter.punktid=etrs89.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_KDI_VANDSTANDSMAALERE',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_kdi_vandstandsmaalere_geometri_idx ON v_kdi_vandstandsmaalere (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

-- DVR90 definerende vandstandsmålere
CREATE MATERIALIZED VIEW v_dvr90_vandstandsmaalere
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:DEFVAND' AND pi.registreringtil IS NULL
	),
	gnss_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	etrs89 AS (
		SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:4937' AND k.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	landsnr.ident LANDSNR,
	gnss_ident.ident GNSS_NAVN,
	etrs89.t  ETRS89_T,
	etrs89.x  ETRS89_LON,
	etrs89.y  ETRS89_LAT,
	etrs89.z  ETRS89_ELLPSH,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN etrs89 ON punkter.punktid=etrs89.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_DVR90_VANDSTANDSMAALERE',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_dvr90_vandstandsmaalere_geometri_idx ON v_dvr90_vandstandsmaalere (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

-- GPSNet PUNKTER
CREATE MATERIALIZED VIEW v_gpsnet
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:GPSNET' AND pi.registreringtil IS NULL
	),
	gnss_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	ekstern_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:ekstern' AND pi.registreringtil IS NULL
	),
	etrs89 AS (
		SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:4937' AND k.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	dkcors AS (
		SELECT pi.punktid, 'TRUE' AS dkcors FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:CORS' AND pi.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	gnss_ident.ident GNSS_NAVN,
	landsnr.ident LANDSNR,
	ekstern_ident.ident EKSTERN_IDENT,
	dkcors.dkcors IN_DKCORS,
	etrs89.t  ETRS89_T,
	etrs89.x  ETRS89_LON,
	etrs89.y  ETRS89_LAT,
	etrs89.z  ETRS89_ELLPSH,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN ekstern_ident ON punkter.punktid=ekstern_ident.punktid
LEFT JOIN etrs89 ON punkter.punktid=etrs89.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
LEFT JOIN dkcors ON punkter.punktid=dkcors.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_GPSNET',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_gpsnet_geometri_idx ON v_gpsnet (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');


-- SmartNet PUNKTER
CREATE MATERIALIZED VIEW v_smartnet
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:SMARTNET' AND pi.registreringtil IS NULL
	),
	gnss_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	ekstern_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:ekstern' AND pi.registreringtil IS NULL
	),
	etrs89 AS (
		SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:4937' AND k.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	dkcors AS (
		SELECT pi.punktid, 'TRUE' AS dkcors FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:CORS' AND pi.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	gnss_ident.ident GNSS_NAVN,
	landsnr.ident LANDSNR,
	ekstern_ident.ident EKSTERN_IDENT,
	dkcors.dkcors IN_DKCORS,
	etrs89.t  ETRS89_T,
	etrs89.x  ETRS89_LON,
	etrs89.y  ETRS89_LAT,
	etrs89.z  ETRS89_ELLPSH,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN ekstern_ident ON punkter.punktid=ekstern_ident.punktid
LEFT JOIN etrs89 ON punkter.punktid=etrs89.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
LEFT JOIN dkcors ON punkter.punktid=dkcors.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_SMARTNET',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_smartnet_geometri_idx ON v_smartnet (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

-- RTKConnect PUNKTER
CREATE MATERIALIZED VIEW v_rtkconnect
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:RTKCONNECT' AND pi.registreringtil IS NULL
	),
	gnss_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	ekstern_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:ekstern' AND pi.registreringtil IS NULL
	),
	etrs89 AS (
		SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:4937' AND k.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	dkcors AS (
		SELECT pi.punktid, 'TRUE' AS dkcors FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:CORS' AND pi.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	gnss_ident.ident GNSS_NAVN,
	landsnr.ident LANDSNR,
	ekstern_ident.ident EKSTERN_IDENT,
	dkcors.dkcors IN_DKCORS,
	etrs89.t  ETRS89_T,
	etrs89.x  ETRS89_LON,
	etrs89.y  ETRS89_LAT,
	etrs89.z  ETRS89_ELLPSH,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN ekstern_ident ON punkter.punktid=ekstern_ident.punktid
LEFT JOIN etrs89 ON punkter.punktid=etrs89.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
LEFT JOIN dkcors ON punkter.punktid=dkcors.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_RTKCONNECT',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_rtkconnect_geometri_idx ON v_rtkconnect (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

-- Tabtgåede punkter
CREATE MATERIALIZED VIEW v_tabte_punkter
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid, pi.registreringfra tabstidspunkt FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	beskrivelser AS (
		SELECT pi.punktid, pi.tekst tekst FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:beskrivelse' AND pi.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	landsnr.ident landsnr,
	beskrivelser.tekst,
	punkter.tabstidspunkt
FROM punkter
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN beskrivelser ON punkter.punktid=beskrivelser.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_TABTE_PUNKTER',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_tabte_punkter_geometri_idx ON v_tabte_punkter (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

--  GNET Stationer
CREATE MATERIALIZED VIEW v_gnet
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:GNET' AND pi.registreringtil IS NULL
	),
	gnss_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GNSS' AND pi.registreringtil IS NULL
	),
	townsite AS (
		SELECT punktid, 'TOWN' AS sitetype
		FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:townsite' AND pi.registreringtil IS NULL
	),
	remotesite AS (
		SELECT punktid, 'REMOTE' AS sitetype
		FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:remotesite' AND pi.registreringtil IS NULL
	),
	igs AS (
		SELECT punktid, 'IGS' AS sitetype
		FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='NET:IGS' AND pi.registreringtil IS NULL
	),
	afm AS (
		SELECT punktid, pi.tekst afm
		FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='AFM:4650' AND pi.registreringtil IS NULL
	),
	gr96 AS (
		SELECT k.punktid,k.t,k.x,k.y,k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'GL:GR96(2021)' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	gnss_ident.ident GNSS_NAVN,
	COALESCE(igs.sitetype, townsite.sitetype, remotesite.sitetype) AS SITE_TYPE,
	afm.afm AS AFMÆRKNING,
	gr96.t  GR96_T,
	gr96.x  GR96_X,
	gr96.y  GR96_Y,
	gr96.z  GR96_Z
FROM punkter
LEFT JOIN gnss_ident ON punkter.punktid=gnss_ident.punktid
LEFT JOIN gr96 ON punkter.punktid=gr96.punktid
LEFT JOIN townsite ON punkter.punktid=townsite.punktid
LEFT JOIN remotesite ON punkter.punktid=remotesite.punktid
LEFT JOIN afm ON punkter.punktid=afm.punktid
LEFT JOIN igs ON punkter.punktid=igs.punktid
LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid
WHERE tabtgaaet.tabtgaaet IS NULL;


INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_GNET',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', -180.0000, 180.0000, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', -90.0000, 90.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_gnet_geometri_idx ON v_gnet (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');


-- 3. præs observationer
CREATE MATERIALIZED VIEW v_pres3_obs AS
WITH
	gi_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GI' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	)
SELECT
	-- go1.geometri geometri_opstillingspunkt,
	-- go2.geometri geometri_sigtepunkt,
	COALESCE(og.ident, ol.ident) as opstillingspunkt_ident,
	COALESCE(sg.ident, sl.ident) as sigtepunkt_ident,
	sdo_geometry(
		2002,
		4326,
		NULL,
		sdo_elem_info_array (1,2,1),
		sdo_ordinate_array (go1.geometri.sdo_point.x, go1.geometri.sdo_point.y, go2.geometri.sdo_point.x, go2.geometri.sdo_point.y)) geometri,
	o.observationstidspunkt,
	o.value1 koteforskel,
	o.value2 nivlaengde,
	o.value3 antal_opstillinger,
	o.value4 eta1,
	o.value5 spredning,
	o.value6 centreringsfejl
FROM observation o
JOIN observationstype ot ON ot.observationstypeid=o.observationstypeid
JOIN geometrier go1 ON go1.PUNKTID=o.opstillingspunktid
JOIN geometrier go2 ON go2.PUNKTID=o.sigtepunktid
LEFT JOIN landsnr ol ON ol.punktid = o.opstillingspunktid
LEFT JOIN landsnr sl ON sl.punktid = o.sigtepunktid
LEFT JOIN gi_ident og ON og.punktid = o.opstillingspunktid
LEFT JOIN gi_ident sg ON sg.punktid = o.sigtepunktid
WHERE
	ot.observationstype='geometrisk_koteforskel'
	AND
	o.value7=3
;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_PRES3_OBS',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_pres3_obs_geometri_idx ON v_pres3_obs (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=line');

-- 2. præs observationer
CREATE MATERIALIZED VIEW v_pres2_obs AS
WITH
	gi_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GI' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	)
SELECT
	-- go1.geometri geometri_opstillingspunkt,
	-- go2.geometri geometri_sigtepunkt,
	COALESCE(og.ident, ol.ident) as opstillingspunkt_ident,
	COALESCE(sg.ident, sl.ident) as sigtepunkt_ident,
	sdo_geometry(
		2002,
		4326,
		NULL,
		sdo_elem_info_array (1,2,1),
		sdo_ordinate_array (go1.geometri.sdo_point.x, go1.geometri.sdo_point.y, go2.geometri.sdo_point.x, go2.geometri.sdo_point.y)) geometri,
	o.observationstidspunkt,
	o.value1 koteforskel,
	o.value2 nivlaengde,
	o.value3 antal_opstillinger,
	o.value4 eta1,
	o.value5 spredning,
	o.value6 centreringsfejl
FROM observation o
JOIN observationstype ot ON ot.observationstypeid=o.observationstypeid
JOIN geometrier go1 ON go1.PUNKTID=o.opstillingspunktid
JOIN geometrier go2 ON go2.PUNKTID=o.sigtepunktid
LEFT JOIN landsnr ol ON ol.punktid = o.opstillingspunktid
LEFT JOIN landsnr sl ON sl.punktid = o.sigtepunktid
LEFT JOIN gi_ident og ON og.punktid = o.opstillingspunktid
LEFT JOIN gi_ident sg ON sg.punktid = o.sigtepunktid
WHERE
	ot.observationstype='geometrisk_koteforskel'
	AND
	o.value7=2
;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_PRES2_OBS',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_pres2_obs_geometri_idx ON v_pres2_obs (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=line');


-- 1. præs observationer
CREATE MATERIALIZED VIEW v_pres1_obs AS
WITH
	gi_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GI' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	)
SELECT
	-- go1.geometri geometri_opstillingspunkt,
	-- go2.geometri geometri_sigtepunkt,
	COALESCE(og.ident, ol.ident) as opstillingspunkt_ident,
	COALESCE(sg.ident, sl.ident) as sigtepunkt_ident,
	sdo_geometry(
		2002,
		4326,
		NULL,
		sdo_elem_info_array (1,2,1),
		sdo_ordinate_array (go1.geometri.sdo_point.x, go1.geometri.sdo_point.y, go2.geometri.sdo_point.x, go2.geometri.sdo_point.y)) geometri,
	o.observationstidspunkt,
	o.value1 koteforskel,
	o.value2 nivlaengde,
	o.value3 antal_opstillinger,
	o.value4 eta1,
	o.value5 spredning,
	o.value6 centreringsfejl
FROM observation o
JOIN observationstype ot ON ot.observationstypeid=o.observationstypeid
JOIN geometrier go1 ON go1.PUNKTID=o.opstillingspunktid
JOIN geometrier go2 ON go2.PUNKTID=o.sigtepunktid
LEFT JOIN landsnr ol ON ol.punktid = o.opstillingspunktid
LEFT JOIN landsnr sl ON sl.punktid = o.sigtepunktid
LEFT JOIN gi_ident og ON og.punktid = o.opstillingspunktid
LEFT JOIN gi_ident sg ON sg.punktid = o.sigtepunktid
WHERE
	ot.observationstype='geometrisk_koteforskel'
	AND
	o.value7=1
;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_PRES1_OBS',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_pres1_obs_geometri_idx ON v_pres1_obs (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=line');


-- Alle nivellementobservationer inkl. diverse sagsinformationer.
CREATE MATERIALIZED VIEW v_alle_niv_obs
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	gi_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GI' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	sager AS (
		SELECT se.ID AS sagseventid, si.beskrivelse, sei.beskrivelse AS eventbeskrivelse, si.behandler, si.aktiv
		FROM SAGSEVENT se
		INNER JOIN SAGSINFO si ON se.SAGSID = si.SAGSID
		INNER JOIN sagseventinfo sei ON se.id = sei.sagseventid
		INNER JOIN (
			-- Tag højde for at visse sagsevents har flere aktive beskrivelser,
			-- hvilket førte til at der kom flere identiske observationer med i viewet.
			SELECT se.id, MAX(sei.OBJEKTID) AS id_max
			FROM SAGSEVENT se
			INNER JOIN sagseventinfo sei ON se.id = sei.sagseventid
			WHERE sei.REGISTRERINGTIL IS NULL
			GROUP BY se.ID
			) sei_max ON sei_max.id_max = sei.objektid
		WHERE si.registreringtil IS NULL
	)
SELECT
	COALESCE(og.ident, ol.ident) as opstillingspunkt_ident,
	COALESCE(sg.ident, sl.ident) as sigtepunkt_ident,
	sdo_geometry(
		2002,
		4326,
		NULL,
		sdo_elem_info_array (1,2,1),
		sdo_ordinate_array (go1.geometri.sdo_point.x, go1.geometri.sdo_point.y, go2.geometri.sdo_point.x, go2.geometri.sdo_point.y)) geometri,
	o.observationstidspunkt,
	o.value1 koteforskel,
	o.value2 nivlaengde,
	o.value3 antal_opstillinger,
	CASE o.observationstypeid WHEN 1 THEN o.value4 WHEN 2 THEN NULL     END AS eta1,
	CASE o.observationstypeid WHEN 1 THEN o.value5 WHEN 2 THEN o.value4 END AS spredning,
	CASE o.observationstypeid WHEN 1 THEN o.value6 WHEN 2 THEN o.value5 END AS centreringsfejl,
	ot.observationstype,
	CASE WHEN o.value7 IS NULL THEN 0 ELSE o.value7 END AS landsdækkende_nivellement,
	o.id,
	s.beskrivelse AS sagsbeskrivelse,
	s.eventbeskrivelse,
	s.behandler,
	s.aktiv AS er_aktiv
FROM observation o
JOIN observationstype ot ON ot.observationstypeid=o.observationstypeid
JOIN geometrier go1 ON go1.PUNKTID=o.opstillingspunktid
JOIN geometrier go2 ON go2.PUNKTID=o.sigtepunktid
LEFT JOIN landsnr ol ON ol.punktid = o.opstillingspunktid
LEFT JOIN landsnr sl ON sl.punktid = o.sigtepunktid
LEFT JOIN gi_ident og ON og.punktid = o.opstillingspunktid
LEFT JOIN gi_ident sg ON sg.punktid = o.sigtepunktid
LEFT JOIN sager s ON o.sagseventfraid = s.sagseventid
WHERE
	ot.observationstype IN ('geometrisk_koteforskel', 'trigonometrisk_koteforskel')
	AND o.fejlmeldt = 'false'
	AND o.registreringtil IS NULL
;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'v_alle_niv_obs',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_alle_niv_obs_geometri_idx ON v_alle_niv_obs (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=line');

-- Alt præcisionsnivellement. Filtreret ud fra skiftende præcisionskrav igennem tiden.
CREATE MATERIALIZED VIEW v_praecisionsnivellement
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	gi_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GI' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	)
SELECT
	COALESCE(og.ident, ol.ident) as opstillingspunkt_ident,
	COALESCE(sg.ident, sl.ident) as sigtepunkt_ident,
	sdo_geometry(
		2002,
		4326,
		NULL,
		sdo_elem_info_array (1,2,1),
		sdo_ordinate_array (go1.geometri.sdo_point.x, go1.geometri.sdo_point.y, go2.geometri.sdo_point.x, go2.geometri.sdo_point.y)) geometri,
	o.observationstidspunkt,
	o.value1 koteforskel,
	o.value2 nivlaengde,
	o.value3 antal_opstillinger,
	CASE o.observationstypeid WHEN 1 THEN o.value4 WHEN 2 THEN NULL     END AS eta1,
	CASE o.observationstypeid WHEN 1 THEN o.value5 WHEN 2 THEN o.value4 END AS spredning,
	CASE o.observationstypeid WHEN 1 THEN o.value6 WHEN 2 THEN o.value5 END AS centreringsfejl,
	ot.observationstype,
	CASE WHEN o.value7 IS NULL THEN 0 ELSE o.value7 END AS landsdækkende_nivellement
FROM observation o
JOIN observationstype ot ON ot.observationstypeid=o.observationstypeid
JOIN geometrier go1 ON go1.PUNKTID=o.opstillingspunktid
JOIN geometrier go2 ON go2.PUNKTID=o.sigtepunktid
LEFT JOIN landsnr ol ON ol.punktid = o.opstillingspunktid
LEFT JOIN landsnr sl ON sl.punktid = o.sigtepunktid
LEFT JOIN gi_ident og ON og.punktid = o.opstillingspunktid
LEFT JOIN gi_ident sg ON sg.punktid = o.sigtepunktid
WHERE
	(
		(ot.observationstype = 'geometrisk_koteforskel' and o.value5<=0.6) -- præcisionskrav for MGL
		OR (ot.observationstype = 'trigonometrisk_koteforskel' and o.value4<=1.5 and extract(year from o.observationstidspunkt) >= 2020) -- mtl præc krav efter 2020
		OR (ot.observationstype = 'trigonometrisk_koteforskel' and o.value4<=0.06 and extract(year from o.observationstidspunkt) < 2020) -- mtl præc krav før 2020
	)
	AND o.fejlmeldt = 'false'
	AND o.registreringtil IS NULL
;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'v_praecisionsnivellement',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_praecisionsnivellement_geometri_idx ON v_praecisionsnivellement (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=line');


-- Jessenpunkter
CREATE MATERIALIZED VIEW v_jessenpunkter
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT DISTINCT pi.punktid FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE (pit.infotype IN ('NET:jessen', 'IDENT:jessen'))
			AND pi.registreringtil IS NULL
	),
	jessenpunkter AS (
		SELECT ps.navn, COALESCE(ps.jessenpunktid, p.punktid) AS punktid, ps.jessenkoordinatid
		FROM punktsamling ps
		-- Vi medtager alle punkter som har attributten "NET:jessen" eller "IDENT:jessen".
		-- Hvis der er nogen af dem som ikke er tilknyttet en Punktsamling, så vil de
		-- stadig blive vist.
		FULL JOIN punkter p ON p.punktid = ps.jessenpunktid
		WHERE ps.registreringtil IS NULL
	),
	gi_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GI' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	jessennr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:jessen' AND pi.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	gi_ident.ident GI_IDENT,
	landsnr.ident LANDSNR,
	jessennr.ident JESSENNR,
	jessenpunkter.navn PUNKTSAMLINGSNAVN,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE,
	jessenkote.t   JESSENKOTE_T,
	jessenkote.z   JESSENKOTE,
	COALESCE(tabtgaaet.tabtgaaet, 'FALSE') AS tabtgaaet
FROM jessenpunkter
LEFT JOIN gi_ident ON jessenpunkter.punktid=gi_ident.punktid
LEFT JOIN landsnr ON jessenpunkter.punktid=landsnr.punktid
LEFT JOIN jessennr ON jessenpunkter.punktid=jessennr.punktid
LEFT JOIN dvr90 ON jessenpunkter.punktid=dvr90.punktid
LEFT JOIN koordinat jessenkote ON jessenpunkter.jessenkoordinatid=jessenkote.objektid
LEFT JOIN tabtgaaet ON jessenpunkter.punktid=tabtgaaet.punktid
JOIN geometrier ON jessenpunkter.punktid=geometrier.punktid;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_JESSENPUNKTER',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_jessenpunkter_geometri_idx ON v_jessenpunkter (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');


-- Tidsserier og Punkter i punktsamlinger
CREATE MATERIALIZED VIEW v_hoejdetidsserier
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT ps.objektid as punktsamlingsid, psp.punktid, ps.jessenpunktid, ps.jessenkoordinatid, ps.navn
		FROM punktsamling_punkt psp
		JOIN punktsamling ps ON psp.punktsamlingsid = ps.objektid
	),
	gi_ident AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:GI' AND pi.registreringtil IS NULL
	),
	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	jessennr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:jessen' AND pi.registreringtil IS NULL
	),
	koordinater AS (
		SELECT k.objektid AS koordinatid, k.punktid, k.t, k.z
		FROM koordinat k
	),
	tidsserier AS (
		SELECT t.punktid, t.punktsamlingsid, t.navn, t.formaal, tk.t, tk.kote
		FROM tidsserie t
		LEFT JOIN (
			SELECT tk.tidsserieobjektid,
				-- Tager den senete kote i tidsserien
				max(k.t) as T,
				max(k.z) keep (DENSE_RANK FIRST ORDER BY k.t DESC) AS kote
			FROM tidsserie_koordinat tk
			INNER JOIN koordinat k ON tk.koordinatobjektid = k.objektid
			GROUP BY tk.tidsserieobjektid
		) tk ON t.objektid = tk.tidsserieobjektid
		WHERE t.tstype = 2 AND t.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
	tabtgaaet AS (
		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	gi_ident.ident GI_IDENT,
	landsnr.ident LANDSNR,
	p.NAVN PUNKTSAMLINGSNAVN,
	t.navn TIDSSERIENAVN,
	t.formaal,
	t.kote AS TSKOTE, -- tidsseriens seneste kote
	t.t AS TSKOTE_T,  -- og tilsvarende tidspunkt
	jessennr.ident JESSENNR,
	jessenkoord.z   JESSENKOTE,   -- jessenpunktets kote
	jessenkoord.t   JESSENKOTE_T, -- og tilsvarende tidspunkt
	COALESCE(tabtgaaet.tabtgaaet, 'FALSE') AS tabtgaaet
FROM punkter p
LEFT JOIN tidsserier t ON p.punktsamlingsid = t.punktsamlingsid AND p.punktid = t.punktid
LEFT JOIN gi_ident ON p.punktid=gi_ident.punktid
LEFT JOIN landsnr ON p.punktid=landsnr.punktid
LEFT JOIN jessennr ON p.jessenpunktid=jessennr.punktid
LEFT JOIN koordinater jessenkoord ON p.jessenkoordinatid = jessenkoord.koordinatid
LEFT JOIN tabtgaaet ON p.punktid=tabtgaaet.punktid
LEFT JOIN geometrier ON p.punktid=geometrier.punktid;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_HOEJDETIDSSERIER',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_hoejdetidsserier_geometri_idx ON v_hoejdetidsserier (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');


-- Punktsamlinger (indeholder de samme punkter som v_hoejdetidsserier
-- men er her lavet som multigeometri)
CREATE MATERIALIZED VIEW v_punktsamlinger
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT punktid, jessenpunktid, jessenkoordinatid, ps.navn
		FROM punktsamling_punkt psp
		JOIN punktsamling ps ON psp.punktsamlingsid = ps.objektid
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	),
-- Vi vil gerne se de tabtgåede punkter. Derfor nedenstående er udkommenteret.
--	tabtgaaet AS (
--		SELECT pi.punktid, 'TRUE' AS tabtgaaet FROM punktinfo pi
--		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
--		WHERE pit.infotype='ATTR:tabtgået' AND pi.registreringtil IS NULL
--	),
	multigeometrier AS (
		SELECT punkter.navn,
			punkter.jessenpunktid,
			punkter.jessenkoordinatid,
			SDO_AGGR_UNION(SDOAGGRTYPE(geometrier.geometri, NULL)) AS multigeometri
		FROM punkter
		INNER JOIN geometrier ON punkter.punktid=geometrier.punktid
--		LEFT JOIN tabtgaaet ON punkter.punktid=tabtgaaet.punktid
--		WHERE tabtgaaet.tabtgaaet IS NULL
		GROUP BY punkter.navn, punkter.jessenpunktid, punkter.jessenkoordinatid
	),
	jessennr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:jessen' AND pi.registreringtil IS NULL
	),
	koordinater AS (
		SELECT k.objektid AS koordinatid, k.punktid, k.t, k.z
		FROM koordinat k
	)
SELECT
	multigeometrier.multigeometri,
	multigeometrier.NAVN AS PUNKTSAMLINGSNAVN,
	jessennr.ident JESSENNR,
	koordinater.z   JESSENKOTE,
	koordinater.t   JESSENKOTE_T
FROM multigeometrier
LEFT JOIN jessennr ON multigeometrier.jessenpunktid=jessennr.punktid
LEFT JOIN koordinater ON multigeometrier.jessenkoordinatid = koordinater.koordinatid;

INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_PUNKTSAMLINGER',
    'MULTIGEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

 CREATE INDEX v_punktsamlinger_multigeometri_idx ON v_punktsamlinger (multigeometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=multipoint');


-- Reflektorer, både Corner og CAT
CREATE MATERIALIZED VIEW v_reflektorer
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
	punkter AS (
		SELECT DISTINCT pi.punktid, infotype FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype IN ('ATTR:reflektor', 'ATTR:CAT')
			AND pi.registreringtil IS NULL
	),
	beskrivelser AS (
		SELECT pi.punktid, pi.tekst FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='ATTR:beskrivelse' AND pi.registreringtil IS NULL
  	),
  	landsnr AS (
		SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
		JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
		WHERE pit.infotype='IDENT:landsnr' AND pi.registreringtil IS NULL
	),
	dvr90 AS (
		SELECT k.punktid, k.t, k.z FROM koordinat k
		JOIN sridtype st ON k.sridid=st.sridid
		WHERE st.srid = 'EPSG:5799' AND k.registreringtil IS NULL
	),
	geometrier AS (
		SELECT geometri, punktid FROM geometriobjekt go
		WHERE go.registreringtil IS NULL
	)
SELECT
	geometrier.geometri,
	landsnr.ident LANDSNR,
	punkter.infotype,
	dvr90.t   DVR90_T,
	dvr90.z   DVR90_KOTE,
	beskrivelser.tekst beskrivelse
FROM punkter
LEFT JOIN landsnr ON punkter.punktid=landsnr.punktid
LEFT JOIN beskrivelser ON punkter.punktid = beskrivelser.punktid
LEFT JOIN dvr90 ON punkter.punktid=dvr90.punktid
JOIN geometrier ON punkter.punktid=geometrier.punktid;


INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_REFLEKTORER',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_reflektorer_geometri_idx ON v_reflektorer (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');

-- Alle punkter som har en LRL-kote
CREATE MATERIALIZED VIEW v_lrl
REFRESH ON DEMAND
START WITH SYSDATE NEXT SYSDATE + 1 / 24
AS
WITH
  landsnr AS (
    SELECT infotypeid id
    FROM punktinfotype
    WHERE infotype = 'IDENT:landsnr'
  ),
  landsnumre AS (
    SELECT
      pi.punktid punktid,
	  -- I tilfælde af flere landsnumre er registret. De *bør* der ikke være,
	  -- men det kan ske og derfor er det smart med en safe-guard
      MIN(tekst) KEEP (DENSE_RANK FIRST ORDER BY tekst) landsnummer
    FROM punktinfo pi, landsnr
    WHERE
        pi.infotypeid = landsnr.id
      AND
        pi.registreringtil IS NULL
    GROUP BY pi.punktid
  ),
  gi_ident AS (
	SELECT pi.punktid, pi.tekst ident FROM punktinfo pi
	JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
	WHERE pit.infotype='IDENT:GI' AND pi.registreringtil IS NULL
  ),
  -- punkter med følgende attributter er uønskede (listen bør korrespondere med "fire niv udtræk-revision")
  tabtgaaet AS (
    SELECT p.punktid
    FROM punktinfo p
    INNER JOIN punktinfotype pit ON p.infotypeid = pit.infotypeid
    WHERE pit.infotype = 'ATTR:tabtgået' AND p.registreringtil IS NULL
  ),
  -- geometrier
  geometrier AS (
    SELECT go.geometri, go.punktid
    FROM geometriobjekt go
    WHERE go.registreringtil IS NULL
  ),
  -- koordinater
  dvr90 AS (
    SELECT sridid id
    FROM sridtype
    WHERE sridtype.srid = 'EPSG:5799'
  ),
  koter AS (
    SELECT k.z, k.sz, k.t, k.transformeret, k.punktid
    FROM koordinat k, dvr90
    WHERE
        k.registreringtil IS NULL
      AND
        k.sridid = dvr90.id
  ),
  lrlkote AS (
    SELECT k.z, k.sz, k.t, k.punktid AS id
    FROM koordinat k
    WHERE k.registreringtil IS NULL
      AND k.sridid = 32 -- TS:LRL
  ),
  beskrivelser AS (
	SELECT pi.punktid, pi.tekst FROM punktinfo pi
	JOIN punktinfotype pit ON pi.infotypeid=pit.infotypeid
	WHERE pit.infotype='ATTR:beskrivelse' AND pi.registreringtil IS NULL
  )
SELECT
  geometrier.geometri geometri,
  p.id punktid,
  landsnumre.landsnummer landsnr,
  gi_ident.ident gi_nr,
  p.z AS lrl_kote,
  p.t AS lrl_t,
  koter.z dvr90_kote,
  koter.t dvr90_t,
  beskrivelser.tekst beskrivelse,
  CASE WHEN tabtgaaet.punktid IS NOT NULL THEN 'Tabtgået' ELSE NULL END AS tabtgået
FROM lrlkote p
JOIN landsnumre ON landsnumre.punktid = p.id
JOIN geometrier ON geometrier.punktid = p.id
-- ikke alle punkter har beskrivelse m.m.
LEFT JOIN gi_ident ON gi_ident.punktid = p.id
LEFT JOIN koter ON koter.punktid = p.id
LEFT JOIN beskrivelser ON beskrivelser.punktid = p.id
LEFT JOIN tabtgaaet ON tabtgaaet.punktid = p.id;


INSERT INTO
  user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES
  (
    'V_LRL',
    'GEOMETRI',
    MDSYS.SDO_DIM_ARRAY(
      MDSYS.SDO_DIM_ELEMENT('Longitude', 7.0, 16.0, 0.005),
      MDSYS.SDO_DIM_ELEMENT('Latitude', 54.0000, 59.0000, 0.005)
    ),
    4326
  );

CREATE INDEX v_lrl_geometri_idx ON v_lrl (geometri) INDEXTYPE IS MDSYS.SPATIAL_INDEX PARAMETERS('layer_gtype=point');
