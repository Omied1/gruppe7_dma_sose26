-- =============================================================================
-- 00_sql_cheatsheet.sql
-- Cheat Sheet: PostgreSQL öffnen und wichtige SQL-Abfragen ausführen
--
-- Nutzung:
--   1. Terminal öffnen
--   2. In den Projektordner wechseln
--   3. PostgreSQL-Container starten
--   4. In psql einloggen
--   5. SQL-Befehle aus dieser Datei einzeln kopieren und ausführen
-- =============================================================================

-- -----------------------------------------------------------------------------
-- TERMINAL: In den richtigen Projektordner wechseln
-- -----------------------------------------------------------------------------
-- cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26

-- -----------------------------------------------------------------------------
-- TERMINAL: PostgreSQL-Container starten, falls er noch nicht läuft
-- -----------------------------------------------------------------------------
-- docker compose -f bananasupplychain/container/docker-compose.yml up -d postgres

-- -----------------------------------------------------------------------------
-- TERMINAL: PostgreSQL interaktiv öffnen
-- Danach kannst du mehrere SQL-Befehle nacheinander eingeben.
-- -----------------------------------------------------------------------------
-- docker exec -it postgres psql -U user -d logistics

-- -----------------------------------------------------------------------------
-- PSQL: Nützliche psql-Kommandos innerhalb von PostgreSQL
-- Diese Befehle beginnen mit Backslash und brauchen kein Semikolon.
-- -----------------------------------------------------------------------------
-- \dn                 -- alle Schemas anzeigen
-- \dt erp.*           -- alle ERP-Tabellen anzeigen
-- \dt wms.*           -- alle WMS-Tabellen anzeigen
-- \dt tms.*           -- alle TMS-Tabellen anzeigen
-- \dt mdm.*           -- alle MDM-Tabellen anzeigen
-- \dt dwh.*           -- alle DWH-Tabellen anzeigen
-- \d erp.suppliers    -- Spalten einer Tabelle anzeigen
-- \q                  -- PostgreSQL verlassen

-- =============================================================================
-- ALLGEMEINE ÜBERSICHTEN
-- =============================================================================

-- Alle Tabellen in den wichtigsten Schemas anzeigen:
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('erp', 'wms', 'tms', 'mdm', 'dwh', 'meta')
  AND table_type = 'BASE TABLE'
ORDER BY table_schema, table_name;

-- Anzahl Datensätze pro wichtiger Tabelle:
SELECT 'erp.suppliers' AS table_name, COUNT(*) AS row_count FROM erp.suppliers
UNION ALL
SELECT 'erp.customers', COUNT(*) FROM erp.customers
UNION ALL
SELECT 'erp.products', COUNT(*) FROM erp.products
UNION ALL
SELECT 'erp.orders', COUNT(*) FROM erp.orders
UNION ALL
SELECT 'erp.order_items', COUNT(*) FROM erp.order_items
UNION ALL
SELECT 'erp.batches', COUNT(*) FROM erp.batches
UNION ALL
SELECT 'wms.warehouse_skus', COUNT(*) FROM wms.warehouse_skus
UNION ALL
SELECT 'wms.supply_chain_nodes', COUNT(*) FROM wms.supply_chain_nodes
UNION ALL
SELECT 'wms.node_processings', COUNT(*) FROM wms.node_processings
UNION ALL
SELECT 'tms.carriers', COUNT(*) FROM tms.carriers
UNION ALL
SELECT 'tms.shipments', COUNT(*) FROM tms.shipments
UNION ALL
SELECT 'tms.shipment_positions', COUNT(*) FROM tms.shipment_positions
UNION ALL
SELECT 'tms.transport_completions', COUNT(*) FROM tms.transport_completions
UNION ALL
SELECT 'tms.deliveries', COUNT(*) FROM tms.deliveries
ORDER BY table_name;

-- =============================================================================
-- ERP: Enterprise Resource Planning
-- =============================================================================

-- Lieferanten anzeigen:
SELECT supplier_code, supplier_name, country
FROM erp.suppliers
ORDER BY country, supplier_code;

-- Kunden anzeigen:
SELECT customer_number, customer_name, city, country
FROM erp.customers
ORDER BY country, customer_name;

-- Produkte mit Lieferanteninfo:
SELECT
    p.product_code,
    p.product_name,
    p.category,
    s.supplier_name,
    s.country AS herkunft
FROM erp.products p
JOIN erp.suppliers s ON s.supplier_id = p.supplier_id
ORDER BY p.product_code;

-- Bestellungen mit Kundennamen:
SELECT
    o.order_reference,
    c.customer_name,
    o.delivery_priority,
    o.order_timestamp
FROM erp.orders o
JOIN erp.customers c ON c.customer_id = o.customer_id
ORDER BY o.order_timestamp DESC;

-- Bestellpositionen mit Produktnamen:
SELECT
    o.order_reference,
    p.product_code,
    p.product_name,
    oi.quantity,
    oi.unit_price,
    ROUND(oi.quantity * oi.unit_price, 2) AS positionswert_eur
FROM erp.order_items oi
JOIN erp.orders o ON o.order_id = oi.order_id
JOIN erp.products p ON p.product_id = oi.product_id
ORDER BY o.order_timestamp DESC, p.product_code;

-- Bestellvolumen pro Kunde:
SELECT
    c.customer_name,
    COUNT(DISTINCT o.order_id) AS anzahl_bestellungen,
    SUM(oi.quantity) AS gesamtmenge,
    ROUND(SUM(oi.quantity * oi.unit_price), 2) AS gesamtwert_eur
FROM erp.customers c
JOIN erp.orders o ON o.customer_id = c.customer_id
JOIN erp.order_items oi ON oi.order_id = o.order_id
GROUP BY c.customer_name
ORDER BY gesamtwert_eur DESC;

-- Ernte-Batches mit Produktinfo:
SELECT
    b.batch_identifier,
    p.product_code,
    p.product_name,
    b.origin_country,
    b.quantity,
    b.wms_sku,
    b.tms_product_reference,
    b.harvested_at
FROM erp.batches b
JOIN erp.products p ON p.product_id = b.product_id
ORDER BY b.harvested_at DESC;

-- =============================================================================
-- WMS: Warehouse Management System
-- =============================================================================

-- WMS-SKUs mit ERP-Produktcode:
SELECT sku, erp_product_code, event_timestamp
FROM wms.warehouse_skus
ORDER BY sku;

-- Supply-Chain-Knoten in Prozessreihenfolge:
SELECT node_code, node_name, node_type, region, sequence_order
FROM wms.supply_chain_nodes
ORDER BY sequence_order;

-- Verarbeitete Batches je Supply-Chain-Knoten:
SELECT
    n.node_name,
    n.sequence_order,
    COUNT(np.processing_id) AS anzahl_verarbeitungen
FROM wms.supply_chain_nodes n
LEFT JOIN wms.node_processings np ON np.node_id = n.node_id
GROUP BY n.node_name, n.sequence_order
ORDER BY n.sequence_order;

-- WMS-Prozessereignisse mit Knotenname:
SELECT
    np.batch_reference,
    np.sku,
    n.node_name,
    np.status,
    np.temperature,
    np.processed_at
FROM wms.node_processings np
JOIN wms.supply_chain_nodes n ON n.node_id = np.node_id
ORDER BY np.processed_at DESC;

-- Kühlkettenprüfung im WMS: Temperaturen außerhalb 10 bis 15 Grad:
SELECT
    np.batch_reference,
    np.sku,
    n.node_name,
    np.temperature,
    np.processed_at
FROM wms.node_processings np
JOIN wms.supply_chain_nodes n ON n.node_id = np.node_id
WHERE np.temperature < 10 OR np.temperature > 15
ORDER BY np.processed_at DESC;

-- =============================================================================
-- TMS: Transport Management System
-- =============================================================================

-- Carrier anzeigen:
SELECT carrier_code, carrier_name, event_timestamp
FROM tms.carriers
ORDER BY carrier_code;

-- TMS-Produktreferenzen mit ERP-Code:
SELECT erp_product_code, transport_product_reference
FROM tms.transport_product_references
ORDER BY erp_product_code;

-- Shipments mit Carrier:
SELECT
    s.shipment_identifier,
    s.source_node,
    s.target_node,
    s.transport_mode,
    s.cargo_product_reference,
    c.carrier_name,
    s.started_at,
    s.estimated_arrival
FROM tms.shipments s
JOIN tms.carriers c ON c.carrier_id = s.carrier_id
ORDER BY s.started_at DESC;

-- Durchschnittliche Verspätung pro Carrier:
SELECT
    c.carrier_name,
    COUNT(tc.completion_id) AS abgeschlossene_transporte,
    ROUND(AVG(tc.delay_minutes), 2) AS durchschnitt_delay_minuten,
    MAX(tc.delay_minutes) AS max_delay_minuten
FROM tms.transport_completions tc
JOIN tms.shipments s ON s.shipment_id = tc.shipment_id
JOIN tms.carriers c ON c.carrier_id = s.carrier_id
GROUP BY c.carrier_name
ORDER BY durchschnitt_delay_minuten DESC;

-- Lieferstatus-Übersicht:
SELECT
    delivery_status,
    COUNT(*) AS anzahl_lieferungen
FROM tms.deliveries
GROUP BY delivery_status
ORDER BY anzahl_lieferungen DESC;

-- GPS-Positionen mit Shipment:
SELECT
    s.shipment_identifier,
    sp.latitude,
    sp.longitude,
    sp.container_temperature,
    sp.speed_kmh,
    sp.recorded_at
FROM tms.shipment_positions sp
JOIN tms.shipments s ON s.shipment_id = sp.shipment_id
ORDER BY sp.recorded_at DESC;

-- Kühlkettenprüfung im TMS: Container-Temperaturen außerhalb 10 bis 15 Grad:
SELECT
    s.shipment_identifier,
    sp.container_temperature,
    sp.latitude,
    sp.longitude,
    sp.recorded_at
FROM tms.shipment_positions sp
JOIN tms.shipments s ON s.shipment_id = sp.shipment_id
WHERE sp.container_temperature < 10 OR sp.container_temperature > 15
ORDER BY sp.recorded_at DESC;

-- =============================================================================
-- SYSTEMÜBERGREIFENDE ABFRAGEN
-- =============================================================================

-- ERP-Produkt, WMS-SKU und TMS-Referenz zusammen anzeigen:
SELECT
    p.product_code AS erp_product_code,
    p.product_name,
    ws.sku AS wms_sku,
    tpr.transport_product_reference AS tms_product_reference
FROM erp.products p
LEFT JOIN wms.warehouse_skus ws
    ON ws.erp_product_code = p.product_code
LEFT JOIN tms.transport_product_references tpr
    ON tpr.erp_product_code = p.product_code
ORDER BY p.product_code;

-- Batch-Tracking: Ernte-Batch plus WMS-Verarbeitung:
SELECT
    b.batch_identifier,
    p.product_code,
    p.product_name,
    n.node_name,
    np.status,
    np.temperature,
    np.processed_at
FROM erp.batches b
JOIN erp.products p ON p.product_id = b.product_id
LEFT JOIN wms.node_processings np ON np.batch_reference = b.batch_identifier
LEFT JOIN wms.supply_chain_nodes n ON n.node_id = np.node_id
ORDER BY b.batch_identifier, n.sequence_order;

-- =============================================================================
-- DATEI DIREKT AUSFÜHREN
-- =============================================================================
-- Wenn du die ganze Datei ausführen willst:
-- docker exec -i postgres psql -U user -d logistics < sql/00_sql_cheatsheet.sql
--
-- Achtung: Diese Datei ist eher zum Kopieren einzelner Befehle gedacht.
-- Die Terminal-Befehle sind deshalb als Kommentare geschrieben.
-- =============================================================================
