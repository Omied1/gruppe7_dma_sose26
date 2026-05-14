# ETL-Konzept – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-12

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
Schritt 1: ERP-Stammdaten zuerst (erp.suppliers, erp.customers, erp.products)
           → SupplierCreated, CustomerCreated, ProductCreated
           → Schlüssel werden via normalize_key() auf BAN-NNN-Format gebracht
           → MDM-Tabellen enthalten ein vollständiges Referenzbeispiel (BAN-101)

Schritt 2: WMS/TMS-Stammdaten (wms.warehouse_skus, tms.carriers, tms.transport_product_references)
           → CarrierCreated, WarehouseSKUCreated, TransportProductReferenceCreated
           → normalize_key() harmonisiert BAN_101 / ban-101 → BAN-101

Schritt 3: WMS-Stammdaten (wms.warehouse_skus, wms.supply_chain_nodes)
           → Unabhängig von Schritt 2

Schritt 4: TMS-Stammdaten (tms.carriers, tms.transport_product_references)
           → Unabhängig von Schritt 2

Schritt 5: ERP-Bewegungsdaten (erp.orders, erp.order_items, erp.batches)
           → Abhängig von Schritt 2 (FK zu suppliers, customers, products)

Schritt 6: WMS-Eventdaten (wms.node_processings)
           → Abhängig von Schritt 3 (FK zu supply_chain_nodes)
           → Cross-Schema-Ref auf Schritt 5 (batch_reference)

Schritt 7: TMS-Eventdaten (tms.shipments, tms.shipment_positions,
                           tms.transport_completions, tms.deliveries)
           → Abhängig von Schritt 4 (FK zu carriers)

Schritt 8: MongoDB – Event-Collections (parallel zu Schritt 5-7)
Schritt 9: Redis – Echtzeitzustände (aus Schritt 7-Events)
Schritt 10: Neo4j – Graph-Beziehungen (aus Schritt 2-7)
Schritt 11: MinIO – Dokumente generieren und hochladen
```

---

## 3. ETL-Phase 2: Operative Schemas → DWH

> **Wichtig:** Diese Phase findet **separat** statt und entspricht dem ETL-Konzept des Data Warehouses. Die operativen ERP/WMS/TMS-Schemas sind **Quellsysteme** des DWH.

```sql
-- Beispiel: ETL-Insert in dwh.fact_fulfillment
INSERT INTO dwh.fact_fulfillment (
    customer_sk, product_sk, supplier_sk, carrier_sk,
    destination_node_sk, order_date_sk, delivery_date_sk, delivery_status_sk,
    order_reference, batch_identifier, shipment_identifier,
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
    TO_CHAR(d.delivered_at,    'YYYYMMDD')::INT,
    dds.status_sk,
    o.order_reference,
    b.batch_identifier,
    s.shipment_identifier,
    oi.quantity,
    oi.unit_price,
    (oi.quantity * oi.unit_price)   AS total_value,
    COALESCE(tc.delay_minutes, 0)   AS delay_minutes,
    avg_temps.avg_temp              AS avg_temperature,
    o.delivery_priority
FROM erp.orders               o
JOIN erp.order_items          oi  ON oi.order_id    = o.order_id
JOIN erp.products             p   ON p.product_id   = oi.product_id
JOIN erp.customers            cu  ON cu.customer_id = o.customer_id
JOIN erp.batches              b   ON b.order_id     = o.order_id
JOIN erp.suppliers            sup ON sup.supplier_id = p.supplier_id
-- TMS via MDM-Schlüssel
JOIN tms.transport_product_references tpr ON tpr.erp_product_code = p.product_code
JOIN tms.shipments            s   ON s.cargo_product_reference = tpr.transport_product_reference
LEFT JOIN tms.transport_completions tc ON tc.shipment_id = s.shipment_id
LEFT JOIN tms.deliveries      d   ON d.shipment_id = s.shipment_id
-- Temperatur-Aggregation aus WMS
LEFT JOIN (
    SELECT np.batch_reference, AVG(np.temperature) AS avg_temp
    FROM   wms.node_processings np
    WHERE  np.temperature IS NOT NULL
    GROUP  BY np.batch_reference
) avg_temps ON avg_temps.batch_reference = b.batch_identifier
-- Surrogate Key Lookups
JOIN dwh.dim_customer         dc  ON dc.customer_number = cu.customer_number
JOIN dwh.dim_product          dp  ON dp.product_code    = p.product_code
JOIN dwh.dim_supplier         ds  ON ds.supplier_code   = sup.supplier_code
LEFT JOIN dwh.dim_carrier     dca ON dca.carrier_code   = (SELECT carrier_code FROM tms.carriers WHERE carrier_id = s.carrier_id)
LEFT JOIN dwh.dim_supply_chain_node dn ON dn.node_code  = s.target_node
JOIN dwh.dim_delivery_status  dds ON dds.status_code    = COALESCE(d.delivery_status, 'FAILED')
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
| `shared/erp/` | `BatchHarvested` | Timestamp parsen, order_reference → order_id FK | PostgreSQL `erp.batches` | Operative Bewegungsdaten |
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

## 5. Fehlerbehandlung im ETL

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

Alle INSERT-Statements nutzen `ON CONFLICT DO NOTHING` auf UNIQUE-Constraints, sodass der ETL-Prozess mehrfach ausgeführt werden kann ohne Duplikate.
