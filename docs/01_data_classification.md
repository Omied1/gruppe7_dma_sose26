# Datenklassifikation – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-15  
**Grundlage:** Analyse der generierten JSON-Dateien in `shared/erp/`, `shared/wms/`, `shared/tms/`

---

## 1. Überblick: Quellsysteme und Eventmengen

| Quellsystem | Anzahl JSON-Dateien | Eventtypen | Beschreibung |
|---|---|---|---|
| ERP | 50 | 5 | Enterprise Resource Planning – Stamm- und Bewegungsdaten |
| WMS | 70 | 2 | Warehouse Management System – Lager- und Knotenverarbeitung |
| TMS | 257 | 6 | Transport Management System – Carrier, Transporte, GPS, Lieferungen |
| **Gesamt** | **377** | **13** | Alle verarbeitbaren Ereignisse in der Supply Chain (10 operative Iterationen + Stammdaten) |

---

## 2. Datenart-Taxonomie

Für die Klassifikation gelten folgende Definitionen, angewendet auf den Banana-Supply-Chain-Kontext:

| Datenart | Definition (projektbezogen) | Beispiel |
|---|---|---|
| **Stammdaten** | Relativ statische Kernobjekte, die den Rahmen der Supply Chain definieren. Ändern sich selten, sind Referenzpunkt aller anderen Daten. | Lieferant `SUP-101 Golden Banana Ltd`, Produkt `BAN-101 Cavendish` |
| **Bewegungsdaten** | Entstehen durch Geschäftsvorfälle und beschreiben den Fluss von Mengen, Werten oder Ressourcen. Transaktional, ACID-relevant. | `OrderCreated` mit 760 kg BAN-108 für CUST-109 |
| **Eventdaten** | Zustandsändernde Ereignisse innerhalb einer Prozesskette. Jedes Event hat einen eindeutigen Zeitstempel und ist Teil einer Event-Kette. | `NodeProcessed` an AFRICA_COLD_STORAGE, `TransportCompleted` mit 169 min Verzögerung |
| **Echtzeitdaten** | Hochfrequente, kurzlebige Sensor- oder Positionsdaten. Zeitkritisch, benötigen schnellen Schreibzugriff und automatischen Ablauf. | GPS-Position `ShipmentPositionUpdated` mit Containertemperatur 13,39 °C |
| **Dokumentdaten** | Strukturierte Dokumente, die durch Ereignisse ausgelöst werden. Nicht direkt als JSON-Event vorhanden, sondern als abgeleitetes Artefakt. | Lieferschein aus `DeliveryCompleted`, Chargenzertifikat aus `BatchHarvested` |

**Abgrenzung:** Klassische **Bestandsdaten** werden vom Datengenerator nicht als eigener JSON-Eventtyp erzeugt. Mengen erscheinen zwar in `OrderCreated` und `BatchHarvested`, beschreiben dort aber konkrete Geschäftsvorfälle und werden deshalb als Bewegungsdaten klassifiziert. **Metadaten** werden im Projekt separat im Schema `meta` modelliert (`sql/06_create_metadata_tables.sql`) und in `docs/05_metadata_management.md` dokumentiert. Die generierten JSON-Dateien enthalten nur technische Event-Metadaten wie `event_type` und `timestamp`, aber keine eigenständigen Metadaten-Events.

---

## 3. Vollständige Eventtyp-Klassifikation

### 3.1 ERP-Events

#### `SupplierCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | ERP |
| **Anzahl Dateien** | 10 (SUP-101 bis SUP-110) |
| **Datenart** | Stammdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`erp`-Schema, Tabelle: `suppliers`) |
| **Sekundäre Zieldatenbank** | Neo4j (`Supplier`-Knoten), MDM (Golden Record) |
| **Wichtigste Felder** | `supplier_code`, `supplier_name`, `country`, `timestamp` |

**Beispiel aus JSON:**
```json
{
  "event_type": "SupplierCreated",
  "supplier_code": "SUP-101",
  "supplier_name": "Golden Banana Ltd",
  "country": "Ghana",
  "timestamp": "2026-05-12T11:50:40.901581"
}
```

**Fachliche Begründung:**  
Lieferanten sind Ursprungspartner der Banana Supply Chain. Sie liefern Cavendish-Bananen aus Ghana. `supplier_code` (Format `SUP-101`) ist der kanonische Business Key im ERP und Bezugspunkt des MDM Golden Records. Die Daten sind strukturiert und ohne NULL-Overhead – keine Flexibilität für Schemavarianten notwendig.

**Begründung PostgreSQL:** Vollständig strukturiertes Schema, referenzielle Integrität zu `products` (via `supplier_reference`), ACID-Garantie für transaktionssichere Verwaltung.

**Begründung Neo4j (sekundär, via ETL):** `SUP-101` wird als `Supplier`-Knoten im Graphen angelegt und erhält eine `(SUPPLIES {product_code})`-Kante zu `Product`-Knoten – notwendig für Supply-Chain-Pfad-Abfragen PLANTATION→RETAIL.

---

#### `CustomerCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | ERP |
| **Anzahl Dateien** | 10 (CUST-101 bis CUST-110) |
| **Datenart** | Stammdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`erp`-Schema, Tabelle: `customers`) |
| **Sekundäre Zieldatenbank** | Neo4j (`Customer`-Knoten), MDM |
| **Wichtigste Felder** | `customer_number`, `customer_name`, `city`, `country`, `timestamp` |

**Beispiel aus JSON:**
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

**Hinweis: Eingebettetes Objekt in OrderCreated.** Das `OrderCreated`-Event enthält das Customer-Objekt eingebettet (inkl. `"event_type": "CustomerCreated"`) als Snapshot. Bei der ETL-Verarbeitung muss dieses verschachtelte `event_type`-Feld gefiltert werden – es darf nicht als eigenständiger Event-Eintrag behandelt werden.

**Fachliche Begründung:**  
Kunden sind Einzelhandelsketten (ALDI, AUCHAN, REWE etc.) als Endpunkte der Fulfillment-Kette. `customer_number` (Format `CUST-101`) ist kanonischer ERP-Key. Die Kunden treten nur im ERP auf – WMS und TMS referenzieren Kunden nicht direkt.

**Begründung PostgreSQL:** Strukturierte Stammdaten mit stabilen Attributen (`city`, `country`), die für JOIN-Operationen mit `orders` benötigt werden.

**Begründung Neo4j (sekundär):** `CUST-101` wird als `Customer`-Knoten angelegt und erhält eine `(ORDERED_BY)`-Kante von `Order`-Knoten.

---

#### `ProductCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | ERP |
| **Anzahl Dateien** | 10 (BAN-101 bis BAN-110) |
| **Datenart** | Stammdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`erp`-Schema, Tabelle: `products`) + MDM-Schema |
| **Sekundäre Zieldatenbank** | Neo4j (`Product`-Knoten) |
| **Wichtigste Felder** | `product_code`, `product_name`, `category`, `supplier_reference`, `timestamp` |

**Beispiel aus JSON:**
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

**Fachliche Begründung:**  
`BAN-101` ist das zentrale Objekt der gesamten Supply Chain. Die **systemübergreifende Produktcode-Inkonsistenz** (ERP: `BAN-101`, WMS: `BAN_101`, TMS: `ban-101`) macht diesen Eventtyp zum Ausgangspunkt des MDM. `supplier_reference: SUP-104` verknüpft das Produkt mit dem Lieferanten im ERP.

**Begründung PostgreSQL + MDM:** PostgreSQL für operative Stammdaten; MDM-Schema speichert den Golden Record mit drei `source_mappings`-Einträgen (ERP/WMS/TMS je Produkt), die von `mdm.resolve_canonical_key()` aufgelöst werden.

---

#### `OrderCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | ERP |
| **Anzahl Dateien** | 10 (10 Iterationen) |
| **Datenart** | Bewegungsdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`erp`-Schema, Tabellen: `orders`, `order_items`) |
| **Sekundäre Zieldatenbank** | Neo4j (`Order`-Knoten), MinIO (Auftragsbestätigung) |
| **Wichtigste Felder** | `order_reference`, `customer.customer_number`, `items[].product_code`, `items[].quantity`, `items[].unit_price`, `delivery_priority`, `timestamp` |

**Beispiel aus JSON:**
```json
{
  "event_type": "OrderCreated",
  "order_reference": "ORD-0f7dc974-b15d-434f-8a24-9e09f66ce508",
  "customer": {
    "event_type": "CustomerCreated",
    "customer_number": "CUST-109",
    "customer_name": "AUCHAN",
    "city": "Frankfurt",
    "country": "Germany"
  },
  "items": [{ "product_code": "BAN-108", "quantity": 760, "unit_price": 3.09 }],
  "delivery_priority": "NORMAL",
  "timestamp": "2026-05-12T11:50:40.911185"
}
```

**Fachliche Begründung:**  
Bestellungen initiieren die gesamte Supply Chain und sind der kaufmännische Kern. `order_reference` (UUID-Format `ORD-*`) ist unveränderlicher Geschäftsschlüssel. `delivery_priority` (HIGH/NORMAL/LOW) steuert Priorisierung in WMS und TMS. `items[]` bildet die 1:N-Beziehung zu `order_items` ab.

**Begründung PostgreSQL:** Transaktionssicherheit (ACID) ist zwingend – eine Bestellung mit drei Positionen darf nicht partiell gespeichert werden. JOIN-Fähigkeit für DWH-ETL (`fact_fulfillment`).

**Begründung MinIO (Dokumentdaten, abgeleitet):** In einer realen Implementierung löst `OrderCreated` die Erzeugung einer Auftragsbestätigung (PDF) aus → Bucket `invoices`, Pfad `invoices/ORD-{uuid}.pdf`. PostgreSQL speichert nur den Objektpfad.

---

#### `BatchHarvested`

| Attribut | Wert |
|---|---|
| **Quellsystem** | ERP |
| **Anzahl Dateien** | 10 (10 Iterationen, immer an `BANANA_PLANTATION`) |
| **Datenart** | Bewegungsdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`erp`-Schema, Tabelle: `batches`) |
| **Sekundäre Zieldatenbank** | Neo4j (`Batch`-Knoten), MinIO (Chargenzertifikat) |
| **Wichtigste Felder** | `batch_identifier`, `product_code`, `wms_sku`, `tms_product_reference`, `quantity`, `origin_country`, `supply_chain_node`, `timestamp` |

**Beispiel aus JSON:**
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

**Fachliche Begründung:**  
Ein Batch ist die physische Erntemengen-Einheit, die einer Order zugeordnet wird. Dieses Event ist das **einzige in der Supply Chain, das alle drei Produktschlüssel gleichzeitig enthält** (`product_code: BAN-108`, `wms_sku: BAN_108`, `tms_product_reference: ban-108`). Damit ist `BatchHarvested` das primäre Quell-Event für die MDM-Schlüsselharmonisierung.

**Begründung PostgreSQL:** Strukturierte, ACID-konforme Batchverwaltung mit Fremdschlüssel auf `products`.

**Begründung MinIO (Dokumentdaten, abgeleitet):** Jede Ernte erzeugt ein Chargenzertifikat (Herkunftsnachweis, Qualitätsparameter) → Bucket `batch-certificates`, Pfad `batch-certificates/BATCH-{uuid}.pdf`.

---

### 3.2 WMS-Events

#### `WarehouseSKUCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | WMS |
| **Anzahl Dateien** | 10 (BAN_101 bis BAN_110) |
| **Datenart** | Stammdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`wms`-Schema, Tabelle: `warehouse_skus`) + MDM-Schema |
| **Sekundäre Zieldatenbank** | — |
| **Wichtigste Felder** | `erp_product_code`, `sku`, `timestamp` |

**Beispiel aus JSON:**
```json
{
  "event_type": "WarehouseSKUCreated",
  "erp_product_code": "BAN-101",
  "sku": "BAN_101",
  "timestamp": "2026-05-12T11:50:40.901817"
}
```

**Fachliche Begründung:**  
Das WMS verwaltet Produkte unter Underscore-SKUs (`BAN_101`). Das Feld `erp_product_code: BAN-101` ist die explizite Cross-Reference zum ERP und macht dieses Event zur WMS-seitigen Registrierung im MDM. Jede SKU entspricht 1:1 einem ERP-Produktcode.

**Begründung PostgreSQL + MDM:** PostgreSQL für WMS-Stammdaten; MDM-`source_mappings` verknüpft `BAN_101` (WMS) → `BAN-101` (ERP Golden Record). Kein Neo4j-Bedarf, da SKUs keine eigenständigen Graphknoten sind.

---

#### `NodeProcessed`

| Attribut | Wert |
|---|---|
| **Quellsystem** | WMS |
| **Anzahl Dateien** | 60 (10 Iterationen × 6 Knoten) |
| **Datenart** | Eventdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`wms`-Schema, Tabelle: `node_processings`) |
| **Sekundäre Zieldatenbank** | MongoDB (Collection: `node_events`), Neo4j (`PROCESSED_AT`-Kante) |
| **Wichtigste Felder** | `supply_chain_node`, `batch_reference`, `sku`, `temperature`, `status`, `timestamp` |

**Verarbeitete Knoten (aus tatsächlichen JSON-Dateien, alle 6 WMS-Knoten):**

| Knoten | Typ | Bedeutung |
|---|---|---|
| `BANANA_PLANTATION` | Produktionsknoten | Erste Verarbeitung nach der Ernte |
| `COLLECTION_CENTER` | Sammelknoten | Bündelung mehrerer Batches |
| `QUALITY_CONTROL` | Prüfknoten | Qualitätsprüfung vor Kühlung |
| `AFRICA_COLD_STORAGE` | Kühlknoten (Afrika) | Vorkühlung vor Seefracht |
| `EUROPE_COLD_STORAGE` | Kühlknoten (Europa) | Empfangslager nach Seefracht |
| `CENTRAL_WAREHOUSE` | Auslieferungslager | Letzte Station vor Einzelhandel |

**Hinweis:** `RETAIL_STORE` ist **kein WMS-Knoten**. Der Einzelhandel ist ausschließlich im TMS über `DeliveryCompleted` modelliert.

**Beispiel aus JSON:**
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

**Fachliche Begründung:**  
Jeder WMS-Knoten erzeugt genau ein `NodeProcessed`-Event pro Batch-Iteration. Die Temperatur (hier: 12,57 °C) ist qualitätskritisch – der Sollbereich für Cavendish-Bananen beträgt 10–15 °C (Kühlkette). `status: COMPLETED` bedeutet, dass der Batch den Knoten vollständig verarbeitet verlassen hat. Mit 60 Events (6 Knoten × 10 Iterationen) ist dies der volumenstärkste WMS-Eventtyp.

**Begründung PostgreSQL:** Strukturierte Knotenverarbeitungen mit referenzieller Integrität zu `batches` (via `batch_reference`). Grundlage für DQM-Checks (Temperaturausreißer-Abfragen).

**Begründung MongoDB (sekundär):** Flexible Eventarchivierung für den vollständigen Batch-Lifecycle in einer Collection. Alle 6 `NodeProcessed`-Events eines Batches können als eingebettetes Array in einem einzigen Dokument gespeichert werden.

**Begründung Neo4j (sekundär, via ETL):** `PROCESSED_AT`-Kante zwischen `Batch`-Knoten und `SupplyChainNode`-Knoten mit Temperatur als Kanten-Property – ermöglicht Kühlkettenanalyse auf Graphebene.

---

### 3.3 TMS-Events

#### `CarrierCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Anzahl Dateien** | 5 (CAR-101 bis CAR-105) |
| **Datenart** | Stammdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`tms`-Schema, Tabelle: `carriers`) |
| **Sekundäre Zieldatenbank** | Neo4j (`Carrier`-Knoten) |
| **Wichtigste Felder** | `carrier_id`, `carrier_name`, `timestamp` |

**Beispiel aus JSON:**
```json
{
  "event_type": "CarrierCreated",
  "carrier_id": "CAR-101",
  "carrier_name": "DHL",
  "timestamp": "2026-05-12T11:50:40.901848"
}
```

**Carrier im System:** DHL (CAR-101), Maersk (CAR-102), MSC (CAR-103), DB Schenker (CAR-104), Hapag-Lloyd (CAR-105).

**Fachliche Begründung:**  
Carrier sind Transportdienstleister. Alle 5 Carrier-Datensätze werden in Iteration 0 angelegt (Stammdaten-Phase). `carrier_id` ist TMS-interner Business Key und Fremdschlüssel in `shipments`. Die minimalen Felder (nur Name und ID) sind typisch für TMS-Carrier-Stammdaten.

**Begründung PostgreSQL:** TMS-Stammdaten, referenziell verknüpft mit `shipments`.

**Begründung Neo4j (sekundär):** `CAR-104` (DB Schenker) wird als `Carrier`-Knoten angelegt und erhält `(TRANSPORTED_BY)`-Kanten von allen `Shipment`-Knoten auf der Seefrachtstrecke.

---

#### `TransportProductReferenceCreated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Anzahl Dateien** | 10 (ban-101 bis ban-110) |
| **Datenart** | Stammdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`tms`-Schema, Tabelle: `transport_product_refs`) + MDM-Schema |
| **Sekundäre Zieldatenbank** | — |
| **Wichtigste Felder** | `erp_product_code`, `transport_product_reference`, `timestamp` |

**Beispiel aus JSON:**
```json
{
  "event_type": "TransportProductReferenceCreated",
  "erp_product_code": "BAN-101",
  "transport_product_reference": "ban-101",
  "timestamp": "2026-05-12T11:50:40.901835"
}
```

**Fachliche Begründung:**  
Spiegelstruktur zu `WarehouseSKUCreated` auf TMS-Seite. `ban-101` (Kleinbuchstaben) ist die TMS-seitige Produktreferenz. `erp_product_code: BAN-101` ist auch hier die explizite Cross-Reference zum ERP. Dieses Event dient ausschließlich der Schlüsselregistrierung für das MDM.

**Begründung PostgreSQL + MDM:** MDM-`source_mappings` verknüpft `ban-101` (TMS) → `BAN-101` (ERP Golden Record). Kein Neo4j-Bedarf, da TMS-Produktreferenzen keine eigenständigen Graphknoten sind – sie werden auf `Product`-Knoten aufgelöst.

---

#### `TransportStarted`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Anzahl Dateien** | 60 (10 Iterationen × 6 Transportstrecken) |
| **Datenart** | Bewegungsdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`tms`-Schema, Tabelle: `shipments`) |
| **Sekundäre Zieldatenbank** | MongoDB (Collection: `shipment_events`), Neo4j (`Shipment`-Knoten + Kanten), MinIO (Transportauftrag) |
| **Wichtigste Felder** | `shipment_identifier`, `source_node`, `target_node`, `transport_mode`, `cargo_product_reference`, `carrier.carrier_id`, `estimated_arrival`, `timestamp` |

**Transporttopologie (vollständige 6-Strecken-Route, aus JSON-Dateien verifiziert):**

| Strecke | `source_node` | `target_node` | `transport_mode` |
|---|---|---|---|
| 1 | `BANANA_PLANTATION` | `COLLECTION_CENTER` | `TRUCK` |
| 2 | `COLLECTION_CENTER` | `QUALITY_CONTROL` | `TRUCK` |
| 3 | `QUALITY_CONTROL` | `AFRICA_COLD_STORAGE` | `TRUCK` |
| 4 | `AFRICA_COLD_STORAGE` | `EUROPE_COLD_STORAGE` | `SEA_FREIGHT` |
| 5 | `EUROPE_COLD_STORAGE` | `CENTRAL_WAREHOUSE` | `TRUCK` |
| 6 | `CENTRAL_WAREHOUSE` | `RETAIL_STORE` | `TRUCK` |

**Beispiel aus JSON:**
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

**Fachliche Begründung:**  
`TransportStarted` ist der Start jedes Transportabschnitts. `shipment_identifier` (Format `SHIP-{UUID}`) ist der primäre Tracking-Schlüssel, der alle nachfolgenden TMS-Events (`ShipmentPositionUpdated`, `TransportCompleted`) verbindet. Die einzige Seefrachtstrecke (Afrika→Europa) wird vom Carrier DB Schenker oder Maersk bedient. `estimated_arrival` ermöglicht Soll/Ist-Vergleich für die Delay-KPI.

**Begründung PostgreSQL:** Transaktionale Bewegungsdaten mit Fremdschlüsseln zu `carriers` und Basis für DWH-Faktentabelle.

**Begründung Neo4j (sekundär):** `Shipment`-Knoten mit `(TRANSPORTED_BY)`-Kante zu `Carrier` und `(FROM_NODE/TO_NODE)`-Kanten zu `SupplyChainNode`-Knoten – Grundlage für Pfadabfragen.

**Begründung MinIO (Dokumentdaten, abgeleitet):** Jeder Transport erzeugt ein Transportdokument (Frachtbrief/CMR) → Bucket `transport-docs`, Pfad `transport-docs/SHIP-{uuid}.pdf`.

---

#### `ShipmentPositionUpdated`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Anzahl Dateien** | 118 (ca. 2 GPS-Updates pro Transportstrecke) |
| **Datenart** | **Echtzeitdaten** |
| **Primäre Zieldatenbank** | **Redis** (aktueller Standort) |
| **Sekundäre Zieldatenbank** | MongoDB (Collection: `shipment_events`, Archivierung) |
| **Wichtigste Felder** | `shipment_identifier`, `coordinates.latitude`, `coordinates.longitude`, `container_temperature`, `speed_kmh`, `current_route.source`, `current_route.target`, `timestamp` |

**Beispiel aus JSON:**
```json
{
  "event_type": "ShipmentPositionUpdated",
  "shipment_identifier": "SHIP-935eae1b-717f-44aa-a11b-de974734236e",
  "cargo_product_reference": "ban-108",
  "current_route": {
    "source": "EUROPE_COLD_STORAGE",
    "target": "CENTRAL_WAREHOUSE"
  },
  "coordinates": { "latitude": -13.286561, "longitude": 174.034529 },
  "container_temperature": 13.39,
  "speed_kmh": 59.85,
  "timestamp": "2026-05-12T11:50:40.911348"
}
```

**Fachliche Begründung:**  
`ShipmentPositionUpdated` ist der **einzige echte Echtzeitdatentyp** im System. Er enthält neben GPS-Koordinaten auch `container_temperature` (Kühlkettenüberwachung, Sollbereich 10–15 °C) und `speed_kmh`. Mit 118 Events über 60 Transportabschnitte (≈ 2 Updates pro Strecke) ist dieses Event das volumenstärkste im TMS.

**Begründung Redis (primär):** Echtzeitdaten erfordern schnellen Schreibzugriff (< 1 ms) und automatisches Ablaufen nach TTL. Redis speichert den **aktuellen** Standort unter dem Key `shipment:SHIP-{uuid}:position` mit TTL 300 s. Nach Ablauf gilt der Standort als veraltet – der Container hat die Strecke beendet oder kein Update gesendet. Redis `HASH` ermöglicht atomare Updates einzelner Felder (Lat/Lon, Temperatur) ohne vollständigen Objekt-Overhead.

**Begründung MongoDB (sekundär):** Historische GPS-Spuren werden als Array eingebetteter Positionsdokumente in der `shipment_events`-Collection archiviert. Das schema-flexible Dokument ermöglicht zukünftige Erweiterungen (z. B. Feuchtigkeitssensor) ohne Schemamigration. TTL-Index auf `timestamp` löscht alte GPS-Daten automatisch nach 90 Tagen.

**Kein PostgreSQL:** Persistente GPS-Daten in PostgreSQL würden bei realen Intervallen (alle 30 s) innerhalb eines Monats Millionen Zeilen erzeugen und JOIN-Performance der operativen Tabellen beeinträchtigen.

---

#### `TransportCompleted`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Anzahl Dateien** | 60 (10 Iterationen × 6 Strecken) |
| **Datenart** | Eventdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`tms`-Schema, Tabelle: `transport_completions`) |
| **Sekundäre Zieldatenbank** | MongoDB (Collection: `shipment_events`) |
| **Wichtigste Felder** | `shipment_identifier`, `cargo_product_reference`, `arrival_node`, `delay_minutes`, `timestamp` |

**Beispiel aus JSON:**
```json
{
  "event_type": "TransportCompleted",
  "shipment_identifier": "SHIP-7ccb17f1-74c9-44dc-8b98-fc800449ae7d",
  "cargo_product_reference": "ban-108",
  "arrival_node": "RETAIL_STORE",
  "delay_minutes": 169,
  "timestamp": "2026-05-12T11:50:40.911370"
}
```

**Fachliche Begründung:**  
`TransportCompleted` schließt einen Transportabschnitt ab und liefert das Ist-Ankunftsdatum. `delay_minutes: 169` (≈ 2,8 Stunden Verzögerung) ist das zentrale Maß für die KPI „Liefertreue". Das Event schließt den Lifecycle eines `Shipment`-Objekts (gestartet → abgeschlossen). Zusammen mit `TransportStarted` bildet dieses Event das Soll/Ist-Paar für jede Transportstrecke.

**Begründung PostgreSQL:** Strukturierter Eventabschluss mit referenzieller Integrität zu `shipments`. `delay_minutes` fließt direkt in die DWH-Faktentabelle `fact_fulfillment` ein.

**Begründung MongoDB (sekundär):** `TransportCompleted` wird als abschließendes Event in das Shipment-Lifecycle-Dokument eingebettet, das alle Events eines Transports (Start → GPS → Abschluss) zusammenfasst.

---

#### `DeliveryCompleted`

| Attribut | Wert |
|---|---|
| **Quellsystem** | TMS |
| **Anzahl Dateien** | 10 (10 Iterationen, immer an `RETAIL_STORE`) |
| **Datenart** | Eventdaten |
| **Primäre Zieldatenbank** | PostgreSQL (`tms`-Schema, Tabelle: `deliveries`) |
| **Sekundäre Zieldatenbank** | MongoDB (Collection: `shipment_events`), MinIO (Lieferschein) |
| **Wichtigste Felder** | `supply_chain_node`, `shipment_identifier`, `cargo_product_reference`, `delivery_status`, `received_by`, `timestamp` |

**Beispiel aus JSON:**
```json
{
  "event_type": "DeliveryCompleted",
  "supply_chain_node": "RETAIL_STORE",
  "shipment_identifier": "SHIP-7ccb17f1-74c9-44dc-8b98-fc800449ae7d",
  "cargo_product_reference": "ban-108",
  "delivery_status": "SUCCESSFUL",
  "received_by": "EMP-7",
  "timestamp": "2026-05-12T11:50:40.911373"
}
```

**Fachliche Begründung:**  
`DeliveryCompleted` ist das **abschließende Ereignis der gesamten Supply Chain**. `delivery_status` (SUCCESSFUL / DELAYED) und `received_by` (Mitarbeiter-ID am Retail Store) dokumentieren die finale Übergabe. In einem realen System löst dieses Event die Rechnungsstellung und Bestandsfortschreibung im ERP aus. Der Knoten ist immer `RETAIL_STORE` – kein WMS-Knoten.

**Begründung PostgreSQL:** Strukturierter Lieferabschluss; `delivery_status` fließt in DQM-Regeln und DWH-KPIs ein.

**Begründung MinIO (Dokumentdaten, abgeleitet):** Jede erfolgreiche Lieferung erzeugt einen Lieferschein (Empfangsbestätigung mit Batch-Referenz, EMP-ID, Timestamp) → Bucket `delivery-notes`, Pfad `delivery-notes/SHIP-{uuid}.pdf`. PostgreSQL speichert nur Bucket-Name und Objektpfad als Referenz.

---

## 4. Gesamtübersicht: Eventtypen nach Datenart und Zieldatenbank

| # | Eventtyp | System | Anzahl | Datenart | Primär | Sekundär |
|---|---|---|---|---|---|---|
| 1 | `SupplierCreated` | ERP | 10 | Stammdaten | PostgreSQL (erp) | Neo4j, MDM |
| 2 | `CustomerCreated` | ERP | 10 | Stammdaten | PostgreSQL (erp) | Neo4j, MDM |
| 3 | `ProductCreated` | ERP | 10 | Stammdaten | PostgreSQL (erp) | Neo4j, MDM |
| 4 | `OrderCreated` | ERP | 10 | Bewegungsdaten | PostgreSQL (erp) | Neo4j, MinIO |
| 5 | `BatchHarvested` | ERP | 10 | Bewegungsdaten | PostgreSQL (erp) | Neo4j, MinIO |
| 6 | `WarehouseSKUCreated` | WMS | 10 | Stammdaten | PostgreSQL (wms) | MDM |
| 7 | `NodeProcessed` | WMS | 60 | Eventdaten | PostgreSQL (wms) | MongoDB, Neo4j |
| 8 | `CarrierCreated` | TMS | 5 | Stammdaten | PostgreSQL (tms) | Neo4j |
| 9 | `TransportProductReferenceCreated` | TMS | 10 | Stammdaten | PostgreSQL (tms) | MDM |
| 10 | `TransportStarted` | TMS | 60 | Bewegungsdaten | PostgreSQL (tms) | MongoDB, Neo4j, MinIO |
| 11 | `ShipmentPositionUpdated` | TMS | 112 | **Echtzeitdaten** | **Redis** | MongoDB |
| 12 | `TransportCompleted` | TMS | 60 | Eventdaten | PostgreSQL (tms) | MongoDB |
| 13 | `DeliveryCompleted` | TMS | 10 | Eventdaten | PostgreSQL (tms) | MongoDB, MinIO |
| | **Gesamt** | | **377** | | | |

---

## 5. Datenbankenmatrix: Welche Events gehen wohin?

| Zieldatenbank | Eventtypen (primär) | Eventtypen (sekundär) | Begründung |
|---|---|---|---|
| **PostgreSQL** | 1–6, 8–10, 12, 13 (12 von 13) | — | Strukturierte, ACID-konforme Stamm- und Bewegungsdaten mit referenzieller Integrität |
| **MongoDB** | — | NodeProcessed, TransportStarted, ShipmentPositionUpdated (Archiv), TransportCompleted, DeliveryCompleted | Flexible Eventarchivierung; heterogene Felder; eingebettete Shipment-Lifecycles ohne NULL-Overhead |
| **Redis** | ShipmentPositionUpdated (1 von 13) | — | Echtzeitdaten; TTL-basiertes Ablaufen veralteter Positionen; < 1 ms Lesezugriff |
| **Neo4j** | — | SupplierCreated, CustomerCreated, ProductCreated, BatchHarvested, CarrierCreated, OrderCreated, TransportStarted, NodeProcessed | Graph-Knoten und -Kanten für Supply-Chain-Pfadabfragen (PLANTATION→RETAIL = 6 Hops) |
| **MinIO** | — | OrderCreated, BatchHarvested, TransportStarted, DeliveryCompleted | Abgeleitete Dokumente (PDF): Auftragsbestätigung, Chargenzertifikat, Frachtbrief, Lieferschein |

---

## 6. Dokumentdaten: Abgeleitete Dokumente und MinIO-Bucket-Zuordnung

Kein Event-Typ ist selbst ein Dokumentdatentyp. Vier Events **triggern** Dokumenterzeugung:

| Auslösendes Event | Dokument | MinIO-Bucket | Objektpfad-Schema | PostgreSQL-Referenz |
|---|---|---|---|---|
| `OrderCreated` | Auftragsbestätigung | `invoices` | `invoices/ORD-{uuid}.pdf` | `erp.orders.invoice_path` |
| `BatchHarvested` | Chargenzertifikat | `batch-certificates` | `batch-certificates/BATCH-{uuid}.pdf` | `erp.batches.certificate_path` |
| `TransportStarted` | Frachtbrief / CMR | `transport-docs` | `transport-docs/SHIP-{uuid}.pdf` | `tms.shipments.transport_doc_path` |
| `DeliveryCompleted` | Lieferschein | `delivery-notes` | `delivery-notes/SHIP-{uuid}.pdf` | `tms.deliveries.delivery_note_path` |

**Begründung MinIO statt PostgreSQL BLOB:**  
PDFs können mehrere MB groß sein. In PostgreSQL als BLOB gespeichert würden sie Join-Performance und Backup-Größe massiv beeinträchtigen. MinIO ermöglicht versionierte Objektspeicherung mit automatischer Replikation und HTTP(S)-Direktzugriff. PostgreSQL speichert ausschließlich den Bucket-Namen und Objektpfad als TEXT-Referenz.

---

## 7. Identifizierte Masterdaten-Inkonsistenz

Die **systemübergreifende Produktcode-Inkonsistenz** ist im Datengenerator bewusst implementiert (`MASTERDATA_INCONSISTENCY_MODE = "targeted"`):

| System | Produktcode-Format | Beispiel | Trennzeichen |
|---|---|---|---|
| ERP (kanonisch) | `BAN-101` | Bindestriche, Großbuchstaben | `-` |
| WMS | `BAN_101` | Unterstriche statt Bindestriche | `_` |
| TMS | `ban-101` | Kleinbuchstaben + Bindestriche | `-` |

**Konsequenz:** Ohne MDM können `OrderCreated` (ERP, `BAN-108`) nicht mit `NodeProcessed` (WMS, `BAN_108`) oder `TransportStarted` (TMS, `ban-108`) systemübergreifend gejoint werden. Das `BatchHarvested`-Event ist das einzige Event, das **alle drei Schlüssel gleichzeitig** enthält und damit den Mapping-Goldstandard für das MDM liefert.

**Auflösung:** `mdm.resolve_canonical_key('BAN_108', 'WMS')` → `BAN-108` (ERP-Canonical-Key)
