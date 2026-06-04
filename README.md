# Banana Supply Chain Datenplattform

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26 – TH Lübeck  
**Gruppe:** 7  
**Deadline:** 01.07.2026

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

Python-Pakete installieren:

```bash
pip install psycopg2-binary pymongo redis neo4j minio reportlab pandas matplotlib scikit-learn statsmodels
```

---

## Startsequenz

> **Wichtig:** Den Datengenerator und alle ETL-Skripte immer aus dem **Repo-Root** starten, nie aus dem Unterordner `bananasupplychain/`.

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
> **Wichtig:** Den Generator **nur einmal** ausführen. Mehrfache Ausführung erzeugt neue UUIDs und verdoppelt die Datensätze beim nächsten ETL-Lauf (statt 10 → 20 fact_fulfillment-Zeilen). Falls `shared/` bereits befüllt ist, erst löschen: `rm -rf shared/erp shared/wms shared/tms`

```bash
python3 bananasupplychain/test_data_generator.py
```

Erwartete Ausgabe: 50 ERP- / 70 WMS- / 265 TMS-JSON-Dateien in `shared/`.

### Schritt 4: ETL Phase 1 (ERP/WMS/TMS → alle Datenbanken)

```bash
python3 bananasupplychain/etl_load.py
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
```

> Output-Dateien (`dashboard.pdf`, `clustering.pdf`, `forecast.pdf` etc.) werden in `analytics/` gespeichert.

---

## Erwartete Ergebnisse nach vollständigem Durchlauf

| System     | Ergebnis                                                          |
|------------|-------------------------------------------------------------------|
| PostgreSQL | 10 Supplier, Customers, Products, Orders, Batches                 |
|            | 60 Shipments, 112 GPS-Positionen, 10 Deliveries                   |
|            | DWH: 10 fact_fulfillment-Zeilen, 1095 dim_date-Zeilen             |
| MongoDB    | 60 shipment_events, 60 node_events, 10 batch_tracking, 10 order_events |
| Redis      | STRING / HASH / LIST / ZSET / COUNTER + TTLs auf allen Keys       |
| Neo4j      | 125+ Nodes; Pfad PLANTATION → RETAIL in 6 Hops                   |
| MinIO      | 98 PDFs: 60 Lieferscheine, 8 Rechnungen, 10 Bill of Lading,       |
|            | 10 Zollfreigaben, 10 Qualitätszertifikate                         |

---

## Projektstruktur

```
shared/                    # ERP/WMS/TMS JSON-Quelldaten (50 + 70 + 265 Dateien)
sql/                       # PostgreSQL DDL (01–09)
bananasupplychain/         # ETL-Skripte + Docker-Compose
analytics/                 # Python Charts, Clustering, Absatzprognose
docs/                      # Vollständige Dokumentation (00–13)
cypher/                    # Neo4j Graphmodell + Verifikationsqueries
```

---

## Dokumentation

| Dokument | Inhalt |
|---|---|
| `docs/00_part1_checklist.md` | Anforderungsabgleich Teil 1 (Checkliste) |
| `docs/02_target_architecture.md` | Systemarchitektur mit Mermaid-Diagramm |
| `docs/07_dwh_model.md` | DWH-Sternschema, ETL-Übergänge, analytische Views |
| `docs/12_etl_concept.md` | ETL-Konzept mit vollständiger Mapping-Tabelle (13 Eventtypen) |
| `docs/13_data_quality_results.md` | DQ-Audit: 34 Checks, 31/34 PASS (91 %) |
| `PROJECT_STATUS.md` | Aktueller Projektstatus, offene Punkte, bekannte Fehler |
