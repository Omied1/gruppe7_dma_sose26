# Projektanleitung – Banana Supply Chain Datenplattform

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26 – TH Lübeck  
**Gruppe:** 7  
**Deadline:** 06.07.2026  
**Dieses Dokument erklärt:** Was jede Datei tut, wie alle Teile zusammenhängen und in welcher Reihenfolge alles ausgeführt wird.

---

## Inhaltsverzeichnis

1. [Projektüberblick und Architektur](#1-projektüberblick-und-architektur)
2. [Verzeichnisstruktur auf einen Blick](#2-verzeichnisstruktur-auf-einen-blick)
3. [Infrastruktur: Docker-Container](#3-infrastruktur-docker-container)
4. [Quelldaten: Die JSON-Events in `shared/`](#4-quelldaten-die-json-events-in-shared)
5. [Datenbankschemas in PostgreSQL (`sql/`)](#5-datenbankschemas-in-postgresql-sql)
6. [Python-Skripte in `bananasupplychain/`](#6-python-skripte-in-bananasupplychain)
7. [Neo4j Graphmodell (`cypher/`)](#7-neo4j-graphmodell-cypher)
8. [Analytics (`analytics/`)](#8-analytics-analytics)
9. [Dokumentation (`docs/`)](#9-dokumentation-docs)
10. [Vollständige Ausführungsreihenfolge (Schritt für Schritt)](#10-vollständige-ausführungsreihenfolge-schritt-für-schritt)
11. [Datenpfade: Wie ein Event durch das System fließt](#11-datenpfade-wie-ein-event-durch-das-system-fließt)
12. [Zugriff auf die Datenbanken](#12-zugriff-auf-die-datenbanken)
13. [Bekannte Fehler und deren Lösungen](#13-bekannte-fehler-und-deren-lösungen)
14. [Checkliste vor der Abgabe](#14-checkliste-vor-der-abgabe)

---

## 1. Projektüberblick und Architektur

### Was das Projekt abbildet

Eine Banana Supply Chain mit 6 Stationen: Plantage → Sammelstelle → Qualitätskontrolle → Kältespeicher Afrika → Kältespeicher Europa → Zentrallager → Einzelhandel. Drei Quellsysteme liefern JSON-Ereignisse:

- **ERP** (Enterprise Resource Planning): Stammdaten (Lieferanten, Kunden, Produkte) und Geschäftsvorfälle (Bestellungen, Chargen)
- **WMS** (Warehouse Management System): Lagerplatzverwaltung (SKUs) und Knotenverarbeitung an den 6 Stationen
- **TMS** (Transport Management System): Carrier-Daten, Transportaufträge, GPS-Positionsupdates, Lieferabschlüsse

### Zielsysteme

Die ETL-Pipeline verteilt diese Events auf **5 spezialisierte Datenbanken**:

| System | Zweck | Port |
|--------|-------|------|
| **PostgreSQL 15** | Relationale Stamm- und Bewegungsdaten + MDM + Metadaten + DWH | 5432 |
| **MongoDB 7** | Ereignisdokumente (Shipment-Lifecycle, Node-Events, Batch-Tracking) | 27017 |
| **Redis 7** | Echtzeit-Tracking (GPS, Temperatur, aktive Sendungen) | 6379 |
| **Neo4j 5** | Supply-Chain-Graphmodell (Pfade, Routen, Lieferketten) | 7474 / 7687 |
| **MinIO** | Objektspeicher für Logistikdokumente (PDFs: Rechnungen, Lieferscheine, etc.) | 9000 / 9001 |

### Gesamtarchitektur (Datenfluss)

```
shared/erp/  (534 JSON)  ─┐
shared/wms/  (1.522 JSON)  ──┼──► etl_load.py ──► PostgreSQL (erp/wms/tms-Schemas)
shared/tms/  (6.300 JSON) ─┘         │           MongoDB (4 Collections)
                                   │           Redis (STRING/HASH/LIST/ZSET)
                                   │           Neo4j (8 Node-Typen, 13 Beziehungen)
                                   │
                         generate_documents.py ──► MinIO (4 Buckets, 2.444 PDFs)
                                   │
                         etl_dwh.py ──► PostgreSQL dwh-Schema (Sternschema)
                                   │
                         analytics/ ──► PDF/PNG-Charts, Clustering, Prognose
```

---

## 2. Verzeichnisstruktur auf einen Blick

```
gruppe7_dma_sose26/
│
├── Aufgabenstellung.pdf          ← Maßgebliche Aufgabenstellung (ZUERST lesen!)
├── README.md                     ← Kurzreferenz Startsequenz + erwartete Ergebnisse
├── PROJECT_STATUS.md             ← Lebendiges Arbeitsprotokoll (Fehler, Status, offene Punkte)
├── PROJEKTANLEITUNG.md           ← Diese Datei
│
├── shared/                       ← Quelldaten (JSON-Events, NICHT bearbeiten)
│   ├── erp/   (534 Dateien)       ← ERP-Events (Supplier, Customer, Product, Order, Batch)
│   ├── wms/   (1.522 Dateien)       ← WMS-Events (WarehouseSKU, NodeProcessed)
│   └── tms/  (6.300 Dateien)       ← TMS-Events (Carrier, TransportRef, Shipment, Position, Delivery)
│
├── sql/                          ← PostgreSQL DDL-Skripte (in Nummerierungsreihenfolge ausführen)
│   ├── 01_create_schemas.sql
│   ├── 02_create_erp_tables.sql
│   ├── 03_create_wms_tables.sql
│   ├── 04_create_tms_tables.sql
│   ├── 05_create_mdm_tables.sql
│   ├── 06_create_metadata_tables.sql
│   ├── 06b_metadata_complete.sql
│   ├── 07_create_dwh_schema.sql
│   ├── 08_data_quality_checks.sql
│   ├── 08b_dq_audit.sql
│   └── 09_verification_queries.sql
│
├── bananasupplychain/            ← Python-Skripte + Docker
│   ├── container/
│   │   └── docker-compose.yml   ← 5 Datenbank-Services + Cleanup-Job
│   ├── test_data_generator.py   ← Erzeugt JSON-Events in shared/ (anpassbar – Änderungen dokumentieren)
│   ├── etl_load.py              ← ETL Phase 1: JSON → PostgreSQL/MongoDB/Redis/Neo4j
│   ├── etl_dwh.py               ← ETL Phase 2: PostgreSQL-Schemas → DWH-Sternschema
│   ├── generate_documents.py    ← Erzeugt PDFs und lädt in MinIO hoch
│   └── verify_all_systems.py    ← Technische Nachweise für alle 5 Systeme
│
├── cypher/                       ← Neo4j Cypher-Skripte
│   ├── 01_create_graph_model.cypher   ← Constraints, Stammdaten, Topologie
│   └── 02_verification_queries.cypher ← Prüfabfragen Neo4j
│
├── docs/                         ← Vollständige Projektdokumentation (14 Dateien)
│   ├── 00_part1_checklist.md
│   ├── 01_data_classification.md
│   ├── 02_target_architecture.md
│   ├── 03_er_model.md
│   ├── 04_masterdata_management.md
│   ├── 05_metadata_management.md
│   ├── 06_data_quality.md
│   ├── 07_dwh_model.md
│   ├── 08_mongodb_event_model.md
│   ├── 09_redis_realtime_model.md
│   ├── 10_neo4j_graph_model.md
│   ├── 11_minio_document_model.md
│   ├── 12_etl_concept.md
│   └── 13_data_quality_results.md
│
└── analytics/                    ← Teil 2: Analytics-Skripte und Ausgaben
    ├── dashboard.py              ← 5 BI-Charts
    ├── clustering.py             ← k-Means Kundensegmentierung
    ├── forecast.py               ← ARIMA Absatzprognose
    ├── dashboard.pdf/png/html    ← Erzeugte Ausgaben
    ├── clustering.pdf/png        ← Erzeugte Ausgaben
    └── forecast.pdf/png/txt      ← Erzeugte Ausgaben
```

---

## 3. Infrastruktur: Docker-Container

### Datei: `bananasupplychain/container/docker-compose.yml`

Diese Datei definiert **6 Services**, die per Docker Compose gestartet werden:

| Service | Image | Port(s) | Credentials | Besonderheit |
|---------|-------|---------|-------------|--------------|
| `postgres` | postgres:15 | 5432 | user / password | DB: `logistics` |
| `mongodb` | mongo:7 | 27017 | (keine Auth) | WiredTiger Cache 0,25 GB |
| `redis` | redis:7 | 6379 | (keine Auth) | maxmemory 256 MB, allkeys-lru |
| `neo4j` | neo4j:5 | 7474, 7687 | neo4j / password | Heap 512 MB, PageCache 256 MB |
| `minio` | minio/minio | 9000, 9001 | admin / password | Console auf Port 9001 |
| `cleanup` | postgres:15 | – | – | Löscht GPS-Positionen > 90 Tage täglich |

**Volumes** (persistente Datenspeicherung zwischen Container-Neustarts):
- `postgres_data`, `mongo_data`, `neo4j_data`, `minio_data`

**Cleanup-Job:** Ein separater PostgreSQL-Container führt täglich `DELETE FROM tms.shipment_positions WHERE recorded_at < NOW() - INTERVAL '90 days'` aus. Das simuliert das Ablaufen von GPS-Rohdaten (wie der TTL-Index in MongoDB).

**Starten:**
```bash
cd bananasupplychain/container && docker compose up -d && cd ../..
```

**Status prüfen:**
```bash
docker ps
```

Alle 6 Container müssen den Status `Up` haben.

---

## 4. Quelldaten: Die JSON-Events in `shared/`

### Datei: `bananasupplychain/test_data_generator.py`

> **WICHTIG:** Diese Datei ist anpassbar, jede Änderung muss aber in `PROJECT_STATUS.md`, `README.md` und dieser Anleitung dokumentiert werden. Danach `shared/` neu generieren und den vollständigen ETL-Lauf wiederholen.

Der Generator erzeugt eine **52-Wochen-Zeitreihe** mit variabler Anzahl Bestellungen pro Woche und schreibt die Ergebnisse als JSON-Dateien in `shared/erp/`, `shared/wms/`, `shared/tms/`. Produktkategorien werden als analytische Segmente erzeugt: `Standard`, `Sustainable`, `Premium`, `Specialty`.

**Ausführung (immer aus dem Repo-Root!):**
```bash
python3 bananasupplychain/test_data_generator.py
```

**Erzeugte Dateien:**

| Ordner | Anzahl | Eventtypen |
|--------|--------|------------|
| `shared/erp/` | 534 | SupplierCreated, CustomerCreated, ProductCreated, OrderCreated, BatchHarvested |
| `shared/wms/` | 1.522 | WarehouseSKUCreated, NodeProcessed |
| `shared/tms/` | 6.300 | CarrierCreated, TransportProductReferenceCreated, TransportStarted, ShipmentPositionUpdated, TransportCompleted, DeliveryCompleted |

**Dateinamen-Schema:**
```
supplychain_iteration_000_supplier_sup-101_supplier_created.json
supplychain_iteration_001_shipmentpositionupdated_uuid.json
```
- `iteration_000` = Stammdaten-Runde (Initialdaten: Supplier, Customer, Product, Carrier)
- `iteration_001` bis `iteration_010` = 10 operative Durchläufe (1 Bestellzyklus je Runde)

**Timestamps:** Der Generator setzt echte Event-Zeitstempel direkt (nicht mehr die ETL). Zeitanker `_ITER_BASE = 2025-06-16`; Woche N = Anker + (N-1)·7 Tage, jede Bestellung zusätzlich 0–6 Tage Offset. Ein Fulfillment fächert über ~15 Tage auf (Plantage Tag 0 → Supermarkt Tag 14–15). Spanne: ~Juni 2025 → Juni 2026 (letzte ~12 Monate, alle Daten ≤ heute).

### Die 13 Eventtypen im Überblick

| # | Eventtyp | Quelle | Datenart | Primär-Ziel |
|---|----------|--------|----------|-------------|
| 1 | `SupplierCreated` | ERP | Stammdaten | PostgreSQL `erp.suppliers` + Neo4j |
| 2 | `CustomerCreated` | ERP | Stammdaten | PostgreSQL `erp.customers` + Neo4j |
| 3 | `ProductCreated` | ERP | Stammdaten | PostgreSQL `erp.products` + Neo4j |
| 4 | `OrderCreated` | ERP | Bewegungsdaten | PostgreSQL `erp.orders` + `erp.order_items` |
| 5 | `BatchHarvested` | ERP | Bewegungsdaten | PostgreSQL `erp.batches` + MongoDB |
| 6 | `WarehouseSKUCreated` | WMS | Stammdaten | PostgreSQL `wms.warehouse_skus` |
| 7 | `NodeProcessed` | WMS | Eventdaten | PostgreSQL `wms.node_processings` + MongoDB |
| 8 | `CarrierCreated` | TMS | Stammdaten | PostgreSQL `tms.carriers` + Neo4j |
| 9 | `TransportProductReferenceCreated` | TMS | Stammdaten | PostgreSQL `tms.transport_product_refs` |
| 10 | `ShipmentStarted` | TMS | Bewegungsdaten | PostgreSQL `tms.shipments` + Neo4j |
| 11 | `ShipmentPositionUpdated` | TMS | Echtzeitdaten | PostgreSQL `tms.shipment_positions` + Redis |
| 12 | `TransportCompleted` | TMS | Eventdaten | PostgreSQL `tms.transport_completions` + MongoDB |
| 13 | `DeliveryCompleted` | TMS | Eventdaten | PostgreSQL `tms.deliveries` + MongoDB + Neo4j |

---

## 5. Datenbankschemas in PostgreSQL (`sql/`)

Die SQL-Dateien müssen in **numerischer Reihenfolge** ausgeführt werden. Jede Datei baut auf der vorherigen auf.

### `sql/01_create_schemas.sql` – Schemas anlegen

Legt die 6 PostgreSQL-Schemas an:
- `erp` – ERP-Tabellen
- `wms` – WMS-Tabellen
- `tms` – TMS-Tabellen
- `mdm` – Masterdatenmanagement
- `meta` – Metadaten
- `dwh` – Data Warehouse (Sternschema)

**Ausführen:**
```bash
docker exec -i postgres psql -U user -d logistics < sql/01_create_schemas.sql
```

---

### `sql/02_create_erp_tables.sql` – ERP-Datenmodell (6 Tabellen)

| Tabelle | Inhalt | PK |
|---------|--------|-----|
| `erp.suppliers` | Lieferanten (SUP-101 bis SUP-110) | `supplier_id` (SERIAL) |
| `erp.customers` | Kunden (CUST-101 bis CUST-110) | `customer_id` (SERIAL) |
| `erp.products` | Produkte (BAN-101 bis BAN-110, Cavendish-Varianten) | `product_id` (SERIAL) |
| `erp.orders` | Bestellungen mit `order_code`, `customer_id`, Datum | `order_id` (SERIAL) |
| `erp.order_items` | Positionen je Bestellung (product_id, quantity, unit_price) | `item_id` (SERIAL) |
| `erp.batches` | Geerntete Chargen mit Gewicht, Qualitätsnote | `batch_id` (SERIAL) |

**Wichtige Designentscheidungen:**
- `erp.batches` hat **kein** `order_id`-FK (wurde mit Patch `d1d46a1` entfernt, weil BatchHarvested-Events keinen Bestellbezug enthalten)
- `event_timestamp` in allen Tabellen speichert den originalen JSON-Timestamp
- `erp.order_items` hat einen FK auf `erp.orders(order_id)` und `erp.products(product_id)`

---

### `sql/03_create_wms_tables.sql` – WMS-Datenmodell (3 Tabellen)

| Tabelle | Inhalt | PK |
|---------|--------|-----|
| `wms.warehouse_skus` | SKU-Einträge im Lager. `sku` im WMS-Format (BAN_101), `erp_product_code` normalisiert (BAN-101) | `sku_id` (SERIAL) |
| `wms.supply_chain_nodes` | Die 6 Stationen: banana_plantation, collection_center, quality_control, africa_cold_storage, europe_cold_storage, central_warehouse | `node_id` (SERIAL) |
| `wms.node_processings` | Welche Charge wurde an welchem Knoten verarbeitet; Temperatur, Gewicht | `processing_id` (SERIAL) |

**Wichtig:** `wms.warehouse_skus.sku` behält bewusst das WMS-Format (Unterstrich), damit der MDM-Kontrast sichtbar bleibt. Die Harmonisierung findet in `mdm.resolve_canonical_key()` statt.

**UNIQUE-Constraint** auf `node_processings(batch_reference, node_id)` verhindert doppelte Einträge bei ETL-Wiederholung.

---

### `sql/04_create_tms_tables.sql` – TMS-Datenmodell (6 Tabellen)

| Tabelle | Inhalt | PK |
|---------|--------|-----|
| `tms.carriers` | Transportunternehmen (CAR-101 bis CAR-105) | `carrier_id` (SERIAL) |
| `tms.transport_product_refs` | Transportprodukt-Referenzen je SKU (Temperaturbereich, Verpackungstyp) | `ref_id` (SERIAL) |
| `tms.shipments` | Sendungen mit Route, Status, carrier_id (NOT NULL) | `shipment_id` (SERIAL) |
| `tms.shipment_positions` | GPS-Positionen je Sendung (lat, lon, Temperatur) | `position_id` (SERIAL) |
| `tms.transport_completions` | Abschluss eines Transportabschnitts (delay_minutes, tatsächliche Ankunft) | `completion_id` (SERIAL) |
| `tms.deliveries` | Endlieferung an den Kunden (delivery_status, signed_by) | `delivery_id` (SERIAL) |

**Wichtig:** `tms.shipments.carrier_id` ist NOT NULL – jede Sendung muss einem Carrier zugeordnet sein.

---

### `sql/05_create_mdm_tables.sql` – Masterdatenmanagement (3 Tabellen + Funktionen)

Das MDM löst die zentrale Inkonsistenz des Projekts: Produkt `BAN-101` heißt im ERP `BAN-101`, im WMS `BAN_101` und im TMS `ban-101`.

| Tabelle | Inhalt |
|---------|--------|
| `mdm.entity_types` | Typen von Golden Records (PRODUCT, SUPPLIER, CUSTOMER, CARRIER, NODE) |
| `mdm.golden_records` | 42 kanonische Master-Schlüssel (z.B. `BAN-101` als Goldstandard) |
| `mdm.source_mappings` | 69 Einträge: welche Systemvariante auf welchen Golden Record zeigt |

**Funktion `mdm.resolve_canonical_key(source_key TEXT, source_system TEXT) RETURNS TEXT`:**
- Eingabe: `'BAN_101', 'WMS'` → Ausgabe: `'BAN-101'`
- Eingabe: `'ban-101', 'TMS'` → Ausgabe: `'BAN-101'`
- Eingabe: `'BAN-101', 'ERP'` → Ausgabe: `'BAN-101'`

**Test:**
```sql
SELECT mdm.resolve_canonical_key('BAN_101', 'WMS');   -- muss 'BAN-101' zurückgeben
SELECT mdm.resolve_canonical_key('ban-101', 'TMS');   -- muss 'BAN-101' zurückgeben
```

**View `mdm.v_golden_overview`:** Zeigt alle Golden Records mit Anzahl Quellsystem-Mappings.

---

### `sql/06_create_metadata_tables.sql` + `sql/06b_metadata_complete.sql` – Metadatenmanagement

Beschreibt alle Spalten aller Tabellen mit Skalenniveaus, Datentypen und Qualitätsregeln.

| Tabelle | Inhalt |
|---------|--------|
| `meta.systems` | ERP, WMS, TMS, MDM, DWH – Systemsteckbriefe |
| `meta.tables` | Jede Tabelle mit Beschreibung und Systemzuordnung |
| `meta.columns` | Jede Spalte mit Skalenniveau, Typ, Qualitätsregel |

**Skalenniveaus im Projekt:**
- `NOMINAL`: event_type, carrier_mode, delivery_status (keine Rangordnung)
- `ORDINAL`: delivery_priority (HIGH > MEDIUM > LOW), quality_grade (A > B > C)
- `INTERVAL`: avg_temperature in °C (kein absoluter Nullpunkt)
- `RATIO`: delay_minutes, quantity, unit_price (absoluter Nullpunkt, Verhältnisse sinnvoll)

`06b_metadata_complete.sql` ergänzt alle 168 Spalten, die in der Basisdatei noch nicht enthalten waren.

---

### `sql/07_create_dwh_schema.sql` – Data Warehouse Sternschema

Das DWH-Schema enthält das analytische Sternschema für Teil 2.

**Dimensionstabellen (7):**

| Dimension | Inhalt | Quelle |
|-----------|--------|--------|
| `dwh.dim_date` | Date Spine 2025-01-01 bis 2027-12-31 (1095 Zeilen) | SQL-Generierung |
| `dwh.dim_customer` | Kunde mit Typ und Herkunftsland | `erp.customers` |
| `dwh.dim_supplier` | Lieferant mit Land | `erp.suppliers` |
| `dwh.dim_product` | Produkt mit Kategorie (`Standard`, `Sustainable`, `Premium`, `Specialty`) und Lieferantenattributen | `erp.products` |
| `dwh.dim_carrier` | Transportunternehmen mit Typ | `tms.carriers` |
| `dwh.dim_route` | Transportrouten (Plantage → Retail) | ETL-Ableitung |
| `dwh.dim_supply_chain_node` | Die 6 Stationen | `wms.supply_chain_nodes` |

**Faktentabelle:**

`dwh.fact_fulfillment` – Grain: 1 Zeile pro Endlieferung (252 Zeilen bei 252 Bestellungen)

| Measure | Bedeutung |
|---------|-----------|
| `quantity` | Gelieferte Menge in kg |
| `unit_price` | Preis je Einheit |
| `total_value` | Gesamtwert der Lieferung |
| `delay_minutes` | Verzögerung gegenüber Plantermin |
| `avg_temperature` | Durchschnittstemperatur über alle GPS-Punkte der Route |
| `num_hops` | Anzahl Supply-Chain-Stationen |
| `on_time_flag` | Boolean: `delay_minutes <= 0` |

**Analytische Views:**
- `dwh.v_carrier_performance` – Durchschnittliche Verzögerung und Anzahl Lieferungen je Carrier
- `dwh.v_kpi_summary` – Aggregierte KPIs (Liefertreue, Ø Umsatz, Temperaturausreißer)
- `dwh.v_monthly_revenue` – Monatlicher Umsatz aggregiert

---

### `sql/08_data_quality_checks.sql` – Datenqualitätsprüfungen (41 Checks)

Jeder Check gibt `'PASS'` oder `'FAIL'` zurück. 6 DQ-Dimensionen:

| Dimension | Kürzel | Beispiel-Check |
|-----------|--------|----------------|
| Vollständigkeit | VQ | `supplier_name IS NULL` → 0 Zeilen erwartet |
| Eindeutigkeit | EQ | `supplier_code` UNIQUE → keine Duplikate |
| Konsistenz | KQ | `delivery_status = 'SUCCESSFUL'` nur wenn `delay_minutes` vorhanden |
| Plausibilität | PQ | `avg_temperature` zwischen 10 und 15 °C (Kühlkette) |
| Aktualität | AQ | `event_timestamp` darf nicht in der Zukunft liegen |
| Referenzielle Integrität | RI | alle `shipment_id` in `deliveries` existieren in `shipments` |

**Erwartetes Ergebnis:** 38/41 PASS (93 %). 3 bewusste FAILs:
- `PQ-4.10`: GPS-Koordinaten sind weltweit zufällig → kein geografischer Routenkorridor
- `KQ-6.3`: `delivery_status = 'SUCCESSFUL'` vs. `delay_minutes > 0` → bewusste Inkonsistenz im Generator
- `KQ-6.4`: `carrier_mode` stimmt nicht mit Transportstrecke überein (Datengenerator-Limitierung)

**Ausführen:**
```bash
docker exec -i postgres psql -U user -d logistics < sql/08_data_quality_checks.sql
```

---

### `sql/08b_dq_audit.sql` – Konsolidierter DQ-Audit

Führt alle 41 Checks als einzelnes Result-Set aus. Nützlich für die Dokumentation der Prüfergebnisse.

---

### `sql/09_verification_queries.sql` – Befüllungsnachweise

Enthält COUNT(*)-Abfragen für alle Tabellen, FK-Integritätsprüfungen und DWH-Plausibilitätschecks. Dient als abschließender Nachweis, dass alle ETL-Schritte erfolgreich waren.

**Ausführen:**
```bash
docker exec -i postgres psql -U user -d logistics < sql/09_verification_queries.sql
```

**Erwartete Ergebnisse:**

| Tabelle | Erwartete Zeilen |
|---------|-----------------|
| `erp.suppliers` | 10 |
| `erp.customers` | 10 |
| `erp.products` | 10 |
| `erp.orders` | 10 |
| `erp.order_items` | 10 |
| `erp.batches` | 10 |
| `wms.warehouse_skus` | 10 |
| `wms.supply_chain_nodes` | 6 |
| `wms.node_processings` | 60 |
| `tms.carriers` | 5 |
| `tms.shipments` | 60 |
| `tms.shipment_positions` | 112+ |
| `tms.transport_completions` | 60 |
| `tms.deliveries` | 10 |
| `dwh.dim_date` | 1095 |
| `dwh.fact_fulfillment` | 10 |

---

### `sql/00_sql_cheatsheet.sql` – Referenz-Queries

Nützliche SQL-Schnipsel für häufige Abfragen: JOIN-Beispiele über Schema-Grenzen, MDM-Auflösung, DWH-Aggregationen. Wird nicht ausgeführt, nur als Nachschlagewerk verwendet.

---

## 6. Python-Skripte in `bananasupplychain/`

### `etl_load.py` – ETL Phase 1 (Hauptskript)

**Was es tut:** Liest alle 385 JSON-Events aus `shared/erp/`, `shared/wms/`, `shared/tms/` und lädt sie in PostgreSQL, MongoDB, Redis und Neo4j.

**Ausführen (immer aus Repo-Root!):**
```bash
python3 bananasupplychain/etl_load.py
```

**Interne Struktur:**

```
etl_load.py
├── normalize_key()          ← MDM: BAN_101 → BAN-101
├── safe_float() / safe_int() ← Typkonvertierung
├── Timestamp-Offset-Logik   ← Realistische Zeitverteilung je Iteration/Route
│
├── load_postgresql()        ← Schreibt in erp/wms/tms-Schemas
│   ├── SupplierCreated → erp.suppliers
│   ├── CustomerCreated → erp.customers
│   ├── ProductCreated  → erp.products
│   ├── OrderCreated    → erp.orders + erp.order_items
│   ├── BatchHarvested  → erp.batches
│   ├── WarehouseSKUCreated → wms.warehouse_skus
│   ├── NodeProcessed   → wms.node_processings
│   ├── CarrierCreated  → tms.carriers
│   ├── TransportProductReferenceCreated → tms.transport_product_refs
│   ├── ShipmentStarted → tms.shipments
│   ├── ShipmentPositionUpdated → tms.shipment_positions
│   ├── TransportCompleted → tms.transport_completions
│   └── DeliveryCompleted  → tms.deliveries
│
├── load_mongodb()           ← Schreibt in 4 Collections
│   ├── shipment_events      ← 1 Dokument pro Shipment (Lifecycle: alle Positions + Completion)
│   ├── node_events          ← 1 Dokument pro NodeProcessed-Event
│   ├── batch_tracking       ← 1 Dokument pro Batch (alle Knotendurchläufe eingebettet)
│   └── order_events         ← 1 Dokument pro OrderCreated
│
├── load_redis()             ← Schreibt 7 Key-Typen
│   ├── STRING: shipment:<id>:status
│   ├── HASH:   shipment:<id>:details
│   ├── LIST:   shipment:<id>:positions
│   ├── SORTED SET: shipment:route (Score = timestamp)
│   ├── COUNTER: active_shipments (INCR/DECR)
│   ├── Produktcache: product:<code>
│   └── DailyCounter: orders_today (EXPIREAT Mitternacht)
│
└── load_neo4j()             ← Schreibt Nodes + Relationships
    ├── Supplier, Customer, Product, Carrier-Nodes (Stammdaten)
    ├── Batch-Node mit HARVESTED_BY → Supplier
    ├── Shipment-Node mit CARRIES → Carrier, TRANSPORTS → Batch
    ├── TRANSPORTED_VIA → Shipment (aus TransportStarted)
    └── DELIVERED_TO → Customer (aus DeliveryCompleted)
```

**Idempotenz:** Alle INSERT-Befehle verwenden `ON CONFLICT DO NOTHING`. Das Skript kann mehrfach ausgeführt werden, ohne Duplikate zu erzeugen.

---

### `etl_dwh.py` – ETL Phase 2 (DWH-Befüllung)

**Was es tut:** Liest aus den operativen PostgreSQL-Schemas (erp, wms, tms) und befüllt das DWH-Sternschema.

**Ausführen:**
```bash
python3 bananasupplychain/etl_dwh.py
```

**Grain:** 1 Zeile pro Endlieferung (`tms.deliveries`). INNER JOIN auf `tms.deliveries` stellt sicher, dass nur abgeschlossene Lieferketten ins DWH fließen (kein LEFT JOIN, der zu 60 statt 10 Facts führen würde – Fehler F-9 aus der Vergangenheit).

**Ablauf:**
1. Dimensionen befüllen: `dim_customer`, `dim_supplier`, `dim_product`, `dim_carrier`, `dim_route`, `dim_supply_chain_node`
2. `fact_fulfillment` befüllen: JOIN über erp.orders, erp.order_items, tms.shipments, tms.deliveries
3. `on_time_flag` berechnen: `delay_minutes <= 0`

---

### `generate_documents.py` – MinIO-Dokumentengenerator

**Was es tut:** Erzeugt PDF-Dokumente aus den PostgreSQL-Daten und lädt sie in MinIO hoch. Speichert die Objektreferenzen (Bucket + Pfad) zurück in PostgreSQL.

**Ausführen:**
```bash
python3 bananasupplychain/generate_documents.py
```

**Erzeugte Dokumente (2.444 PDFs):**

| Bucket | Inhalt | Anzahl | Auslöser |
|--------|--------|--------|---------|
| `invoices` | Rechnungen an Kunden | 8 | OrderCreated |
| `delivery-notes` | Lieferscheine | 60 | DeliveryCompleted |
| `transport-docs` | Bill of Lading + Zollfreigaben | 10 + 10 | ShipmentStarted |
| `batch-certificates` | Qualitätszertifikate für Chargen | 10 | BatchHarvested |

**Referenzierungsmuster:** PostgreSQL speichert **nur** den Objektpfad (z.B. `delivery-notes/2026/01/DN-SHP-abc123.pdf`), nie das Dokument selbst. So bleibt die Datenbank schlank, und das PDF liegt in MinIO.

---

### `verify_all_systems.py` – Systemverifikation

**Was es tut:** Verbindet sich mit allen 5 Datenbanken und führt technische Prüfungen durch. Gibt `PASS`/`FAIL` je Prüfung aus.

**Ausführen:**
```bash
python3 bananasupplychain/verify_all_systems.py
```

**Geprüfte Aspekte:**
- MongoDB: Collection-Counts, TTL-Index vorhanden, Index auf `batch_id + node_id`
- Redis: Key-Typen korrekt, TTLs gesetzt
- Neo4j: Node-Counts je Typ, Relationship-Counts, 6-Hop-Pfad PLANTATION → RETAIL
- MinIO: Alle 4 Buckets vorhanden, Objektanzahl korrekt

---

### `test_data_generator.py` – Datengenerator (anpassbar, mit Dokumentationspflicht)

Erzeugt die JSON-Quelldaten. **Anpassung erlaubt.** Jede Änderung am Generator muss in `PROJECT_STATUS.md`, `README.md` und dieser Anleitung dokumentiert werden. Aktuelle Generator-Anpassungen: 52-Wochen-Zeitreihe, variable Bestellungen pro Woche, Kühlkettenausreißer, fester Seed für stabile Werteverteilungen, Produktkategorien `Standard`, `Sustainable`, `Premium`, `Specialty` sowie das **Transport-Kern-Set [ANPASSUNG 2026-07-01]**: Distanz je Route (`distance_km`), modusgerechte Carrier-Zuordnung mit konsistenter `carrier_id` (Land→TRUCK, See→SEA_FREIGHT), Transportkosten je Leg (`transport_cost`/`currency`), Plan/Ist-konsistente Zeiten (`estimated_arrival` = Plan, Ist = Plan + `delay_minutes`, carrier-spezifische Verzögerung) und Verspätungsgrund (`delay_reason`), sowie **Block 2 [ANPASSUNG 2026-07-01]**: realistische GPS-Positionen (Interpolation zwischen den Knoten Ghana→Rotterdam→Deutschland, modusabhängige Geschwindigkeit → Power-BI-Geokarte) und deterministische UUIDs/Dateinamen (geseedeter RNG `det_uuid()` → Läufe reproduzierbar, kein Akkumulieren beim Re-Load), sowie **Kunden-Segmente + Preis-nach-Kategorie [ANPASSUNG 2026-07-01]**: `customer_type` (DISCOUNTER/VOLLSORTIMENTER/PREMIUM) mit festem Verhaltensprofil (gewichtete Bestellhäufigkeit, segment-abhängige Menge/Kategorie) und `unit_price` nach Produktkategorie (Standard<Sustainable<Specialty<Premium) → schaltet Clustering + Umsatz-Analysen frei; `customer_type` läuft bis `dwh.dim_customer`. Hinweis: `etl_dwh` leert die Dimensionen vor dem Laden, damit Quelländerungen übernommen werden. Weiter **Kühlkette→Qualität [ANPASSUNG 2026-07-02]**: aus den Knoten-Temperaturen eines Batches werden `quality_status` (OK/REDUCED/REJECTED) und `spoilage_pct` abgeleitet (Kühlkettenbruch = außerhalb 10–15 °C) → Felder in `erp.batches`, View `dwh.v_batch_quality` (Qualitätsrate + Schwund je Woche) für KPI Batchqualitätsrate und Chart „Batchqualität über Zeit". Da `shared/` alle fünf Zielsysteme speist, nach jeder Änderung `shared/` neu erzeugen **und** den vollständigen ETL-Lauf wiederholen. Daten neu generieren:
```bash
# ganze Verzeichnisse löschen (nicht per Glob shared/erp/* – bei ~6.000 Dateien sonst "argument list too long")
rm -rf shared/erp shared/wms shared/tms
python3 bananasupplychain/test_data_generator.py
```

---

## 7. Neo4j Graphmodell (`cypher/`)

### `cypher/01_create_graph_model.cypher`

**Was es tut:** Legt Constraints, Indizes und Beispieldaten für das Neo4j-Graphmodell an.

Das Graphmodell muss **vor** dem ETL (etl_load.py) nicht manuell eingerichtet werden – `etl_load.py` schreibt Nodes und Relationships direkt. Das Cypher-Skript dient als:
1. Dokumentation der Graphstruktur
2. Manuelle Initialisierung falls Docker-Volume geleert wurde
3. Demonstration der Beispiel-Queries

**8 Node-Typen:**

| Node | Bedeutung | Beispiel-Property |
|------|-----------|-------------------|
| `Supplier` | Lieferant | `supplier_code: 'SUP-101'` |
| `Customer` | Kunde | `customer_code: 'CUST-101'` |
| `Product` | Produkt | `product_code: 'BAN-101'` |
| `Batch` | Ernte-Charge | `batch_id: 'BATCH-...'` |
| `Carrier` | Transportunternehmen | `carrier_code: 'CAR-101'` |
| `Shipment` | Einzelsendung | `shipment_code: 'SHP-...'` |
| `Order` | Kundenbestellung | `order_code: 'ORD-...'` |
| `SupplyChainNode` | Station | `name: 'banana_plantation'` |

**13 Relationship-Typen:**
`SUPPLIES`, `ORDERS_FROM`, `CONTAINS`, `HARVESTED_BY`, `PROCESSES`, `TRANSPORTED_VIA`, `CARRIES`, `TRANSPORTS`, `PROCESSED_AT`, `DELIVERS_TO`, `DELIVERED_TO`, `PART_OF`, `REFERENCES`

**Wichtigste Abfrage – 6-Hop-Pfad:**
```cypher
MATCH path = (start:SupplyChainNode {name: 'banana_plantation'})
             -[:PROCESSED_AT*1..8]-
             (end:SupplyChainNode {name: 'retail_store'})
RETURN path LIMIT 1
```

**Warum Neo4j?** SQL-Rekursion für mehrstufige Lieferkettenpfade ist aufwendig und langsam. Neo4j traversiert denselben 6-Hop-Pfad in <10 ms, unabhängig von der Datenmenge.

---

### `cypher/02_verification_queries.cypher`

Aktive Verifikationsqueries:
- `MATCH (n) RETURN labels(n), count(*)` – Node-Counts je Typ
- `MATCH ()-[r]->() RETURN type(r), count(*)` – Relationship-Counts
- Constraints und Indizes prüfen
- 6-Hop-Pfad PLANTATION → RETAIL
- Fulfillment-Kette (SUPPLIES → CARRIES → DELIVERED_TO)
- Kühlketten-Monitoring (GPS-Temperatur über 15 °C)

**Ausführen über Neo4j Browser (http://localhost:7474)** oder per `cypher-shell`:
```bash
docker exec -i neo4j cypher-shell -u neo4j -p password < cypher/02_verification_queries.cypher
```

---

## 8. Analytics (`analytics/`)

Die drei Analytics-Skripte lesen aus dem PostgreSQL-DWH (`dwh`-Schema) und erzeugen Visualisierungen.

**Voraussetzung:** ETL Phase 2 (`etl_dwh.py`) muss zuerst ausgeführt worden sein.

### `analytics/dashboard.py` – 5 BI-Charts

**Ausführen:**
```bash
python3 analytics/dashboard.py
```

**Erzeugte Dateien:** `analytics/dashboard.pdf`, `analytics/dashboard.png`, `analytics/dashboard.html`

**5 Charts:**

| Chart | Typ | Fachliche Aussage |
|-------|-----|-------------------|
| 1 | Zeitreihe | Umsatz pro Woche – Trend und Saisonalität erkennbar |
| 2 | Balkendiagramm | Carrier-Performance: Ø Verzögerung und Lieferanzahl je CAR-1xx |
| 3 | Balkendiagramm | Umsatz nach Produkt (BAN-101 vs. BAN-110) |
| 4 | Balkendiagramm | Durchschnittliche Verzögerung je Supply-Chain-Knoten |
| 5 | Zeitreihe | Kühlketten-Qualität: Anteil Temperaturausreißer (> 15 °C) pro Woche |

---

### `analytics/clustering.py` – k-Means Kundensegmentierung

**Ausführen:**
```bash
python3 analytics/clustering.py
```

**Erzeugte Dateien:** `analytics/clustering.pdf`, `analytics/clustering.png`

**Methode:**
1. Features: Bestellhäufigkeit, Ø Bestellwert, Ø Verzögerung, Liefertreue
2. Elbow-/Silhouette-Diagnose für k=1 bis k=5 berechnen
3. k-Means mit fachlich gewähltem k=3 ausführen (10 Kunden, keine Mini-Cluster)
4. Business-Interpretation als Scatterplot: Ø Bestellwert vs. Ø Verzögerung
5. Cluster-Steckbrief mit Wert, Delay, Liefertreue und fachlichem Label

**Beispiel-Segmente:**
- Segment A: Großkunden mit hohem Bestellwert, wenig Verzögerungen
- Segment B: Kleinkunden, frequent, preissensitiv

---

### `analytics/forecast.py` – ARIMA Absatzprognose

**Ausführen:**
```bash
python3 analytics/forecast.py
```

**Erzeugte Dateien:** `analytics/forecast.pdf`, `analytics/forecast.png`, `analytics/forecast_model_summary.txt`

**Methode:**
- Modell: ARIMA(1,0,1)
- Datenbasis: 13 echte Monate aus `dwh.v_monthly_revenue` + 24 Monate synthetische Vorlauf-History (transparent als solche markiert)
- Prognose: 3 Monate voraus mit 95%-Konfidenzintervall
- Bewertungsmetriken: RMSE und MAE als In-Sample-Fit-Fehler auf den echten Monaten im Chart ausgewiesen
- Hinweis: Erster und letzter echter Monat sind Randmonate der 52-Wochen-Zeitreihe; mit längerer echter Historie wird die Prognose belastbarer.

**Hinweis R-4 aus PROJECT_STATUS.md:** Der Datengenerator erzeugt inzwischen eine 52-Wochen-Zeitreihe mit mehreren Bestellungen pro Woche. Ältere Analytics-Hilfsdaten bzw. synthetische Historien sind nach einem Generator-Refresh zu prüfen und ggf. zu ersetzen.

---

## 9. Dokumentation (`docs/`)

Alle 14 Dokumente sind in Deutsch verfasst und referenzieren konkrete Projektdaten (kein generischer Text).

### `docs/00_part1_checklist.md` – Anforderungsabgleich

Vollständige Checkliste aller Pflichtanforderungen aus der `Aufgabenstellung.pdf`. Status: ✅ Erfüllt / ⚠️ Teilweise / ❌ Offen. Dient als Nachweis gegenüber dem Prüfer.

**Kategorien:** Infrastruktur, Datenklassifikation, PostgreSQL-Modelle, MDM, Metadaten, DQ, DWH, MongoDB, Redis, Neo4j, MinIO, ETL.

---

### `docs/01_data_classification.md` – Datenklassifikation

Klassifiziert alle **13 Eventtypen** nach:
- Datenart (Stamm-, Bewegungs-, Event-, Echtzeit-, Dokumentdaten)
- Primäre und sekundäre Zieldatenbank
- Wichtigste Felder mit JSON-Beispiel

Enthält außerdem die Abgrenzung zu Bestandsdaten und Metadaten, sowie die Begründung warum bestimmte Events in bestimmte Systeme gehen.

---

### `docs/02_target_architecture.md` – Zielarchitektur

Beschreibt die Gesamtarchitektur mit Mermaid-Diagramm. Beantwortet: Welches System bekommt welche Daten und warum?

**Kernargumente:**
- PostgreSQL: ACID-Transaktionen, FK-Integrität, SQL-Analysen
- MongoDB: Heterogene Event-Dokumente, kein NULL-Overhead, eingebettete Lifecycle-Dokumente
- Redis: Sub-Millisekunden-Latenz, TTL-native, GPS-Tracking in Echtzeit
- Neo4j: Pfadabfragen, Netzwerkanalyse, Supply-Chain-Tracing ohne rekursives SQL
- MinIO: BLOB-Größe außerhalb der DB, S3-kompatibel, Versionierung

---

### `docs/03_er_model.md` – ER-Modell

Vollständiges Entity-Relationship-Modell in Mermaid-Syntax für alle 15 PostgreSQL-Tabellen (erp + wms + tms). Enthält:
- Alle PKs und FKs
- Kardinalitäten (1:1, 1:N, M:N)
- Cross-Schema-Beziehungen (z.B. `tms.deliveries` → `erp.orders`)
- Begründungen aus dem Supply-Chain-Kontext

**Lesen:** `erp.orders ||--|{ erp.order_items` bedeutet: Eine Order hat 1 bis N Order-Items.

---

### `docs/04_masterdata_management.md` – MDM-Konzept

Beschreibt das MDM-System mit:
- Problem: 3 verschiedene Schlüsselformate für dasselbe Produkt
- Lösung: Golden Records in `mdm.golden_records` + `resolve_canonical_key()`
- Normalisierungsalgorithmus: `key.strip().lower().replace("_", "-").upper()`
- Alle 42 Golden Records mit Herkunft
- Edge Cases: NULL-Handling, ETL-Reihenfolge (Stammdaten müssen vor Bewegungsdaten geladen werden)
- Diagnose-Queries für nicht-harmonisierte Schlüssel in WMS und TMS

---

### `docs/05_metadata_management.md` – Metadatenmanagement

Beschreibt alle Skalenniveaus für alle 168 Spalten aus allen Tabellen. Enthält:
- Definition aller 4 Skalenniveaus mit Projektbeispielen
- Begründungen für jede Klassifikation
- Vollständige Tabelle aller Schlüsselspalten mit Qualitätsregeln
- Tabellen-Steckbriefe für alle 4 Hauptsysteme

---

### `docs/06_data_quality.md` – DQ-Framework

Beschreibt alle **34 Datenqualitätsregeln** gegliedert nach 6 Dimensionen. Je Regel:
- Regel-ID (z.B. `VQ-01`)
- Beschreibung mit Supply-Chain-Bezug
- SQL-Check-Referenz (auf `sql/08_data_quality_checks.sql`)
- Erwartetes Ergebnis

Enthält auch das DQ-Dashboard (Übersicht: 38/41 PASS) und die Erklärung der 3 erwarteten FAILs.

---

### `docs/07_dwh_model.md` – DWH-Sternschema

Vollständige Dokumentation des Data Warehouse mit:
- Sternschema-Diagramm (Mermaid)
- Grain-Begründung (1 Zeile = 1 Endlieferung)
- ETL-Übergänge: welche Quelle liefert welche Dimension/Measure
- Die 3 analytischen Views mit Beispielabfragen
- PowerBI-Abschnitt: Datenquelle, Measures, Visuals, Slicer
- Prüfqueries zum Nachweis der korrekten Befüllung

---

### `docs/08_mongodb_event_model.md` – MongoDB-Eventmodell

Beschreibt die 4 MongoDB-Collections mit:
- Schema-Beispiel je Collection (eingebettetes JSON)
- Lifecycle-Modell für `shipment_events` (1 Dokument pro Shipment, alle Positionsupdates eingebettet)
- TTL-Index auf GPS-Events (90 Tage)
- Indizes: Compound Index auf `batch_id + node_id` in `node_events`
- Begründung: MongoDB vs. PostgreSQL für Eventdaten

---

### `docs/09_redis_realtime_model.md` – Redis-Echtzeitmodell

Beschreibt alle **7 Key-Typen** mit vollständiger Key-Taxonomie:

| Key-Muster | Typ | TTL | Inhalt |
|------------|-----|-----|--------|
| `shipment:<id>:status` | STRING | 24h | Aktueller Status |
| `shipment:<id>:details` | HASH | 6h | Alle Felder als Hash |
| `shipment:<id>:positions` | LIST | 24h | GPS-Koordinaten LIFO |
| `shipment:route` | SORTED SET | 7 Tage | Score = Timestamp |
| `active_shipments` | COUNTER | – | INCR/DECR je Start/Ende |
| `product:<code>` | HASH | 1h | Produktcache |
| `orders_today` | COUNTER | bis Mitternacht | EXPIREAT |
| `monitoring:temp_violations:<date>` | STRING | 7 Tage | Anzahl Kühlkettenbrüche |

Enthält außerdem Abgrenzungstabelle: Was kommt in Redis, was bleibt in PostgreSQL/MongoDB?

---

### `docs/10_neo4j_graph_model.md` – Neo4j-Graphmodell

Beschreibt alle 8 Node-Typen und 13 Relationship-Typen mit:
- Cypher-Beispielabfragen
- Produktions-Lieferanten-Tabelle (welches Produkt kommt von welchem Supplier)
- Vergleich Neo4j vs. SQL für Pfadabfragen
- Der wichtigste Pfad: PLANTATION → COLLECTION_CENTER → QUALITY_CONTROL → AFRICA_COLD_STORAGE → EUROPE_COLD_STORAGE → CENTRAL_WAREHOUSE → RETAIL (6 Hops)

---

### `docs/11_minio_document_model.md` – MinIO-Dokumentmodell

Beschreibt den Objektspeicher mit:
- 4 Buckets und deren Inhalte
- Referenzierungsmuster: PostgreSQL ↔ MinIO
- Bucket-Versionierung (aktiviert für `batch-certificates`)
- Object-Tags (document_type, shipment_id, created_at)
- Zwei-Phasen-Ansatz: ETL Phase 1 lädt keine PDFs, generate_documents.py ist der einzige MinIO-Einstiegspunkt
- 6 Prüfqueries

**Begründung MinIO statt BLOB:** BLOBs in PostgreSQL blähen die DB auf, verlangsamen Backups und sind nicht HTTP-streambar. MinIO bietet S3-kompatibles HTTP-Streaming, Versionierung und Metadaten.

---

### `docs/12_etl_concept.md` – ETL-Konzept

Vollständiges ETL-Konzept mit:
- Architekturdiagramm (Extract → Transform → Load)
- Ausführungsreihenfolge aller 6 Schritte
- **Vollständige Mapping-Tabelle:** Für jeden der 13 Eventtypen: Quell-Feld → Transformation → Ziel-Tabelle/Spalte
- Idempotenz-Beschreibung für PostgreSQL, MongoDB, Redis und Neo4j
- ETL-Nachweise: erwartete Record-Counts je System
- Abgrenzung ETL Phase 1 (operative Schemas) vs. ETL Phase 2 (DWH)

---

### `docs/13_data_quality_results.md` – DQ-Audit-Ergebnisse

Dokumentiert die tatsächlichen Prüfergebnisse nach Ausführung von `sql/08b_dq_audit.sql`:
- 38/41 PASS (93 %)
- Detaillierte Erklärung der 3 FAILs (was erwartet wurde, was tatsächlich kam, warum das akzeptabel ist)
- Tabellarische Ergebnisübersicht aller 41 Checks

---

## 10. Vollständige Ausführungsreihenfolge (Schritt für Schritt)

> **Alle Befehle immer aus dem Repo-Root ausführen** (`gruppe7_dma_sose26/`), nicht aus Unterordnern.

### Schritt 0: Voraussetzungen prüfen

```bash
# Docker Desktop muss laufen
docker --version

# Python-Pakete installieren (feste Versionen aus der getesteten Umgebung)
pip install -r requirements.txt
# Alternativ ohne Versionsbindung:
# pip install psycopg2-binary pymongo redis neo4j minio reportlab pandas numpy matplotlib seaborn plotly scikit-learn statsmodels
```

---

> **⚠️ Immer nur EINEN Docker-Stack starten.** Neben diesem produktiven Stack `bananasupplychain/container/` liegt die unveränderte Dozenten-Vorlage `databasemodels_logistics_playground/container/`. Beide haben **dieselben** `container_name` und Ports und – weil beide im Ordner `container/` liegen – **denselben** Compose-Projektnamen `container` und damit **dieselben** Volumes (`container_postgres_data` …). Startet man beide, kollidieren Namen/Ports; startet man die Vorlage nacheinander, schreibt ihr `initialize_db.py` ein fremdes Demo-Schema (Orders/OrderDetails/Warehouses) in **dieselbe** `logistics`-DB. Für dieses Projekt daher ausschließlich `bananasupplychain/container` starten, nie den Playground.

### Schritt 1: Docker-Container starten

```bash
cd bananasupplychain/container && docker compose up -d && cd ../..
docker ps   # alle 6 Container müssen 'Up' zeigen
```

Warten bis PostgreSQL bereit ist (ca. 10 Sekunden):
```bash
docker logs postgres 2>&1 | tail -5
# Erwartete Ausgabe: "database system is ready to accept connections"
```

---

### Schritt 2: PostgreSQL-Schemas anlegen (nur bei Erstaufbau oder nach Volume-Reset)

```bash
docker exec -i postgres psql -U user -d logistics < sql/01_create_schemas.sql
docker exec -i postgres psql -U user -d logistics < sql/02_create_erp_tables.sql
docker exec -i postgres psql -U user -d logistics < sql/03_create_wms_tables.sql
docker exec -i postgres psql -U user -d logistics < sql/04_create_tms_tables.sql
docker exec -i postgres psql -U user -d logistics < sql/05_create_mdm_tables.sql
docker exec -i postgres psql -U user -d logistics < sql/06_create_metadata_tables.sql
docker exec -i postgres psql -U user -d logistics < sql/06b_metadata_complete.sql
docker exec -i postgres psql -U user -d logistics < sql/07_create_dwh_schema.sql
```

**Prüfen:**
```bash
docker exec -i postgres psql -U user -d logistics -c "\dn"
# Erwartet: erp, wms, tms, mdm, meta, dwh, public
```

---

### Schritt 3: Testdaten generieren (optional, nur wenn neue JSONs gewünscht)

```bash
# Vorher alte Daten löschen (optional)
rm -rf shared/erp/* shared/wms/* shared/tms/*

python3 bananasupplychain/test_data_generator.py
```

**Prüfen:**
```bash
ls shared/erp/ | wc -l    # 534
ls shared/wms/ | wc -l    # 1.522
ls shared/tms/ | wc -l    # 6.300
```

---

### Schritt 4: ETL Phase 1 – JSON-Events in alle Datenbanken laden

```bash
python3 bananasupplychain/etl_load.py
```

**Erwartete Ausgabe:**
```
ERP: 534 Events verarbeitet
WMS: 1.522 Events verarbeitet
TMS: 6.300 Events verarbeitet
PostgreSQL: 10 Suppliers, 10 Customers, 10 Products, 252 Orders, 1.512 Shipments geladen
MongoDB: 1.512 shipment_events, 1.512 node_events, 252 batch_tracking, 252 order_events
Redis: alle Key-Typen gesetzt
Neo4j: Nodes und Relationships angelegt
```

---

### Schritt 5: Logistikdokumente in MinIO

```bash
python3 bananasupplychain/generate_documents.py
```

**Erwartete Ausgabe:** 2.444 PDFs hochgeladen (1.512 + 176 + 252 + 252 + 252)

---

### Schritt 6: ETL Phase 2 – DWH-Sternschema befüllen

```bash
python3 bananasupplychain/etl_dwh.py
```

**Prüfen:**
```bash
docker exec -i postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM dwh.fact_fulfillment;"
# Erwartet: 10
docker exec -i postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM dwh.dim_date;"
# Erwartet: 1095
```

---

### Schritt 7: Verifikation aller Systeme

```bash
docker exec -i postgres psql -U user -d logistics < sql/09_verification_queries.sql
docker exec -i postgres psql -U user -d logistics < sql/08_data_quality_checks.sql
python3 bananasupplychain/verify_all_systems.py
```

---

### Schritt 8: Analytics ausführen

```bash
python3 analytics/dashboard.py
python3 analytics/clustering.py
python3 analytics/forecast.py
```

**Erzeugte Ausgaben in `analytics/`:**
- `dashboard.pdf`, `dashboard.png`, `dashboard.html`
- `clustering.pdf`, `clustering.png`
- `forecast.pdf`, `forecast.png`, `forecast_model_summary.txt`

---

## 11. Datenpfade: Wie ein Event durch das System fließt

### Beispiel: `ShipmentStarted`-Event (TMS)

**1. Quelle:**
```
shared/tms/supplychain_iteration_001_shipmentstarted_uuid.json
{
  "event_type": "ShipmentStarted",
  "shipment_id": "SHP-abc123",
  "carrier_code": "CAR-101",
  "route": "banana_plantation_to_collection_center",
  "product_code": "ban-101",
  "timestamp": "2026-01-05T08:23:00"
}
```

**2. Extract** (`etl_load.py`):
- JSON-Datei gelesen und als dict geparst

**3. Transform** (`etl_load.py`):
- `normalize_key('ban-101')` → `'BAN-101'`
- Timestamp-Offset berechnet (Iteration 001, Route 0, Day 0.58–0.75)
- `carrier_code` validiert (muss in `tms.carriers` existieren)

**4. Load in PostgreSQL** (`tms.shipments`):
```sql
INSERT INTO tms.shipments (shipment_code, carrier_id, route, status, event_timestamp)
VALUES ('SHP-abc123', 1, 'banana_plantation_to_collection_center', 'IN_TRANSIT', '2026-01-05T08:23:00')
ON CONFLICT (shipment_code) DO NOTHING;
```

**5. Load in Neo4j**:
```cypher
MERGE (s:Shipment {shipment_code: 'SHP-abc123'})
MERGE (c:Carrier {carrier_code: 'CAR-101'})
MERGE (s)-[:CARRIES]->(c)
```

**6. Load in Redis** (erst bei `ShipmentPositionUpdated`):
```
SET shipment:SHP-abc123:status "IN_TRANSIT" EX 86400
```

**7. In MongoDB** (aggregiert bei `DeliveryCompleted`):
```json
{
  "shipment_code": "SHP-abc123",
  "events": [
    {"type": "ShipmentStarted", "timestamp": "..."},
    {"type": "PositionUpdated", "lat": 5.6, "lon": -0.2, "temp": 13.2},
    {"type": "TransportCompleted", "delay_minutes": 45}
  ]
}
```

**8. In DWH** (über `etl_dwh.py`):
- Geht in `fact_fulfillment` ein, verknüpft über `dim_carrier`, `dim_route`

---

## 12. Zugriff auf die Datenbanken

### PostgreSQL (psql)
```bash
docker exec -it postgres psql -U user -d logistics
# SQL-Befehl:
\dt erp.*        # Tabellen im erp-Schema
SELECT COUNT(*) FROM erp.suppliers;
```

### MongoDB (mongosh)
```bash
docker exec -it mongodb mongosh
use logistics
db.shipment_events.countDocuments()
db.shipment_events.findOne()
```

### Redis (redis-cli)
```bash
docker exec -it redis redis-cli
KEYS shipment:*:status
GET shipment:SHP-abc123:status
TTL shipment:SHP-abc123:status
```

### Neo4j (Browser)
URL: http://localhost:7474  
Login: neo4j / password  
```cypher
MATCH (n) RETURN labels(n), count(*) ORDER BY count(*) DESC
MATCH (s:SupplyChainNode)-[r]->(t:SupplyChainNode) RETURN s.name, type(r), t.name
```

### MinIO (Web Console)
URL: http://localhost:9001  
Login: admin / password  
Oder per mc (MinIO Client):
```bash
mc alias set local http://localhost:9000 admin password
mc ls local/delivery-notes/
```

---

## 13. Bekannte Fehler und deren Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `git: .git/index.lock` | VS Code und git greifen gleichzeitig zu | `rm .git/index.lock` |
| `etl_load.py` wirft FK-Fehler bei Carriers | Carrier-Events nicht vor Shipment-Events geladen | Reihenfolge: ETL liest `iteration_000_*` vor `iteration_001_*` – ist bereits so implementiert |
| MongoDB zeigt viele flache Dokumente (1 pro Event) statt Lifecycle-Dokumente (1 pro Shipment) | `db.shipment_events.drop()` nicht ausgeführt vor Re-Run | `docker exec -it mongodb mongosh --eval "db.shipment_events.drop()"` und ETL neu ausführen |
| PostgreSQL: `relation "erp.batches.order_id" does not exist` | Alter SQL-Code mit entfernter Spalte | Prüfen ob `sql/02_create_erp_tables.sql` aktuell ist (kein `order_id` in `batches`) |
| DQ-Check 6.3 immer FAIL | Datengenerator-Inkonsistenz: `status = SUCCESSFUL` aber `delay_minutes > 0` | Dokumentiertes, erwartetes FAIL – kein Fehler im Code |
| `verify_all_systems.py` FAIL Neo4j 6-Hop-Pfad | ETL-Load hat PROCESSED_AT-Kanten nicht vollständig angelegt | `etl_load.py` erneut ausführen; prüfen ob Cypher-Skript `cypher/01_create_graph_model.cypher` manuell eingespielt werden muss |

---

## 14. Checkliste vor der Abgabe

### Teil 1: Datenmanagement

- [ ] Docker-Container starten und alle 6 Dienste aktiv
- [ ] SQL 01–08 ohne Fehler ausgeführt
- [ ] `test_data_generator.py` ausgeführt: 534 + 1.522 + 6.300 JSON-Dateien vorhanden
- [ ] `etl_load.py` ausgeführt: alle Records in PostgreSQL, MongoDB, Redis, Neo4j
- [ ] `generate_documents.py` ausgeführt: 2.444 PDFs in MinIO
- [ ] `etl_dwh.py` ausgeführt: 252 fact_fulfillment-Zeilen, 1095 dim_date-Zeilen
- [ ] `sql/09_verification_queries.sql` zeigt korrekte Counts
- [ ] `sql/08b_dq_audit.sql` zeigt 38/41 PASS
- [ ] `verify_all_systems.py` PASS für alle Systeme
- [ ] MDM: `SELECT mdm.resolve_canonical_key('BAN_101', 'WMS')` gibt `'BAN-101'` zurück
- [ ] Neo4j: 6-Hop-Pfad PLANTATION → RETAIL funktioniert
- [ ] Alle 14 `docs/`-Dateien vorhanden und konsistent

### Teil 2: Analytics

- [ ] `analytics/dashboard.py` ausgeführt: dashboard.pdf vorhanden
- [ ] `analytics/clustering.py` ausgeführt: clustering.pdf vorhanden
- [ ] `analytics/forecast.py` ausgeführt: forecast.pdf + forecast_model_summary.txt vorhanden
- [ ] Deskriptive Statistik (A-1) – **NOCH OFFEN**
- [ ] KPI-Dokumentation (A-2) – **NOCH OFFEN**
- [ ] PowerBI-Dashboard (A-4) – **NOCH OFFEN**
- [ ] Abschlussbericht (A-7) – **NOCH OFFEN**

### Abgabe-Formalien

- [ ] Git-Repository sauber (kein .git/index.lock, keine uncommitted changes)
- [ ] `PROJECT_STATUS.md` aktuell
- [ ] `README.md` spiegelt korrekte Ausführungsreihenfolge wider
- [ ] Alle Python-Abhängigkeiten in `README.md` aufgelistet
- [ ] PowerBI-Verbindungsparameter geprüft (R-2: PostgreSQL localhost:5432)

---

*Letztes Update: 2026-06-02*
