// =============================================================================
// 01_create_graph_model.cypher
// Neo4j Graphmodell für die Banana Supply Chain
//
// Erstellt:
//   - Constraints und Indizes
//   - Stammdaten-Nodes (Supplier, Customer, Product, Carrier, SupplyChainNode)
//   - Supply-Chain-Topologie (CONNECTED_TO zwischen Knoten)
//   - Produkt-Lieferanten-Beziehungen (aus ProductCreated-Events abgeleitet)
//   - Vollständiger Fulfillment-Beispielvorgang (alle 7 Stationen, 6 Hops)
//   - Beispiel-Cypher-Abfragen
//
// Ausführung: Im Neo4j Browser unter http://localhost:7474
//             oder via cypher-shell:
//             cypher-shell -u neo4j -p password < 01_create_graph_model.cypher
//
// Node-Typen (8): Supplier, Customer, Product, Batch, Carrier, Shipment,
//                 Order, SupplyChainNode
// Relationships (13): SUPPLIES, DELIVERS_TO, CONNECTED_TO, OPERATES_ON,
//                     PLACED, CONTAINS, TRIGGERED, PROCESSED_AT,
//                     TRANSPORTED_VIA, TRANSPORTED_BY, FROM, TO,
//                     DELIVERED_TO
// =============================================================================

// =============================================================================
// 1. CONSTRAINTS UND INDIZES
// =============================================================================

CREATE CONSTRAINT supplier_code_unique IF NOT EXISTS
FOR (s:Supplier) REQUIRE s.supplier_code IS UNIQUE;

CREATE CONSTRAINT customer_number_unique IF NOT EXISTS
FOR (c:Customer) REQUIRE c.customer_number IS UNIQUE;

CREATE CONSTRAINT product_code_unique IF NOT EXISTS
FOR (p:Product) REQUIRE p.product_code IS UNIQUE;

CREATE CONSTRAINT carrier_code_unique IF NOT EXISTS
FOR (c:Carrier) REQUIRE c.carrier_code IS UNIQUE;

CREATE CONSTRAINT node_code_unique IF NOT EXISTS
FOR (n:SupplyChainNode) REQUIRE n.node_code IS UNIQUE;

CREATE CONSTRAINT batch_identifier_unique IF NOT EXISTS
FOR (b:Batch) REQUIRE b.batch_identifier IS UNIQUE;

CREATE CONSTRAINT shipment_identifier_unique IF NOT EXISTS
FOR (s:Shipment) REQUIRE s.shipment_identifier IS UNIQUE;

CREATE CONSTRAINT order_reference_unique IF NOT EXISTS
FOR (o:Order) REQUIRE o.order_reference IS UNIQUE;

// Index auf häufig gefilterte Properties
CREATE INDEX supply_chain_node_type IF NOT EXISTS
FOR (n:SupplyChainNode) ON (n.node_type);

CREATE INDEX supply_chain_node_region IF NOT EXISTS
FOR (n:SupplyChainNode) ON (n.region);

CREATE INDEX shipment_transport_mode IF NOT EXISTS
FOR (s:Shipment) ON (s.transport_mode);

CREATE INDEX batch_origin IF NOT EXISTS
FOR (b:Batch) ON (b.origin_country);

// =============================================================================
// 2. SUPPLY-CHAIN-KNOTEN STAMMDATEN
// Stellt die vollständige Topologie der Banana Supply Chain dar (7 Stationen)
// =============================================================================

MERGE (n1:SupplyChainNode {node_code: "BANANA_PLANTATION"})
  SET n1.node_name      = "Banana Plantation Ghana",
      n1.node_type      = "PLANTATION",
      n1.region         = "Africa",
      n1.sequence_order = 1;

MERGE (n2:SupplyChainNode {node_code: "COLLECTION_CENTER"})
  SET n2.node_name      = "Collection Center Ghana",
      n2.node_type      = "COLLECTION_CENTER",
      n2.region         = "Africa",
      n2.sequence_order = 2;

MERGE (n3:SupplyChainNode {node_code: "QUALITY_CONTROL"})
  SET n3.node_name      = "Quality Control Station",
      n3.node_type      = "QUALITY_CONTROL",
      n3.region         = "Africa",
      n3.sequence_order = 3;

MERGE (n4:SupplyChainNode {node_code: "AFRICA_COLD_STORAGE"})
  SET n4.node_name      = "Africa Cold Storage Accra",
      n4.node_type      = "COLD_STORAGE",
      n4.region         = "Africa",
      n4.sequence_order = 4;

MERGE (n5:SupplyChainNode {node_code: "EUROPE_COLD_STORAGE"})
  SET n5.node_name      = "Europe Cold Storage Hamburg",
      n5.node_type      = "COLD_STORAGE",
      n5.region         = "Europe",
      n5.sequence_order = 5;

MERGE (n6:SupplyChainNode {node_code: "CENTRAL_WAREHOUSE"})
  SET n6.node_name      = "Central Warehouse Germany",
      n6.node_type      = "WAREHOUSE",
      n6.region         = "Europe",
      n6.sequence_order = 6;

MERGE (n7:SupplyChainNode {node_code: "RETAIL_STORE"})
  SET n7.node_name      = "Retail Store",
      n7.node_type      = "RETAIL",
      n7.region         = "Europe",
      n7.sequence_order = 7;

// Supply Chain Topologie: 6 CONNECTED_TO-Kanten → 6-Hop-Pfad
MATCH (n1:SupplyChainNode {node_code: "BANANA_PLANTATION"}),
      (n2:SupplyChainNode {node_code: "COLLECTION_CENTER"})
MERGE (n1)-[:CONNECTED_TO {transport_mode: "TRUCK", typical_hours: 4}]->(n2);

MATCH (n2:SupplyChainNode {node_code: "COLLECTION_CENTER"}),
      (n3:SupplyChainNode {node_code: "QUALITY_CONTROL"})
MERGE (n2)-[:CONNECTED_TO {transport_mode: "TRUCK", typical_hours: 2}]->(n3);

MATCH (n3:SupplyChainNode {node_code: "QUALITY_CONTROL"}),
      (n4:SupplyChainNode {node_code: "AFRICA_COLD_STORAGE"})
MERGE (n3)-[:CONNECTED_TO {transport_mode: "TRUCK", typical_hours: 6}]->(n4);

MATCH (n4:SupplyChainNode {node_code: "AFRICA_COLD_STORAGE"}),
      (n5:SupplyChainNode {node_code: "EUROPE_COLD_STORAGE"})
MERGE (n4)-[:CONNECTED_TO {transport_mode: "SEA_FREIGHT", typical_hours: 240}]->(n5);

MATCH (n5:SupplyChainNode {node_code: "EUROPE_COLD_STORAGE"}),
      (n6:SupplyChainNode {node_code: "CENTRAL_WAREHOUSE"})
MERGE (n5)-[:CONNECTED_TO {transport_mode: "TRUCK", typical_hours: 8}]->(n6);

MATCH (n6:SupplyChainNode {node_code: "CENTRAL_WAREHOUSE"}),
      (n7:SupplyChainNode {node_code: "RETAIL_STORE"})
MERGE (n6)-[:CONNECTED_TO {transport_mode: "TRUCK", typical_hours: 3}]->(n7);

// =============================================================================
// 3. LIEFERANTEN-STAMMDATEN
// Quelle: ERP SupplierCreated-Events (SUP-101 bis SUP-110)
// =============================================================================

MERGE (s:Supplier {supplier_code: "SUP-101"}) SET s.supplier_name = "Golden Banana Ltd",        s.country = "Ghana";
MERGE (s:Supplier {supplier_code: "SUP-102"}) SET s.supplier_name = "Fresh Banana Export",      s.country = "Ghana";
MERGE (s:Supplier {supplier_code: "SUP-103"}) SET s.supplier_name = "Tropical Banana Group",    s.country = "Ghana";
MERGE (s:Supplier {supplier_code: "SUP-104"}) SET s.supplier_name = "Banana Kingdom",           s.country = "Ghana";
MERGE (s:Supplier {supplier_code: "SUP-105"}) SET s.supplier_name = "West Africa Fruits",       s.country = "Ghana";
MERGE (s:Supplier {supplier_code: "SUP-106"}) SET s.supplier_name = "Premium Banana Farms",     s.country = "Ghana";
MERGE (s:Supplier {supplier_code: "SUP-107"}) SET s.supplier_name = "Green Harvest Export",     s.country = "Ghana";
MERGE (s:Supplier {supplier_code: "SUP-108"}) SET s.supplier_name = "Sunshine Produce",         s.country = "Ghana";
MERGE (s:Supplier {supplier_code: "SUP-109"}) SET s.supplier_name = "Eco Banana Trading",       s.country = "Ghana";
MERGE (s:Supplier {supplier_code: "SUP-110"}) SET s.supplier_name = "Global Banana Source",     s.country = "Ghana";

// Alle Lieferanten starten an der Plantation (DELIVERS_TO)
MATCH (s:Supplier), (n:SupplyChainNode {node_code: "BANANA_PLANTATION"})
MERGE (s)-[:DELIVERS_TO]->(n);

// =============================================================================
// 4. KUNDEN-STAMMDATEN
// Quelle: ERP CustomerCreated-Events (CUST-101 bis CUST-110)
// =============================================================================

MERGE (c:Customer {customer_number: "CUST-101"}) SET c.customer_name = "ALDI",      c.city = "Frankfurt", c.country = "Germany";
MERGE (c:Customer {customer_number: "CUST-102"}) SET c.customer_name = "LIDL",      c.city = "Berlin",    c.country = "Germany";
MERGE (c:Customer {customer_number: "CUST-103"}) SET c.customer_name = "REWE",      c.city = "Hamburg",   c.country = "Germany";
MERGE (c:Customer {customer_number: "CUST-104"}) SET c.customer_name = "EDEKA",     c.city = "Munich",    c.country = "Germany";
MERGE (c:Customer {customer_number: "CUST-105"}) SET c.customer_name = "METRO",     c.city = "Cologne",   c.country = "Germany";
MERGE (c:Customer {customer_number: "CUST-106"}) SET c.customer_name = "KAUFLAND",  c.city = "Berlin",    c.country = "Germany";
MERGE (c:Customer {customer_number: "CUST-107"}) SET c.customer_name = "TESCO",     c.city = "Hamburg",   c.country = "Germany";
MERGE (c:Customer {customer_number: "CUST-108"}) SET c.customer_name = "CARREFOUR", c.city = "Frankfurt", c.country = "Germany";
MERGE (c:Customer {customer_number: "CUST-109"}) SET c.customer_name = "AUCHAN",    c.city = "Frankfurt", c.country = "Germany";
MERGE (c:Customer {customer_number: "CUST-110"}) SET c.customer_name = "SPAR",      c.city = "Munich",    c.country = "Germany";

// Kunden empfangen Lieferungen am Retail Store (RECEIVES_FROM)
MATCH (c:Customer), (n:SupplyChainNode {node_code: "RETAIL_STORE"})
MERGE (c)-[:RECEIVES_FROM]->(n);

// =============================================================================
// 5. PRODUKT-STAMMDATEN
// Quelle: ERP ProductCreated-Events (BAN-101 bis BAN-110)
// =============================================================================

MERGE (p:Product {product_code: "BAN-101"}) SET p.product_name = "Cavendish Banana", p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-102"}) SET p.product_name = "Organic Banana",   p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-103"}) SET p.product_name = "Premium Banana",   p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-104"}) SET p.product_name = "Baby Banana",      p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-105"}) SET p.product_name = "Fairtrade Banana", p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-106"}) SET p.product_name = "Export Banana",    p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-107"}) SET p.product_name = "Sweet Banana",     p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-108"}) SET p.product_name = "Green Banana",     p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-109"}) SET p.product_name = "Yellow Banana",    p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-110"}) SET p.product_name = "Tropical Banana",  p.category = "Fresh Fruit";

// SUPPLIES-Beziehungen: aus ERP ProductCreated supplier_reference abgeleitet
// BAN-101 → SUP-103, BAN-102 → SUP-106, BAN-103 → SUP-102, BAN-104 → SUP-108
// BAN-105 → SUP-108, BAN-106 → SUP-109, BAN-107 → SUP-107, BAN-108 → SUP-106
// BAN-109 → SUP-104, BAN-110 → SUP-101
MATCH (sup:Supplier {supplier_code: "SUP-103"}), (p:Product {product_code: "BAN-101"}) MERGE (sup)-[:SUPPLIES]->(p);
MATCH (sup:Supplier {supplier_code: "SUP-106"}), (p:Product {product_code: "BAN-102"}) MERGE (sup)-[:SUPPLIES]->(p);
MATCH (sup:Supplier {supplier_code: "SUP-102"}), (p:Product {product_code: "BAN-103"}) MERGE (sup)-[:SUPPLIES]->(p);
MATCH (sup:Supplier {supplier_code: "SUP-108"}), (p:Product {product_code: "BAN-104"}) MERGE (sup)-[:SUPPLIES]->(p);
MATCH (sup:Supplier {supplier_code: "SUP-108"}), (p:Product {product_code: "BAN-105"}) MERGE (sup)-[:SUPPLIES]->(p);
MATCH (sup:Supplier {supplier_code: "SUP-109"}), (p:Product {product_code: "BAN-106"}) MERGE (sup)-[:SUPPLIES]->(p);
MATCH (sup:Supplier {supplier_code: "SUP-107"}), (p:Product {product_code: "BAN-107"}) MERGE (sup)-[:SUPPLIES]->(p);
MATCH (sup:Supplier {supplier_code: "SUP-106"}), (p:Product {product_code: "BAN-108"}) MERGE (sup)-[:SUPPLIES]->(p);
MATCH (sup:Supplier {supplier_code: "SUP-104"}), (p:Product {product_code: "BAN-109"}) MERGE (sup)-[:SUPPLIES]->(p);
MATCH (sup:Supplier {supplier_code: "SUP-101"}), (p:Product {product_code: "BAN-110"}) MERGE (sup)-[:SUPPLIES]->(p);

// =============================================================================
// 6. CARRIER-STAMMDATEN
// Quelle: TMS CarrierCreated-Events (CAR-101 bis CAR-105)
// =============================================================================

MERGE (c:Carrier {carrier_code: "CAR-101"}) SET c.carrier_name = "DHL";
MERGE (c:Carrier {carrier_code: "CAR-102"}) SET c.carrier_name = "Maersk";
MERGE (c:Carrier {carrier_code: "CAR-103"}) SET c.carrier_name = "MSC";
MERGE (c:Carrier {carrier_code: "CAR-104"}) SET c.carrier_name = "DB Schenker";
MERGE (c:Carrier {carrier_code: "CAR-105"}) SET c.carrier_name = "Hapag Lloyd";

// OPERATES_ON: LKW-Carrier auf Landstrecken
MATCH (c:Carrier {carrier_code: "CAR-101"}),
      (n:SupplyChainNode)
WHERE n.node_type IN ["PLANTATION", "COLLECTION_CENTER", "QUALITY_CONTROL", "WAREHOUSE", "RETAIL"]
MERGE (c)-[:OPERATES_ON {transport_mode: "TRUCK"}]->(n);

// OPERATES_ON: Seefracht-Carrier auf Kaltlagerrouten
MATCH (c:Carrier {carrier_code: "CAR-102"}),
      (n:SupplyChainNode)
WHERE n.node_type = "COLD_STORAGE"
MERGE (c)-[:OPERATES_ON {transport_mode: "SEA_FREIGHT"}]->(n);

MATCH (c:Carrier {carrier_code: "CAR-103"}),
      (n:SupplyChainNode)
WHERE n.node_type = "COLD_STORAGE"
MERGE (c)-[:OPERATES_ON {transport_mode: "SEA_FREIGHT"}]->(n);

MATCH (c:Carrier {carrier_code: "CAR-104"}),
      (n:SupplyChainNode)
WHERE n.node_type = "COLD_STORAGE"
MERGE (c)-[:OPERATES_ON {transport_mode: "SEA_FREIGHT"}]->(n);

// =============================================================================
// 7. VOLLSTÄNDIGER FULFILLMENT-BEISPIELVORGANG
//
// Demonstriert alle 8 Node-Typen und 13 Relationship-Typen in einem
// durchgehenden Order-to-Delivery-Prozess.
//
// Realer Batch aus ERP-Event: BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b
// Produkt: BAN-108 (Green Banana), Lieferant: SUP-106 (Premium Banana Farms)
// Kunde:   CUST-109 (AUCHAN, Frankfurt)
// =============================================================================

// --- 7.1 Order ---
MERGE (o:Order {order_reference: "ORD-DEMO-001"})
  SET o.delivery_priority = "NORMAL",
      o.order_date        = "2026-05-12";

// Kunde CUST-109 hat Bestellung aufgegeben (PLACED)
MATCH (cust:Customer {customer_number: "CUST-109"}),
      (o:Order {order_reference: "ORD-DEMO-001"})
MERGE (cust)-[:PLACED {timestamp: "2026-05-12T11:50:40"}]->(o);

// Bestellung enthält Produkt BAN-108 (CONTAINS)
MATCH (p:Product {product_code: "BAN-108"}),
      (o:Order {order_reference: "ORD-DEMO-001"})
MERGE (o)-[:CONTAINS {quantity: 760, unit_price: 3.09}]->(p);

// --- 7.2 Batch ---
// Quelle: ERP BatchHarvested-Event (iteration_001)
MERGE (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"})
  SET b.quantity         = 760,
      b.origin_country   = "Ghana",
      b.harvested_at     = "2026-05-12T11:50:40";

// Bestellung löste Ernte aus (TRIGGERED)
MATCH (o:Order {order_reference: "ORD-DEMO-001"}),
      (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"})
MERGE (o)-[:TRIGGERED]->(b);

// --- 7.3 PROCESSED_AT – alle 7 Stationen (vollständiger 6-Hop-Pfad) ---
// Quelle: WMS NodeProcessed-Events + Temperaturen aus tatsächlichen Events

MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"}),
      (n:SupplyChainNode {node_code: "BANANA_PLANTATION"})
MERGE (b)-[:PROCESSED_AT {temperature: 14.2, status: "COMPLETED",
      processed_at: "2026-05-12T11:51:00"}]->(n);

MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"}),
      (n:SupplyChainNode {node_code: "COLLECTION_CENTER"})
MERGE (b)-[:PROCESSED_AT {temperature: 13.8, status: "COMPLETED",
      processed_at: "2026-05-12T15:55:00"}]->(n);

MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"}),
      (n:SupplyChainNode {node_code: "QUALITY_CONTROL"})
MERGE (b)-[:PROCESSED_AT {temperature: 13.5, status: "COMPLETED",
      processed_at: "2026-05-12T17:58:00"}]->(n);

MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"}),
      (n:SupplyChainNode {node_code: "AFRICA_COLD_STORAGE"})
MERGE (b)-[:PROCESSED_AT {temperature: 12.57, status: "COMPLETED",
      processed_at: "2026-05-13T00:15:00"}]->(n);

MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"}),
      (n:SupplyChainNode {node_code: "EUROPE_COLD_STORAGE"})
MERGE (b)-[:PROCESSED_AT {temperature: 12.1, status: "COMPLETED",
      processed_at: "2026-05-23T10:00:00"}]->(n);

MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"}),
      (n:SupplyChainNode {node_code: "CENTRAL_WAREHOUSE"})
MERGE (b)-[:PROCESSED_AT {temperature: 11.9, status: "COMPLETED",
      processed_at: "2026-05-23T18:30:00"}]->(n);

MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"}),
      (n:SupplyChainNode {node_code: "RETAIL_STORE"})
MERGE (b)-[:PROCESSED_AT {temperature: 11.5, status: "COMPLETED",
      processed_at: "2026-05-24T09:00:00"}]->(n);

// --- 7.4 Shipment (Seefracht Afrika → Europa) ---
// Quelle: TMS TransportStarted-Event (CAR-104 DB Schenker, SEA_FREIGHT)
MERGE (ship:Shipment {shipment_identifier: "SHIP-DEMO-001"})
  SET ship.transport_mode = "SEA_FREIGHT",
      ship.delay_minutes  = 45,
      ship.started_at     = "2026-05-13T14:00:00",
      ship.completed_at   = "2026-05-23T10:00:00";

// Batch wurde per Schiff transportiert (TRANSPORTED_VIA)
MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"}),
      (ship:Shipment {shipment_identifier: "SHIP-DEMO-001"})
MERGE (b)-[:TRANSPORTED_VIA]->(ship);

// Carrier DB Schenker hat transportiert (TRANSPORTED_BY)
MATCH (ship:Shipment {shipment_identifier: "SHIP-DEMO-001"}),
      (car:Carrier {carrier_code: "CAR-104"})
MERGE (ship)-[:TRANSPORTED_BY {started_at: "2026-05-13T14:00:00",
               delay_minutes: 45}]->(car);

// Quell- und Zielknoten des Shipments (FROM / TO)
MATCH (ship:Shipment {shipment_identifier: "SHIP-DEMO-001"}),
      (from:SupplyChainNode {node_code: "AFRICA_COLD_STORAGE"}),
      (to:SupplyChainNode   {node_code: "EUROPE_COLD_STORAGE"})
MERGE (ship)-[:FROM]->(from)
MERGE (ship)-[:TO]->(to);

// Finale Lieferung an Kunden (DELIVERED_TO)
MATCH (ship:Shipment {shipment_identifier: "SHIP-DEMO-001"}),
      (cust:Customer {customer_number: "CUST-109"})
MERGE (ship)-[:DELIVERED_TO {
    delivery_status: "SUCCESSFUL",
    received_by:     "EMP-7",
    delivered_at:    "2026-05-24T09:30:00"
}]->(cust);

// =============================================================================
// 8. NACHWEIS: Graphstatistik nach dem Laden
// =============================================================================

// Anzahl Nodes je Typ:
// MATCH (n) RETURN labels(n)[0] AS node_type, COUNT(n) AS count ORDER BY count DESC

// Anzahl Relationships je Typ:
// MATCH ()-[r]->() RETURN type(r) AS rel_type, COUNT(r) AS count ORDER BY count DESC

// =============================================================================
// 9. BEISPIEL-CYPHER-ABFRAGEN
// =============================================================================

// --- Q1: Vollständiger Weg eines Batches durch alle Stationen ---
// Zeigt die 7 Stationen mit Temperatur und Zeitstempel (6-Hop-Pfad)
//
// MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"})
//       -[r:PROCESSED_AT]->(n:SupplyChainNode)
// RETURN b.batch_identifier,
//        n.sequence_order,
//        n.node_name,
//        r.temperature,
//        r.status,
//        r.processed_at
// ORDER BY n.sequence_order

// --- Q2: Supply-Chain-Topologie PLANTATION → RETAIL (kürzester Pfad, 6 Hops) ---
//
// MATCH (start:SupplyChainNode {node_code: "BANANA_PLANTATION"}),
//       (end:SupplyChainNode   {node_code: "RETAIL_STORE"}),
//       path = shortestPath((start)-[:CONNECTED_TO*]->(end))
// RETURN [n IN nodes(path) | n.node_name] AS stationen,
//        [r IN relationships(path) | r.transport_mode] AS transport_mittel,
//        reduce(h = 0, r IN relationships(path) | h + r.typical_hours) AS gesamtstunden,
//        length(path) AS anzahl_hops

// --- Q3: Carrier mit höchster Durchschnittsverzögerung (Seefracht) ---
//
// MATCH (car:Carrier)<-[:TRANSPORTED_BY]-(ship:Shipment {transport_mode: "SEA_FREIGHT"})
// RETURN car.carrier_name,
//        COUNT(ship)              AS anzahl_shipments,
//        AVG(ship.delay_minutes)  AS avg_verzoegerung_min,
//        MAX(ship.delay_minutes)  AS max_verzoegerung_min
// ORDER BY avg_verzoegerung_min DESC

// --- Q4: Kühlketten-Verletzungen – Batches außerhalb 10–15 °C ---
//
// MATCH (b:Batch)-[r:PROCESSED_AT]->(n:SupplyChainNode)
// WHERE r.temperature < 10.0 OR r.temperature > 15.0
// RETURN b.batch_identifier,
//        n.node_name,
//        r.temperature AS temperatur_celsius,
//        r.processed_at
// ORDER BY r.processed_at DESC

// --- Q5: Lieferant → Produkt → Bestellung → Kunde (vollständige Kette) ---
//
// MATCH (sup:Supplier)-[:SUPPLIES]->(p:Product)<-[:CONTAINS]-(o:Order)<-[:PLACED]-(cust:Customer)
// RETURN sup.supplier_name,
//        p.product_name,
//        o.order_reference,
//        o.delivery_priority,
//        cust.customer_name
// ORDER BY o.order_date

// --- Q6: Alle Carrier und ihre aktiven Seefracht-Routen ---
//
// MATCH (car:Carrier)<-[:TRANSPORTED_BY]-(ship:Shipment),
//       (ship)-[:FROM]->(from:SupplyChainNode),
//       (ship)-[:TO]->(to:SupplyChainNode)
// RETURN car.carrier_name,
//        from.node_name AS von,
//        to.node_name   AS nach,
//        ship.transport_mode,
//        COUNT(ship)    AS fahrten
// ORDER BY fahrten DESC

// --- Q7: Durchschnittliche Temperatur je Station (Kühlketten-Monitoring) ---
//
// MATCH (b:Batch)-[r:PROCESSED_AT]->(n:SupplyChainNode)
// RETURN n.node_name,
//        n.sequence_order,
//        ROUND(AVG(r.temperature), 2) AS avg_temperatur,
//        MIN(r.temperature)           AS min_temperatur,
//        MAX(r.temperature)           AS max_temperatur
// ORDER BY n.sequence_order

// --- Q8: Welche Lieferanten beliefern welche Kunden indirekt über die Supply Chain? ---
// (Multi-Hop: Supplier → Product → Order → Customer)
//
// MATCH (sup:Supplier)-[:SUPPLIES]->(p:Product)<-[:CONTAINS]-(o:Order)<-[:PLACED]-(cust:Customer)
// RETURN DISTINCT sup.supplier_name AS lieferant,
//                 cust.customer_name AS kunde,
//                 COUNT(o) AS bestellungen
// ORDER BY bestellungen DESC
