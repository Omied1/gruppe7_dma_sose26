# Projektstatus – Banana Supply Chain Datenplattform

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26 – TH Lübeck  
**Deadline:** 01.07.2026  
**Zuletzt aktualisiert:** 2026-05-13

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
| `docs/03_er_model.md` | ER-Modell mit PKs, FKs, Kardinalitäten (Mermaid) | abgabefähig |
| `docs/04_masterdata_management.md` | MDM-Konzept, Schlüsselharmonisierung BAN-101/BAN_101/ban-101 | abgabefähig |
| `docs/05_metadata_management.md` | Skalenniveaus (NOMINAL/ORDINAL/INTERVAL/RATIO) für alle Kernspalten | abgabefähig |
| `docs/06_data_quality.md` | 6 DQ-Dimensionen mit je 2–4 Regeln + SQL-Checks | abgabefähig |
| `docs/07_dwh_model.md` | Sternschema-Dokumentation (7 Dimensionen + 1 Faktentabelle) | abgabefähig |
| `docs/08_mongodb_event_model.md` | 4 Collections mit Beispieldokumenten und Indizes | abgabefähig |
| `docs/09_redis_realtime_model.md` | Key-Taxonomie mit TTL, Konfiguration | abgabefähig |
| `docs/10_neo4j_graph_model.md` | 8 Node-Typen, 12 Relationship-Typen, 5 Cypher-Abfragen | abgabefähig |
| `docs/11_minio_document_model.md` | 4 Buckets, Referenzierungsmuster PostgreSQL <-> MinIO | abgabefähig |
| `docs/12_etl_concept.md` | ETL-Konzept mit Mapping-Tabelle für alle 13 Eventtypen | abgabefähig |

### SQL (`sql/`)

| Datei | Inhalt | Status |
|---|---|---|
| `sql/01_create_schemas.sql` | 6 PostgreSQL-Schemas (erp, wms, tms, mdm, meta, dwh) | getestet |
| `sql/02_create_erp_tables.sql` | 6 ERP-Tabellen | getestet |
| `sql/03_create_wms_tables.sql` | 3 WMS-Tabellen + 7 Knoten-Stammdaten | getestet |
| `sql/04_create_tms_tables.sql` | 6 TMS-Tabellen | getestet |
| `sql/05_create_mdm_tables.sql` | 3 MDM-Tabellen + Funktion `mdm.resolve_canonical_key()` | getestet |
| `sql/06_create_metadata_tables.sql` | 3 Meta-Tabellen + exemplarische Einträge | getestet |
| `sql/07_create_dwh_schema.sql` | 7 Dimensionen + 1 Faktentabelle + Date Spine 2025-2027 (1095 Zeilen) | getestet |
| `sql/08_data_quality_checks.sql` | 20+ SQL-Qualitätsprüfungen über alle 6 DQ-Dimensionen | erstellt |

### Python / ETL (`bananasupplychain/`)

| Datei | Inhalt | Status |
|---|---|---|
| `bananasupplychain/etl_load.py` | ETL-Hauptskript: 383 Events -> PostgreSQL, MongoDB, Redis, Neo4j, MinIO | getestet |
| `bananasupplychain/etl_dwh.py` | ETL Phase 2: Operative Schemas -> DWH-Sternschema (6 Dimensionen + fact_fulfillment) | getestet |
| `bananasupplychain/generate_documents.py` | MinIO-Dokumentengenerator (PDFs + 66 PostgreSQL-Referenzen) | getestet |
| `bananasupplychain/test_data_generator.py` | Datengenerator für ERP/WMS/TMS-JSON-Events | getestet |
| `bananasupplychain/container/docker-compose.yml` | Docker-Setup: PostgreSQL, MongoDB, Redis, Neo4j, MinIO | getestet |

### Cypher (`cypher/`)

| Datei | Inhalt | Status |
|---|---|---|
| `cypher/01_create_graph_model.cypher` | Constraints, Stammdaten, Supply-Chain-Topologie, Beispiel-Fulfillment | getestet |

### Generierte Daten (`shared/`)

| Ordner | Dateien | Status |
|---|---|---|
| `shared/erp/` | 50 JSON-Events | getestet |
| `shared/wms/` | 70 JSON-Events | getestet |
| `shared/tms/` | 263 JSON-Events | getestet |

---

## 3. Technisch getestete Artefakte

Alle folgenden Komponenten wurden zuletzt am **2026-05-14** gegen laufende Docker-Container geprüft:

| Komponente | Ergebnis |
|---|---|
| PostgreSQL: SQL 01-08 | 6 Schemas, 26 Tabellen erstellt (mit UNIQUE-Constraints auf TMS-Tabellen) |
| MDM `resolve_canonical_key()` | BAN_101 / ban-101 / BAN-101 -> alle loesen auf BAN-101 auf |
| DWH `dim_date` | 1095 Zeilen (2025-01-01 bis 2027-12-31) |
| DWH `fact_fulfillment` | 60 Facts (Shipment-Hop-Grain): 6 SUCCESSFUL + 4 DELAYED + 50 IN_TRANSIT |
| MongoDB: 4 Collections | shipment_events (248), node_events (60), batch_tracking (10), order_events (10) |
| Redis: alle Key-Typen | STRING, HASH, LIST, SORTED SET, COUNTER + TTLs auf info/position |
| Neo4j: Graphmodell | 125+ Nodes, alle Relationships; Pfad PLANTATION->RETAIL in 6 Hops |
| MinIO: 4 Buckets | 60 Lieferscheine, 6 Rechnungen, 66 PostgreSQL-Referenzen |
| ETL Phase 1 idempotent | 2 aufeinanderfolgende Läufe ergeben identische Zeilenzahlen (PG + MongoDB) |
| ETL Phase 2 idempotent | DELETE+INSERT-Pattern, 60 Facts konstant bei Mehrfach-Lauf |

---

## 4. Noch nicht getestete Artefakte

| Artefakt | Hinweis |
|---|---|
| `sql/08_data_quality_checks.sql` | Erstellt, aber noch nicht systematisch ausgefuehrt und Ergebnisse dokumentiert |
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

---

## 8. Risiken und Annahmen

| # | Typ | Beschreibung |
|---|---|---|
| R-1 | Risiko | ETL Phase 2 (DWH) implementiert aber noch nicht getestet – erst nach Docker-Test freigeben |
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
