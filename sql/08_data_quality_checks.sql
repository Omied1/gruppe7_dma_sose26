-- =============================================================================
-- 08_data_quality_checks.sql
-- Datenqualitätsprüfungen für die Banana Supply Chain
--
-- Qualitätsdimensionen:
--   1. Vollständigkeit (Completeness)   - Pflichtfelder vorhanden?
--   2. Eindeutigkeit (Uniqueness)       - Keine Duplikate?
--   3. Konsistenz (Consistency)         - Systemübergreifende Übereinstimmung?
--   4. Plausibilität (Validity)         - Werte im gültigen Bereich?
--   5. Aktualität (Timeliness)          - Daten aktuell?
--   6. Ref. Integrität (Referential)    - FKs auflösbar?
--
-- Voraussetzung: Alle operativen Schemas müssen befüllt sein (02-04).
-- Ausführung: psql -h localhost -U user -d logistics -f 08_data_quality_checks.sql
-- =============================================================================

-- =============================================================================
-- 1. VOLLSTÄNDIGKEIT (Completeness)
-- Pflichtfelder prüfen: NULL-Werte in NOT-NULL-Spalten
-- =============================================================================

-- 1.1 ERP: Produkte ohne Lieferantenreferenz
SELECT
    'VOLLSTÄNDIGKEIT' AS dimension,
    'erp.products'    AS tabelle,
    'supplier_id NULL' AS regel,
    COUNT(*)          AS verstösse
FROM erp.products
WHERE supplier_id IS NULL;

-- 1.2 ERP: Bestellpositionen ohne Menge oder Preis
SELECT
    'VOLLSTÄNDIGKEIT'   AS dimension,
    'erp.order_items'   AS tabelle,
    'quantity oder unit_price NULL' AS regel,
    COUNT(*)            AS verstösse
FROM erp.order_items
WHERE quantity IS NULL OR unit_price IS NULL;

-- 1.3 WMS: Knotenverarbeitungen ohne Temperatur
-- Temperatur ist qualitätskritisch für die Kühlkette, aber nullable
SELECT
    'VOLLSTÄNDIGKEIT'       AS dimension,
    'wms.node_processings'  AS tabelle,
    'temperature NULL (Kühlkette-Lücke)' AS regel,
    COUNT(*)                AS verstösse
FROM wms.node_processings
WHERE temperature IS NULL;

-- 1.4 TMS: Lieferungen ohne received_by (bei SUCCESSFUL)
SELECT
    'VOLLSTÄNDIGKEIT'  AS dimension,
    'tms.deliveries'   AS tabelle,
    'received_by NULL bei SUCCESSFUL' AS regel,
    COUNT(*)           AS verstösse
FROM tms.deliveries
WHERE delivery_status = 'SUCCESSFUL'
AND   received_by IS NULL;

-- 1.5 ERP: Bestellungen ohne Bestellpositionen
-- Fachlich: Jede Order muss mindestens eine Position haben, sonst kein Rechnungswert berechenbar
SELECT
    'VOLLSTÄNDIGKEIT'  AS dimension,
    'erp.orders'       AS tabelle,
    'Order ohne Bestellpositionen' AS regel,
    COUNT(*)           AS verstösse
FROM erp.orders o
WHERE NOT EXISTS (
    SELECT 1 FROM erp.order_items oi WHERE oi.order_id = o.order_id
);

-- =============================================================================
-- 2. EINDEUTIGKEIT (Uniqueness)
-- Duplikate in Business Keys erkennen
-- =============================================================================

-- 2.1 ERP: Doppelte supplier_codes
SELECT
    'EINDEUTIGKEIT'  AS dimension,
    'erp.suppliers'  AS tabelle,
    'supplier_code Duplikat' AS regel,
    supplier_code,
    COUNT(*) AS anzahl
FROM erp.suppliers
GROUP BY supplier_code
HAVING COUNT(*) > 1;

-- 2.2 ERP: Doppelte order_references
SELECT
    'EINDEUTIGKEIT' AS dimension,
    'erp.orders'    AS tabelle,
    'order_reference Duplikat' AS regel,
    order_reference,
    COUNT(*) AS anzahl
FROM erp.orders
GROUP BY order_reference
HAVING COUNT(*) > 1;

-- 2.3 ERP: Doppelte batch_identifiers
SELECT
    'EINDEUTIGKEIT' AS dimension,
    'erp.batches'   AS tabelle,
    'batch_identifier Duplikat' AS regel,
    batch_identifier,
    COUNT(*) AS anzahl
FROM erp.batches
GROUP BY batch_identifier
HAVING COUNT(*) > 1;

-- 2.4 TMS: Doppelte shipment_identifiers
SELECT
    'EINDEUTIGKEIT' AS dimension,
    'tms.shipments' AS tabelle,
    'shipment_identifier Duplikat' AS regel,
    shipment_identifier,
    COUNT(*) AS anzahl
FROM tms.shipments
GROUP BY shipment_identifier
HAVING COUNT(*) > 1;

-- =============================================================================
-- 3. KONSISTENZ (Consistency)
-- Systemübergreifende Schlüsselkonsistenz (MDM-Prüfung)
-- =============================================================================

-- 3.1 WMS-SKUs ohne MDM-Mapping
-- Prüfung direkt über source_key = w.sku (WMS-Format BAN_101), da mdm.source_mappings
-- source_key im Originalformat (BAN_101) speichert. Einfacher und direkter als REPLACE-Transformation.
SELECT
    'KONSISTENZ'         AS dimension,
    'wms.warehouse_skus' AS tabelle,
    'SKU ohne MDM-Mapping' AS regel,
    w.sku,
    w.erp_product_code
FROM wms.warehouse_skus w
WHERE NOT EXISTS (
    SELECT 1 FROM mdm.source_mappings sm
    WHERE sm.source_system = 'WMS'
      AND sm.source_key    = w.sku
);

-- 3.2 TMS-Produktreferenzen ohne MDM-Mapping
SELECT
    'KONSISTENZ'                    AS dimension,
    'tms.transport_product_references' AS tabelle,
    'TMS-Referenz ohne MDM-Mapping' AS regel,
    t.transport_product_reference,
    t.erp_product_code
FROM tms.transport_product_references t
WHERE NOT EXISTS (
    SELECT 1 FROM mdm.source_mappings sm
    WHERE sm.source_system  = 'TMS'
      AND sm.normalized_key = LOWER(t.transport_product_reference)
);

-- 3.3 Batches mit inkonsistenten WMS-SKUs
-- wms_sku im Batch muss zum product_code passen (via MDM)
SELECT
    'KONSISTENZ'   AS dimension,
    'erp.batches'  AS tabelle,
    'wms_sku passt nicht zu product_code' AS regel,
    b.batch_identifier,
    b.product_id,
    b.wms_sku,
    p.product_code
FROM erp.batches b
JOIN erp.products p ON p.product_id = b.product_id
WHERE b.wms_sku IS NOT NULL
AND   b.wms_sku != REPLACE(p.product_code, '-', '_'); -- Erwartetes WMS-Format

-- 3.4 TMS: Erfolgreiche Lieferung ohne zugehörigen Transportabschluss
-- Fachlich: Jede Delivery mit Status SUCCESSFUL muss ein TransportCompleted-Event haben;
-- fehlt es, ist die Delivery-Buchung ohne Nachweis (Konsistenz zwischen DeliveryCompleted und TransportCompleted)
SELECT
    'KONSISTENZ'   AS dimension,
    'tms.deliveries + tms.transport_completions' AS tabelle,
    'SUCCESSFUL-Delivery ohne TransportCompleted-Eintrag' AS regel,
    COUNT(*)       AS verstösse
FROM tms.deliveries d
WHERE d.delivery_status = 'SUCCESSFUL'
AND NOT EXISTS (
    SELECT 1 FROM tms.transport_completions tc
    WHERE tc.shipment_id = d.shipment_id
);

-- =============================================================================
-- 4. PLAUSIBILITÄT (Validity)
-- Wertebereiche und Format-Prüfungen
-- =============================================================================

-- 4.1 ERP: Negative oder Null-Mengen
SELECT
    'PLAUSIBILITÄT'   AS dimension,
    'erp.order_items' AS tabelle,
    'quantity <= 0'   AS regel,
    COUNT(*)          AS verstösse
FROM erp.order_items
WHERE quantity <= 0;

-- 4.2 ERP: Unplausible Preise (außerhalb 1.50 – 5.00 EUR)
SELECT
    'PLAUSIBILITÄT'   AS dimension,
    'erp.order_items' AS tabelle,
    'unit_price außerhalb [1.50, 5.00]' AS regel,
    COUNT(*)          AS verstösse
FROM erp.order_items
WHERE unit_price < 1.50 OR unit_price > 5.00;

-- 4.3 WMS: Temperaturen außerhalb Kühlkette (10-15°C)
SELECT
    'PLAUSIBILITÄT'         AS dimension,
    'wms.node_processings'  AS tabelle,
    'temperature außerhalb [10.0, 15.0]°C (Kühlkettenbruch!)' AS regel,
    COUNT(*)                AS verstösse,
    MIN(temperature)        AS min_temp,
    MAX(temperature)        AS max_temp
FROM wms.node_processings
WHERE temperature IS NOT NULL
AND   (temperature < 10.0 OR temperature > 15.0);

-- 4.4 TMS: Container-Temperaturen außerhalb Kühlkette
SELECT
    'PLAUSIBILITÄT'           AS dimension,
    'tms.shipment_positions'  AS tabelle,
    'container_temperature außerhalb [10.0, 15.0]°C' AS regel,
    COUNT(*)                  AS verstösse
FROM tms.shipment_positions
WHERE container_temperature IS NOT NULL
AND   (container_temperature < 10.0 OR container_temperature > 15.0);

-- 4.5 TMS: GPS-Koordinaten außerhalb Wertebereich
SELECT
    'PLAUSIBILITÄT'          AS dimension,
    'tms.shipment_positions' AS tabelle,
    'latitude/longitude außerhalb Wertebereich' AS regel,
    COUNT(*)                 AS verstösse
FROM tms.shipment_positions
WHERE latitude  NOT BETWEEN -90  AND 90
OR    longitude NOT BETWEEN -180 AND 180;

-- 4.6 TMS: Ungültige delivery_status-Werte
SELECT
    'PLAUSIBILITÄT' AS dimension,
    'tms.deliveries' AS tabelle,
    'delivery_status ungültig' AS regel,
    delivery_status,
    COUNT(*) AS anzahl
FROM tms.deliveries
WHERE delivery_status NOT IN ('SUCCESSFUL', 'DELAYED', 'FAILED')
GROUP BY delivery_status;

-- 4.7 ERP: Ungültige delivery_priority-Werte
SELECT
    'PLAUSIBILITÄT' AS dimension,
    'erp.orders'    AS tabelle,
    'delivery_priority ungültig' AS regel,
    delivery_priority,
    COUNT(*) AS anzahl
FROM erp.orders
WHERE delivery_priority NOT IN ('HIGH', 'NORMAL', 'LOW')
GROUP BY delivery_priority;

-- 4.8 TMS: Unplausible Verzögerungen (> 180 Min = Maximum laut Datengenerator)
SELECT
    'PLAUSIBILITÄT'              AS dimension,
    'tms.transport_completions'  AS tabelle,
    'delay_minutes > 180 (außerhalb erwartetem Bereich)' AS regel,
    COUNT(*)                     AS verstösse
FROM tms.transport_completions
WHERE delay_minutes > 180;

-- 4.9 TMS: Unplausible Geschwindigkeit (> 200 km/h oder negativ)
SELECT
    'PLAUSIBILITÄT'          AS dimension,
    'tms.shipment_positions' AS tabelle,
    'speed_kmh > 200 oder < 0' AS regel,
    COUNT(*)                 AS verstösse
FROM tms.shipment_positions
WHERE speed_kmh IS NOT NULL
AND   (speed_kmh > 200 OR speed_kmh < 0);

-- 4.10 TMS: GPS-Koordinaten außerhalb erwarteter Routenkorridore
-- Der Generator erzeugt syntaktisch gültige WGS84-Koordinaten zufällig weltweit.
-- Dieser Check prüft zusätzlich fachliche Plausibilität gegen grobe Supply-Chain-Korridore:
--   Ghana-Landrouten:       ca. Ghana / Westafrika
--   Seefracht Ghana→Europa: grober Atlantik-/Europa-Korridor
--   Europa-Landrouten:      ca. Niederlande / Deutschland
SELECT
    'PLAUSIBILITÄT'          AS dimension,
    'tms.shipment_positions' AS tabelle,
    'GPS-Koordinaten außerhalb erwarteter Routenkorridore' AS regel,
    COUNT(*)                 AS verstösse
FROM tms.shipment_positions sp
JOIN tms.shipments s
  ON s.shipment_id = sp.shipment_id
WHERE NOT (
    (
        s.source_node IN ('BANANA_PLANTATION', 'COLLECTION_CENTER', 'QUALITY_CONTROL')
        AND s.target_node IN ('COLLECTION_CENTER', 'QUALITY_CONTROL', 'AFRICA_COLD_STORAGE')
        AND sp.latitude  BETWEEN 4.5 AND 7.5
        AND sp.longitude BETWEEN -2.5 AND 1.0
    )
    OR
    (
        s.source_node = 'AFRICA_COLD_STORAGE'
        AND s.target_node = 'EUROPE_COLD_STORAGE'
        AND sp.latitude  BETWEEN 0.0 AND 55.0
        AND sp.longitude BETWEEN -20.0 AND 10.0
    )
    OR
    (
        s.source_node IN ('EUROPE_COLD_STORAGE', 'CENTRAL_WAREHOUSE')
        AND s.target_node IN ('CENTRAL_WAREHOUSE', 'RETAIL_STORE')
        AND sp.latitude  BETWEEN 49.0 AND 54.0
        AND sp.longitude BETWEEN 3.0 AND 15.0
    )
);

-- =============================================================================
-- 5. AKTUALITÄT (Timeliness)
-- Zeitliche Plausibilität: Events müssen in logischer Reihenfolge liegen
-- und event_timestamp muss innerhalb der Projektlaufzeit (2026) liegen
-- =============================================================================

-- 5.0 Stammdaten: event_timestamp ausserhalb der Projektlaufzeit
SELECT
    'AKTUALITÄT'        AS dimension,
    'erp.suppliers'     AS tabelle,
    'event_timestamp ausserhalb 2026' AS regel,
    COUNT(*)            AS verstösse
FROM erp.suppliers
WHERE event_timestamp < '2026-01-01' OR event_timestamp > NOW() + INTERVAL '1 day';

SELECT
    'AKTUALITÄT'        AS dimension,
    'erp.customers'     AS tabelle,
    'event_timestamp ausserhalb 2026' AS regel,
    COUNT(*)            AS verstösse
FROM erp.customers
WHERE event_timestamp < '2026-01-01' OR event_timestamp > NOW() + INTERVAL '1 day';

SELECT
    'AKTUALITÄT'        AS dimension,
    'erp.products'      AS tabelle,
    'event_timestamp ausserhalb 2026' AS regel,
    COUNT(*)            AS verstösse
FROM erp.products
WHERE event_timestamp < '2026-01-01' OR event_timestamp > NOW() + INTERVAL '1 day';

SELECT
    'AKTUALITÄT'        AS dimension,
    'tms.carriers'      AS tabelle,
    'event_timestamp ausserhalb 2026' AS regel,
    COUNT(*)            AS verstösse
FROM tms.carriers
WHERE event_timestamp < '2026-01-01' OR event_timestamp > NOW() + INTERVAL '1 day';

-- 5.1 TMS: Transportabschluss vor Transportstart
SELECT
    'AKTUALITÄT'    AS dimension,
    'tms'           AS tabelle,
    'TransportCompleted vor TransportStarted' AS regel,
    COUNT(*)        AS verstösse
FROM tms.transport_completions tc
JOIN tms.shipments             s  ON s.shipment_id = tc.shipment_id
WHERE tc.completed_at < s.started_at;

-- 5.2 ERP: Batches mit unrealistischem Erntezeitpunkt
-- (Hinweis: direkter order_id-FK entfernt, da BatchHarvested kein order_id enthält.
--  Plausibilitätscheck ersetzt den früheren Reihenfolgecheck.)
SELECT
    'AKTUALITÄT'   AS dimension,
    'erp.batches'  AS tabelle,
    'harvested_at ausserhalb Projektlaufzeit (2026)' AS regel,
    COUNT(*)       AS verstösse
FROM erp.batches
WHERE harvested_at < '2026-01-01'
   OR harvested_at > NOW() + INTERVAL '1 day';

-- 5.3 Veraltete aktive Orders (älter als 90 Tage ohne zugehörige Delivery)
-- Verknüpfung Batch→Order erfolgt über product_code (kein direkter FK mehr)
SELECT
    'AKTUALITÄT'                  AS dimension,
    'erp.orders + tms.deliveries' AS tabelle,
    'Order > 90 Tage ohne Delivery' AS regel,
    COUNT(*)                      AS verstösse
FROM erp.orders o
WHERE o.order_timestamp < NOW() - INTERVAL '90 days'
AND NOT EXISTS (
    SELECT 1
    FROM   erp.order_items  oi
    JOIN   erp.products     p  ON p.product_id  = oi.product_id
    JOIN   erp.batches      b  ON b.product_id  = p.product_id
    JOIN   tms.shipments    s  ON s.cargo_product_reference = b.tms_product_reference
    JOIN   tms.deliveries   d  ON d.shipment_id = s.shipment_id
    WHERE  oi.order_id = o.order_id
);

-- =============================================================================
-- 6. REFERENZIELLE INTEGRITÄT (Referential Integrity)
-- Cross-Schema-Referenzen prüfen (nicht via FK erzwungen)
-- =============================================================================

-- 6.1 WMS NodeProcessings: batch_reference ohne ERP-Batch
SELECT
    'REFERENZIELLE INTEGRITÄT' AS dimension,
    'wms.node_processings'     AS tabelle,
    'batch_reference ohne erp.batches-Eintrag' AS regel,
    COUNT(*)                   AS verstösse
FROM wms.node_processings np
WHERE NOT EXISTS (
    SELECT 1 FROM erp.batches b
    WHERE b.batch_identifier = np.batch_reference
);

-- 6.2 TMS Shipments: cargo_product_reference ohne TMS-Produktreferenz
SELECT
    'REFERENZIELLE INTEGRITÄT' AS dimension,
    'tms.shipments'            AS tabelle,
    'cargo_product_reference ohne tms.transport_product_references' AS regel,
    COUNT(*)                   AS verstösse
FROM tms.shipments s
WHERE NOT EXISTS (
    SELECT 1 FROM tms.transport_product_references r
    WHERE r.transport_product_reference = s.cargo_product_reference
);

-- 6.3 TMS Deliveries: Status-Inkonsistenz mit 60-min-SLA (Datengenerator-Bug)
-- Der Datengenerator würfelt delivery_status und delay_minutes unabhängig voneinander.
-- Das DWH korrigiert den Status anhand des SLA-Schwellenwerts: delay <= 60 → SUCCESSFUL,
-- delay > 60 → DELAYED. Diese Prüfung erfasst Datensätze, bei denen TMS-Rohstatus und
-- der SLA-korrigierte DWH-Status nicht übereinstimmen:
--   Fall A: TMS=SUCCESSFUL, aber delay_minutes > 60 (SLA verletzt → DWH: DELAYED)
--   Fall B: TMS=DELAYED, aber delay_minutes <= 60 (innerhalb SLA → DWH: SUCCESSFUL)
-- Verstösse sind erwartet und dokumentiert; Korrektur erfolgt in etl_dwh.py.
SELECT
    'KONSISTENZ'               AS dimension,
    'tms.deliveries'           AS tabelle,
    'Status-Inkonsistenz mit 60-min-SLA (TMS-Rohstatus vs. SLA-korrigierter Status)' AS regel,
    COUNT(*)                   AS verstösse
FROM tms.deliveries d
JOIN tms.transport_completions tc ON tc.shipment_id = d.shipment_id
WHERE (d.delivery_status = 'SUCCESSFUL' AND tc.delay_minutes > 60)
   OR (d.delivery_status = 'DELAYED'    AND tc.delay_minutes <= 60);

-- 6.4 TMS: Carrier-Transportmodus-Inkonsistenz
-- Prüft ob ein Seefracht-Carrier (Maersk, MSC, Hapag Lloyd = CAR-102/103/105) auf einer
-- TRUCK-Strecke eingesetzt wird oder umgekehrt ein Landcarrier auf SEA_FREIGHT.
-- Ursache: Datengenerator verknüpft Carrier und Transportmodus unabhängig.
-- Verstösse sind ein bekannter Datengenerator-Bug und werden hier dokumentiert.
SELECT
    'KONSISTENZ'      AS dimension,
    'tms.shipments'   AS tabelle,
    'Seefracht-Carrier auf TRUCK-Route oder Landcarrier auf SEA_FREIGHT' AS regel,
    COUNT(*)          AS verstösse
FROM tms.shipments s
JOIN tms.carriers  c ON c.carrier_id = s.carrier_id
WHERE
    -- Reedereien (Maersk, MSC, Hapag Lloyd) dürfen nicht auf TRUCK-Strecken fahren
    (c.carrier_code IN ('CAR-102', 'CAR-103', 'CAR-105') AND s.transport_mode = 'TRUCK')
    OR
    -- Landcarrier (DHL, DB Schenker) dürfen nicht auf SEA_FREIGHT-Strecken fahren
    (c.carrier_code IN ('CAR-101', 'CAR-104') AND s.transport_mode = 'SEA_FREIGHT');

-- =============================================================================
-- ZUSAMMENFASSUNG: Qualitäts-Score pro Dimension
-- Gibt eine kompakte Übersicht aller Verstösse (0 = perfekt)
-- Gesamt: 34 Einzel-Checks über 6 Dimensionen (Regel 5.0 = 4 Tabellen × 1 Query)
-- Konsolidierte Übersicht mit PASS/FAIL: sql/08b_dq_audit.sql
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE '=== DQ-Check abgeschlossen (34 Einzel-Checks). Alle Ergebnisse mit verstösse > 0 erfordern Nacharbeit. ===';
END $$;

-- Nachweis: Datenbasis für DQ-Checks
SELECT 'erp.suppliers'              AS tabelle, COUNT(*) AS datensaetze FROM erp.suppliers
UNION ALL SELECT 'erp.customers',              COUNT(*) FROM erp.customers
UNION ALL SELECT 'erp.products',               COUNT(*) FROM erp.products
UNION ALL SELECT 'erp.orders',                 COUNT(*) FROM erp.orders
UNION ALL SELECT 'erp.order_items',            COUNT(*) FROM erp.order_items
UNION ALL SELECT 'erp.batches',                COUNT(*) FROM erp.batches
UNION ALL SELECT 'wms.warehouse_skus',         COUNT(*) FROM wms.warehouse_skus
UNION ALL SELECT 'wms.node_processings',       COUNT(*) FROM wms.node_processings
UNION ALL SELECT 'tms.carriers',               COUNT(*) FROM tms.carriers
UNION ALL SELECT 'tms.shipments',              COUNT(*) FROM tms.shipments
UNION ALL SELECT 'tms.shipment_positions',     COUNT(*) FROM tms.shipment_positions
UNION ALL SELECT 'tms.transport_completions',  COUNT(*) FROM tms.transport_completions
UNION ALL SELECT 'tms.deliveries',             COUNT(*) FROM tms.deliveries;
