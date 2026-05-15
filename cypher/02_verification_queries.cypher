// =============================================================================
// 02_verification_queries.cypher
// Technische Nachweise – Neo4j Graphmodell Banana Supply Chain
//
// Alle Queries sind ausführbar (nicht kommentiert).
// Ausführung: Im Neo4j Browser (http://localhost:7474) oder via cypher-shell:
//   cypher-shell -u neo4j -p password -f cypher/02_verification_queries.cypher
//
// Erwartete Ergebnisse (Stand Testlauf 2026-05-14):
//   Nodes gesamt:          ≥ 125 (10 Sup + 10 Cust + 10 Prod + Carrier + Nodes + Batches + Orders + Shipments)
//   Relationships gesamt:  ≥ 47
// =============================================================================

// =============================================================================
// 1. NACHWEIS: Node-Typen und Anzahl
// Erwartet: 8 Node-Typen – alle Stammdaten + ETL-Daten geladen
// =============================================================================

MATCH (n)
RETURN labels(n)[0] AS node_typ, COUNT(n) AS anzahl
ORDER BY anzahl DESC;

// Erwartete Ausgabe (Mindestwerte nach ETL):
//   Supplier          10
//   Customer          10
//   Product           10
//   SupplyChainNode    7
//   Carrier            5
//   Order             11  (10 ETL + 1 DEMO)
//   Batch             11  (10 ETL + 1 DEMO)
//   Shipment          62  (61 ETL + 1 DEMO)

// =============================================================================
// 2. NACHWEIS: Relationship-Typen und Anzahl
// Erwartet: 12+ Typen
// =============================================================================

MATCH ()-[r]->()
RETURN type(r) AS relationship_typ, COUNT(r) AS anzahl
ORDER BY anzahl DESC;

// =============================================================================
// 3. NACHWEIS: Constraints und Indizes (Schema-Integrität)
// =============================================================================

SHOW CONSTRAINTS;

SHOW INDEXES WHERE type <> 'LOOKUP';

// =============================================================================
// 4. NACHWEIS: Vollständige Stammdaten-Abdeckung
// =============================================================================

// 4.1 Alle 10 Lieferanten vorhanden?
MATCH (s:Supplier)
RETURN COUNT(s) AS anzahl_supplier,
       COLLECT(s.supplier_code) AS supplier_codes;

// 4.2 Alle 10 Produkte vorhanden?
MATCH (p:Product)
RETURN COUNT(p) AS anzahl_produkte,
       COLLECT(p.product_code) AS product_codes;

// 4.3 Alle 7 Supply-Chain-Knoten in korrekter Reihenfolge?
MATCH (n:SupplyChainNode)
RETURN n.sequence_order AS reihenfolge,
       n.node_code      AS node_code,
       n.node_name      AS name,
       n.node_type      AS typ
ORDER BY n.sequence_order;

// =============================================================================
// 5. NACHWEIS: Supply-Chain-Topologie (6-Hop-Pfad PLANTATION → RETAIL)
// =============================================================================

MATCH (start:SupplyChainNode {node_code: "BANANA_PLANTATION"}),
      (end:SupplyChainNode   {node_code: "RETAIL_STORE"}),
      path = shortestPath((start)-[:CONNECTED_TO*]->(end))
RETURN [n IN nodes(path) | n.node_name]              AS stationen,
       [r IN relationships(path) | r.transport_mode] AS transportmittel,
       reduce(h = 0, r IN relationships(path) | h + r.typical_hours) AS gesamtstunden,
       length(path) AS anzahl_hops;

// Erwartete Ausgabe:
//   stationen: [Banana Plantation Ghana, Collection Center Ghana, Quality Control Station,
//               Africa Cold Storage Accra, Europe Cold Storage Hamburg, Central Warehouse Germany, Retail Store]
//   anzahl_hops: 6

// =============================================================================
// 6. NACHWEIS: Fulfillment-Beispielvorgang (Demo-Batch)
// Prüft den vollständigen Order-to-Delivery-Pfad aus 01_create_graph_model.cypher
// =============================================================================

// 6.1 Batch-Weg durch alle 7 Stationen
MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"})
      -[r:PROCESSED_AT]->(n:SupplyChainNode)
RETURN b.batch_identifier,
       n.sequence_order AS station_nr,
       n.node_name      AS station,
       r.temperature    AS temp_celsius,
       r.status         AS status,
       r.processed_at   AS zeitpunkt
ORDER BY n.sequence_order;

// Erwartete Ausgabe: 7 Zeilen (alle Stationen), Temperaturen 10–15 °C

// 6.2 Vollständige Fulfillment-Kette: Kunde → Order → Batch → Shipment → Carrier
MATCH (cust:Customer)-[:PLACED]->(o:Order)-[:TRIGGERED]->(b:Batch)
      -[:TRANSPORTED_VIA]->(ship:Shipment)-[:TRANSPORTED_BY]->(car:Carrier)
WHERE o.order_reference = "ORD-DEMO-001"
RETURN cust.customer_name AS kunde,
       o.order_reference  AS order_ref,
       b.batch_identifier AS batch,
       ship.shipment_identifier AS shipment,
       ship.transport_mode AS modus,
       car.carrier_name   AS carrier;

// =============================================================================
// 7. NACHWEIS: ETL-geladene Orders und Batches
// =============================================================================

// 7.1 Alle ETL-Orders mit Kunde und Produkt
MATCH (c:Customer)-[:PLACED]->(o:Order)-[:CONTAINS]->(p:Product)
RETURN c.customer_number AS kunde,
       o.order_reference AS order_ref,
       p.product_code    AS produkt,
       o.delivery_priority AS prioritaet
ORDER BY o.order_reference;

// 7.2 Carrier-Übersicht mit Anzahl transportierter Shipments
MATCH (car:Carrier)<-[:TRANSPORTED_BY]-(ship:Shipment)
RETURN car.carrier_code  AS carrier_code,
       car.carrier_name  AS carrier,
       COUNT(ship)        AS anzahl_shipments,
       COLLECT(DISTINCT ship.transport_mode) AS transport_modi
ORDER BY anzahl_shipments DESC;

// =============================================================================
// 8. NACHWEIS: Kühlketten-Monitoring (Demo-Batch)
// Alle Temperaturen müssen zwischen 10.0 und 15.0 °C liegen
// =============================================================================

MATCH (b:Batch)-[r:PROCESSED_AT]->(n:SupplyChainNode)
WHERE b.batch_identifier = "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"
RETURN
    n.node_name                                        AS station,
    r.temperature                                      AS temp_celsius,
    CASE WHEN r.temperature >= 10.0 AND r.temperature <= 15.0
         THEN "OK"
         ELSE "KUEHLKETTENBRUCH"
    END AS kuehlketten_status
ORDER BY n.sequence_order;

// =============================================================================
// 9. NACHWEIS: Lieferant→Produkt-Abdeckung (SUPPLIES-Relationships)
// Jedes Produkt muss genau einen Lieferanten haben
// =============================================================================

MATCH (sup:Supplier)-[:SUPPLIES]->(p:Product)
RETURN p.product_code AS produkt,
       p.product_name AS name,
       sup.supplier_code AS lieferant_code,
       sup.supplier_name AS lieferant
ORDER BY p.product_code;

// =============================================================================
// 10. INTEGRITÄTSPRÜFUNG: Produkte ohne Lieferanten (Soll: 0 Zeilen)
// =============================================================================

MATCH (p:Product)
WHERE NOT EXISTS { MATCH (:Supplier)-[:SUPPLIES]->(p) }
RETURN COUNT(p) AS produkte_ohne_lieferant;

// =============================================================================
// 11. INTEGRITÄTSPRÜFUNG: Supplier-Produkt-Kunde-Kette vollständig?
// Zeigt alle indirekten Lieferanten-Kunden-Verbindungen (via Order)
// =============================================================================

MATCH (sup:Supplier)-[:SUPPLIES]->(p:Product)<-[:CONTAINS]-(o:Order)<-[:PLACED]-(cust:Customer)
RETURN sup.supplier_name   AS lieferant,
       COUNT(DISTINCT cust) AS belieferte_kunden,
       COUNT(o)             AS bestellungen
ORDER BY bestellungen DESC;
