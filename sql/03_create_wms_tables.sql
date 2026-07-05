-- =============================================================================
-- 03_create_wms_tables.sql
-- WMS-Schema: Warehouse Management System der Banana Supply Chain
--
-- Tabellen:
--   wms.warehouse_skus      - WMS-spezifische Produktreferenzen (aus: WarehouseSKUCreated)
--   wms.supply_chain_nodes  - Bekannte Supply-Chain-Knoten (Stammdaten)
--   wms.node_processings    - Knotenverarbeitungsereignisse (aus: NodeProcessed)
--
-- Das WMS verwaltet die physische Warenbewegung durch alle Knoten der Supply Chain.
-- Die WMS-SKU (BAN_101) ist eine systemspezifische Darstellung des ERP-Codes (BAN-101).
--
-- Voraussetzung: 01_create_schemas.sql muss vorher ausgeführt worden sein.
-- Ausführung:    psql -h localhost -U user -d logistics -f 03_create_wms_tables.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- WMS-Produktreferenzen (SKUs)
-- Quelle: WarehouseSKUCreated-Events (shared/wms/)
-- WMS verwendet Unterstriche statt Bindestriche: BAN_101 statt BAN-101
-- erp_product_code ist die Cross-Reference zu erp.products.product_code
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wms.warehouse_skus (
    sku_id              SERIAL          PRIMARY KEY,
    erp_product_code    VARCHAR(20)     NOT NULL UNIQUE, -- Cross-Reference: "BAN-101"
    sku                 VARCHAR(20)     NOT NULL UNIQUE, -- WMS-Format: "BAN_101" (Unterstriche)
    event_timestamp     TIMESTAMP       NOT NULL,        -- Zeitstempel aus WarehouseSKUCreated-Event (JSON: timestamp)
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event        VARCHAR(50)     NOT NULL DEFAULT 'WarehouseSKUCreated'
);

COMMENT ON TABLE  wms.warehouse_skus IS 'WMS-spezifische Produktreferenzen (SKUs). sku verwendet Unterstriche, erp_product_code Bindestriche (MDM-Inkonsistenz).';
COMMENT ON COLUMN wms.warehouse_skus.erp_product_code IS 'Referenz auf ERP-Produktcode (BAN-101). Für FK-Auflösung: JOIN auf erp.products.product_code.';
COMMENT ON COLUMN wms.warehouse_skus.sku              IS 'WMS-internes Format mit Unterstrichen: BAN_101. Wird in NodeProcessed-Events verwendet.';

-- -----------------------------------------------------------------------------
-- Supply-Chain-Knoten (Stammdaten)
-- Nicht direkt aus einem Eventtyp, sondern aus der Domänenkenntnis des Prozesses.
-- Diese Tabelle definiert alle bekannten Knoten der Banana Supply Chain.
-- Annahme: Knoten sind Stammdaten und werden einmalig initialisiert.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wms.supply_chain_nodes (
    node_id         SERIAL          PRIMARY KEY,
    node_code       VARCHAR(50)     NOT NULL UNIQUE, -- z.B. "BANANA_PLANTATION"
    node_name       VARCHAR(100)    NOT NULL,
    node_type       VARCHAR(30)     NOT NULL CHECK (node_type IN (
                        'PLANTATION', 'COLLECTION_CENTER', 'QUALITY_CONTROL',
                        'COLD_STORAGE', 'WAREHOUSE', 'RETAIL'
                    )),
    region          VARCHAR(50),    -- z.B. "Africa", "Europe"
    sequence_order  INT             NOT NULL, -- Position im Supply-Chain-Flow (1-7)
    storage_cost_per_unit_day NUMERIC(8,4),  -- [ANPASSUNG 2026-07-05] Lagerkostensatz (EUR/Einheit/Tag), nur Lagerknoten
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- [ANPASSUNG 2026-07-05] Lagerkostensatz idempotent für bestehende DBs ergänzen und setzen.
-- [ANNAHME] Vereinfachte Sätze: Kühlknoten teurer als trockenes Lager (Energie/Kühlung);
-- Nicht-Lagerknoten (Plantage, Sammelstelle, QC, Retail) verursachen keine Lagerkosten.
ALTER TABLE wms.supply_chain_nodes ADD COLUMN IF NOT EXISTS storage_cost_per_unit_day NUMERIC(8,4);
UPDATE wms.supply_chain_nodes SET storage_cost_per_unit_day = CASE node_type
    WHEN 'COLD_STORAGE' THEN 0.0200   -- Kühlhaus: Energie + Kühlkette
    WHEN 'WAREHOUSE'    THEN 0.0120   -- Zentrallager: trockene Lagerung
    ELSE 0
END;

COMMENT ON TABLE  wms.supply_chain_nodes IS 'Stammdaten aller Supply-Chain-Knoten. sequence_order definiert die logische Reihenfolge im Prozessfluss. Hinweis: RETAIL_STORE ist als Knoten modelliert, erzeugt aber keine NodeProcessed-Events – der Retail Store liegt außerhalb des WMS-Verantwortungsbereichs und wird ausschließlich über TMS DeliveryCompleted-Events abgebildet.';
COMMENT ON COLUMN wms.supply_chain_nodes.node_code      IS 'Interner Code wie im Datengenerator: BANANA_PLANTATION, COLLECTION_CENTER, etc.';
COMMENT ON COLUMN wms.supply_chain_nodes.sequence_order IS 'Reihenfolge im Supply-Chain-Flow: 1=Plantation, 2=Collection, ..., 7=Retail.';

-- Stammdaten: Knoten der Banana Supply Chain
-- node_name entspricht dem kanonischen Namen aus mdm.golden_records (05_create_mdm_tables.sql).
-- Änderungen hier müssen mit MDM-Seed-Daten und etl_load.py (_SUPPLY_CHAIN_NODES) abgestimmt sein.
INSERT INTO wms.supply_chain_nodes (node_code, node_name, node_type, region, sequence_order)
VALUES
    ('BANANA_PLANTATION',   'Banana Plantation Ghana', 'PLANTATION',        'Africa',  1),
    ('COLLECTION_CENTER',   'Collection Center',       'COLLECTION_CENTER', 'Africa',  2),
    ('QUALITY_CONTROL',     'Quality Control Station', 'QUALITY_CONTROL',   'Africa',  3),
    ('AFRICA_COLD_STORAGE', 'Africa Cold Storage',     'COLD_STORAGE',      'Africa',  4),
    ('EUROPE_COLD_STORAGE', 'Europe Cold Storage',     'COLD_STORAGE',      'Europe',  5),
    ('CENTRAL_WAREHOUSE',   'Central Warehouse',       'WAREHOUSE',         'Europe',  6),
    ('RETAIL_STORE',        'Retail Store',            'RETAIL',            'Europe',  7)
ON CONFLICT (node_code) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Knotenverarbeitungsereignisse
-- Quelle: NodeProcessed-Events (shared/wms/)
-- Dokumentiert, dass ein Batch einen bestimmten Knoten durchlaufen hat
-- temperature ist qualitätskritisch: Kühlkette muss zwischen 10-15°C gehalten werden
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wms.node_processings (
    processing_id   SERIAL          PRIMARY KEY,
    node_id         INT             NOT NULL REFERENCES wms.supply_chain_nodes(node_id),
    batch_reference VARCHAR(60)     NOT NULL,   -- FK-Referenz auf erp.batches.batch_identifier
    sku             VARCHAR(20)     NOT NULL,    -- WMS-Format: BAN_108 (unverändertes Quellformat, kein normalize_key())
    temperature     NUMERIC(5,2),               -- Lagertemperatur in °C (Kühlkette: 10-15°C)
    status          VARCHAR(20)     NOT NULL CHECK (status IN ('COMPLETED', 'PENDING', 'FAILED')),
    processed_at    TIMESTAMP       NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event    VARCHAR(50)     NOT NULL DEFAULT 'NodeProcessed',
    -- Idempotenz: Jeder Batch durchläuft jeden Knoten genau einmal
    CONSTRAINT uq_wms_nodeprocessing_batch_node UNIQUE (batch_reference, node_id)
);

COMMENT ON TABLE  wms.node_processings IS 'Protokoll der Knotenverarbeitungen. Jeder Batch durchläuft alle 7 Knoten. temperature dokumentiert die Kühlkette (Soll: 10-15°C).';
COMMENT ON COLUMN wms.node_processings.batch_reference IS 'Referenz auf erp.batches.batch_identifier (kein FK da Cross-Schema, Integrität via ETL).';
COMMENT ON COLUMN wms.node_processings.temperature     IS 'Containertemperatur in °C. Plausibel: 10.0 – 15.0°C. Abweichungen sind Qualitätsverstöße.';
COMMENT ON COLUMN wms.node_processings.sku             IS 'WMS-SKU-Format (BAN_108). Harmonisierung mit ERP-Code via mdm.source_mappings.';

-- -----------------------------------------------------------------------------
-- Bestandsbewegungen (einfaches Inventory-Modell)
-- [ANPASSUNG 2026-07-05] KEIN eigener Quell-Eventtyp: Bewegungen werden im ETL
-- deterministisch aus NodeProcessed abgeleitet (IN = Ankunft am Knoten,
-- OUT = Ankunft am Folgeknoten; letzter WMS-Knoten: OUT = delivered_at der
-- Endlieferung). Dadurch keine neuen JSON-Dateien und strukturell keine
-- negativen Bestände (IN liegt je Batch/Knoten immer vor OUT).
-- Idempotenz: ETL leert die Tabelle vor dem Ableiten (DELETE + Rebuild).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wms.stock_movements (
    movement_id     SERIAL          PRIMARY KEY,
    node_id         INT             NOT NULL REFERENCES wms.supply_chain_nodes(node_id),
    sku             VARCHAR(20)     NOT NULL,   -- WMS-Format (BAN_108), wie node_processings.sku
    batch_reference VARCHAR(60)     NOT NULL,   -- Referenz auf erp.batches.batch_identifier
    quantity        INT             NOT NULL CHECK (quantity > 0),
    direction       VARCHAR(3)      NOT NULL CHECK (direction IN ('IN', 'OUT')),
    moved_at        TIMESTAMP       NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    source          VARCHAR(50)     NOT NULL DEFAULT 'ETL_DERIVED_NodeProcessed',
    -- Jeder Batch hat je Knoten genau einen Wareneingang und einen Warenausgang
    CONSTRAINT uq_wms_stock_movement UNIQUE (batch_reference, node_id, direction)
);

COMMENT ON TABLE  wms.stock_movements IS 'Bestandsbewegungen je Knoten/SKU/Batch (IN = Wareneingang, OUT = Warenausgang). Im ETL deterministisch aus NodeProcessed + Endlieferung abgeleitet, kein eigener Quell-Eventtyp. Aktueller Bestand am Simulationsende ist 0 (alle Batches ausgeliefert), daher bewusst keine Redis-Echtzeitbestände.';
COMMENT ON COLUMN wms.stock_movements.direction IS 'IN = Ankunft am Knoten (processed_at), OUT = Abgang (Ankunft Folgeknoten bzw. delivered_at am letzten WMS-Knoten).';
COMMENT ON COLUMN wms.stock_movements.quantity  IS 'Batchmenge in Kartons (erp.batches.quantity). [ANNAHME] Schwund reduziert die Bewegungsmenge nicht (vereinfachtes Modell).';

-- -----------------------------------------------------------------------------
-- Indizes für Performance
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_wms_node_processings_node        ON wms.node_processings(node_id);
CREATE INDEX IF NOT EXISTS idx_wms_node_processings_batch       ON wms.node_processings(batch_reference);
CREATE INDEX IF NOT EXISTS idx_wms_node_processings_processed   ON wms.node_processings(processed_at);
CREATE INDEX IF NOT EXISTS idx_wms_node_processings_sku         ON wms.node_processings(sku);
CREATE INDEX IF NOT EXISTS idx_wms_stock_movements_node         ON wms.stock_movements(node_id, moved_at);
CREATE INDEX IF NOT EXISTS idx_wms_stock_movements_batch        ON wms.stock_movements(batch_reference);

DO $$
BEGIN
    RAISE NOTICE 'WMS-Tabellen erstellt: warehouse_skus, supply_chain_nodes (mit 7 Knoten + Lagerkostensätzen befüllt), node_processings, stock_movements';
END $$;
