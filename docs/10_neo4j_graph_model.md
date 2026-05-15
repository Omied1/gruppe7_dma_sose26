# Neo4j Graphmodell – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-15  
**Cypher-Implementierung:** `cypher/01_create_graph_model.cypher`

---

## 1. Warum Neo4j für die Supply Chain?

Die Banana Supply Chain ist ein **Netzwerk** aus Akteuren (Lieferanten, Kunden, Carrier) und physischen Stationen (Plantage, Kaltlager, Retail) mit vielschichtigen Beziehungen. Relationale Datenbanken modellieren Beziehungen als JOINs, die bei tieferen Pfaden (z.B. 6+ Ebenen) exponentiell teuer werden.

**Neo4j beantwortet Fragen, die in SQL umständlich sind:**

| Frage | SQL | Cypher |
|---|---|---|
| Welchen Weg hat Batch BAN-108 durch alle 7 Stationen genommen? | 3 JOINs (batches + node_processings + supply_chain_nodes) | `MATCH (b:Batch)-[:PROCESSED_AT*]->(n:SupplyChainNode)` |
| Welche Carrier transportieren auf der Afrika→Europa-Strecke? | JOIN tms.shipments + tms.carriers + Knotenfilter | `MATCH (c:Carrier)<-[:TRANSPORTED_BY]-(s:Shipment)-[:FROM]->()` |
| Gibt es alternative Routen zwischen zwei Knoten? | Rekursive CTE | `MATCH p = shortestPath(...)` |
| Welche Lieferanten beliefern welche Kunden indirekt? | 4-facher JOIN über 3 Schemas | `MATCH (sup)-[:SUPPLIES]->()<-[:CONTAINS]-()<-[:PLACED]-(cust)` |

**Konkrete Stärke bei Pfadanalysen:** SQL mit rekursiven CTEs kann den 6-Hop-Pfad PLANTATION→RETAIL theoretisch abbilden, wird aber bei variablen Tiefenangaben (`*1..6`) und mehreren gleichzeitigen Pfadoptimierungen (kürzeste Route, billigste Route, kälteste Route) erheblich komplexer als die entsprechende Cypher-Abfrage.

---

## 2. Graphmodell: Node-Typen und Properties

### 8 Node-Labels

| Label | Entspricht | Properties | Beispiel |
|---|---|---|---|
| `Supplier` | erp.suppliers | supplier_code, supplier_name, country | `SUP-103, Tropical Banana Group, Ghana` |
| `Customer` | erp.customers | customer_number, customer_name, city, country | `CUST-101, ALDI, Frankfurt, Germany` |
| `Product` | erp.products | product_code, product_name, category | `BAN-101, Cavendish Banana, Fresh Fruit` |
| `Carrier` | tms.carriers | carrier_code, carrier_name | `CAR-101, DHL` |
| `SupplyChainNode` | wms.supply_chain_nodes | node_code, node_name, node_type, region, sequence_order | `AFRICA_COLD_STORAGE, Cold Storage Accra, COLD_STORAGE, Africa, 4` |
| `Order` | erp.orders | order_reference, delivery_priority, order_date | `ORD-DEMO-001, NORMAL, 2026-05-12` |
| `Batch` | erp.batches | batch_identifier, quantity, origin_country, harvested_at | `BATCH-9c6818ad-…, 760, Ghana, 2026-05-12` |
| `Shipment` | tms.shipments | shipment_identifier, transport_mode, delay_minutes, started_at, completed_at | `SHIP-DEMO-001, SEA_FREIGHT, 45` |

### Supply-Chain-Topologie (7 Stationen, 6 Hops)

| Seq | Node-Code | Node-Type | Region |
|---|---|---|---|
| 1 | BANANA_PLANTATION | PLANTATION | Africa |
| 2 | COLLECTION_CENTER | COLLECTION_CENTER | Africa |
| 3 | QUALITY_CONTROL | QUALITY_CONTROL | Africa |
| 4 | AFRICA_COLD_STORAGE | COLD_STORAGE | Africa |
| 5 | EUROPE_COLD_STORAGE | COLD_STORAGE | Europe |
| 6 | CENTRAL_WAREHOUSE | WAREHOUSE | Europe |
| 7 | RETAIL_STORE | RETAIL | Europe |

---

## 3. Beziehungen (Relationships)

### 13 Relationship-Typen

#### Stammdaten-Beziehungen (4)

```
(Supplier)-[:SUPPLIES]->(Product)
  Bedeutung: Lieferant produziert/liefert dieses Produkt
  Properties: –
  Beispiel:   SUP-103 (Tropical Banana Group) SUPPLIES BAN-101 (Cavendish Banana)

(Supplier)-[:DELIVERS_TO]->(SupplyChainNode)
  Bedeutung: Lieferant liefert an den Startknoten (BANANA_PLANTATION)
  Properties: –

(SupplyChainNode)-[:CONNECTED_TO]->(SupplyChainNode)
  Bedeutung: Zwei Stationen sind über eine Transportstrecke verbunden
  Properties: transport_mode (TRUCK / SEA_FREIGHT), typical_hours

(Carrier)-[:OPERATES_ON]->(SupplyChainNode)
  Bedeutung: Carrier ist auf einer bestimmten Strecke/Station aktiv
  Properties: transport_mode
```

#### Operative Beziehungen (9)

```
(Customer)-[:PLACED]->(Order)
  Bedeutung: Kunde hat Bestellung aufgegeben
  Properties: timestamp

(Customer)-[:RECEIVES_FROM]->(SupplyChainNode)
  Bedeutung: Kunde empfängt Lieferungen vom RETAIL_STORE

(Order)-[:CONTAINS]->(Product)
  Bedeutung: Bestellung enthält ein Produkt
  Properties: quantity, unit_price

(Order)-[:TRIGGERED]->(Batch)
  Bedeutung: Bestellung löste den Ernte-Batch aus

(Batch)-[:PROCESSED_AT]->(SupplyChainNode)
  Bedeutung: Batch wurde an dieser Station verarbeitet
  Properties: temperature (°C), status (COMPLETED / FAILED), processed_at

(Batch)-[:TRANSPORTED_VIA]->(Shipment)
  Bedeutung: Batch wurde mit diesem Shipment transportiert

(Shipment)-[:TRANSPORTED_BY]->(Carrier)
  Bedeutung: Transport wurde von diesem Carrier durchgeführt
  Properties: started_at, delay_minutes

(Shipment)-[:FROM]->(SupplyChainNode)
(Shipment)-[:TO]->(SupplyChainNode)
  Bedeutung: Quell- und Zielstation eines Transports

(Shipment)-[:DELIVERED_TO]->(Customer)
  Bedeutung: Finale Lieferung an den Kunden
  Properties: delivery_status, received_by, delivered_at
```

---

## 4. Graphmodell-Diagramm

```
[Supplier]──SUPPLIES──►[Product]◄──CONTAINS──[Order]◄──PLACED──[Customer]
    │                                             │                  ▲
    │                                         TRIGGERED         DELIVERED_TO
    │                                             ▼                  │
    └──DELIVERS_TO──►[Batch]──TRANSPORTED_VIA──►[Shipment]──TRANSPORTED_BY──►[Carrier]
                        │                          │
                   PROCESSED_AT               FROM / TO
                        ▼                          ▼
              [SupplyChainNode]◄──CONNECTED_TO──[SupplyChainNode]
                        ▲
                   OPERATES_ON
                        │
                    [Carrier]

Topologie-Pfad (6 CONNECTED_TO-Kanten = 6 Hops):
BANANA_PLANTATION ──TRUCK(4h)──► COLLECTION_CENTER
COLLECTION_CENTER ──TRUCK(2h)──► QUALITY_CONTROL
QUALITY_CONTROL   ──TRUCK(6h)──► AFRICA_COLD_STORAGE
AFRICA_COLD_STORAGE ──SEA_FREIGHT(240h)──► EUROPE_COLD_STORAGE
EUROPE_COLD_STORAGE ──TRUCK(8h)──► CENTRAL_WAREHOUSE
CENTRAL_WAREHOUSE ──TRUCK(3h)──► RETAIL_STORE
```

---

## 5. Produkt-Lieferanten-Zuordnung

Aus den ERP `ProductCreated`-Events abgeleitete `SUPPLIES`-Beziehungen:

| Produkt | Name | Lieferant |
|---|---|---|
| BAN-101 | Cavendish Banana | SUP-103 (Tropical Banana Group) |
| BAN-102 | Organic Banana | SUP-106 (Premium Banana Farms) |
| BAN-103 | Premium Banana | SUP-102 (Fresh Banana Export) |
| BAN-104 | Baby Banana | SUP-108 (Sunshine Produce) |
| BAN-105 | Fairtrade Banana | SUP-108 (Sunshine Produce) |
| BAN-106 | Export Banana | SUP-109 (Eco Banana Trading) |
| BAN-107 | Sweet Banana | SUP-107 (Green Harvest Export) |
| BAN-108 | Green Banana | SUP-106 (Premium Banana Farms) |
| BAN-109 | Yellow Banana | SUP-104 (Banana Kingdom) |
| BAN-110 | Tropical Banana | SUP-101 (Golden Banana Ltd) |

---

## 6. Beispiel-Cypher-Abfragen

### Q1: Vollständiger Weg eines Batches (6-Hop-Pfad)

```cypher
MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"})
      -[r:PROCESSED_AT]->(n:SupplyChainNode)
RETURN b.batch_identifier,
       n.sequence_order,
       n.node_name,
       r.temperature,
       r.status,
       r.processed_at
ORDER BY n.sequence_order
```

Erwartete Ausgabe: 7 Zeilen (PLANTATION → RETAIL_STORE), Temperatur je Station 11–14 °C.

### Q2: Supply-Chain-Topologie – kürzester Pfad (6 Hops)

```cypher
MATCH (start:SupplyChainNode {node_code: "BANANA_PLANTATION"}),
      (end:SupplyChainNode   {node_code: "RETAIL_STORE"}),
      path = shortestPath((start)-[:CONNECTED_TO*]->(end))
RETURN [n IN nodes(path) | n.node_name]              AS stationen,
       [r IN relationships(path) | r.transport_mode] AS transportmittel,
       reduce(h = 0, r IN relationships(path) | h + r.typical_hours) AS gesamtstunden,
       length(path) AS anzahl_hops
```

Erwartetes Ergebnis: `anzahl_hops = 6`, `gesamtstunden = 263`

### Q3: Carrier mit höchster Durchschnittsverzögerung (Seefracht)

```cypher
MATCH (car:Carrier)<-[:TRANSPORTED_BY]-(ship:Shipment {transport_mode: "SEA_FREIGHT"})
RETURN car.carrier_name,
       COUNT(ship)             AS anzahl_shipments,
       AVG(ship.delay_minutes) AS avg_verzoegerung_min,
       MAX(ship.delay_minutes) AS max_verzoegerung_min
ORDER BY avg_verzoegerung_min DESC
```

### Q4: Kühlketten-Verletzungen – Batches außerhalb 10–15 °C

```cypher
MATCH (b:Batch)-[r:PROCESSED_AT]->(n:SupplyChainNode)
WHERE r.temperature < 10.0 OR r.temperature > 15.0
RETURN b.batch_identifier,
       n.node_name,
       r.temperature AS temperatur_celsius,
       r.processed_at
ORDER BY r.processed_at DESC
```

Fachliche Bedeutung: Temperatur außerhalb 10–15 °C = Kühlkettenbruch → Qualitätsrisiko für BAN-108 (Green Banana).

### Q5: Lieferant → Produkt → Bestellung → Kunde

```cypher
MATCH (sup:Supplier)-[:SUPPLIES]->(p:Product)<-[:CONTAINS]-(o:Order)<-[:PLACED]-(cust:Customer)
RETURN sup.supplier_name,
       p.product_name,
       o.order_reference,
       o.delivery_priority,
       cust.customer_name
ORDER BY o.order_date
```

### Q6: Alle Carrier und ihre Seefracht-Routen

```cypher
MATCH (car:Carrier)<-[:TRANSPORTED_BY]-(ship:Shipment),
      (ship)-[:FROM]->(from:SupplyChainNode),
      (ship)-[:TO]->(to:SupplyChainNode)
RETURN car.carrier_name,
       from.node_name AS von,
       to.node_name   AS nach,
       ship.transport_mode,
       COUNT(ship)    AS fahrten
ORDER BY fahrten DESC
```

### Q7: Durchschnittliche Temperatur je Station (Kühlketten-Monitoring)

```cypher
MATCH (b:Batch)-[r:PROCESSED_AT]->(n:SupplyChainNode)
RETURN n.node_name,
       n.sequence_order,
       round(avg(r.temperature), 2) AS avg_temperatur,
       min(r.temperature)           AS min_temperatur,
       max(r.temperature)           AS max_temperatur
ORDER BY n.sequence_order
```

### Q8: Indirekte Lieferanten-Kunden-Beziehungen

```cypher
MATCH (sup:Supplier)-[:SUPPLIES]->(p:Product)<-[:CONTAINS]-(o:Order)<-[:PLACED]-(cust:Customer)
RETURN DISTINCT sup.supplier_name AS lieferant,
                cust.customer_name AS kunde,
                COUNT(o) AS bestellungen
ORDER BY bestellungen DESC
```

---

## 7. Neo4j vs. PostgreSQL: Vergleich Pfadabfrage

### Frage: Welchen Weg hat Batch BATCH-9c6818ad durch die Supply Chain genommen?

**SQL (PostgreSQL):**
```sql
SELECT n.node_name, np.temperature, np.processed_at
FROM   erp.batches           b
JOIN   wms.node_processings  np ON np.batch_reference = b.batch_identifier
JOIN   wms.supply_chain_nodes n  ON n.node_id = np.node_id
WHERE  b.batch_identifier = 'BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b'
ORDER  BY n.sequence_order;
-- 2 JOINs, überschaubar – skaliert aber schlecht bei variablen Traversaltiefen
```

**Cypher (Neo4j):**
```cypher
MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"})
      -[r:PROCESSED_AT]->(n:SupplyChainNode)
RETURN n.node_name, r.temperature ORDER BY n.sequence_order
-- nativer Graph-Traversal, keine JOINs, direkt auf Beziehungsstruktur optimiert
```

**Fazit:** Für einfache Pfade (3 JOINs) ist SQL noch konkurrenzfähig. Bei Netzwerkanalysen wie „Welche Lieferanten sind über mehrere Carrier mit welchen Kunden verbunden?" oder „Gibt es einen Alternativpfad, wenn AFRICA_COLD_STORAGE ausfällt?" skaliert Neo4j erheblich besser — SQL benötigt dann rekursive CTEs mit exponentiell wachsenden Laufzeiten.

---

## 8. Datenbankstruktur – Nachweis

```cypher
-- Alle Node-Typen mit Anzahl
MATCH (n) RETURN labels(n)[0] AS node_type, COUNT(n) AS count ORDER BY count DESC

-- Alle Relationship-Typen mit Anzahl
MATCH ()-[r]->() RETURN type(r) AS rel_type, COUNT(r) AS count ORDER BY count DESC

-- Alle SupplyChainNodes in Reihenfolge
MATCH (n:SupplyChainNode) RETURN n.node_name, n.node_type, n.region
ORDER BY n.sequence_order
```

Erwartete Node-Counts nach Skriptausführung:

| Node-Typ | Erwartete Anzahl |
|---|---|
| Supplier | 10 |
| Customer | 10 |
| Product | 10 |
| Carrier | 5 |
| SupplyChainNode | 7 |
| Order | 1 (Demo) |
| Batch | 1 (Demo) |
| Shipment | 1 (Demo) |
| **Gesamt** | **45** |
