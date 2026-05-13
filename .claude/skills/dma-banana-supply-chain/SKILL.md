---
name: dma-banana-supply-chain
description: >
  Aktiviere diesen Skill bei allen Aufgaben im Projekt „Banana Supply Chain Datenplattform"
  des Moduls „Datenmanagement und Analytics" (M.Sc., SoSe 26, TH Lübeck).
  Deckt Teil 1 (Datenmanagement: PostgreSQL, MongoDB, Redis, Neo4j, MinIO, ETL, MDM, DQ, DWH)
  und Teil 2 (Analytics: KPIs, deskriptive Statistik, Python-Charts, PowerBI, Clustering,
  Absatzprognose) ab. Greift bei Schlüsselwörtern wie „Banana", „Supply Chain",
  „DMA", „ETL", „ERP", „WMS", „TMS", „Teil 1", „Analytics" oder Verweisen auf
  Projektdateien wie Aufgabenstellung.pdf, etl_load.py oder die docs/-Ordner.
---

# Skill: DMA Banana Supply Chain

## Zweck

Dieser Skill leitet Claude Code an, prüfungsorientiert, fachlich sauber und
projektbezogen im DMA-Projekt zu arbeiten. Ziel ist eine Hochschulabgabe auf
Niveau „gut bis sehr gut".

---

## 1. Projektgrundsätze

- **`Aufgabenstellung.pdf` ist maßgeblich.** Vor jeder Aufgabe: Anforderungen
  aus der PDF ableiten, nicht aus Annahmen erfinden.
- **Projektordner zuerst prüfen.** Bevor etwas neu erstellt wird, immer prüfen,
  ob bereits eine Datei existiert (`docs/`, `sql/`, `cypher/`, `bananasupplychain/`).
- **Klare Trennung**: Aufgabenstellung ≠ vorhandene Codebasis ≠ generierte Daten
  ≠ noch fehlende Bestandteile. Immer explizit benennen, was in welche Kategorie fällt.
- **Keine generischen KI-Texte.** Jede Aussage muss sich auf konkrete
  Projektdaten, Eventtypen oder Datenbankschemas beziehen.
- **Annahmen klar markieren** mit dem Präfix: `[ANNAHME]`

---

## 2. Kontextübersicht

| Dimension        | Wert |
|------------------|------|
| Modul            | Datenmanagement und Analytics (M.Sc.), SoSe 26 |
| Hochschule       | TH Lübeck |
| Deadline         | 01.07.2026 |
| Use Case         | Banana Supply Chain |
| Quellsysteme     | ERP (`shared/erp/`), WMS (`shared/wms/`), TMS (`shared/tms/`) |
| Infrastruktur    | PostgreSQL, MongoDB, Redis, Neo4j, MinIO, Docker |
| Teil 1           | Datenmanagement |
| Teil 2           | Analytics |

**Eventmengen (aktuell generiert):**
- ERP: 50 JSON-Dateien (Supplier, Customer, Product, Order, Batch)
- WMS: 70 JSON-Dateien (WarehouseSKU, NodeProcessed)
- TMS: 263 JSON-Dateien (Carrier, TransportRef, Shipment, Position, Delivery)

---

## 3. Arbeitsregeln – Teil 1: Datenmanagement

Wenn der Nutzer „Teil 1" sagt: **ausschließlich Datenmanagement**, kein Analytics.

### 3.1 Datenklassifikation
- Jeden Eventtyp klassifizieren: Stammdaten / Bewegungsdaten / Ereignisdaten
- Für jeden Eventtyp: Primär-Zielsystem und Begründung angeben
- Vorlage: `docs/01_data_classification.md`
- Alle 13 Eventtypen müssen abgedeckt sein

### 3.2 ERP / WMS / TMS – Datenmodelle
- ERP: suppliers, customers, products, orders, order_items, batches
- WMS: warehouse_skus, supply_chain_nodes, node_processings
- TMS: carriers, transport_product_refs, shipments, positions, completions, deliveries
- Schemas: `sql/02_create_erp_tables.sql`, `sql/03_create_wms_tables.sql`, `sql/04_create_tms_tables.sql`
- Fremdschlüssel müssen korrekte ON DELETE-Verhalten haben
- Constraints (NOT NULL, UNIQUE, CHECK) wo fachlich sinnvoll

### 3.3 ER-Modell
- Mermaid-Syntax verwenden (für `docs/03_er_model.md`)
- PKs, FKs und Kardinalitäten (1:1, 1:N, M:N) explizit darstellen
- Begründung der Beziehungen aus dem Supply-Chain-Kontext herleiten
- Beispiel: Eine `Order` hat genau einen `Customer`, aber mehrere `OrderItems`

### 3.4 Masterdatenmanagement (MDM)
- Bekannte Inkonsistenz: `BAN-101` (ERP) = `BAN_101` (WMS) = `ban-101` (TMS)
- Schema: `sql/05_create_mdm_tables.sql` (entity_types, golden_records, source_mappings)
- Funktion `mdm.resolve_canonical_key()` muss alle drei Formate auflösen
- Test: `SELECT mdm.resolve_canonical_key('BAN_101', 'WMS');` → muss `BAN-101` zurückgeben

### 3.5 Metadatenmanagement
- Schema: `sql/06_create_metadata_tables.sql` (systems, tables, columns)
- Für alle relevanten Spalten: Skalenniveau bestimmen (NOMINAL / ORDINAL / INTERVAL / RATIO)
- Pflicht: temperature → INTERVAL, delay_minutes → RATIO, delivery_priority → ORDINAL
- Qualitätsregeln in `meta.columns.quality_rule` eintragen

### 3.6 Datenqualitätsmanagement
- 6 Dimensionen: Vollständigkeit, Eindeutigkeit, Konsistenz, Plausibilität, Aktualität, Referenzielle Integrität
- Je Dimension: mindestens 2 konkrete Regeln mit Supply-Chain-Bezug
- SQL-Checks in `sql/08_data_quality_checks.sql` müssen ausführbar sein
- Beispiel: Temperatur außerhalb 10–15 °C = Kühlkettenbruch (Plausibilität)

### 3.7 Data Warehouse (DWH)
- Sternschema: 1 Faktentabelle + mindestens 7 Dimensionen
- Schema: `sql/07_create_dwh_schema.sql`
- Measures: quantity, unit_price, total_value, delay_minutes, avg_temperature, num_hops
- ETL Phase 2: operative Schemas → DWH klar beschreiben (nicht mit operativen Schemas vermischen)
- dim_date muss als Date Spine vorliegen (2025–2027 = 1095 Zeilen)

### 3.8 MongoDB – Eventmodell
- 4 Collections: shipment_events, node_events, batch_tracking, order_events
- Eingebettete Dokumente bevorzugen (Shipment-Lifecycle als 1 Dokument)
- TTL-Index auf GPS-Events definieren
- Begründung: Warum MongoDB statt PostgreSQL für Eventdaten?

### 3.9 Redis – Echtzeitmodell
- Key-Taxonomie vollständig: STRING, HASH, LIST, SORTED SET, COUNTER
- TTL für alle Keys definieren
- Konfiguration beachten: `maxmemory 256mb`, `allkeys-lru`, `appendonly no`
- Anwendungsfälle: Shipment-Tracking, GPS-Updates, Kühlketten-Alerts

### 3.10 Neo4j – Graphmodell
- 8 Node-Typen: Supplier, Customer, Product, Batch, Carrier, Shipment, Order, SupplyChainNode
- 12 Relationship-Typen dokumentieren
- Cypher-Skript: `cypher/01_create_graph_model.cypher`
- Pflicht: Beispielabfrage Supply-Chain-Pfad PLANTATION → RETAIL (6 Hops)
- Begründung: Warum Graph statt SQL für Pfad-Abfragen?

### 3.11 MinIO – Dokumentmodell
- 4 Buckets: invoices, delivery-notes, transport-docs, batch-certificates
- PostgreSQL speichert nur Referenz (Bucket + Objektpfad), nicht das Dokument selbst
- Begründung: Warum Object Store statt BLOB in Datenbank?
- Bucket Versioning und Object-Tags beschreiben

### 3.12 ETL – Konzept und Implementierung
- Strikte Phasentrennung: Extract → Transform → Load
- Extract: JSON-Datei lesen, Struktur validieren
- Transform: MDM-Auflösung, Typkonvertierung, Qualitätsprüfung
- Load: Zieldatenbank befüllen (idempotent, ON CONFLICT DO NOTHING)
- Mapping-Tabelle: alle 13 Eventtypen mit Quell-Feld → Transformation → Ziel-Spalte
- Implementierung: `bananasupplychain/etl_load.py`

### 3.13 Technische Nachweise und Prüfqueries
Am Ende jedes SQL-Blocks immer eine Prüfquery ergänzen:
```sql
-- Nachweis: Anzahl geladener Datensätze
SELECT COUNT(*) FROM erp.suppliers;
SELECT COUNT(*) FROM erp.orders;
```
Bei ETL-Skripten: Logging-Ausgabe mit Anzahl verarbeiteter Records je System.

---

## 4. Arbeitsregeln – Teil 2: Analytics

Wenn der Nutzer „Analytics" sagt: **ausschließlich Teil 2**, kein Datenmanagement.

### 4.1 KPIs
- Mindestens 5 Business-KPIs definieren
- Je KPI: Name, Formel, Datenquelle (Tabelle/Spalte), Zielwert/Benchmark
- Pflicht-KPIs: Liefertreue (%), Ø Transportdauer (Tage), Temperaturausreißer-Quote (%), Ø Bestellwert (€), Batchqualitätsrate (%)
- SQL-Abfragen aus dem DWH-Schema ableiten

### 4.2 Deskriptive Statistik
- Minimum, Maximum, Mittelwert, Median, Standardabweichung, Quartile
- Pflichtfelder: delay_minutes, avg_temperature, quantity, unit_price
- Python: `pandas.describe()` als Ausgangspunkt, dann vertiefen
- Ausreißer identifizieren (IQR-Methode)

### 4.3 Python-Charts (5 Stück)
Jeder Chart muss wirtschaftlich getrieben sein – kein Chart ohne Aussage:
1. **Lieferverzögerungen** – Histogramm `delay_minutes` nach Carrier
2. **Temperaturverlauf** – Zeitreihe `avg_temperature` je Route
3. **Bestellwert-Verteilung** – Boxplot `total_value` nach Kundentyp
4. **Transportrouten-Heatmap** – Häufigkeit der Routen (Herkunft → Ziel)
5. **Batchqualität über Zeit** – Liniendiagramm Ausreißerquote pro Woche

Bibliotheken: `matplotlib`, `seaborn`, `pandas`. Jeder Chart: Titel, Achsenbeschriftung, fachliche Interpretation als Kommentar.

### 4.4 PowerBI
- Konzept beschreiben: welche Measures, welche Visuals, welcher Filter
- Datenquelle: PostgreSQL DWH-Schema via DirectQuery oder Import
- Pflicht-Visuals: KPI-Cards, Zeitreihen-Liniendiagramm, Geokarte (wenn Koordinaten vorhanden), Slicer auf Datum/Carrier/Route

### 4.5 Clustering
- Ziel: Kundensegmentierung oder Lieferanten-Cluster
- Algorithmus: k-Means, Optimalanzahl mit Elbow-Methode bestimmen
- Features: Bestellhäufigkeit, Ø Bestellwert, Ø Verzögerung
- Ergebnis: Cluster-Label + fachliche Interpretation je Segment

### 4.6 Absatzprognose
- Zeitreihe: Bestellvolumen pro Woche/Monat aus `fact_fulfillment`
- Methode: ARIMA oder Facebook Prophet
- Ausgabe: Prognose für 4–8 Wochen + Konfidenzintervall
- Bewertung: RMSE oder MAE angeben

---

## 5. Code-Regeln

- **Bestehende Dateien nicht ohne Rückfrage überschreiben.** Immer fragen, bevor eine existierende Datei ersetzt wird.
- **SQL muss ausführbar und konsistent sein.** Tabellennamen, Schemas und Spalten müssen mit den tatsächlich vorhandenen DDL-Dateien übereinstimmen.
- **Python-Code kommentieren.** Jede Funktion bekommt einen einzeiligen Kommentar, der erklärt *warum* – nicht was – sie tut.
- **ETL-Phasen klar trennen.** Keine gemischten Extract/Load-Blöcke. Jede Phase als eigene Funktion oder Sektion.
- **Idempotenz:** ETL-Skripte müssen mehrfach ausführbar sein (ON CONFLICT DO NOTHING oder Existenz-Check).
- **Am Ende jedes Code-Blocks:** Prüfquery oder Testanweisung ergänzen.

---

## 6. Dokumentationsregeln

- **Sprache:** Deutsch, klar und präzise – kein akademisches Geschwurbel.
- **Konkrete Beispiele:** Immer aus der Banana Supply Chain – z.B. nicht „ein Produkt", sondern „das Produkt BAN-101 (Cavendish Bananen)".
- **Keine generischen KI-Floskeln** wie „natürlich", „selbstverständlich", „im Allgemeinen" oder „es ist wichtig zu beachten".
- **Fachliche Begründung:** Jede Datenbankwahl oder Modellentscheidung mit konkretem Argument belegen (z.B. „MongoDB, weil Shipment-Events heterogene Felder haben und kein NULL-Overhead entstehen soll").
- **Annahmen:** Mit `[ANNAHME]` kennzeichnen, damit der Nutzer weiß, was er prüfen muss.
- **Mermaid-Diagramme** für ER-Modelle und Architekturübersichten bevorzugen.

---

## 7. Qualitätscheckliste

Vor jeder Ausgabe selbst prüfen:

- [ ] Passt die Lösung zur `Aufgabenstellung.pdf`?
- [ ] Wurden echte Projektdateien (docs/, sql/, shared/) berücksichtigt?
- [ ] Sind ERP, WMS und TMS sauber voneinander getrennt?
- [ ] Sind PK, FK und Kardinalitäten fachlich logisch und vollständig?
- [ ] Ist SQL ausführbar (Schema-/Tabellenname korrekt)?
- [ ] Gibt es Nachweise, Prüfqueries oder Testanweisungen?
- [ ] Kann ich das Ergebnis fachlich erklären (ohne KI-Hilfe)?
- [ ] Sind Annahmen markiert?
- [ ] Ist die Sprache Deutsch und konkret?

---

## 8. Projektstatus-Pflege

Im Projektroot liegt die Datei `PROJECT_STATUS.md`. Sie ist das zentrale
Arbeitsgedächtnis des Projekts und muss immer aktuell gehalten werden.

### 8.1 Initiale Befüllung

Wenn `PROJECT_STATUS.md` leer ist oder nicht existiert, muss sie beim nächsten
projektbezogenen Auftrag automatisch befüllt werden. Die initiale Struktur enthält:

1. **Aktueller Gesamtstatus** – ein Satz zum Stand von Teil 1 und Teil 2
2. **Fertige Artefakte Teil 1** – alle vorhandenen Dateien mit Status
3. **Technisch getestete Artefakte** – was gegen laufende Docker-Container geprüft wurde
4. **Noch nicht getestete Artefakte** – was erstellt, aber nicht ausgeführt wurde
5. **Offene Aufgaben Teil 1** – was laut Aufgabenstellung noch fehlt
6. **Offene Aufgaben Analytics** – alle Teil-2-Aufgaben
7. **Bekannte Fehler** – reproduzierbare Probleme mit Beschreibung
8. **Risiken und Annahmen** – was schiefgehen könnte, was noch ungeprüft ist
9. **Nächste konkrete Schritte** – priorisierte To-do-Liste

### 8.2 Statusbegriffe

In `PROJECT_STATUS.md` immer einen dieser vier Begriffe verwenden – keinen anderen:

| Begriff | Bedeutung |
|---|---|
| **erstellt** | Datei oder Konzept existiert, wurde aber noch nicht ausgeführt |
| **getestet** | Wurde technisch ausgeführt oder gegen Docker-Container geprüft |
| **abgabefähig** | Fachlich geprüft, technisch plausibel und vollständig dokumentiert |
| **offen** | Noch nicht erledigt |
| **Risiko** | Könnte später Probleme verursachen – muss beobachtet werden |

### 8.3 Wann muss `PROJECT_STATUS.md` aktualisiert werden?

Bei jeder der folgenden Änderungen sofort aktualisieren:

- Neu erstellte Dateien (SQL, Python, Cypher, Markdown)
- Geänderte Dateien (auch kleine Korrekturen)
- Erfolgreich getestete SQL-/Python-/Docker-Komponenten
- Gefundene Fehler (mit Beschreibung und betroffener Datei)
- Behobene Fehler (Datum und Lösung vermerken)
- Neue offene Risiken oder Annahmen
- Abgeschlossene Aufgaben
- Neu erkannte To-dos
- Änderungen am Abgabestatus

### 8.4 Abschluss-Zusammenfassung nach jeder größeren Aufgabe

Am Ende jeder Antwort, die eine relevante Projektänderung enthält, folgendes
kurz ausgeben:

```
---
**Änderungsprotokoll:**
- Erstellt/Geändert: [Dateiname] – [was]
- Getestet: [was wurde ausgeführt, mit welchem Ergebnis]
- Noch offen: [was fehlt noch]
- PROJECT_STATUS.md: [aktualisiert / nicht aktualisiert, warum]
---
```

---

## 9. Wichtige Dateipfade

| Datei / Ordner | Inhalt |
|---|---|
| `Aufgabenstellung.pdf` | Prüfungsrelevante Aufgabenstellung – immer zuerst lesen |
| `docs/00_part1_checklist.md` | Checkliste aller Anforderungen Teil 1 |
| `docs/01_data_classification.md` | Klassifikation aller 13 Eventtypen |
| `docs/12_etl_concept.md` | ETL-Konzept mit Mapping-Tabelle |
| `sql/` | Alle PostgreSQL DDL-Skripte (01–08) |
| `cypher/01_create_graph_model.cypher` | Neo4j Constraints, Stammdaten, Topologie |
| `bananasupplychain/etl_load.py` | ETL-Hauptskript (383 Events → 5 Systeme) |
| `bananasupplychain/container/docker-compose.yml` | Docker-Setup aller 5 Datenbanken |
| `shared/erp/` | 50 ERP-JSON-Events |
| `shared/wms/` | 70 WMS-JSON-Events |
| `shared/tms/` | 263 TMS-JSON-Events |
