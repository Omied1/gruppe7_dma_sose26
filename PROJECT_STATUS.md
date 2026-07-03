# Projektstatus – Banana Supply Chain Datenplattform

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26 – TH Lübeck  
**Deadline:** 06.07.2026  
**Zuletzt aktualisiert:** 2026-07-01 (Datengenerator weiter angepasst: 52-Wochen-Zeitreihe mit variabler Bestellanzahl, generatorseitige Event-Zeitstempel, Kühlkettenausreißer, fester Seed für stabile Werteverteilungen und Produktkategorien `Standard`, `Sustainable`, `Premium`, `Specialty`. Dokumentation in README, PROJEKTANLEITUNG, Metadata-/Klassifikations-/Neo4j-Doku nachgezogen. Danach: faithful DWH via `order_reference`, Analytics auf neue Felder gehoben, voller Refresh (252 Orders/8.356 Events) + verify 43 Checks/0 FAIL + exakte Zahlen in allen Fach-Docs — **erledigt (2026-07-02)**.)

**Nachtrag 2026-07-02 (Packaging/Doku):** `requirements.txt` angelegt (13 gepinnte Pakete = getestete Umgebung); die unvollständige `pip install`-Zeile in `README.md` und `PROJEKTANLEITUNG.md` um `seaborn`, `plotly`, `numpy` ergänzt und auf `requirements.txt` verwiesen (Audit-Punkte **M-1/M-2 erledigt**; reine Doku/Packaging, kein `shared/`-Refresh oder ETL nötig).

**Nachtrag 2026-07-02 (M-3, Stack-Kollision):** Die Dozenten-Vorlage `databasemodels_logistics_playground/container/docker-compose.yml` teilt `container_name`, Ports und – über den Ordnernamen `container` – Compose-Projektname **und Volumes** (`container_*`) mit dem produktiven Stack. Live verifiziert: laufender Stack ist der Banana-Stack (cleanup löscht `tms.shipment_positions`), Volumes werden gemeinsam genutzt. Gelöst per **Warnhinweis** in `README.md` + `PROJEKTANLEITUNG.md` (nur einen Stack starten). Die Vorlagedateien wurden bewusst **nicht** verändert – ihr `initialize_db.py`/`simulate_fullfillment.py` verdrahtet Ports/Containernamen hart, ein Umbenennen würde die Vorlage brechen und die Abgabe verfälschen. **M-3 erledigt.**

**Nachtrag 2026-07-02 (Kleinkram-Audit):** Restliche Audit-Punkte abgeräumt: `docs/00` untere Hälfte auf kanonische Zahlen gehoben (275 → 6.300 TMS; 395-Event-/60-Shipment-/10-Order-Stand → 8.356/1.512/252; Datei-Listen um docs 13–16 + sql 06b/10 ergänzt; Test-Sektion auf faithful DWH + verify aktualisiert). Ebenso `docs/12` §7 (ETL-Nachweis-Tabelle + Prüfqueries) von 395-Event- auf 8.356-Event-Basis gehoben. SKILL.md Event-Counts (50/70/257/263 → 534/1.522/6.300, ETL 383 → 8.356; DDL 01–08 → 01–10). README/SKILL Doc-/SQL-Counts (00–16, 01–10). `.gitignore`-Platzhalter `{database_file}` entfernt. `dashboard.py`-Docstring ohne ungenutztes `kaleido` (verifiziert: nur `savefig`/`write_html`, kein `write_image`). „43/43 PASS" → „43 Checks, 0 FAIL" (docs/16 + README + PROJECT_STATUS; zeitunabhängig korrekt, da 2 der 43 Checks TTL-bedingt WARN sein können). Veraltete Root-PDFs (Projektstand/Projektanleitung) **gelöscht** – Inhalt widersprach den .md (383 Events/60 Shipments), Generatoren schrieben in alten Desktop-Pfad; die .md sind maßgeblich. Die zugehörigen Generator-Skripte (`create_status_report.py`, `create_guide_pdf.py`) sind damit verwaist. Ein anschließender Vollsweep hob weitere Alt-Zahlen in Abgabe-Docs auf kanonisch (`docs/01` Eventtyp-Gesamtübersicht 377 → 8.356; `docs/11` 377 Events/98 Dokumente → 8.356/2.444; `PROJEKTANLEITUNG` erwartete ETL-Ausgabe 50/70/10 Orders/60 Shipments → 534/1.522/252/1.512 + F-6-Troubleshooting-Eintrag volumen-unabhängig) — `docs/` + `README` + `PROJEKTANLEITUNG` sind jetzt frei von Alt-Zahlen (Sweep grün). **Alle Audit-Punkte (M-1/M-2/M-3 + Kleinkram) erledigt.**

---

## 1. Aktueller Gesamtstatus

**Teil 1 – Datenmanagement:** Alle Pflichtanforderungen erfüllt. Infrastruktur,
Datenmodelle, ETL-Skript, alle Datenbanksysteme und Dokumentation sind erstellt
und getestet.

**Teil 2 – Analytics:** Dashboard (5 Charts, auf neue Felder gehoben: Kundensegment-Umsatz, Verspätungsgründe, Bestellwert-Boxplot/Kundentyp, Transportkosten/Route, Batchqualität/Zeit), Clustering (k-Means + Cluster↔Segment-Abgleich) und Absatzprognose (ARIMA) laufen gegen den faithful DWH (252 Fact-Zeilen, 13 Monate). **Neu (2026-07-02):** Deskriptive Statistik (`descriptive_stats.py`), KPI-Katalog (`sql/10_kpi_queries.sql` + `docs/14`), PowerBI-Konzept (`docs/15`) und Abschlussbericht (`docs/16`) erstellt und getestet → **A-1 bis A-7 abgabefähig, Teil 2 vollständig**.

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
| `docs/06_data_quality.md` | 6 DQ-Dimensionen, 41 Regeln (inkl. 7.1–7.7: Kern-Set/Segment/Qualität); DQ-Dashboard 38/41 PASS aktualisiert | abgabefähig |
| `docs/07_dwh_model.md` | Sternschema-Doku: 7 Dim + Faktentabelle + ETL-Übergänge + 3 analytische Views + PowerBI-Abschnitt + Prüfqueries; `on_time_flag` dokumentiert | abgabefähig |
| `docs/08_mongodb_event_model.md` | 4 Collections; Lifecycle-Modell für shipment_events; TTL-Index (90 Tage); korrekter node_events-Index (batch+node unique); vollständige Knotenobjekte in batch_tracking; Prüfqueries | abgabefähig |
| `docs/09_redis_realtime_model.md` | Key-Taxonomie vollständig (Abschnitte inkl. 3.6 SET `active_shipments`, 3.7 SORTED SET `live_etas`, 3.8 Begründung warehouse_queue weggelassen); TTL-Übersicht; ERP+TMS-Events; ETL-Nachweis mit Prüfabfragen; Datentyp-Begründung (inkl. SET); Abgrenzungstabelle | abgabefähig |
| `docs/10_neo4j_graph_model.md` | 8 Node-Typen, 13 Relationship-Typen, 8 Cypher-Abfragen; Produkt-Lieferanten-Tabelle; Neo4j-vs-SQL-Vergleich | abgabefähig |
| `docs/11_minio_document_model.md` | 4 Buckets, Referenzierungsmuster PostgreSQL <-> MinIO; Bucket Versioning (Kap. 6); Zwei-Phasen-Ansatz (Kap. 7); 6 Prüfqueries (Kap. 8) | abgabefähig |
| `docs/12_etl_concept.md` | ETL-Konzept mit Mapping-Tabelle für alle 13 Eventtypen; Feld-Ebene-Mapping ergänzt (6 Tabellen); Load-Reihenfolge bereinigt; Idempotenz-Abschnitt auf MongoDB/Redis/Neo4j ausgeweitet; ETL-Nachweis mit Prüfqueries hinzugefügt; **Bug-Fix 2026-05-15:** Phase-2-SQL-Beispiel korrigiert (JOIN auf erp.batches.order_id entfernt, der nicht existiert); BatchHarvested-Mapping-Eintrag korrigiert; ETL-Nachweis-Zahlen auf 60 korrigiert | abgabefähig |
| `docs/13_data_quality_results.md` | Audit auf **41 Checks** (38/41 PASS = 93 %); 3 bewusste FAILs (4.3/4.4 Kühlkette + 6.3 SLA); 4.10 (GPS) + 6.4 (Carrier-Modus) behoben → PASS; §3.7 + Tabelle + 7.x aktualisiert; Zahlen auf faithful DWH | abgabefähig |

### SQL (`sql/`)

| Datei | Inhalt | Status |
|---|---|---|
| `sql/01_create_schemas.sql` | 6 PostgreSQL-Schemas (erp, wms, tms, mdm, meta, dwh) | getestet |
| `sql/02_create_erp_tables.sql` | 6 ERP-Tabellen; `event_timestamp` ergaenzt; `order_id` FK aus `batches` entfernt (nicht in Events) | getestet |
| `sql/03_create_wms_tables.sql` | 3 WMS-Tabellen; `event_timestamp` in `warehouse_skus`; UNIQUE(batch_reference, node_id) in `node_processings` | getestet |
| `sql/04_create_tms_tables.sql` | 6 TMS-Tabellen; `event_timestamp` in `carriers` + `transport_product_references`; `carrier_id NOT NULL` in `shipments` | getestet |
| `sql/05_create_mdm_tables.sql` | 3 MDM-Tabellen; vollst. Seed-Daten (42 GR / 69 Mappings); `resolve_canonical_key()` + `resolve_canonical_key_fuzzy()`; VIEW `mdm.v_golden_overview`; Diagnose-Queries für nicht-harmonisierte Schlüssel; Partial Unique Index; 7 Prüfqueries | erstellt |
| `sql/06_create_metadata_tables.sql` | 3 Meta-Tabellen; explizite Spalteneinträge für alle ERP/WMS/TMS-Kerntabellen (customers, batches, warehouse_skus, supply_chain_nodes, carriers, transport_product_references ergänzt); delay_minutes Quality Rule um SLA-Schwelle ergänzt; TMS.TRANSPORT_COMPLETIONS und TMS.DELIVERIES vollständig dokumentiert | erstellt |
| `sql/07_create_dwh_schema.sql` | 7 Dimensionen + 1 Faktentabelle + Date Spine 2025-2027; `on_time_flag` ergaenzt; ALTER TABLE IF NOT EXISTS fuer Upgrade-Sicherheit; 5 analytische Views (`v_carrier_performance`, `v_carrier_speed_performance`, `v_batch_quality`, `v_kpi_summary`, `v_monthly_revenue`); Pruefqueries | abgabefähig |
| `sql/08_data_quality_checks.sql` | 41 DQ-Prüfungen in 6 Dimensionen (inkl. 7.1–7.7 Kern-Set/Segment/Qualität); 38/41 PASS (3 bewusste FAILs: 4.3/4.4/6.3) | getestet |
| `sql/08b_dq_audit.sql` | Konsolidierter Audit (41 Checks, 1 Result-Set); 7.1–7.7 ergänzt; 3 bewusste FAILs (4.3/4.4/6.3), 4.10 + 6.4 behoben | getestet |
| `sql/09_verification_queries.sql` | Befüllungsnachweise: COUNT für alle Tabellen (ERP/WMS/TMS/MDM/Meta/DWH), FK-Integrität (intra-Schema + Cross-Schema), DWH Date Spine, fact_fulfillment Plausibilität, MDM Schlüsselauflösung | erstellt |

### Python / ETL (`bananasupplychain/`)

| Datei | Inhalt | Status |
|---|---|---|
| `bananasupplychain/etl_load.py` | ETL-Hauptskript: 395 Events -> PostgreSQL, MongoDB, Redis, Neo4j (kein MinIO); Bug-Fix: node_processings.sku behält WMS-Format (BAN_108, nicht normalisiert); Bug-Fix Neo4j: product_code auf Batch-Node gesetzt, TRANSPORTED_VIA-Relationship in TransportStarted-Handler ergänzt → DeliveryCompleted kann jetzt DELIVERED_TO-Kante anlegen; **2026-06-30:** Redis-Strukturen aus Kapitel 5 Folie 7 ergänzt: SET `active_shipments` (SADD/SREM/DELETE) zeigt WELCHE Sendungen aktiv sind; SORTED SET `live_etas` (ZADD/ZREM/DELETE) sortiert aktive Sendungen nach geschätzter Ankunft (`estimated_arrival` aus dem Event, keine Berechnung). `warehouse_queue` bewusst nicht modelliert (NodeProcessed nur `COMPLETED` → keine Queue-Semantik in den Daten). **Noch nicht gegen laufende Container getestet.** | erstellt |
| `bananasupplychain/verify_all_systems.py` | Technische Nachweise MongoDB/Redis/Neo4j/MinIO: Collection-Counts, Index-Prüfung, TTL-Prüfung, Key-Typen, Node/Rel-Counts, 6-Hop-Pfad, Bucket-Prüfung, Metadaten-Check; PASS/FAIL-Ausgabe; **2026-06-30:** Konsistenz-Checks ergänzt – `active_shipments` (SET + SCARD == Zähler) und `live_etas` (ZSET + ZCARD == SCARD active_shipments) | erstellt |
| `bananasupplychain/etl_dwh.py` | ETL Phase 2: Operative Schemas -> DWH-Sternschema (6 Dimensionen + fact_fulfillment); `on_time_flag` berechnet; Grain = Endlieferung (INNER JOIN tms.deliveries); **[ANPASSUNG 2026-07-02]** faithful Mapping via `order_reference` → 252 Fact-Zeilen mit echter Bestellung/Datum/Kunde/Batch (13 Monate), `SUM(total_value)`=325.009 EUR; Dim-Refresh vor Load; Views `v_batch_quality` + Transport-Measures | abgabefähig |
| `bananasupplychain/generate_documents.py` | MinIO-Dokumentengenerator (einziger MinIO-Einstiegspunkt): alle 4 Buckets; erwartete Ausgabe: 60+7+10+10+10 = 97 PostgreSQL-Referenzen | erstellt |
| `bananasupplychain/test_data_generator.py` | Datengenerator für ERP/WMS/TMS-JSON-Events. **[ANPASSUNG 2026-06-30/2026-07-01]** 52-Wochen-Zeitreihe mit variabler Bestellanzahl, generatorseitige Event-Zeitstempel, Kühlkette mit Brüchen (`COLD_CHAIN_BREAK_RATE=0.15`), `random.seed(42)` für stabile Werteverteilungen, Produktkategorien `Standard`, `Sustainable`, `Premium`, `Specialty` , **Transport-Kern-Set** (`distance_km`, modusgerechte Carrier-Zuordnung + konsistente `carrier_id`, `transport_cost`/`currency`, Plan/Ist-konsistente Zeiten, `delay_reason`) , **Block 2** (realistische GPS-Interpolation Ghana→Rotterdam→Deutschland + modusabhängige Geschwindigkeit, deterministische UUIDs/Dateinamen via `det_uuid()`) , **Kunden-Segmente + Preis-nach-Kategorie** (`customer_type` DISCOUNTER/VOLLSORTIMENTER/PREMIUM mit gewichteter Bestellhäufigkeit, segment-abhängiger Menge & Kategorie; Preis je Kategorie) → Clustering + Umsatz-/Boxplot-Analysen, und **Kühlkette→Qualität** (Batch `quality_status` OK/REDUCED/REJECTED + `spoilage_pct` aus den Knoten-Temperaturen; View `dwh.v_batch_quality`). Getestet: voller `shared/`-Refresh + ETL + `verify_all_systems` 43 Checks/0 FAIL, DQ 6.4/7.1–7.7 PASS, DQ 4.10 → PASS; Segmente klar getrennt (Discounter Ø-Menge 843 vs. Premium 294); Kausalität Bruch→Qualität belegt (OK 0 Brüche, REDUCED Ø1,3, REJECTED Ø3,1). Weitere Generatoränderung geplant (#8 kontrollierte Inkonsistenzen) → finaler Doku-Zahlen-Refresh am Ende. | in Bearbeitung |
| `bananasupplychain/container/docker-compose.yml` | Docker-Setup: PostgreSQL, MongoDB, Redis, Neo4j, MinIO | getestet |

### Cypher (`cypher/`)

| Datei | Inhalt | Status |
|---|---|---|
| `cypher/01_create_graph_model.cypher` | Constraints + 4 Indizes; 8 Node-Typen, 13 Relationships; vollständige SUPPLIES-Kanten für alle 10 Produkte (aus ProductCreated-Events); Beispiel-Batch (BATCH-fc6d22f2-…) mit 7 PROCESSED_AT-Knoten (6-Hop-Pfad); 8 Beispielabfragen; Nachweis-Queries | abgabefähig |
| `cypher/02_verification_queries.cypher` | Aktive (nicht auskommentierte) Verifikationsqueries: Node/Rel-Counts je Typ, Constraints/Indizes prüfen, 6-Hop-Pfad, Fulfillment-Kette, Kühlketten-Monitoring, Integritätsprüfungen | erstellt |

### Generierte Daten (`shared/`)

| Ordner | Dateien | Status |
|---|---|---|
| `shared/erp/` | 534 JSON-Events (10 Supplier/Customer/Product + 252 Order + 252 Batch) | getestet |
| `shared/wms/` | 1.522 JSON-Events (10 SKU + 1.512 NodeProcessed) | getestet |
| `shared/tms/` | 6.300 JSON-Events (5 Carrier + 10 Ref + 1.512 Shipment + 3.009 GPS + 1.512 Completed + 252 Delivery) | getestet |

### Analytics (`analytics/`)

| Datei | Inhalt | Status |
|---|---|---|
| `analytics/dashboard.py` | 5 BI-Charts (Umsatz-Zeitreihe nach Kundensegment, Verspaetungsgruende, Bestellwert-Boxplot nach Kundentyp, Transportkosten je Route, Batchqualitaet ueber Zeit); Output: PDF + PNG + HTML | abgabefaehig |
| `analytics/clustering.py` | Kundensegmentierung k-Means mit fachlich gewähltem k=3; Elbow-/Silhouette-Diagnose; Business-Interpretation Ø Bestellwert vs. Ø Verzögerung; Output: PDF + PNG | abgabefaehig |
| `analytics/forecast.py` | Absatzprognose ARIMA(1,0,1); 13 echte Monate + 24 Monate synthetische History (transparent markiert); 3-Monats-Prognose, RMSE 3.626 / MAE 3.035; Output: PDF + PNG + TXT | abgabefaehig |
| `analytics/descriptive_stats.py` | Deskriptive Statistik (A-1): n/Min/Max/Mittelwert/Median/Std/Q1/Q3/IQR + IQR-Ausreißer fuer delay_minutes, avg_temperature, quantity, unit_price, total_value; Output: Konsole + `descriptive_stats.txt`; getestet gegen DWH (252 Zeilen) | abgabefaehig |
| `sql/10_kpi_queries.sql` | KPI-Definition (A-2): 5 Pflicht-KPIs + Ursachen-KPI aus DWH (Liefertreue 96,8 %, Ø Transportdauer 14,92 T, Temp-Ausreißer 7,9 %, Ø Bestellwert 1.289,72 €, Batchqualität 36,5 %); ausfuehrbar gegen laufende DB | abgabefaehig |
| `docs/14_analytics_kpis.md` | KPI-Katalog (Formel/Quelle/Zielwert/Ist) + deskriptive Statistik + fachliche Interpretation | abgabefaehig |
| `docs/15_powerbi_concept.md` | PowerBI-Konzept (A-4): Datenmodell, DAX-Measures, 4 Report-Seiten, Slicer, Umsetzungsleitfaden | abgabefaehig |

---

## 3. Technisch getestete Artefakte

Alle folgenden Komponenten wurden zuletzt am **2026-05-14** gegen laufende Docker-Container geprüft:

| Komponente | Ergebnis |
|---|---|
| PostgreSQL: SQL 01-08 | 6 Schemas, 26 Tabellen erstellt; alle neuen Constraints (UNIQUE, NOT NULL, event_timestamp) aktiv |
| MDM `resolve_canonical_key()` | BAN_101 / ban-101 / BAN-101 -> alle loesen auf BAN-101 auf |
| DWH `dim_date` | 1095 Zeilen (2025-01-01 bis 2027-12-31) |
| DWH `fact_fulfillment` | 10 Facts (1 pro Endlieferung, Grain-Fix 2026-05-15); dim_customer/supplier/carrier mit `source_created_at` befuellt |
| DQ-Checks `08` + `08b` | 41 Checks; 38/41 PASS; 3 bewusste FAILs: 4.3/4.4 (Kühlkette), 6.3 (SLA); 4.10 (GPS) + 6.4 (Carrier-Modus) behoben → PASS; dokumentiert in docs/13 §3.7 |
| WMS warehouse_skus | sku im WMS-Format (BAN_101), erp_product_code normalisiert (BAN-101) – Fix wirksam |
| erp.batches | kein order_id mehr; harvested_at korrekt aus event.timestamp befuellt |
| ETL Phase 1 | 395 Events -> PostgreSQL/MongoDB/Redis/Neo4j; 10 Suppliers/Customers/Products, 10 Orders/Batches, 60 NodeProcessings, 60 Shipments |
| ETL Phase 2 | 10 dim_customer, 10 dim_supplier, 10 dim_product, 5 dim_carrier, 10 fact_fulfillment (nach Grain-Fix) |
| MongoDB: 4 Collections | 1.512 shipment_events, 1.512 node_events, 252 batch_tracking, 252 order_events |
| Redis: alle Key-Typen | STRING, HASH, LIST, SORTED SET, COUNTER + TTLs auf allen Keys; load_redis() verarbeitet ERP+TMS; monitoring:temp_violations mit Datumskey + 7-Tage-TTL; active_shipments INCR/DECR; shipment:route Sorted Set; Produktcache; orders_today mit EXPIREAT |
| Neo4j: Graphmodell | 124 Nodes, alle Relationships; Pfad PLANTATION->RETAIL in 6 Hops |
| MinIO: 4 Buckets | 97 Dokumente: 60 Lieferscheine, 7 Rechnungen, 10 B/L, 10 Zollfreigaben, 10 Qualitätszertifikate |

---

## 4. Noch nicht getestete Artefakte

| Artefakt | Hinweis |
|---|---|
| Neo4j ETL aus TMS-Daten | Stammdaten + Shipments/Deliveries geladen; volle Fulfillment-Routen-Pfade nicht automatisch importiert |
| Generator-Änderungen (2026-06-30 bis 2026-07-02) | Kühlkette/Seed/Zeitstempel/Kategorien + **Transport-Kern-Set** + **Block 2 (GPS realistisch, UUID-Determinismus)** + **Kunden-Segmente & Preis-nach-Kategorie** + **Kühlkette→Qualität** umgesetzt und getestet: sauberer `shared/`-Refresh (252 Orders, 8.356 Events), voller ETL + generate_documents + `verify_all_systems` **43 Checks/0 FAIL**, DQ 38/41 (3 bewusste FAILs 4.3/4.4/6.3). **faithful DWH** via `order_reference` (252 Fact, 13 Monate, 325.009 EUR). Analytics auf neue Felder gehoben. **Fixes:** etl_dwh Dim-Refresh; clustering-Farbpalette und fachliche k=3-Wahl; verify Batch-Check dynamisch. **#8 übersprungen** (DQ-Abdeckung ausreichend). Exakte Zahlen in alle Fach-Docs eingetragen. |

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
| A-3 | 5 Python-Charts (Matplotlib/Seaborn/Plotly): Umsatz-Zeitreihe nach Kundensegment, Verspaetungsgruende, Bestellwert-Boxplot nach Kundentyp, Transportkosten je Route, Batchqualitaet ueber Zeit | **abgabefaehig** | `analytics/dashboard.py` → `dashboard.pdf`, `dashboard.png`, `dashboard.html` |
| A-5 | Clustering: Kundensegmentierung mit k-Means (Elbow-Methode, 4 Features, Silhouette-Score) | **abgabefaehig** | `analytics/clustering.py` → `clustering.pdf`, `clustering.png` |
| A-6 | Absatzprognose: ARIMA auf Bestellvolumen (RMSE/MAE im Chart; 13 echte Monate + 24 Monate synthetische Vorlauf-History transparent markiert) | **abgabefaehig** | `analytics/forecast.py` → `forecast.pdf`, `forecast.png`, `forecast_model_summary.txt` |
| A-1 | Deskriptive Statistik: n/Min/Max/Mittelwert/Median/Std/Q1/Q3/IQR + IQR-Ausreißer fuer delay_minutes, avg_temperature, quantity, unit_price, total_value | **abgabefaehig** | `analytics/descriptive_stats.py` → `descriptive_stats.txt`; `docs/14_analytics_kpis.md` §2 |
| A-2 | KPI-Definition: 5 Pflicht-KPIs + Ursachen-KPI mit Formel, Datenquelle, Zielwert, Ist-Wert (SQL aus DWH) | **abgabefaehig** | `sql/10_kpi_queries.sql` (getestet); `docs/14_analytics_kpis.md` §1 |
| A-4 | PowerBI-Dashboard: Konzept (Datenmodell, DAX-Measures, 4 Report-Seiten, Slicer, Umsetzungsleitfaden) | **abgabefaehig** | `docs/15_powerbi_concept.md` (.pbix optional, Windows-only) |
| A-7 | Abschlussbericht: Zusammenfassung aller Ergebnisse Teil 1 + Teil 2 (inkl. Kennzahlen-Überblick, bewusste Entscheidungen) | **abgabefaehig** | `docs/16_abschlussbericht.md` |

### Noch offen

_Alle Analytics-Aufgaben (A-1 bis A-7) abgeschlossen._

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
| F-13 | iCloud-Sync zerschoss `shared/`: TMS-Ordner dreifach (`tms` leer, `tms 2`, `tms 3` mit den echten Daten), zusätzlich ~3.300 Datei-Dubletten (`* N.json`) in erp/wms/tms. `etl_load.py` liest fest `shared/tms/*.json` → ein frischer ETL-Lauf hätte **0 TMS-Datensätze** geladen (leere Faktentabelle, Analytics kaputt). Aktuell geladene DB war unberührt. | `shared/` (Disk-Zustand, kein Code-Bug) | **behoben 2026-07-02** (Dubletten-Sicherheit geprüft: jede Kopie hatte ein Original; `tms 2`+leeres `tms` entfernt, `tms 3`→`tms` umbenannt, alle `* N.json` gelöscht → 534/1.522/6.300 = 8.356; materialisiert + lesbar verifiziert; ETL-Glob findet 6.300 TMS). **Restrisiko:** `shared/` liegt weiter auf iCloud-Desktop → Wiederauftreten möglich; dauerhafte Lösung = Projekt aus iCloud herausnehmen (Risiko R-8). |

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
| R-8 | Risiko | `shared/` liegt auf dem **iCloud-Desktop** → iCloud dupliziert Dateien (`* N.json`) und ganze Ordner (`tms 2`, `tms 3`) und lagert Inhalte aus (`open()` kann blockieren). Führte zu F-13 (behoben 2026-07-02). **Wiederauftreten möglich.** Dauerhafte Lösung: Projekt aus dem iCloud-Desktop herausnehmen; kurzfristig nach jeder `shared/`-Neugenerierung sofort den ETL laufen lassen und vor jedem Frischlauf `find shared -name '* [0-9].json' -delete` prüfen. |

---

## 9. Naechste konkrete Schritte

Priorisiert fuer den naechsten Arbeitssprint:

1. **Deskriptive Statistik** – Python-Skript mit `pandas` auf DWH-Daten; Min/Max/Mittelwert/Median/Std fuer delay_minutes, avg_temperature, quantity, unit_price (A-1)
2. **KPIs definieren und berechnen** – mindestens 5 KPIs mit Formel, Datenquelle, Zielwert; SQL aus DWH-Schema (A-2)
3. **PowerBI-Dashboard** – Konzept + Umsetzung mit DWH-Schema als Datenquelle (A-4)
4. **Abschlussbericht** – nach Fertigstellung aller Aufgaben (A-7)

---

*Statuslegende: **erstellt** = vorhanden, nicht ausgefuehrt | **getestet** = technisch geprueft | **abgabefaehig** = fachlich + technisch vollstaendig | **offen** = noch nicht erledigt | **Risiko** = moegliches Problem*
