-- =============================================================================
-- 07_create_dwh_schema.sql
-- Data Warehouse – Sternschema für die Banana Supply Chain
--
-- WICHTIG: Dieses Schema ist KEIN operatives System.
-- Es wird AUSSCHLIESSLICH durch ETL-Prozesse aus ERP/WMS/TMS befüllt.
-- Direkte Schreibzugriffe aus operativen Systemen sind nicht vorgesehen.
--
-- Architektur: Sternschema (Star Schema)
--   Faktentabelle: dwh.fact_fulfillment
--   Dimensionen:  dim_customer, dim_product, dim_supplier, dim_carrier,
--                 dim_supply_chain_node, dim_date, dim_delivery_status
--
-- Voraussetzung: 01_create_schemas.sql muss vorher ausgeführt worden sein.
-- Ausführung:    psql -h localhost -U user -d logistics -f 07_create_dwh_schema.sql
-- =============================================================================

-- =============================================================================
-- DIMENSIONSTABELLEN
-- Denormalisiert für Analytics-Performance (wenige JOINs in Abfragen)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Dimension: Kunde
-- Quelle: erp.customers (via ETL)
-- Enthält denormalisierte Kundenattribute für Slicing & Dicing
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_customer (
    customer_sk         SERIAL          PRIMARY KEY,        -- Surrogate Key (DWH-intern)
    customer_number     VARCHAR(20)     NOT NULL UNIQUE,    -- Business Key aus ERP
    customer_name       VARCHAR(100)    NOT NULL,
    city                VARCHAR(50),
    country             VARCHAR(50)     NOT NULL,
    source_created_at   TIMESTAMP,                         -- event_timestamp aus erp.customers (CustomerCreated)
    etl_loaded_at       TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  dwh.dim_customer IS 'Kunden-Dimension. Denormalisiert aus erp.customers via ETL. customer_number ist Business Key.';
COMMENT ON COLUMN dwh.dim_customer.customer_sk        IS 'Surrogate Key (DWH-intern). Wird in fact_fulfillment als FK verwendet.';
COMMENT ON COLUMN dwh.dim_customer.source_created_at  IS 'Originalzeitstempel aus CustomerCreated-Event. Ermöglicht Analyse: Neukunden pro Zeitraum.';

-- -----------------------------------------------------------------------------
-- Dimension: Produkt
-- Quelle: erp.products + erp.suppliers (via ETL, denormalisiert)
-- Enthält auch Lieferanteninformationen für bessere Abfragbarkeit
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_product (
    product_sk          SERIAL          PRIMARY KEY,
    product_code        VARCHAR(20)     NOT NULL UNIQUE,    -- Business Key: BAN-101
    product_name        VARCHAR(100)    NOT NULL,
    category            VARCHAR(50)     NOT NULL,
    supplier_code       VARCHAR(20),                        -- Denormalisiert aus erp.suppliers
    supplier_name       VARCHAR(100),
    supplier_country    VARCHAR(50),
    etl_loaded_at       TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  dwh.dim_product IS 'Produkt-Dimension. Enthält denormalisierte Lieferanteninfo (Supplier in Produkt "eingefaltet") für einfachere Abfragen.';

-- -----------------------------------------------------------------------------
-- Dimension: Lieferant (separat für eigenständige Lieferantenanalyse)
-- Quelle: erp.suppliers (via ETL)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_supplier (
    supplier_sk         SERIAL          PRIMARY KEY,
    supplier_code       VARCHAR(20)     NOT NULL UNIQUE,    -- Business Key: SUP-101
    supplier_name       VARCHAR(100)    NOT NULL,
    country             VARCHAR(50)     NOT NULL,
    source_created_at   TIMESTAMP,                         -- event_timestamp aus erp.suppliers (SupplierCreated)
    etl_loaded_at       TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  dwh.dim_supplier IS 'Lieferanten-Dimension für eigenständige Lieferantenauswertungen (z.B. Lieferzuverlässigkeit pro Lieferant).';
COMMENT ON COLUMN dwh.dim_supplier.source_created_at IS 'Originalzeitstempel aus SupplierCreated-Event. Ermöglicht Analyse: Lieferantenalter vs. Qualitätskennzahlen.';

-- -----------------------------------------------------------------------------
-- Dimension: Carrier
-- Quelle: tms.carriers (via ETL)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_carrier (
    carrier_sk          SERIAL          PRIMARY KEY,
    carrier_code        VARCHAR(20)     NOT NULL UNIQUE,    -- Business Key: CAR-101
    carrier_name        VARCHAR(100)    NOT NULL,
    source_created_at   TIMESTAMP,                         -- event_timestamp aus tms.carriers (CarrierCreated)
    etl_loaded_at       TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  dwh.dim_carrier IS 'Carrier-Dimension für Transportdienstleister-Analysen (z.B. durchschnittliche Verzögerung pro Carrier).';
COMMENT ON COLUMN dwh.dim_carrier.source_created_at IS 'Originalzeitstempel aus CarrierCreated-Event. Ermöglicht Analyse: Carrier-Performance seit Onboarding.';

-- -----------------------------------------------------------------------------
-- Dimension: Supply-Chain-Knoten
-- Quelle: wms.supply_chain_nodes (via ETL)
-- Ermöglicht Knotenanalysen (z.B. Durchlaufzeiten, Temperaturen pro Station)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_supply_chain_node (
    node_sk             SERIAL          PRIMARY KEY,
    node_code           VARCHAR(50)     NOT NULL UNIQUE,
    node_name           VARCHAR(100)    NOT NULL,
    node_type           VARCHAR(30)     NOT NULL,
    region              VARCHAR(50),
    sequence_order      INT             NOT NULL,
    etl_loaded_at       TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  dwh.dim_supply_chain_node IS 'Supply-Chain-Knoten-Dimension. Ermöglicht Analysen pro Station (Plantation, Cold Storage, Warehouse etc.).';

-- -----------------------------------------------------------------------------
-- Dimension: Datum
-- Wird durch ETL-Prozess für alle relevanten Zeiträume vorab befüllt (Date Spine)
-- Ermöglicht effiziente Zeitreihenanalysen ohne Datumsfunktionen in Abfragen
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_date (
    date_sk             INT             PRIMARY KEY,        -- Format: YYYYMMDD, z.B. 20260512
    full_date           DATE            NOT NULL UNIQUE,
    year                INT             NOT NULL,
    quarter             INT             NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month               INT             NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name          VARCHAR(20)     NOT NULL,
    week_of_year        INT             NOT NULL,
    day_of_month        INT             NOT NULL,
    day_of_week         INT             NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    day_name            VARCHAR(20)     NOT NULL,
    is_weekend          BOOLEAN         NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE  dwh.dim_date IS 'Datums-Dimension (Date Spine). Vorab befüllt für alle relevanten Jahre. Ermöglicht schnelle Zeitreihenanalysen ohne Datumsfunktionen.';

-- Date Spine: 2025-01-01 bis 2027-12-31 (abdeckt den Projektzeitraum)
INSERT INTO dwh.dim_date (date_sk, full_date, year, quarter, month, month_name, week_of_year, day_of_month, day_of_week, day_name, is_weekend)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT,
    d,
    EXTRACT(YEAR  FROM d)::INT,
    EXTRACT(QUARTER FROM d)::INT,
    EXTRACT(MONTH FROM d)::INT,
    TO_CHAR(d, 'Month'),
    EXTRACT(WEEK  FROM d)::INT,
    EXTRACT(DAY   FROM d)::INT,
    EXTRACT(DOW   FROM d)::INT + 1,  -- 1=Sonntag, 7=Samstag
    TO_CHAR(d, 'Day'),
    EXTRACT(DOW FROM d) IN (0, 6)
FROM GENERATE_SERIES('2025-01-01'::DATE, '2027-12-31'::DATE, '1 day'::INTERVAL) AS d
ON CONFLICT (date_sk) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Dimension: Lieferstatus
-- Kleine Lookup-Tabelle für Delivery-Status-Analyse
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_delivery_status (
    status_sk           SERIAL          PRIMARY KEY,
    status_code         VARCHAR(20)     NOT NULL UNIQUE,
    status_name         VARCHAR(50)     NOT NULL,
    is_successful       BOOLEAN         NOT NULL DEFAULT FALSE,
    description         TEXT
);

INSERT INTO dwh.dim_delivery_status (status_code, status_name, is_successful, description) VALUES
    ('SUCCESSFUL', 'Erfolgreich geliefert',     TRUE,  'Ware pünktlich und vollständig beim Kunden angekommen'),
    ('DELAYED',    'Verzögert geliefert',       TRUE,  'Ware angekommen, aber mit Zeitverzögerung'),
    ('FAILED',     'Lieferung fehlgeschlagen',  FALSE, 'Ware nicht beim Kunden angekommen'),
    ('IN_TRANSIT', 'Zwischenhop in Lieferkette', FALSE, 'Transportetappe ohne Endlieferung (Plantation -> ... -> RETAIL_STORE)')
ON CONFLICT (status_code) DO NOTHING;

-- =============================================================================
-- FAKTENTABELLE
-- Grain: Eine Zeile pro abgeschlossenem Fulfillment-Vorgang
--        (1 Order-Item → 1 Batch → 1 finaler Transport → 1 Delivery)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dwh.fact_fulfillment (
    fulfillment_sk          SERIAL          PRIMARY KEY,

    -- Dimensions-FKs (Surrogate Keys)
    customer_sk             INT             NOT NULL REFERENCES dwh.dim_customer(customer_sk),
    product_sk              INT             NOT NULL REFERENCES dwh.dim_product(product_sk),
    supplier_sk             INT             NOT NULL REFERENCES dwh.dim_supplier(supplier_sk),
    carrier_sk              INT             REFERENCES dwh.dim_carrier(carrier_sk),
    destination_node_sk     INT             REFERENCES dwh.dim_supply_chain_node(node_sk),
    order_date_sk           INT             REFERENCES dwh.dim_date(date_sk),
    delivery_date_sk        INT             REFERENCES dwh.dim_date(date_sk),
    delivery_status_sk      INT             NOT NULL REFERENCES dwh.dim_delivery_status(status_sk),

    -- Business Keys (für Nachverfolgung)
    order_reference         VARCHAR(60),    -- erp.orders.order_reference
    batch_identifier        VARCHAR(60),    -- erp.batches.batch_identifier
    shipment_identifier     VARCHAR(60),    -- tms.shipments.shipment_identifier

    -- Kennzahlen (Measures)
    quantity                INT             NOT NULL,       -- Bestellmenge
    unit_price              NUMERIC(10,2)   NOT NULL,       -- Einzelpreis
    total_value             NUMERIC(12,2)   NOT NULL,       -- Gesamtwert (quantity × unit_price)
    delay_minutes           INT             DEFAULT 0,      -- Gesamtverzögerung in Minuten
    avg_temperature         NUMERIC(5,2),                   -- Durchschn. Temperatur über alle Knoten
    num_supply_chain_hops   INT             DEFAULT 6,      -- Anzahl durchlaufener Knoten (Standard: 6)
    delivery_priority_code  VARCHAR(10),                    -- HIGH / NORMAL / LOW

    -- Abgeleitete KPI-Flags (berechnet im ETL, vermeidet redundante CASE-Logik in Analytics)
    on_time_flag            BOOLEAN,                        -- TRUE = SUCCESSFUL + delay_minutes = 0

    -- ETL-Metadaten
    etl_loaded_at           TIMESTAMP       NOT NULL DEFAULT NOW(),
    etl_source              VARCHAR(50)     NOT NULL DEFAULT 'ETL'
);

COMMENT ON TABLE  dwh.fact_fulfillment IS
    'Faktentabelle: Ein Datensatz pro abgeschlossenem Fulfillment-Vorgang. '
    'Grain: 1 Bestellposition → 1 Batch → 1 finaler Transport → 1 Lieferung. '
    'KEIN direkter Schreibzugriff aus operativen Systemen – nur via ETL.';

COMMENT ON COLUMN dwh.fact_fulfillment.total_value         IS 'Berechnete Kennzahl: quantity × unit_price. Basiskennzahl für Umsatzanalysen.';
COMMENT ON COLUMN dwh.fact_fulfillment.delay_minutes       IS 'Summierte Verzögerungsminuten aller Transporte im Fulfillment-Vorgang.';
COMMENT ON COLUMN dwh.fact_fulfillment.avg_temperature     IS 'Durchschnittliche Containertemperatur über alle Knotenverarbeitungen. Kühlketten-KPI.';
COMMENT ON COLUMN dwh.fact_fulfillment.num_supply_chain_hops IS 'Anzahl durchlaufener Knoten. Standard: 6. Abweichungen deuten auf Prozessänderungen hin.';
COMMENT ON COLUMN dwh.fact_fulfillment.on_time_flag        IS 'TRUE = pünktliche Lieferung (status=SUCCESSFUL und delay_minutes=0). Basisflag für Liefertreue-KPI.';

-- -----------------------------------------------------------------------------
-- Indizes für Analytics-Performance
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_dwh_fact_customer        ON dwh.fact_fulfillment(customer_sk);
CREATE INDEX IF NOT EXISTS idx_dwh_fact_product         ON dwh.fact_fulfillment(product_sk);
CREATE INDEX IF NOT EXISTS idx_dwh_fact_supplier        ON dwh.fact_fulfillment(supplier_sk);
CREATE INDEX IF NOT EXISTS idx_dwh_fact_carrier         ON dwh.fact_fulfillment(carrier_sk);
CREATE INDEX IF NOT EXISTS idx_dwh_fact_order_date      ON dwh.fact_fulfillment(order_date_sk);
CREATE INDEX IF NOT EXISTS idx_dwh_fact_delivery_date   ON dwh.fact_fulfillment(delivery_date_sk);
CREATE INDEX IF NOT EXISTS idx_dwh_fact_status          ON dwh.fact_fulfillment(delivery_status_sk);

-- -----------------------------------------------------------------------------
-- Upgrade bestehender Installationen: neue Spalten idempotent ergänzen
-- (harmlos, wenn die Tabelle gerade neu angelegt wurde)
-- -----------------------------------------------------------------------------
ALTER TABLE dwh.fact_fulfillment ADD COLUMN IF NOT EXISTS on_time_flag BOOLEAN;

-- =============================================================================
-- ANALYTISCHE VIEWS
-- Vorberechnete Sichten für PowerBI und Python-Analytics (Teil 2)
-- Kein eigener Datenbestand – nur Lesezugriff auf fact_fulfillment + Dimensionen
-- =============================================================================

-- -----------------------------------------------------------------------------
-- View: Carrier-Performance
-- Grain: 1 Zeile pro Carrier
-- Verwendung: PowerBI KPI-Card „On-Time-Delivery-Rate", Python-Chart „Verzögerungen nach Carrier"
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW dwh.v_carrier_performance AS
SELECT
    ca.carrier_code,
    ca.carrier_name,
    COUNT(*)                                                                          AS total_hops,
    SUM(CASE WHEN f.on_time_flag = TRUE  THEN 1 ELSE 0 END)                          AS on_time_count,
    SUM(CASE WHEN f.on_time_flag = FALSE THEN 1 ELSE 0 END)                          AS delayed_count,
    ROUND(
        100.0 * SUM(CASE WHEN f.on_time_flag = TRUE THEN 1 ELSE 0 END) / COUNT(*), 1
    )                                                                                 AS otd_rate_pct,
    ROUND(AVG(f.delay_minutes), 1)                                                    AS avg_delay_minutes,
    MAX(f.delay_minutes)                                                              AS max_delay_minutes
FROM  dwh.fact_fulfillment    f
JOIN  dwh.dim_carrier         ca ON ca.carrier_sk = f.carrier_sk
GROUP BY ca.carrier_code, ca.carrier_name;

COMMENT ON VIEW dwh.v_carrier_performance IS
    'Carrier-Performance-Übersicht: OTD-Rate, Ø Verzögerung, Max-Verzögerung pro Transportdienstleister. Quelle: fact_fulfillment + dim_carrier.';

-- -----------------------------------------------------------------------------
-- View: KPI-Zusammenfassung
-- Grain: 1 Zeile (Gesamtaggregat über alle Fulfillment-Vorgänge)
-- Verwendung: PowerBI KPI-Cards (Liefertreue, Ø Bestellwert, Temperaturausreißer)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW dwh.v_kpi_summary AS
SELECT
    COUNT(*)                                                                 AS total_fulfillments,
    -- KPI 1: Liefertreue
    ROUND(
        100.0 * SUM(CASE WHEN on_time_flag = TRUE THEN 1 ELSE 0 END) / COUNT(*), 1
    )                                                                        AS kpi_otd_rate_pct,
    -- KPI 2: Ø Transportdauer (gemessen als Verzögerung; 0 = planmäßig)
    ROUND(AVG(delay_minutes) / 60.0, 2)                                      AS kpi_avg_delay_hours,
    -- KPI 3: Temperaturausreißer-Quote (Kühlkette: 10–15 °C)
    ROUND(
        100.0 * SUM(CASE WHEN avg_temperature NOT BETWEEN 10 AND 15 THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN avg_temperature IS NOT NULL THEN 1 ELSE 0 END), 0), 1
    )                                                                        AS kpi_temp_outlier_pct,
    -- KPI 4: Ø Bestellwert
    ROUND(AVG(total_value), 2)                                               AS kpi_avg_order_value_eur,
    -- KPI 5: Gesamtumsatz
    ROUND(SUM(total_value), 2)                                               AS kpi_total_revenue_eur
FROM  dwh.fact_fulfillment;

COMMENT ON VIEW dwh.v_kpi_summary IS
    'Gesamtaggregat aller 5 Pflicht-KPIs: Liefertreue, Ø Verzögerung, Temperaturausreißer-Quote, Ø Bestellwert, Gesamtumsatz. Direkte Datenquelle für PowerBI KPI-Cards.';

-- -----------------------------------------------------------------------------
-- View: Monatliche Umsatz-Zeitreihe (Absatzprognose-Basis)
-- Grain: 1 Zeile pro Produkt und Monat
-- Verwendung: Python Absatzprognose (ARIMA/Prophet), PowerBI Zeitreihen-Liniendiagramm
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW dwh.v_monthly_revenue AS
SELECT
    d.year,
    d.month,
    d.month_name,
    p.product_code,
    p.product_name,
    SUM(f.quantity)      AS total_quantity,
    SUM(f.total_value)   AS total_revenue_eur,
    COUNT(*)             AS num_shipments
FROM  dwh.fact_fulfillment f
JOIN  dwh.dim_date         d ON d.date_sk    = f.order_date_sk
JOIN  dwh.dim_product      p ON p.product_sk = f.product_sk
GROUP BY d.year, d.month, d.month_name, p.product_code, p.product_name
ORDER BY d.year, d.month, p.product_code;

COMMENT ON VIEW dwh.v_monthly_revenue IS
    'Monatliche Umsatz- und Mengenzeitreihe pro Produkt. Basis für Absatzprognose (ARIMA/Prophet) und PowerBI Zeitreihen-Visual.';

-- =============================================================================
-- PRÜFQUERIES – Nachweis der korrekten Befüllung
-- Nach ETL Phase 2 ausführen; erwartete Werte in Klammern (Stand: Testlauf 2026-05-14)
-- =============================================================================
-- SELECT COUNT(*) FROM dwh.dim_customer;           -- erwartet: 10
-- SELECT COUNT(*) FROM dwh.dim_supplier;           -- erwartet: 10
-- SELECT COUNT(*) FROM dwh.dim_product;            -- erwartet: 10
-- SELECT COUNT(*) FROM dwh.dim_carrier;            -- erwartet:  5
-- SELECT COUNT(*) FROM dwh.dim_supply_chain_node;  -- erwartet:  7
-- SELECT COUNT(*) FROM dwh.dim_date;               -- erwartet: 1095 (2025-01-01 bis 2027-12-31)
-- SELECT COUNT(*) FROM dwh.dim_delivery_status;    -- erwartet:  4
-- SELECT COUNT(*) FROM dwh.fact_fulfillment;       -- erwartet: 10 (1 Endlieferung pro Order/Batch)
-- SELECT * FROM dwh.v_kpi_summary;                 -- 1 Zeile mit 5 KPI-Werten
-- SELECT * FROM dwh.v_carrier_performance;         -- 5 Zeilen (1 pro Carrier)

DO $$
BEGIN
    RAISE NOTICE 'DWH-Schema erstellt: 7 Dimensionstabellen + 1 Faktentabelle + 3 analytische Views. dim_date: 1095 Zeilen (2025–2027). on_time_flag ergänzt.';
END $$;
