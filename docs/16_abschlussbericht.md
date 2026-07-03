# Abschlussbericht – Banana Supply Chain Datenplattform

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26 – TH Lübeck
**Gruppe:** 7 · **Deadline:** 06.07.2026

Dieser Bericht fasst die Ergebnisse aus **Teil 1 (Datenmanagement)** und
**Teil 2 (Analytics)** zusammen. Alle Zahlen stammen aus dem zuletzt vollständig
neu generierten und geladenen Datenbestand (252 Bestellungen, 13 Monate,
2025-06-17 bis 2026-06-14). Detailnachweise stehen in den referenzierten
Einzeldokumenten (`docs/00`–`docs/15`).

---

## 1. Projektüberblick

Der Use Case ist eine Bananen-Lieferkette von der Plantage in Ghana über die
Seefracht nach Rotterdam bis zur Auslieferung an zehn deutsche/europäische
Retailer. Drei Quellsysteme (**ERP, WMS, TMS**) liefern **13 Eventtypen** als
JSON-Dateien in `shared/`. Ein zweiphasiger ETL-Prozess verteilt diese über
**Polyglot Persistence** auf fünf Zielsysteme und anschließend in ein
DWH-Sternschema. Der gesamte Stack läuft containerisiert (Docker).

| Baustein | Technologie |
|---|---|
| Relationale Stamm-/Bewegungsdaten, MDM, Metadaten, DWH | PostgreSQL 15 |
| Event-Dokumente | MongoDB 7 |
| Echtzeit-Tracking | Redis 7 |
| Supply-Chain-Graph | Neo4j 5 |
| Logistikdokumente | MinIO (Object Store) |

---

## 2. Teil 1 – Datenmanagement

### 2.1 Datenklassifikation und Modellierung
Alle 13 Eventtypen sind als Stamm-, Bewegungs- oder Ereignisdaten klassifiziert
(`docs/01`), jeweils mit Primär-Zielsystem und Begründung. Die relationalen
Modelle für ERP (suppliers, customers, products, orders, order_items, batches),
WMS (warehouse_skus, supply_chain_nodes, node_processings) und TMS (carriers,
shipments, positions, completions, deliveries) liegen mit PK/FK, ON-DELETE-Regeln
und CHECK-Constraints vor (`sql/02`–`04`, ER-Modell in `docs/03`).

### 2.2 Polyglot Persistence – Begründung je System
- **PostgreSQL:** transaktionale Stamm-/Bewegungsdaten mit referenzieller Integrität.
- **MongoDB:** Shipment-Lifecycle als eingebettetes Dokument – heterogene Felder ohne NULL-Overhead; TTL-Index auf GPS-Events.
- **Redis:** Echtzeit-Tracking (STRING/HASH/LIST/SORTED SET/COUNTER) mit TTLs, `allkeys-lru`.
- **Neo4j:** Pfadabfragen PLANTATION → RETAIL (6 Hops) sind im Graph natürlich, in SQL teure rekursive Joins.
- **MinIO:** Logistik-PDFs als Objekte; PostgreSQL speichert nur die Referenz (Bucket + Objektpfad), nicht das BLOB.

### 2.3 MDM und Metadaten
Die bewusste Schlüssel-Inkonsistenz `BAN-101` (ERP) = `BAN_101` (WMS) =
`ban-101` (TMS) wird über `mdm.resolve_canonical_key()` auf das ERP-Format
aufgelöst (`docs/04`). Das Metadatenmanagement (`docs/05`) hält Skalenniveaus
(z. B. `avg_temperature` INTERVAL, `delay_minutes` RATIO, `delivery_priority`
ORDINAL) und Qualitätsregeln je Spalte.

### 2.4 Datenqualität
**41 Checks über 6 Dimensionen** (Vollständigkeit, Eindeutigkeit, Konsistenz,
Plausibilität, Aktualität, Referenzielle Integrität): **38 PASS (93 %)**. Die
**3 FAILs sind bewusst** und belegen echte Supply-Chain-Probleme statt sie zu
verstecken (`docs/13`):
- **4.3 / 4.4 Kühlkettenbrüche** (Temperatur außerhalb 10–15 °C) – Ursache des Qualitätsverlusts.
- **6.3 delivery_status vs. SLA** – dokumentierte Zwei-Schwellen-Logik (30-min-Leg vs. 60-min-SLA).

### 2.5 Data Warehouse
Sternschema mit **1 Faktentabelle + 7 Dimensionen** und Date-Spine 2025–2027
(1.095 Zeilen). Der Fakt ist **faithful** modelliert: jede Endlieferung wird
über `order_reference` auf ihre *tatsächliche* Bestellung gemappt (252 Zeilen,
10 Kunden, 13 Monate) – dadurch sind Zeitreihen-, Segment- und Prognoseanalysen
belastbar (`docs/07`). Fünf vorberechnete Views dienen als direkte
Analytics-Quelle.

### 2.6 Verifikation
`verify_all_systems.py` prüft alle fünf Zielsysteme end-to-end: **43 Checks, 0 FAIL** (41 PASS + 2 TTL-WARN beim Redis-Cache).

---

## 3. Teil 2 – Analytics

### 3.1 KPIs (`docs/14`, `sql/10_kpi_queries.sql`)
| KPI | Ziel | Ist |
|---|--:|--:|
| Liefertreue (OTD) | ≥ 95 % | **96,8 %** |
| Ø Transportdauer | ≤ 18 T | **14,92 T** |
| Temperaturausreißer-Quote | ≤ 10 % | **7,9 %** |
| Ø Bestellwert | ≥ 1.000 € | **1.289,72 €** |
| Batchqualitätsrate (OK) | ≥ 40 % | **36,5 %** |
| Gesamtumsatz | – | **325.008,80 €** |

Vier von fünf Zielwerten erfüllt; die Batchqualität verfehlt 40 % knapp, der
Ø-Schwund (10,58 %) liegt aber unter dem 15-%-Ziel.

### 3.2 Deskriptive Statistik (`analytics/descriptive_stats.py`)
Vollständige Kennzahlen (n, Min, Max, Mittelwert, Median, Std, Q1, Q3, IQR) +
IQR-Ausreißer für `delay_minutes`, `avg_temperature`, `quantity`, `unit_price`,
`total_value`. Die IQR-Methode identifiziert genau die fachlichen Anomalien
(7 Temperatur-, 2 Verzögerungsausreißer) und **keine** Menge-Ausreißer – die
Mengenstreuung ist gewolltes Segmentverhalten.

### 3.3 Python-Charts (`analytics/dashboard.py`)
Fünf wirtschaftlich getriebene Charts (PDF/PNG + interaktives HTML): Umsatz je
Kundensegment, Verspätungsgründe, Bestellwert-Boxplot je Kundentyp, Ø
Transportkosten je Route, Batchqualität über Zeit.

### 3.4 Clustering (`analytics/clustering.py`)
k-Means-Kundensegmentierung mit fachlich gewähltem **k = 3** (nur 10 Kunden;
Elbow/Silhouette dienen als Diagnose, k=5 wäre übersegmentiert). Features:
Bestellhäufigkeit, Ø Bestellwert, Ø Verzögerung, Liefertreue. Der Scatterplot
zeigt als Business-Interpretation Ø Bestellwert vs. Ø Verzögerung; eine
Kreuztabelle validiert die Cluster gegen das echte `customer_type`.

### 3.5 Absatzprognose (`analytics/forecast.py`)
ARIMA(1,0,1) auf der monatlichen Bestellmenge (13 echte Monate + 24 Monate
transparent markierte synthetische History zur Modellstabilität). 3-Monats-
Prognose mit **RMSE 3.626 / MAE 3.035** Einheiten als In-Sample-Fit-Fehler auf
den echten Monaten (Basisniveau ~11.600 Einheiten/Monat).

### 3.6 PowerBI-Konzept (`docs/15`)
Umsetzungsreifes Konzept: Sternschema-Datenmodell (rollenspielende `dim_date`),
DAX-Measures für alle KPIs, vier Report-Seiten (Überblick / Logistik / Kühlkette
/ Umsatz), Slicer und Geokarte aus dem GPS-Trace. Datenquelle PostgreSQL-DWH im
Import-Modus.

---

## 4. Kennzahlen-Überblick (nach vollständigem Durchlauf)

| Bereich | Wert |
|---|---|
| Quelldateien (ERP / WMS / TMS) | 534 / 1.522 / 6.300 = **8.356** |
| Bestellungen / Order-Items / Batches | je **252** |
| Shipments / GPS-Positionen / Completions / Deliveries | 1.512 / 3.009 / 1.512 / 252 |
| MongoDB (shipment/node/batch/order events) | 1.512 / 1.512 / 252 / 252 |
| Neo4j Nodes | 2.058 |
| MinIO PDFs | 2.444 |
| DWH fact_fulfillment / dim_date | 252 / 1.095 |
| Verifikation | **43 Checks, 0 FAIL** |
| Datenqualität | **38/41 PASS (93 %)**, 3 bewusste FAILs |
| Gesamtumsatz | **325.008,80 €** |

---

## 5. Bewusste Entscheidungen und Einschränkungen

- **3 DQ-FAILs bleiben bestehen** – sie bilden reale Kühlketten- und SLA-Probleme ab; ihr „Wegputzen" würde die Analytik verfälschen.
- **Zwei SLA-Schwellen** (30 min operativer Leg-Delay, 60 min Liefer-SLA) sind absichtlich getrennt und dokumentiert.
- **Prognose-History teils synthetisch** – 13 reale Monate reichen für ARIMA-Stabilität nicht aus; die synthetischen Punkte sind im Chart transparent markiert.
- **PowerBI als Konzept** – die `.pbix`-Datei ist optional (PowerBI Desktop nur unter Windows); alle Visuals/Measures sind 1:1 nachbaubar spezifiziert.
- **Kontrollierte Zusatz-Inkonsistenzen (Generator #8)** wurden bewusst nicht ergänzt – die vorhandene DQ-Abdeckung ist ausreichend.

---

## 6. Fazit

Die Plattform deckt beide Projektteile vollständig ab: ein konsistentes,
polyglottes Datenfundament mit belegter Qualität (Teil 1) und darauf aufbauende,
wirtschaftlich interpretierbare Analysen (Teil 2). Datengenerator, ETL, alle
fünf Zielsysteme, DWH und sämtliche Analytics-Skripte laufen reproduzierbar und
sind gegen die Container getestet (verify 43 Checks/0 FAIL, DQ 38/41). Offene Punkte
bestehen nur noch als bewusste, dokumentierte Entscheidungen.
