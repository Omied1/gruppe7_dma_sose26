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
    ('completion_id',  'SERIAL',      'Technischer Primärschlüssel',                     NULL,             'METADATEN',  'NOMINAL', 'Eindeutig, auto-generiert',                                                                             FALSE, TRUE,  FALSE),
    ('shipment_id',    'INT',         'FK zum Transportvorgang',                          'shipment_id',    'EVENTDATEN', 'NOMINAL', 'Muss auf gültigen tms.shipments.shipment_id verweisen. Eindeutig (1 Abschluss pro Shipment).',           FALSE, FALSE, TRUE),
    ('arrival_node',   'VARCHAR(50)', 'Ankunftsknoten des Transports',                   'arrival_node',   'EVENTDATEN', 'NOMINAL', 'Erlaubt: Gültige node_codes aus wms.supply_chain_nodes (z.B. RETAIL_STORE).',                           FALSE, FALSE, FALSE),
    ('delay_minutes',  'INT',         'Tatsächliche Verzögerung in Minuten',             'delay_minutes',  'EVENTDATEN', 'RATIO',   '>= 0 (CHECK-Constraint). > 30 min = SLA-Verletzung. 0 = pünktlich. Skalentyp RATIO: 0 bedeutet ''keine Verzögerung'', Verhältnisse sinnvoll (60/30 = doppelte Verzögerung).', FALSE, FALSE, FALSE),
    ('completed_at',   'TIMESTAMP',   'Zeitpunkt des Transportabschlusses',              'timestamp',      'EVENTDATEN', 'INTERVAL','Nicht in der Zukunft. Muss nach tms.shipments.started_at liegen. INTERVAL: kein nat. Nullpunkt.',       FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'tms' AND t.table_name = 'transport_completions'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- ERP.CUSTOMERS
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('customer_id',     'SERIAL',      'Technischer Primärschlüssel',              NULL,              'METADATEN',    'NOMINAL',  'Eindeutig, auto-generiert',                                                                  FALSE, TRUE,  FALSE),
    ('customer_number', 'VARCHAR(20)', 'Kanonischer Business Key des Kunden',      'customer_number', 'STAMMDATEN',   'NOMINAL',  'Format: CUST-NNN. Eindeutig. Pflichtfeld. Keine inhärente Reihenfolge (NOMINAL).',            FALSE, FALSE, FALSE),
    ('customer_name',   'VARCHAR(100)','Name der Einzelhandelskette',              'customer_name',   'STAMMDATEN',   'NOMINAL',  'Nicht leer. Bekannte Werte: ALDI, LIDL, REWE, Carrefour, Tesco.',                            FALSE, FALSE, FALSE),
    ('city',            'VARCHAR(50)', 'Standortstadt des Kunden',                 'city',            'STAMMDATEN',   'NOMINAL',  'Nullable. Stadtname ohne feste Reihenfolge (NOMINAL). ISO-Stadtname empfohlen.',              TRUE,  FALSE, FALSE),
    ('country',         'VARCHAR(50)', 'Herkunftsland des Kunden',                 'country',         'STAMMDATEN',   'NOMINAL',  'ISO-Ländername (z.B. "Germany"). Nicht leer. Europäische Märkte.',                           FALSE, FALSE, FALSE),
    ('event_timestamp', 'TIMESTAMP',   'Zeitpunkt des CustomerCreated-Events',     'timestamp',       'METADATEN',    'INTERVAL', 'Nicht in der Zukunft. INTERVAL: Zeitstempel ohne natürlichen Nullpunkt.',                    FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'erp' AND t.table_name = 'customers'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- ERP.BATCHES
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('batch_id',               'SERIAL',      'Technischer Primärschlüssel',                    NULL,                   'METADATEN',    'NOMINAL',  'Eindeutig, auto-generiert',                                                                             FALSE, TRUE,  FALSE),
    ('batch_identifier',       'VARCHAR(60)', 'Eindeutiger Batch-Tracking-Key',                 'batch_identifier',     'BEWEGUNGSDATEN','NOMINAL',  'Format: BATCH-<uuid>. Eindeutig. Verbindet ERP-Batch mit WMS NodeProcessed-Events.',                    FALSE, FALSE, FALSE),
    ('product_id',             'INT',         'FK zum Produkt (erp.products)',                  'product_code',         'BEWEGUNGSDATEN','NOMINAL',  'Muss auf gültigen erp.products.product_id verweisen. Pflichtfeld.',                                     FALSE, FALSE, TRUE),
    ('origin_country',         'VARCHAR(50)', 'Ernteherkunftsland (z.B. Ghana)',                'origin_country',       'BEWEGUNGSDATEN','NOMINAL',  'ISO-Ländername. Typisch: Ghana, Ecuador, Colombia. NOMINAL: keine Reihenfolge.',                        FALSE, FALSE, FALSE),
    ('quantity',               'INT',         'Erntevolumen in Einheiten',                      'quantity',             'BEWEGUNGSDATEN','RATIO',    '> 0 (CHECK-Constraint). RATIO: 0 = kein Batch, Verhältnisse sinnvoll (400 = doppelt so viel wie 200).', FALSE, FALSE, FALSE),
    ('supply_chain_node',      'VARCHAR(50)', 'Startknotencode des Batches',                    'supply_chain_node',    'BEWEGUNGSDATEN','NOMINAL',  'Wert: BANANA_PLANTATION (Standardwert, Ernteort). NOMINAL: Bezeichner.',                                FALSE, FALSE, FALSE),
    ('wms_sku',                'VARCHAR(30)', 'WMS-spezifische SKU-Referenz',                   'wms_sku',              'BEWEGUNGSDATEN','NOMINAL',  'Format: BAN_NNN (Unterstriche). Nullable. Redundant mit mdm.source_mappings.',                          TRUE,  FALSE, FALSE),
    ('tms_product_reference',  'VARCHAR(30)', 'TMS-spezifische Produktreferenz',                'tms_product_reference','BEWEGUNGSDATEN','NOMINAL',  'Format: ban-nnn (Kleinbuchstaben). Nullable. Redundant mit mdm.source_mappings.',                       TRUE,  FALSE, FALSE),
    ('harvested_at',           'TIMESTAMP',   'Erntezeitpunkt (= event_timestamp)',             'timestamp',            'BEWEGUNGSDATEN','INTERVAL', 'Nicht in der Zukunft. INTERVAL: Zeitstempel ohne natürlichen Nullpunkt.',                               FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'erp' AND t.table_name = 'batches'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- WMS.WAREHOUSE_SKUS
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('sku_id',           'SERIAL',      'Technischer Primärschlüssel',             NULL,               'METADATEN',  'NOMINAL',  'Eindeutig, auto-generiert',                                                         FALSE, TRUE,  FALSE),
    ('erp_product_code', 'VARCHAR(20)', 'Cross-Referenz zum ERP-Produktcode',      'erp_product_code', 'STAMMDATEN', 'NOMINAL',  'Format: BAN-101 (Bindestriche). Eindeutig. FK-Auflösung via erp.products.product_code.',FALSE, FALSE, FALSE),
    ('sku',              'VARCHAR(20)', 'WMS-spezifische SKU (Unterstriche)',       'sku',              'STAMMDATEN', 'NOMINAL',  'Format: BAN_101 (Unterstriche). Eindeutig. MDM-Inkonsistenz zu ERP und TMS.',        FALSE, FALSE, FALSE),
    ('event_timestamp',  'TIMESTAMP',   'Zeitpunkt des WarehouseSKUCreated-Events','timestamp',        'METADATEN',  'INTERVAL', 'Nicht in der Zukunft. INTERVAL: Zeitstempel ohne natürlichen Nullpunkt.',           FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'wms' AND t.table_name = 'warehouse_skus'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- WMS.SUPPLY_CHAIN_NODES
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('node_id',       'SERIAL',      'Technischer Primärschlüssel',                  NULL,           'METADATEN',  'NOMINAL',  'Eindeutig, auto-generiert',                                                                                                 FALSE, TRUE,  FALSE),
    ('node_code',     'VARCHAR(50)', 'Interner Knotenbezeichner',                     NULL,           'STAMMDATEN', 'NOMINAL',  'Erlaubt: BANANA_PLANTATION, COLLECTION_CENTER, QUALITY_CONTROL, AFRICA_COLD_STORAGE, EUROPE_COLD_STORAGE, CENTRAL_WAREHOUSE, RETAIL_STORE. NOMINAL: keine numerische Bedeutung.', FALSE, FALSE, FALSE),
    ('node_name',     'VARCHAR(100)','Lesbarer Name des Supply-Chain-Knotens',        NULL,           'STAMMDATEN', 'NOMINAL',  'Nicht leer. Beschreibender Name für Reports und Visualisierungen.',                                                         FALSE, FALSE, FALSE),
    ('node_type',     'VARCHAR(30)', 'Funktionstyp des Knotens',                      NULL,           'STAMMDATEN', 'NOMINAL',  'Erlaubt: PLANTATION, COLLECTION_CENTER, QUALITY_CONTROL, COLD_STORAGE, WAREHOUSE, RETAIL. CHECK-Constraint. NOMINAL.',      FALSE, FALSE, FALSE),
    ('region',        'VARCHAR(50)', 'Geografische Region des Knotens',               NULL,           'STAMMDATEN', 'NOMINAL',  'Erlaubt: Africa, Europe. Nullable. NOMINAL: Bezeichner ohne Reihenfolge.',                                                  TRUE,  FALSE, FALSE),
    ('sequence_order','INT',         'Position im Supply-Chain-Flow (1–7)',           NULL,           'STAMMDATEN', 'RATIO',    'Wertebereich: 1 (Plantation) – 7 (Retail). RATIO: 0 = kein Knoten, Abstände gleichmäßig. NOT NULL.',                         FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'wms' AND t.table_name = 'supply_chain_nodes'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- TMS.CARRIERS
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('carrier_id',      'SERIAL',      'Technischer Primärschlüssel',                 NULL,              'METADATEN',  'NOMINAL',  'Eindeutig, auto-generiert',                                                         FALSE, TRUE,  FALSE),
    ('carrier_code',    'VARCHAR(20)', 'Kanonischer Business Key des Carriers',        'carrier_id',      'STAMMDATEN', 'NOMINAL',  'Format: CAR-NNN. Eindeutig. JSON-Feld heißt "carrier_id" (ETL-Mapping beachten!).',  FALSE, FALSE, FALSE),
    ('carrier_name',    'VARCHAR(100)','Name des Transportdienstleisters',             'carrier_name',    'STAMMDATEN', 'NOMINAL',  'Bekannte Werte: DHL, Maersk, MSC, DB Schenker, Hapag Lloyd. Nicht leer.',            FALSE, FALSE, FALSE),
    ('event_timestamp', 'TIMESTAMP',   'Zeitpunkt des CarrierCreated-Events',          'timestamp',       'METADATEN',  'INTERVAL', 'Nicht in der Zukunft. INTERVAL: Zeitstempel ohne natürlichen Nullpunkt.',           FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'tms' AND t.table_name = 'carriers'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- TMS.TRANSPORT_PRODUCT_REFERENCES
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('ref_id',                       'SERIAL',      'Technischer Primärschlüssel',               NULL,                          'METADATEN',  'NOMINAL',  'Eindeutig, auto-generiert',                                                                   FALSE, TRUE,  FALSE),
    ('erp_product_code',             'VARCHAR(20)', 'Cross-Referenz zum ERP-Produktcode',         'erp_product_code',            'STAMMDATEN', 'NOMINAL',  'Format: BAN-101 (Großbuchstaben, Bindestrich). Eindeutig. MDM-kanonischer Schlüssel.',          FALSE, FALSE, FALSE),
    ('transport_product_reference',  'VARCHAR(20)', 'TMS-spezifische Produktreferenz',            'transport_product_reference', 'STAMMDATEN', 'NOMINAL',  'Format: ban-101 (Kleinbuchstaben, Bindestrich). Eindeutig. MDM-Inkonsistenz zu ERP/WMS.',      FALSE, FALSE, FALSE),
    ('event_timestamp',              'TIMESTAMP',   'Zeitpunkt des TransportProductReferenceCreated-Events','timestamp',        'METADATEN',  'INTERVAL', 'Nicht in der Zukunft. INTERVAL: Zeitstempel ohne natürlichen Nullpunkt.',                      FALSE, FALSE, FALSE)
) AS c(column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
WHERE t.schema_name = 'tms' AND t.table_name = 'transport_product_references'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- TMS.DELIVERIES
INSERT INTO meta.columns (table_id, column_name, data_type, description, source, data_category, scale_level, quality_rule, is_nullable, is_pk, is_fk)
SELECT t.table_id, c.column_name, c.data_type, c.description, c.source, c.data_category, c.scale_level, c.quality_rule, c.is_nullable, c.is_pk, c.is_fk
FROM meta.tables t
CROSS JOIN (VALUES
    ('delivery_id',              'SERIAL',      'Technischer Primärschlüssel',                  NULL,                      'METADATEN',  'NOMINAL',  'Eindeutig, auto-generiert',                                                                                                             FALSE, TRUE,  FALSE),
    ('shipment_id',              'INT',         'FK zum Transportvorgang',                       'shipment_id',             'EVENTDATEN', 'NOMINAL',  'Muss auf gültigen tms.shipments.shipment_id verweisen. Eindeutig (1 Delivery pro Shipment).',                                           FALSE, FALSE, TRUE),
    ('supply_chain_node',        'VARCHAR(50)', 'Zielknoten der Lieferung',                      'supply_chain_node',       'EVENTDATEN', 'NOMINAL',  'Wert: RETAIL_STORE (Standardwert, Standardfall). NOMINAL: Knotenbezeichner ohne Reihenfolge.',                                          FALSE, FALSE, FALSE),
    ('delivery_status',          'VARCHAR(20)', 'Finaler Lieferstatus (Haupt-KPI)',               'delivery_status',         'EVENTDATEN', 'NOMINAL',  'Erlaubt: SUCCESSFUL, DELAYED, FAILED. CHECK-Constraint. ~2/3 SUCCESSFUL, ~1/3 DELAYED laut Datengenerator. NOMINAL: Kategorie.',        FALSE, FALSE, FALSE),
    ('received_by',              'VARCHAR(20)', 'Mitarbeiter-ID des Empfängers am Retail Store', 'received_by',             'EVENTDATEN', 'NOMINAL',  'Format: EMP-NNN (1-99). Nullable. Nicht leer bei SUCCESSFUL-Lieferung. NOMINAL: Bezeichner.',                                           TRUE,  FALSE, FALSE),
    ('cargo_product_reference',  'VARCHAR(30)', 'TMS-Produktreferenz in Lieferung',              'cargo_product_reference', 'EVENTDATEN', 'NOMINAL',  'Format: ban-nnn (Kleinbuchstaben). Nullable. MDM-Mapping zu ERP-Code erforderlich.',                                                     TRUE,  FALSE, FALSE),
    ('delivered_at',             'TIMESTAMP',   'Tatsächlicher Lieferzeitpunkt',                 'timestamp',               'EVENTDATEN', 'INTERVAL', 'Nicht in der Zukunft. Muss nach tms.shipments.started_at liegen. INTERVAL: kein natürlicher Nullpunkt.',                                FALSE, FALSE, FALSE)
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
DECLARE v_col_count INT;
BEGIN
    SELECT COUNT(*) INTO v_col_count FROM meta.columns;
    RAISE NOTICE 'Metadaten-Tabellen erstellt: systems (6), tables (18+), columns (% Einträge). Abdeckung: ERP (suppliers, customers, products, orders, order_items, batches), WMS (warehouse_skus, supply_chain_nodes, node_processings), TMS (carriers, transport_product_references, shipments, shipment_positions, transport_completions, deliveries). Vollabdeckung via 06b_metadata_complete.sql.', v_col_count;
END $$;
