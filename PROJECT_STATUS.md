# Projektstatus – Banana Supply Chain Datenplattform

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26 – TH Lübeck  
**Deadline:** 01.07.2026  
**Zuletzt aktualisiert:** 2026-05-15 (Review-Fixes F-1 + F-2)

---

## 1. Aktueller Gesamtstatus

**Teil 1 – Datenmanagement:** Alle Pflichtanforderungen erfüllt. Infrastruktur,
Datenmodelle, ETL-Skript, alle Datenbanksysteme und Dokumentation sind erstellt
und getestet.

**Teil 2 – Analytics:** Noch nicht begonnen. Vollständig offen.

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
| `docs/06_data_quality.md` | 6 DQ-Dimensionen, 28 Regeln; VQ-05 + KQ-04 ergänzt; AQ-01 auf korrekte Logik (kein order_id-FK) korrigiert; DQ-Dashboard aktualisiert | abgabefähig |
| `docs/07_dwh_model.md` | Sternschema-Doku: 7 Dim + Faktentabelle + ETL-Übergänge + 3 analytische Views + PowerBI-Abschnitt + Prüfqueries; `on_time_flag` dokumentiert | abgabefähig |
| `docs/08_mongodb_event_model.md` | 4 Collections; Lifecycle-Modell für shipment_events; TTL-Index (90 Tage); korrekter node_events-Index (batch+node unique); vollständige Knotenobjekte in batch_tracking; Prüfqueries | abgabefähig |
| `docs/09_redis_realtime_model.md` | Key-Taxonomie vollständig (7 Abschnitte); TTL-Übersicht; ERP+TMS-Events; ETL-Nachweis mit Prüfabfragen; Datentyp-Begründung; Abgrenzungstabelle | abgabefähig |
| `docs/10_neo4j_graph_model.md` | 8 Node-Typen, 13 Relationship-Typen, 8 Cypher-Abfragen; Produkt-Lieferanten-Tabelle; Neo4j-vs-SQL-Vergleich | abgabefähig |
| `docs/11_minio_document_model.md` | 4 Buckets, Referenzierungsmuster PostgreSQL <-> MinIO; Bucket Versioning (Kap. 6); Zwei-Phasen-Ansatz (Kap. 7); 6 Prüfqueries (Kap. 8) | abgabefähig |
| `docs/12_etl_concept.md` | ETL-Konzept mit Mapping-Tabelle für alle 13 Eventtypen; Feld-Ebene-Mapping ergänzt (6 Tabellen); Load-Reihenfolge bereinigt; Idempotenz-Abschnitt auf MongoDB/Redis/Neo4j ausgeweitet; ETL-Nachweis mit Prüfqueries hinzugefügt; **Bug-Fix 2026-05-15:** Phase-2-SQL-Beispiel korrigiert (JOIN auf erp.batches.order_id entfernt, der nicht existiert); BatchHarvested-Mapping-Eintrag korrigiert; ETL-Nachweis-Zahlen auf 60 korrigiert | abgabefähig |
| `docs/13_data_quality_results.md` | Live-Audit-Ergebnisse (28/28 PASS); Check 5.2 korrigiert; neue Checks 1.5 + 3.4 dokumentiert; Abschnitt 7 ergänzt: systemübergreifende Befüllungsnachweise für alle 5 Systeme (PostgreSQL/MDM/DWH/MongoDB/Redis/Neo4j/MinIO) | abgabefähig |

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
| `sql/08_data_quality_checks.sql` | 28 DQ-Prüfungen in 6 Dimensionen; VQ-05 + KQ-04 neu; DQ 6.3 auf carrier_id-Check korrigiert (konsistent mit 08b); Datenbasis-Prüfquery am Ende ergänzt | getestet |
| `sql/08b_dq_audit.sql` | Konsolidierter Audit (28 Checks, 1 Result-Set); Bugfix Check 5.2 (broken JOIN auf nicht-existente order_id-Spalte); Pos-Nummern neu durchgezählt; VQ-05 + KQ-04 eingebaut | getestet |
| `sql/09_verification_queries.sql` | Befüllungsnachweise: COUNT für alle Tabellen (ERP/WMS/TMS/MDM/Meta/DWH), FK-Integrität (intra-Schema + Cross-Schema), DWH Date Spine, fact_fulfillment Plausibilität, MDM Schlüsselauflösung | erstellt |

### Python / ETL (`bananasupplychain/`)

| Datei | Inhalt | Status |
|---|---|---|
| `bananasupplychain/etl_load.py` | ETL-Hauptskript: 714 Events -> 5 Systeme; Bug-Fix: node_processings.sku behält WMS-Format (BAN_108, nicht normalisiert); Bug-Fix Neo4j: product_code auf Batch-Node gesetzt, TRANSPORTED_VIA-Relationship in TransportStarted-Handler ergänzt → DeliveryCompleted kann jetzt DELIVERED_TO-Kante anlegen | erstellt |
| `bananasupplychain/verify_all_systems.py` | Technische Nachweise MongoDB/Redis/Neo4j/MinIO: Collection-Counts, Index-Prüfung, TTL-Prüfung, Key-Typen, Node/Rel-Counts, 6-Hop-Pfad, Bucket-Prüfung, Metadaten-Check; PASS/FAIL-Ausgabe | erstellt |
| `bananasupplychain/etl_dwh.py` | ETL Phase 2: Operative Schemas -> DWH-Sternschema (6 Dimensionen + fact_fulfillment); `on_time_flag` berechnet und geladen; **Bug-Fix 2026-05-15:** Grain auf Endlieferungen korrigiert (INNER JOIN tms.deliveries), fact_fulfillment 20 Zeilen statt 120 – Umsatz-Inflation behoben | abgabefähig |
| `bananasupplychain/generate_documents.py` | MinIO-Dokumentengenerator: alle 4 Buckets; neu: Bill of Lading + Customs Clearance (transport-docs) für 20 SEA_FREIGHT-Shipments; erwartete Ausgabe: 60+20+20+6+10 = 116 PostgreSQL-Referenzen | erstellt |
| `bananasupplychain/test_data_generator.py` | Datengenerator für ERP/WMS/TMS-JSON-Events | getestet |
| `bananasupplychain/container/docker-compose.yml` | Docker-Setup: PostgreSQL, MongoDB, Redis, Neo4j, MinIO | getestet |

### Cypher (`cypher/`)

| Datei | Inhalt | Status |
|---|---|---|
| `cypher/01_create_graph_model.cypher` | Constraints + 4 Indizes; 8 Node-Typen, 13 Relationships; vollständige SUPPLIES-Kanten für alle 10 Produkte (aus ProductCreated-Events); Beispiel-Batch (BATCH-9c6818ad-…) mit 7 PROCESSED_AT-Knoten (6-Hop-Pfad); 8 Beispielabfragen; Nachweis-Queries | abgabefähig |
| `cypher/02_verification_queries.cypher` | Aktive (nicht auskommentierte) Verifikationsqueries: Node/Rel-Counts je Typ, Constraints/Indizes prüfen, 6-Hop-Pfad, Fulfillment-Kette, Kühlketten-Monitoring, Integritätsprüfungen | erstellt |

### Generierte Daten (`shared/`)

| Ordner | Dateien | Status |
|---|---|---|
| `shared/erp/` | 70 JSON-Events | getestet |
| `shared/wms/` | 130 JSON-Events | getestet |
| `shared/tms/` | 514 JSON-Events | getestet |

---

## 3. Technisch getestete Artefakte

Alle folgenden Komponenten wurden zuletzt am **2026-05-14** gegen laufende Docker-Container geprüft:

| Komponente | Ergebnis |
|---|---|
| PostgreSQL: SQL 01-08 | 6 Schemas, 26 Tabellen erstellt; alle neuen Constraints (UNIQUE, NOT NULL, event_timestamp) aktiv |
| MDM `resolve_canonical_key()` | BAN_101 / ban-101 / BAN-101 -> alle loesen auf BAN-101 auf |
| DWH `dim_date` | 1095 Zeilen (2025-01-01 bis 2027-12-31) |
| DWH `fact_fulfillment` | 20 Facts (1 pro Endlieferung, Grain-Fix 2026-05-15); dim_customer/supplier/carrier mit `source_created_at` befuellt |
| DQ-Checks `08` | 29/30 PASS + 1 echter Befund: 6x SUCCESSFUL-Delivery trotz delay_minutes > 0 (Datengenerator-Inkonsistenz) |
| WMS warehouse_skus | sku im WMS-Format (BAN_101), erp_product_code normalisiert (BAN-101) – Fix wirksam |
| erp.batches | kein order_id mehr; harvested_at korrekt aus event.timestamp befuellt |
| ETL Phase 1 | 714 Events -> 5 Systeme; 10 Suppliers/Customers/Products, 20 Orders/Batches, 120 NodeProcessings, 120 Shipments |
| ETL Phase 2 | 10 dim_customer, 10 dim_supplier, 10 dim_product, 5 dim_carrier, 20 fact_fulfillment (nach Grain-Fix) |
| MongoDB: 4 Collections | shipment_events (248 flat, vor Korrektur); ETL load_mongodb() korrigiert – Re-Run erforderlich für Lifecycle-Modell (60 Docs statt 248) |
| Redis: alle Key-Typen | STRING, HASH, LIST, SORTED SET, COUNTER + TTLs auf allen Keys; load_redis() verarbeitet ERP+TMS; monitoring:temp_violations mit Datumskey + 7-Tage-TTL; active_shipments INCR/DECR; shipment:route Sorted Set; Produktcache; orders_today mit EXPIREAT |
| Neo4j: Graphmodell | 125+ Nodes, alle Relationships; Pfad PLANTATION->RETAIL in 6 Hops |
| MinIO: 4 Buckets | 120 Lieferscheine, 6 Rechnungen (ETL-Wiederholung gegen Docker erforderlich für aktualisierten Stand) |

---

## 4. Noch nicht getestete Artefakte

| Artefakt | Hinweis |
|---|---|
| Neo4j ETL aus TMS-Daten | Stammdaten + Shipments/Deliveries geladen; volle Fulfillment-Routen-Pfade nicht automatisch importiert |

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

## 6. Offene Aufgaben – Teil 2: Analytics

| # | Aufgabe | Priorität |
|---|---|---|
| A-1 | Deskriptive Statistik: Min, Max, Mittelwert, Median, Std fuer delay_minutes, temperature, quantity | Hoch |
| A-2 | KPI-Definition: mindestens 5 KPIs mit Formel, Datenquelle, Zielwert | Hoch |
| A-3 | 5 Python-Charts (Matplotlib/Seaborn): Lieferverzoegerungen, Temperatur, Bestellwert, Routen-Heatmap, Batchqualitaet | Hoch |
| A-4 | PowerBI-Dashboard: Konzept + Umsetzung mit DWH-Schema als Datenquelle | Hoch |
| A-5 | Clustering: Kundensegmentierung mit k-Means (Elbow-Methode) | Mittel |
| A-6 | Absatzprognose: Zeitreihe Bestellvolumen mit ARIMA oder Prophet (RMSE/MAE angeben) | Mittel |
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
| F-9 | `etl_dwh.py` Grain-Fehler: LEFT JOIN auf tms.deliveries ergab 120 Fact-Zeilen (6 Hops × 20 Iterationen); `SUM(total_value)` war 6-fach inflationiert; alle Revenue-KPIs in `v_kpi_summary` und `v_carrier_performance` falsch | `bananasupplychain/etl_dwh.py`, `sql/07_create_dwh_schema.sql`, `docs/07_dwh_model.md` | **behoben 2026-05-15** (INNER JOIN auf tms.deliveries; Grain = 20 Endlieferungen; Grain-Doku aktualisiert) |

---

## 8. Risiken und Annahmen

| # | Typ | Beschreibung |
|---|---|---|
| R-1 | ~~Risiko~~ | ETL Phase 2 (DWH) getestet; Grain-Fix 2026-05-15 → 20 Facts (Endlieferungen), idempotent – **erledigt** |
| R-2 | Risiko | PowerBI benoetigt laufende PostgreSQL-Verbindung – Verbindungsparameter muessen vor Abgabe geprueft werden |
| R-3 | Annahme | [ANNAHME] Docker-Container laufen bei der Abgabe auf dem lokalen Rechner – kein Cloud-Deployment geplant |
| R-4 | Annahme | [ANNAHME] TMS-Daten enthalten genuegend Zeitreihenpunkte fuer eine sinnvolle Prognose (aktuell 10 Iterationen) |

---

## 9. Naechste konkrete Schritte

Priorisiert fuer den naechsten Arbeitssprint:

1. **ETL Phase 2 implementieren** (`analytics/etl_dwh.py`) – operative PostgreSQL-Schemas -> DWH befuellen. Blockiert alle Analytics-Aufgaben.
2. **Deskriptive Statistik** – Python-Skript mit `pandas` auf DWH-Daten (A-1)
3. **KPIs definieren und berechnen** – SQL + Python (A-2)
4. **5 Python-Charts erstellen** – Matplotlib/Seaborn (A-3)
5. **PowerBI-Dashboard** – Verbindung zu PostgreSQL DWH testen (A-4)
6. **Clustering** – k-Means auf Kundendaten (A-5)
7. **Absatzprognose** – ARIMA oder Prophet (A-6)
8. **Abschlussbericht** – nach Fertigstellung aller Aufgaben (A-7)

---

*Statuslegende: **erstellt** = vorhanden, nicht ausgefuehrt | **getestet** = technisch geprueft | **abgabefaehig** = fachlich + technisch vollstaendig | **offen** = noch nicht erledigt | **Risiko** = moegliches Problem*
