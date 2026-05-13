-- =============================================================================
-- 06_create_metadata_tables.sql
-- Metadatenmanagement-Schema für die Banana Supply Chain
--
-- Tabellen:
--   meta.systems       - Registrierte Quellsysteme (ERP, WMS, TMS, MDM, DWH)
--   meta.tables        - Tabellen-Metadaten (Schema, Name, Beschreibung, Kategorie)
--   meta.columns       - Spalten-Metadaten (Typ, Skalenniveau, Qualitätsregel)
--
-- Skalenniveaus (Stevens 1946):
--   NOMINAL    - Kategorien ohne Reihenfolge (z.B. Lieferstatus, Produktkategorie)
--   ORDINAL    - Kategorien mit Reihenfolge (z.B. delivery_priority: LOW < NORMAL < HIGH)
--   INTERVAL   - Numerisch mit gleichem Abstand, kein natürlicher Nullpunkt (z.B. Temperatur °C)
--   RATIO      - Numerisch mit natürlichem Nullpunkt (z.B. Menge, Preis, Verzögerung)
--
-- Voraussetzung: 01_create_schemas.sql muss vorher ausgeführt worden sein.
-- Ausführung:    psql -h localhost -U user -d logistics -f 06_create_metadata_tables.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Systeme-Referenztabelle
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta.systems (
    system_id       SERIAL          PRIMARY KEY,
    system_code     VARCHAR(10)     NOT NULL UNIQUE,
    system_name     VARCHAR(50)     NOT NULL,
    description     TEXT,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

INSERT INTO meta.systems (system_code, system_name, description) VALUES
    ('ERP',  'Enterprise Resource Planning', 'Stamm- und Bewegungsdaten: Lieferanten, Kunden, Produkte, Orders, Batches'),
    ('WMS',  'Warehouse Management System',  'Lagerverwaltung: SKUs, Knotenverarbeitungen, Supply-Chain-Knoten'),
    ('TMS',  'Transport Management System',  'Transportverwaltung: Carrier, Shipments, GPS-Tracking, Lieferungen'),
    ('MDM',  'Master Data Management',       'Stammdatenharmonisierung: Golden Records, Source Mappings'),
    ('META', 'Metadatenmanagement',          'Datenkatalog: Tabellen-, Spaltenmetadaten, Skalenniveaus'),
    ('DWH',  'Data Warehouse',               'Analytisches Schema (Sternschema). Wird ausschließlich durch ETL befüllt.')
ON CONFLICT (system_code) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Tabellen-Metadaten
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta.tables (
    table_id        SERIAL          PRIMARY KEY,
    system_id       INT             NOT NULL REFERENCES meta.systems(system_id),
    schema_name     VARCHAR(20)     NOT NULL,
    table_name      VARCHAR(100)    NOT NULL,
    description     TEXT,
    data_category   VARCHAR(30)     NOT NULL CHECK (data_category IN (
                        'STAMMDATEN', 'BEWEGUNGSDATEN', 'EVENTDATEN',
                        'ECHTZEITDATEN', 'METADATEN', 'ANALYTIK'
                    )),
    source_event    VARCHAR(50),    -- auslösendes Event aus dem Datengenerator
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UNIQUE (schema_name, table_name)
);

-- Tabellen-Einträge für alle wichtigen Tabellen
INSERT INTO meta.tables (system_id, schema_name, table_name, description, data_category, source_event)
SELECT s.system_id, t.schema_name, t.table_name, t.description, t.data_category, t.source_event
FROM (
    VALUES
    -- ERP
    ('ERP', 'erp', 'suppliers',     'Lieferantenstammdaten (Ghanaische Bananenlieferanten)',         'STAMMDATEN',    'SupplierCreated'),
    ('ERP', 'erp', 'customers',     'Kundenstammdaten (Europäische Einzelhandelskunden)',             'STAMMDATEN',    'CustomerCreated'),
    ('ERP', 'erp', 'products',      'Produktstammdaten (10 Bananensorten)',                          'STAMMDATEN',    'ProductCreated'),
    ('ERP', 'erp', 'orders',        'Bestellköpfe (initiieren den Supply-Chain-Prozess)',             'BEWEGUNGSDATEN','OrderCreated'),
    ('ERP', 'erp', 'order_items',   'Bestellpositionen (Menge und Preis pro Produkt)',               'BEWEGUNGSDATEN','OrderCreated'),
    ('ERP', 'erp', 'batches',       'Ernte-Batches (physische Wareneinheiten)',                       'BEWEGUNGSDATEN','BatchHarvested'),
    -- WMS
    ('WMS', 'wms', 'warehouse_skus',       'WMS-Produktreferenzen (SKUs im Unterstriche-Format)',    'STAMMDATEN',    'WarehouseSKUCreated'),
    ('WMS', 'wms', 'supply_chain_nodes',   'Stammdaten der 7 Supply-Chain-Knoten',                   'STAMMDATEN',    NULL),
    ('WMS', 'wms', 'node_processings',     'Knotenverarbeitungsprotokolle mit Temperaturmessung',    'BEWEGUNGSDATEN','NodeProcessed'),
    -- TMS
    ('TMS', 'tms', 'carriers',                     'Transportdienstleister-Stammdaten',              'STAMMDATEN',    'CarrierCreated'),
    ('TMS', 'tms', 'transport_product_references', 'TMS-Produktreferenzen (Kleinbuchstaben-Format)', 'STAMMDATEN',    'TransportProductReferenceCreated'),
    ('TMS', 'tms', 'shipments',                    'Transportvorgänge zwischen Supply-Chain-Knoten', 'BEWEGUNGSDATEN','TransportStarted'),
    ('TMS', 'tms', 'shipment_positions',           'GPS-Positionsarchiv (Primär: Redis)',             'ECHTZEITDATEN', 'ShipmentPositionUpdated'),
    ('TMS', 'tms', 'transport_completions',        'Transportabschlüsse mit Verzögerungsminuten',    'EVENTDATEN',    'TransportCompleted'),
    ('TMS', 'tms', 'deliveries',                   'Finale Lieferabschlüsse am Retail Store',        'EVENTDATEN',    'DeliveryCompleted'),
    -- MDM
    ('MDM', 'mdm', 'entity_types',    'Entitätstypen im MDM (PRODUCT, SUPPLIER etc.)',               'METADATEN',     NULL),
    ('MDM', 'mdm', 'golden_records',  'Kanonische Stammdaten (Single Source of Truth)',              'METADATEN',     NULL),
    ('MDM', 'mdm', 'source_mappings', 'Systemspezifische Schlüsselmappings',                         'METADATEN',     NULL)
) AS t(system_code, schema_name, table_name, description, data_category, source_event)
JOIN meta.systems s ON s.system_code = t.system_code
ON CONFLICT (schema_name, table_name) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Spalten-Metadaten
-- Die wichtigsten Spalten mit Skalenniveau, Datenart und Qualitätsregel
-- Skalenniveaus nach Stevens (1946): NOMINAL, ORDINAL, INTERVAL, RATIO
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta.columns (
    column_id       SERIAL          PRIMARY KEY,
    table_id        INT             NOT NULL REFERENCES meta.tables(table_id),
    column_name     VARCHAR(100)    NOT NULL,
    data_type       VARCHAR(50)     NOT NULL,   -- PostgreSQL-Datentyp
    description     TEXT,
    source          VARCHAR(200),               -- JSON-Feldname im Quell-Event
    data_category   VARCHAR(30)     NOT NULL CHECK (data_category IN (
                        'STAMMDATEN', 'BEWEGUNGSDATEN', 'EVENTDATEN',
                        'ECHTZEITDATEN', 'METADATEN', 'ANALYTIK'
                    )),
    scale_level     VARCHAR(10)     NOT NULL CHECK (scale_level IN (
                        'NOMINAL', 'ORDINAL', 'INTERVAL', 'RATIO'
                    )),
    quality_rule    TEXT,                       -- Validierungsregel in natürlicher Sprache
    is_nullable     BOOLEAN         NOT NULL DEFAULT TRUE,
    is_pk           BOOLEAN         NOT NULL DEFAULT FALSE,
    is_fk           BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UNIQUE (table_id, column_name)
);

COMMENT ON TABLE  meta.columns IS 'Spalten-Metadaten für alle wichtigen Tabellen. Enthält Skalenniveaus nach Stevens (1946) und Qualitätsregeln.';
COMMENT ON COLUMN meta.columns.scale_level IS 'NOMINAL: Kategorien. ORDINAL: Geordnete Kategorien. INTERVAL: Numerisch ohne Nullpunkt. RATIO: Numerisch mit Nullpunkt.';

-- -----------------------------------------------------------------------------
-- Exemplarische Spalten-Metadaten (wichtigste Tabellen)
-- Eingefügt via subselect auf meta.tables für Referenzintegrität
-- -----------------------------------------------------------------------------

-- ERP.SUPPLIERS
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('supplier_id',   'SERIAL',      'Technischer Primärschlüssel',              NULL,              'METADATEN',    'NOMINAL',  'Eindeutig, auto-generiert',                                                    FALSE, TRUE,  FALSE),
    ('supplier_code', 'VARCHAR(20)', 'Kanonischer Business Key des Lieferanten', 'supplier_code',   'STAMMDATEN',   'NOMINAL',  'Format: SUP-Nnn (3 Buchstaben, Bindestrich, 3 Ziffern). Eindeutig. Pflichtfeld.',FALSE, FALSE, FALSE),
    ('supplier_name', 'VARCHAR(100)','Offizieller Unternehmensname',             'supplier_name',   'STAMMDATEN',   'NOMINAL',  'Nicht leer. Max. 100 Zeichen.',                                                 FALSE, FALSE, FALSE),
    ('country',       'VARCHAR(50)', 'Herkunftsland des Lieferanten',            'country',         'STAMMDATEN',   'NOMINAL',  'ISO-Ländername (z.B. "Ghana"). Nicht leer.',                                    FALSE, FALSE, FALSE),
    ('created_at',    'TIMESTAMP',   'Zeitpunkt der Erfassung im System',        'timestamp',       'METADATEN',    'INTERVAL', 'Nicht in der Zukunft. ISO-8601-Format.',                                        FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'erp' AND t.table_name = 'suppliers'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- ERP.PRODUCTS
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('product_id',   'SERIAL',      'Technischer Primärschlüssel',             NULL,             'METADATEN',    'NOMINAL',  'Eindeutig, auto-generiert',                                                          FALSE, TRUE,  FALSE),
    ('product_code', 'VARCHAR(20)', 'Kanonischer Produktcode (ERP-Format)',    'product_code',   'STAMMDATEN',   'NOMINAL',  'Format: BAN-1nn. Eindeutig. MDM-kanonisch. Pflichtfeld.',                             FALSE, FALSE, FALSE),
    ('product_name', 'VARCHAR(100)','Produktbezeichnung (Bananensorte)',       'product_name',   'STAMMDATEN',   'NOMINAL',  'Nicht leer. Beschreibende Bezeichnung der Bananensorte.',                            FALSE, FALSE, FALSE),
    ('category',     'VARCHAR(50)', 'Produktkategorie',                        'category',       'STAMMDATEN',   'NOMINAL',  'Erlaubt: "Fresh Fruit". Erweiterbar für weitere Kategorien.',                       FALSE, FALSE, FALSE),
    ('supplier_id',  'INT',         'FK zum Lieferanten',                      'supplier_reference','STAMMDATEN','NOMINAL',  'Muss auf gültigen erp.suppliers.supplier_id verweisen. Pflichtfeld.',               FALSE, FALSE, TRUE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'erp' AND t.table_name = 'products'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- ERP.ORDERS
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('order_id',          'SERIAL',      'Technischer Primärschlüssel',         NULL,               'METADATEN',    'NOMINAL',  'Eindeutig, auto-generiert',                                                        FALSE, TRUE,  FALSE),
    ('order_reference',   'VARCHAR(60)', 'UUID-basierter Bestellreferenzcode',  'order_reference',  'BEWEGUNGSDATEN','NOMINAL', 'Format: ORD-<uuid>. Eindeutig. Pflichtfeld.',                                      FALSE, FALSE, FALSE),
    ('customer_id',       'INT',         'FK zum Kunden',                        'customer_number',  'BEWEGUNGSDATEN','NOMINAL', 'Muss auf gültigen erp.customers.customer_id verweisen.',                           FALSE, FALSE, TRUE),
    ('delivery_priority', 'VARCHAR(10)', 'Lieferpriorität der Bestellung',      'delivery_priority','BEWEGUNGSDATEN','ORDINAL', 'Erlaubt: HIGH > NORMAL > LOW (geordnet). Pflichtfeld.',                            FALSE, FALSE, FALSE),
    ('order_timestamp',   'TIMESTAMP',   'Zeitpunkt der Bestellaufgabe',        'timestamp',        'BEWEGUNGSDATEN','INTERVAL','Nicht in der Zukunft. Muss vor harvested_at des zugehörigen Batches liegen.',      FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'erp' AND t.table_name = 'orders'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- ERP.ORDER_ITEMS
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('quantity',   'INT',          'Bestellmenge in Einheiten',     'quantity',   'BEWEGUNGSDATEN','RATIO',   'Ganzzahl > 0. Plausibel: 100-1000 Einheiten laut Datengenerator.',            FALSE, FALSE, FALSE),
    ('unit_price', 'NUMERIC(10,2)','Einzelpreis in EUR',            'unit_price', 'BEWEGUNGSDATEN','RATIO',   'Positiv. Plausibel: 1.50 – 5.00 EUR laut Datengenerator. 2 Dezimalstellen.', FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'erp' AND t.table_name = 'order_items'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- WMS.NODE_PROCESSINGS
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('node_id',        'INT',          'FK zum Supply-Chain-Knoten',        'supply_chain_node','BEWEGUNGSDATEN','NOMINAL', 'Muss auf gültigen wms.supply_chain_nodes.node_id verweisen.',                  FALSE, FALSE, TRUE),
    ('batch_reference','VARCHAR(60)',  'Referenz auf den verarbeiteten Batch','batch_reference', 'BEWEGUNGSDATEN','NOMINAL', 'Format: BATCH-<uuid>. Muss in erp.batches existieren (Cross-Schema-Check).',  FALSE, FALSE, FALSE),
    ('sku',            'VARCHAR(20)',  'WMS-SKU des verarbeiteten Produkts', 'sku',              'BEWEGUNGSDATEN','NOMINAL', 'Format: BAN_NNN (Unterstriche). Muss in wms.warehouse_skus.sku existieren.',  FALSE, FALSE, FALSE),
    ('temperature',    'NUMERIC(5,2)','Lagertemperatur in °C',              'temperature',      'BEWEGUNGSDATEN','INTERVAL','Kühlkette: 10.0 – 15.0°C. Abweichungen = Qualitätsproblem.',                  TRUE,  FALSE, FALSE),
    ('status',         'VARCHAR(20)', 'Verarbeitungsstatus',                'status',           'EVENTDATEN',   'NOMINAL', 'Erlaubt: COMPLETED, PENDING, FAILED.',                                        FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'wms' AND t.table_name = 'node_processings'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- TMS.SHIPMENTS
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('shipment_identifier',     'VARCHAR(60)', 'Eindeutiger Shipment-Tracking-Key',    'shipment_identifier',     'BEWEGUNGSDATEN','NOMINAL',  'Format: SHIP-<uuid>. Eindeutig. Verbindet alle TMS-Events.',        FALSE, FALSE, FALSE),
    ('transport_mode',          'VARCHAR(20)', 'Transportmodus',                       'transport_mode',          'BEWEGUNGSDATEN','NOMINAL',  'Erlaubt: TRUCK, SEA_FREIGHT.',                                      FALSE, FALSE, FALSE),
    ('cargo_product_reference', 'VARCHAR(30)', 'TMS-Produktreferenz (Kleinbuchstaben)','cargo_product_reference', 'BEWEGUNGSDATEN','NOMINAL',  'Format: ban-nnn. MDM-Mapping zu ERP-Code erforderlich.',            FALSE, FALSE, FALSE),
    ('estimated_arrival',       'TIMESTAMP',   'Geplante Ankunftszeit',                'estimated_arrival',       'BEWEGUNGSDATEN','INTERVAL', 'Muss nach started_at liegen.',                                      TRUE,  FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'tms' AND t.table_name = 'shipments'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- TMS.SHIPMENT_POSITIONS (GPS)
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('latitude',              'NUMERIC(9,6)', 'WGS84-Breitengrad',             'coordinates.latitude',    'ECHTZEITDATEN','INTERVAL','Wertebereich: -90.0 bis 90.0. CHECK-Constraint.',                       FALSE, FALSE, FALSE),
    ('longitude',             'NUMERIC(9,6)', 'WGS84-Längengrad',              'coordinates.longitude',   'ECHTZEITDATEN','INTERVAL','Wertebereich: -180.0 bis 180.0. CHECK-Constraint.',                     FALSE, FALSE, FALSE),
    ('container_temperature', 'NUMERIC(5,2)', 'Containertemperatur in °C',     'container_temperature',   'ECHTZEITDATEN','INTERVAL','Kühlkette: 10.0 – 15.0°C. Abweichungen = Qualitätsproblem.',            TRUE,  FALSE, FALSE),
    ('speed_kmh',             'NUMERIC(6,2)', 'Fahrzeuggeschwindigkeit in km/h','speed_kmh',              'ECHTZEITDATEN','RATIO',  'Wertebereich: 0 – 120 km/h laut Datengenerator. Plausibilitätsprüfung.', TRUE,  FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'tms' AND t.table_name = 'shipment_positions'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- TMS.TRANSPORT_COMPLETIONS
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('delay_minutes', 'INT', 'Tatsächliche Verzögerung in Minuten', 'delay_minutes', 'EVENTDATEN', 'RATIO', 'Wertebereich: 0 – 180 Min laut Datengenerator. Nicht negativ.', FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'tms' AND t.table_name = 'transport_completions'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- TMS.DELIVERIES
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('delivery_status', 'VARCHAR(20)', 'Finaler Lieferstatus', 'delivery_status', 'EVENTDATEN', 'NOMINAL', 'Erlaubt: SUCCESSFUL, DELAYED, FAILED. Häufigkeit: ~2/3 SUCCESSFUL, ~1/3 DELAYED.', FALSE, FALSE, FALSE),
    ('received_by',     'VARCHAR(20)', 'Empfänger-Mitarbeiter-ID', 'received_by', 'EVENTDATEN', 'NOMINAL', 'Format: EMP-NNN (1-99). Nicht leer bei SUCCESSFUL.',                              TRUE,  FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'tms' AND t.table_name = 'deliveries'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Indizes
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_meta_tables_system   ON meta.tables(system_id);
CREATE INDEX IF NOT EXISTS idx_meta_columns_table   ON meta.columns(table_id);
CREATE INDEX IF NOT EXISTS idx_meta_columns_scale   ON meta.columns(scale_level);

DO $$
BEGIN
    RAISE NOTICE 'Metadaten-Tabellen erstellt: systems, tables, columns (mit exemplarischen Einträgen für alle wichtigen Spalten)';
END $$;
