# ETL-Konzept – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-15

---

## 1. Übersicht: ETL-Architektur

Der ETL-Prozess (Extract, Transform, Load) verbindet die JSON-basierten Quellsysteme (ERP, WMS, TMS) mit den Zielsystemen (PostgreSQL, MongoDB, Redis, Neo4j, MinIO). Das DWH-Schema wird in einem separaten ETL-Schritt aus den operativen PostgreSQL-Schemas befüllt.

```
                 EXTRACT                    TRANSFORM                    LOAD
                    │                          │                           │
  shared/erp/  ─────┤                          │                           │
  shared/wms/  ──►  │  JSON-Reader  ──►  Harmonisierung  ──►  PostgreSQL (erp/wms/tms)
  shared/tms/  ─────┤  (Python)          MDM-Auflösung        MongoDB (events)
                    │                   Validierung            Redis (realtime)
                    │                   Typkonvertierung       Neo4j (graph)
                    │                                          MinIO (docs)
                    │
  Operative DBs ────┤
  (PostgreSQL)  ──► │  SQL-ETL       ──►  Aggregation    ──►  PostgreSQL (dwh)
                         (Teil 2)         Denormalisierung
```

---

## 2. ETL-Phase 1: JSON → Operative Systeme

### 2.1 Extract (E)

**Quellen:** JSON-Dateien in `shared/erp/`, `shared/wms/`, `shared/tms/`

**Strategie:**
- **Iteration 000** (Masterdata-Präfix): Stammdaten-Events zuerst laden
- **Iterationen 001-010**: Operative Events in chronologischer Reihenfolge

```python
import json, os, glob

def extract_events(base_dir: str, system: str) -> list[dict]:
    """Liest alle JSON-Events eines Systems. Stammdaten (iteration_000) zuerst."""
    pattern = os.path.join(base_dir, system, "*.json")
    files   = sorted(glob.glob(pattern))  # Alphabetisch → 000 vor 001 etc.
    events  = []
    for f in files:
        with open(f) as fp:
            events.append(json.load(fp))
    return events
```

### 2.2 Transform (T)

**Schritt 1: Schlüsselharmonisierung via ETL**

Die Normalisierung aller Produktschlüssel auf das kanonische ERP-Format (`BAN-NNN`) findet direkt im ETL-Skript statt — nicht über einen separaten MDM-Ladeschritt. Die Funktion wird auf jeden eingehenden Schlüssel angewendet, bevor er in eine Zieldatenbank geschrieben wird:

```python
def normalize_key(key: str) -> str:
    """Normalisiert Produktschlüssel auf ERP-Format, unabhängig vom Quellsystem."""
    return key.strip().lower().replace("_", "-").upper()
    # BAN_101 (WMS) → ban-101 → BAN-101  ✓
    # ban-101 (TMS) → ban-101 → BAN-101  ✓
    # BAN-101 (ERP) → ban-101 → BAN-101  ✓
```

Die MDM-Tabellen (`mdm.golden_records`, `mdm.source_mappings`) dokumentieren die Mapping-Regeln als formales Referenzmodell und stellen die SQL-Funktion `mdm.resolve_canonical_key()` für Laufzeit-Auflösungen bereit. Die Inkonsistenz der Quellschlüssel bleibt ausschließlich in den JSON-Quelldateien erhalten.

**Schritt 2: Typkonvertierung**
```python
from datetime import datetime

def parse_timestamp(ts: str) -> datetime:
    """ISO-8601 → Python datetime."""
    return datetime.fromisoformat(ts)

def safe_float(val) -> float | None:
    """Sicherer Float-Cast mit NULL-Handling."""
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None
```

**Schritt 3: Qualitätsvalidierung**
```python
def validate_event(event: dict) -> tuple[bool, list[str]]:
    """Validiert ein Event gegen Qualitätsregeln. Gibt (ok, fehler_liste) zurück."""
    errors = []
    et = event.get("event_type", "")

    if et == "NodeProcessed":
        temp = safe_float(event.get("temperature"))
        if temp is None:
            errors.append("VQ-03: temperature fehlt")
        elif not (10.0 <= temp <= 15.0):
            errors.append(f"PQ-03: temperature {temp}°C außerhalb Kühlkette [10-15°C]")

    if et == "OrderCreated":
        for item in event.get("items", []):
            if item.get("quantity", 0) <= 0:
                errors.append(f"PQ-01: quantity {item['quantity']} <= 0")
            if not (1.50 <= item.get("unit_price", 0) <= 5.00):
                errors.append(f"PQ-02: unit_price {item['unit_price']} außerhalb [1.50, 5.00]")

    return len(errors) == 0, errors
```

### 2.3 Load-Reihenfolge (wichtig wegen FK-Abhängigkeiten)

```
Schritt 1: ERP-Stammdaten (erp.suppliers, erp.customers, erp.products)
           → SupplierCreated, CustomerCreated, ProductCreated
           → normalize_key() auf product_code: BAN-101 bleibt BAN-101
           → Repair-Pass: supplier_id-FK wird nachträglich gesetzt (alphabetische
             Verarbeitungsreihenfolge erzwingt 2-Phasen-Insert)

Schritt 2: WMS-Stammdaten (wms.warehouse_skus)
           → WarehouseSKUCreated
           → sku bleibt im WMS-Format (BAN_101); erp_product_code wird normalisiert
           → wms.supply_chain_nodes ist DDL-vorbefüllt (INSERT IN sql/03); kein ETL-Schritt nötig

Schritt 3: TMS-Stammdaten (tms.carriers, tms.transport_product_references)
           → CarrierCreated, TransportProductReferenceCreated
           → normalize_key() auf erp_product_code: ban-101 → BAN-101

Schritt 4: ERP-Bewegungsdaten (erp.orders, erp.order_items, erp.batches)
           → OrderCreated, BatchHarvested
           → FK-Abhängigkeit von Schritt 1 (customer_id, product_id)

Schritt 5: WMS-Eventdaten (wms.node_processings)
           → NodeProcessed
           → FK zu wms.supply_chain_nodes (node_code → node_id)
           → Cross-Schema-Ref: batch_reference → erp.batches.batch_identifier (kein FK,
             Integrität via ETL-Validierung sichergestellt)

Schritt 6: TMS-Eventdaten (tms.shipments, tms.shipment_positions,
                           tms.transport_completions, tms.deliveries)
           → TransportStarted zuerst (erzeugt shipments); Folge-Events danach
           → FK zu tms.carriers (carrier_id)
           → Reihenfolge-Sortierung innerhalb TMS-Events nötig (tms_sorted)

Schritt 7: MDM (mdm.golden_records, mdm.source_mappings)
           → Läuft nach Schritt 1–3, da erp.products vollständig befüllt sein muss
           → 5 Entity-Typen: PRODUCT (3 Quellsysteme), CUSTOMER, SUPPLIER, CARRIER,
             SUPPLY_CHAIN_NODE

Schritt 8: MongoDB – Event-Collections (parallel zu Schritt 4–6)
Schritt 9: Redis – Echtzeitzustände (aus TMS-Events)
Schritt 10: Neo4j – Graph-Knoten und Beziehungen (BatchHarvested → product_code auf Batch,
            TransportStarted → TRANSPORTED_VIA, DeliveryCompleted → DELIVERED_TO)
Schritt 11: MinIO – Dokument-Trigger (TransportStarted → Lieferschein, DeliveryCompleted → Rechnung)
```

---

## 3. ETL-Phase 2: Operative Schemas → DWH

> **Wichtig:** Diese Phase findet **separat** statt und entspricht dem ETL-Konzept des Data Warehouses. Die operativen ERP/WMS/TMS-Schemas sind **Quellsysteme** des DWH.

```sql
-- ETL-Insert in dwh.fact_fulfillment
-- Hinweis: erp.batches hat KEINEN order_id-FK (wurde entfernt, da BatchHarvested-Events
-- keine Bestellreferenz enthalten). Batches werden über product_id mit Orders verknüpft.
-- Vollständige CTE-basierte Implementierung: bananasupplychain/etl_dwh.py
INSERT INTO dwh.fact_fulfillment (
    customer_sk, product_sk, supplier_sk, carrier_sk,
    destination_node_sk, order_date_sk, delivery_date_sk, delivery_status_sk,
    order_reference, shipment_identifier,
    quantity, unit_price, total_value, delay_minutes, avg_temperature,
    delivery_priority_code
)
SELECT
    dc.customer_sk,
    dp.product_sk,
    ds.supplier_sk,
    dca.carrier_sk,
    dn.node_sk,
    TO_CHAR(o.order_timestamp, 'YYYYMMDD')::INT,
    TO_CHAR(COALESCE(d.delivered_at, s.started_at), 'YYYYMMDD')::INT,
    dds.status_sk,
    o.order_reference,
    s.shipment_identifier,
    oi.quantity,
    oi.unit_price,
    (oi.quantity * oi.unit_price)          AS total_value,
    COALESCE(tc.delay_minutes, 0)          AS delay_minutes,
    avg_temps.avg_temp                     AS avg_temperature,
    o.delivery_priority
FROM erp.orders               o
JOIN erp.order_items          oi  ON oi.order_id    = o.order_id
JOIN erp.products             p   ON p.product_id   = oi.product_id
JOIN erp.customers            cu  ON cu.customer_id = o.customer_id
JOIN erp.suppliers            sup ON sup.supplier_id = p.supplier_id
-- Shipments via normalisiertem Produktcode (kein order_id-FK in erp.batches)
JOIN tms.shipments            s   ON s.cargo_product_reference = p.product_code
LEFT JOIN tms.carriers        ca  ON ca.carrier_id  = s.carrier_id
LEFT JOIN tms.transport_completions tc ON tc.shipment_id = s.shipment_id
LEFT JOIN tms.deliveries      d   ON d.shipment_id  = s.shipment_id
-- Ø-Temperatur pro Produkt über alle Batches und Knotenverarbeitungen
LEFT JOIN (
    SELECT p2.product_code, ROUND(AVG(np.temperature)::NUMERIC, 2) AS avg_temp
    FROM   erp.batches             b
    JOIN   erp.products            p2 ON p2.product_id = b.product_id
    LEFT JOIN wms.node_processings np ON np.batch_reference = b.batch_identifier
    WHERE  np.temperature IS NOT NULL
    GROUP  BY p2.product_code
) avg_temps ON avg_temps.product_code = p.product_code
-- Surrogate Key Lookups
JOIN dwh.dim_customer         dc  ON dc.customer_number = cu.customer_number
JOIN dwh.dim_product          dp  ON dp.product_code    = p.product_code
JOIN dwh.dim_supplier         ds  ON ds.supplier_code   = sup.supplier_code
LEFT JOIN dwh.dim_carrier     dca ON dca.carrier_code   = ca.carrier_code
LEFT JOIN dwh.dim_supply_chain_node dn ON dn.node_code  = s.target_node
JOIN dwh.dim_delivery_status  dds ON dds.status_code    = COALESCE(d.delivery_status, 'IN_TRANSIT')
WHERE  d.delivery_status IS NOT NULL;  -- Nur abgeschlossene Fulfillments
```

---

## 4. ETL-Mapping-Tabelle

| Quelle | Eventtyp / Tabelle | Transformation | Zielsystem | Begründung |
|---|---|---|---|---|
| `shared/erp/` | `SupplierCreated` | `normalize_key()` auf supplier_code | PostgreSQL `erp.suppliers` | Stammdaten, referenzielle Integrität |
| `shared/erp/` | `CustomerCreated` | `normalize_key()` auf customer_number | PostgreSQL `erp.customers` | Stammdaten, referenzielle Integrität |
| `shared/erp/` | `ProductCreated` | `normalize_key()` auf product_code, supplier_reference → FK | PostgreSQL `erp.products` | Stammdaten mit FK |
| `shared/wms/` | `WarehouseSKUCreated` | `normalize_key()`: `BAN_101` → `BAN-101` | PostgreSQL `wms.warehouse_skus` | WMS-Stammdaten (Inkonsistenz wird im ETL aufgelöst) |
| `shared/tms/` | `CarrierCreated` | `normalize_key()` auf carrier_id | PostgreSQL `tms.carriers` | TMS-Stammdaten |
| `shared/tms/` | `TransportProductReferenceCreated` | `normalize_key()`: `ban-101` → `BAN-101` | PostgreSQL `tms.transport_product_references` | TMS-Stammdaten (Inkonsistenz wird im ETL aufgelöst) |
| `shared/erp/` | `OrderCreated` | items[] normalisieren, customer-Objekt → FK auflösen | PostgreSQL `erp.orders` + `erp.order_items` | Transaktionale Bewegungsdaten |
| `shared/erp/` | `BatchHarvested` | Timestamp parsen, `normalize_key()` auf product_code → product_id FK | PostgreSQL `erp.batches` | Operative Bewegungsdaten (kein order_id-FK; Batch-Order-Verknüpfung läuft über product_id) |
| `shared/wms/` | `NodeProcessed` | supply_chain_node → node_id FK, Temperatur validieren | PostgreSQL `wms.node_processings` + MongoDB `node_events` | Knotenverarbeitung + Event-Archiv |
| `shared/tms/` | `TransportStarted` | `normalize_key()` auf cargo_product_reference, carrier-Objekt → carrier_id | PostgreSQL `tms.shipments` + MongoDB `shipment_events` + Neo4j | Strukturiert + Event-Stream + Graph |
| `shared/tms/` | `ShipmentPositionUpdated` | Koordinaten validieren, Temperatur prüfen | **Redis** `shipment:position:*` (aktuell) + MongoDB `shipment_events` (Archiv) | Echtzeit + Persistenz |
| `shared/tms/` | `TransportCompleted` | delay_minutes validieren (≥ 0) | PostgreSQL `tms.transport_completions` + MongoDB `shipment_events.$push` | Abschluss-Event |
| `shared/tms/` | `DeliveryCompleted` | delivery_status validieren, Redis-Status aktualisieren | PostgreSQL `tms.deliveries` + MongoDB + Redis (Status-Update) | Finales Event |
| Dokument-Trigger | Nach DeliveryCompleted | Rechnung generieren (PDF) | MinIO `invoices/` | Dokumentenspeicher |
| Dokument-Trigger | Nach TransportStarted | Lieferschein generieren (PDF) | MinIO `delivery-notes/` | Dokumentenspeicher |
| Dokument-Trigger | Nach SEA_FREIGHT TransportStarted | Frachtbrief generieren | MinIO `transport-docs/` | Spezifisch für Seefracht |
| PostgreSQL operative Schemas | `erp.*` + `wms.*` + `tms.*` | Aggregation, SK-Lookup, Denormalisierung | PostgreSQL `dwh.fact_fulfillment` | Analytics-DWH (nur via ETL) |

---

## 5. Feld-Ebene-Mapping (Quell-Feld → Transformation → Ziel-Spalte)

Die folgende Tabelle zeigt die Transformation auf Feldebene für die wichtigsten Eventtypen.

### 5.1 ERP: SupplierCreated

| Quell-Feld (JSON) | Typ (Quelle) | Transformation | Ziel-Tabelle | Ziel-Spalte | Typ (Ziel) |
|---|---|---|---|---|---|
| `supplier_code` | string | keine | `erp.suppliers` | `supplier_code` | VARCHAR(20) PK |
| `supplier_name` | string | keine | `erp.suppliers` | `supplier_name` | VARCHAR(200) |
| `country` | string | keine (optional) | `erp.suppliers` | `country` | VARCHAR(100) |
| `timestamp` | ISO-8601 string | `datetime.fromisoformat()` | `erp.suppliers` | `event_timestamp` | TIMESTAMPTZ |

### 5.2 WMS: WarehouseSKUCreated

| Quell-Feld (JSON) | Typ (Quelle) | Transformation | Ziel-Tabelle | Ziel-Spalte | Typ (Ziel) |
|---|---|---|---|---|---|
| `sku` | string (`BAN_101`) | **keine** – WMS-Format beibehalten | `wms.warehouse_skus` | `sku` | VARCHAR(50) PK |
| `erp_product_code` | string (`BAN-101`) | `normalize_key()` → `BAN-101` | `wms.warehouse_skus` | `erp_product_code` | VARCHAR(20) |
| `timestamp` | ISO-8601 string | `datetime.fromisoformat()` | `wms.warehouse_skus` | `event_timestamp` | TIMESTAMPTZ |

> **Designentscheidung:** `sku` behält das WMS-Format mit Unterstrichen (`BAN_101`), weil WMS-interne Referenzen (z.B. in `NodeProcessed`-Events) dieses Format verwenden. Die Harmonisierung mit dem ERP-Format erfolgt ausschließlich über `mdm.source_mappings`.

### 5.3 WMS: NodeProcessed

| Quell-Feld (JSON) | Typ (Quelle) | Transformation | Ziel-Tabelle | Ziel-Spalte | Typ (Ziel) |
|---|---|---|---|---|---|
| `supply_chain_node` | string (`BANANA_PLANTATION`) | FK-Lookup: `wms.supply_chain_nodes.node_code` → `node_id` | `wms.node_processings` | `node_id` | INT FK |
| `batch_reference` | string (`BATCH-...`) | keine | `wms.node_processings` | `batch_reference` | VARCHAR(100) |
| `sku` | string (`BAN_108`) | **keine** – WMS-Format beibehalten | `wms.node_processings` | `sku` | VARCHAR(50) |
| `temperature` | number | `safe_float()` + Plausibilitätsprüfung [10–15 °C] | `wms.node_processings` | `temperature` | NUMERIC(5,2) |
| `status` | string | keine | `wms.node_processings` | `status` | VARCHAR(50) |
| `timestamp` | ISO-8601 string | `datetime.fromisoformat()` | `wms.node_processings` | `processed_at` | TIMESTAMPTZ |

### 5.4 TMS: TransportStarted

| Quell-Feld (JSON) | Typ (Quelle) | Transformation | Ziel-Tabelle | Ziel-Spalte | Typ (Ziel) |
|---|---|---|---|---|---|
| `shipment_identifier` | string | keine | `tms.shipments` | `shipment_identifier` | VARCHAR(100) PK |
| `carrier.carrier_id` | string (`CAR-102`) | FK-Lookup: `tms.carriers.carrier_code` → `carrier_id` | `tms.shipments` | `carrier_id` | INT FK |
| `cargo_product_reference` | string (`ban-107`) | `normalize_key()` → `BAN-107` | `tms.shipments` | `cargo_product_reference` | VARCHAR(50) |
| `source_node` | string | keine | `tms.shipments` | `source_node` | VARCHAR(100) |
| `target_node` | string | keine | `tms.shipments` | `target_node` | VARCHAR(100) |
| `transport_mode` | string | keine | `tms.shipments` | `transport_mode` | VARCHAR(50) |
| `timestamp` | ISO-8601 string | `datetime.fromisoformat()` | `tms.shipments` | `started_at` | TIMESTAMPTZ |
| `estimated_arrival` | ISO-8601 string | `datetime.fromisoformat()` | `tms.shipments` | `estimated_arrival` | TIMESTAMPTZ |

### 5.5 ERP: OrderCreated (Mehrfach-Ziel)

| Quell-Feld (JSON) | Typ (Quelle) | Transformation | Ziel-Tabelle | Ziel-Spalte | Typ (Ziel) |
|---|---|---|---|---|---|
| `order_reference` | string | keine | `erp.orders` | `order_reference` | VARCHAR(100) PK |
| `customer.customer_number` | string | FK-Lookup: `erp.customers` → `customer_id` | `erp.orders` | `customer_id` | INT FK |
| `delivery_priority` | string | Default: `NORMAL` | `erp.orders` | `delivery_priority` | VARCHAR(20) |
| `timestamp` | ISO-8601 string | `datetime.fromisoformat()` | `erp.orders` | `order_timestamp` | TIMESTAMPTZ |
| `items[].product_code` | string | `normalize_key()` + FK-Lookup → `product_id` | `erp.order_items` | `product_id` | INT FK |
| `items[].quantity` | number | Plausibilitätsprüfung > 0 | `erp.order_items` | `quantity` | INT |
| `items[].unit_price` | number | `safe_float()` + Check [1.50–5.00] | `erp.order_items` | `unit_price` | NUMERIC(10,2) |

### 5.6 ETL Phase 2: Operative Schemas → DWH (ausgewählte Felder)

| Quelle (Tabelle.Spalte) | Transformation | DWH-Ziel (Tabelle.Spalte) |
|---|---|---|
| `erp.customers.customer_number` | SK-Lookup via `dwh.dim_customer` | `dwh.fact_fulfillment.customer_sk` |
| `erp.products.product_code` | SK-Lookup via `dwh.dim_product` | `dwh.fact_fulfillment.product_sk` |
| `erp.suppliers.supplier_code` | SK-Lookup via `dwh.dim_supplier` | `dwh.fact_fulfillment.supplier_sk` |
| `tms.carriers.carrier_code` | SK-Lookup via `dwh.dim_carrier` | `dwh.fact_fulfillment.carrier_sk` |
| `erp.order_items.quantity` | keine | `dwh.fact_fulfillment.quantity` |
| `erp.order_items.unit_price` | keine | `dwh.fact_fulfillment.unit_price` |
| `erp.order_items.quantity * unit_price` | Berechnung | `dwh.fact_fulfillment.total_value` |
| `tms.transport_completions.delay_minutes` | `COALESCE(..., 0)` | `dwh.fact_fulfillment.delay_minutes` |
| `wms.node_processings.temperature` | `AVG()` GROUP BY `batch_reference` | `dwh.fact_fulfillment.avg_temperature` |
| `erp.orders.order_timestamp` | `TO_CHAR(ts, 'YYYYMMDD')::INT` | `dwh.fact_fulfillment.order_date_sk` |

---

## 6. Fehlerbehandlung im ETL

### Quarantäne-Strategie

Events, die gegen kritische Qualitätsregeln verstoßen, werden nicht verworfen, sondern in eine Quarantäne-Tabelle verschoben:

```python
# Kritische Fehler → Quarantäne
CRITICAL_RULES = ["RI-01", "RI-02", "EQ-01"]  # Referenzielle Integrität, Duplikate

# Warnungen → Laden mit Flag
WARNING_RULES  = ["PQ-03", "VQ-03"]  # Temperatur außerhalb Bereich, fehlt

def load_event(event: dict, pg_conn, errors: list[str]):
    if any(r in errors for r in CRITICAL_RULES):
        # In Quarantäne
        quarantine_table.insert(event, errors)
    elif errors:
        # Laden mit Quality-Flag
        target_table.insert(event, quality_flag="WARNING", quality_notes=str(errors))
    else:
        # Normal laden
        target_table.insert(event)
```

### Idempotenz

Der ETL-Prozess ist vollständig idempotent: mehrfaches Ausführen erzeugt keine Duplikate.

**PostgreSQL:** Alle INSERT-Statements nutzen `ON CONFLICT DO NOTHING` auf UNIQUE-Constraints.

```sql
INSERT INTO erp.suppliers (supplier_code, ...) VALUES (...)
ON CONFLICT (supplier_code) DO NOTHING;
```

**MongoDB:** Upsert-Muster mit `$setOnInsert` verhindert Überschreiben bestehender Dokumente. GPS-Positionen werden nur eingefügt, wenn der Zeitstempel noch nicht existiert:

```python
# Lifecycle-Dokument: einmalig anlegen, nie überschreiben
se.update_one({"shipment_identifier": sid}, {"$setOnInsert": doc}, upsert=True)

# GPS-Position: Duplikat-Guard über event_type + timestamp
se.update_one(
    {"shipment_identifier": sid,
     "events": {"$not": {"$elemMatch": {"event_type": "ShipmentPositionUpdated",
                                        "timestamp":  ev.get("timestamp")}}}},
    {"$push": {"events": event_entry}}
)
```

**Redis:** `SET`-Operationen überschreiben Keys mit demselben Wert. Counter (`INCR`) werden beim Mehrfach-Lauf hochgezählt – dies ist beabsichtigt (systemweite Laufzähler). `ZADD` auf SORTED SETs überschreibt gleiche Member (idempotent).

**Neo4j:** `MERGE` statt `CREATE` in allen Cypher-Statements. Existierende Nodes und Relationships werden wiederverwendet, nicht dupliziert.

---

## 7. ETL-Nachweis (aktualisiert 2026-05-15, Datenstand: 377 Events, 10 Iterationen)

Erwartetes ETL-Ergebnis auf Basis des aktuellen Datenbestands (377 JSON-Events, 10 operative Iterationen + Stammdaten).

| System | Ziel-Tabelle / Collection | Geladene Datensätze |
|---|---|---|
| PostgreSQL | `erp.suppliers` | 10 |
| PostgreSQL | `erp.customers` | 10 |
| PostgreSQL | `erp.products` | 10 |
| PostgreSQL | `erp.orders` | 10 |
| PostgreSQL | `erp.batches` | 10 |
| PostgreSQL | `tms.shipments` | 60 |
| PostgreSQL | `tms.shipment_positions` | 112 |
| PostgreSQL | `tms.transport_completions` | 60 |
| PostgreSQL | `tms.deliveries` | 10 |
| PostgreSQL | `wms.warehouse_skus` | 10 |
| PostgreSQL | `wms.node_processings` | 60 |
| MDM | `mdm.golden_records` | 5 Entity-Typen, je 5–10 Einträge |
| MongoDB | `shipment_events` | 60 (Lifecycle-Dokumente, 1 pro Shipment) |
| MongoDB | `node_events` | 60 |
| MongoDB | `batch_tracking` | 60 |
| MongoDB | `order_events` | 10 |
| Redis | Shipment-Status-Keys | 60 |
| Redis | Position-Updates | 112 |
| Redis | Delivery-Status-Keys | 10 |
| Neo4j | Shipments | 60 |
| Neo4j | Orders / Batches / Deliveries | je 10 |
| MinIO | Lieferscheine (`delivery-notes/`) | 60 |
| MinIO | Rechnungen (`invoices/`) | 8 |
| MinIO | B/L + Zollfreigaben (`transport-docs/`) | je 10 |
| MinIO | Qualitätszertifikate (`batch-certificates/`) | 10 |

**Prüfqueries:**

```sql
-- PostgreSQL: Grundzählung
SELECT COUNT(*) FROM erp.suppliers;        -- Erwartet: 10
SELECT COUNT(*) FROM tms.shipments;        -- Erwartet: 60
SELECT COUNT(*) FROM wms.node_processings; -- Erwartet: 60

-- MDM-Funktion: Schlüsselauflösung
SELECT mdm.resolve_canonical_key('BAN_101', 'WMS');  -- Erwartet: BAN-101
SELECT mdm.resolve_canonical_key('ban-101', 'TMS');  -- Erwartet: BAN-101

-- WMS sku-Format (muss WMS-Format behalten)
SELECT sku FROM wms.node_processings LIMIT 3;
-- Erwartet: BAN_108, BAN_107 etc. (Unterstriche, NICHT normalisiert)
```
