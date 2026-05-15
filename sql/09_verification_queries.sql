-- =============================================================================
-- 09_verification_queries.sql
-- Technische Nachweise – vollständige Befüllungsprüfung aller PostgreSQL-Schemas
--
-- Deckt ab:
--   1. Datenbasis (ERP / WMS / TMS): Tabellenmengen nach ETL Phase 1
--   2. MDM: Golden Records, Source Mappings, Schlüsselauflösung
--   3. Metadaten: systems, tables, columns
--   4. DWH: Dimensionen + Faktentabelle nach ETL Phase 2
--   5. Fremdschlüssel-Integrität (intra-Schema)
--   6. Cross-Schema-Referenzen (WMS↔ERP, TMS↔ERP)
--
-- Ausführung: docker exec -i postgres psql -U user -d logistics < sql/09_verification_queries.sql
-- Erwartetes Ergebnis (Stand Testlauf 2026-05-14): alle Counts gemäß Kommentaren.
-- =============================================================================

\echo ''
\echo '============================================================'
\echo ' TECHNISCHE NACHWEISE – PostgreSQL Banana Supply Chain'
\echo '============================================================'

-- =============================================================================
-- 1. DATENBASIS: ERP-Schema
-- =============================================================================

\echo ''
\echo '--- 1. ERP-Schema ---'

SELECT 'erp.suppliers'   AS tabelle, COUNT(*) AS zeilen,
       '10 Lieferanten (SUP-101..SUP-110)' AS erwarteter_wert
FROM erp.suppliers
UNION ALL
SELECT 'erp.customers',  COUNT(*),
       '10 Kunden (CUST-101..CUST-110)'
FROM erp.customers
UNION ALL
SELECT 'erp.products',   COUNT(*),
       '10 Produkte (BAN-101..BAN-110)'
FROM erp.products
UNION ALL
SELECT 'erp.orders',     COUNT(*),
       '10 Bestellungen (ORD-...)'
FROM erp.orders
UNION ALL
SELECT 'erp.order_items', COUNT(*),
       '10-20 Positionen (je 1-2 Items pro Order)'
FROM erp.order_items
UNION ALL
SELECT 'erp.batches',    COUNT(*),
       '10 Chargen (BATCH-...)'
FROM erp.batches
UNION ALL
SELECT 'erp.document_references', COUNT(*),
       '≥ 66 Dokumentreferenzen (ETL) / 116 mit generate_documents.py'
FROM erp.document_references;

-- FK-Integrität: products.supplier_id muss in suppliers vorhanden sein
-- (DB-Constraint prüft bereits, dieser Check dient als Protokollnachweis)
SELECT
    'ERP FK-Check' AS check_name,
    'erp.products → erp.suppliers' AS beziehung,
    COUNT(*) AS orphan_produkte
FROM erp.products p
WHERE p.supplier_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM erp.suppliers s WHERE s.supplier_id = p.supplier_id
);

-- FK-Integrität: order_items.order_id + product_id
SELECT
    'ERP FK-Check' AS check_name,
    'erp.order_items → erp.orders + erp.products' AS beziehung,
    SUM(CASE WHEN o.order_id   IS NULL THEN 1 ELSE 0 END) AS orphan_orders,
    SUM(CASE WHEN pr.product_id IS NULL THEN 1 ELSE 0 END) AS orphan_products
FROM erp.order_items oi
LEFT JOIN erp.orders   o  ON o.order_id   = oi.order_id
LEFT JOIN erp.products pr ON pr.product_id = oi.product_id;

-- FK-Integrität: orders.customer_id
SELECT
    'ERP FK-Check' AS check_name,
    'erp.orders → erp.customers' AS beziehung,
    COUNT(*) AS orphan_orders
FROM erp.orders ord
WHERE NOT EXISTS (
    SELECT 1 FROM erp.customers c WHERE c.customer_id = ord.customer_id
);

-- =============================================================================
-- 2. DATENBASIS: WMS-Schema
-- =============================================================================

\echo ''
\echo '--- 2. WMS-Schema ---'

SELECT 'wms.warehouse_skus'    AS tabelle, COUNT(*) AS zeilen,
       '10 SKUs (BAN_101..BAN_110)' AS erwarteter_wert
FROM wms.warehouse_skus
UNION ALL
SELECT 'wms.supply_chain_nodes', COUNT(*),
       '7 Knoten (PLANTATION → RETAIL)'
FROM wms.supply_chain_nodes
UNION ALL
SELECT 'wms.node_processings', COUNT(*),
       '60 Verarbeitungen (10 Batches × 6 aktive Knoten)'
FROM wms.node_processings;

-- FK-Integrität: node_processings.node_id → supply_chain_nodes
SELECT
    'WMS FK-Check' AS check_name,
    'wms.node_processings → wms.supply_chain_nodes' AS beziehung,
    COUNT(*) AS orphan_processings
FROM wms.node_processings np
WHERE NOT EXISTS (
    SELECT 1 FROM wms.supply_chain_nodes n WHERE n.node_id = np.node_id
);

-- =============================================================================
-- 3. DATENBASIS: TMS-Schema
-- =============================================================================

\echo ''
\echo '--- 3. TMS-Schema ---'

SELECT 'tms.carriers'                    AS tabelle, COUNT(*) AS zeilen,
       '5 Carrier (CAR-101..CAR-105)'    AS erwarteter_wert
FROM tms.carriers
UNION ALL
SELECT 'tms.transport_product_references', COUNT(*),
       '10 TMS-Produktreferenzen (BAN-101..BAN-110)'
FROM tms.transport_product_references
UNION ALL
SELECT 'tms.shipments',                  COUNT(*),
       '60 Transporte (10 Batches × 6 Hops)'
FROM tms.shipments
UNION ALL
SELECT 'tms.shipment_positions',         COUNT(*),
       '118 GPS-Positionen (≈2 je Shipment)'
FROM tms.shipment_positions
UNION ALL
SELECT 'tms.transport_completions',      COUNT(*),
       '60 Transportabschlüsse'
FROM tms.transport_completions
UNION ALL
SELECT 'tms.deliveries',                 COUNT(*),
       '10 Endlieferungen (DeliveryCompleted-Events)'
FROM tms.deliveries;

-- FK-Integrität: shipments → carriers
SELECT
    'TMS FK-Check' AS check_name,
    'tms.shipments → tms.carriers' AS beziehung,
    COUNT(*) AS orphan_shipments
FROM tms.shipments s
WHERE NOT EXISTS (
    SELECT 1 FROM tms.carriers c WHERE c.carrier_id = s.carrier_id
);

-- FK-Integrität: positions / completions / deliveries → shipments
SELECT
    'TMS FK-Check'                            AS check_name,
    'tms.shipment_positions → tms.shipments'  AS beziehung,
    COUNT(*) AS orphan_positionen
FROM tms.shipment_positions sp
WHERE NOT EXISTS (
    SELECT 1 FROM tms.shipments s WHERE s.shipment_id = sp.shipment_id
)
UNION ALL
SELECT
    'TMS FK-Check',
    'tms.transport_completions → tms.shipments',
    COUNT(*)
FROM tms.transport_completions tc
WHERE NOT EXISTS (
    SELECT 1 FROM tms.shipments s WHERE s.shipment_id = tc.shipment_id
)
UNION ALL
SELECT
    'TMS FK-Check',
    'tms.deliveries → tms.shipments',
    COUNT(*)
FROM tms.deliveries d
WHERE NOT EXISTS (
    SELECT 1 FROM tms.shipments s WHERE s.shipment_id = d.shipment_id
);

-- =============================================================================
-- 4. MDM: Golden Records und Schlüsselauflösung
-- =============================================================================

\echo ''
\echo '--- 4. MDM-Schema ---'

-- Abdeckung Golden Records je Entity-Typ
-- Erwartet: CARRIER=5, CUSTOMER=10, PRODUCT=10, SUPPLIER=10, SUPPLY_CHAIN_NODE=7
SELECT
    et.entity_type_code                                        AS entity_typ,
    COUNT(gr.golden_id)                                        AS golden_records,
    COUNT(gr.golden_id) FILTER (WHERE gr.status = 'ACTIVE')   AS active
FROM mdm.entity_types et
LEFT JOIN mdm.golden_records gr ON gr.entity_type_id = et.entity_type_id
GROUP BY et.entity_type_code
ORDER BY et.entity_type_code;

-- Source Mappings je Quellsystem
-- Erwartet: ERP=30, WMS=17, TMS=22
SELECT
    source_system,
    COUNT(*)                                     AS total_mappings,
    COUNT(*) FILTER (WHERE is_canonical = TRUE)  AS canonical_mappings
FROM mdm.source_mappings
GROUP BY source_system
ORDER BY source_system;

-- Kerntest: Schlüsselauflösung (alle drei Formate → BAN-101)
SELECT
    mdm.resolve_canonical_key('BAN-101', 'ERP') AS erp_auflosung,
    mdm.resolve_canonical_key('BAN_101', 'WMS') AS wms_auflosung,
    mdm.resolve_canonical_key('ban-101', 'TMS') AS tms_auflosung;

-- Integritätsprüfung: 0 Verletzungen erwartet (je Golden Record genau 1 canonical mapping)
SELECT
    CASE WHEN COUNT(*) = 0
         THEN 'PASS – jeder Golden Record hat genau 1 canonical mapping'
         ELSE 'FAIL – ' || COUNT(*) || ' Golden Records ohne oder mit mehreren canonical mappings'
    END AS is_canonical_check
FROM (
    SELECT golden_id, COUNT(*) FILTER (WHERE is_canonical) AS canon_count
    FROM   mdm.source_mappings
    GROUP  BY golden_id
    HAVING COUNT(*) FILTER (WHERE is_canonical) != 1
) t;

-- =============================================================================
-- 5. METADATEN-SCHEMA
-- =============================================================================

\echo ''
\echo '--- 5. Metadaten-Schema ---'

SELECT 'meta.systems' AS tabelle, COUNT(*) AS zeilen,
       '≥ 5 Systeme (ERP, WMS, TMS, MDM, DWH)' AS erwarteter_wert
FROM meta.systems
UNION ALL
SELECT 'meta.tables', COUNT(*),
       '≥ 15 Tabellen (alle relevanten operativen Tabellen)'
FROM meta.tables
UNION ALL
SELECT 'meta.columns', COUNT(*),
       '≥ 50 Spalten mit Skalenniveau und Qualitätsregeln'
FROM meta.columns;

-- Skalenniveau-Abdeckung (alle 4 Typen müssen vorhanden sein)
SELECT
    scale_level,
    COUNT(*) AS spalten
FROM meta.columns
GROUP BY scale_level
ORDER BY scale_level;

-- =============================================================================
-- 6. DWH: Dimensionen + Faktentabelle (nach ETL Phase 2)
-- =============================================================================

\echo ''
\echo '--- 6. DWH-Schema ---'

SELECT 'dwh.dim_customer'         AS tabelle, COUNT(*) AS zeilen,
       '10 Kunden' AS erwarteter_wert
FROM dwh.dim_customer
UNION ALL
SELECT 'dwh.dim_supplier',        COUNT(*), '10 Lieferanten' FROM dwh.dim_supplier
UNION ALL
SELECT 'dwh.dim_product',         COUNT(*), '10 Produkte'    FROM dwh.dim_product
UNION ALL
SELECT 'dwh.dim_carrier',         COUNT(*), '5 Carrier'      FROM dwh.dim_carrier
UNION ALL
SELECT 'dwh.dim_supply_chain_node', COUNT(*),
       '7 Knoten (PLANTATION → RETAIL)'
FROM dwh.dim_supply_chain_node
UNION ALL
SELECT 'dwh.dim_date',            COUNT(*),
       '1095 Zeilen (2025-01-01 bis 2027-12-31)'
FROM dwh.dim_date
UNION ALL
SELECT 'dwh.dim_delivery_status', COUNT(*),
       '4 Statuscodes (SUCCESSFUL, DELAYED, FAILED, IN_TRANSIT)'
FROM dwh.dim_delivery_status
UNION ALL
SELECT 'dwh.fact_fulfillment',    COUNT(*),
       '≥ 60 Fulfillment-Fakten (10 Endlieferungen × 6 Hops)'
FROM dwh.fact_fulfillment;

-- DWH Date Spine: Bereich und Vollständigkeit prüfen
SELECT
    MIN(date_actual) AS von,
    MAX(date_actual) AS bis,
    COUNT(*)         AS tage_gesamt,
    CASE WHEN COUNT(*) = 1095 THEN 'PASS – 1095 Tage (2025-2027)'
         ELSE 'FAIL – erwartet 1095, gefunden: ' || COUNT(*)
    END AS date_spine_check
FROM dwh.dim_date;

-- DWH Measures: Plausibilitätsprüfung der Faktentabelle
SELECT
    COUNT(*)                                               AS total_facts,
    ROUND(AVG(quantity), 1)                                AS avg_menge,
    ROUND(AVG(avg_temperature), 2)                         AS avg_temp_celsius,
    ROUND(AVG(delay_minutes), 1)                           AS avg_verzoegerung_min,
    SUM(CASE WHEN on_time_flag THEN 1 ELSE 0 END)          AS on_time_count,
    ROUND(100.0 * SUM(CASE WHEN on_time_flag THEN 1 ELSE 0 END) / COUNT(*), 1) AS liefertreue_pct
FROM dwh.fact_fulfillment;

-- =============================================================================
-- 7. CROSS-SCHEMA-REFERENZEN (WMS↔ERP, TMS↔ERP)
-- Diese FKs sind logisch, aber nicht als DB-Constraints erzwungen.
-- Nachweis: ETL hat alle Referenzen korrekt befüllt.
-- =============================================================================

\echo ''
\echo '--- 7. Cross-Schema-Referenzen ---'

-- WMS batch_reference → ERP batch_identifier
SELECT
    CASE WHEN COUNT(*) = 0
         THEN 'PASS – alle batch_references in WMS auflösbar'
         ELSE 'FAIL – ' || COUNT(*) || ' node_processings ohne ERP-Batch'
    END AS wms_erp_batch_check
FROM wms.node_processings np
WHERE NOT EXISTS (
    SELECT 1 FROM erp.batches b WHERE b.batch_identifier = np.batch_reference
);

-- TMS cargo_product_reference → TMS transport_product_references
SELECT
    CASE WHEN COUNT(*) = 0
         THEN 'PASS – alle cargo_product_references in TMS auflösbar'
         ELSE 'FAIL – ' || COUNT(*) || ' Shipments ohne TMS-Produktreferenz'
    END AS tms_productref_check
FROM tms.shipments s
WHERE NOT EXISTS (
    SELECT 1 FROM tms.transport_product_references r
    WHERE r.transport_product_reference = s.cargo_product_reference
);

-- =============================================================================
-- 8. GESAMTÜBERSICHT: Tabellen-Counts in einer Ergebniszeile
-- =============================================================================

\echo ''
\echo '--- 8. Gesamtübersicht ---'

SELECT
    (SELECT COUNT(*) FROM erp.suppliers)                AS erp_suppliers,
    (SELECT COUNT(*) FROM erp.customers)                AS erp_customers,
    (SELECT COUNT(*) FROM erp.products)                 AS erp_products,
    (SELECT COUNT(*) FROM erp.orders)                   AS erp_orders,
    (SELECT COUNT(*) FROM erp.order_items)              AS erp_order_items,
    (SELECT COUNT(*) FROM erp.batches)                  AS erp_batches,
    (SELECT COUNT(*) FROM wms.warehouse_skus)           AS wms_skus,
    (SELECT COUNT(*) FROM wms.supply_chain_nodes)       AS wms_nodes,
    (SELECT COUNT(*) FROM wms.node_processings)         AS wms_processings,
    (SELECT COUNT(*) FROM tms.carriers)                 AS tms_carriers,
    (SELECT COUNT(*) FROM tms.shipments)                AS tms_shipments,
    (SELECT COUNT(*) FROM tms.shipment_positions)       AS tms_positions,
    (SELECT COUNT(*) FROM tms.transport_completions)    AS tms_completions,
    (SELECT COUNT(*) FROM tms.deliveries)               AS tms_deliveries,
    (SELECT COUNT(*) FROM mdm.golden_records)           AS mdm_golden_records,
    (SELECT COUNT(*) FROM mdm.source_mappings)          AS mdm_source_mappings,
    (SELECT COUNT(*) FROM dwh.dim_date)                 AS dwh_dim_date,
    (SELECT COUNT(*) FROM dwh.fact_fulfillment)         AS dwh_facts;

DO $$
BEGIN
    RAISE NOTICE '=== Verifikation abgeschlossen. Alle FAIL-Einträge erfordern Nacharbeit. ===';
END $$;
