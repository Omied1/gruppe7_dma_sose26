-- =============================================================================
-- 04_create_tms_tables.sql
-- TMS-Schema: Transport Management System der Banana Supply Chain
--
-- Tabellen:
--   tms.carriers                      - Transportdienstleister (aus: CarrierCreated)
--   tms.transport_product_references  - TMS-Produktreferenzen (aus: TransportProductReferenceCreated)
--   tms.shipments                     - Transportvorgänge (aus: TransportStarted)
--   tms.shipment_positions            - GPS-Positionen (aus: ShipmentPositionUpdated)
--   tms.transport_completions         - Transportabschlüsse (aus: TransportCompleted)
--   tms.deliveries                    - Lieferabschlüsse (aus: DeliveryCompleted)
--
-- Das TMS verantwortet alle physischen Transporte zwischen den Supply-Chain-Knoten.
-- Die TMS-Produktreferenz (ban-101) ist eine systemspezifische Darstellung des ERP-Codes (BAN-101).
--
-- Voraussetzung: 01_create_schemas.sql muss vorher ausgeführt worden sein.
-- Ausführung:    psql -h localhost -U user -d logistics -f 04_create_tms_tables.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Carrier-Stammdaten
-- Quelle: CarrierCreated-Events (shared/tms/)
-- Carrier sind Transportdienstleister: DHL, Maersk, MSC, DB Schenker, Hapag Lloyd
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tms.carriers (
    carrier_id      SERIAL          PRIMARY KEY,
    carrier_code    VARCHAR(20)     NOT NULL UNIQUE, -- Business Key, z.B. "CAR-101"
    carrier_name    VARCHAR(100)    NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event    VARCHAR(50)     NOT NULL DEFAULT 'CarrierCreated'
);

COMMENT ON TABLE  tms.carriers IS 'Transportdienstleister-Stammdaten. carrier_code ist TMS-interner Business Key (CAR-101 bis CAR-105).';
COMMENT ON COLUMN tms.carriers.carrier_code IS 'TMS-Format: CAR-NNN. DHL=CAR-101, Maersk=CAR-102, MSC=CAR-103, DB Schenker=CAR-104, Hapag Lloyd=CAR-105.';

-- -----------------------------------------------------------------------------
-- TMS-Produktreferenzen
-- Quelle: TransportProductReferenceCreated-Events (shared/tms/)
-- TMS verwendet Kleinbuchstaben: ban-101 statt BAN-101
-- erp_product_code ist die Cross-Reference zum ERP
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tms.transport_product_references (
    ref_id                          SERIAL          PRIMARY KEY,
    erp_product_code                VARCHAR(20)     NOT NULL UNIQUE, -- Cross-Ref: "BAN-101"
    transport_product_reference     VARCHAR(20)     NOT NULL UNIQUE, -- TMS-Format: "ban-101"
    created_at                      TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event                    VARCHAR(50)     NOT NULL DEFAULT 'TransportProductReferenceCreated'
);

COMMENT ON TABLE  tms.transport_product_references IS 'TMS-spezifische Produktreferenzen. Kleinbuchstaben-Format: ban-101. Für Harmonisierung: JOIN via mdm.source_mappings.';
COMMENT ON COLUMN tms.transport_product_references.erp_product_code            IS 'ERP-Referenz: BAN-101.';
COMMENT ON COLUMN tms.transport_product_references.transport_product_reference IS 'TMS-Format: ban-101 (vollständig klein, Bindestriche beibehalten).';

-- -----------------------------------------------------------------------------
-- Shipments (Transportvorgänge)
-- Quelle: TransportStarted-Events (shared/tms/)
-- Jedes Shipment verbindet genau einen Quell-Knoten mit einem Ziel-Knoten
-- Transport-Modi: TRUCK oder SEA_FREIGHT
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tms.shipments (
    shipment_id                 SERIAL          PRIMARY KEY,
    shipment_identifier         VARCHAR(60)     NOT NULL UNIQUE, -- z.B. "SHIP-<uuid>"
    source_node                 VARCHAR(50)     NOT NULL,        -- z.B. "AFRICA_COLD_STORAGE"
    target_node                 VARCHAR(50)     NOT NULL,        -- z.B. "EUROPE_COLD_STORAGE"
    transport_mode              VARCHAR(20)     NOT NULL CHECK (transport_mode IN ('TRUCK', 'SEA_FREIGHT')),
    cargo_product_reference     VARCHAR(30)     NOT NULL,        -- TMS-Format: "ban-108"
    carrier_id                  INT             REFERENCES tms.carriers(carrier_id),
    estimated_arrival           TIMESTAMP,
    started_at                  TIMESTAMP       NOT NULL,
    created_at                  TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event                VARCHAR(50)     NOT NULL DEFAULT 'TransportStarted'
);

COMMENT ON TABLE  tms.shipments IS 'Transportvorgänge zwischen Supply-Chain-Knoten. Ein Batch erzeugt je nach Transportmodus 6 Shipments (6 Knotenpaare im Flow).';
COMMENT ON COLUMN tms.shipments.shipment_identifier     IS 'Primärer Tracking-Schlüssel: SHIP-<uuid>. Verbindet alle TMS-Events desselben Transports.';
COMMENT ON COLUMN tms.shipments.transport_mode          IS 'TRUCK: Landtransport. SEA_FREIGHT: Seefracht (nur Afrika→Europa-Strecke).';
COMMENT ON COLUMN tms.shipments.cargo_product_reference IS 'TMS-Format des Produktcodes (Kleinbuchstaben). Für ERP-Zuordnung: JOIN via mdm.source_mappings.';

-- -----------------------------------------------------------------------------
-- GPS-Positionen (Archivtabelle)
-- Quelle: ShipmentPositionUpdated-Events (shared/tms/)
-- Primärsystem: Redis (aktueller Zustand). Diese Tabelle ist das persistente Archiv.
-- Pro Shipment werden 1-3 GPS-Updates generiert.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tms.shipment_positions (
    position_id             SERIAL          PRIMARY KEY,
    shipment_id             INT             NOT NULL REFERENCES tms.shipments(shipment_id),
    latitude                NUMERIC(9,6)    NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude               NUMERIC(9,6)    NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    container_temperature   NUMERIC(5,2),               -- Kühlkettenüberwachung: Soll 10-15°C
    speed_kmh               NUMERIC(6,2)    CHECK (speed_kmh >= 0),
    recorded_at             TIMESTAMP       NOT NULL,
    created_at              TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event            VARCHAR(50)     NOT NULL DEFAULT 'ShipmentPositionUpdated',
    CONSTRAINT uq_tms_position_per_time UNIQUE (shipment_id, recorded_at)
);

COMMENT ON TABLE  tms.shipment_positions IS 'GPS-Positionsarchiv. Primärsystem für aktuelle Position ist Redis. Diese Tabelle speichert den historischen Positionsverlauf.';
COMMENT ON COLUMN tms.shipment_positions.container_temperature IS 'Containertemperatur beim GPS-Update. Kühlkette: 10-15°C. Abweichungen = Qualitätsproblem.';
COMMENT ON COLUMN tms.shipment_positions.latitude              IS 'WGS84-Breitengrad: -90 bis 90. CHECK-Constraint verhindert ungültige Werte.';

-- -----------------------------------------------------------------------------
-- Transportabschlüsse
-- Quelle: TransportCompleted-Events (shared/tms/)
-- Schließt einen Transportvorgang ab. delay_minutes ist KPI für Lieferperformance.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tms.transport_completions (
    completion_id           SERIAL          PRIMARY KEY,
    shipment_id             INT             NOT NULL REFERENCES tms.shipments(shipment_id),
    arrival_node            VARCHAR(50)     NOT NULL,
    delay_minutes           INT             NOT NULL DEFAULT 0 CHECK (delay_minutes >= 0),
    completed_at            TIMESTAMP       NOT NULL,
    created_at              TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event            VARCHAR(50)     NOT NULL DEFAULT 'TransportCompleted',
    CONSTRAINT uq_tms_completion_per_shipment UNIQUE (shipment_id)
);

COMMENT ON TABLE  tms.transport_completions IS 'Abschlüsse von Transportvorgängen. delay_minutes ist zentrale KPI (0-180 Min laut Datengenerator). Jedes Shipment hat genau einen Abschluss.';
COMMENT ON COLUMN tms.transport_completions.delay_minutes IS 'Tatsächliche Verzögerung in Minuten. 0 = pünktlich. KPI: durchschnittliche Verzögerung pro Route/Carrier.';

-- -----------------------------------------------------------------------------
-- Lieferabschlüsse
-- Quelle: DeliveryCompleted-Events (shared/tms/)
-- Finales Ereignis der Supply Chain. Nur für Transporte zum RETAIL_STORE.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tms.deliveries (
    delivery_id                 SERIAL          PRIMARY KEY,
    shipment_id                 INT             NOT NULL REFERENCES tms.shipments(shipment_id),
    supply_chain_node           VARCHAR(50)     NOT NULL DEFAULT 'RETAIL_STORE',
    delivery_status             VARCHAR(20)     NOT NULL CHECK (delivery_status IN ('SUCCESSFUL', 'DELAYED', 'FAILED')),
    received_by                 VARCHAR(20),    -- Mitarbeiter-ID, z.B. "EMP-7"
    cargo_product_reference     VARCHAR(30),    -- TMS-Format: "ban-108"
    delivered_at                TIMESTAMP       NOT NULL,
    created_at                  TIMESTAMP       NOT NULL DEFAULT NOW(),
    source_event                VARCHAR(50)     NOT NULL DEFAULT 'DeliveryCompleted',
    CONSTRAINT uq_tms_delivery_per_shipment UNIQUE (shipment_id)
);

COMMENT ON TABLE  tms.deliveries IS 'Lieferabschlüsse am Retail Store. delivery_status SUCCESSFUL/DELAYED ist Haupt-KPI für Fulfillment-Qualität.';
COMMENT ON COLUMN tms.deliveries.delivery_status IS 'SUCCESSFUL: Pünktlich. DELAYED: Mit Verspätung zugestellt. FAILED: Nicht zugestellt (Ausnahmefall).';
COMMENT ON COLUMN tms.deliveries.received_by     IS 'Mitarbeiter-ID des Empfängers am Retail Store (EMP-NNN).';

-- -----------------------------------------------------------------------------
-- Indizes für Performance
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_tms_shipments_identifier     ON tms.shipments(shipment_identifier);
CREATE INDEX IF NOT EXISTS idx_tms_shipments_carrier        ON tms.shipments(carrier_id);
CREATE INDEX IF NOT EXISTS idx_tms_shipments_started        ON tms.shipments(started_at);
CREATE INDEX IF NOT EXISTS idx_tms_positions_shipment       ON tms.shipment_positions(shipment_id);
CREATE INDEX IF NOT EXISTS idx_tms_positions_recorded       ON tms.shipment_positions(recorded_at);
CREATE INDEX IF NOT EXISTS idx_tms_completions_shipment     ON tms.transport_completions(shipment_id);
CREATE INDEX IF NOT EXISTS idx_tms_deliveries_shipment      ON tms.deliveries(shipment_id);
CREATE INDEX IF NOT EXISTS idx_tms_deliveries_status        ON tms.deliveries(delivery_status);

DO $$
BEGIN
    RAISE NOTICE 'TMS-Tabellen erstellt: carriers, transport_product_references, shipments, shipment_positions, transport_completions, deliveries';
END $$;
