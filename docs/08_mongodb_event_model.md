# MongoDB Event-Modell – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-14

---

## 1. Warum MongoDB für Eventdaten?

In der Banana Supply Chain entstehen Ereignisströme mit **heterogener Struktur**: Ein `ShipmentPositionUpdated`-Event hat GPS-Koordinaten und Geschwindigkeit, ein `DeliveryCompleted`-Event hat einen Empfänger und Status, ein `NodeProcessed`-Event hat eine Temperatur. In einem relationalen Schema würden diese Events eine gemeinsame Tabelle mit vielen `NULL`-Spalten erzeugen oder in mehrere normalisierte Tabellen aufgeteilt werden, was die Rekonstruktion des Lifecycles erschwert.

**Vorteile von MongoDB für diesen Use Case:**

| Vorteil | Anwendung in der Supply Chain |
|---|---|
| **Flexible Schemas** | Jeder Event-Typ hat eigene Felder ohne NULL-Overhead |
| **Eingebettete Dokumente** | Vollständiger Shipment-Lifecycle als ein Dokument abrufbar |
| **Hohe Schreibleistung** | GPS-Updates kommen in kurzen Abständen (real: alle 30 s) |
| **TTL-Index** | Automatisches Ablaufen von Lifecycle-Dokumenten nach 90 Tagen |
| **Schema-Evolution** | Neue Felder (z.B. Luftfeuchtigkeit) ohne Migration hinzufügbar |

---

## 2. Collections und Datenmodell

### 2.1 Collection: `shipment_events`

**Zweck:** Vollständiger Event-Lifecycle einer Sendung – von `TransportStarted` bis `DeliveryCompleted`. Das Lifecycle-Modell speichert alle Events eines Shipments in einem einzigen Dokument als eingebettetes Array.

**Struktur:** Ein Dokument pro `shipment_identifier`. Folge-Events (`ShipmentPositionUpdated`, `TransportCompleted`, `DeliveryCompleted`) werden per `$push` in das `events[]`-Array eingebettet.

**Beispiel-Dokument:**
```json
{
  "_id": "SHIP-bf5d4354-817b-41b3-ba5e-5e9001ccc31c",
  "shipment_identifier": "SHIP-bf5d4354-817b-41b3-ba5e-5e9001ccc31c",
  "cargo_product_reference": "BAN-108",
  "source_node": "AFRICA_COLD_STORAGE",
  "target_node": "EUROPE_COLD_STORAGE",
  "transport_mode": "SEA_FREIGHT",
  "carrier": {
    "carrier_id": "CAR-104",
    "carrier_name": "DB Schenker"
  },
  "estimated_arrival": "2026-05-13T01:50:40.911324",
  "started_at": "2026-05-12T11:50:40.911326",
  "completed_at": "2026-05-12T14:30:00.000000",
  "delivery_status": "SUCCESSFUL",
  "delay_minutes": 45,
  "events": [
    {
      "event_type": "TransportStarted",
      "timestamp": "2026-05-12T11:50:40.911326"
    },
    {
      "event_type": "ShipmentPositionUpdated",
      "coordinates": { "latitude": -13.286561, "longitude": 174.034529 },
      "container_temperature": 13.39,
      "speed_kmh": 59.85,
      "timestamp": "2026-05-12T12:00:00.000000"
    },
    {
      "event_type": "TransportCompleted",
      "arrival_node": "EUROPE_COLD_STORAGE",
      "delay_minutes": 45,
      "timestamp": "2026-05-12T14:30:00.000000"
    },
    {
      "event_type": "DeliveryCompleted",
      "delivery_status": "SUCCESSFUL",
      "received_by": "EMP-7",
      "timestamp": "2026-05-12T14:35:00.000000"
    }
  ],
  "created_at": "2026-05-12T11:50:40.911326",
  "updated_at": "2026-05-12T14:35:00.000000"
}
```

**MongoDB-Indizes:**
```javascript
// Eindeutigkeit pro Shipment (Lifecycle-Modell: 1 Dokument = 1 Shipment)
db.shipment_events.createIndex({ "shipment_identifier": 1 }, { unique: true })

// Performance-Indizes für häufige Filterabfragen
db.shipment_events.createIndex({ "cargo_product_reference": 1 })
db.shipment_events.createIndex({ "source_node": 1, "target_node": 1 })
db.shipment_events.createIndex({ "transport_mode": 1 })
db.shipment_events.createIndex({ "delivery_status": 1 })

// TTL-Index: Lifecycle-Dokumente laufen 90 Tage nach Transport-Start ab.
// Begründung: GPS-Spuren und Temperaturdaten werden für Kühlkettenanalysen
// 90 Tage vorgehalten; dauerhafte KPIs werden vorher ins DWH (PostgreSQL) überführt.
db.shipment_events.createIndex(
  { "created_at": 1 },
  { expireAfterSeconds: 7776000, name: "ttl_shipment_lifecycle" }
)
```

**Warum Lifecycle-Modell (embedded events[]) statt Flat-Dokumente?**

| Kriterium | Flat-Modell (1 Event = 1 Dokument) | Lifecycle-Modell (1 Shipment = 1 Dokument) |
|---|---|---|
| Vollständiger Verlauf abrufen | Mehrere Queries nötig | `findOne({shipment_identifier: "SHIP-..."})` |
| Kühlketten-Check über alle GPS-Positionen | Aggregation über N Dokumente | Direkt aus eingebettetem `events[]`-Array |
| Neue Event-Felder hinzufügen | Kein Impact auf andere Events | Kein Impact, Array ist heterogen |
| `$push` für neue Events | N/A | Atomare Erweiterung ohne Lock auf anderen Collections |

---

### 2.2 Collection: `node_events`

**Zweck:** Knotenverarbeitungsereignisse mit Temperaturhistorie – optimiert für Kühlketten-Monitoring. Liefert für jeden Batch-Knoten-Durchlauf sofort abrufbare Quality-Flags, ohne Multi-Table-JOINs.

**Struktur:** Ein Dokument pro `(batch_reference, supply_chain_node)`-Kombination. Jeder der 6 WMS-Knoten erzeugt genau ein Dokument pro Batch.

**Beispiel-Dokument:**
```json
{
  "_id": "BATCH-9c6818ad_AFRICA_COLD_STORAGE",
  "batch_reference": "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b",
  "supply_chain_node": "AFRICA_COLD_STORAGE",
  "sku": "BAN_108",
  "canonical_product_code": "BAN-108",
  "temperature": 12.57,
  "temperature_within_range": true,
  "status": "COMPLETED",
  "processed_at": "2026-05-12T11:50:40.911318",
  "quality_flags": {
    "temperature_ok": true,
    "min_allowed": 10.0,
    "max_allowed": 15.0
  }
}
```

**MongoDB-Indizes:**
```javascript
// Eindeutigkeit pro batch+node-Kombination (1 NodeProcessed-Event pro Batch und Knoten)
db.node_events.createIndex(
  { "batch_reference": 1, "supply_chain_node": 1 },
  { unique: true, name: "uq_node_event" }
)

// Performance-Indizes für Kühlketten-Abfragen
db.node_events.createIndex({ "batch_reference": 1 })
db.node_events.createIndex({ "supply_chain_node": 1 })
db.node_events.createIndex({ "temperature": 1 })
db.node_events.createIndex({ "temperature_within_range": 1 })
db.node_events.createIndex({ "processed_at": -1 })
```

**Fachliche Begründung für `temperature_within_range` und `quality_flags`:**  
Der Sollbereich für Cavendish-Bananen beträgt 10–15 °C. Das Feld `temperature_within_range: true/false` ermöglicht direkte Filterabfragen ohne Bereichsvergleich:  
`db.node_events.find({ temperature_within_range: false })` → alle Kühlkettenbrüche auf einen Blick.

---

### 2.3 Collection: `batch_tracking`

**Zweck:** Vollständige Bewegungshistorie eines Batches durch alle WMS-Knoten der Supply Chain. Zentrales Dokument für Batch-Lifecycle-Übersicht.

**Struktur:** Ein Dokument pro `batch_identifier` mit eingebetteter Knotenhistorie als Array vollständiger Knotenobjekte.

**Beispiel-Dokument:**
```json
{
  "_id": "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b",
  "batch_identifier": "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b",
  "erp_product_code": "BAN-108",
  "wms_sku": "BAN_108",
  "tms_product_reference": "ban-108",
  "origin_country": "Ghana",
  "quantity": 760,
  "harvested_at": "2026-05-12T11:50:40.911207",
  "current_node": "EUROPE_COLD_STORAGE",
  "nodes_processed": [
    { "node": "BANANA_PLANTATION",   "temperature": 14.2,  "status": "COMPLETED", "processed_at": "2026-05-12T11:50:40" },
    { "node": "COLLECTION_CENTER",   "temperature": 13.8,  "status": "COMPLETED", "processed_at": "2026-05-12T12:10:00" },
    { "node": "QUALITY_CONTROL",     "temperature": 13.1,  "status": "COMPLETED", "processed_at": "2026-05-12T12:30:00" },
    { "node": "AFRICA_COLD_STORAGE", "temperature": 12.57, "status": "COMPLETED", "processed_at": "2026-05-12T13:00:00" },
    { "node": "EUROPE_COLD_STORAGE", "temperature": 12.9,  "status": "COMPLETED", "processed_at": "2026-05-13T08:00:00" }
  ],
  "updated_at": "2026-05-13T08:00:00"
}
```

**MongoDB-Indizes:**
```javascript
db.batch_tracking.createIndex({ "batch_identifier": 1 }, { unique: true })
db.batch_tracking.createIndex({ "erp_product_code": 1 })
db.batch_tracking.createIndex({ "nodes_processed.node": 1 })
```

**Warum vollständige Knotenobjekte statt String-Array?**  
`$addToSet` mit dem vollen Knotenobjekt `{node, temperature, status, processed_at}` ist idempotent und speichert alle fachlich relevanten Felder pro Knoten. Ein reines String-Array `["AFRICA_COLD_STORAGE", ...]` enthält keine Temperaturdaten – damit wäre die Kühlketten-Auswertung über `batch_tracking` nicht möglich.

---

### 2.4 Collection: `order_events`

**Zweck:** Vollständige Order-Lifecycle-Daten vom Eingang bis zur Lieferung. Speichert den `OrderCreated`-Event als Basis-Dokument mit eingebetteten Customer- und Item-Informationen.

**Beispiel-Dokument:**
```json
{
  "_id": "ORD-0f7dc974-b15d-434f-8a24-9e09f66ce508",
  "event_type": "OrderCreated",
  "order_reference": "ORD-0f7dc974-b15d-434f-8a24-9e09f66ce508",
  "customer": {
    "customer_number": "CUST-109",
    "customer_name": "AUCHAN",
    "city": "Frankfurt",
    "country": "Germany"
  },
  "items": [
    {
      "product_code": "BAN-108",
      "quantity": 760,
      "unit_price": 3.09
    }
  ],
  "delivery_priority": "NORMAL",
  "timestamp": "2026-05-12T11:50:40"
}
```

**MongoDB-Indizes:**
```javascript
db.order_events.createIndex({ "order_reference": 1 }, { unique: true })
db.order_events.createIndex({ "customer.customer_number": 1 })
db.order_events.createIndex({ "items.product_code": 1 })
db.order_events.createIndex({ "delivery_priority": 1 })
```

---

## 3. Collections-Übersicht

| Collection | Granularität | Dokumente (10 Iter.) | Primärer Use Case | TTL |
|---|---|---|---|---|
| `shipment_events` | 1 pro `shipment_identifier` | 60 | Vollständiger Transportlebenszyklus inkl. GPS-Spuren | 90 Tage |
| `node_events` | 1 pro `(batch, knoten)` | 60 | Kühlketten-Monitoring pro Verarbeitungsstation | keiner |
| `batch_tracking` | 1 pro `batch_identifier` | 10 | Batch-Durchlauf durch alle WMS-Knoten | keiner |
| `order_events` | 1 pro `order_reference` | 10 | Order-Snapshot mit Customer + Items | keiner |

---

## 4. Abgrenzung: MongoDB vs. PostgreSQL für Eventdaten

| Aspekt | PostgreSQL (tms.shipments etc.) | MongoDB (shipment_events) |
|---|---|---|
| **Primärnutzung** | Strukturierte Abfragen, JOINs, FK-Integrität | Vollständiger Event-Stream, Lifecycle-Ansicht |
| **Struktur** | Normalisiert (6 Tabellen für TMS) | Denormalisiert (1 Dokument = 1 Shipment-Lifecycle) |
| **Abfrage** | `SELECT s.* FROM tms.shipments JOIN ... WHERE` | `db.shipment_events.findOne({shipment_identifier: "SHIP-..."})` |
| **Neue Events** | `INSERT INTO tms.transport_completions` | `$push` in `events[]`-Array des Shipment-Dokuments |
| **Kühlketten-Check** | Multi-Table-Join nötig | Direkt aus `quality_flags.temperature_ok` in `node_events` |
| **Datenhaltung** | Dauerhaft (ACID, archivfähig) | Operativ (TTL 90 Tage für Shipment-Lifecycle) |

Beide Systeme **ergänzen sich**: PostgreSQL bietet relationale Integrität und normalisierte Strukturen für DWH-ETL und KPI-Berechnung; MongoDB bietet den vollständigen Event-Kontext in einem einzigen Dokument für Monitoring und Echtzeitabfragen.

---

## 5. Prüfqueries (MongoDB Shell)

```javascript
// Nachweis: Anzahl Dokumente je Collection
db.shipment_events.countDocuments()  // Erwartung: 60 (1 pro Shipment)
db.node_events.countDocuments()      // Erwartung: 60 (6 Knoten × 10 Iterationen)
db.batch_tracking.countDocuments()   // Erwartung: 10 (1 pro Batch)
db.order_events.countDocuments()     // Erwartung: 10 (1 pro Order)

// Lifecycle-Nachweis: Vollständiger Shipment-Verlauf in einem Dokument
db.shipment_events.findOne(
  {},
  { shipment_identifier: 1, "events.event_type": 1, delivery_status: 1 }
)
// Erwartung: events[]-Array enthält TransportStarted + ShipmentPositionUpdated(n) + TransportCompleted

// TTL-Index prüfen
db.shipment_events.getIndexes()
// Erwartung: Index mit name "ttl_shipment_lifecycle" und expireAfterSeconds: 7776000

// Kühlketten-Verletzungen über alle Knoten
db.node_events.find({ "temperature_within_range": false }).count()
// Erwartung: 0 (alle generierten Events liegen im Sollbereich 10–15 °C)

// batch_tracking: Vollständige Knotenobjekte prüfen
db.batch_tracking.findOne(
  {},
  { batch_identifier: 1, "nodes_processed.node": 1, "nodes_processed.temperature": 1 }
)
// Erwartung: nodes_processed enthält Objekte mit {node, temperature, status, processed_at},
//            KEINE reinen Strings

// Abfrage: Alle Shipments mit Verzögerung > 60 Minuten
db.shipment_events.find(
  { delay_minutes: { $gt: 60 } },
  { shipment_identifier: 1, source_node: 1, target_node: 1, delay_minutes: 1 }
).sort({ delay_minutes: -1 })

// Abfrage: Alle Batches, die AFRICA_COLD_STORAGE mit Temperatur < 12 °C passiert haben
db.node_events.find(
  { supply_chain_node: "AFRICA_COLD_STORAGE", temperature: { $lt: 12.0 } },
  { batch_reference: 1, temperature: 1, processed_at: 1 }
)
```
