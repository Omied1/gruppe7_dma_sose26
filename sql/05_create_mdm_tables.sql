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
-- Beispieldaten: Produkt BAN-101 "Cavendish Banana"
-- Zeigt die vollständige MDM-Struktur für ein Produkt
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_product_type_id   INT;
    v_golden_id         INT;
BEGIN
    SELECT entity_type_id INTO v_product_type_id
    FROM mdm.entity_types WHERE entity_type_code = 'PRODUCT';

    -- Golden Record für BAN-101
    INSERT INTO mdm.golden_records (entity_type_id, canonical_key, canonical_name, status, quality_score)
    VALUES (v_product_type_id, 'BAN-101', 'Cavendish Banana', 'ACTIVE', 0.95)
    ON CONFLICT (entity_type_id, canonical_key) DO NOTHING
    RETURNING golden_id INTO v_golden_id;

    IF v_golden_id IS NOT NULL THEN
        -- ERP-Mapping (kanonisch)
        INSERT INTO mdm.source_mappings (golden_id, source_system, source_key, normalized_key, is_canonical)
        VALUES
            (v_golden_id, 'ERP', 'BAN-101', 'ban-101', TRUE),
            (v_golden_id, 'WMS', 'BAN_101', 'ban-101', FALSE),
            (v_golden_id, 'TMS', 'ban-101', 'ban-101', FALSE)
        ON CONFLICT (source_system, source_key) DO NOTHING;

        RAISE NOTICE 'MDM-Beispieldaten für BAN-101 eingefügt (golden_id=%)', v_golden_id;
    END IF;
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
-- Indizes
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_mdm_golden_records_type          ON mdm.golden_records(entity_type_id);
CREATE INDEX IF NOT EXISTS idx_mdm_golden_records_canonical     ON mdm.golden_records(canonical_key);
CREATE INDEX IF NOT EXISTS idx_mdm_source_mappings_golden       ON mdm.source_mappings(golden_id);
CREATE INDEX IF NOT EXISTS idx_mdm_source_mappings_source       ON mdm.source_mappings(source_system, source_key);

DO $$
BEGIN
    RAISE NOTICE 'MDM-Tabellen erstellt: entity_types, golden_records, source_mappings + Hilfsfunktion mdm.resolve_canonical_key()';
END $$;
