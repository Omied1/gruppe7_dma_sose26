# Datenqualitäts-Audit – Ergebnisse

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26
**Stand:** 2026-07-02 (41 Checks; Kern-Set/Segment/Qualität 7.1–7.7 ergänzt; 4.10 GPS + 6.4 Carrier-Modus behoben; 4.3/4.4 Kühlkette nun FAIL)
**SQL-Skripte:** `sql/08_data_quality_checks.sql` (Einzelchecks, 41 Regeln) · `sql/08b_dq_audit.sql` (konsolidierte Übersicht)

---

## 1. Methodik

Die Banana-Supply-Chain-Datenbank wurde gegen **41 Qualitätsregeln** in den **6 Dimensionen** nach DAMA-Standard geprüft. Jede Regel liefert eine Zahl `verstoesse` (Anzahl Datensätze, die die Regel verletzen) und einen Status (`PASS` = 0 Verstöße, `FAIL` = ≥ 1 Verstoß).

**Zwei-Linien-Schutz** der Datenqualität in diesem Projekt:

| Linie | Wirkung | Beispiel |
|---|---|---|
| **Präventiv** (DB-Constraints) | Verhindert ungültige Inserts | `CHECK (quantity > 0)` blockiert negative Mengen |
| **Detektiv** (DQ-Checks) | Findet Verstöße nach dem Insert | `WHERE temperature < 10 OR > 15` findet Kühlkettenbrüche |

Der Sanity-Test (siehe §4) belegt: Eine bewusst negative Menge kann gar nicht erst eingefügt werden — der CHECK-Constraint greift. Erst Verstöße ohne DB-Schutz (Temperatur, Zeitlogik, Konsistenz) durchdringen die erste Linie und werden von den DQ-Checks aufgedeckt.

**Hinweis zu bewussten FAILs:** Drei Checks liefern gewollt FAIL — **4.3/4.4** (modellierte Kühlkettenbrüche, Plausibilitätsbefund) und **6.3** (Roh-Inkonsistenz delivery_status vs. SLA, die das DWH bereinigt). Die früheren FAILs **4.10** (GPS) und **6.4** (Carrier-Modus) wurden durch Generator-Anpassungen behoben und sind jetzt PASS. Details in §3.7.

---

## 2. Audit-Ergebnis (Stand 2026-05-24)

Ausführung gegen die Live-PostgreSQL nach erfolgreichem ETL Phase 1 + 2:

| # | Dimension | Tabelle | Regel | Verstöße | Status |
|---|---|---|---|---:|---|
| 1.1 | Vollständigkeit | `erp.products` | supplier_id NULL | 0 | ✅ PASS |
| 1.2 | Vollständigkeit | `erp.order_items` | quantity oder unit_price NULL | 0 | ✅ PASS |
| 1.3 | Vollständigkeit | `wms.node_processings` | temperature NULL (Kühlkette-Lücke) | 0 | ✅ PASS |
| 1.4 | Vollständigkeit | `tms.deliveries` | received_by NULL bei SUCCESSFUL | 0 | ✅ PASS |
| 1.5 | Vollständigkeit | `erp.orders` | Order ohne Bestellpositionen | 0 | ✅ PASS |
| 2.1 | Eindeutigkeit | `erp.suppliers` | supplier_code Duplikat | 0 | ✅ PASS |
| 2.2 | Eindeutigkeit | `erp.orders` | order_reference Duplikat | 0 | ✅ PASS |
| 2.3 | Eindeutigkeit | `erp.batches` | batch_identifier Duplikat | 0 | ✅ PASS |
| 2.4 | Eindeutigkeit | `tms.shipments` | shipment_identifier Duplikat | 0 | ✅ PASS |
| 3.1 | Konsistenz | `wms.warehouse_skus` | SKU ohne MDM-Mapping | 0 | ✅ PASS |
| 3.2 | Konsistenz | `tms.transport_product_references` | TMS-Referenz ohne MDM-Mapping (über normalized_key) | 0 | ✅ PASS |
| 3.3 | Konsistenz | `erp.batches` | wms_sku passt nicht zu product_code | 0 | ✅ PASS |
| 3.4 | Konsistenz | `tms.deliveries + tms.transport_completions` | SUCCESSFUL-Delivery ohne TransportCompleted-Eintrag | 0 | ✅ PASS |
| 4.1 | Plausibilität | `erp.order_items` | quantity ≤ 0 | 0 | ✅ PASS |
| 4.2 | Plausibilität | `erp.order_items` | unit_price außerhalb [1.50, 5.00] EUR | 0 | ✅ PASS |
| **4.3** | **Plausibilität** | `wms.node_processings` | **temperature außerhalb [10, 15] °C (Kühlkettenbruch)** | **230** | **❌ FAIL\*** |
| **4.4** | **Plausibilität** | `tms.shipment_positions` | **container_temperature außerhalb [10, 15] °C** | **463** | **❌ FAIL\*** |
| 4.5 | Plausibilität | `tms.shipment_positions` | latitude/longitude außerhalb Wertebereich | 0 | ✅ PASS |
| 4.6 | Plausibilität | `tms.deliveries` | delivery_status ungültig | 0 | ✅ PASS |
| 4.7 | Plausibilität | `erp.orders` | delivery_priority ungültig | 0 | ✅ PASS |
| 4.8 | Plausibilität | `tms.transport_completions` | delay_minutes > 600 (unplausibel je Leg) | 0 | ✅ PASS |
| 4.9 | Plausibilität | `tms.shipment_positions` | speed_kmh > 200 oder < 0 | 0 | ✅ PASS |
| 4.10 | Plausibilität | `tms.shipment_positions` | GPS-Koordinaten außerhalb erwarteter Routenkorridore | 0 | ✅ PASS |
| 5.0 | Aktualität | `erp.suppliers` | event_timestamp außerhalb 2025–2026 | 0 | ✅ PASS |
| 5.0 | Aktualität | `erp.customers` | event_timestamp außerhalb 2025–2026 | 0 | ✅ PASS |
| 5.0 | Aktualität | `erp.products` | event_timestamp außerhalb 2025–2026 | 0 | ✅ PASS |
| 5.0 | Aktualität | `tms.carriers` | event_timestamp außerhalb 2025–2026 | 0 | ✅ PASS |
| 5.1 | Aktualität | `tms` | TransportCompleted vor TransportStarted | 0 | ✅ PASS |
| 5.2 | Aktualität | `erp.batches` | harvested_at außerhalb Projektlaufzeit (2025–2026) | 0 | ✅ PASS |
| 5.3 | Aktualität | `erp.orders` | Order > 90 Tage ohne Delivery | 0 | ✅ PASS |
| 6.1 | Ref. Integrität | `wms.node_processings` | batch_reference ohne erp.batches | 0 | ✅ PASS |
| 6.2 | Ref. Integrität | `tms.shipments` | cargo_product_reference ohne tms.transport_product_references | 0 | ✅ PASS |
| **6.3** | **Konsistenz** | `tms.deliveries` | **Status-Inkonsistenz mit 60-min-SLA (TMS-Rohstatus vs. SLA-korrigierter Status)** | **80** | **❌ FAIL\*** |
| 6.4 | Konsistenz | `tms.shipments` | Seefracht-Carrier auf TRUCK / Landcarrier auf SEA_FREIGHT | 0 | ✅ PASS |
| 7.1 | Plausibilität | `tms.shipments` | distance_km NULL oder ≤ 0 | 0 | ✅ PASS |
| 7.2 | Plausibilität | `tms.shipments` | transport_cost NULL oder ≤ 0 | 0 | ✅ PASS |
| 7.3 | Konsistenz | `tms.transport_completions` | delay_reason gesetzt XOR delay_minutes > 30 | 0 | ✅ PASS |
| 7.4 | Konsistenz | `tms.shipments + completions` | completed_at < estimated_arrival (Ist vor Plan) | 0 | ✅ PASS |
| 7.5 | Konsistenz | `erp.customers` | customer_type fehlt oder ungültig | 0 | ✅ PASS |
| 7.6 | Plausibilität | `erp.batches` | quality_status fehlt oder ungültig | 0 | ✅ PASS |
| 7.7 | Konsistenz | `erp.batches + node_processings` | quality_status=OK trotz Kühlkettenbruch | 0 | ✅ PASS |

**Score: 38 / 41 = 93 % PASS** — 3 bewusste FAILs (Kühlkettenbrüche 4.3/4.4 als Plausibilitätsbefund + SLA-Inkonsistenz 6.3, dokumentiert in §3.7). Zuvor erwartete FAILs 4.10 (GPS) und 6.4 (Carrier-Modus) wurden durch Generator-Anpassungen **behoben** (jetzt PASS).

---

## 3. Befunde nach Dimension

### 3.1 Vollständigkeit (5/5 PASS)
Alle Pflichtfelder sind gefüllt. Besonders bemerkenswert: `temperature` ist in **allen 1.512** `wms.node_processings`-Einträgen vorhanden — der Datengenerator simuliert eine lückenlose Kühlkettenüberwachung. Check 1.5 bestätigt: Jede der generierten Orders hat mindestens eine Bestellposition.

### 3.2 Eindeutigkeit (4/4 PASS)
Alle Business Keys (`supplier_code`, `order_reference`, `batch_identifier`, `shipment_identifier`) sind eindeutig. Das bestätigt, dass die in K1 behobenen Idempotenz-Bugs vollständig ausgeräumt sind.

### 3.3 Konsistenz (1 bewusster FAIL: 6.3; 6.4 behoben)
**Checks 3.1–3.4: 4/4 PASS.**
Die erste Version von Check 3.1/3.2 prüfte `wms.warehouse_skus.sku = mdm.source_mappings.source_key`. Das schlug fehl, weil das ETL die WMS-SKUs über `normalize_key()` kanonisiert (`BAN_101` → `BAN-101`). Die korrigierte Variante joint direkt über `source_key` (WMS-Format):

```sql
WHERE sm.source_system = 'WMS'
  AND sm.source_key    = w.sku   -- WMS-Format: BAN_101
```

Check 3.4 belegt: Jede `SUCCESSFUL`-Delivery hat einen korrespondierenden `TransportCompleted`-Eintrag — die Event-Kette ist lückenlos.

**Check 6.3: FAIL** (erwartet) — SLA-Inkonsistenz zwischen `delivery_status` und `delay_minutes`. Erklärung in §3.7.

**Check 6.4: PASS** — der Generator wählt Carrier jetzt modusgerecht (Land → TRUCK, See → SEA_FREIGHT) mit konsistenter `carrier_id`. Erklärung in §3.7.

### 3.4 Plausibilität (2 bewusste Kühlketten-FAILs: 4.3/4.4)
**Kühlkette (4.3/4.4): FAIL — bewusst.** 230 von 1.512 NodeProcessed (15,2 %) und 463 GPS-Container-Messungen außerhalb 10–15 °C — die im Generator modellierten Kühlkettenbrüche (Erklärung §3.7).
- GPS-Bereich (WGS84): 0 Verstöße — alle Koordinaten in gültigen Wertebereichen
- Verzögerungen: alle Completions ≤ 180 min
- Speed: alle GPS-Positionen mit speed_kmh zwischen 0 und 200

**Check 4.10: PASS** — GPS-Punkte werden jetzt zwischen den Knoten interpoliert (Ghana → Rotterdam → Deutschland), alle in den Korridoren (Erklärung §3.7).

### 3.5 Aktualität (7/7 PASS)  — Projektlaufzeit 2025–2026
- **Check 5.0** (4 Tabellen): Alle `event_timestamp`-Werte in den Stammdatentabellen liegen innerhalb der Projektlaufzeit (2025–2026, 52-Wochen-Historie).
- **Check 5.1**: Keine Transportabschlüsse vor Transportstart.
- **Check 5.2**: Alle `harvested_at`-Zeitstempel in `erp.batches` liegen innerhalb der Projektlaufzeit 2026. (Bugfix: `erp.batches` hat kein `order_id`-Feld; daher Plausibilitätsprüfung gegen Projektlaufzeit statt direktem Vergleich mit `order_timestamp`.)
- **Check 5.3**: Keine Order älter als 90 Tage ohne Delivery (jede Order wird vollständig ausgeliefert).

### 3.6 Referenzielle Integrität (2/2 PASS)
Alle Cross-Schema-Referenzen (WMS↔ERP, TMS↔TMS-Produktreferenz) sind auflösbar. Die `carrier_id NOT NULL`-Constraint in `tms.shipments` macht einen separaten NULL-Check obsolet — dieser wurde aus dem Audit entfernt (war in der alten Version Check 6.3 „Shipment ohne Carrier").

### 3.7 Bewusste FAILs — Erklärung und Behandlung

Drei Checks liefern **bewusst** FAIL. Sie sind kein Datenfehler, sondern modellierte Realität (Kühlkette) bzw. eine gewollte Roh-Inkonsistenz, die das DWH bereinigt.

#### FAIL 4.3 / 4.4 — Kühlkettenbrüche (Plausibilität)

Der Generator modelliert in `random_temperature()` bewusst ~15 % Temperaturen außerhalb 10–15 °C (≈70 % zu warm = Reifung/Verderb, ≈30 % zu kalt = Kälteschaden):

```python
COLD_CHAIN_BREAK_RATE = 0.15   # ~15 % der Messungen brechen die Kühlkette
```

**Gemessen:** **230** von 1.512 `NodeProcessed` (15,2 %) und **463** GPS-Container-Messungen außerhalb des Sollbereichs.
**Behandlung:** Erwünschter Befund — Grundlage für die Kühlketten-KPIs und für Feature D (Kühlkette → Batch-Qualität: `quality_status`/`spoilage_pct`). Check **7.7** belegt die Kausalität (ein als OK markierter Batch hat nie einen Bruch). Keine „Korrektur"; die Brüche **sind** das analytische Signal.

#### FAIL 6.3 — delivery_status vs. delay_minutes SLA-Inkonsistenz

Der Generator würfelt `delivery_status` **unabhängig** von `delay_minutes` (`complete_delivery()`: `random.choice(["SUCCESSFUL","SUCCESSFUL","DELAYED"])`). Dadurch:

- **Fall A:** `delivery_status = 'SUCCESSFUL'` obwohl `delay_minutes > 60` → SLA verletzt, DWH korrigiert zu DELAYED
- **Fall B:** `delivery_status = 'DELAYED'` obwohl `delay_minutes ≤ 60` → innerhalb SLA, DWH korrigiert zu SUCCESSFUL

**Gemessen:** **80** Inkonsistenzen (SLA-Schwelle 60 min).
**Behandlung:** Rohdaten bleiben unverändert (bewusster Cleansing-Showcase). ETL Phase 2 (`etl_dwh.py`) leitet `on_time_flag` und den bereinigten Status aus `delay_minutes ≤ 60` neu ab — das DWH ist konsistent.
*Abgrenzung der Schwellen:* Die **30-min**-Schwelle steuert den `delay_reason` je **Transport-Leg** (operatives Monitoring), die **60-min**-SLA bewertet die **Gesamtlieferung** (KPI Liefertreue) — zwei bewusst getrennte Ebenen.

#### Behoben (vormals FAIL, jetzt PASS)

- **4.10 GPS-Routenkorridore:** GPS-Punkte werden jetzt zwischen Quell- und Zielknoten interpoliert (Ghana → Rotterdam → Deutschland) statt zufällig weltweit → alle Punkte in den Korridoren → **PASS**.
- **6.4 Carrier-Transportmodus:** Der Generator wählt Carrier jetzt modusgerecht (Land → TRUCK, See → SEA_FREIGHT) mit konsistenter `carrier_id` → **PASS**. Carrier-Vergleiche im DWH sind damit fachlich valide.

---

## 4. Sanity-Test – Werden FAILs erkannt?

100 % PASS bei generierten Testdaten kann täuschen: Wir müssen beweisen, dass die Checks auch dann anschlagen, **wenn Verstöße tatsächlich vorhanden sind**.

**Vorgehen:** In einer `BEGIN/ROLLBACK`-Transaktion künstliche Verstöße einbauen, DQ-Audit ausführen, danach Rollback (keine bleibenden Änderungen).

**Injizierte Verstöße:**
| Regel | Manipulation |
|---|---|
| 4.3 | `INSERT temperature = 25.5°C` in `wms.node_processings` |
| 5.2 | Neuer Batch mit `harvested_at = order_timestamp - 5 Tage` |
| 3.1 | Neue SKU `UNKNOWN-999` ohne MDM-Mapping |

**Beobachtung:** Ein vierter Versuch (`quantity = -1` in `erp.order_items`) wurde von dem DB-CHECK-Constraint `order_items_quantity_check` **präventiv blockiert** — bestätigt die erste Verteidigungslinie.

**Ergebnis der drei verbleibenden Verstöße:**

```
   dimension   | nummer |       tabelle        |              regel              | verstoesse | status
---------------+--------+----------------------+---------------------------------+------------+--------
 PLAUSIBILITÄT | 4.3    | wms.node_processings | temperature außerhalb [10,15]   |          1 | FAIL
 AKTUALITÄT    | 5.2    | erp                  | BatchHarvested vor OrderCreated |          1 | FAIL
 KONSISTENZ    | 3.1    | wms.warehouse_skus   | SKU ohne MDM-Mapping            |          1 | FAIL
```

3 von 3 Verstößen korrekt erkannt → **Detektionsrate 100 %**. Die DQ-Checks sind beweisbar funktionsfähig, nicht nur „grün, weil keine Verstöße da sind".

---

## 5. Bewertung

| Aspekt | Bewertung |
|---|---|
| Abdeckung aller 6 DAMA-Dimensionen | ✅ vollständig |
| Anzahl Checks | 34 (weit über Mindestanforderung „2 pro Dimension" hinaus) |
| Funktionsnachweis | ✅ Sanity-Test zeigt korrekte FAIL-Detektion |
| Live-Audit-Ergebnis | 38/41 PASS = 93 % (3 bewusste FAILs aus Datengenerator-Inkonsistenzen) |
| Konsolidierte Übersicht | ✅ `sql/08b_dq_audit.sql` liefert Single-Result-Set |
| Bugfix dokumentiert | ✅ Check 5.2 korrigiert (kein `order_id`-FK in `erp.batches`) |
| Neue Checks (gegenüber v1) | ✅ VQ-05, KQ-04, PQ-10 (GPS-Korridore), AQ-5.0 (event_timestamp), KQ-6.3 (SLA), KQ-6.4 (Carrier-Modus) |
| Erwartete FAILs explizit begründet | ✅ §3.7 mit Ursache, Umfang und Behandlungsstrategie |

---

## 6. Ausführungsanleitung

**DQ-Audit (konsolidiert):**
```bash
docker exec -i postgres psql -U user -d logistics < sql/08b_dq_audit.sql
```

**DQ-Detail-Checks (mit betroffenen IDs):**
```bash
docker exec -i postgres psql -U user -d logistics < sql/08_data_quality_checks.sql
```

**PostgreSQL-Befüllungsnachweise (alle Schemas + DWH + FK):**
```bash
docker exec -i postgres psql -U user -d logistics < sql/09_verification_queries.sql
```

**MongoDB / Redis / Neo4j / MinIO – Systemübergreifende Verifikation:**
```bash
cd bananasupplychain && python3 verify_all_systems.py
```

**Neo4j – Graphmodell-Prüfqueries (im Neo4j Browser oder cypher-shell):**
```bash
cypher-shell -u neo4j -p password -f cypher/02_verification_queries.cypher
```

**Erwartetes Ergebnis nach sauberem ETL-Lauf:** 38/41 DQ-Checks PASS. FAILs bei 4.3, 4.4, 6.3 sind bewusst und in §3.7 begründet.

---

## 7. Systemübergreifende Befüllungsnachweise (Stand 2026-05-14)

Ergänzend zu den 41 DQ-Checks belegen die folgenden Prüfqueries, dass alle fünf Zielsysteme nach einem vollständigen ETL-Lauf korrekt befüllt wurden.

### 7.1 PostgreSQL – Tabellenmengen (sql/09_verification_queries.sql)

| Schema | Tabelle | Zeilen | Kommentar |
|---|---|---:|---|
| `erp` | `suppliers` | 10 | SUP-101 bis SUP-110 |
| `erp` | `customers` | 10 | CUST-101 bis CUST-110 |
| `erp` | `products` | 10 | BAN-101 bis BAN-110 (ERP-Format) |
| `erp` | `orders` | 10 | 10 OrderCreated-Events (1 pro Iteration) |
| `erp` | `order_items` | 10 | 1 Item pro Order |
| `erp` | `batches` | 10 | 10 BatchHarvested-Events |
| `erp` | `document_references` | ≥ 66 | befüllt durch `generate_documents.py` |
| `wms` | `warehouse_skus` | 10 | BAN_101..BAN_110 (WMS-Format) |
| `wms` | `supply_chain_nodes` | 7 | PLANTATION bis RETAIL |
| `wms` | `node_processings` | 60 | 10 Batches × 6 aktive Knoten |
| `tms` | `carriers` | 5 | CAR-101 bis CAR-105 |
| `tms` | `transport_product_references` | 10 | ban-101..ban-110 (TMS-Format) |
| `tms` | `shipments` | 60 | 60 TransportStarted-Events |
| `tms` | `shipment_positions` | ≈112 | ≈2 GPS-Positionen je Shipment |
| `tms` | `transport_completions` | 60 | 60 TransportCompleted-Events |
| `tms` | `deliveries` | 10 | 10 DeliveryCompleted-Events |
| `mdm` | `golden_records` | 42 | 10 Prod + 10 Kund + 10 Lief + 5 Carrier + 7 Knoten |
| `mdm` | `source_mappings` | 69 | ERP=30, WMS=17, TMS=22 |
| `dwh` | `dim_date` | 1095 | 2025-01-01 bis 2027-12-31 (Date Spine) |
| `dwh` | `dim_customer` | 10 | aus ETL Phase 2 |
| `dwh` | `dim_supplier` | 10 | aus ETL Phase 2 |
| `dwh` | `dim_product` | 10 | aus ETL Phase 2 |
| `dwh` | `dim_carrier` | 5 | aus ETL Phase 2 |
| `dwh` | `dim_supply_chain_node` | 7 | aus ETL Phase 2 |
| `dwh` | `dim_delivery_status` | 4 | SUCCESSFUL, DELAYED, FAILED, IN_TRANSIT |
| `dwh` | `fact_fulfillment` | 10 | 10 Endlieferungen (1 pro Iteration, Grain-Fix 2026-05-15) |

**FK-Integrität (intra-Schema):** 0 Orphan-Datensätze in allen geprüften Beziehungen.
**Cross-Schema-Referenzen:** WMS `batch_reference` → ERP `batch_identifier` = 0 Fehler; TMS `cargo_product_reference` → TMS `transport_product_references` = 0 Fehler.

### 7.2 MDM – Schlüsselauflösung

| Eingabe | Quellsystem | Ergebnis `resolve_canonical_key()` | Status |
|---|---|---|---|
| `BAN-101` | ERP | `BAN-101` | ✅ PASS |
| `BAN_101` | WMS | `BAN-101` | ✅ PASS |
| `ban-101` | TMS | `BAN-101` | ✅ PASS |

Alle 42 Golden Records haben genau ein kanonisches Source Mapping (`is_canonical_check` = PASS).

### 7.3 MongoDB – Collection-Counts und Strukturprüfung

| Collection | Dokumente | Prüfung | Status |
|---|---:|---|---|
| `shipment_events` | ≥ 60 | Unique-Index auf `shipment_identifier` vorhanden | ✅ PASS |
| `shipment_events` | ≥ 60 | TTL-Index (90 Tage) vorhanden | ✅ PASS |
| `shipment_events` | ≥ 60 | `events[]`-Array in Dokumenten vorhanden | ✅ PASS |
| `node_events` | ≥ 60 | `quality_flags` (temperature_ok) vorhanden | ✅ PASS |
| `batch_tracking` | ≥ 10 | `nodes_processed[]` eingebettet | ✅ PASS |
| `order_events` | ≥ 10 | Unique-Index auf `order_reference` vorhanden | ✅ PASS |

### 7.4 Redis – Key-Typen und -Counts

| Key-Pattern | Typ | Anzahl | Status |
|---|---|---:|---|
| `shipment:status:*` | STRING | ≥ 120 | ✅ PASS |
| `shipment:info:*` | HASH | ≥ 120 | ✅ PASS |
| `shipment:position:*` | HASH | ≥ 1 (TTL 1h) | ✅ PASS |
| `shipment:route:*` | ZSET | ≥ 1 | ✅ PASS |
| `order:status:*` | STRING | ≥ 10 | ✅ PASS |
| `order:timeline:*` | LIST | ≥ 10 | ✅ PASS |
| `cache:product:*` | HASH | ≥ 10 | ✅ PASS |
| `system:counter:etl_runs` | STRING | ≥ 1 | ✅ PASS |

### 7.5 Neo4j – Nodes, Relationships und Topologie

| Prüfung | Ergebnis | Status |
|---|---|---|
| Supplier-Nodes | 10 | ✅ PASS |
| Customer-Nodes | 10 | ✅ PASS |
| Product-Nodes | 10 | ✅ PASS |
| SupplyChainNode-Nodes | 7 | ✅ PASS |
| Carrier-Nodes | 5 | ✅ PASS |
| Order-Nodes | ≥ 10 (ETL) | ✅ PASS |
| Batch-Nodes | ≥ 10 (ETL) | ✅ PASS |
| Shipment-Nodes | ≥ 60 | ✅ PASS |
| Nodes gesamt | ≥ 124 | ✅ PASS |
| Relationships gesamt | ≥ 47 (Ist 464) | ✅ PASS |
| Kürzester Pfad PLANTATION → RETAIL | 6 Hops | ✅ PASS |
| Produkte ohne SUPPLIES-Beziehung | 0 | ✅ PASS |
| Demo-Batch PROCESSED_AT (7 Stationen) | 7 | ✅ PASS |

### 7.6 MinIO – Buckets und Objekte

| Bucket | Objekte | Metadaten | Status |
|---|---:|---|---|
| `delivery-notes` | ≥ 60 | `shipment_identifier`, `transport_mode` | ✅ PASS |
| `invoices` | ≥ 6 | `shipment_identifier`, `delivery_status` | ✅ PASS |
| `transport-docs` | ≥ 10 | `document_type: bill_of_lading` | ✅ PASS |
| `batch-certificates` | ≥ 10 | `batch_identifier`, `product_code` | ✅ PASS |

**Referenzierungsmuster:** PostgreSQL `erp.document_references` enthält Einträge mit Bucket-Name und Objektpfad (befüllt durch `generate_documents.py`). Die Dokumente selbst liegen ausschließlich in MinIO — kein BLOB in der Datenbank.

---

## 8. Bewertung (aktualisiert 2026-05-24)

| Aspekt | Bewertung |
|---|---|
| Abdeckung aller 6 DAMA-Dimensionen (PostgreSQL) | ✅ vollständig |
| Anzahl DQ-Checks | 34 (weit über Mindestanforderung „2 pro Dimension") |
| Funktionsnachweis (Sanity-Test) | ✅ Detektionsrate 100 % |
| Live-Audit-Ergebnis | **38/41 PASS = 93 %** |
| Erwartete FAILs | 3 (4.10 GPS-Simulation, 6.3 SLA-Inkonsistenz, 6.4 Carrier-Modus) — alle dokumentiert in §3.7 |
| Konsolidierte Übersicht | ✅ `sql/08b_dq_audit.sql` |
| PostgreSQL-Befüllungsnachweise | ✅ `sql/09_verification_queries.sql` (alle Schemas + DWH + FK) |
| MongoDB / Redis / Neo4j / MinIO | ✅ `bananasupplychain/verify_all_systems.py` |
| Neo4j Graphmodell-Prüfqueries | ✅ `cypher/02_verification_queries.cypher` |
| MDM-Schlüsselauflösung getestet | ✅ alle 3 Formate → BAN-101 |
| DWH Date Spine verifiziert | ✅ 1095 Zeilen (2025-01-01 bis 2027-12-31) |
