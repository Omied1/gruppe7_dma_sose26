-- =============================================================================
-- 08b_dq_audit.sql
-- Konsolidierte Datenqualitäts-Auditierung
--
-- Liefert EINE Ergebnistabelle mit allen 22 DQ-Checks aus 08_data_quality_checks.sql
-- für eine schnelle Übersicht. Sortiert nach Dimension und Verstössen.
--
-- Spaltenformat:
--   dimension  - eine der 6 DQ-Dimensionen
--   nummer     - Regel-Nummer (1.1, 4.3 etc.)
--   tabelle    - betroffene Tabelle
--   regel      - Validierungsregel
--   verstoesse - Anzahl der Datensätze, die die Regel verletzen
--   status     - PASS (0 Verstösse) oder FAIL (>0)
--
-- Ausführung: docker exec -i postgres psql -U user -d logistics < 08b_dq_audit.sql
-- =============================================================================

WITH dq AS (
    -- ── 1. VOLLSTÄNDIGKEIT ────────────────────────────────────────────────────
    SELECT 1 AS pos, 'VOLLSTÄNDIGKEIT' AS dimension, '1.1' AS nummer,
           'erp.products' AS tabelle, 'supplier_id NULL' AS regel,
           (SELECT COUNT(*) FROM erp.products WHERE supplier_id IS NULL) AS verstoesse
    UNION ALL SELECT 2, 'VOLLSTÄNDIGKEIT', '1.2',
           'erp.order_items', 'quantity oder unit_price NULL',
           (SELECT COUNT(*) FROM erp.order_items WHERE quantity IS NULL OR unit_price IS NULL)
    UNION ALL SELECT 3, 'VOLLSTÄNDIGKEIT', '1.3',
           'wms.node_processings', 'temperature NULL (Kühlkette-Lücke)',
           (SELECT COUNT(*) FROM wms.node_processings WHERE temperature IS NULL)
    UNION ALL SELECT 4, 'VOLLSTÄNDIGKEIT', '1.4',
           'tms.deliveries', 'received_by NULL bei SUCCESSFUL',
           (SELECT COUNT(*) FROM tms.deliveries
            WHERE delivery_status = 'SUCCESSFUL' AND received_by IS NULL)

    -- ── 2. EINDEUTIGKEIT ──────────────────────────────────────────────────────
    UNION ALL SELECT 5, 'EINDEUTIGKEIT', '2.1',
           'erp.suppliers', 'supplier_code Duplikat',
           (SELECT COALESCE(SUM(anzahl), 0) FROM (
                SELECT COUNT(*) - 1 AS anzahl FROM erp.suppliers
                GROUP BY supplier_code HAVING COUNT(*) > 1
            ) x)
    UNION ALL SELECT 6, 'EINDEUTIGKEIT', '2.2',
           'erp.orders', 'order_reference Duplikat',
           (SELECT COALESCE(SUM(anzahl), 0) FROM (
                SELECT COUNT(*) - 1 AS anzahl FROM erp.orders
                GROUP BY order_reference HAVING COUNT(*) > 1
            ) x)
    UNION ALL SELECT 7, 'EINDEUTIGKEIT', '2.3',
           'erp.batches', 'batch_identifier Duplikat',
           (SELECT COALESCE(SUM(anzahl), 0) FROM (
                SELECT COUNT(*) - 1 AS anzahl FROM erp.batches
                GROUP BY batch_identifier HAVING COUNT(*) > 1
            ) x)
    UNION ALL SELECT 8, 'EINDEUTIGKEIT', '2.4',
           'tms.shipments', 'shipment_identifier Duplikat',
           (SELECT COALESCE(SUM(anzahl), 0) FROM (
                SELECT COUNT(*) - 1 AS anzahl FROM tms.shipments
                GROUP BY shipment_identifier HAVING COUNT(*) > 1
            ) x)

    -- ── 3. KONSISTENZ ─────────────────────────────────────────────────────────
    -- 3.1 / 3.2: SKUs werden im ETL durch normalize_key() bereits auf ERP-Format
    -- gebracht. Die MDM-Auflösung erfolgt daher über normalized_key, nicht über
    -- source_key (das speichert das System-Originalformat).
    UNION ALL SELECT 9, 'KONSISTENZ', '3.1',
           'wms.warehouse_skus', 'SKU ohne MDM-Mapping (über normalized_key)',
           (SELECT COUNT(*) FROM wms.warehouse_skus w
            WHERE NOT EXISTS (SELECT 1 FROM mdm.source_mappings sm
                              WHERE sm.source_system  = 'WMS'
                                AND sm.normalized_key = LOWER(REPLACE(w.sku, '_', '-'))))
    UNION ALL SELECT 10, 'KONSISTENZ', '3.2',
           'tms.transport_product_references', 'TMS-Referenz ohne MDM-Mapping (über normalized_key)',
           (SELECT COUNT(*) FROM tms.transport_product_references t
            WHERE NOT EXISTS (SELECT 1 FROM mdm.source_mappings sm
                              WHERE sm.source_system  = 'TMS'
                                AND sm.normalized_key = LOWER(t.transport_product_reference)))
    UNION ALL SELECT 11, 'KONSISTENZ', '3.3',
           'erp.batches', 'wms_sku passt nicht zu product_code',
           (SELECT COUNT(*) FROM erp.batches b
            JOIN erp.products p ON p.product_id = b.product_id
            WHERE b.wms_sku IS NOT NULL
              AND b.wms_sku != REPLACE(p.product_code, '-', '_'))

    -- ── 4. PLAUSIBILITÄT ──────────────────────────────────────────────────────
    UNION ALL SELECT 12, 'PLAUSIBILITÄT', '4.1',
           'erp.order_items', 'quantity <= 0',
           (SELECT COUNT(*) FROM erp.order_items WHERE quantity <= 0)
    UNION ALL SELECT 13, 'PLAUSIBILITÄT', '4.2',
           'erp.order_items', 'unit_price außerhalb [1.50, 5.00]',
           (SELECT COUNT(*) FROM erp.order_items WHERE unit_price < 1.50 OR unit_price > 5.00)
    UNION ALL SELECT 14, 'PLAUSIBILITÄT', '4.3',
           'wms.node_processings', 'temperature außerhalb [10, 15]°C (Kühlkettenbruch)',
           (SELECT COUNT(*) FROM wms.node_processings
            WHERE temperature IS NOT NULL AND (temperature < 10.0 OR temperature > 15.0))
    UNION ALL SELECT 15, 'PLAUSIBILITÄT', '4.4',
           'tms.shipment_positions', 'container_temperature außerhalb [10, 15]°C',
           (SELECT COUNT(*) FROM tms.shipment_positions
            WHERE container_temperature IS NOT NULL
              AND (container_temperature < 10.0 OR container_temperature > 15.0))
    UNION ALL SELECT 16, 'PLAUSIBILITÄT', '4.5',
           'tms.shipment_positions', 'latitude/longitude außerhalb Wertebereich',
           (SELECT COUNT(*) FROM tms.shipment_positions
            WHERE latitude NOT BETWEEN -90 AND 90
               OR longitude NOT BETWEEN -180 AND 180)
    UNION ALL SELECT 17, 'PLAUSIBILITÄT', '4.6',
           'tms.deliveries', 'delivery_status ungültig',
           (SELECT COUNT(*) FROM tms.deliveries
            WHERE delivery_status NOT IN ('SUCCESSFUL','DELAYED','FAILED'))
    UNION ALL SELECT 18, 'PLAUSIBILITÄT', '4.7',
           'erp.orders', 'delivery_priority ungültig',
           (SELECT COUNT(*) FROM erp.orders
            WHERE delivery_priority NOT IN ('HIGH','NORMAL','LOW'))
    UNION ALL SELECT 19, 'PLAUSIBILITÄT', '4.8',
           'tms.transport_completions', 'delay_minutes > 180',
           (SELECT COUNT(*) FROM tms.transport_completions WHERE delay_minutes > 180)
    UNION ALL SELECT 20, 'PLAUSIBILITÄT', '4.9',
           'tms.shipment_positions', 'speed_kmh > 200 oder < 0',
           (SELECT COUNT(*) FROM tms.shipment_positions
            WHERE speed_kmh IS NOT NULL AND (speed_kmh > 200 OR speed_kmh < 0))

    -- ── 5. AKTUALITÄT ─────────────────────────────────────────────────────────
    UNION ALL SELECT 21, 'AKTUALITÄT', '5.1',
           'tms', 'TransportCompleted vor TransportStarted',
           (SELECT COUNT(*) FROM tms.transport_completions tc
            JOIN tms.shipments s ON s.shipment_id = tc.shipment_id
            WHERE tc.completed_at < s.started_at)
    UNION ALL SELECT 22, 'AKTUALITÄT', '5.2',
           'erp', 'BatchHarvested vor OrderCreated',
           (SELECT COUNT(*) FROM erp.batches b
            JOIN erp.orders o ON o.order_id = b.order_id
            WHERE b.harvested_at < o.order_timestamp)
    UNION ALL SELECT 23, 'AKTUALITÄT', '5.3',
           'erp.orders', 'Order > 90 Tage ohne Delivery',
           (SELECT COUNT(*) FROM erp.orders o
            WHERE o.order_timestamp < NOW() - INTERVAL '90 days'
              AND NOT EXISTS (
                  SELECT 1 FROM erp.batches b
                  JOIN tms.shipments  sp ON sp.cargo_product_reference = b.tms_product_reference
                  JOIN tms.deliveries d  ON d.shipment_id = sp.shipment_id
                  WHERE b.order_id = o.order_id))

    -- ── 6. REFERENZIELLE INTEGRITÄT ───────────────────────────────────────────
    UNION ALL SELECT 24, 'REF. INTEGRITÄT', '6.1',
           'wms.node_processings', 'batch_reference ohne erp.batches',
           (SELECT COUNT(*) FROM wms.node_processings np
            WHERE NOT EXISTS (SELECT 1 FROM erp.batches b
                              WHERE b.batch_identifier = np.batch_reference))
    UNION ALL SELECT 25, 'REF. INTEGRITÄT', '6.2',
           'tms.shipments', 'cargo_product_reference ohne tms.transport_product_references',
           (SELECT COUNT(*) FROM tms.shipments s
            WHERE NOT EXISTS (SELECT 1 FROM tms.transport_product_references r
                              WHERE r.transport_product_reference = s.cargo_product_reference))
    UNION ALL SELECT 26, 'REF. INTEGRITÄT', '6.3',
           'tms.shipments', 'Shipment ohne Carrier (carrier_id NULL)',
           (SELECT COUNT(*) FROM tms.shipments WHERE carrier_id IS NULL)
)
SELECT
    dimension,
    nummer,
    tabelle,
    regel,
    verstoesse,
    CASE WHEN verstoesse = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM dq
ORDER BY pos;
