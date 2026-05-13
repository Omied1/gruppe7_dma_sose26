# MongoDB Event-Modell – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-12

---

## 1. Warum MongoDB für Eventdaten?

In der Banana Supply Chain entstehen Ereignisströme mit **heterogener Struktur**: Ein `ShipmentPositionUpdated`-Event hat GPS-Koordinaten und Geschwindigkeit, ein `DeliveryCompleted`-Event hat einen Empfänger und Status, ein `NodeProcessed`-Event hat eine Temperatur. In einem relationalen Schema würden diese Events eine gemeinsame Tabelle mit vielen `NULL`-Spalten erzeugen oder in mehrere normalisierte Tabellen aufgeteilt werden, was Rekonstruktion des Lifecycles erschwert.

**Vorteile von MongoDB für diesen Use Case:**

| Vorteil | Anwendung in der Supply Chain |
|---|---|
| **Flexible Schemas** | Jeder Event-Typ hat eigene Felder ohne NULL-Overhead |
| **Eingebettete Dokumente** | Vollständiger Shipment-Lifecycle als ein Dokument |
| **Hohe Schreibleistung** | GPS-Updates kommen in kurzen Abständen |
| **Zeitbasierte Indizes** | TTL-Index für automatisches Ablaufen alter GPS-Events |
| **Schema-Evolution** | Neue Felder (z.B. Luftfeuchtigkeit) ohne Migration hinzufügbar |

---

## 2. Collections und Datenmodell

### 2.1 Collection: `shipment_events`

**Zweck:** Vollständiger Event-Lifecycle einer Sendung – von TransportStarted bis DeliveryCompleted.

**Struktur:** Ein Dokument pro `shipment_identifier`. Events werden in ein Array eingebettet, sodass der gesamte Verlauf eines Shipments in einem Dokument abrufbar ist.

**Beispiel-Dokument:**
```json
{
  "_id": "SHIP-bf5d4354-817b-41b3-ba5e-5e9001ccc31c",
  "shipment_identifier": "SHIP-bf5d4354-817b-41b3-ba5e-5e9001ccc31c",
  "cargo_product_reference": "ban-108",
  "canonical_product_code": "BAN-108",
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
    }
  ],
  "created_at": "2026-05-12T11:50:40.911326",
  "updated_at": "2026-05-12T14:30:00.000000"
}
```

**MongoDB-Indizes:**
```javascript
db.shipment_events.createIndex({ "shipment_identifier": 1 }, { unique: true })
db.shipment_events.createIndex({ "cargo_product_reference": 1 })
db.shipment_events.createIndex({ "source_node": 1, "target_node": 1 })
db.shipment_events.createIndex({ "transport_mode": 1 })
db.shipment_events.createIndex({ "created_at": 1 })
```

---

### 2.2 Collection: `node_events`

**Zweck:** Knotenverarbeitungsereignisse mit Temperaturhistorie – optimiert für Kühlketten-Monitoring.

**Struktur:** Ein Dokument pro `batch_reference + supply_chain_node`.

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
db.node_events.createIndex({ "batch_reference": 1 })
db.node_events.createIndex({ "supply_chain_node": 1 })
db.node_events.createIndex({ "temperature": 1 })
db.node_events.createIndex({ "temperature_within_range": 1 })
db.node_events.createIndex({ "processed_at": -1 })
```

---

### 2.3 Collection: `batch_tracking`

**Zweck:** Vollständige Bewegungshistorie eines Batches durch alle 7 Knoten der Supply Chain.

**Struktur:** Ein Dokument pro `batch_identifier` mit eingebetteter Knotenhistorie.

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
  "order_reference": "ORD-0f7dc974-b15d-434f-8a24-9e09f66ce508",
  "harvested_at": "2026-05-12T11:50:40.911207",
  "current_node": "EUROPE_COLD_STORAGE",
  "nodes_processed": [
    { "node": "BANANA_PLANTATION",   "temperature": 14.2, "status": "COMPLETED", "processed_at": "2026-05-12T11:50:40" },
    { "node": "COLLECTION_CENTER",   "temperature": 13.8, "status": "COMPLETED", "processed_at": "2026-05-12T12:10:00" },
    { "node": "QUALITY_CONTROL",     "temperature": 13.1, "status": "COMPLETED", "processed_at": "2026-05-12T12:30:00" },
    { "node": "AFRICA_COLD_STORAGE", "temperature": 12.57,"status": "COMPLETED", "processed_at": "2026-05-12T13:00:00" },
    { "node": "EUROPE_COLD_STORAGE", "temperature": 12.9, "status": "COMPLETED", "processed_at": "2026-05-13T08:00:00" }
  ],
  "temperature_stats": {
    "min": 12.57,
    "max": 14.2,
    "avg": 13.31,
    "all_within_range": true
  }
}
```

**MongoDB-Indizes:**
```javascript
db.batch_tracking.createIndex({ "batch_identifier": 1 }, { unique: true })
db.batch_tracking.createIndex({ "erp_product_code": 1 })
db.batch_tracking.createIndex({ "order_reference": 1 })
db.batch_tracking.createIndex({ "temperature_stats.all_within_range": 1 })
```

---

### 2.4 Collection: `order_events`

**Zweck:** Vollständiger Order-Lifecycle vom Eingang bis zur Lieferung.

**Beispiel-Dokument:**
```json
{
  "_id": "ORD-0f7dc974-b15d-434f-8a24-9e09f66ce508",
  "order_reference": "ORD-0f7dc974-b15d-434f-8a24-9e09f66ce508",
  "customer_number": "CUST-109",
  "customer_name": "AUCHAN",
  "delivery_priority": "NORMAL",
  "items": [
    {
      "product_code": "BAN-108",
      "description": "Green Banana",
      "quantity": 760,
      "unit_price": 3.09,
      "total_value": 2348.40
    }
  ],
  "status": "DELIVERED",
  "created_at": "2026-05-12T11:50:40",
  "delivered_at": "2026-05-14T09:30:00",
  "batch_references": ["BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"],
  "final_delivery_status": "SUCCESSFUL"
}
```

---

## 3. Abgrenzung: MongoDB vs. PostgreSQL für Eventdaten

| Aspekt | PostgreSQL (tms.shipments etc.) | MongoDB (shipment_events) |
|---|---|---|
| **Primärnutzung** | Strukturierte Abfragen, JOINs, FK-Integrität | Vollständiger Event-Stream, Lifecycle-Ansicht |
| **Struktur** | Normalisiert (6 Tabellen für TMS) | Denormalisiert (1 Dokument = 1 Shipment-Lifecycle) |
| **Abfrage** | `SELECT ... JOIN ... WHERE` | `db.shipment_events.findOne({shipment_identifier: "SHIP-..."})` |
| **Aktualisierung** | UPDATE einzelne Zeilen | `$push` für neue Events in Array |
| **Kühlketten-Check** | Multi-Table-Join nötig | Direkt aus `temperature_stats.all_within_range` |

Beide Systeme **ergänzen sich**: PostgreSQL bietet relationale Integrität und normalisierte Strukturen; MongoDB bietet den vollständigen Event-Kontext in einem einzigen Dokument.
