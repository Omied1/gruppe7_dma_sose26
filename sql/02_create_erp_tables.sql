-- =============================================================================
-- 02_create_erp_tables.sql
-- ERP-Schema: Stamm- und Bewegungsdaten des Enterprise Resource Planning Systems
--
-- Tabellen:
--   erp.suppliers        - Lieferantenstammdaten (aus: SupplierCreated)
--   erp.customers        - Kundenstammdaten (aus: CustomerCreated)
--   erp.products         - Produktstammdaten (aus: ProductCreated)
--   erp.orders           - Bestellköpfe (aus: OrderCreated)
--   erp.order_items      - Bestellpositionen (aus: OrderCreated.items[])
--   erp.batches          - Ernte-Batches (aus: BatchHarvested)
--
-- Voraussetzung: 01_create_schemas.sql muss vorher ausgeführt worden sein.
-- Ausführung:    psql -h localhost -U user -d logistics -f 02_create_erp_tables.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Lieferantenstammdaten
-- Quelle: SupplierCreated-Events (shared/erp/)
-- Kanonischer Business Key: supplier_code (z.B. "SUP-101")
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.suppliers (
    supplier_id     SERIAL          PRIMARY KEY,
    supplier_code   VARCHAR(20)     NOT NULL UNIQUE,    -- Business Key, z.B. "SUP-101"
    supplier_name   VARCHAR(100)    NOT NULL,
    country         VARCHAR(50)     NOT NULL,
    event_timestamp TIMESTAMP       NOT NULL,           -- Zeitstempel aus SupplierCreated-Event (JSON: timestamp)
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event    VARCHAR(50)     NOT NULL DEFAULT 'SupplierCreated'
);

COMMENT ON TABLE  erp.suppliers IS 'Lieferantenstammdaten aus ERP. supplier_code ist kanonischer Business Key im MDM.';
COMMENT ON COLUMN erp.suppliers.supplier_code IS 'Kanonischer Schlüssel im Format SUP-NNN. Wird im MDM als Golden Record geführt.';

-- -----------------------------------------------------------------------------
-- Kundenstammdaten
-- Quelle: CustomerCreated-Events (shared/erp/)
-- Kanonischer Business Key: customer_number (z.B. "CUST-101")
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.customers (
    customer_id     SERIAL          PRIMARY KEY,
    customer_number VARCHAR(20)     NOT NULL UNIQUE,    -- Business Key, z.B. "CUST-101"
    customer_name   VARCHAR(100)    NOT NULL,
    city            VARCHAR(50),
    country         VARCHAR(50)     NOT NULL,
    event_timestamp TIMESTAMP       NOT NULL,           -- Zeitstempel aus CustomerCreated-Event (JSON: timestamp)
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event    VARCHAR(50)     NOT NULL DEFAULT 'CustomerCreated'
);

COMMENT ON TABLE  erp.customers IS 'Kundenstammdaten aus ERP. Kunden sind Einzelhandelsketten (ALDI, LIDL, REWE etc.).';
COMMENT ON COLUMN erp.customers.customer_number IS 'Kanonischer Schlüssel im Format CUST-NNN.';

-- -----------------------------------------------------------------------------
-- Produktstammdaten
-- Quelle: ProductCreated-Events (shared/erp/)
-- Kanonischer Business Key: product_code (z.B. "BAN-101")
-- WICHTIG: WMS und TMS verwenden andere Formate (BAN_101, ban-101) → MDM notwendig
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.products (
    product_id      SERIAL          PRIMARY KEY,
    product_code    VARCHAR(20)     NOT NULL UNIQUE,    -- Kanonischer Key, z.B. "BAN-101"
    product_name    VARCHAR(100)    NOT NULL,
    category        VARCHAR(50)     NOT NULL,
    supplier_id     INT             REFERENCES erp.suppliers(supplier_id),
    -- Nullable wegen ETL-Zweiphasen-Lade: erst product_code, dann supplier_id per UPDATE-Pass
    event_timestamp TIMESTAMP       NOT NULL,           -- Zeitstempel aus ProductCreated-Event (JSON: timestamp)
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event    VARCHAR(50)     NOT NULL DEFAULT 'ProductCreated'
);

COMMENT ON TABLE  erp.products IS 'Produktstammdaten aus ERP. product_code ist kanonischer Business Key. WMS und TMS verwenden abweichende Formate (MDM erforderlich).';
COMMENT ON COLUMN erp.products.product_code IS 'ERP-Format: BAN-101. WMS-Format: BAN_101. TMS-Format: ban-101. Harmonisierung via mdm.source_mappings.';
COMMENT ON COLUMN erp.products.supplier_id  IS 'FK zu erp.suppliers. Jedes Produkt hat genau einen Lieferanten.';

-- -----------------------------------------------------------------------------
-- Bestellköpfe
-- Quelle: OrderCreated-Events (shared/erp/)
-- Jede Bestellung hat genau einen Kunden und eine Lieferpriorität
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.orders (
    order_id            SERIAL          PRIMARY KEY,
    order_reference     VARCHAR(60)     NOT NULL UNIQUE, -- UUID-basiert, z.B. "ORD-<uuid>"
    customer_id         INT             NOT NULL REFERENCES erp.customers(customer_id),
    delivery_priority   VARCHAR(10)     NOT NULL CHECK (delivery_priority IN ('HIGH', 'NORMAL', 'LOW')),
    order_timestamp     TIMESTAMP       NOT NULL,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event        VARCHAR(50)     NOT NULL DEFAULT 'OrderCreated'
);

COMMENT ON TABLE  erp.orders IS 'Bestellköpfe aus ERP. Eine Order initiiert den gesamten Supply-Chain-Prozess.';
COMMENT ON COLUMN erp.orders.order_reference    IS 'UUID-basierter Bestellreferenzcode aus dem ERP-Event.';
COMMENT ON COLUMN erp.orders.delivery_priority  IS 'Lieferpriorität: HIGH, NORMAL, LOW. Steuert Prozessreihenfolge im Fulfillment.';

-- -----------------------------------------------------------------------------
-- Bestellpositionen
-- Quelle: OrderCreated-Events, Feld items[]
-- Normalisiert aus dem verschachtelten items-Array
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.order_items (
    item_id         SERIAL          PRIMARY KEY,
    order_id        INT             NOT NULL REFERENCES erp.orders(order_id),
    product_id      INT             NOT NULL REFERENCES erp.products(product_id),
    quantity        INT             NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(10,2)   NOT NULL CHECK (unit_price > 0),
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  erp.order_items IS 'Bestellpositionen, normalisiert aus OrderCreated.items[]. Jede Position hat Menge und Einzelpreis.';
COMMENT ON COLUMN erp.order_items.quantity   IS 'Bestellmenge in Einheiten. Muss > 0 sein (CHECK-Constraint).';
COMMENT ON COLUMN erp.order_items.unit_price IS 'Einzelpreis in EUR. Plausibilitätsbereich: 1.50 – 5.00 EUR laut Datengenerator.';

-- -----------------------------------------------------------------------------
-- Ernte-Batches
-- Quelle: BatchHarvested-Events (shared/erp/)
-- Verbindet ERP-Produktcode mit WMS-SKU und TMS-Produktreferenz
-- Dieses Objekt ist das Kernstück der systemübergreifenden Nachverfolgung
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.batches (
    batch_id                    SERIAL          PRIMARY KEY,
    batch_identifier            VARCHAR(60)     NOT NULL UNIQUE, -- z.B. "BATCH-<uuid>"
    product_id                  INT             NOT NULL REFERENCES erp.products(product_id),
    -- Kein order_id FK: BatchHarvested-Events enthalten keine Bestellreferenz.
    -- Produkt-Order-Verknüpfung erfolgt über product_code via erp.order_items.
    origin_country              VARCHAR(50)     NOT NULL,
    quantity                    INT             NOT NULL CHECK (quantity > 0),
    supply_chain_node           VARCHAR(50)     NOT NULL DEFAULT 'BANANA_PLANTATION',
    -- Cross-System-Referenzen (werden auch im MDM geführt)
    wms_sku                     VARCHAR(30),    -- WMS-Format: BAN_108
    tms_product_reference       VARCHAR(30),    -- TMS-Format: ban-108
    harvested_at                TIMESTAMP       NOT NULL, -- = event_timestamp (JSON: timestamp)
    created_at                  TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event                VARCHAR(50)     NOT NULL DEFAULT 'BatchHarvested'
);

COMMENT ON TABLE  erp.batches IS 'Ernte-Batches aus ERP. Verbindet ERP-Produktcode mit WMS-SKU und TMS-Referenz. Zentrales Tracking-Objekt der Supply Chain. Kein FK zu orders – BatchHarvested enthält keine Bestellreferenz.';
COMMENT ON COLUMN erp.batches.batch_identifier        IS 'Eindeutiger Batch-Identifier im Format BATCH-<uuid>.';
COMMENT ON COLUMN erp.batches.wms_sku                 IS 'WMS-spezifische SKU (Unterstriche statt Bindestriche). Redundant mit mdm.source_mappings.';
COMMENT ON COLUMN erp.batches.tms_product_reference   IS 'TMS-spezifische Produktreferenz (Kleinbuchstaben). Redundant mit mdm.source_mappings.';
COMMENT ON COLUMN erp.batches.harvested_at            IS 'Erntezeitpunkt = event.timestamp aus BatchHarvested. Entspricht dem event_timestamp-Muster der Stammdatentabellen.';

-- -----------------------------------------------------------------------------
-- Tabelle: erp.document_references
-- Speichert MinIO-Pfade zu Dokumenten (Rechnungen, Lieferscheine etc.)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.document_references (
    ref_id        SERIAL       PRIMARY KEY,
    entity_type   VARCHAR(20)  NOT NULL,
    entity_key    VARCHAR(100) NOT NULL,
    document_type VARCHAR(30)  NOT NULL,
    bucket        VARCHAR(50)  NOT NULL,
    object_path   VARCHAR(200) NOT NULL,
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    UNIQUE (entity_key, document_type)
);

-- -----------------------------------------------------------------------------
-- Indizes für Performance
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_erp_products_supplier    ON erp.products(supplier_id);
CREATE INDEX IF NOT EXISTS idx_erp_orders_customer      ON erp.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_erp_orders_timestamp     ON erp.orders(order_timestamp);
CREATE INDEX IF NOT EXISTS idx_erp_order_items_order    ON erp.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_erp_order_items_product  ON erp.order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_erp_batches_product      ON erp.batches(product_id);
CREATE INDEX IF NOT EXISTS idx_erp_batches_harvested    ON erp.batches(harvested_at);
CREATE INDEX IF NOT EXISTS idx_erp_docrefs_entity       ON erp.document_references(entity_key, document_type);

DO $$
BEGIN
    RAISE NOTICE 'ERP-Tabellen erstellt: suppliers, customers, products, orders, order_items, batches, document_references';
END $$;
