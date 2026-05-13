// =============================================================================
// 01_create_graph_model.cypher
// Neo4j Graphmodell für die Banana Supply Chain
//
// Erstellt:
//   - Constraints und Indizes
//   - Stammdaten-Nodes (Supplier, Customer, Product, Carrier, SupplyChainNode)
//   - Supply-Chain-Topologie (CONNECTED_TO-Beziehungen zwischen Knoten)
//   - Beispiel-Beziehungen für einen vollständigen Fulfillment-Vorgang
//
// Ausführung: Im Neo4j Browser unter http://localhost:7474
//             oder via cypher-shell:
//             cypher-shell -u neo4j -p password < 01_create_graph_model.cypher
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

// =============================================================================
// 2. SUPPLY-CHAIN-KNOTEN STAMMDATEN
// Stellt die Topologie der Banana Supply Chain dar
// =============================================================================

MERGE (n1:SupplyChainNode {node_code: "BANANA_PLANTATION"})
  SET n1.node_name     = "Banana Plantation Ghana",
      n1.node_type     = "PLANTATION",
      n1.region        = "Africa",
      n1.sequence_order = 1;

MERGE (n2:SupplyChainNode {node_code: "COLLECTION_CENTER"})
  SET n2.node_name     = "Collection Center Ghana",
      n2.node_type     = "COLLECTION_CENTER",
      n2.region        = "Africa",
      n2.sequence_order = 2;

MERGE (n3:SupplyChainNode {node_code: "QUALITY_CONTROL"})
  SET n3.node_name     = "Quality Control Station",
      n3.node_type     = "QUALITY_CONTROL",
      n3.region        = "Africa",
      n3.sequence_order = 3;

MERGE (n4:SupplyChainNode {node_code: "AFRICA_COLD_STORAGE"})
  SET n4.node_name     = "Africa Cold Storage Accra",
      n4.node_type     = "COLD_STORAGE",
      n4.region        = "Africa",
      n4.sequence_order = 4;

MERGE (n5:SupplyChainNode {node_code: "EUROPE_COLD_STORAGE"})
  SET n5.node_name     = "Europe Cold Storage Hamburg",
      n5.node_type     = "COLD_STORAGE",
      n5.region        = "Europe",
      n5.sequence_order = 5;

MERGE (n6:SupplyChainNode {node_code: "CENTRAL_WAREHOUSE"})
  SET n6.node_name     = "Central Warehouse Germany",
      n6.node_type     = "WAREHOUSE",
      n6.region        = "Europe",
      n6.sequence_order = 6;

MERGE (n7:SupplyChainNode {node_code: "RETAIL_STORE"})
  SET n7.node_name     = "Retail Store",
      n7.node_type     = "RETAIL",
      n7.region        = "Europe",
      n7.sequence_order = 7;

// Supply Chain Flow: CONNECTED_TO-Beziehungen
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

// Lieferanten starten an der Plantation
MATCH (s:Supplier), (n:SupplyChainNode {node_code: "BANANA_PLANTATION"})
MERGE (s)-[:DELIVERS_TO]->(n);

// =============================================================================
// 4. KUNDEN-STAMMDATEN
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

// Kunden empfangen am Retail Store
MATCH (c:Customer), (n:SupplyChainNode {node_code: "RETAIL_STORE"})
MERGE (c)-[:RECEIVES_FROM]->(n);

// =============================================================================
// 5. PRODUKT-STAMMDATEN
// =============================================================================

MERGE (p:Product {product_code: "BAN-101"}) SET p.product_name = "Cavendish Banana",  p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-102"}) SET p.product_name = "Organic Banana",    p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-103"}) SET p.product_name = "Premium Banana",    p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-104"}) SET p.product_name = "Baby Banana",       p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-105"}) SET p.product_name = "Fairtrade Banana",  p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-106"}) SET p.product_name = "Export Banana",     p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-107"}) SET p.product_name = "Sweet Banana",      p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-108"}) SET p.product_name = "Green Banana",      p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-109"}) SET p.product_name = "Yellow Banana",     p.category = "Fresh Fruit";
MERGE (p:Product {product_code: "BAN-110"}) SET p.product_name = "Tropical Banana",   p.category = "Fresh Fruit";

// =============================================================================
// 6. CARRIER-STAMMDATEN
// =============================================================================

MERGE (c:Carrier {carrier_code: "CAR-101"}) SET c.carrier_name = "DHL";
MERGE (c:Carrier {carrier_code: "CAR-102"}) SET c.carrier_name = "Maersk";
MERGE (c:Carrier {carrier_code: "CAR-103"}) SET c.carrier_name = "MSC";
MERGE (c:Carrier {carrier_code: "CAR-104"}) SET c.carrier_name = "DB Schenker";
MERGE (c:Carrier {carrier_code: "CAR-105"}) SET c.carrier_name = "Hapag Lloyd";

// Carrier-Routenzuordnungen
MATCH (c:Carrier {carrier_code: "CAR-101"}),
      (n:SupplyChainNode)
WHERE n.node_type IN ["PLANTATION", "COLLECTION_CENTER", "QUALITY_CONTROL", "WAREHOUSE", "RETAIL"]
MERGE (c)-[:OPERATES_ON {transport_mode: "TRUCK"}]->(n);

MATCH (c:Carrier {carrier_code: "CAR-102"}),
      (n:SupplyChainNode)
WHERE n.node_type = "COLD_STORAGE"
MERGE (c)-[:OPERATES_ON {transport_mode: "SEA_FREIGHT"}]->(n);

MATCH (c:Carrier {carrier_code: "CAR-103"}),
      (n:SupplyChainNode)
WHERE n.node_type = "COLD_STORAGE"
MERGE (c)-[:OPERATES_ON {transport_mode: "SEA_FREIGHT"}]->(n);

// =============================================================================
// 7. BEISPIEL-FULFILLMENT-VORGANG
// Demonstriert den vollständigen Graph eines Order-to-Delivery-Prozesses
// =============================================================================

// Lieferant-Produkt-Beziehung (Beispiel: SUP-104 liefert BAN-101)
MATCH (sup:Supplier {supplier_code: "SUP-104"}),
      (p:Product {product_code: "BAN-101"})
MERGE (sup)-[:SUPPLIES {since: "2024-01-01"}]->(p);

// Beispiel-Order
MERGE (o:Order {order_reference: "ORD-example-001"})
  SET o.delivery_priority = "NORMAL",
      o.order_date        = "2026-05-12";

// Kunde hat Bestellung aufgegeben
MATCH (cust:Customer {customer_number: "CUST-109"}),
      (o:Order {order_reference: "ORD-example-001"})
MERGE (cust)-[:PLACED {timestamp: "2026-05-12T11:50:40"}]->(o);

// Produkt in Bestellung
MATCH (p:Product {product_code: "BAN-108"}),
      (o:Order {order_reference: "ORD-example-001"})
MERGE (o)-[:CONTAINS {quantity: 760, unit_price: 3.09}]->(p);

// Batch zur Bestellung
MERGE (b:Batch {batch_identifier: "BATCH-example-001"})
  SET b.quantity       = 760,
      b.origin_country = "Ghana",
      b.harvested_at   = "2026-05-12T11:51:00";

MATCH (o:Order {order_reference: "ORD-example-001"}),
      (b:Batch {batch_identifier: "BATCH-example-001"})
MERGE (o)-[:TRIGGERED]->(b);

// Batch durch Knoten verarbeitet (Supply Chain Flow)
MATCH (b:Batch {batch_identifier: "BATCH-example-001"}),
      (n:SupplyChainNode {node_code: "BANANA_PLANTATION"})
MERGE (b)-[:PROCESSED_AT {temperature: 14.2, status: "COMPLETED", processed_at: "2026-05-12T12:00:00"}]->(n);

MATCH (b:Batch {batch_identifier: "BATCH-example-001"}),
      (n:SupplyChainNode {node_code: "AFRICA_COLD_STORAGE"})
MERGE (b)-[:PROCESSED_AT {temperature: 12.57, status: "COMPLETED", processed_at: "2026-05-12T13:00:00"}]->(n);

// Shipment (Seefracht)
MERGE (ship:Shipment {shipment_identifier: "SHIP-example-001"})
  SET ship.transport_mode  = "SEA_FREIGHT",
      ship.delay_minutes   = 45,
      ship.started_at      = "2026-05-12T14:00:00",
      ship.completed_at    = "2026-05-13T08:45:00";

MATCH (b:Batch {batch_identifier: "BATCH-example-001"}),
      (ship:Shipment {shipment_identifier: "SHIP-example-001"})
MERGE (b)-[:TRANSPORTED_VIA]->(ship);

MATCH (ship:Shipment {shipment_identifier: "SHIP-example-001"}),
      (car:Carrier {carrier_code: "CAR-104"})
MERGE (ship)-[:TRANSPORTED_BY {started_at: "2026-05-12T14:00:00", delay_minutes: 45}]->(car);

MATCH (ship:Shipment {shipment_identifier: "SHIP-example-001"}),
      (from:SupplyChainNode {node_code: "AFRICA_COLD_STORAGE"}),
      (to:SupplyChainNode {node_code: "EUROPE_COLD_STORAGE"})
MERGE (ship)-[:FROM]->(from)
MERGE (ship)-[:TO]->(to);

// Finale Lieferung
MATCH (ship:Shipment {shipment_identifier: "SHIP-example-001"}),
      (cust:Customer {customer_number: "CUST-109"})
MERGE (ship)-[:DELIVERED_TO {
    delivery_status: "SUCCESSFUL",
    received_by: "EMP-7",
    delivered_at: "2026-05-14T09:30:00"
}]->(cust);

// =============================================================================
// 8. NÜTZLICHE ABFRAGEN (als Kommentar)
// =============================================================================

// Alle Knoten der Supply Chain in Reihenfolge:
// MATCH (n:SupplyChainNode) RETURN n.node_name ORDER BY n.sequence_order

// Supply Chain Pfad:
// MATCH path = (:SupplyChainNode {node_code: "BANANA_PLANTATION"})-[:CONNECTED_TO*]->(:SupplyChainNode {node_code: "RETAIL_STORE"})
// RETURN [n IN nodes(path) | n.node_name] AS route

// Carrier mit höchster Durchschnittsverzögerung:
// MATCH (c:Carrier)-[:TRANSPORTED_BY]-(s:Shipment)
// RETURN c.carrier_name, AVG(s.delay_minutes) AS avg_delay ORDER BY avg_delay DESC

// Alle Produkte eines Lieferanten:
// MATCH (sup:Supplier {supplier_code: "SUP-104"})-[:SUPPLIES]->(p:Product)
// RETURN p.product_code, p.product_name
