-- =============================================================================
-- 08b_dq_audit.sql
-- Konsolidierte Datenqualitäts-Auditierung
--
-- Liefert EINE Ergebnistabelle mit allen 34 DQ-Checks aus 08_data_quality_checks.sql
-- für eine schnelle Übersicht. Sortiert nach Dimension und Verstössen.
-- Hinweis: Regel 5.0 (Stammdaten event_timestamp) prüft 4 Tabellen → 4 Zeilen (pos 24–27).
--
-- Spaltenformat:
--   dimension  - eine der 6 DQ-Dimensionen
--   nummer     - Regel-Nummer (1.1, 4.3 etc.)
--   tabelle    - betroffene Tabelle
--   regel      - Validierungsregel
--   verstoesse - Anzahl der Datensätze, die die Regel verletzen
--   status     - PASS (0 Verstösse) oder FAIL (>0)
--
-- Ausführung: docker exec -i postgres psql -U user -d logistics < sql/08b_dq_audit.sql
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
    -- Neue Regel VQ-05: Bestellungen ohne zugehörige Positionen
    -- Fachlich: Jede Order muss mindestens eine Bestellposition haben, sonst kein Rechnungswert berechenbar
    UNION ALL SELECT 5, 'VOLLSTÄNDIGKEIT', '1.5',
           'erp.orders', 'Order ohne Bestellpositionen',
           (SELECT COUNT(*) FROM erp.orders o
            WHERE NOT EXISTS (SELECT 1 FROM erp.order_items oi WHERE oi.order_id = o.order_id))

    -- ── 2. EINDEUTIGKEIT ──────────────────────────────────────────────────────
    UNION ALL SELECT 6, 'EINDEUTIGKEIT', '2.1',
           'erp.suppliers', 'supplier_code Duplikat',
           (SELECT COALESCE(SUM(anzahl), 0) FROM (
                SELECT COUNT(*) - 1 AS anzahl FROM erp.suppliers
                GROUP BY supplier_code HAVING COUNT(*) > 1
            ) x)
    UNION ALL SELECT 7, 'EINDEUTIGKEIT', '2.2',
           'erp.orders', 'order_reference Duplikat',
           (SELECT COALESCE(SUM(anzahl), 0) FROM (
                SELECT COUNT(*) - 1 AS anzahl FROM erp.orders
                GROUP BY order_reference HAVING COUNT(*) > 1
            ) x)
    UNION ALL SELECT 8, 'EINDEUTIGKEIT', '2.3',
           'erp.batches', 'batch_identifier Duplikat',
           (SELECT COALESCE(SUM(anzahl), 0) FROM (
                SELECT COUNT(*) - 1 AS anzahl FROM erp.batches
                GROUP BY batch_identifier HAVING COUNT(*) > 1
            ) x)
    UNION ALL SELECT 9, 'EINDEUTIGKEIT', '2.4',
           'tms.shipments', 'shipment_identifier Duplikat',
           (SELECT COALESCE(SUM(anzahl), 0) FROM (
                SELECT COUNT(*) - 1 AS anzahl FROM tms.shipments
                GROUP BY shipment_identifier HAVING COUNT(*) > 1
            ) x)

    -- ── 3. KONSISTENZ ─────────────────────────────────────────────────────────
    -- 3.1: Prüfung über source_key = w.sku (WMS-Format BAN_101).
    -- mdm.source_mappings.source_key speichert den Originalschlüssel je Quellsystem,
    -- daher direkter Vergleich ohne REPLACE-Transformation.
    UNION ALL SELECT 10, 'KONSISTENZ', '3.1',
           'wms.warehouse_skus', 'SKU ohne MDM-Mapping',
           (SELECT COUNT(*) FROM wms.warehouse_skus w
            WHERE NOT EXISTS (SELECT 1 FROM mdm.source_mappings sm
                              WHERE sm.source_system = 'WMS'
                                AND sm.source_key    = w.sku))
    UNION ALL SELECT 11, 'KONSISTENZ', '3.2',
           'tms.transport_product_references', 'TMS-Referenz ohne MDM-Mapping (über normalized_key)',
           (SELECT COUNT(*) FROM tms.transport_product_references t
            WHERE NOT EXISTS (SELECT 1 FROM mdm.source_mappings sm
                              WHERE sm.source_system  = 'TMS'
                                AND sm.normalized_key = LOWER(t.transport_product_reference)))
    UNION ALL SELECT 12, 'KONSISTENZ', '3.3',
           'erp.batches', 'wms_sku passt nicht zu product_code',
           (SELECT COUNT(*) FROM erp.batches b
            JOIN erp.products p ON p.product_id = b.product_id
            WHERE b.wms_sku IS NOT NULL
              AND b.wms_sku != REPLACE(p.product_code, '-', '_'))
    -- Neue Regel KQ-04: Lieferung als SUCCESSFUL markiert ohne abgeschlossenen Transport
    -- Fachlich: Jede erfolgreiche Delivery setzt voraus, dass auch ein TransportCompleted-Event existiert
    UNION ALL SELECT 13, 'KONSISTENZ', '3.4',
           'tms.deliveries + tms.transport_completions',
           'SUCCESSFUL-Delivery ohne TransportCompleted-Eintrag',
           (SELECT COUNT(*) FROM tms.deliveries d
            WHERE d.delivery_status = 'SUCCESSFUL'
              AND NOT EXISTS (
                  SELECT 1 FROM tms.transport_completions tc
                  WHERE tc.shipment_id = d.shipment_id
              ))

    -- ── 4. PLAUSIBILITÄT ──────────────────────────────────────────────────────
    UNION ALL SELECT 14, 'PLAUSIBILITÄT', '4.1',
           'erp.order_items', 'quantity <= 0',
           (SELECT COUNT(*) FROM erp.order_items WHERE quantity <= 0)
    UNION ALL SELECT 15, 'PLAUSIBILITÄT', '4.2',
           'erp.order_items', 'unit_price außerhalb [1.50, 5.00]',
           (SELECT COUNT(*) FROM erp.order_items WHERE unit_price < 1.50 OR unit_price > 5.00)
    UNION ALL SELECT 16, 'PLAUSIBILITÄT', '4.3',
           'wms.node_processings', 'temperature außerhalb [10, 15]°C (Kühlkettenbruch)',
           (SELECT COUNT(*) FROM wms.node_processings
            WHERE temperature IS NOT NULL AND (temperature < 10.0 OR temperature > 15.0))
    UNION ALL SELECT 17, 'PLAUSIBILITÄT', '4.4',
           'tms.shipment_positions', 'container_temperature außerhalb [10, 15]°C',
           (SELECT COUNT(*) FROM tms.shipment_positions
            WHERE container_temperature IS NOT NULL
              AND (container_temperature < 10.0 OR container_temperature > 15.0))
    UNION ALL SELECT 18, 'PLAUSIBILITÄT', '4.5',
           'tms.shipment_positions', 'latitude/longitude außerhalb Wertebereich',
           (SELECT COUNT(*) FROM tms.shipment_positions
            WHERE latitude NOT BETWEEN -90 AND 90
               OR longitude NOT BETWEEN -180 AND 180)
    UNION ALL SELECT 19, 'PLAUSIBILITÄT', '4.6',
           'tms.deliveries', 'delivery_status ungültig',
           (SELECT COUNT(*) FROM tms.deliveries
            WHERE delivery_status NOT IN ('SUCCESSFUL','DELAYED','FAILED'))
    UNION ALL SELECT 20, 'PLAUSIBILITÄT', '4.7',
           'erp.orders', 'delivery_priority ungültig',
           (SELECT COUNT(*) FROM erp.orders
            WHERE delivery_priority NOT IN ('HIGH','NORMAL','LOW'))
    UNION ALL SELECT 21, 'PLAUSIBILITÄT', '4.8',
           'tms.transport_completions', 'delay_minutes > 180',
           (SELECT COUNT(*) FROM tms.transport_completions WHERE delay_minutes > 180)
    UNION ALL SELECT 22, 'PLAUSIBILITÄT', '4.9',
           'tms.shipment_positions', 'speed_kmh > 200 oder < 0',
           (SELECT COUNT(*) FROM tms.shipment_positions
            WHERE speed_kmh IS NOT NULL AND (speed_kmh > 200 OR speed_kmh < 0))
    UNION ALL SELECT 23, 'PLAUSIBILITÄT', '4.10',
           'tms.shipment_positions', 'GPS-Koordinaten außerhalb erwarteter Routenkorridore',
           (SELECT COUNT(*)
            FROM tms.shipment_positions sp
            JOIN tms.shipments s ON s.shipment_id = sp.shipment_id
            WHERE NOT (
                (
                    s.source_node IN ('BANANA_PLANTATION', 'COLLECTION_CENTER', 'QUALITY_CONTROL')
                    AND s.target_node IN ('COLLECTION_CENTER', 'QUALITY_CONTROL', 'AFRICA_COLD_STORAGE')
                    AND sp.latitude BETWEEN 4.5 AND 7.5
                    AND sp.longitude BETWEEN -2.5 AND 1.0
                )
                OR
                (
                    s.source_node = 'AFRICA_COLD_STORAGE'
                    AND s.target_node = 'EUROPE_COLD_STORAGE'
                    AND sp.latitude BETWEEN 0.0 AND 55.0
                    AND sp.longitude BETWEEN -20.0 AND 10.0
                )
                OR
                (
                    s.source_node IN ('EUROPE_COLD_STORAGE', 'CENTRAL_WAREHOUSE')
                    AND s.target_node IN ('CENTRAL_WAREHOUSE', 'RETAIL_STORE')
                    AND sp.latitude BETWEEN 49.0 AND 54.0
                    AND sp.longitude BETWEEN 3.0 AND 15.0
                )
            ))

    -- ── 5. AKTUALITÄT ─────────────────────────────────────────────────────────
    -- Regel 5.0 aus 08_data_quality_checks.sql: Stammdaten event_timestamp ausserhalb 2025-2026.
    -- 4 Unterprüfungen – eine je Tabelle mit event_timestamp-Spalte (pos 24–27).
    UNION ALL SELECT 24, 'AKTUALITÄT', '5.0',
           'erp.suppliers', 'event_timestamp ausserhalb 2025-2026',
           (SELECT COUNT(*) FROM erp.suppliers
            WHERE event_timestamp < '2025-01-01' OR event_timestamp > NOW() + INTERVAL '1 day')
    UNION ALL SELECT 25, 'AKTUALITÄT', '5.0',
           'erp.customers', 'event_timestamp ausserhalb 2025-2026',
           (SELECT COUNT(*) FROM erp.customers
            WHERE event_timestamp < '2025-01-01' OR event_timestamp > NOW() + INTERVAL '1 day')
    UNION ALL SELECT 26, 'AKTUALITÄT', '5.0',
           'erp.products', 'event_timestamp ausserhalb 2025-2026',
           (SELECT COUNT(*) FROM erp.products
            WHERE event_timestamp < '2025-01-01' OR event_timestamp > NOW() + INTERVAL '1 day')
    UNION ALL SELECT 27, 'AKTUALITÄT', '5.0',
           'tms.carriers', 'event_timestamp ausserhalb 2025-2026',
           (SELECT COUNT(*) FROM tms.carriers
            WHERE event_timestamp < '2025-01-01' OR event_timestamp > NOW() + INTERVAL '1 day')
    UNION ALL SELECT 28, 'AKTUALITÄT', '5.1',
           'tms', 'TransportCompleted vor TransportStarted',
           (SELECT COUNT(*) FROM tms.transport_completions tc
            JOIN tms.shipments s ON s.shipment_id = tc.shipment_id
            WHERE tc.completed_at < s.started_at)
    -- Bugfix Check 5.2: erp.batches hat KEIN order_id-Feld (BatchHarvested enthält keine Bestellreferenz).
    -- Geändert von "BatchHarvested vor OrderCreated" zu Plausibilitätsprüfung des Erntezeitpunkts.
    UNION ALL SELECT 29, 'AKTUALITÄT', '5.2',
           'erp.batches', 'harvested_at außerhalb Projektlaufzeit (2025-2026)',
           (SELECT COUNT(*) FROM erp.batches
            WHERE harvested_at < '2025-01-01' OR harvested_at > NOW() + INTERVAL '1 day')
    UNION ALL SELECT 30, 'AKTUALITÄT', '5.3',
           'erp.orders', 'Order > 90 Tage ohne Delivery',
           (SELECT COUNT(*) FROM erp.orders o
            WHERE o.order_timestamp < NOW() - INTERVAL '90 days'
              AND NOT EXISTS (
                  SELECT 1
                  FROM   erp.order_items  oi
                  JOIN   erp.products     p  ON p.product_id  = oi.product_id
                  JOIN   erp.batches      b  ON b.product_id  = p.product_id
                  JOIN   tms.shipments    sp ON sp.cargo_product_reference = b.tms_product_reference
                  JOIN   tms.deliveries   d  ON d.shipment_id = sp.shipment_id
                  WHERE  oi.order_id = o.order_id))

    -- ── 6. REFERENZIELLE INTEGRITÄT ───────────────────────────────────────────
    UNION ALL SELECT 31, 'REF. INTEGRITÄT', '6.1',
           'wms.node_processings', 'batch_reference ohne erp.batches',
           (SELECT COUNT(*) FROM wms.node_processings np
            WHERE NOT EXISTS (SELECT 1 FROM erp.batches b
                              WHERE b.batch_identifier = np.batch_reference))
    UNION ALL SELECT 32, 'REF. INTEGRITÄT', '6.2',
           'tms.shipments', 'cargo_product_reference ohne tms.transport_product_references',
           (SELECT COUNT(*) FROM tms.shipments s
            WHERE NOT EXISTS (SELECT 1 FROM tms.transport_product_references r
                              WHERE r.transport_product_reference = s.cargo_product_reference))
    -- Check 6.3: Status-Inkonsistenz mit 60-min-SLA (Datengenerator-Bug).
    -- Fall A: TMS=SUCCESSFUL, delay_minutes > 60 (SLA verletzt → DWH korrigiert zu DELAYED)
    -- Fall B: TMS=DELAYED, delay_minutes <= 60 (innerhalb SLA → DWH korrigiert zu SUCCESSFUL)
    -- Verstösse sind erwartet und dokumentiert; Korrektur erfolgt in etl_dwh.py.
    UNION ALL SELECT 33, 'KONSISTENZ', '6.3',
           'tms.deliveries', 'Status-Inkonsistenz mit 60-min-SLA (TMS-Rohstatus vs. SLA-korrigierter Status)',
           (SELECT COUNT(*) FROM tms.deliveries d
            JOIN tms.transport_completions tc ON tc.shipment_id = d.shipment_id
            WHERE (d.delivery_status = 'SUCCESSFUL' AND tc.delay_minutes > 60)
               OR (d.delivery_status = 'DELAYED'    AND tc.delay_minutes <= 60))
    -- Check 6.4: Carrier/Transport-Mode-Inkonsistenz (Datengenerator-Bug).
    -- Reedereien (CAR-102/103/105) dürfen nicht auf TRUCK-Strecken erscheinen;
    -- Landcarrier (CAR-101/104) nicht auf SEA_FREIGHT-Strecken.
    UNION ALL SELECT 34, 'KONSISTENZ', '6.4',
           'tms.shipments', 'Seefracht-Carrier auf TRUCK-Route oder Landcarrier auf SEA_FREIGHT',
           (SELECT COUNT(*) FROM tms.shipments s
            JOIN tms.carriers c ON c.carrier_id = s.carrier_id
            WHERE (c.carrier_code IN ('CAR-102','CAR-103','CAR-105') AND s.transport_mode = 'TRUCK')
               OR (c.carrier_code IN ('CAR-101','CAR-104') AND s.transport_mode = 'SEA_FREIGHT'))
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
