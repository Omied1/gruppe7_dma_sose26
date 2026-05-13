# Datenklassifikation – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-12  
**Grundlage:** Analyse der generierten JSON-Dateien in `shared/erp/`, `shared/wms/`, `shared/tms/`

---

## 1. Überblick: Quellsysteme und Eventmengen

| Quellsystem | Anzahl JSON-Dateien | Beschreibung |
|---|---|---|
| ERP | 50 | Enterprise Resource Planning – Stamm- und Bewegungsdaten |
| WMS | 70 | Warehouse Management System – Lager- und Knotenverarbeitung |
| TMS | 263 | Transport Management System – Carrier, Transporte, GPS, Lieferungen |

---

## 2. Vollständige Eventtyp-Klassifikation

### 2.1 ERP-Events

#### `SupplierCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | ERP |
| **Datenart** | Stammdaten (Master Data) |
| **Empfohlene Zieldatenbank** | PostgreSQL (`erp`-Schema) |
| **Wichtigste Felder** | `supplier_code`, `supplier_name`, `country`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "SupplierCreated",
  "supplier_code": "SUP-101",
  "supplier_name": "Golden Banana Ltd",
  "country": "Ghana",
  "timestamp": "2026-05-12T11:50:40.901581"
}
```

**Fachliche Bedeutung:** Lieferanten sind die Ursprungspartner der Banana Supply Chain. Sie liefern Produkte aus Ghana an die Plantagenstandorte. Die `supplier_code`-Referenz (`SUP-101`) wird über das ERP hinaus nicht vereinheitlicht und bildet damit den kanonischen Schlüssel im MDM.

**Begründung Zieldatenbank:** Lieferantenstammdaten sind strukturiert, unterliegen referenzieller Integrität (Produkte referenzieren Lieferanten) und müssen transaktionssicher verwaltet werden → PostgreSQL.

---

#### `CustomerCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | ERP |
| **Datenart** | Stammdaten (Master Data) |
| **Empfohlene Zieldatenbank** | PostgreSQL (`erp`-Schema) |
| **Wichtigste Felder** | `customer_number`, `customer_name`, `city`, `country`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "CustomerCreated",
  "customer_number": "CUST-101",
  "customer_name": "ALDI",
  "city": "Frankfurt",
  "country": "Germany",
  "timestamp": "2026-05-12T11:50:40.901772"
}
```

**Fachliche Bedeutung:** Kunden sind die Abnehmer der Bananensupplychain (Einzelhandelsketten wie ALDI, LIDL, REWE). Sie geben Bestellungen auf und sind Endziel der Fulfillment-Kette. `customer_number` ist der kanonische Business Key im ERP.

**Begründung Zieldatenbank:** Kundenstammdaten sind strukturiert, haben feste Attribute und müssen für JOIN-Operationen (z. B. mit Orders) verfügbar sein → PostgreSQL.

---

#### `ProductCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | ERP |
| **Datenart** | Stammdaten (Master Data) |
| **Empfohlene Zieldatenbank** | PostgreSQL (`erp`-Schema) + MDM-Schema |
| **Wichtigste Felder** | `product_code`, `product_name`, `category`, `supplier_reference`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "ProductCreated",
  "product_code": "BAN-101",
  "product_name": "Cavendish Banana",
  "category": "Fresh Fruit",
  "supplier_reference": "SUP-104",
  "timestamp": "2026-05-12T11:50:40.901793"
}
```

**Fachliche Bedeutung:** Produkte sind das zentrale Objekt der Supply Chain. Der ERP-Produktcode `BAN-101` ist der kanonische Schlüssel. **Kritisch:** WMS verwendet `BAN_101`, TMS verwendet `ban-101` für dasselbe Produkt – dies erzeugt systemübergreifende Inkonsistenz, die Masterdatenmanagement erfordert.

**Begründung Zieldatenbank:** PostgreSQL für strukturierte Stammdaten; MDM-Schema für Golden-Record-Verwaltung und systemübergreifende Schlüsselharmonisierung.

---

#### `OrderCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | ERP |
| **Datenart** | Bewegungsdaten (Transactional Data) |
| **Empfohlene Zieldatenbank** | PostgreSQL (`erp`-Schema) |
| **Wichtigste Felder** | `order_reference`, `customer.customer_number`, `items[].product_code`, `items[].quantity`, `items[].unit_price`, `delivery_priority`, `timestamp` |

**Beispiel (gekürzt):**
```json
{
  "event_type": "OrderCreated",
  "order_reference": "ORD-0f7dc974-b15d-434f-8a24-9e09f66ce508",
  "customer": { "customer_number": "CUST-109", "customer_name": "AUCHAN" },
  "items": [{ "product_code": "BAN-108", "quantity": 760, "unit_price": 3.09 }],
  "delivery_priority": "NORMAL",
  "timestamp": "2026-05-12T11:50:40.911185"
}
```

**Fachliche Bedeutung:** Bestellungen initiieren die Supply Chain. Jede Order enthält mindestens eine Produktposition mit Menge und Preis. `delivery_priority` (HIGH/NORMAL/LOW) steuert die Priorisierung im Fulfillment-Prozess.

**Begründung Zieldatenbank:** Bestelldaten sind transaktional, strukturiert und unterliegen ACID-Anforderungen (eine Bestellung darf nicht halb gespeichert werden) → PostgreSQL.

---

#### `BatchHarvested`

| Attribut | Wert |
|---|---|
| **Quellsystem** | ERP |
| **Datenart** | Bewegungsdaten (Operational Data) |
| **Empfohlene Zieldatenbank** | PostgreSQL (`erp`-Schema) |
| **Wichtigste Felder** | `batch_identifier`, `product_code`, `wms_sku`, `tms_product_reference`, `quantity`, `origin_country`, `supply_chain_node`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "BatchHarvested",
  "supply_chain_node": "BANANA_PLANTATION",
  "product_code": "BAN-108",
  "wms_sku": "BAN_108",
  "tms_product_reference": "ban-108",
  "batch_identifier": "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b",
  "origin_country": "Ghana",
  "quantity": 760,
  "timestamp": "2026-05-12T11:50:40.911207"
}
```

**Fachliche Bedeutung:** Ein geernteter Batch ist die physische Menge Bananen, die einer Bestellung zugeordnet wird. **Dieses Ereignis enthält bereits alle drei Produktschlüssel** (`product_code`, `wms_sku`, `tms_product_reference`) – es ist damit das verbindende Element für das Masterdatenmanagement.

**Begründung Zieldatenbank:** PostgreSQL für strukturierte, ACID-konforme Batchverwaltung.

---

### 2.2 WMS-Events

#### `WarehouseSKUCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | WMS |
| **Datenart** | Stammdaten (Master Data) |
| **Empfohlene Zieldatenbank** | PostgreSQL (`wms`-Schema) + MDM-Schema |
| **Wichtigste Felder** | `erp_product_code`, `sku`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "WarehouseSKUCreated",
  "erp_product_code": "BAN-101",
  "sku": "BAN_101",
  "timestamp": "2026-05-12T11:50:40.901817"
}
```

**Fachliche Bedeutung:** Das WMS verwaltet Produkte unter eigenen SKUs (Stock-Keeping Units). Die SKU `BAN_101` ist die WMS-spezifische Darstellung des ERP-Codes `BAN-101`. Das `erp_product_code`-Feld ist die Cross-Reference zum MDM und ermöglicht die Schlüsselharmonisierung.

**Begründung Zieldatenbank:** PostgreSQL für WMS-Stammdaten; MDM-Schema für die systemübergreifende Zuordnung.

---

#### `NodeProcessed`

| Attribut | Wert |
|---|---|
| **Quellsystem** | WMS |
| **Datenart** | Bewegungsdaten / Eventdaten |
| **Empfohlene Zieldatenbank** | PostgreSQL (`wms`-Schema) + MongoDB |
| **Wichtigste Felder** | `supply_chain_node`, `batch_reference`, `sku`, `temperature`, `status`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "NodeProcessed",
  "supply_chain_node": "AFRICA_COLD_STORAGE",
  "batch_reference": "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b",
  "sku": "BAN_108",
  "temperature": 12.57,
  "status": "COMPLETED",
  "timestamp": "2026-05-12T11:50:40.911318"
}
```

**Fachliche Bedeutung:** Jeder Supply-Chain-Knoten (Plantation, Collection Center, Quality Control, Cold Storage, Warehouse, Retail) verarbeitet den Batch und protokolliert die Umgebungstemperatur. Die Temperatur ist qualitätskritisch (Kühlkette). `status: COMPLETED` bedeutet, dass der Batch den Knoten verlassen hat.

**Begründung Zieldatenbank:** PostgreSQL für strukturierte Knotenverarbeitungen; MongoDB für flexible Eventaufzeichnungen (z. B. wenn zukünftig weitere Felder wie Feuchtigkeit hinzukommen).

---

### 2.3 TMS-Events

#### `CarrierCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Datenart** | Stammdaten (Master Data) |
| **Empfohlene Zieldatenbank** | PostgreSQL (`tms`-Schema) |
| **Wichtigste Felder** | `carrier_id`, `carrier_name`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "CarrierCreated",
  "carrier_id": "CAR-101",
  "carrier_name": "DHL",
  "timestamp": "2026-05-12T11:50:40.901848"
}
```

**Fachliche Bedeutung:** Carrier sind die Transportdienstleister (DHL, Maersk, MSC, DB Schenker, Hapag Lloyd). Jeder Transport wird einem Carrier zugeordnet. `carrier_id` ist der TMS-spezifische Business Key.

**Begründung Zieldatenbank:** PostgreSQL für TMS-Stammdaten.

---

#### `TransportProductReferenceCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Datenart** | Stammdaten (Master Data) |
| **Empfohlene Zieldatenbank** | PostgreSQL (`tms`-Schema) + MDM-Schema |
| **Wichtigste Felder** | `erp_product_code`, `transport_product_reference`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "TransportProductReferenceCreated",
  "erp_product_code": "BAN-101",
  "transport_product_reference": "ban-101",
  "timestamp": "2026-05-12T11:50:40.901835"
}
```

**Fachliche Bedeutung:** Das TMS verwaltet Produkte unter Kleinbuchstaben-Referenzen (`ban-101`). Analog zu `WarehouseSKUCreated` im WMS bildet dieses Event die TMS-seitige Schlüsselmapping-Tabelle für das MDM.

**Begründung Zieldatenbank:** PostgreSQL + MDM für Schlüsselharmonisierung.

---

#### `TransportStarted`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Datenart** | Bewegungsdaten (Transactional Data) |
| **Empfohlene Zieldatenbank** | PostgreSQL (`tms`-Schema) + MongoDB |
| **Wichtigste Felder** | `shipment_identifier`, `source_node`, `target_node`, `transport_mode`, `cargo_product_reference`, `carrier.carrier_id`, `estimated_arrival`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "TransportStarted",
  "shipment_identifier": "SHIP-bf5d4354-817b-41b3-ba5e-5e9001ccc31c",
  "source_node": "AFRICA_COLD_STORAGE",
  "target_node": "EUROPE_COLD_STORAGE",
  "transport_mode": "SEA_FREIGHT",
  "cargo_product_reference": "ban-108",
  "carrier": { "carrier_id": "CAR-104", "carrier_name": "DB Schenker" },
  "estimated_arrival": "2026-05-13T01:50:40.911324",
  "timestamp": "2026-05-12T11:50:40.911326"
}
```

**Fachliche Bedeutung:** Jeder Transport verbindet zwei Supply-Chain-Knoten. Es gibt zwei Transportmodi: `TRUCK` (Landtransport) und `SEA_FREIGHT` (Seefracht für Afrika→Europa). `shipment_identifier` ist der primäre Tracking-Schlüssel über alle TMS-Events.

**Begründung Zieldatenbank:** PostgreSQL für strukturierte Transportdaten (referenzielle Integrität); MongoDB für den vollständigen Shipment-Event-Stream.

---

#### `ShipmentPositionUpdated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Datenart** | **Echtzeitdaten (Real-time Data)** |
| **Empfohlene Zieldatenbank** | Redis (Echtzeit) + MongoDB (Archiv) |
| **Wichtigste Felder** | `shipment_identifier`, `coordinates.latitude`, `coordinates.longitude`, `container_temperature`, `speed_kmh`, `current_route`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "ShipmentPositionUpdated",
  "shipment_identifier": "SHIP-935eae1b",
  "cargo_product_reference": "ban-108",
  "current_route": { "source": "EUROPE_COLD_STORAGE", "target": "CENTRAL_WAREHOUSE" },
  "coordinates": { "latitude": -13.286561, "longitude": 174.034529 },
  "container_temperature": 13.39,
  "speed_kmh": 59.85,
  "timestamp": "2026-05-12T11:50:40.911348"
}
```

**Fachliche Bedeutung:** GPS-Tracking-Events sind die einzigen echten Echtzeitdaten im System. Sie werden für jede Transportstrecke 1–3 Mal generiert und enthalten neben Position auch Containertemperatur (Kühlkettenkontrolle) und Geschwindigkeit. Da viele Events pro Sekunde entstehen können, sind sie für persistente Datenbanken weniger geeignet.

**Begründung Zieldatenbank:** Redis für den **aktuellen** Standort (schneller Zugriff, automatisches Ablaufen nach TTL); MongoDB für die **historische Positionsarchivierung** (flexibles Dokument, keine Schemaänderung nötig).

---

#### `TransportCompleted`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Datenart** | Eventdaten |
| **Empfohlene Zieldatenbank** | PostgreSQL (`tms`-Schema) + MongoDB |
| **Wichtigste Felder** | `shipment_identifier`, `cargo_product_reference`, `arrival_node`, `delay_minutes`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "TransportCompleted",
  "shipment_identifier": "SHIP-7ccb17f1",
  "cargo_product_reference": "ban-108",
  "arrival_node": "RETAIL_STORE",
  "delay_minutes": 169,
  "timestamp": "2026-05-12T11:50:40.911370"
}
```

**Fachliche Bedeutung:** Abschluss eines Transportabschnitts mit tatsächlicher Verzögerung in Minuten. `delay_minutes` ist eine wichtige KPI für die Lieferperformance. Dieses Event schließt den Lifecycle eines Transports (gestartet → abgeschlossen).

**Begründung Zieldatenbank:** PostgreSQL für strukturierte Abschlüsse; MongoDB für den vollständigen Event-Stream eines Shipments.

---

#### `DeliveryCompleted`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Datenart** | Eventdaten |
| **Empfohlene Zieldatenbank** | PostgreSQL (`tms`-Schema) + MongoDB |
| **Wichtigste Felder** | `supply_chain_node`, `shipment_identifier`, `cargo_product_reference`, `delivery_status`, `received_by`, `timestamp` |

**Beispiel:**
```json
{
  "event_type": "DeliveryCompleted",
  "supply_chain_node": "RETAIL_STORE",
  "shipment_identifier": "SHIP-7ccb17f1",
  "cargo_product_reference": "ban-108",
  "delivery_status": "SUCCESSFUL",
  "received_by": "EMP-7",
  "timestamp": "2026-05-12T11:50:40.911373"
}
```

**Fachliche Bedeutung:** Abschlussereignis der gesamten Supply Chain. `delivery_status` (SUCCESSFUL / DELAYED) und `received_by` (Mitarbeiter-ID) dokumentieren die finale Übergabe. Dieses Event löst in einem realen System die Rechnungsstellung und Bestandsfortschreibung aus.

**Begründung Zieldatenbank:** PostgreSQL für strukturierte Lieferabschlüsse; MongoDB für den vollständigen Shipment-Lifecycle.

---

## 3. Zusammenfassung: Eventtypen nach Datenart und Zieldatenbank

| Eventtyp | Quellsystem | Datenart | Zieldatenbank (primär) | Zieldatenbank (sekundär) |
|---|---|---|---|---|
| `SupplierCreated` | ERP | Stammdaten | PostgreSQL (erp) | MDM |
| `CustomerCreated` | ERP | Stammdaten | PostgreSQL (erp) | MDM |
| `ProductCreated` | ERP | Stammdaten | PostgreSQL (erp) | MDM |
| `OrderCreated` | ERP | Bewegungsdaten | PostgreSQL (erp) | — |
| `BatchHarvested` | ERP | Bewegungsdaten | PostgreSQL (erp) | — |
| `WarehouseSKUCreated` | WMS | Stammdaten | PostgreSQL (wms) | MDM |
| `NodeProcessed` | WMS | Bewegungsdaten / Events | PostgreSQL (wms) | MongoDB |
| `CarrierCreated` | TMS | Stammdaten | PostgreSQL (tms) | MDM |
| `TransportProductReferenceCreated` | TMS | Stammdaten | PostgreSQL (tms) | MDM |
| `TransportStarted` | TMS | Bewegungsdaten | PostgreSQL (tms) | MongoDB |
| `ShipmentPositionUpdated` | TMS | **Echtzeitdaten** | **Redis** | MongoDB (Archiv) |
| `TransportCompleted` | TMS | Eventdaten | PostgreSQL (tms) | MongoDB |
| `DeliveryCompleted` | TMS | Eventdaten | PostgreSQL (tms) | MongoDB |

---

## 4. Identifizierte Masterdaten-Inkonsistenz

Ein zentrales Problem der Banana Supply Chain ist die **systemübergreifende Produktcode-Inkonsistenz**:

| System | Produktcode-Format | Beispiel |
|---|---|---|
| ERP (kanonisch) | `BAN-101` | Bindestriche, Großbuchstaben |
| WMS | `BAN_101` | Unterstriche statt Bindestriche |
| TMS | `ban-101` | Kleinbuchstaben |

Diese Inkonsistenz ist **bewusst im Datengenerator implementiert** (`MASTERDATA_INCONSISTENCY_MODE = "targeted"`) und macht ein **Masterdatenmanagement mit Golden Records** zwingend notwendig. Ohne MDM können ERP-Orders nicht mit WMS-Knotenverarbeitungen oder TMS-Transporten systemübergreifend verknüpft werden.
