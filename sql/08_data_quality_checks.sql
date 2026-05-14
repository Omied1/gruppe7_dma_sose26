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
-- Hinweis: Das ETL normalisiert WMS-SKUs (BAN_101 → BAN-101) beim Laden, damit
-- alle Schlüssel in der Datenbank im ERP-Format vorliegen. Der Lookup gegen
-- mdm.source_mappings erfolgt daher über normalized_key (kanonisches Format).
SELECT
    'KONSISTENZ'         AS dimension,
    'wms.warehouse_skus' AS tabelle,
    'SKU ohne MDM-Mapping' AS regel,
    w.sku,
    w.erp_product_code
FROM wms.warehouse_skus w
WHERE NOT EXISTS (
    SELECT 1 FROM mdm.source_mappings sm
    WHERE sm.source_system  = 'WMS'
      AND sm.normalized_key = LOWER(REPLACE(w.sku, '_', '-'))
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

-- =============================================================================
-- 5. AKTUALITÄT (Timeliness)
-- Zeitliche Plausibilität: Events müssen in logischer Reihenfolge liegen
-- =============================================================================

-- 5.1 TMS: Transportabschluss vor Transportstart
SELECT
    'AKTUALITÄT'    AS dimension,
    'tms'           AS tabelle,
    'TransportCompleted vor TransportStarted' AS regel,
    COUNT(*)        AS verstösse
FROM tms.transport_completions tc
JOIN tms.shipments             s  ON s.shipment_id = tc.shipment_id
WHERE tc.completed_at < s.started_at;

-- 5.2 ERP: Batch-Ernte vor Bestellungsdatum
SELECT
    'AKTUALITÄT'   AS dimension,
    'erp'          AS tabelle,
    'BatchHarvested vor OrderCreated' AS regel,
    COUNT(*)       AS verstösse
FROM erp.batches  b
JOIN erp.orders   o ON o.order_id = b.order_id
WHERE b.harvested_at < o.order_timestamp;

-- 5.3 Veraltete aktive Orders (älter als 90 Tage ohne Delivery)
SELECT
    'AKTUALITÄT'   AS dimension,
    'erp.orders + tms.deliveries' AS tabelle,
    'Order > 90 Tage ohne Delivery' AS regel,
    COUNT(*)       AS verstösse
FROM erp.orders o
WHERE o.order_timestamp < NOW() - INTERVAL '90 days'
AND NOT EXISTS (
    SELECT 1 FROM erp.batches b
    JOIN   tms.shipments    s  ON s.cargo_product_reference = b.tms_product_reference
    JOIN   tms.deliveries   d  ON d.shipment_id = s.shipment_id
    WHERE  b.order_id = o.order_id
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

-- 6.3 TMS Transport_completions: Shipment ohne Carrier
SELECT
    'REFERENZIELLE INTEGRITÄT' AS dimension,
    'tms.shipments'            AS tabelle,
    'Shipment ohne Carrier (carrier_id NULL)' AS regel,
    COUNT(*)                   AS verstösse
FROM tms.shipments
WHERE carrier_id IS NULL;

-- =============================================================================
-- ZUSAMMENFASSUNG: Qualitäts-Score pro Dimension
-- Gibt eine kompakte Übersicht aller Verstösse (0 = perfekt)
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE '=== DQ-Check abgeschlossen. Alle Ergebnisse mit verstösse > 0 erfordern Nacharbeit. ===';
END $$;
