# Banana Supply Chain Datenplattform

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26 – TH Lübeck  
**Gruppe:** 7  
**Deadline:** 06.07.2026

---

## Projektbeschreibung

Dieses Projekt implementiert eine vollständige Datenplattform für eine Banana Supply Chain im Rahmen des Moduls Datenmanagement und Analytics (M.Sc., SoSe 26, TH Lübeck). Die Plattform integriert drei Quellsysteme (ERP, WMS, TMS), die Ereignisse als JSON-Dateien liefern, und verteilt diese über einen ETL-Prozess auf fünf Zielsysteme: PostgreSQL, MongoDB, Redis, Neo4j und MinIO. Das Projekt gliedert sich in Teil 1 (Datenmanagement: Modellierung, ETL, MDM, Datenqualität, Data Warehouse) und Teil 2 (Analytics: KPIs, deskriptive Statistik, Python-Charts, PowerBI, Clustering, Absatzprognose).

---

## Technologie-Stack

- **PostgreSQL 15** – relationale Stamm- und Bewegungsdaten (ERP/WMS/TMS), MDM, Metadaten, DWH-Sternschema
- **MongoDB 7** – Event-Dokumente (shipment_events, node_events, batch_tracking, order_events)
- **Redis 7** – Echtzeit-Tracking (STRING, HASH, LIST, SORTED SET, COUNTER mit TTLs)
- **Neo4j 5** – Supply-Chain-Graphmodell (8 Node-Typen, 13 Relationship-Typen)
- **MinIO** – Objektspeicher für Logistikdokumente (Lieferscheine, Rechnungen, B/L, Zertifikate)
- **Docker** – Containerisierung aller fünf Datenbanksysteme
- **Python 3** – Datengenerator, ETL-Skripte, Analytics

---

## Voraussetzungen

**Docker Desktop** muss installiert und gestartet sein.

Python-Pakete installieren (empfohlen, feste Versionen aus der getesteten Umgebung):

```bash
pip install -r requirements.txt
```

Alternativ direkt (gleiche Pakete, ohne Versionsbindung):

```bash
pip install psycopg2-binary pymongo redis neo4j minio reportlab pandas numpy matplotlib seaborn plotly scikit-learn statsmodels
```

---

## Startsequenz

> **Wichtig:** Den Datengenerator und alle ETL-Skripte immer aus dem **Repo-Root** starten, nie aus dem Unterordner `bananasupplychain/`.

> **⚠️ Immer nur EINEN Docker-Stack starten.** Neben dem produktiven Stack `bananasupplychain/container/` liegt die unveränderte Dozenten-Vorlage `databasemodels_logistics_playground/container/`. Beide haben **dieselben** `container_name` (postgres, mongodb, redis, neo4j, minio, cleanup) und Ports (5432/27017/6379/7474/7687/9000/9001) und – weil beide im Ordner `container/` liegen – **denselben** Compose-Projektnamen `container` und damit **dieselben** Volumes (`container_postgres_data` …). Für dieses Projekt daher ausschließlich `bananasupplychain/container` hochfahren; die Vorlage nie parallel oder nacheinander gegen dieselbe `logistics`-DB starten (ihr `initialize_db.py` schriebe sein generisches Demo-Schema Orders/OrderDetails/Warehouses in dieselben Volumes).

### Schritt 1: Infrastruktur starten

```bash
cd bananasupplychain/container && docker compose up -d && cd ../..
```

### Schritt 2: PostgreSQL-Schemas anlegen

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

### Schritt 3: Testdaten generieren (immer aus Repo-Root!)

> **Hinweis:** Der Ordner `shared/` ist bewusst nicht im Repository enthalten – er enthält generierte JSON-Ereignisdaten und gehört nicht ins Versionskontrollsystem. Er wird durch diesen Schritt erzeugt.
>
> **Wichtig:** Den Generator **nur einmal** ausführen. Mehrfache Ausführung erzeugt neue UUIDs und verdoppelt die Datensätze beim nächsten ETL-Lauf. Falls `shared/` bereits befüllt ist, erst löschen: `rm -rf shared/erp shared/wms shared/tms`
>
> **Generator anpassbar:** `test_data_generator.py` darf geändert werden. Jede Änderung muss in `PROJECT_STATUS.md`, dieser README und `PROJEKTANLEITUNG.md` dokumentiert werden; danach `shared/` neu generieren und den vollständigen ETL-Lauf wiederholen (`shared/` ist der Ursprung aller fünf Zielsysteme).
>
> **Aktuelle Generator-Anpassungen (Transport-Kern-Set, [ANPASSUNG 2026-07-01]):** Distanz je Route (`distance_km`), modusgerechte Carrier-Zuordnung mit konsistenter `carrier_id` (Land→TRUCK, See→SEA_FREIGHT), Transportkosten je Leg (`transport_cost`/`currency`), Plan/Ist-konsistente Zeiten (`estimated_arrival` = Plan, Ist-Ankunft = Plan + carrier-spezifisches `delay_minutes`) und Verspätungsgrund (`delay_reason`). Diese Felder fließen über `etl_load.py` in `tms.shipments`/`tms.transport_completions` und über `etl_dwh.py` als Measures/Slicer in `dwh.fact_fulfillment` (für Power BI).
>
> **Realistische GPS-Positionen + deterministische IDs (Block 2, [ANPASSUNG 2026-07-01]):** GPS-Punkte werden zwischen den Knoten interpoliert (Ghana → Rotterdam → Deutschland → plausible Power-BI-Geokarte statt Zufallspunkten weltweit), Geschwindigkeit modusabhängig (LKW 45–90, See 25–40 km/h). UUIDs/Dateinamen stammen aus einem geseedeten RNG (`det_uuid()`) → Läufe **exakt reproduzierbar**, IDs überschreiben sich beim Re-Generieren statt zu akkumulieren. Getestet: `verify_all_systems` 43 Checks/0 FAIL, DQ-Check 6.4 + 7.1–7.4 PASS, DQ 4.10 (GPS-Routenkorridore) durch die Interpolation → PASS.
>
> **Kunden-Segmente + Preis-nach-Kategorie ([ANPASSUNG 2026-07-01]):** Jeder Retailer hat ein festes Segment `customer_type` (DISCOUNTER: ALDI/LIDL/KAUFLAND · VOLLSORTIMENTER: REWE/EDEKA/TESCO/SPAR · PREMIUM: METRO/CARREFOUR/AUCHAN) mit eigenem Verhaltensprofil: gewichtete Bestellhäufigkeit, segment-abhängige Menge und bevorzugte Produktkategorie. Der `unit_price` hängt an der Produktkategorie (Standard < Sustainable < Specialty < Premium, alle in [1,50; 5,00] €). `customer_type` fließt bis `dwh.dim_customer` → **Clustering** (Teil 2) findet echte Segmente, **Umsatz-/Boxplot-Analysen** werden aussagekräftig. **Fix:** `etl_dwh` leert die Dimensionen jetzt vor dem Laden (sonst blieben Dim-Werte via `ON CONFLICT DO NOTHING` veraltet). Getestet: `verify_all_systems` 43 Checks/0 FAIL, DQ 7.5 (Segment gültig) PASS; im DWH klar getrennte Segmente (Discounter Ø-Menge 843 vs. Premium 294).
>
> **Kühlkette → Qualität ([ANPASSUNG 2026-07-02]):** Aus den Knoten-Temperaturen eines Batches wird ein `quality_status` (OK = keine Brüche · REDUCED = 1–2 Brüche · REJECTED = ≥3 Brüche) und ein `spoilage_pct` (Schwund) abgeleitet → die vorhandenen Kühlkettenbrüche werden zur **belegbaren Ursache** von Qualitätsverlust. Felder liegen in `erp.batches`; die View `dwh.v_batch_quality` liefert Qualitätsrate + Ø-Schwund je Woche (KPI Batchqualitätsrate, Chart „Batchqualität über Zeit"). Getestet: Kausalität belegt (OK Ø0 Brüche, REDUCED Ø1,3, REJECTED Ø3,1), DQ 7.6/7.7 PASS.
>
> **Profitabilität: allokierte Transportkosten + COGS ([ANPASSUNG 2026-07-05]):** Zwei Generator-Änderungen machen Margen-Analysen möglich. **(1) Transportkosten kapazitätsallokiert:** Vorher trug jede Bestellung die Vollkosten aller 6 Legs (Transportkostenquote 137 % vom Umsatz – wirtschaftlich unbrauchbar). Neu belegt eine Bestellung nur ihren Mengenanteil der Transporteinheit ([ANNAHME] LKW-Sammeltour 2.000 / Sammelverschiffung 13.800 Kartons) plus 0,02 €/Karton Handling je Leg → Quote jetzt **24,9 %** (Zielkorridor 15–30 %). **(2) `unit_cost` (simulierter Wareneinsatz)** je Produkt = 50–65 % der Preisband-Untergrenze der Kategorie → strukturell `unit_cost < unit_price`. **Beide Änderungen sind seed-neutral** (Allokation deterministisch, `unit_cost` aus separatem RNG): alle bisherigen Kennzahlen (Umsatz 325.008,80 €, Liefertreue 96,8 % …) bleiben exakt unverändert. Daraus im DWH: `cogs_total`, `gross_profit` (Bruttomarge **53,2 %**), `storage_days`/`storage_cost` (Verweildauer aus WMS-/TMS-Zeitstempeln × Knotensatz, **1,0 %**) und `contribution_margin` = **vereinfachter logistischer Deckungsbeitrag 88.630,56 € (27,3 %)** – bewusst kein Unternehmensgewinn. Dazu ein einfaches Inventory-Modell: `wms.stock_movements` (3.024 Bewegungen, im ETL deterministisch aus NodeProcessed abgeleitet – kein neuer Eventtyp), View `dwh.v_stock_by_node`; Verifikation in `sql/09` §7 (8 Checks PASS). Der Profitabilitäts-Wasserfall ist **Chart 5 des BI-Dashboards** (`analytics/dashboard.py`).

```bash
python3 bananasupplychain/test_data_generator.py
```

Erwartete Ausgabe beim aktuellen Generatorstand: 534 ERP- / 1.522 WMS- / 6.300 TMS-JSON-Dateien in `shared/`.

### Schritt 4: ETL Phase 1 (ERP/WMS/TMS → alle Datenbanken)

```bash
python3 bananasupplychain/etl_load.py
```

### Schritt 4b: Neo4j-Graphmodell + Demo-Fulfillment laden

> Lädt Constraints, Stammdaten-Topologie und den vollständigen Demo-Vorgang (ORD-DEMO-001 / Demo-Batch über alle 7 Stationen). Ohne diesen Schritt scheitern zwei Neo4j-Checks in Schritt 7.

```bash
docker exec -i neo4j cypher-shell -u neo4j -p password < cypher/01_create_graph_model.cypher
```

### Schritt 5: Logistikdokumente → MinIO

```bash
python3 bananasupplychain/generate_documents.py
```

### Schritt 6: ETL Phase 2 (operative Schemas → DWH)

```bash
python3 bananasupplychain/etl_dwh.py
```

### Schritt 7: Verifikation aller Systeme

```bash
docker exec -i postgres psql -U user -d logistics < sql/09_verification_queries.sql
docker exec -i postgres psql -U user -d logistics < sql/08_data_quality_checks.sql
python3 bananasupplychain/verify_all_systems.py
```

### Schritt 8: Analytics ausführen

```bash
python3 analytics/dashboard.py
python3 analytics/clustering.py
python3 analytics/forecast.py
python3 analytics/descriptive_stats.py
docker exec -i postgres psql -U user -d logistics < sql/10_kpi_queries.sql
```

> Output-Dateien (`dashboard.pdf`, `clustering.pdf`, `forecast.pdf` etc.) werden in `analytics/` gespeichert.

---

## Erwartete Ergebnisse nach vollständigem Durchlauf

| System     | Ergebnis                                                          |
|------------|-------------------------------------------------------------------|
| PostgreSQL | je 10 Supplier / Customers / Products, 252 Orders / Order-Items / Batches |
|            | 5 Carrier, 1.512 Shipments, 3.009 GPS-Positionen, 1.512 Completions, 252 Deliveries |
|            | DWH: 252 fact_fulfillment-Zeilen, 1.095 dim_date-Zeilen           |
|            | wms.stock_movements: 3.024 Bestandsbewegungen (1.512 IN / 1.512 OUT) |
|            | Profitabilität: Bruttomarge 53,2 %, Transportkostenquote 24,9 %, log. DB 27,3 % |
| MongoDB    | 1.512 shipment_events, 1.512 node_events, 252 batch_tracking, 252 order_events |
| Redis      | STRING / HASH / LIST / ZSET / COUNTER + TTLs auf allen Keys       |
| Neo4j      | 2.061 Nodes (2.058 aus ETL + 3 Demo-Objekte aus cypher/01); Pfad PLANTATION → RETAIL in 6 Hops |
| MinIO      | 2.520 PDFs: 1.512 Lieferscheine, 252 Rechnungen, 252 Bill of Lading, |
|            | 252 Zollfreigaben, 252 Qualitätszertifikate                       |

---

## Projektstruktur

```
shared/                    # ERP/WMS/TMS JSON-Quelldaten (534 + 1.522 + 6.300 Dateien)
sql/                       # PostgreSQL DDL (01–10, inkl. 06b/08b)
bananasupplychain/         # ETL-Skripte + Docker-Compose
analytics/                 # Python Charts, Clustering, Absatzprognose
docs/                      # Vollständige Dokumentation (00–16)
cypher/                    # Neo4j Graphmodell + Verifikationsqueries
databasemodels_logistics_playground/   # Dozenten-Vorlage aus Moodle – NICHT starten (Stack-Kollision, s. Startsequenz)
```

---

## Dokumentation

| Dokument | Inhalt |
|---|---|
| `docs/00_part1_checklist.md` | Anforderungsabgleich Teil 1 (Checkliste) |
| `docs/02_target_architecture.md` | Systemarchitektur mit Mermaid-Diagramm |
| `docs/07_dwh_model.md` | DWH-Sternschema, ETL-Übergänge, analytische Views |
| `docs/12_etl_concept.md` | ETL-Konzept mit vollständiger Mapping-Tabelle (13 Eventtypen) |
| `docs/13_data_quality_results.md` | DQ-Audit: 41 Checks, 38/41 PASS (93 %) |
| `docs/14_analytics_kpis.md` | Teil 2: KPI-Katalog (5+ KPIs) + deskriptive Statistik + Interpretation |
| `docs/15_powerbi_concept.md` | Teil 2: PowerBI-Konzept (Datenmodell, DAX-Measures, Report-Seiten, Slicer) |
| `docs/16_abschlussbericht.md` | Abschlussbericht: Zusammenfassung Teil 1 + Teil 2 mit Kennzahlen-Überblick |
| `PROJECT_STATUS.md` | Aktueller Projektstatus, offene Punkte, bekannte Fehler |
