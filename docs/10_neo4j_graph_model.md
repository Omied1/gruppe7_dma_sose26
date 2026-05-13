# Neo4j Graphmodell – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-12  
**Cypher-Implementierung:** `cypher/01_create_graph_model.cypher`

---

## 1. Warum Neo4j für die Supply Chain?

Die Banana Supply Chain ist ein **Netzwerk** aus Akteuren (Lieferanten, Kunden, Carrier) und physischen Stationen (Plantage, Lager, Retail) mit vielschichtigen Beziehungen. Relationale Datenbanken modellieren Beziehungen als JOINs, die bei tieferen Pfaden (z.B. 4+ Ebenen) exponentiell teuer werden.

**Neo4j beantwortet Fragen, die in SQL kompliziert sind:**

| Frage | SQL | Cypher |
|---|---|---|
| Welchen Weg hat Batch X durch die Supply Chain genommen? | 6+ JOINs über 4 Schemas | `MATCH (b:Batch)-[:PROCESSED_AT*]->(n:SupplyChainNode)` |
| Welche Carrier transportieren auf der Afrika→Europa-Strecke? | JOIN tms.shipments + tms.carriers + Knotenfilter | `MATCH (c:Carrier)-[:TRANSPORTED]->(s:Shipment)-[:ON_ROUTE]->` |
| Gibt es alternative Routen zwischen zwei Knoten? | Rekursive CTE (aufwendig) | `MATCH p = shortestPath(...)` |
| Welche Lieferanten beliefern welche Kunden indirekt? | Multi-level JOIN | `MATCH (s:Supplier)-[*1..6]-(c:Customer)` |

---

## 2. Graphmodell: Nodes und Properties

### Node-Labels

| Label | Entspricht | Properties | Beispiel |
|---|---|---|---|
| `Supplier` | erp.suppliers | supplier_code, supplier_name, country | `SUP-101, Golden Banana Ltd, Ghana` |
| `Customer` | erp.customers | customer_number, customer_name, city, country | `CUST-101, ALDI, Frankfurt, Germany` |
| `Product` | erp.products | product_code, product_name, category | `BAN-101, Cavendish Banana, Fresh Fruit` |
| `Carrier` | tms.carriers | carrier_code, carrier_name | `CAR-101, DHL` |
| `SupplyChainNode` | wms.supply_chain_nodes | node_code, node_name, node_type, region, sequence_order | `AFRICA_COLD_STORAGE, Cold Storage Accra, COLD_STORAGE, Africa, 4` |
| `Order` | erp.orders | order_reference, delivery_priority, order_date | `ORD-<uuid>, HIGH, 2026-05-12` |
| `Batch` | erp.batches | batch_identifier, quantity, origin_country | `BATCH-<uuid>, 760, Ghana` |
| `Shipment` | tms.shipments | shipment_identifier, transport_mode, delay_minutes | `SHIP-<uuid>, SEA_FREIGHT, 45` |

---

## 3. Beziehungen (Relationships)

### Stammdaten-Beziehungen

```
(Supplier)-[:SUPPLIES]->(Product)
  Bedeutung: Lieferant produziert/liefert dieses Produkt
  Properties: since (Datum der ersten Lieferbeziehung)

(Supplier)-[:DELIVERS_TO]->(SupplyChainNode)
  Bedeutung: Lieferant liefert an bestimmten Ausgangspunkt
  Properties: contract_start

(SupplyChainNode)-[:CONNECTED_TO {transport_mode: "TRUCK"}]->(SupplyChainNode)
  Bedeutung: Zwei Knoten sind über eine Transportstrecke verbunden
  Properties: transport_mode, typical_duration_hours, distance_km

(Carrier)-[:OPERATES_ON]->(SupplyChainNode)
  Bedeutung: Carrier ist auf einer bestimmten Route aktiv
```

### Operative Beziehungen

```
(Customer)-[:PLACED]->(Order)
  Bedeutung: Kunde hat Bestellung aufgegeben
  Properties: order_timestamp

(Order)-[:CONTAINS]->(Product)
  Bedeutung: Bestellung enthält Produkt
  Properties: quantity, unit_price

(Order)-[:TRIGGERED]->(Batch)
  Bedeutung: Bestellung löste Ernte aus
  Properties: harvest_date

(Batch)-[:PROCESSED_AT]->(SupplyChainNode)
  Bedeutung: Batch wurde an diesem Knoten verarbeitet
  Properties: temperature, status, processed_at

(Batch)-[:TRANSPORTED_VIA]->(Shipment)
  Bedeutung: Batch wurde mit diesem Shipment transportiert

(Shipment)-[:TRANSPORTED_BY]->(Carrier)
  Bedeutung: Transport wurde von Carrier durchgeführt
  Properties: started_at, completed_at, delay_minutes

(Shipment)-[:FROM]->(SupplyChainNode)
(Shipment)-[:TO]->(SupplyChainNode)
  Bedeutung: Quell- und Zielknoten eines Transports

(Shipment)-[:DELIVERED_TO]->(Customer)
  Bedeutung: Finale Lieferung an Kunden (letzter Transport)
  Properties: delivery_status, received_by, delivered_at
```

---

## 4. Graphmodell-Diagramm

```
[Supplier]──SUPPLIES──►[Product]
    │                      │
    │                 CONTAINS
    │                      ▼
    │                  [Order]◄──PLACED──[Customer]
    │                      │                  ▲
    │                 TRIGGERED           DELIVERED_TO
    │                      ▼                  │
    └──DELIVERS_TO──►[Batch]──TRANSPORTED_VIA──►[Shipment]──TRANSPORTED_BY──►[Carrier]
                       │                           │
                  PROCESSED_AT                  FROM / TO
                       ▼                           ▼
              [SupplyChainNode]◄──CONNECTED_TO──[SupplyChainNode]

Knotenfolge (Supply Chain Flow):
BANANA_PLANTATION ──TRUCK──► COLLECTION_CENTER
COLLECTION_CENTER ──TRUCK──► QUALITY_CONTROL
QUALITY_CONTROL   ──TRUCK──► AFRICA_COLD_STORAGE
AFRICA_COLD_STORAGE ──SEA_FREIGHT──► EUROPE_COLD_STORAGE
EUROPE_COLD_STORAGE ──TRUCK──► CENTRAL_WAREHOUSE
CENTRAL_WAREHOUSE ──TRUCK──► RETAIL_STORE
```

---

## 5. Beispiel-Cypher-Abfragen

### 5.1 Vollständiger Weg eines Batches
```cypher
MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad"})-[:PROCESSED_AT]->(n:SupplyChainNode)
RETURN b.batch_identifier, n.node_name, n.sequence_order
ORDER BY n.sequence_order
```

### 5.2 Alle Carrier auf der Seefrachtstrecke
```cypher
MATCH (c:Carrier)-[:TRANSPORTED_BY]-(s:Shipment {transport_mode: "SEA_FREIGHT"})
      -[:FROM]->(from:SupplyChainNode {node_code: "AFRICA_COLD_STORAGE"})
      -[:TO]->(to:SupplyChainNode {node_code: "EUROPE_COLD_STORAGE"})
RETURN c.carrier_name, COUNT(s) AS shipments, AVG(s.delay_minutes) AS avg_delay
ORDER BY avg_delay
```

### 5.3 Lieferant → Kunde-Pfad (gesamte Supply Chain)
```cypher
MATCH path = (sup:Supplier)-[:SUPPLIES]->(p:Product)<-[:CONTAINS]-(o:Order)<-[:PLACED]-(c:Customer)
WHERE sup.supplier_code = "SUP-101"
RETURN sup.supplier_name, p.product_name, o.order_reference, c.customer_name
```

### 5.4 Kühlketten-Probleme: Welche Batches hatten Temperaturprobleme?
```cypher
MATCH (b:Batch)-[r:PROCESSED_AT]->(n:SupplyChainNode)
WHERE r.temperature < 10.0 OR r.temperature > 15.0
RETURN b.batch_identifier, n.node_name, r.temperature, r.processed_at
ORDER BY r.processed_at DESC
```

### 5.5 Kürzester Pfad zwischen zwei Knoten
```cypher
MATCH (start:SupplyChainNode {node_code: "BANANA_PLANTATION"}),
      (end:SupplyChainNode {node_code: "RETAIL_STORE"}),
      path = shortestPath((start)-[:CONNECTED_TO*]->(end))
RETURN [n IN nodes(path) | n.node_name] AS route,
       LENGTH(path) AS hops
```

---

## 6. Neo4j vs. PostgreSQL: Typische Abfragen im Vergleich

### Frage: Welchen Weg hat ein Batch durch die Supply Chain genommen?

**SQL (PostgreSQL):**
```sql
SELECT n.node_name, np.temperature, np.processed_at
FROM   erp.batches        b
JOIN   wms.node_processings np ON np.batch_reference = b.batch_identifier
JOIN   wms.supply_chain_nodes n ON n.node_id = np.node_id
WHERE  b.batch_identifier = 'BATCH-9c6818ad'
ORDER  BY n.sequence_order;
-- 3 JOINs, einfach – aber skaliert schlecht bei tieferen Hierarchien
```

**Cypher (Neo4j):**
```cypher
MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad"})-[:PROCESSED_AT]->(n:SupplyChainNode)
RETURN n.node_name ORDER BY n.sequence_order
-- 1 Pattern-Match, nativ für Graphtraversal optimiert
```

**Fazit:** Für diese spezifische Abfrage ist SQL noch konkurrenzfähig. Bei Netzwerkanalysen (z.B. „Welche Lieferanten sind über mehrere Carrier mit welchen Kunden verbunden?") skaliert Neo4j erheblich besser als SQL.
