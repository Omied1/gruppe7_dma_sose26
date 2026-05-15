-- =============================================================================
-- 05_create_mdm_tables.sql
-- MDM-Schema: Master Data Management für die Banana Supply Chain
--
-- Tabellen:
--   mdm.golden_records    - Kanonische Stammdaten (eine Wahrheit pro Entität)
--   mdm.source_mappings   - Systemspezifische Schlüsselmappings (ERP/WMS/TMS)
--   mdm.entity_types      - Referenztabelle für Entitätstypen
--
-- Zweck: Harmonisierung der systemübergreifenden Inkonsistenz
--   ERP: BAN-101  /  WMS: BAN_101  /  TMS: ban-101
--   → MDM löst auf: Golden Record = "BAN-101" (ERP-Format ist kanonisch)
--
-- Voraussetzung: 01_create_schemas.sql muss vorher ausgeführt worden sein.
-- Ausführung:    psql -h localhost -U user -d logistics -f 05_create_mdm_tables.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Entitätstypen-Referenztabelle
-- Definiert welche Stammdatenentitäten im MDM verwaltet werden
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mdm.entity_types (
    entity_type_id      SERIAL          PRIMARY KEY,
    entity_type_code    VARCHAR(30)     NOT NULL UNIQUE,
    entity_type_name    VARCHAR(100)    NOT NULL,
    description         TEXT,
    source_schema       VARCHAR(20)     -- primäres Quellschema
);

INSERT INTO mdm.entity_types (entity_type_code, entity_type_name, description, source_schema) VALUES
    ('PRODUCT',             'Produkt',                  'Bananensorten und Produkte der Supply Chain',           'erp'),
    ('SUPPLIER',            'Lieferant',                'Ghanaische Bananenlieferanten und Plantagen',           'erp'),
    ('CUSTOMER',            'Kunde',                    'Europäische Einzelhandelskunden (ALDI, LIDL etc.)',      'erp'),
    ('CARRIER',             'Transportdienstleister',   'Carrier für Land- und Seetransporte',                   'tms'),
    ('SUPPLY_CHAIN_NODE',   'Supply-Chain-Knoten',      'Physische Stationen der Lieferkette',                   'wms')
ON CONFLICT (entity_type_code) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Golden Records
-- Jede Entität wird als ein kanonischer Golden Record geführt.
-- Der Golden Record enthält den "richtigen" Namen und den kanonischen Business Key.
-- Kanonisches Format: ERP-Format (BAN-101, SUP-101, CUST-101)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mdm.golden_records (
    golden_id           SERIAL          PRIMARY KEY,
    entity_type_id      INT             NOT NULL REFERENCES mdm.entity_types(entity_type_id),
    canonical_key       VARCHAR(50)     NOT NULL,                   -- Kanonischer Business Key (ERP-Format)
    canonical_name      VARCHAR(200)    NOT NULL,                   -- Kanonischer Name
    status              VARCHAR(20)     NOT NULL DEFAULT 'ACTIVE'   -- ACTIVE / DEPRECATED / MERGED
                            CHECK (status IN ('ACTIVE', 'DEPRECATED', 'MERGED')),
    quality_score       NUMERIC(3,2)    CHECK (quality_score BETWEEN 0 AND 1), -- 0.0-1.0
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    UNIQUE (entity_type_id, canonical_key)
);

COMMENT ON TABLE  mdm.golden_records IS 'Kanonische Stammdaten-Masterdaten. Ein Golden Record pro Entität ist die einzige Wahrheitsquelle (Single Source of Truth).';
COMMENT ON COLUMN mdm.golden_records.canonical_key   IS 'Kanonischer Business Key im ERP-Format: BAN-101, SUP-101, CUST-101, CAR-101.';
COMMENT ON COLUMN mdm.golden_records.quality_score   IS 'Datenqualitätsscore 0.0-1.0. Basiert auf Vollständigkeit, Konsistenz und Aktualität.';
COMMENT ON COLUMN mdm.golden_records.status          IS 'ACTIVE: Aktuell. DEPRECATED: Veraltet (Produkt eingestellt). MERGED: Mit anderem Record zusammengeführt.';

-- -----------------------------------------------------------------------------
-- Source-System-Mappings
-- Jedes Quellsystem hat eigene Schlüsselformate für dieselbe Entität.
-- Diese Tabelle verknüpft systemspezifische Schlüssel mit dem Golden Record.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mdm.source_mappings (
    mapping_id          SERIAL          PRIMARY KEY,
    golden_id           INT             NOT NULL REFERENCES mdm.golden_records(golden_id),
    source_system       VARCHAR(10)     NOT NULL CHECK (source_system IN ('ERP', 'WMS', 'TMS')),
    source_key          VARCHAR(50)     NOT NULL,   -- Schlüssel wie im Quellsystem: BAN_101 (WMS)
    normalized_key      VARCHAR(50)     NOT NULL,   -- Normalisierter Schlüssel: ban-101
    is_canonical        BOOLEAN         NOT NULL DEFAULT FALSE, -- TRUE nur für ERP-Mapping
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    UNIQUE (source_system, source_key)
);

COMMENT ON TABLE  mdm.source_mappings IS 'Systemspezifische Schlüsselmappings. Löst die BAN-101 / BAN_101 / ban-101-Inkonsistenz auf. Kernfunktion des MDM.';
COMMENT ON COLUMN mdm.source_mappings.source_system  IS 'ERP: kanonisches System (BAN-101). WMS: Unterstriche (BAN_101). TMS: Kleinbuchstaben (ban-101).';
COMMENT ON COLUMN mdm.source_mappings.source_key     IS 'Schlüssel exakt wie im Quellsystem gespeichert (ohne Transformation).';
COMMENT ON COLUMN mdm.source_mappings.normalized_key IS 'Kleinbuchstaben-normalisierter Key für systemübergreifende Suche.';
COMMENT ON COLUMN mdm.source_mappings.is_canonical   IS 'TRUE = dies ist der kanonische ERP-Schlüssel. Genau ein Mapping pro Golden Record hat is_canonical=TRUE.';

-- -----------------------------------------------------------------------------
-- Seed-Daten: Vollständige Golden Records für alle 5 Entity-Typen
--
-- Abdeckung:
--   PRODUCT (10)           → 3 Mappings je: ERP (BAN-NNN), WMS (BAN_NNN), TMS (ban-nnn)
--   CUSTOMER (10)          → 1 Mapping:  ERP (CUST-NNN)
--   SUPPLIER (10)          → 1 Mapping:  ERP (SUP-NNN)
--   CARRIER (5)            → 1 Mapping:  TMS (CAR-NNN)  [Stammsystem = TMS]
--   SUPPLY_CHAIN_NODE (7)  → 2 Mappings: WMS (kanonisch) + TMS (identischer Code)
--
-- Total: 42 Golden Records, 69 Source Mappings
-- Idempotent: ON CONFLICT DO NOTHING in allen INSERT-Statements
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_type_id   INT;
    v_gid       INT;
    -- PRODUCT: canonical_key, canonical_name
    products    TEXT[][] := ARRAY[
        ARRAY['BAN-101', 'Cavendish Banana'],
        ARRAY['BAN-102', 'Organic Banana'],
        ARRAY['BAN-103', 'Premium Banana'],
        ARRAY['BAN-104', 'Baby Banana'],
        ARRAY['BAN-105', 'Fairtrade Banana'],
        ARRAY['BAN-106', 'Export Banana'],
        ARRAY['BAN-107', 'Sweet Banana'],
        ARRAY['BAN-108', 'Green Banana'],
        ARRAY['BAN-109', 'Yellow Banana'],
        ARRAY['BAN-110', 'Tropical Banana']
    ];
    -- CUSTOMER: canonical_key, canonical_name
    customers   TEXT[][] := ARRAY[
        ARRAY['CUST-101', 'ALDI'],
        ARRAY['CUST-102', 'LIDL'],
        ARRAY['CUST-103', 'REWE'],
        ARRAY['CUST-104', 'EDEKA'],
        ARRAY['CUST-105', 'METRO'],
        ARRAY['CUST-106', 'KAUFLAND'],
        ARRAY['CUST-107', 'TESCO'],
        ARRAY['CUST-108', 'CARREFOUR'],
        ARRAY['CUST-109', 'AUCHAN'],
        ARRAY['CUST-110', 'SPAR']
    ];
    -- SUPPLIER: canonical_key, canonical_name
    suppliers   TEXT[][] := ARRAY[
        ARRAY['SUP-101', 'Golden Banana Ltd'],
        ARRAY['SUP-102', 'Fresh Banana Export'],
        ARRAY['SUP-103', 'Tropical Banana Group'],
        ARRAY['SUP-104', 'Banana Kingdom'],
        ARRAY['SUP-105', 'West Africa Fruits'],
        ARRAY['SUP-106', 'Premium Banana Farms'],
        ARRAY['SUP-107', 'Green Harvest Export'],
        ARRAY['SUP-108', 'Sunshine Produce'],
        ARRAY['SUP-109', 'Eco Banana Trading'],
        ARRAY['SUP-110', 'Global Banana Source']
    ];
    -- CARRIER: canonical_key, canonical_name
    carriers    TEXT[][] := ARRAY[
        ARRAY['CAR-101', 'DHL'],
        ARRAY['CAR-102', 'Maersk'],
        ARRAY['CAR-103', 'MSC'],
        ARRAY['CAR-104', 'DB Schenker'],
        ARRAY['CAR-105', 'Hapag Lloyd']
    ];
    -- SUPPLY_CHAIN_NODE: canonical_key, canonical_name, sequence (für Dokumentation)
    nodes       TEXT[][] := ARRAY[
        ARRAY['BANANA_PLANTATION',   'Banana Plantation Ghana'],
        ARRAY['COLLECTION_CENTER',   'Collection Center'],
        ARRAY['QUALITY_CONTROL',     'Quality Control Station'],
        ARRAY['AFRICA_COLD_STORAGE', 'Africa Cold Storage'],
        ARRAY['EUROPE_COLD_STORAGE', 'Europe Cold Storage'],
        ARRAY['CENTRAL_WAREHOUSE',   'Central Warehouse'],
        ARRAY['RETAIL_STORE',        'Retail Store']
    ];
    i           INT;
    v_ckey      TEXT;
    v_cname     TEXT;
    v_wms_key   TEXT;
    v_tms_key   TEXT;
BEGIN

    -- ── PRODUCT: ERP (kanonisch) + WMS (Underscore) + TMS (Lowercase) ────────
    SELECT entity_type_id INTO v_type_id FROM mdm.entity_types WHERE entity_type_code = 'PRODUCT';
    FOR i IN 1..array_length(products, 1) LOOP
        v_ckey   := products[i][1];  -- BAN-101
        v_cname  := products[i][2];
        v_wms_key := replace(v_ckey, '-', '_');   -- BAN_101
        v_tms_key := lower(v_ckey);               -- ban-101

        INSERT INTO mdm.golden_records (entity_type_id, canonical_key, canonical_name, status, quality_score)
        VALUES (v_type_id, v_ckey, v_cname, 'ACTIVE', 0.95)
        ON CONFLICT (entity_type_id, canonical_key) DO NOTHING
        RETURNING golden_id INTO v_gid;

        IF v_gid IS NULL THEN
            SELECT golden_id INTO v_gid FROM mdm.golden_records
            WHERE entity_type_id = v_type_id AND canonical_key = v_ckey;
        END IF;

        INSERT INTO mdm.source_mappings (golden_id, source_system, source_key, normalized_key, is_canonical)
        VALUES
            (v_gid, 'ERP', v_ckey,    lower(v_ckey),    TRUE),
            (v_gid, 'WMS', v_wms_key, lower(v_tms_key), FALSE),
            (v_gid, 'TMS', v_tms_key, lower(v_tms_key), FALSE)
        ON CONFLICT (source_system, source_key) DO NOTHING;
    END LOOP;
    RAISE NOTICE 'PRODUCT: % Golden Records angelegt', array_length(products, 1);

    -- ── CUSTOMER: Single-Source ERP (keine systemübergreifende Inkonsistenz) ─
    SELECT entity_type_id INTO v_type_id FROM mdm.entity_types WHERE entity_type_code = 'CUSTOMER';
    FOR i IN 1..array_length(customers, 1) LOOP
        v_ckey  := customers[i][1];
        v_cname := customers[i][2];

        INSERT INTO mdm.golden_records (entity_type_id, canonical_key, canonical_name, status, quality_score)
        VALUES (v_type_id, v_ckey, v_cname, 'ACTIVE', 1.00)
        ON CONFLICT (entity_type_id, canonical_key) DO NOTHING
        RETURNING golden_id INTO v_gid;

        IF v_gid IS NULL THEN
            SELECT golden_id INTO v_gid FROM mdm.golden_records
            WHERE entity_type_id = v_type_id AND canonical_key = v_ckey;
        END IF;

        INSERT INTO mdm.source_mappings (golden_id, source_system, source_key, normalized_key, is_canonical)
        VALUES (v_gid, 'ERP', v_ckey, lower(v_ckey), TRUE)
        ON CONFLICT (source_system, source_key) DO NOTHING;
    END LOOP;
    RAISE NOTICE 'CUSTOMER: % Golden Records angelegt', array_length(customers, 1);

    -- ── SUPPLIER: Single-Source ERP ──────────────────────────────────────────
    SELECT entity_type_id INTO v_type_id FROM mdm.entity_types WHERE entity_type_code = 'SUPPLIER';
    FOR i IN 1..array_length(suppliers, 1) LOOP
        v_ckey  := suppliers[i][1];
        v_cname := suppliers[i][2];

        INSERT INTO mdm.golden_records (entity_type_id, canonical_key, canonical_name, status, quality_score)
        VALUES (v_type_id, v_ckey, v_cname, 'ACTIVE', 1.00)
        ON CONFLICT (entity_type_id, canonical_key) DO NOTHING
        RETURNING golden_id INTO v_gid;

        IF v_gid IS NULL THEN
            SELECT golden_id INTO v_gid FROM mdm.golden_records
            WHERE entity_type_id = v_type_id AND canonical_key = v_ckey;
        END IF;

        INSERT INTO mdm.source_mappings (golden_id, source_system, source_key, normalized_key, is_canonical)
        VALUES (v_gid, 'ERP', v_ckey, lower(v_ckey), TRUE)
        ON CONFLICT (source_system, source_key) DO NOTHING;
    END LOOP;
    RAISE NOTICE 'SUPPLIER: % Golden Records angelegt', array_length(suppliers, 1);

    -- ── CARRIER: Single-Source TMS (Carrier entstehen nur im TMS) ───────────
    -- Kanonisches Format ist trotzdem ERP-ähnlich (CAR-101) da TMS dieses Format nutzt.
    SELECT entity_type_id INTO v_type_id FROM mdm.entity_types WHERE entity_type_code = 'CARRIER';
    FOR i IN 1..array_length(carriers, 1) LOOP
        v_ckey  := carriers[i][1];
        v_cname := carriers[i][2];

        INSERT INTO mdm.golden_records (entity_type_id, canonical_key, canonical_name, status, quality_score)
        VALUES (v_type_id, v_ckey, v_cname, 'ACTIVE', 1.00)
        ON CONFLICT (entity_type_id, canonical_key) DO NOTHING
        RETURNING golden_id INTO v_gid;

        IF v_gid IS NULL THEN
            SELECT golden_id INTO v_gid FROM mdm.golden_records
            WHERE entity_type_id = v_type_id AND canonical_key = v_ckey;
        END IF;

        INSERT INTO mdm.source_mappings (golden_id, source_system, source_key, normalized_key, is_canonical)
        VALUES (v_gid, 'TMS', v_ckey, lower(v_ckey), TRUE)
        ON CONFLICT (source_system, source_key) DO NOTHING;
    END LOOP;
    RAISE NOTICE 'CARRIER: % Golden Records angelegt', array_length(carriers, 1);

    -- ── SUPPLY_CHAIN_NODE: WMS (kanonisch) + TMS (identischer Code) ─────────
    -- WMS und TMS verwenden denselben node_code (keine Formatinkonsistenz).
    -- Beide Systeme werden registriert für vollständige Datenkatalog-Abdeckung.
    SELECT entity_type_id INTO v_type_id FROM mdm.entity_types WHERE entity_type_code = 'SUPPLY_CHAIN_NODE';
    FOR i IN 1..array_length(nodes, 1) LOOP
        v_ckey  := nodes[i][1];
        v_cname := nodes[i][2];

        INSERT INTO mdm.golden_records (entity_type_id, canonical_key, canonical_name, status, quality_score)
        VALUES (v_type_id, v_ckey, v_cname, 'ACTIVE', 1.00)
        ON CONFLICT (entity_type_id, canonical_key) DO NOTHING
        RETURNING golden_id INTO v_gid;

        IF v_gid IS NULL THEN
            SELECT golden_id INTO v_gid FROM mdm.golden_records
            WHERE entity_type_id = v_type_id AND canonical_key = v_ckey;
        END IF;

        INSERT INTO mdm.source_mappings (golden_id, source_system, source_key, normalized_key, is_canonical)
        VALUES
            (v_gid, 'WMS', v_ckey, lower(v_ckey), TRUE),
            (v_gid, 'TMS', v_ckey, lower(v_ckey), FALSE)
        ON CONFLICT (source_system, source_key) DO NOTHING;
    END LOOP;
    RAISE NOTICE 'SUPPLY_CHAIN_NODE: % Golden Records angelegt', array_length(nodes, 1);

END $$;

-- -----------------------------------------------------------------------------
-- Hilfsfunktion: Schlüsselharmonisierung
-- Gibt den kanonischen Golden-Record-Key zurück für einen gegebenen source_key
-- Verwendung: SELECT mdm.resolve_canonical_key('BAN_101', 'WMS');
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION mdm.resolve_canonical_key(
    p_source_key    VARCHAR,
    p_source_system VARCHAR
) RETURNS VARCHAR AS $$
DECLARE
    v_canonical_key VARCHAR;
BEGIN
    SELECT gr.canonical_key
    INTO   v_canonical_key
    FROM   mdm.source_mappings sm
    JOIN   mdm.golden_records  gr ON sm.golden_id = gr.golden_id
    WHERE  sm.source_key    = p_source_key
    AND    sm.source_system = p_source_system
    AND    gr.status        = 'ACTIVE';

    RETURN v_canonical_key;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION mdm.resolve_canonical_key IS
    'Löst einen systemspezifischen Schlüssel in den kanonischen ERP-Schlüssel auf. '
    'Beispiel: mdm.resolve_canonical_key(''BAN_101'', ''WMS'') → ''BAN-101''';

-- -----------------------------------------------------------------------------
-- Hilfsfunktion: Fuzzy-Schlüsselauflösung (systemunabhängig, normalisierend)
-- Löst einen Schlüssel in beliebigem Format auf den kanonischen Wert auf.
-- Schritt 1: exakter Treffer über source_key in allen Systemen
-- Schritt 2: normalisierter Treffer über normalized_key (Fallback)
-- Verwendung: SELECT mdm.resolve_canonical_key_fuzzy('BAN_108');  → 'BAN-108'
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION mdm.resolve_canonical_key_fuzzy(
    p_raw_key VARCHAR
) RETURNS VARCHAR AS $$
DECLARE
    v_canonical_key VARCHAR;
    v_normalized    VARCHAR;
BEGIN
    -- Exakter Treffer: deckt alle bekannten source_keys ab
    SELECT gr.canonical_key INTO v_canonical_key
    FROM   mdm.source_mappings sm
    JOIN   mdm.golden_records  gr ON sm.golden_id = gr.golden_id
    WHERE  sm.source_key = p_raw_key
    AND    gr.status     = 'ACTIVE'
    LIMIT 1;

    IF v_canonical_key IS NOT NULL THEN
        RETURN v_canonical_key;
    END IF;

    -- Fallback: Normalisierung (Kleinbuchstaben, Unterstriche → Bindestriche)
    -- deckt unbekannte Schreibweisen wie 'ban_108' oder 'BAN 108' ab
    v_normalized := lower(replace(trim(p_raw_key), '_', '-'));

    SELECT gr.canonical_key INTO v_canonical_key
    FROM   mdm.source_mappings sm
    JOIN   mdm.golden_records  gr ON sm.golden_id = gr.golden_id
    WHERE  sm.normalized_key = v_normalized
    AND    gr.status         = 'ACTIVE'
    LIMIT 1;

    RETURN v_canonical_key;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION mdm.resolve_canonical_key_fuzzy IS
    'Normalisierungsbasierte Schlüsselauflösung ohne Systemangabe. '
    'Erst exakter Treffer, dann Fallback über normalized_key. '
    'Beispiel: mdm.resolve_canonical_key_fuzzy(''BAN_108'') → ''BAN-108''';

-- -----------------------------------------------------------------------------
-- Indizes
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_mdm_golden_records_type          ON mdm.golden_records(entity_type_id);
CREATE INDEX IF NOT EXISTS idx_mdm_golden_records_canonical     ON mdm.golden_records(canonical_key);
CREATE INDEX IF NOT EXISTS idx_mdm_source_mappings_golden       ON mdm.source_mappings(golden_id);
CREATE INDEX IF NOT EXISTS idx_mdm_source_mappings_source       ON mdm.source_mappings(source_system, source_key);
CREATE INDEX IF NOT EXISTS idx_mdm_source_mappings_normalized   ON mdm.source_mappings(normalized_key);

-- Erzwingt: genau ein is_canonical=TRUE pro Golden Record.
-- Verhindert den Fall, dass z.B. ERP- und WMS-Mapping beide als kanonisch markiert werden.
CREATE UNIQUE INDEX IF NOT EXISTS uq_mdm_one_canonical_per_entity
    ON mdm.source_mappings(golden_id)
    WHERE is_canonical = TRUE;

-- -----------------------------------------------------------------------------
-- Übersichts-View: alle Golden Records mit systemspezifischen Schlüsseln
-- Nützlich für Audits und DWH-Abfragen ohne expliziten JOIN auf source_mappings
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW mdm.v_golden_overview AS
SELECT
    et.entity_type_code                                                     AS entity_type,
    gr.canonical_key,
    gr.canonical_name,
    gr.status,
    gr.quality_score,
    MAX(sm.source_key) FILTER (WHERE sm.source_system = 'ERP')             AS erp_key,
    MAX(sm.source_key) FILTER (WHERE sm.source_system = 'WMS')             AS wms_key,
    MAX(sm.source_key) FILTER (WHERE sm.source_system = 'TMS')             AS tms_key,
    COUNT(sm.mapping_id)                                                    AS total_mappings
FROM  mdm.golden_records  gr
JOIN  mdm.entity_types    et ON et.entity_type_id  = gr.entity_type_id
LEFT JOIN mdm.source_mappings sm ON sm.golden_id   = gr.golden_id
GROUP BY et.entity_type_code, gr.golden_id, gr.canonical_key,
         gr.canonical_name, gr.status, gr.quality_score
ORDER BY et.entity_type_code, gr.canonical_key;

COMMENT ON VIEW mdm.v_golden_overview IS
    'Übersichts-View: ein Golden Record pro Zeile mit erp_key / wms_key / tms_key nebeneinander. '
    'Ermöglicht schnellen Audit der MDM-Abdeckung ohne manuellen JOIN auf source_mappings.';

-- =============================================================================
-- PRÜFQUERIES – MDM-Nachweis
-- Alle Queries müssen nach ETL-Ausführung die erwarteten Werte liefern.
-- =============================================================================

-- Abdeckung: Golden Records je Entity-Typ
-- Erwartet: CARRIER=5, CUSTOMER=10, PRODUCT=10, SUPPLIER=10, SUPPLY_CHAIN_NODE=7
SELECT
    et.entity_type_code,
    COUNT(gr.golden_id)                                    AS golden_records,
    COUNT(gr.golden_id) FILTER (WHERE gr.status = 'ACTIVE') AS active_records
FROM mdm.entity_types et
LEFT JOIN mdm.golden_records gr ON gr.entity_type_id = et.entity_type_id
GROUP BY et.entity_type_code
ORDER BY et.entity_type_code;

-- Source-Mapping-Abdeckung je Quellsystem
-- Erwartet: ERP=30 (10 Prod + 10 Cust + 10 Sup), WMS=17 (10 Prod + 7 Node), TMS=22 (10 Prod + 5 Car + 7 Node)
SELECT
    source_system,
    COUNT(*)                                     AS total_mappings,
    COUNT(*) FILTER (WHERE is_canonical = TRUE)  AS canonical_mappings
FROM mdm.source_mappings
GROUP BY source_system
ORDER BY source_system;

-- Kerntest: Schlüsselauflösung der drei Inkonsistenzformate
-- Alle drei müssen 'BAN-101' zurückgeben
SELECT
    mdm.resolve_canonical_key('BAN-101', 'ERP') AS erp_auflosung,   -- BAN-101 → BAN-101
    mdm.resolve_canonical_key('BAN_101', 'WMS') AS wms_auflosung,   -- BAN_101 → BAN-101
    mdm.resolve_canonical_key('ban-101', 'TMS') AS tms_auflosung;   -- ban-101 → BAN-101

-- Erweiterter Test: Fuzzy-Auflösung für BAN-108 in allen Schreibweisen
SELECT
    mdm.resolve_canonical_key_fuzzy('BAN-108') AS standard_format,  -- BAN-108 → BAN-108
    mdm.resolve_canonical_key_fuzzy('BAN_108') AS wms_format,       -- BAN_108 → BAN-108
    mdm.resolve_canonical_key_fuzzy('ban-108') AS tms_format,       -- ban-108 → BAN-108
    mdm.resolve_canonical_key_fuzzy('ban_108') AS hybrid_format;    -- ban_108 → BAN-108

-- Integritätsprüfung: Darf keine Zeilen zurückgeben (0 = korrekt)
-- Jeder Golden Record muss genau ein kanonisches Mapping haben
SELECT COUNT(*) AS verletzungen_is_canonical
FROM (
    SELECT golden_id, COUNT(*) FILTER (WHERE is_canonical) AS canon_count
    FROM   mdm.source_mappings
    GROUP  BY golden_id
    HAVING COUNT(*) FILTER (WHERE is_canonical) != 1
) t;

-- Cross-System-JOIN-Nachweis: Welche TMS-Cargo-Referenzen gehören zu ERP-Produkt BAN-108?
-- Zeigt dass MDM systemübergreifende Verknüpfungen ermöglicht.
SELECT
    sm_tms.source_key         AS tms_cargo_ref,
    gr.canonical_key          AS kanonischer_key,
    gr.canonical_name         AS produktname,
    sm_erp.source_key         AS erp_code
FROM   mdm.golden_records  gr
JOIN   mdm.source_mappings sm_tms ON sm_tms.golden_id    = gr.golden_id
                                 AND sm_tms.source_system = 'TMS'
JOIN   mdm.source_mappings sm_erp ON sm_erp.golden_id    = gr.golden_id
                                 AND sm_erp.source_system = 'ERP'
WHERE  gr.canonical_key = 'BAN-108'
AND    gr.entity_type_id = (SELECT entity_type_id FROM mdm.entity_types WHERE entity_type_code = 'PRODUCT');

-- Übersichts-View nutzen: alle Produkte mit allen drei Systemschlüsseln
-- Zeigt das Ergebnis der Schlüsselharmonisierung in einer Zeile je Produkt
SELECT entity_type, canonical_key, canonical_name, erp_key, wms_key, tms_key
FROM   mdm.v_golden_overview
WHERE  entity_type = 'PRODUCT'
ORDER  BY canonical_key;

-- Diagnose-Query 1: WMS-SKUs ohne MDM-Mapping (muss 0 Zeilen liefern)
-- Erkennt neue Produkte, die im WMS auftauchen, bevor ihr Golden Record angelegt wurde.
SELECT ws.sku AS nicht_harmonisierte_wms_sku
FROM   wms.warehouse_skus ws
WHERE  NOT EXISTS (
    SELECT 1 FROM mdm.source_mappings sm
    WHERE  sm.source_system = 'WMS' AND sm.source_key = ws.sku
);

-- Diagnose-Query 2: TMS-Cargo-Referenzen ohne MDM-Mapping (muss 0 Zeilen liefern)
-- Erkennt Shipments, deren Produktreferenz vom MDM nicht aufgelöst werden kann.
SELECT DISTINCT s.cargo_product_reference AS nicht_harmonisierte_tms_ref
FROM   tms.shipments s
WHERE  NOT EXISTS (
    SELECT 1 FROM mdm.source_mappings sm
    WHERE  sm.source_system = 'TMS' AND sm.source_key = s.cargo_product_reference
);

DO $$
BEGIN
    RAISE NOTICE 'MDM-Tabellen erstellt: entity_types, golden_records, source_mappings';
    RAISE NOTICE 'Funktionen: resolve_canonical_key(), resolve_canonical_key_fuzzy()';
    RAISE NOTICE 'Golden Records: 42 (10 Produkte, 10 Kunden, 10 Lieferanten, 5 Carrier, 7 Nodes)';
    RAISE NOTICE 'Source Mappings: 69 (ERP=30, WMS=17, TMS=22)';
END $$;
