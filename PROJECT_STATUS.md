# Projektstatus – Banana Supply Chain Datenplattform

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26 – TH Lübeck  
**Deadline:** 06.07.2026  
**Zuletzt aktualisiert:** 2026-07-01 (Datengenerator weiter angepasst: 52-Wochen-Zeitreihe mit variabler Bestellanzahl, generatorseitige Event-Zeitstempel, Kühlkettenausreißer, fester Seed für stabile Werteverteilungen und Produktkategorien `Standard`, `Sustainable`, `Premium`, `Specialty`. Dokumentation in README, PROJEKTANLEITUNG, Metadata-/Klassifikations-/Neo4j-Doku nachgezogen. Voller `shared/`-Refresh + ETL/Verify steht nach Abschluss aller Generatoränderungen aus.)

---

## 1. Aktueller Gesamtstatus

**Teil 1 – Datenmanagement:** Alle Pflichtanforderungen erfüllt. Infrastruktur,
Datenmodelle, ETL-Skript, alle Datenbanksysteme und Dokumentation sind erstellt
und getestet.

**Teil 2 – Analytics:** In Bearbeitung. Dashboard (5 Charts), Clustering (k-Means) und Absatzprognose (ARIMA) sind implementiert und getestet. Deskriptive Statistik, KPI-Dokumentation, PowerBI-Dashboard und Abschlussbericht stehen noch aus.

---

## 2. Fertige Artefakte – Teil 1

### Dokumentation (`docs/`)

| Datei | Inhalt | Status |
|---|---|---|
| `docs/00_part1_checklist.md` | Checkliste aller Pflichtanforderungen | abgabefähig |
| `docs/01_data_classification.md` | 13 Eventtypen klassifiziert (Stamm-/Bewegungs-/Ereignisdaten) | abgabefähig |
| `docs/02_target_architecture.md` | Zielarchitektur mit Mermaid-Diagramm | abgabefähig |
| `docs/03_er_model.md` | ER-Modell mit PKs, FKs, Kardinalitäten (Mermaid); `order_id` aus `ERP_BATCHES` entfernt; `ERP_DOCUMENT_REFERENCES` ergaenzt; Cross-Schema-Tabelle vervollstaendigt | abgabefähig |
| `docs/04_masterdata_management.md` | MDM-Konzept, Schlüsselharmonisierung BAN-101/BAN_101/ban-101; View `mdm.v_golden_overview` dokumentiert; Edge Cases (NULL-Handling, ETL-Reihenfolge) ergänzt; Diagnose-Queries für nicht-harmonisierte WMS/TMS-Schlüssel ergänzt | abgabefähig |
| `docs/05_metadata_management.md` | Skalenniveaus für alle Kernspalten; Section 4 um 4 weitere Tabellen (customers, batches, supply_chain_nodes, fact_fulfillment) erweitert; Section 6 auf 52 Schlüsselspalten ausgebaut | abgabefähig |
| `docs/06_data_quality.md` | 6 DQ-Dimensionen, 34 Regeln (28 ursprünglich + 6 ergänzt: PQ-4.10, AQ-5.0×4, KQ-6.3, KQ-6.4); VQ-05 + KQ-04 ergänzt; AQ-01 auf korrekte Logik (kein order_id-FK) korrigiert; DQ-Dashboard aktualisiert | abgabefähig |
| `docs/07_dwh_model.md` | Sternschema-Doku: 7 Dim + Faktentabelle + ETL-Übergänge + 3 analytische Views + PowerBI-Abschnitt + Prüfqueries; `on_time_flag` dokumentiert | abgabefähig |
| `docs/08_mongodb_event_model.md` | 4 Collections; Lifecycle-Modell für shipment_events; TTL-Index (90 Tage); korrekter node_events-Index (batch+node unique); vollständige Knotenobjekte in batch_tracking; Prüfqueries | abgabefähig |
| `docs/09_redis_realtime_model.md` | Key-Taxonomie vollständig (Abschnitte inkl. 3.6 SET `active_shipments`, 3.7 SORTED SET `live_etas`, 3.8 Begründung warehouse_queue weggelassen); TTL-Übersicht; ERP+TMS-Events; ETL-Nachweis mit Prüfabfragen; Datentyp-Begründung (inkl. SET); Abgrenzungstabelle | abgabefähig |
| `docs/10_neo4j_graph_model.md` | 8 Node-Typen, 13 Relationship-Typen, 8 Cypher-Abfragen; Produkt-Lieferanten-Tabelle; Neo4j-vs-SQL-Vergleich | abgabefähig |
| `docs/11_minio_document_model.md` | 4 Buckets, Referenzierungsmuster PostgreSQL <-> MinIO; Bucket Versioning (Kap. 6); Zwei-Phasen-Ansatz (Kap. 7); 6 Prüfqueries (Kap. 8) | abgabefähig |
| `docs/12_etl_concept.md` | ETL-Konzept mit Mapping-Tabelle für alle 13 Eventtypen; Feld-Ebene-Mapping ergänzt (6 Tabellen); Load-Reihenfolge bereinigt; Idempotenz-Abschnitt auf MongoDB/Redis/Neo4j ausgeweitet; ETL-Nachweis mit Prüfqueries hinzugefügt; **Bug-Fix 2026-05-15:** Phase-2-SQL-Beispiel korrigiert (JOIN auf erp.batches.order_id entfernt, der nicht existiert); BatchHarvested-Mapping-Eintrag korrigiert; ETL-Nachweis-Zahlen auf 60 korrigiert | abgabefähig |
| `docs/13_data_quality_results.md` | Audit-Ergebnisse auf 34 Checks aktualisiert (31/34 PASS = 91 %); 3 erwartete FAILs erklärt (4.10 GPS-Simulation, 6.3 SLA-Inkonsistenz, 6.4 Carrier-Modus); §3.7 neu; Dateianzahlen in §7.1 korrigiert (10 orders, 10 batches) | abgabefähig |

### SQL (`sql/`)

| Datei | Inhalt | Status |
|---|---|---|
| `sql/01_create_schemas.sql` | 6 PostgreSQL-Schemas (erp, wms, tms, mdm, meta, dwh) | getestet |
| `sql/02_create_erp_tables.sql` | 6 ERP-Tabellen; `event_timestamp` ergaenzt; `order_id` FK aus `batches` entfernt (nicht in Events) | getestet |
| `sql/03_create_wms_tables.sql` | 3 WMS-Tabellen; `event_timestamp` in `warehouse_skus`; UNIQUE(batch_reference, node_id) in `node_processings` | getestet |
| `sql/04_create_tms_tables.sql` | 6 TMS-Tabellen; `event_timestamp` in `carriers` + `transport_product_references`; `carrier_id NOT NULL` in `shipments` | getestet |
| `sql/05_create_mdm_tables.sql` | 3 MDM-Tabellen; vollst. Seed-Daten (42 GR / 69 Mappings); `resolve_canonical_key()` + `resolve_canonical_key_fuzzy()`; VIEW `mdm.v_golden_overview`; Diagnose-Queries für nicht-harmonisierte Schlüssel; Partial Unique Index; 7 Prüfqueries | erstellt |
| `sql/06_create_metadata_tables.sql` | 3 Meta-Tabellen; explizite Spalteneinträge für alle ERP/WMS/TMS-Kerntabellen (customers, batches, warehouse_skus, supply_chain_nodes, carriers, transport_product_references ergänzt); delay_minutes Quality Rule um SLA-Schwelle ergänzt; TMS.TRANSPORT_COMPLETIONS und TMS.DELIVERIES vollständig dokumentiert | erstellt |
| `sql/07_create_dwh_schema.sql` | 7 Dimensionen + 1 Faktentabelle + Date Spine 2025-2027; `on_time_flag` ergaenzt; ALTER TABLE IF NOT EXISTS fuer Upgrade-Sicherheit; 3 analytische Views (v_carrier_performance, v_kpi_summary, v_monthly_revenue); Pruefqueries | abgabefähig |
| `sql/08_data_quality_checks.sql` | 34 DQ-Prüfungen in 6 Dimensionen; neu: PQ-4.10 (GPS-Routenkorridore), AQ-5.0 (event_timestamp ×4), KQ-6.3 (SLA-Inkonsistenz), KQ-6.4 (Carrier-Transportmodus); 31/34 PASS erwartet | getestet |
| `sql/08b_dq_audit.sql` | Konsolidierter Audit (34 Checks, 1 Result-Set); Checks 4.10 / 5.0×4 / 6.3 / 6.4 ergänzt; 3 erwartete FAILs dokumentiert (Datengenerator-Inkonsistenzen) | getestet |
| `sql/09_verification_queries.sql` | Befüllungsnachweise: COUNT für alle Tabellen (ERP/WMS/TMS/MDM/Meta/DWH), FK-Integrität (intra-Schema + Cross-Schema), DWH Date Spine, fact_fulfillment Plausibilität, MDM Schlüsselauflösung | erstellt |

### Python / ETL (`bananasupplychain/`)

| Datei | Inhalt | Status |
|---|---|---|
| `bananasupplychain/etl_load.py` | ETL-Hauptskript: 395 Events -> PostgreSQL, MongoDB, Redis, Neo4j (kein MinIO); Bug-Fix: node_processings.sku behält WMS-Format (BAN_108, nicht normalisiert); Bug-Fix Neo4j: product_code auf Batch-Node gesetzt, TRANSPORTED_VIA-Relationship in TransportStarted-Handler ergänzt → DeliveryCompleted kann jetzt DELIVERED_TO-Kante anlegen; **2026-06-30:** Redis-Strukturen aus Kapitel 5 Folie 7 ergänzt: SET `active_shipments` (SADD/SREM/DELETE) zeigt WELCHE Sendungen aktiv sind; SORTED SET `live_etas` (ZADD/ZREM/DELETE) sortiert aktive Sendungen nach geschätzter Ankunft (`estimated_arrival` aus dem Event, keine Berechnung). `warehouse_queue` bewusst nicht modelliert (NodeProcessed nur `COMPLETED` → keine Queue-Semantik in den Daten). **Noch nicht gegen laufende Container getestet.** | erstellt |
| `bananasupplychain/verify_all_systems.py` | Technische Nachweise MongoDB/Redis/Neo4j/MinIO: Collection-Counts, Index-Prüfung, TTL-Prüfung, Key-Typen, Node/Rel-Counts, 6-Hop-Pfad, Bucket-Prüfung, Metadaten-Check; PASS/FAIL-Ausgabe; **2026-06-30:** Konsistenz-Checks ergänzt – `active_shipments` (SET + SCARD == Zähler) und `live_etas` (ZSET + ZCARD == SCARD active_shipments) | erstellt |
| `bananasupplychain/etl_dwh.py` | ETL Phase 2: Operative Schemas -> DWH-Sternschema (6 Dimensionen + fact_fulfillment); `on_time_flag` berechnet und geladen; **Bug-Fix 2026-05-15:** Grain auf Endlieferungen korrigiert (INNER JOIN tms.deliveries), fact_fulfillment 10 Zeilen statt 60 – Umsatz-Inflation behoben | abgabefähig |
| `bananasupplychain/generate_documents.py` | MinIO-Dokumentengenerator (einziger MinIO-Einstiegspunkt): alle 4 Buckets; erwartete Ausgabe: 60+7+10+10+10 = 97 PostgreSQL-Referenzen | erstellt |
| `bananasupplychain/test_data_generator.py` | Datengenerator für ERP/WMS/TMS-JSON-Events. **[ANPASSUNG 2026-06-30/2026-07-01]** 52-Wochen-Zeitreihe mit variabler Bestellanzahl, generatorseitige Event-Zeitstempel, Kühlkette mit Brüchen (`COLD_CHAIN_BREAK_RATE=0.15`), `random.seed(42)` für stabile Werteverteilungen, Produktkategorien `Standard`, `Sustainable`, `Premium`, `Specialty` und **Transport-Kern-Set** (`distance_km`, modusgerechte Carrier-Zuordnung + konsistente `carrier_id`, `transport_cost`/`currency`, Plan/Ist-konsistente Zeiten, `delay_reason`). Kern-Set getestet: voller `shared/`-Refresh + ETL + `verify_all_systems` 43/43, DQ 6.4 → PASS, neue Checks 7.1–7.4 PASS. Weitere Generatoränderungen geplant (#6–#10) → finaler Doku-Zahlen-Refresh am Ende. | in Bearbeitung |
| `bananasupplychain/container/docker-compose.yml` | Docker-Setup: PostgreSQL, MongoDB, Redis, Neo4j, MinIO | getestet |

### Cypher (`cypher/`)

| Datei | Inhalt | Status |
|---|---|---|
| `cypher/01_create_graph_model.cypher` | Constraints + 4 Indizes; 8 Node-Typen, 13 Relationships; vollständige SUPPLIES-Kanten für alle 10 Produkte (aus ProductCreated-Events); Beispiel-Batch (BATCH-fc6d22f2-…) mit 7 PROCESSED_AT-Knoten (6-Hop-Pfad); 8 Beispielabfragen; Nachweis-Queries | abgabefähig |
| `cypher/02_verification_queries.cypher` | Aktive (nicht auskommentierte) Verifikationsqueries: Node/Rel-Counts je Typ, Constraints/Indizes prüfen, 6-Hop-Pfad, Fulfillment-Kette, Kühlketten-Monitoring, Integritätsprüfungen | erstellt |

### Generierte Daten (`shared/`)

| Ordner | Dateien | Status |
|---|---|---|
| `shared/erp/` | aktuell alter Bestand: 50 JSON-Events; nach Generator-Refresh erwartet: ca. 560 | Refresh ausstehend |
| `shared/wms/` | aktuell alter Bestand: 70 JSON-Events; nach Generator-Refresh erwartet: ca. 1.600 | Refresh ausstehend |
| `shared/tms/` | aktuell alter Bestand: 275 JSON-Events; nach Generator-Refresh erwartet: ca. 6.650 | Refresh ausstehend |

### Analytics (`analytics/`)

| Datei | Inhalt | Status |
|---|---|---|
| `analytics/dashboard.py` | 5 BI-Charts (Umsatz-Zeitreihe, Carrier-Performance, Umsatz nach Produkt, Verzoegerung, Kuehlkette); Output: PDF + PNG + HTML | abgabefaehig |
| `analytics/clustering.py` | Kundensegmentierung k-Means; Elbow-Methode; Silhouette-Score; Output: PDF + PNG | abgabefaehig |
| `analytics/forecast.py` | Absatzprognose ARIMA(1,0,1); 1 echter Datenpunkt + 26 Monate synthetische History (transparent markiert); Output: PDF + PNG + TXT | abgabefaehig |

---

## 3. Technisch getestete Artefakte

Alle folgenden Komponenten wurden zuletzt am **2026-05-14** gegen laufende Docker-Container geprüft:

| Komponente | Ergebnis |
|---|---|
| PostgreSQL: SQL 01-08 | 6 Schemas, 26 Tabellen erstellt; alle neuen Constraints (UNIQUE, NOT NULL, event_timestamp) aktiv |
| MDM `resolve_canonical_key()` | BAN_101 / ban-101 / BAN-101 -> alle loesen auf BAN-101 auf |
| DWH `dim_date` | 1095 Zeilen (2025-01-01 bis 2027-12-31) |
| DWH `fact_fulfillment` | 10 Facts (1 pro Endlieferung, Grain-Fix 2026-05-15); dim_customer/supplier/carrier mit `source_created_at` befuellt |
| DQ-Checks `08` + `08b` | 34 Checks; 31/34 PASS; 3 erwartete FAILs: 4.10 (GPS weltweit zufällig), 6.3 (delivery_status vs delay_minutes), 6.4 (Carrier-Typ vs Transportmodus); alle dokumentiert in docs/13_data_quality_results.md §3.7 |
| WMS warehouse_skus | sku im WMS-Format (BAN_101), erp_product_code normalisiert (BAN-101) – Fix wirksam |
| erp.batches | kein order_id mehr; harvested_at korrekt aus event.timestamp befuellt |
| ETL Phase 1 | 395 Events -> PostgreSQL/MongoDB/Redis/Neo4j; 10 Suppliers/Customers/Products, 10 Orders/Batches, 60 NodeProcessings, 60 Shipments |
| ETL Phase 2 | 10 dim_customer, 10 dim_supplier, 10 dim_product, 5 dim_carrier, 10 fact_fulfillment (nach Grain-Fix) |
| MongoDB: 4 Collections | 60 shipment_events, 60 node_events, 10 batch_tracking, 10 order_events |
| Redis: alle Key-Typen | STRING, HASH, LIST, SORTED SET, COUNTER + TTLs auf allen Keys; load_redis() verarbeitet ERP+TMS; monitoring:temp_violations mit Datumskey + 7-Tage-TTL; active_shipments INCR/DECR; shipment:route Sorted Set; Produktcache; orders_today mit EXPIREAT |
| Neo4j: Graphmodell | 124 Nodes, alle Relationships; Pfad PLANTATION->RETAIL in 6 Hops |
| MinIO: 4 Buckets | 97 Dokumente: 60 Lieferscheine, 7 Rechnungen, 10 B/L, 10 Zollfreigaben, 10 Qualitätszertifikate |

---

## 4. Noch nicht getestete Artefakte

| Artefakt | Hinweis |
|---|---|
| Neo4j ETL aus TMS-Daten | Stammdaten + Shipments/Deliveries geladen; volle Fulfillment-Routen-Pfade nicht automatisch importiert |
| Generator-Änderungen (2026-06-30/2026-07-01) | Kühlkette/Seed/Zeitstempel/Kategorien + **Transport-Kern-Set** umgesetzt und getestet: sauberer `shared/`-Refresh (255 Orders, 8.476 Events), voller ETL (Postgres/Mongo/Redis/Neo4j/DWH) + `verify_all_systems` **43/43**, DQ 6.4 → PASS, neue Checks 7.1–7.4 PASS. **Offen:** weitere Generatoränderungen (#6 GPS, #7 UUID-Determinismus, #8 Inkonsistenzen, Kunden-Segmente/Preise, Kühlkette→Qualität) und danach **finaler Doku-Zahlen-Refresh in einem Rutsch**. Absolute Zahlen (Umsatz, Kühlketten-%, Counts) daher noch nicht in die Fach-Docs eingetragen. |

---

## 5. Offene Aufgaben – Teil 1

| # | Aufgabe | Priorität |
|---|---|---|
| T1-1 | ETL-Idempotenz | **erledigt 2026-05-14** |
| T1-2 | DQ-Checks systematisch ausfuehren und dokumentieren | **erledigt 2026-05-14** (26/26 PASS + Sanity-Test bestand) |
| T1-3 | ETL Phase 2 testen | **erledigt 2026-05-14** (60 Facts, idempotent) |
| T1-5 | Metadaten auf alle Spalten erweitern | **erledigt 2026-05-14** (168/168 Spalten in `sql/06b_metadata_complete.sql`) |
| T1-6 | MDM um Customer/Supplier/Carrier/Node Golden Records erweitern | **erledigt 2026-05-14** (42 Golden Records, 69 Source Mappings) |
| T1-4 | Neo4j ETL: Fulfillment-Routen automatisch aus TMS-JSON-Daten laden | Niedrig |

---

## 6. Aufgaben – Teil 2: Analytics

### Erledigt

| # | Aufgabe | Status | Nachweis |
|---|---|---|---|
| A-3 | 5 Python-Charts (Matplotlib/Seaborn/Plotly): Umsatz-Zeitreihe, Carrier-Performance, Umsatz nach Produkt, Verzoegerung pro Knoten, Kuehlkettenqualitaet | **abgabefaehig** | `analytics/dashboard.py` → `dashboard.pdf`, `dashboard.png`, `dashboard.html` |
| A-5 | Clustering: Kundensegmentierung mit k-Means (Elbow-Methode, 4 Features, Silhouette-Score) | **abgabefaehig** | `analytics/clustering.py` → `clustering.pdf`, `clustering.png` |
| A-6 | Absatzprognose: ARIMA auf Bestellvolumen (RMSE/MAE im Chart; 26 Monate synthetische History + 1 echter Datenpunkt Mai 2026 – transparent markiert) | **abgabefaehig** | `analytics/forecast.py` → `forecast.pdf`, `forecast.png`, `forecast_model_summary.txt` |

### Noch offen

| # | Aufgabe | Priorität |
|---|---|---|
| A-1 | Deskriptive Statistik: Min, Max, Mittelwert, Median, Std fuer delay_minutes, temperature, quantity, unit_price | Hoch |
| A-2 | KPI-Definition: mindestens 5 KPIs mit Formel, Datenquelle, Zielwert (SQL aus DWH) | Hoch |
| A-4 | PowerBI-Dashboard: Konzept dokumentiert in `docs/07_dwh_model.md`; .pbix-Datei noch nicht erstellt | Hoch |
| A-7 | Abschlussbericht: Zusammenfassung aller Ergebnisse Teil 1 + Teil 2 | Hoch |

---

## 7. Bekannte Fehler

| # | Fehler | Betroffene Datei | Status |
|---|---|---|---|
| F-1 | Mehrfach-Ausfuehrung von `etl_load.py` erzeugt Duplikate in PostgreSQL | `bananasupplychain/etl_load.py` | **behoben 2026-05-14** (UNIQUE-Constraints + ON CONFLICT auf shipment_positions/transport_completions/deliveries) |
| F-2 | VS Code erzeugt beim gleichzeitigen Committen `.git/index.lock` – git-Operationen blockiert | git-Workflow | offen (Workaround: Lock manuell loeschen) |
| F-3 | `normalize_key()` konvertiert WMS-SKU `BAN_101 → BAN-101`; fuer `warehouse_skus` behoben (raw_sku gespeichert); fuer `node_processings.sku` bewusst normalisiert (kein Einfluss auf MDM-Logik, dokumentiert im Schema-Kommentar) | `bananasupplychain/etl_load.py` + `sql/03_create_wms_tables.sql` | behoben 2026-05-14 |
| F-4 | DQ-Checks 5.2/5.3 referenzierten `erp.batches.order_id` (entfernt) – SQL-Fehler bei Ausfuehrung | `sql/08_data_quality_checks.sql` | behoben 2026-05-14 (Checks auf neue Logik umgestellt) |
| F-5 | DQ-Check 6.3 pruefte `carrier_id IS NULL` obwohl Spalte NOT NULL ist – immer 0, irreführend | `sql/08_data_quality_checks.sql` | behoben 2026-05-14 (Check auf SUCCESSFUL vs delay_minutes umgestellt) |
| F-6 | MongoDB `shipment_events` enthält 248 flat-Dokumente (1 pro Event) statt 60 Lifecycle-Dokumente (1 pro Shipment) – ETL-Logik war falsch | `bananasupplychain/etl_load.py` | behoben 2026-05-14 (load_mongodb() auf Lifecycle-Modell umgestellt); Re-Run nach `db.shipment_events.drop()` erforderlich |
| F-7 | `docs/12_etl_concept.md` Phase-2-SQL-Beispiel verwendete `JOIN erp.batches b ON b.order_id = o.order_id` – diese Spalte existiert nicht (F-4-Fix entfernte `order_id` aus `erp.batches`). Mapping-Tabelle BatchHarvested-Zeile beschrieb falschen FK. ETL-Nachweis-Zahlen waren veraltet (121/500 statt 60/60). | `docs/12_etl_concept.md`, `docs/00_part1_checklist.md`, `docs/06_data_quality.md` | behoben 2026-05-15 (SQL korrigiert; BatchHarvested-Mapping-Eintrag korrigiert; Counts auf 60 aktualisiert) |
| F-8 | `docker-compose.yml` cleanup-Service referenzierte nicht-existente Tabellen `OrderDetails`/`Orders` – PostgreSQL-Fehler bei jedem Container-Start, sofort sichtbar in Logs | `bananasupplychain/container/docker-compose.yml` | **behoben 2026-05-15** (SQL auf `tms.shipment_positions WHERE recorded_at < NOW() - 90 days` korrigiert) |
| F-9 | `etl_dwh.py` Grain-Fehler: LEFT JOIN auf tms.deliveries ergab 60 Fact-Zeilen (6 Hops × 10 Iterationen); `SUM(total_value)` war 6-fach inflationiert; alle Revenue-KPIs in `v_kpi_summary` und `v_carrier_performance` falsch | `bananasupplychain/etl_dwh.py`, `sql/07_create_dwh_schema.sql`, `docs/07_dwh_model.md` | **behoben 2026-05-15** (INNER JOIN auf tms.deliveries; Grain = 10 Endlieferungen; Grain-Doku aktualisiert) |
| F-10 | `sql/09_verification_queries.sql` referenzierte `date_actual` – Spalte heißt `full_date` in `dwh.dim_date` → SQL-Fehler bei Ausführung | `sql/09_verification_queries.sql` | **behoben 2026-05-21** (Spaltenname korrigiert) |
| F-11 | `docs/00_part1_checklist.md` Zeilen 200+211: `batch_tracking (60)` falsch – ETL lädt 1 Dokument pro Batch (10 Batches = 10 Dokumente) | `docs/00_part1_checklist.md` | **behoben 2026-05-21** (beide Stellen auf 10 korrigiert) |
| F-12 | Neo4j SUPPLIES: hartcodierte Lieferanten-Zuordnung in cypher/01 wich nach Daten-Neugenerierung (2026-06-04) vom ETL/ERP-Mapping ab → 8 Produkte mit 2 widersprüchlichen Lieferanten (18 statt 10 Kanten); verify verdeckte es (nur Orphan-Check) | `cypher/01_create_graph_model.cypher`, `docs/10_neo4j_graph_model.md`, `bananasupplychain/verify_all_systems.py` | **behoben 2026-06-13** (cypher/01 + docs/10 §5 ans ERP-Mapping angeglichen; verify prüft jetzt „genau 1 Lieferant je Produkt"; Live-Graph repariert; ETL+cypher reproduzierbar 10 Kanten) |

---

## 8. Risiken und Annahmen

| # | Typ | Beschreibung |
|---|---|---|
| R-1 | ~~Risiko~~ | ETL Phase 2 (DWH) getestet; Grain-Fix 2026-05-15 → 10 Facts (Endlieferungen), idempotent – **erledigt** |
| R-2 | Risiko | PowerBI benoetigt laufende PostgreSQL-Verbindung – Verbindungsparameter muessen vor Abgabe geprueft werden |
| R-3 | Annahme | [ANNAHME] Docker-Container laufen bei der Abgabe auf dem lokalen Rechner – kein Cloud-Deployment geplant |
| R-4 | Annahme | [ANNAHME] TMS-Daten enthalten nach Generator-Refresh genuegend Zeitreihenpunkte fuer eine sinnvolle Prognose (aktuell im Code: 52 Wochen mit variabler Bestellanzahl; alter `shared/`-Bestand noch nicht refreshed) |
| R-5 | **erledigt 2026-06-04** | shared/ wurde neu generiert (rohe utcnow()-Timestamps). Die Zeitverteilung (Jan–März 2026) wird ausschließlich durch `_apply_ts_offset()` in `etl_load.py` erzeugt – deterministisch, prozesslogisch begründet, kein Patch auf Quelldaten. Quelldaten und ETL-Logik sind klar getrennt (Option A). |
| R-6 | **erledigt 2026-06-09** | `verify_all_systems.py` führt die zwei kurzlebigen Redis-Keys `shipment:position:*` und `cache:product:*` (je 1 h TTL, `etl_load.py` expire 3600) als **WARN [TTL-abhängig]** statt FAIL – ein regulär abgelaufener Cache erzeugt keinen Fehlalarm mehr, der Lauf bleibt grün (kein stilles PASS bei 0). Persistente Keys (`shipment:status:*`, `order:status:*`, `shipment:route:*`) lösen weiterhin hart FAIL aus. Verify ist damit zeitunabhängig aussagekräftig. |
| R-7 | Richtlinie | **2026-06-30/2026-07-01:** Datengenerator `test_data_generator.py` ist **anpassbar**. Jede Generator-Änderung muss in **allen drei** Dateien dokumentiert werden – `PROJECT_STATUS.md`, `README.md`, `PROJEKTANLEITUNG.md` – und erfordert anschließend `shared/`-Neugenerierung + vollständigen ETL-Lauf, da `shared/` alle fünf Zielsysteme speist. Aktuelle Änderungen sind dokumentiert; Refresh/Verify steht aus. |

---

## 9. Naechste konkrete Schritte

Priorisiert fuer den naechsten Arbeitssprint:

1. **Deskriptive Statistik** – Python-Skript mit `pandas` auf DWH-Daten; Min/Max/Mittelwert/Median/Std fuer delay_minutes, avg_temperature, quantity, unit_price (A-1)
2. **KPIs definieren und berechnen** – mindestens 5 KPIs mit Formel, Datenquelle, Zielwert; SQL aus DWH-Schema (A-2)
3. **PowerBI-Dashboard** – Konzept + Umsetzung mit DWH-Schema als Datenquelle (A-4)
4. **Abschlussbericht** – nach Fertigstellung aller Aufgaben (A-7)

---

*Statuslegende: **erstellt** = vorhanden, nicht ausgefuehrt | **getestet** = technisch geprueft | **abgabefaehig** = fachlich + technisch vollstaendig | **offen** = noch nicht erledigt | **Risiko** = moegliches Problem*
