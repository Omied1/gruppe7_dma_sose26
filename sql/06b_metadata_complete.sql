-- =============================================================================
-- 06b_metadata_complete.sql
-- Erweiterung des Metadatenmanagements auf ALLE Spalten der SQL-Datenbank.
--
-- Hintergrund: Die Aufgabenstellung verlangt explizit
-- "Bestimmen Sie für JEDE Ihrer Spalten in der SQL-Datenbank das Skalenniveau".
-- 06_create_metadata_tables.sql lieferte nur eine Stichprobe (33 Spalten).
-- Dieses Skript ergänzt sämtliche fehlenden Tabellen- und Spalten-Einträge,
-- inkl. DWH-Sternschema und MDM-Internals.
--
-- Idempotent durch ON CONFLICT-Klauseln.
--
-- Voraussetzung: 06_create_metadata_tables.sql wurde ausgeführt.
-- Ausführung:    psql -h localhost -U user -d logistics -f 06b_metadata_complete.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- A) Fehlende Tabellen registrieren
-- -----------------------------------------------------------------------------
INSERT INTO meta.tables (system_id, schema_name, table_name, description, data_category, source_event)
SELECT s.system_id, t.schema_name, t.table_name, t.description, t.data_category, t.source_event
FROM (
    VALUES
    -- ERP-Erweiterung
    ('ERP', 'erp', 'document_references',  'Referenzen auf MinIO-Dokumente (Bucket+Objektpfad pro Entität)', 'METADATEN',     NULL),
    -- DWH-Sternschema
    ('DWH', 'dwh', 'dim_customer',         'Kunden-Dimension (denormalisiert aus erp.customers)',             'ANALYTIK',      NULL),
    ('DWH', 'dwh', 'dim_product',          'Produkt-Dimension mit eingefalteten Lieferantenattributen',       'ANALYTIK',      NULL),
    ('DWH', 'dwh', 'dim_supplier',         'Lieferanten-Dimension',                                           'ANALYTIK',      NULL),
    ('DWH', 'dwh', 'dim_carrier',          'Carrier-Dimension (Transportdienstleister)',                      'ANALYTIK',      NULL),
    ('DWH', 'dwh', 'dim_supply_chain_node','Knoten-Dimension der Supply Chain',                               'ANALYTIK',      NULL),
    ('DWH', 'dwh', 'dim_date',             'Date Spine (2025-2027, 1095 Tage)',                               'ANALYTIK',      NULL),
    ('DWH', 'dwh', 'dim_delivery_status',  'Lieferstatus-Dimension (SUCCESSFUL/DELAYED/FAILED/IN_TRANSIT)',   'ANALYTIK',      NULL),
    ('DWH', 'dwh', 'fact_fulfillment',     'Faktentabelle: 1 Zeile pro Transport-Hop',                        'ANALYTIK',      NULL)
) AS t(system_code, schema_name, table_name, description, data_category, source_event)
JOIN meta.systems s ON s.system_code = t.system_code
ON CONFLICT (schema_name, table_name) DO NOTHING;

-- -----------------------------------------------------------------------------
-- B) Regelbasierte Klassifikation aller Spalten
-- Skalenniveaus nach Stevens (1946):
--   NOMINAL  - IDs, Codes, Namen, Status, Typ (Kategorien ohne Reihenfolge)
--   ORDINAL  - Priorität (LOW<NORMAL<HIGH), Datumsteile mit Reihenfolge
--   INTERVAL - Temperatur, Koordinaten, Timestamps (kein natürlicher Nullpunkt)
--   RATIO    - Mengen, Preise, Minuten, Geschwindigkeit, Sequenzen
-- -----------------------------------------------------------------------------
WITH all_cols AS (
    SELECT
        c.table_schema,
        c.table_name,
        c.column_name,
        UPPER(c.data_type)              AS pg_data_type,
        (c.is_nullable = 'YES')         AS is_nullable,
        c.ordinal_position
    FROM information_schema.columns c
    WHERE c.table_schema IN ('erp','wms','tms','mdm','dwh')
      -- ETL-Metaspalten ausschließen (haben kein fachliches Skalenniveau)
      AND c.column_name NOT IN ('created_at','source_event','etl_loaded_at','etl_source')
),
classified AS (
    SELECT
        ac.*,
        -- PK-Erkennung anhand des SERIAL/INTEGER-PK-Namensmusters
        (ac.column_name LIKE '%_id'  OR ac.column_name LIKE '%_sk')         AS looks_like_id,
        -- Skalen-Klassifikation per Pattern-Matching
        CASE
            -- Boolesche Flags sind kategorisch
            WHEN ac.pg_data_type = 'BOOLEAN' THEN 'NOMINAL'

            -- ORDINAL: Priorität und Datumsteile mit natürlicher Reihenfolge
            WHEN ac.column_name = 'delivery_priority'
              OR ac.column_name = 'delivery_priority_code'
              OR ac.column_name IN ('year','quarter','month','week_of_year',
                                    'day_of_month','day_of_week','month_name','day_name')
                THEN 'ORDINAL'

            -- INTERVAL: Temperatur, Koordinaten, Timestamps, Datumsangaben
            WHEN ac.column_name LIKE '%temperature%'
              OR ac.column_name IN ('latitude','longitude')
              OR ac.column_name LIKE '%_at'
              OR ac.column_name LIKE '%_timestamp'
              OR ac.column_name LIKE '%_arrival'
              OR ac.pg_data_type = 'TIMESTAMP WITHOUT TIME ZONE'
              OR ac.pg_data_type = 'DATE'
                THEN 'INTERVAL'

            -- RATIO: alle echten Verhältnisgrößen mit natürlichem Nullpunkt
            WHEN ac.column_name IN ('quantity','unit_price','total_value',
                                    'delay_minutes','speed_kmh','sequence_order',
                                    'num_supply_chain_hops','quality_score',
                                    'avg_temperature')
                THEN CASE
                    -- Bonus: avg_temperature ist INTERVAL, nicht RATIO (kein absoluter Nullpunkt)
                    WHEN ac.column_name = 'avg_temperature' THEN 'INTERVAL'
                    ELSE 'RATIO'
                END

            -- Date-Surrogate-Key: numerisch wie YYYYMMDD - geordnet, daher ORDINAL
            WHEN ac.column_name = 'date_sk' THEN 'ORDINAL'

            -- Default: alles andere ist nominal (IDs, Codes, Namen, Status, Typen, Texte)
            ELSE 'NOMINAL'
        END AS scale_level,

        -- Data Category aus der zugehörigen Tabelle erben
        (SELECT data_category FROM meta.tables mt
          WHERE mt.schema_name = ac.table_schema AND mt.table_name = ac.table_name
        ) AS data_category,

        -- Beschreibung generieren
        CASE ac.column_name
            WHEN 'latitude'  THEN 'WGS84-Breitengrad (-90 bis 90)'
            WHEN 'longitude' THEN 'WGS84-Längengrad (-180 bis 180)'
            WHEN 'temperature' THEN 'Containertemperatur in °C; Soll 10-15°C (Kühlkette)'
            WHEN 'avg_temperature' THEN 'Durchschnittstemperatur in °C über alle Knoten dieser Lieferung'
            WHEN 'delay_minutes' THEN 'Verzögerung in Minuten (0 = pünktlich)'
            WHEN 'quantity' THEN 'Mengeneinheiten (Karton, Stück, Einheit)'
            WHEN 'unit_price' THEN 'Einzelpreis in EUR'
            WHEN 'total_value' THEN 'Gesamtwert in EUR (quantity * unit_price)'
            WHEN 'delivery_priority' THEN 'Lieferpriorität: LOW < NORMAL < HIGH'
            WHEN 'sequence_order' THEN 'Reihenfolge im Supply-Chain-Flow (1-7)'
            ELSE NULL
        END AS description,

        -- Qualitätsregel generieren
        CASE
            WHEN ac.column_name = 'temperature' OR ac.column_name LIKE '%temperature' THEN 'Soll 10-15°C; Abweichungen = Kühlkettenbruch'
            WHEN ac.column_name = 'latitude'    THEN 'BETWEEN -90 AND 90'
            WHEN ac.column_name = 'longitude'   THEN 'BETWEEN -180 AND 180'
            WHEN ac.column_name = 'delay_minutes' THEN '>= 0; > 30 min = SLA-Verletzung'
            WHEN ac.column_name = 'quantity'    THEN '> 0 (negative Mengen unzulässig)'
            WHEN ac.column_name = 'unit_price'  THEN '> 0 EUR'
            WHEN ac.column_name = 'delivery_priority' THEN 'IN (LOW, NORMAL, HIGH)'
            WHEN ac.column_name = 'delivery_status'   THEN 'IN (SUCCESSFUL, DELAYED, FAILED)'
            WHEN ac.column_name LIKE '%_code'   THEN 'Format <KÜRZEL>-NNN (z.B. BAN-101)'
            WHEN ac.column_name LIKE '%_reference' OR ac.column_name LIKE '%_identifier'
                                                THEN 'UUID-basiert oder fachliches Eindeutigkeitskriterium'
            ELSE NULL
        END AS quality_rule
    FROM all_cols ac
)
INSERT INTO meta.columns
    (table_id, column_name, data_type, description, data_category, scale_level,
     quality_rule, is_nullable, is_pk, is_fk)
SELECT
    mt.table_id,
    cl.column_name,
    cl.pg_data_type,
    cl.description,
    cl.data_category,
    cl.scale_level,
    cl.quality_rule,
    cl.is_nullable,
    (cl.column_name = mt.table_name || '_id' OR cl.column_name = mt.table_name || '_sk'
     OR cl.column_name IN ('processing_id','item_id','position_id','completion_id',
                           'delivery_id','sku_id','batch_id','mapping_id','golden_id',
                           'entity_type_id','column_id','table_id','system_id','ref_id',
                           'fulfillment_sk','status_sk','node_sk','date_sk')) AS is_pk,
    (cl.looks_like_id AND cl.column_name NOT IN ('order_id','processing_id','item_id',
                                                  'position_id','completion_id','delivery_id',
                                                  'sku_id','batch_id','shipment_id_pk',
                                                  'mapping_id','golden_id','entity_type_id',
                                                  'column_id','table_id','system_id','ref_id',
                                                  'fulfillment_sk')) AS is_fk
FROM classified cl
JOIN meta.tables mt ON mt.schema_name = cl.table_schema
                   AND mt.table_name  = cl.table_name
WHERE cl.data_category IS NOT NULL
ON CONFLICT (table_id, column_name) DO NOTHING;

-- -----------------------------------------------------------------------------
-- C) Nachweis-Queries
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    total_cols INT;
    covered    INT;
BEGIN
    SELECT COUNT(*) INTO total_cols FROM information_schema.columns
     WHERE table_schema IN ('erp','wms','tms','mdm','dwh')
       AND column_name NOT IN ('created_at','source_event','etl_loaded_at','etl_source');
    SELECT COUNT(*) INTO covered FROM meta.columns;
    RAISE NOTICE 'Metadaten-Abdeckung: % von % Spalten klassifiziert (%.1f%%)',
                 covered, total_cols, (100.0 * covered / total_cols);
END $$;
