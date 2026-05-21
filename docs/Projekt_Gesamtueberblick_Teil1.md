# Projekt-Gesamtueberblick Teil 1

Projekt: Banana Supply Chain Datenplattform  
Modul: Datenmanagement und Analytics, SoSe 26  
Stand der Analyse: 2026-05-20  
Analyseart: statische Projektanalyse plus lokale Datei-/JSON-Zaehlung. Docker-Container, ETL-Ladevorgaenge und Datenbankinhalte wurden in dieser Review-Runde nicht veraendert.

---

## 1. Executive Summary

Das Projekt bildet eine Banana-Supply-Chain-Datenplattform ab. Aus drei simulierten Quellsystemen werden JSON-Events erzeugt:

- ERP: Lieferanten, Kunden, Produkte, Bestellungen, Ernte-Batches.
- WMS: Lager-SKUs und Prozessschritte entlang der Supply Chain.
- TMS: Carrier, Transportreferenzen, Transporte, GPS-Positionen, Transportabschluesse und Endlieferungen.

Diese JSON-Dateien werden durch Python-ETL-Skripte in mehrere Zielsysteme geladen:

- PostgreSQL fuer relationale ERP-/WMS-/TMS-Modelle, MDM, Metadaten, Data Quality und DWH.
- MongoDB fuer Event- und Tracking-Dokumente.
- Redis fuer Echtzeitstatus, GPS-Tracking, Caches und Counter.
- Neo4j fuer Supply-Chain-Pfade und Beziehungen zwischen Lieferanten, Produkten, Orders, Batches, Shipments und Knoten.
- MinIO fuer generierte PDF-Dokumente wie Lieferscheine, Rechnungen, Transportdokumente und Qualitaetszertifikate.

**Kurzurteil:** Teil 1 ist fachlich und technisch weitgehend umgesetzt. Fuer eine wirklich saubere Abgabe ist das Projekt aber noch **bedingt abgabebereit**, nicht vollstaendig abgabereif. Der Kern ist vorhanden, aber es gibt mehrere inkonsistente Zaehler und veraltete Pruefskripte/Dokumentstellen. Vor Abgabe sollten diese Widersprueche bereinigt werden.

Wichtigste Risiken:

- `README.md` ist noch eine generische GitLab-Vorlage und erklaert das Projekt nicht.
- Es gibt zwei `docker-compose.yml`. Fuer die Abgabe ist die Datei `bananasupplychain/container/docker-compose.yml` relevant; die alte Playground-Compose-Datei kann verwirren.
- `bananasupplychain/verify_all_systems.py` erwartet bei Neo4j offenbar alte oder doppelte Testdaten und kann auf einem sauberen aktuellen Lauf fehlschlagen.
- Mehrere Dokumente widersprechen sich bei erwarteten Zaehlern, z. B. JSON 377 vs. 383, MinIO 98 vs. 116, DWH-Fakten 10 vs. 60.
- Der DWH- und Graph-ETL kann Order, Batch und Shipment nicht exakt fachlich verbinden, weil die TMS-Events keine `order_id` oder `batch_id` enthalten. Die aktuelle Zuordnung ist produktbasiert.
- `bananasupplychain/test_data_generator.py` sollte aus dem Repo-Root gestartet werden. Aus `bananasupplychain/` heraus wuerde er relativ in den falschen `shared/`-Ordner schreiben.
- `bananasupplychain/reorgFolders.py` loescht alle Dateien in `shared/erp`, `shared/wms` und `shared/tms` ohne Rueckfrage.

---

## 2. Architekturueberblick

### Projektziel in einfachen Worten

Das Projekt simuliert eine Bananen-Lieferkette von der Plantage bis zum Einzelhandel. Dabei entstehen Daten in drei operativen Systemen:

- ERP fuer kaufmaennische Daten wie Lieferanten, Kunden, Produkte und Bestellungen.
- WMS fuer Lager- und Prozessdaten entlang der physischen Warenbewegung.
- TMS fuer Transporte, Carrier, GPS-Positionen und Zustellstatus.

Diese Daten werden als JSON-Dateien erzeugt, klassifiziert, in Datenbanken geladen und fuer Datenmanagement, Qualitaetssicherung und Analytics vorbereitet.

### Fachlicher Kontext

Die Supply Chain besteht aus sieben Stationen und sechs Transportabschnitten:

1. `BANANA_PLANTATION`
2. `COLLECTION_CENTER`
3. `QUALITY_CONTROL`
4. `AFRICA_COLD_STORAGE`
5. `EUROPE_COLD_STORAGE`
6. `CENTRAL_WAREHOUSE`
7. `RETAIL_STORE`

Der fachliche Ablauf:

1. ERP legt Stammdaten an: Lieferanten, Kunden, Produkte.
2. ERP erzeugt eine Bestellung und einen Ernte-Batch.
3. WMS verarbeitet den Batch an sechs operativen Stationen.
4. TMS erzeugt je Iteration sechs Transporte, Positionsupdates und Abschluesse.
5. Eine Endlieferung am Retail Store schliesst den Vorgang ab.
6. Dokumente werden aus TMS/WMS-Daten erzeugt und in MinIO abgelegt.
7. DWH und DQ-Checks machen die Daten pruefbar und analysefaehig.

### Technische Architektur

```text
test_data_generator.py
        |
        v
shared/erp/*.json      shared/wms/*.json      shared/tms/*.json
        |                    |                    |
        +--------------------+--------------------+
                             |
                             v
                     etl_load.py
       +-------------+-------------+-------------+-------------+
       |             |             |             |             |
       v             v             v             v             v
 PostgreSQL       MongoDB        Redis         Neo4j       MinIO via
 ERP/WMS/TMS      Events         Realtime      Graph       generate_documents.py
 MDM/Meta/DQ
       |
       v
   etl_dwh.py
       |
       v
 PostgreSQL dwh.*
```

### Verwendete Technologien

- Docker Compose: Startet die technische Infrastruktur.
- PostgreSQL 15: Relationale Datenmodelle, MDM, Metadaten, Data Warehouse, Data Quality.
- MongoDB 7: Flexible Eventdokumente und Tracking.
- Redis 7: Schnelle Echtzeit-Keys, Caches, Counter, GPS-Zustand.
- Neo4j 5: Graphmodell fuer Pfad- und Beziehungsfragen.
- MinIO: S3-kompatibler Object Store fuer PDFs.
- Python: Datengenerator, ETL, Dokumentgenerierung, Verifikation, Reporting.
- SQL: DDL, Views, Funktionen, DQ- und Verification-Queries.
- Cypher: Neo4j-Modell und Graph-Pruefungen.

### Rollen der Datenbanken

| System | Rolle im Projekt | Typische Inhalte |
|---|---|---|
| PostgreSQL | Operative relationale Kernmodelle und DWH | `erp.*`, `wms.*`, `tms.*`, `mdm.*`, `meta.*`, `dwh.*` |
| MongoDB | Eventmodellierung und Dokument-orientierte Historien | `shipment_events`, `node_events`, `batch_tracking`, `order_events` |
| Redis | Echtzeitstatus und schnelle Abfragen | `shipment:status:*`, `shipment:position:*`, `order:status:*`, `cache:product:*` |
| Neo4j | Graphfragen, Supply-Chain-Pfade, Beziehungen | `Supplier`, `Product`, `Order`, `Batch`, `Shipment`, `SupplyChainNode` |
| MinIO | Dokumentenablage | Buckets `invoices`, `delivery-notes`, `transport-docs`, `batch-certificates` |

### Rolle von Docker und Python

Docker stellt die Datenbank- und Speicherinfrastruktur bereit. Python erzeugt Daten, transformiert und laedt sie, erzeugt Dokumente und prueft Systeme. Wichtig: Docker allein erzeugt keine Banana-Daten. Die Daten kommen aus `test_data_generator.py` und den ETL-Skripten.

### Grober Datenfluss

1. `bananasupplychain/test_data_generator.py` erzeugt JSON-Dateien in `shared/erp`, `shared/wms`, `shared/tms`.
2. SQL-DDL-Dateien in `sql/` erstellen Schemata und Tabellen in PostgreSQL.
3. `bananasupplychain/etl_load.py` liest JSON-Dateien und laedt PostgreSQL, MongoDB, Redis und Neo4j.
4. `bananasupplychain/generate_documents.py` erzeugt PDFs und speichert sie in MinIO; PostgreSQL bekommt Referenzen.
5. `bananasupplychain/etl_dwh.py` befuellt das DWH aus PostgreSQL-ERP/WMS/TMS.
6. SQL-, Cypher- und Python-Pruefungen weisen Datenbestand, Modelle und Qualitaetsregeln nach.

---

## 3. Projektstruktur

### Root-Ebene

| Pfad | Zweck | Kategorie | Abgaberelevanz | Zusammenhang |
|---|---|---|---|---|
| `Aufgabenstellung.pdf` | Offizielle Aufgabenstellung fuer Teil 1 und Teil 2. | Doku/Vorgabe | Sehr hoch | Massgeblich fuer Anforderungen. |
| `Projektanleitung_Gruppe7_DMA_SoSe26.pdf` | Projektanleitung/Statusbericht mit Befehlen und Zahlen. | Doku | Hoch, aber teils stale | Enthalt Widersprueche zu aktuellen Dateien. |
| `README.md` | Aktuell generische GitLab-Vorlage. | Doku | Hoch als Risiko | Sollte vor Abgabe projektspezifisch ersetzt werden. |
| `PROJECT_STATUS.md` | Statusuebersicht mit vielen Nachweisen. | Doku | Hoch | Gute Basis, aber Zaehler/Pruefaussagen teils widerspruechlich. |
| `dashboard_plausibility.py` | Erzeugt Plausibilitaets-Dashboard aus PostgreSQL-Daten. | Analytics/Hilfe | Mittel | Nutzt PostgreSQL-Queries; eher Teil 2/Reporting. |
| `dashboard_plausibility.png` | Gerendertes Dashboard-Bild. | Output | Mittel | Ergebnis von `dashboard_plausibility.py`. |
| `create_status_report.py` | Erzeugt Statusbericht per ReportLab. | Hilfsdatei/Doku | Mittel | Dokumentationshilfe, nicht Kern-ETL. |
| `create_guide_pdf.py` | Erzeugt PDF-Guide. | Hilfsdatei/Doku | Mittel | Dokumentationshilfe. |
| `.claude/skills/dma-banana-supply-chain/SKILL.md` | Projektbezogene Arbeitsregeln fuer KI-Unterstuetzung. | Hilfsdatei | Niedrig bis mittel | Enthalt nuetzliche Projektkonventionen, ist aber kein Datenplattform-Artefakt. |
| `.mcp.json`, `.mcp.windows.json` | MCP-Konfiguration. | Hilfsdatei | Niedrig | Entwicklungsumgebung. |

### `bananasupplychain/`

| Pfad | Zweck | Kategorie | Abgaberelevanz | Zusammenhang |
|---|---|---|---|---|
| `bananasupplychain/container/docker-compose.yml` | Haupt-Compose fuer PostgreSQL, MongoDB, Redis, Neo4j, MinIO und Cleanup. | Setup | Sehr hoch | Dies ist die relevante Compose-Datei fuer die Abgabe. |
| `bananasupplychain/test_data_generator.py` | Erzeugt ERP/WMS/TMS-JSON-Dateien. | Simulation/Generator | Sehr hoch | Quelle fuer `shared/*`; nicht ungefragt aendern. |
| `bananasupplychain/etl_load.py` | Laedt JSON nach PostgreSQL, MongoDB, Redis und Neo4j. | ETL | Sehr hoch | Kernskript Teil 1. |
| `bananasupplychain/etl_dwh.py` | Befuellt das DWH in PostgreSQL aus operativen Tabellen. | ETL/DWH | Sehr hoch | Phase 2 nach operativem Load. |
| `bananasupplychain/generate_documents.py` | Erzeugt PDFs und laedt sie in MinIO. | ETL/Dokumente | Hoch | Schreibt auch `erp.document_references`. |
| `bananasupplychain/verify_all_systems.py` | Prueft MongoDB, Redis, Neo4j und MinIO. | Pruefung | Hoch, aber Risiko | Neo4j-Erwartungen wirken stale. |
| `bananasupplychain/reorgFolders.py` | Loescht Inhalte in `shared/erp`, `shared/wms`, `shared/tms`. | Cleanup | Hoch als Risiko | Destruktiv; nur bewusst nutzen. |

### `sql/`

| Pfad | Zweck | Kategorie | Abgaberelevanz | Zusammenhang |
|---|---|---|---|---|
| `sql/00_sql_cheatsheet.sql` | Hilfsqueries fuer SQL-Arbeit. | Hilfsdatei | Niedrig | Komfortdatei. |
| `sql/01_create_schemas.sql` | Erstellt `erp`, `wms`, `tms`, `mdm`, `meta`, `dwh`. | Setup/DDL | Sehr hoch | Muss zuerst laufen. |
| `sql/02_create_erp_tables.sql` | ERP-Tabellen, Constraints, FKs. | Datenmodell | Sehr hoch | Wird von ETL befuellt. |
| `sql/03_create_wms_tables.sql` | WMS-Tabellen und Supply-Chain-Knoten. | Datenmodell | Sehr hoch | Wird von ETL befuellt. |
| `sql/04_create_tms_tables.sql` | TMS-Tabellen fuer Carrier, Shipments, GPS, Deliveries. | Datenmodell | Sehr hoch | Wird von ETL befuellt. |
| `sql/05_create_mdm_tables.sql` | MDM-Schema, Golden Records, Source Mappings, Resolve-Funktionen. | MDM | Sehr hoch | Zentral fuer Produktcode-Inkonsistenzen. |
| `sql/06_create_metadata_tables.sql` | Basismetadaten fuer Systeme, Tabellen, Spalten. | Metadaten | Sehr hoch | Enthalt Skalenniveaus und Quality Rules. |
| `sql/06b_metadata_complete.sql` | Ergaenzt Metadatenabdeckung ueber Information Schema. | Metadaten | Hoch | Sollte nach `06` ausgefuehrt werden. |
| `sql/07_create_dwh_schema.sql` | DWH-Sternschema, Dimensionen, Faktentabelle, Views. | DWH | Sehr hoch | Wird von `etl_dwh.py` befuellt. |
| `sql/08_data_quality_checks.sql` | Ausfuehrliche Data-Quality-Checks. | DQ | Sehr hoch | Interaktive/ausfuehrliche Pruefung. |
| `sql/08b_dq_audit.sql` | Konsolidierter DQ-Audit mit 28 Checks. | DQ | Sehr hoch | Gut fuer Abgabenachweis. |
| `sql/09_verification_queries.sql` | Technische Nachweisqueries fuer PostgreSQL/DWH. | Pruefung | Hoch, aber fehlerhaft | Enthalt stale DWH-Spalte und Erwartungswerte. |

### `docs/`

| Pfad | Zweck | Kategorie | Abgaberelevanz |
|---|---|---|---|
| `docs/00_part1_checklist.md` | Checkliste Teil 1. | Doku/Review | Hoch |
| `docs/01_data_classification.md` | Klassifikation aller Eventtypen. | Doku/Datenverstaendnis | Sehr hoch |
| `docs/02_target_architecture.md` | Zielarchitektur und Systemrollen. | Doku/Architektur | Sehr hoch |
| `docs/03_er_model.md` | ER-Modell und Beziehungen. | Doku/SQL-Modell | Sehr hoch |
| `docs/04_masterdata_management.md` | MDM-Konzept. | Doku/MDM | Sehr hoch |
| `docs/05_metadata_management.md` | Metadaten, Skalenniveaus, Quality Rules. | Doku/Metadaten | Sehr hoch |
| `docs/06_data_quality.md` | DQ-Konzept. | Doku/DQ | Sehr hoch |
| `docs/07_dwh_model.md` | DWH-Modell. | Doku/DWH | Sehr hoch |
| `docs/08_mongodb_event_model.md` | MongoDB-Eventmodell. | Doku/NoSQL | Sehr hoch |
| `docs/09_redis_realtime_model.md` | Redis-Echtzeitmodell. | Doku/NoSQL | Sehr hoch |
| `docs/10_neo4j_graph_model.md` | Neo4j-Graphmodell. | Doku/NoSQL | Sehr hoch |
| `docs/11_minio_document_model.md` | MinIO-Dokumentmodell. | Doku/Object Store | Sehr hoch, aber Zaehler pruefen |
| `docs/12_etl_concept.md` | ETL-Konzept. | Doku/ETL | Sehr hoch |
| `docs/13_data_quality_results.md` | DQ-Ergebnisse. | Doku/Nachweis | Hoch, aber Zaehler pruefen |
| `docs/Projekt_Gesamtueberblick_Teil1.md` | Dieses Review- und Lern-Dokument. | Doku/Review | Sehr hoch als Orientierung |

### `cypher/`

| Pfad | Zweck | Kategorie | Abgaberelevanz | Hinweis |
|---|---|---|---|---|
| `cypher/01_create_graph_model.cypher` | Statisches Graphmodell mit Constraints, Stammdaten und Demo-Fulfillment. | Neo4j-Modell | Hoch | Gute Demo, aber teilweise getrennt vom ETL-Graph. |
| `cypher/02_verification_queries.cypher` | Graph-Pruefqueries. | Neo4j-Pruefung | Hoch | Erwartet Demo-Batch-ID und Demo-Daten. |

### `shared/`

| Pfad | Zweck | Kategorie | Aktueller Stand |
|---|---|---|---|
| `shared/erp` | ERP-JSON-Events. | Quelldaten | 50 JSON-Dateien |
| `shared/wms` | WMS-JSON-Events. | Quelldaten | 70 JSON-Dateien |
| `shared/tms` | TMS-JSON-Events. | Quelldaten | 257 JSON-Dateien |

Aktuelle lokale Zaehler:

| System | Eventtyp/Pattern | Anzahl |
|---|---|---:|
| ERP | `supplier_created` | 10 |
| ERP | `customer_created` | 10 |
| ERP | `product_created` | 10 |
| ERP | `ordercreated` | 10 |
| ERP | `batchharvested` | 10 |
| WMS | `warehouse_sku_created` | 10 |
| WMS | `nodeprocessed` | 60 |
| TMS | `carrier_created` | 5 |
| TMS | `transport_product_reference_created` | 10 |
| TMS | `transportstarted` | 60 |
| TMS | `shipmentpositionupdated` | 112 |
| TMS | `transportcompleted` | 60 |
| TMS | `deliverycompleted` | 10 |
| TMS | erfolgreiche `deliverycompleted` | 8 |

Gesamt: 377 JSON-Dateien.

### `databasemodels_logistics_playground/`

| Pfad | Zweck | Kategorie | Abgaberelevanz | Risiko |
|---|---|---|---|---|
| `databasemodels_logistics_playground/manual.pdf` | Urspruengliches Manual fuer das Logistics Playground. | Vorlage/Doku | Mittel | Nicht finaler Banana-Use-Case. |
| `databasemodels_logistics_playground/commands.txt` | Alte Docker-/DB-Befehle. | Hilfsdatei | Niedrig bis mittel | Enthalt alte Collection-/Tabellennamen. |
| `databasemodels_logistics_playground/container/docker-compose.yml` | Alte Compose-Datei. | Setup/Vorlage | Niedrig, Risiko | Cleanup referenziert alte Tabellen. |
| `databasemodels_logistics_playground/src/initialize_db.py` | Initialisiert altes Demo-Datenmodell. | Playground | Niedrig | Nicht Kern des Banana-Projekts. |
| `databasemodels_logistics_playground/src/simulate_fullfillment.py` | Alte Fulfillment-Simulation. | Playground | Niedrig | Schreibweise `fullfillment`; nicht Banana-Kern. |
| `databasemodels_logistics_playground/src/cleanup_initialized_db.py` | Cleanup altes Demo. | Cleanup | Niedrig, Risiko | Kann fuer Banana verwirren. |
| `databasemodels_logistics_playground/src/cleanup_simulated_data.py` | Cleanup altes Demo. | Cleanup | Niedrig, Risiko | Nicht fuer Banana verwenden. |

---

## 4. Datenfluss

### 4.1 Quelle: JSON-Generator

`bananasupplychain/test_data_generator.py` erzeugt:

- Stammdaten in Iteration 0.
- Bewegungs- und Eventdaten in Iterationen 1 bis 10.
- Je Iteration einen ERP-Order, einen ERP-Batch, sechs WMS-NodeProcessed-Events, sechs TMS-Transporte, mehrere TMS-GPS-Updates, sechs Transportabschluesse und eine Endlieferung.

Wichtige Besonderheit:

- ERP-Produktcode: `BAN-101`
- WMS-Produktcode/SKU: `BAN_101`
- TMS-Produktreferenz: `ban-101`

Diese absichtliche Inkonsistenz ist die Grundlage fuer MDM.

### 4.2 Operatives Laden

`bananasupplychain/etl_load.py` liest aus:

- `shared/erp`
- `shared/wms`
- `shared/tms`

und schreibt nach:

- PostgreSQL `erp.*`, `wms.*`, `tms.*`, `mdm.*`
- MongoDB `logistics.*`
- Redis Keyspace DB 0
- Neo4j Graph

### 4.3 Dokumentenfluss

`bananasupplychain/generate_documents.py` liest WMS/TMS-Events und erzeugt PDFs:

| Dokumenttyp | Quelle | Bucket | Erwartung bei aktuellem Datenstand |
|---|---|---|---:|
| Delivery Note | 60 `TransportStarted` | `delivery-notes` | 60 |
| Invoice | 8 erfolgreiche `DeliveryCompleted` | `invoices` | 8 |
| Bill of Lading | 10 Sea-Freight-Transporte | `transport-docs` | 10 |
| Customs Clearance | 10 Sea-Freight-Transporte | `transport-docs` | 10 |
| Quality Certificate | 10 Quality-Control-WMS-Events | `batch-certificates` | 10 |

Aktuell daraus ableitbare Gesamterwartung: 98 Objekte. Einige bestehende Dokumente nennen 116; das ist ein Widerspruch und sollte vor Abgabe bereinigt werden.

### 4.4 DWH-Fluss

`bananasupplychain/etl_dwh.py` liest operative PostgreSQL-Tabellen und befuellt:

- `dwh.dim_customer`
- `dwh.dim_product`
- `dwh.dim_supplier`
- `dwh.dim_carrier`
- `dwh.dim_supply_chain_node`
- `dwh.dim_date`
- `dwh.dim_delivery_status`
- `dwh.fact_fulfillment`

Die Faktentabelle ist aktuell als eine Zeile pro Endlieferung modelliert. Bei 10 Endlieferungen sind 10 Faktzeilen plausibel. Aussagen wie "10 Lieferungen mal 6 Hops = 60 Fakten" sind fuer den aktuellen Code stale.

---

## 5. Datenbankmodelle

### 5.1 PostgreSQL

PostgreSQL ist das relationale Rueckgrat.

#### ERP-Schema

Datei: `sql/02_create_erp_tables.sql`

Tabellen:

- `erp.suppliers`: Lieferantenstammdaten.
- `erp.customers`: Kundenstammdaten.
- `erp.products`: Produktstammdaten mit Lieferantenbezug.
- `erp.orders`: Bestellkopf.
- `erp.order_items`: Bestellpositionen.
- `erp.batches`: Ernte-/Produktionsbatch.
- `erp.document_references`: Referenzen auf MinIO-Dokumente.

Warum gebraucht:

- ERP liefert kaufmaennische Kernobjekte.
- Diese Tabellen bilden eine stabile relationale Basis fuer MDM, DWH und DQ.

Pruefung:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM erp.orders;"
```

Erwartung nach aktuellem sauberem Load: etwa 10 Orders.

#### WMS-Schema

Datei: `sql/03_create_wms_tables.sql`

Tabellen:

- `wms.warehouse_skus`: WMS-SKU-Stammdaten.
- `wms.supply_chain_nodes`: Supply-Chain-Knoten.
- `wms.node_processings`: Prozessereignisse je Batch und Station.

Warum gebraucht:

- WMS beschreibt, wo sich Ware in der physischen Supply Chain befindet.
- Temperatur und Status sind wichtig fuer DQ und Kuehlkettenbewertung.

Pruefung:

```bash
docker exec -it postgres psql -U user -d logistics -c "SELECT node_code, sequence_order FROM wms.supply_chain_nodes ORDER BY sequence_order;"
```

Erwartung: 7 Knoten von `BANANA_PLANTATION` bis `RETAIL_STORE`.

#### TMS-Schema

Datei: `sql/04_create_tms_tables.sql`

Tabellen:

- `tms.carriers`: Transportdienstleister.
- `tms.transport_product_references`: TMS-Produktreferenzen.
- `tms.shipments`: Transporte.
- `tms.shipment_positions`: GPS-/Temperaturpositionen.
- `tms.transport_completions`: Transportabschluss.
- `tms.deliveries`: Endlieferung.

Warum gebraucht:

- TMS liefert Bewegungs-, Echtzeit- und Zustelldaten.
- Diese Daten sind Grundlage fuer Lieferzeit, Delay, Route, Carrier Performance und Dokumente.

Pruefung:

```bash
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM tms.shipments;"
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM tms.shipment_positions;"
```

Erwartung nach aktuellem JSON-Stand: 60 Shipments, 112 Positionsupdates.

#### MDM-Schema

Datei: `sql/05_create_mdm_tables.sql`

Tabellen/Funktionen:

- `mdm.entity_types`
- `mdm.golden_records`
- `mdm.source_mappings`
- `mdm.resolve_canonical_key(source_key, source_system)`
- `mdm.resolve_canonical_key_fuzzy(raw_key)`
- `mdm.v_golden_overview`

Warum gebraucht:

- ERP, WMS und TMS benutzen unterschiedliche Schreibweisen fuer dasselbe Produkt.
- MDM fuehrt diese Varianten auf einen kanonischen Golden Record zurueck.

Pruefung:

```bash
docker exec -it postgres psql -U user -d logistics -c "SELECT mdm.resolve_canonical_key('BAN_101', 'WMS');"
docker exec -it postgres psql -U user -d logistics -c "SELECT mdm.resolve_canonical_key('ban-101', 'TMS');"
```

Erwartung: beide Abfragen liefern `BAN-101`.

#### Metadaten-Schema

Dateien:

- `sql/06_create_metadata_tables.sql`
- `sql/06b_metadata_complete.sql`

Tabellen:

- `meta.systems`
- `meta.tables`
- `meta.columns`

Warum gebraucht:

- Die Aufgabenstellung verlangt Metadatenmanagement und Skalenniveaus.
- Hier wird dokumentiert, welche Spalte zu welchem System gehoert, welchen Datentyp sie hat, welches Skalenniveau sie besitzt und welche Qualitaetsregel gilt.

Wichtige Beispiele:

- Temperatur: `INTERVAL`
- Delay-Minuten: `RATIO`
- Delivery Priority: `ORDINAL`
- Status/Codes: meist `NOMINAL`

Pruefung:

```bash
docker exec -it postgres psql -U user -d logistics -c "SELECT scale_level, COUNT(*) FROM meta.columns GROUP BY scale_level ORDER BY scale_level;"
```

#### DWH-Schema

Datei: `sql/07_create_dwh_schema.sql`

Faktentabelle:

- `dwh.fact_fulfillment`

Dimensionen:

- `dwh.dim_customer`
- `dwh.dim_product`
- `dwh.dim_supplier`
- `dwh.dim_carrier`
- `dwh.dim_supply_chain_node`
- `dwh.dim_date`
- `dwh.dim_delivery_status`

Views:

- `dwh.v_carrier_performance`
- `dwh.v_kpi_summary`
- `dwh.v_monthly_revenue`

Warum gebraucht:

- Das DWH trennt analytische Auswertungen von operativen Tabellen.
- Fakten und Dimensionen machen KPI- und BI-Abfragen einfacher.

Pruefung:

```bash
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM dwh.fact_fulfillment;"
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM dwh.dim_date;"
```

Erwartung: `fact_fulfillment` etwa 10 Zeilen; `dim_date` 1095 Zeilen fuer 2025-2027.

#### Data Quality

Dateien:

- `sql/08_data_quality_checks.sql`
- `sql/08b_dq_audit.sql`

DQ-Dimensionen:

- Vollstaendigkeit
- Eindeutigkeit
- Konsistenz
- Plausibilitaet
- Aktualitaet
- Referenzielle Integritaet

Pruefung:

```bash
docker exec -i postgres psql -U user -d logistics < sql/08b_dq_audit.sql
```

Erwartung: 28 Checks. Die genaue PASS/FAIL-Summe haengt vom geladenen Datenstand ab.

### 5.2 MongoDB

Datenbank: `logistics`

Collections aus `etl_load.py`:

- `shipment_events`: ein Dokument pro Shipment, eingebettete Event-Historie, TTL-Index.
- `node_events`: WMS-NodeProcessed-Ereignisse mit Quality Flags.
- `batch_tracking`: ein Dokument pro Batch, eingebettete Prozessstationen.
- `order_events`: Order-Snapshot und Event.

Warum MongoDB:

- Eventdaten haben flexible Struktur.
- Eingebettete Arrays sind praktisch fuer Lifecycle-Dokumente.
- TTL-Indizes passen zu zeitlich begrenzten Trackingdaten.

Pruefung:

```bash
docker exec -it mongodb mongosh logistics --eval "db.shipment_events.countDocuments()"
docker exec -it mongodb mongosh logistics --eval "db.node_events.countDocuments()"
docker exec -it mongodb mongosh logistics --eval "db.batch_tracking.countDocuments()"
docker exec -it mongodb mongosh logistics --eval "db.order_events.countDocuments()"
```

Erwartung nach aktuellem JSON-Stand:

- `shipment_events`: mindestens 60
- `node_events`: 60
- `batch_tracking`: 10 Dokumente, obwohl 60 NodeProcessed-Events verarbeitet werden
- `order_events`: 10

Risiko: Einige Dokumente zaehlen `batch_tracking` als 60. Technisch ist die Collection aber batch-orientiert, also 10 Dokumente mit eingebetteten Stationen.

### 5.3 Redis

Redis speichert schnelle, kurzlebige Daten:

| Key-Pattern | Typ | Zweck |
|---|---|---|
| `cache:product:*` | HASH/Cache | Produktcache |
| `order:status:*` | STRING | aktueller Orderstatus |
| `order:meta:*` | HASH | Ordermetadaten |
| `order:timeline:*` | LIST | Order-Ereignisverlauf |
| `shipment:status:*` | STRING | aktueller Shipmentstatus |
| `shipment:info:*` | HASH | Shipmentdetails |
| `shipment:position:*` | HASH/STRING | aktuelle GPS-Position |
| `shipment:route:*` | ZSET | GPS-Verlauf |
| `alert:temperature:*` | HASH/STRING | Temperaturwarnungen |
| `system:counter:*` | COUNTER | Lauf- und Tageszaehler |

Warum Redis:

- Schnelle Statusabfragen.
- Gut fuer aktuelle Position, aktuelle Lieferphase, Counter und Alerts.
- TTL reduziert Altlasten.

Pruefung:

```bash
docker exec -it redis redis-cli INFO keyspace
docker exec -it redis redis-cli KEYS "shipment:status:*"
docker exec -it redis redis-cli GET "system:counter:etl_runs"
```

Risiko:

- Redis-ETL ist nicht voll idempotent. Counter steigen bei jedem ETL-Lauf.
- Einige GPS-/Realtime-Keys koennen per TTL verschwinden. Pruefungen sollten direkt nach einem frischen ETL-Lauf erfolgen.

### 5.4 Neo4j

Node-Typen:

- `Supplier`
- `Customer`
- `Product`
- `Order`
- `Batch`
- `Shipment`
- `Carrier`
- `SupplyChainNode`

Wichtige Relationship-Typen:

- `SUPPLIES`
- `PLACED`
- `CONTAINS`
- `TRIGGERED`
- `PROCESSED_AT`
- `TRANSPORTED_VIA`
- `TRANSPORTED_BY`
- `FROM`
- `TO`
- `CONNECTED_TO`
- `DELIVERS_TO`
- `DELIVERED_TO`
- `OPERATES_ON`

Warum Neo4j:

- Supply-Chain-Pfade sind Graphfragen.
- Beziehungen wie Lieferant -> Produkt -> Order -> Batch -> Shipment -> Carrier lassen sich gut traversieren.
- Der 6-Hop-Pfad von Plantage bis Retail ist im Graphen direkt abfragbar.

Pruefung:

```bash
docker exec -it neo4j cypher-shell -u neo4j -p password "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC;"
docker exec -it neo4j cypher-shell -u neo4j -p password "MATCH (a:SupplyChainNode {node_code:'BANANA_PLANTATION'}), (b:SupplyChainNode {node_code:'RETAIL_STORE'}), p=shortestPath((a)-[:CONNECTED_TO*]->(b)) RETURN length(p) AS hops;"
```

Erwartung:

- 7 SupplyChainNode-Nodes.
- Kuerzester Pfad von Plantage zu Retail: 6 Hops.

Risiko:

- `verify_all_systems.py` erwartet aktuell mindestens 21 Orders, 20 Batches und 121 Shipments. Bei einem sauberen aktuellen JSON-Lauf waeren eher 10 Orders, 10 Batches und 60 Shipments plausibel.
- Der Graph verbindet Batches und Shipments produktbasiert, weil TMS keine Batch-ID liefert. Das ist fuer Pfad-Demos brauchbar, aber fachlich nicht exakt genug fuer eine perfekte Lineage.

### 5.5 MinIO

Buckets:

- `invoices`
- `delivery-notes`
- `transport-docs`
- `batch-certificates`

Warum MinIO:

- PDFs gehoeren nicht als BLOB in PostgreSQL.
- PostgreSQL speichert nur Referenzen: Bucket, Objektpfad, Dokumenttyp, Entity-Key.
- MinIO bildet objektbasierte Dokumentenablage ab.

Pruefung:

```bash
docker exec -it minio mc alias set local http://localhost:9000 admin password
docker exec -it minio mc ls local
docker exec -it minio mc ls local/delivery-notes --recursive
```

Alternativ im Browser:

- URL: `http://localhost:9001`
- User: `admin`
- Passwort: `password`

---

## 6. Python-Skripte erklaert

### 6.1 `bananasupplychain/test_data_generator.py`

Zweck:

- Erzeugt synthetische Banana-Supply-Chain-Events als JSON-Dateien.

Eingaben:

- Keine externen Eingabedaten.
- Konfiguration im Skript: `OUTPUT_MODE`, `BASE_SHARED_DIR`, Stammdatenlisten, Supply-Chain-Fluss.

Output:

- `shared/erp/*.json`
- `shared/wms/*.json`
- `shared/tms/*.json`

Technische Logik:

1. Definiert Stammdaten fuer Lieferanten, Kunden, Produkte und Carrier.
2. Erzeugt Produktcode-Inkonsistenzen zwischen ERP, WMS und TMS.
3. Schreibt Stammdaten-Events in Iteration 0.
4. Simuliert 10 Supply-Chain-Iterationen.
5. Je Iteration entstehen Order, Batch, WMS-Prozessschritte, TMS-Transporte, Positionsupdates und DeliveryCompleted.

Warum gebraucht:

- Ohne Generator gibt es keine Quell-JSON-Dateien fuer ETL und Datenmodellnachweise.

Wichtig:

- Aus dem Repo-Root starten:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
python3 bananasupplychain/test_data_generator.py
```

Nicht empfohlen:

```bash
cd bananasupplychain
python3 test_data_generator.py
```

Grund: Das Skript schreibt relativ nach `shared/`. Aus `bananasupplychain/` heraus wuerde es nach `bananasupplychain/shared/` schreiben, waehrend `etl_load.py` `../shared` erwartet.

Funktionstest:

```bash
find shared/erp -maxdepth 1 -type f -name "*.json" | wc -l
find shared/wms -maxdepth 1 -type f -name "*.json" | wc -l
find shared/tms -maxdepth 1 -type f -name "*.json" | wc -l
```

Erwartung aktueller Stand:

- ERP: 50
- WMS: 70
- TMS: 257
- Gesamt: 377

Risiko:

- Ein erneuter Generatorlauf loescht bestehende operative JSON-Dateien nicht automatisch. UUID-basierte Dateien koennen sich ansammeln. Fuer reproduzierbare Laeufe vorher bewusst cleanupen.

### 6.2 `bananasupplychain/etl_load.py`

Zweck:

- Laedt die JSON-Events in PostgreSQL, MongoDB, Redis und Neo4j.

Eingaben:

- JSON-Dateien aus `shared/erp`, `shared/wms`, `shared/tms`.
- Laufende Docker-Container.
- Vorhandene PostgreSQL-DDL.

Outputs:

- Befuellte operative PostgreSQL-Tabellen.
- Befuellte MongoDB-Collections.
- Redis-Keys.
- Neo4j-Graph.
- MDM-Records in PostgreSQL.

Technische Hauptschritte:

1. `extract_events(system)` liest alle JSON-Dateien eines Systems.
2. Transform-Funktionen normalisieren Datentypen und Produktcodes.
3. `load_postgres(...)` schreibt ERP/WMS/TMS in relationale Tabellen.
4. MDM-Funktionen erzeugen Golden Records und Source Mappings.
5. Mongo-Loader erzeugt Eventdokumente und eingebettete Lifecycle-Strukturen.
6. Redis-Loader setzt Statuskeys, Caches, Timelines, Counter und Routen.
7. Neo4j-Loader erzeugt Nodes, Constraints und Beziehungen.

Warum gebraucht:

- Es ist das zentrale Integrationsskript fuer Teil 1.

Funktionstest:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
python3 bananasupplychain/etl_load.py
```

Erwartung:

- Konsolenausgaben je Zielsystem.
- Danach pruefbare Daten in PostgreSQL, MongoDB, Redis und Neo4j.

Risiken:

- Redis-Counter sind nicht idempotent.
- Graph- und DWH-Lineage ist produktbasiert, weil TMS keine Batch-/Order-ID liefert.
- Vorher muessen PostgreSQL-Schemata existieren.

### 6.3 `bananasupplychain/etl_dwh.py`

Zweck:

- Befuellt das Data Warehouse aus den operativen PostgreSQL-Tabellen.

Eingaben:

- `erp.*`, `wms.*`, `tms.*`
- DWH-DDL aus `sql/07_create_dwh_schema.sql`

Outputs:

- `dwh.dim_*`
- `dwh.fact_fulfillment`

Technische Logik:

1. Dimensionstabellen werden aus operativen Tabellen befuellt.
2. Date Spine wird in `dwh.dim_date` genutzt.
3. Faktentabelle wird geloescht und neu befuellt.
4. Measures wie Menge, Preis, Gesamtwert, Delay, Durchschnittstemperatur und Hop-Anzahl werden berechnet.

Warum gebraucht:

- Die Aufgabenstellung verlangt ein Data-Warehouse-Schema und ETL-Verbindung zwischen ERP/WMS/TMS und Analytics/DWH.

Funktionstest:

```bash
python3 bananasupplychain/etl_dwh.py
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM dwh.fact_fulfillment;"
```

Erwartung:

- Bei aktuellem JSON-Stand sind 10 Faktzeilen plausibel.

Risiko:

- Die Zuordnung von Delivery zu Order/Batch erfolgt produktbasiert. Wenn derselbe Produktcode mehrfach bestellt wird, kann die Faktzeile einer falschen Order zugeordnet werden.

### 6.4 `bananasupplychain/generate_documents.py`

Zweck:

- Erzeugt PDF-Dokumente und speichert sie in MinIO.
- Schreibt Dokumentreferenzen nach PostgreSQL.

Eingaben:

- `shared/tms`
- `shared/wms`
- Laufendes MinIO
- PostgreSQL-Tabelle `erp.document_references`

Outputs:

- PDFs in MinIO-Buckets.
- Zeilen in `erp.document_references`.

Dokumentarten:

- Delivery Notes fuer `TransportStarted`
- Invoices fuer erfolgreiche `DeliveryCompleted`
- Bill of Lading fuer Sea-Freight-Transporte
- Customs Clearance fuer Sea-Freight-Transporte
- Quality Certificates fuer Quality-Control-Events

Funktionstest:

```bash
python3 bananasupplychain/generate_documents.py
docker exec -it postgres psql -U user -d logistics -c "SELECT document_type, COUNT(*) FROM erp.document_references GROUP BY document_type ORDER BY document_type;"
```

Erwartung aktueller JSON-Stand:

- 60 Delivery Notes
- 8 Invoices
- 10 Bill of Lading
- 10 Customs Clearance
- 10 Quality Certificates

### 6.5 `bananasupplychain/verify_all_systems.py`

Zweck:

- Prueft MongoDB, Redis, Neo4j und MinIO.

Eingaben:

- Laufende Container.
- Bereits geladene Daten.

Output:

- PASS/FAIL-Zusammenfassung in der Konsole.

Funktionstest:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
python3 bananasupplychain/verify_all_systems.py
```

Risiko:

- Neo4j-Checks sind wahrscheinlich stale:
  - Erwartet 21 Orders statt 10.
  - Erwartet 20 Batches statt 10.
  - Erwartet 121 Shipments statt 60.
  - Erwartet eine feste Demo-Batch-ID.
- Das Skript ist als Idee gut, muss aber vor Abgabe an den aktuellen Datenstand angepasst werden.

### 6.6 `bananasupplychain/reorgFolders.py`

Zweck:

- Loescht Dateien und Ordner in:
  - `shared/erp`
  - `shared/wms`
  - `shared/tms`

Warum gefaehrlich:

- Es gibt keine Sicherheitsabfrage.
- Es loescht relevante Quelldaten.

Nutzung nur bewusst:

```bash
python3 bananasupplychain/reorgFolders.py
```

Empfehlung:

- Vor Abgabe nicht unkontrolliert nutzen.
- Besser ein klares Reset-Skript mit Rueckfrage oder dokumentierter Sicherung erstellen.

### 6.7 `dashboard_plausibility.py`

Zweck:

- Erzeugt ein Plausibilitaets-Dashboard aus PostgreSQL-Daten.

Kategorie:

- Eher Analytics/Reporting, nicht Kern von Teil 1.

Output:

- `dashboard_plausibility.png`

Pruefung:

```bash
python3 dashboard_plausibility.py
```

Erwartung:

- Bilddatei wird erzeugt/aktualisiert, sofern PostgreSQL erreichbar ist und Daten vorhanden sind.

### 6.8 `create_status_report.py` und `create_guide_pdf.py`

Zweck:

- Erzeugen PDF-/Statusdokumente aus Projektinformationen.

Kategorie:

- Hilfsdateien fuer Dokumentation.

Risiko:

- Falls sie alte Zahlen enthalten, koennen sie Widersprueche reproduzieren. Vor Abgabe nur verwenden, wenn die Inhalte aktualisiert wurden.

---

## 7. Ausfuehrungsanleitung mit Befehlen

Alle Befehle gehen von macOS/Linux-Terminal aus.

### 7.1 Infrastruktur starten

Ordner:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26/bananasupplychain/container
```

Befehl:

```bash
docker compose up -d
```

Was passiert:

- PostgreSQL, MongoDB, Redis, Neo4j, MinIO und Cleanup-Service werden gestartet.

Erwartung:

- Ausgabe mit `Started` oder `Running`.

Pruefen:

```bash
docker ps
```

Erwartung:

- Container `postgres`, `mongodb`, `redis`, `neo4j`, `minio` laufen.

Hinweis:

- `docker compose config --services` meldet fuer diese Compose-Datei nur, dass `version` obsolete ist. Die Services werden erkannt: `postgres`, `cleanup`, `minio`, `mongodb`, `neo4j`, `redis`.

### 7.2 PostgreSQL-Schemata initialisieren

Ordner:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
```

Befehle:

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

Was passiert:

- Alle benoetigten PostgreSQL-Schemata und Tabellen werden angelegt.

Erwartung:

- `CREATE SCHEMA`, `CREATE TABLE`, `INSERT`, `CREATE VIEW`, `CREATE FUNCTION` oder `NOTICE already exists`.

Pruefen:

```bash
docker exec -it postgres psql -U user -d logistics -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('erp','wms','tms','mdm','meta','dwh') ORDER BY schema_name;"
```

Erfolgskriterium:

- Alle sechs Schemata werden angezeigt.

### 7.3 JSON-Daten erzeugen

Ordner:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
```

Befehl:

```bash
python3 bananasupplychain/test_data_generator.py
```

Was passiert:

- JSON-Dateien werden in `shared/erp`, `shared/wms`, `shared/tms` geschrieben.

Erwartung:

- Konsolenausgabe mit erzeugten Events.

Pruefen:

```bash
find shared/erp -maxdepth 1 -type f -name "*.json" | wc -l
find shared/wms -maxdepth 1 -type f -name "*.json" | wc -l
find shared/tms -maxdepth 1 -type f -name "*.json" | wc -l
```

Erfolgskriterium:

- Aktueller Referenzstand: 50, 70, 257.

### 7.4 Operativen ETL ausfuehren

Ordner:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
```

Befehl:

```bash
python3 bananasupplychain/etl_load.py
```

Was passiert:

- JSON wird gelesen.
- PostgreSQL, MongoDB, Redis und Neo4j werden befuellt.

Erwartung:

- Logausgaben fuer Extract, Transform und Load.

Pruefen:

```bash
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM erp.orders;"
docker exec -it mongodb mongosh logistics --eval "db.shipment_events.countDocuments()"
docker exec -it redis redis-cli DBSIZE
docker exec -it neo4j cypher-shell -u neo4j -p password "MATCH (n) RETURN count(n);"
```

### 7.5 Dokumente erzeugen und nach MinIO laden

Ordner:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
```

Befehl:

```bash
python3 bananasupplychain/generate_documents.py
```

Was passiert:

- PDFs werden erzeugt und in MinIO hochgeladen.
- PostgreSQL bekommt Dokumentreferenzen.

Pruefen:

```bash
docker exec -it postgres psql -U user -d logistics -c "SELECT document_type, COUNT(*) FROM erp.document_references GROUP BY document_type ORDER BY document_type;"
docker exec -it minio mc ls local/delivery-notes --recursive
```

Hinweis:

- Falls `mc alias local` im Container nicht existiert, zuerst:

```bash
docker exec -it minio mc alias set local http://localhost:9000 admin password
```

### 7.6 DWH-ETL ausfuehren

Ordner:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
```

Befehl:

```bash
python3 bananasupplychain/etl_dwh.py
```

Was passiert:

- Dimensionen und `dwh.fact_fulfillment` werden befuellt.

Pruefen:

```bash
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM dwh.fact_fulfillment;"
docker exec -it postgres psql -U user -d logistics -c "SELECT * FROM dwh.v_kpi_summary;"
```

Erwartung:

- Aktuell etwa 10 Faktzeilen.

### 7.7 Data Quality pruefen

Ordner:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
```

Befehl:

```bash
docker exec -i postgres psql -U user -d logistics < sql/08b_dq_audit.sql
```

Was passiert:

- 28 Data-Quality-Checks laufen gegen PostgreSQL.

Erwartung:

- Tabelle/Resultset mit Checknamen und Status.

### 7.8 Systemuebergreifend pruefen

Befehl:

```bash
python3 bananasupplychain/verify_all_systems.py
```

Was passiert:

- MongoDB, Redis, Neo4j und MinIO werden geprueft.

Wichtig:

- Dieses Skript vor Abgabe pruefen/anpassen, da Neo4j-Erwartungen wahrscheinlich nicht zum aktuellen frischen Datenstand passen.

### 7.9 Cleanup / Reset

Vollstaendiger Infrastruktur-Reset:

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26/bananasupplychain/container
docker compose down -v
docker compose up -d
```

Was passiert:

- Container werden entfernt.
- Volumes werden entfernt.
- Alle Datenbanken sind danach leer.

Redis-only Reset:

```bash
docker exec -it redis redis-cli FLUSHALL
```

MongoDB-only Reset:

```bash
docker exec -it mongodb mongosh logistics --eval "db.dropDatabase()"
```

Neo4j-only Reset:

```bash
docker exec -it neo4j cypher-shell -u neo4j -p password "MATCH (n) DETACH DELETE n;"
```

JSON-Reset:

```bash
python3 bananasupplychain/reorgFolders.py
```

Achtung:

- `reorgFolders.py` loescht die Quell-JSON-Dateien ohne Rueckfrage.
- Vor Nutzung sicherstellen, dass genau das gewollt ist.

Nicht empfohlen fuer Banana:

- Cleanup-Skripte aus `databasemodels_logistics_playground/src/`, weil sie fuer das alte Demo-Modell gedacht sind.

---

## 8. Pruef-Befehle pro Datenbank

### PostgreSQL

```bash
docker exec -it postgres psql -U user -d logistics
```

In `psql`:

```sql
\dn
\dt erp.*
\dt wms.*
\dt tms.*
\dt mdm.*
\dt meta.*
\dt dwh.*

SELECT COUNT(*) FROM erp.suppliers;
SELECT COUNT(*) FROM erp.customers;
SELECT COUNT(*) FROM erp.products;
SELECT COUNT(*) FROM erp.orders;
SELECT COUNT(*) FROM erp.batches;
SELECT COUNT(*) FROM wms.node_processings;
SELECT COUNT(*) FROM tms.shipments;
SELECT COUNT(*) FROM tms.shipment_positions;
SELECT COUNT(*) FROM dwh.fact_fulfillment;
```

### MongoDB

```bash
docker exec -it mongodb mongosh logistics
```

In `mongosh`:

```javascript
show collections
db.shipment_events.countDocuments()
db.node_events.countDocuments()
db.batch_tracking.countDocuments()
db.order_events.countDocuments()
db.shipment_events.getIndexes()
db.shipment_events.findOne()
```

### Redis

```bash
docker exec -it redis redis-cli
```

In `redis-cli`:

```text
INFO keyspace
DBSIZE
KEYS shipment:status:*
KEYS shipment:route:*
KEYS order:status:*
GET system:counter:etl_runs
TYPE shipment:status:<shipment_id>
```

### Neo4j

```bash
docker exec -it neo4j cypher-shell -u neo4j -p password
```

Cypher:

```cypher
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC;

MATCH ()-[r]->()
RETURN type(r) AS rel_type, count(r) AS cnt
ORDER BY cnt DESC;

MATCH (start:SupplyChainNode {node_code:'BANANA_PLANTATION'}),
      (end:SupplyChainNode {node_code:'RETAIL_STORE'}),
      p = shortestPath((start)-[:CONNECTED_TO*]->(end))
RETURN length(p) AS hops;
```

### MinIO

Browser:

```text
http://localhost:9001
User: admin
Password: password
```

CLI:

```bash
docker exec -it minio mc alias set local http://localhost:9000 admin password
docker exec -it minio mc ls local
docker exec -it minio mc ls local/delivery-notes --recursive
docker exec -it minio mc ls local/invoices --recursive
docker exec -it minio mc ls local/transport-docs --recursive
docker exec -it minio mc ls local/batch-certificates --recursive
```

---

## 9. Datenverstaendnis

### Welche JSON-Dateien werden erzeugt?

Aktueller Stand:

- `shared/erp`: 50 JSON-Dateien.
- `shared/wms`: 70 JSON-Dateien.
- `shared/tms`: 257 JSON-Dateien.

Gesamt: 377 JSON-Dateien.

### Welche Events gibt es?

ERP:

- `SupplierCreated`
- `CustomerCreated`
- `ProductCreated`
- `OrderCreated`
- `BatchHarvested`

WMS:

- `WarehouseSKUCreated`
- `NodeProcessed`

TMS:

- `CarrierCreated`
- `TransportProductReferenceCreated`
- `TransportStarted`
- `ShipmentPositionUpdated`
- `TransportCompleted`
- `DeliveryCompleted`

### Welche Daten gehoeren zu ERP?

- Lieferanten
- Kunden
- Produkte
- Bestellungen
- Bestellpositionen
- Batches
- Dokumentreferenzen

### Welche Daten gehoeren zu WMS?

- Warehouse SKUs
- Supply-Chain-Knoten
- Batchverarbeitung pro Knoten
- Temperatur und Qualitaetsstatus je Prozessschritt

### Welche Daten gehoeren zu TMS?

- Carrier
- TMS-Produktreferenzen
- Shipments
- GPS-Positionsupdates
- Transportabschluesse
- Lieferabschluss am Retail Store

### Stammdaten

- ERP: Supplier, Customer, Product
- WMS: Warehouse SKU
- TMS: Carrier, TransportProductReference
- MDM: Golden Records und Source Mappings
- WMS/TMS: Supply-Chain-Knoten und Carrier koennen ebenfalls als Stammdaten betrachtet werden.

### Bewegungsdaten

- ERP Orders
- ERP Order Items
- ERP Batches
- TMS Shipments
- TMS Transport Completions
- TMS Deliveries

### Eventdaten

- WMS NodeProcessed
- TMS TransportStarted
- TMS ShipmentPositionUpdated
- TMS TransportCompleted
- TMS DeliveryCompleted
- MongoDB speichert diese besonders eventnah.

### Echtzeitdaten

- GPS-Positionen aus `ShipmentPositionUpdated`
- Aktueller Shipmentstatus
- Aktueller Orderstatus
- Temperaturalerts
- Redis ist das primaere Ziel fuer Echtzeitdaten.

### Dokumentdaten

- MinIO-PDFs:
  - Lieferscheine
  - Rechnungen
  - Bill of Lading
  - Customs Clearance
  - Quality Certificates
- PostgreSQL speichert nur Dokumentreferenzen.

### Welche Daten landen wo?

| Datenart | Primaeres Ziel | Sekundaere Nutzung |
|---|---|---|
| ERP-Stammdaten | PostgreSQL `erp.*` | MDM, DWH, Neo4j |
| WMS-Prozessdaten | PostgreSQL `wms.*`, MongoDB `node_events` | Redis Alerts, Neo4j, DWH |
| TMS-Transportdaten | PostgreSQL `tms.*`, MongoDB `shipment_events` | Redis, Neo4j, DWH, MinIO |
| MDM-Mappings | PostgreSQL `mdm.*` | ETL/Pruefung |
| Metadaten | PostgreSQL `meta.*` | Doku, DQ, Abgabenachweis |
| DQ-Ergebnisse | SQL-Resultsets | Doku/Nachweis |
| DWH-Daten | PostgreSQL `dwh.*` | Analytics/BI |
| Dokumente | MinIO | PostgreSQL `erp.document_references` |

---

## 10. Mapping Aufgabenstellung zu Projektumsetzung

Legende:

- ERFUELLT: Artefakte sind vorhanden und konsistent genug umgesetzt.
- TEILWEISE ERFUELLT: Umsetzung existiert, aber mit dokumentierter Einschraenkung.
- NICHT ERFUELLT: Wesentlicher Bestandteil fehlt.
- UNKLAR / MUSS GETESTET WERDEN: statisch vorhanden, Laufzeitnachweis fehlt oder ist widerspruechlich.

| Anforderung Teil 1 | Status | Begruendung | Relevante Dateien/Objekte | Pruefbefehl | Falls fehlend/Problem |
|---|---|---|---|---|---|
| Docker-Infrastruktur vorhanden und lauffaehig | UNKLAR / MUSS GETESTET WERDEN | Main Compose vorhanden und statisch parsebar; Runtime in dieser Review nicht gestartet. | `bananasupplychain/container/docker-compose.yml` | `cd bananasupplychain/container && docker compose up -d && docker ps` | Alte Compose nicht verwenden; `version`-Warnung optional bereinigen. |
| PostgreSQL vorhanden | ERFUELLT | Service und SQL-DDL vorhanden. | `postgres`, `sql/01-09` | `docker exec -it postgres psql -U user -d logistics -c "\dn"` | Keine. |
| MongoDB vorhanden | ERFUELLT | Service und Loader vorhanden. | `mongodb`, `etl_load.py` | `docker exec -it mongodb mongosh logistics --eval "show collections"` | Runtime frisch pruefen. |
| Redis vorhanden | ERFUELLT | Service und Keymodell vorhanden. | `redis`, `etl_load.py`, `docs/09` | `docker exec -it redis redis-cli INFO keyspace` | Redis-Counter/TTL in Doku klar erklaeren. |
| Neo4j vorhanden | TEILWEISE ERFUELLT | Graphmodell vorhanden; Verifikationswerte teils stale und Lineage produktbasiert. | `neo4j`, `etl_load.py`, `cypher/*` | `MATCH (n) RETURN labels(n), count(n)` | `verify_all_systems.py` und Demo-Erwartungen aktualisieren. |
| MinIO vorhanden | TEILWEISE ERFUELLT | Buckets/Dokumentgenerator vorhanden; Dokumentzaehler in Doku widerspruechlich. | `minio`, `generate_documents.py`, `docs/11` | `mc ls local` | 98 vs. 116 klaeren. |
| Datengenerator vorhanden und lauffaehig | ERFUELLT | Generator existiert und aktuelle JSON-Dateien sind vorhanden. | `test_data_generator.py`, `shared/*` | `python3 bananasupplychain/test_data_generator.py` | Startordner dokumentieren: Repo-Root. |
| JSON-Dateien werden erzeugt | ERFUELLT | 377 JSON-Dateien vorhanden. | `shared/erp`, `shared/wms`, `shared/tms` | `find shared/tms -maxdepth 1 -name "*.json" | wc -l` | Re-Run kann Dateien ansammeln. |
| JSON-Dateien sind klassifiziert | ERFUELLT | Klassifikation dokumentiert. | `docs/01_data_classification.md` | Doku pruefen | Zaehler 377 beibehalten. |
| ERP-Schema vorhanden | ERFUELLT | Vollstaendiges ERP-DDL mit FKs/Constraints. | `sql/02_create_erp_tables.sql` | `\dt erp.*` | Keine. |
| WMS-Schema vorhanden | ERFUELLT | WMS-DDL mit Knoten und Prozessdaten. | `sql/03_create_wms_tables.sql` | `\dt wms.*` | Kommentar "alle 7 Stationen" vs. 6 WMS-Prozessknoten pruefen. |
| TMS-Schema vorhanden | ERFUELLT | TMS-DDL fuer Carrier/Shipments/GPS/Deliveries. | `sql/04_create_tms_tables.sql` | `\dt tms.*` | Keine. |
| ER-Modell ableitbar oder dokumentiert | ERFUELLT | ER-Modell-Doku vorhanden. | `docs/03_er_model.md` | Doku pruefen | Zaehler/Lineage-Hinweise aktualisieren. |
| MDM-Schema vorhanden | ERFUELLT | Golden Records, Source Mappings, Resolve-Funktionen. | `sql/05_create_mdm_tables.sql`, `docs/04` | `SELECT mdm.resolve_canonical_key('BAN_101','WMS');` | Keine. |
| Metadatenmanagement-Schema vorhanden | ERFUELLT | `meta.*` und `06b` zur Vollabdeckung. | `sql/06*`, `docs/05` | `SELECT COUNT(*) FROM meta.columns;` | DWH-Grain-Kommentar in `06b` pruefen. |
| Data-Warehouse-Schema vorhanden | ERFUELLT | Star Schema mit Dimensions/Facts/Views. | `sql/07_create_dwh_schema.sql` | `\dt dwh.*` | Verification-Datei korrigieren. |
| ETL verbindet ERP/WMS/TMS mit Analytics/DWH | TEILWEISE ERFUELLT | `etl_dwh.py` existiert; fachliche Zuordnung nur produktbasiert. | `etl_dwh.py`, `dwh.fact_fulfillment` | `python3 bananasupplychain/etl_dwh.py` | Falls moeglich `batch_id`/`order_id` in TMS oder Mapping-Tabelle ergaenzen. |
| Neo4j-Graphmodellierung vorhanden | TEILWEISE ERFUELLT | Graph vorhanden; Demo und ETL-Erwartungen nicht voll konsistent. | `cypher/*`, `etl_load.py` | `cypher-shell ... shortestPath(...)` | Verification aktualisieren. |
| MongoDB-Eventmodellierung vorhanden | ERFUELLT | Vier Collections und TTL/Indexes vorhanden. | `etl_load.py`, `docs/08` | `db.shipment_events.getIndexes()` | Doku-Zaehler fuer `batch_tracking` korrigieren. |
| MinIO-Dokumentenspeicherung vorhanden | TEILWEISE ERFUELLT | Generator und Buckets vorhanden; Zaehlerkonflikt. | `generate_documents.py`, `docs/11` | `mc ls local/delivery-notes --recursive` | 98-Dokument-Erwartung konsistent dokumentieren oder Generator erweitern. |
| Redis-Echtzeitdaten vorhanden | ERFUELLT | Keymodell und Loader vorhanden. | `etl_load.py`, `docs/09` | `redis-cli KEYS "shipment:*"` | Idempotenz/TTL klar dokumentieren. |
| Datenqualitaetsmanagement vorhanden | ERFUELLT | DQ-Konzept und SQL-Audit vorhanden. | `sql/08*`, `docs/06`, `docs/13` | `psql < sql/08b_dq_audit.sql` | Ergebniszahlen frisch nachziehen. |
| Skalenniveaus/Metadaten fuer SQL-Spalten vorhanden | ERFUELLT | Skalenniveaus in `meta.columns`. | `sql/06*`, `docs/05` | `SELECT scale_level, COUNT(*) FROM meta.columns GROUP BY scale_level;` | Keine. |
| Dokumentation ausreichend | TEILWEISE ERFUELLT | Viele gute Docs vorhanden, aber README und Zaehler widerspruechlich. | `docs/*`, `PROJECT_STATUS.md`, `README.md` | Manuelle Review | README ersetzen; stale Zahlen bereinigen. |

---

## 11. Fehler, Risiken und Luecken

### Kritisch vor Abgabe

1. `README.md` ist nicht projektspezifisch.
   - Wirkung: Pruefer findet keinen sauberen Einstieg.
   - Empfehlung: Kurzes README mit Start, Architektur, Befehlen, erwarteten Outputs.

2. Falscher Startordner fuer Generator moeglich.
   - `test_data_generator.py` schreibt relativ nach `shared`.
   - Korrekt: aus Repo-Root starten.
   - Risiko: Aus `bananasupplychain/` entsteht ein falscher Ordner `bananasupplychain/shared`.

3. `sql/09_verification_queries.sql` enthaelt stale/falsche DWH-Pruefung.
   - `dwh.dim_date` hat `full_date`.
   - Verification fragt `date_actual`.
   - Das sollte vor Abgabe korrigiert werden.

4. `verify_all_systems.py` hat stale Neo4j-Erwartungen.
   - Erwartet alte/groessere Datenmengen.
   - Erwartet eine feste Demo-Batch-ID.
   - Auf sauberem aktuellem Lauf wahrscheinlich FAIL.

5. Zaehlerkonflikte in Dokumentation.
   - Aktueller JSON-Stand: 377.
   - Alte Angaben: 383.
   - Aktuelle MinIO-Ableitung: 98.
   - Alte Angaben: 116.
   - DWH: aktueller Code plausibel 10 Fakten, alte Verification teilweise 60.

### Fachliche Modellrisiken

1. Keine exakte Order-Batch-Shipment-Lineage.
   - TMS-Events enthalten keine `order_id` oder `batch_id`.
   - DWH/Graph verbinden ueber Produktcode.
   - Bei mehrfachen Orders pro Produkt kann Zuordnung falsch sein.

2. WMS verarbeitet sechs operative Stationen, Graph/Doku spricht teils von sieben Stationen.
   - Retail Store ist finale Zustellung im TMS.
   - Das ist fachlich erklaerbar, sollte aber in Docs konsistent beschrieben werden.

3. Mongo `batch_tracking` wird unterschiedlich gezaehlt.
   - Technisch: 10 Batch-Dokumente.
   - Verarbeitete Node-Events: 60.
   - Beide Zahlen sind richtig, aber fuer unterschiedliche Granularitaeten.

4. Redis ist nicht voll idempotent.
   - Counter steigen bei Wiederholung.
   - TTL-Keys koennen verschwinden.
   - Fuer Pruefung muss ein frischer Lauf genutzt werden.

### Technische Risiken

1. Doppelte Compose-Dateien.
   - Hauptdatei: `bananasupplychain/container/docker-compose.yml`.
   - Alte Datei: `databasemodels_logistics_playground/container/docker-compose.yml`.
   - Risiko: Falsche Datei startet denselben Container-Namensraum mit altem Cleanup.

2. Cleanup-Skripte koennen Daten loeschen.
   - `reorgFolders.py` loescht `shared/*`.
   - `docker compose down -v` loescht Datenbankvolumes.
   - Playground-Cleanup nicht fuer Banana nutzen.

3. Python-Abhaengigkeiten nicht zentral dokumentiert.
   - Benutzte Pakete: `psycopg2`, `pymongo`, `redis`, `neo4j`, `minio`, `reportlab`, ggf. `pandas`, `matplotlib`.
   - Empfehlung: `requirements.txt` oder README-Abschnitt ergaenzen.

4. Docker Compose nutzt obsolete `version`.
   - Nicht blockierend.
   - Docker meldet Warnung; kann optional entfernt werden.

---

## 12. Empfehlung: abgabebereit ja/nein

**Empfehlung: bedingt abgabebereit, aber noch nicht sauber final.**

Der Kern von Teil 1 ist stark: Infrastruktur, Generator, JSON-Daten, SQL-Modelle, MDM, Metadaten, DQ, DWH, MongoDB, Redis, Neo4j und MinIO sind vorhanden. Das Projekt erfuellt den fachlichen Anspruch der Aufgabenstellung weitgehend.

Vor einer Abgabe sollten aber mindestens diese Punkte erledigt werden:

1. README projektspezifisch schreiben.
2. `sql/09_verification_queries.sql` korrigieren.
3. `verify_all_systems.py` an aktuellen Datenstand anpassen oder als "alte Demo-Verifikation" kennzeichnen.
4. Dokumentationszahlen vereinheitlichen: JSON 377, TMS 257, GPS 112, Mongo Batch Tracking 10 Dokumente/60 Node-Events, DWH 10 Fakten, MinIO 98 Objekte bei aktuellem Datenstand.
5. In DWH/Graph-Doku ehrlich erklaeren, dass Order-Batch-Shipment-Lineage aktuell produktbasiert ist.
6. Startreihenfolge und Startordner in einer finalen Anleitung fixieren.

Wenn diese Punkte korrigiert sind, wirkt Teil 1 sehr wahrscheinlich abgabereif.

---

## 13. Konkrete To-do-Liste vor Abgabe

### Muss vor Abgabe

- [ ] `README.md` durch projektspezifische Anleitung ersetzen.
- [ ] `sql/09_verification_queries.sql` korrigieren: `date_actual` -> `full_date`.
- [ ] Erwartungswert in `sql/09_verification_queries.sql` fuer `dwh.fact_fulfillment` auf aktuelle Grain-Logik anpassen.
- [ ] `bananasupplychain/verify_all_systems.py` Neo4j-Counts auf aktuellen frischen Datenstand anpassen.
- [ ] Feste Demo-Batch-ID in Neo4j-Verifikation entfernen oder als Demo-Check kennzeichnen.
- [ ] Alle Dokumente mit Zaehlern synchronisieren:
  - JSON gesamt: 377.
  - ERP: 50.
  - WMS: 70.
  - TMS: 257.
  - GPS Positionsupdates: 112.
  - Erfolgreiche Deliveries: 8.
  - MinIO erwartbar: 98.
  - DWH-Fakten: 10.
- [ ] In der finalen Anleitung klar sagen: Generator aus Repo-Root starten.
- [ ] `requirements.txt` oder Installationsabschnitt fuer Python-Pakete ergaenzen.

### Sollte vor Abgabe

- [ ] Alte Playground-Dateien als Vorlage markieren, damit sie nicht mit Banana-Kern verwechselt werden.
- [ ] `docker-compose.yml`-Warnung zu `version` optional entfernen.
- [ ] DWH-/Graph-Lineage-Risiko dokumentieren.
- [ ] `reorgFolders.py` mit Sicherheitsabfrage versehen oder nur in README als destruktiv dokumentieren.
- [ ] `docs/11_minio_document_model.md` auf 98 statt 116 Dokumente aktualisieren oder Generator entsprechend erweitern.
- [ ] `docs/12_etl_concept.md` bei Mongo `batch_tracking` von "60 Dokumente" auf "10 Batch-Dokumente mit 60 Node-Eintraegen" korrigieren.
- [ ] `docs/13_data_quality_results.md` nach einem frischen End-to-End-Lauf neu schreiben.

### Optional

- [ ] Echte `batch_id`/`order_id` in TMS-Events ergaenzen, falls der Generator doch erweitert werden darf.
- [ ] Alternativ eine Mapping-Tabelle `shipment_to_batch` im ETL erzeugen, wenn Generator nicht geaendert werden soll.
- [ ] Kleine `make`-/Shell-Runbook-Datei fuer die komplette Ausfuehrungsreihenfolge anlegen.
- [ ] Screenshots aus PostgreSQL, MongoDB, Redis, Neo4j und MinIO fuer die Abgabe sammeln.

---

## 14. Minimaler End-to-End-Run fuer die Pruefung

Diese Sequenz ist der kuerzeste verstaendliche Ablauf fuer einen frischen Nachweis.

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26/bananasupplychain/container
docker compose up -d
```

```bash
cd /Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26
docker exec -i postgres psql -U user -d logistics < sql/01_create_schemas.sql
docker exec -i postgres psql -U user -d logistics < sql/02_create_erp_tables.sql
docker exec -i postgres psql -U user -d logistics < sql/03_create_wms_tables.sql
docker exec -i postgres psql -U user -d logistics < sql/04_create_tms_tables.sql
docker exec -i postgres psql -U user -d logistics < sql/05_create_mdm_tables.sql
docker exec -i postgres psql -U user -d logistics < sql/06_create_metadata_tables.sql
docker exec -i postgres psql -U user -d logistics < sql/06b_metadata_complete.sql
docker exec -i postgres psql -U user -d logistics < sql/07_create_dwh_schema.sql
```

```bash
python3 bananasupplychain/test_data_generator.py
python3 bananasupplychain/etl_load.py
python3 bananasupplychain/generate_documents.py
python3 bananasupplychain/etl_dwh.py
```

```bash
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM erp.orders;"
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM wms.node_processings;"
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM tms.shipments;"
docker exec -it postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM dwh.fact_fulfillment;"
docker exec -it mongodb mongosh logistics --eval "db.shipment_events.countDocuments()"
docker exec -it redis redis-cli DBSIZE
docker exec -it neo4j cypher-shell -u neo4j -p password "MATCH (n) RETURN labels(n)[0], count(n);"
```

Wichtig: Erst nach Korrektur der bekannten Verification-Probleme sollte `sql/09_verification_queries.sql` oder `verify_all_systems.py` als finaler Abgabenbeweis verwendet werden.

