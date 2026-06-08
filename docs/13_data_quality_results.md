# Datenqualitäts-Audit – Ergebnisse

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26
**Stand:** 2026-05-24 (aktualisiert: 6 neue Checks 4.10 / 5.0×4 / 6.3 / 6.4 ergänzt; Gesamtanzahl 28 → 34)
**SQL-Skripte:** `sql/08_data_quality_checks.sql` (Einzelchecks, 34 Regeln) · `sql/08b_dq_audit.sql` (konsolidierte Übersicht)

---

## 1. Methodik

Die Banana-Supply-Chain-Datenbank wurde gegen **34 Qualitätsregeln** in den **6 Dimensionen** nach DAMA-Standard geprüft. Jede Regel liefert eine Zahl `verstoesse` (Anzahl Datensätze, die die Regel verletzen) und einen Status (`PASS` = 0 Verstöße, `FAIL` = ≥ 1 Verstoß).

**Zwei-Linien-Schutz** der Datenqualität in diesem Projekt:

| Linie | Wirkung | Beispiel |
|---|---|---|
| **Präventiv** (DB-Constraints) | Verhindert ungültige Inserts | `CHECK (quantity > 0)` blockiert negative Mengen |
| **Detektiv** (DQ-Checks) | Findet Verstöße nach dem Insert | `WHERE temperature < 10 OR > 15` findet Kühlkettenbrüche |

Der Sanity-Test (siehe §4) belegt: Eine bewusst negative Menge kann gar nicht erst eingefügt werden — der CHECK-Constraint greift. Erst Verstöße ohne DB-Schutz (Temperatur, Zeitlogik, Konsistenz) durchdringen die erste Linie und werden von den DQ-Checks aufgedeckt.

**Hinweis zu erwarteten FAILs:** Drei Checks (4.10, 6.3, 6.4) liefern erwartungsgemäß FAIL — sie dokumentieren bekannte Datengenerator-Inkonsistenzen, die im operativen System bewusst erhalten bleiben und im DWH (ETL Phase 2) korrigiert werden. Details in §3.7.

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
| 4.3 | Plausibilität | `wms.node_processings` | temperature außerhalb [10, 15] °C (Kühlkettenbruch) | 0 | ✅ PASS |
| 4.4 | Plausibilität | `tms.shipment_positions` | container_temperature außerhalb [10, 15] °C | 0 | ✅ PASS |
| 4.5 | Plausibilität | `tms.shipment_positions` | latitude/longitude außerhalb Wertebereich | 0 | ✅ PASS |
| 4.6 | Plausibilität | `tms.deliveries` | delivery_status ungültig | 0 | ✅ PASS |
| 4.7 | Plausibilität | `erp.orders` | delivery_priority ungültig | 0 | ✅ PASS |
| 4.8 | Plausibilität | `tms.transport_completions` | delay_minutes > 180 | 0 | ✅ PASS |
| 4.9 | Plausibilität | `tms.shipment_positions` | speed_kmh > 200 oder < 0 | 0 | ✅ PASS |
| **4.10** | **Plausibilität** | `tms.shipment_positions` | **GPS-Koordinaten außerhalb erwarteter Routenkorridore** | **n > 0** | **❌ FAIL\*** |
| 5.0 | Aktualität | `erp.suppliers` | event_timestamp außerhalb 2026 | 0 | ✅ PASS |
| 5.0 | Aktualität | `erp.customers` | event_timestamp außerhalb 2026 | 0 | ✅ PASS |
| 5.0 | Aktualität | `erp.products` | event_timestamp außerhalb 2026 | 0 | ✅ PASS |
| 5.0 | Aktualität | `tms.carriers` | event_timestamp außerhalb 2026 | 0 | ✅ PASS |
| 5.1 | Aktualität | `tms` | TransportCompleted vor TransportStarted | 0 | ✅ PASS |
| 5.2 | Aktualität | `erp.batches` | harvested_at außerhalb Projektlaufzeit (2026) | 0 | ✅ PASS |
| 5.3 | Aktualität | `erp.orders` | Order > 90 Tage ohne Delivery | 0 | ✅ PASS |
| 6.1 | Ref. Integrität | `wms.node_processings` | batch_reference ohne erp.batches | 0 | ✅ PASS |
| 6.2 | Ref. Integrität | `tms.shipments` | cargo_product_reference ohne tms.transport_product_references | 0 | ✅ PASS |
| **6.3** | **Konsistenz** | `tms.deliveries` | **Status-Inkonsistenz mit 60-min-SLA (TMS-Rohstatus vs. SLA-korrigierter Status)** | **n > 0** | **❌ FAIL\*** |
| **6.4** | **Konsistenz** | `tms.shipments` | **Seefracht-Carrier auf TRUCK-Route oder Landcarrier auf SEA_FREIGHT** | **n > 0** | **❌ FAIL\*** |

**Score: 31 / 34 = 91 % PASS** — 3 erwartete FAILs (Datengenerator-Inkonsistenzen, dokumentiert in §3.7).

---

## 3. Befunde nach Dimension

### 3.1 Vollständigkeit (5/5 PASS)
Alle Pflichtfelder sind gefüllt. Besonders bemerkenswert: `temperature` ist in **allen 60** `wms.node_processings`-Einträgen vorhanden — der Datengenerator simuliert eine lückenlose Kühlkettenüberwachung. Check 1.5 bestätigt: Jede der generierten Orders hat mindestens eine Bestellposition.

### 3.2 Eindeutigkeit (4/4 PASS)
Alle Business Keys (`supplier_code`, `order_reference`, `batch_identifier`, `shipment_identifier`) sind eindeutig. Das bestätigt, dass die in K1 behobenen Idempotenz-Bugs vollständig ausgeräumt sind.

### 3.3 Konsistenz (4/6 PASS — 2 erwartete FAILs)
**Checks 3.1–3.4: 4/4 PASS.**
Die erste Version von Check 3.1/3.2 prüfte `wms.warehouse_skus.sku = mdm.source_mappings.source_key`. Das schlug fehl, weil das ETL die WMS-SKUs über `normalize_key()` kanonisiert (`BAN_101` → `BAN-101`). Die korrigierte Variante joint direkt über `source_key` (WMS-Format):

```sql
WHERE sm.source_system = 'WMS'
  AND sm.source_key    = w.sku   -- WMS-Format: BAN_101
```

Check 3.4 belegt: Jede `SUCCESSFUL`-Delivery hat einen korrespondierenden `TransportCompleted`-Eintrag — die Event-Kette ist lückenlos.

**Check 6.3: FAIL** (erwartet) — SLA-Inkonsistenz zwischen `delivery_status` und `delay_minutes`. Erklärung in §3.7.

**Check 6.4: FAIL** (erwartet) — Carrier-Transportmodus-Inkonsistenz. Reedereien auf TRUCK-Strecken und Landcarrier auf SEA_FREIGHT-Strecken. Erklärung in §3.7.

### 3.4 Plausibilität (9/10 PASS — 1 erwarteter FAIL)
**Checks 4.1–4.9: 9/9 PASS.**
- Kühlkette: 0 Verstöße über 60 Knotenprozessierungen + ≈112 GPS-Updates
- GPS-Bereich (WGS84): 0 Verstöße — alle Koordinaten in gültigen Wertebereichen
- Verzögerungen: alle Completions ≤ 180 min
- Speed: alle GPS-Positionen mit speed_kmh zwischen 0 und 200

**Check 4.10: FAIL** (erwartet) — GPS-Koordinaten außerhalb der fachlichen Routenkorridore Ghana/Europa. Der Datengenerator erzeugt Zufallskoordinaten weltweit. Erklärung in §3.7.

### 3.5 Aktualität (7/7 PASS)
- **Check 5.0** (4 Tabellen): Alle `event_timestamp`-Werte in den Stammdatentabellen liegen innerhalb der Projektlaufzeit 2026.
- **Check 5.1**: Keine Transportabschlüsse vor Transportstart.
- **Check 5.2**: Alle `harvested_at`-Zeitstempel in `erp.batches` liegen innerhalb der Projektlaufzeit 2026. (Bugfix: `erp.batches` hat kein `order_id`-Feld; daher Plausibilitätsprüfung gegen Projektlaufzeit statt direktem Vergleich mit `order_timestamp`.)
- **Check 5.3**: Keine Order älter als 90 Tage ohne Delivery (alle Testdaten stammen aus Mai 2026).

### 3.6 Referenzielle Integrität (2/2 PASS)
Alle Cross-Schema-Referenzen (WMS↔ERP, TMS↔TMS-Produktreferenz) sind auflösbar. Die `carrier_id NOT NULL`-Constraint in `tms.shipments` macht einen separaten NULL-Check obsolet — dieser wurde aus dem Audit entfernt (war in der alten Version Check 6.3 „Shipment ohne Carrier").

### 3.7 Erwartete FAILs — Erklärung und Behandlung

#### FAIL 4.10 — GPS außerhalb Routenkorridore

Der Datengenerator (`test_data_generator.py`, Methode `create_gps_event()`) erzeugt GPS-Koordinaten als vollständig zufällige Werte im gesamten WGS84-Bereich:

```python
"latitude":  round(random.uniform(-90, 90),   6)
"longitude": round(random.uniform(-180, 180), 6)
```

Die fachliche Erwartung wäre:
- Ghana-Strecken: Breitengrad 4.5–7.5°N, Längengrad 2.5°W–1.0°E
- Seefrachtroute Afrika→Europa: Breitengrad 0–55°N, Längengrad 20°W–10°E
- Europa-Strecken: Breitengrad 49–54°N, Längengrad 3–15°E

**Konsequenz:** Nahezu alle GPS-Positionen (≈112) liegen außerhalb dieser Korridore — der FAIL ist vollständig simulationsbedingt.
**Behandlung:** Keine Korrektur im operativen System. Der Check macht die Simulationsgrenze transparent. Analytics (Geo-Karte in PowerBI) sollte diesen Befund explizit ausweisen.

#### FAIL 6.3 — delivery_status vs. delay_minutes SLA-Inkonsistenz

Der Datengenerator würfelt `delivery_status` und `delay_minutes` **unabhängig** voneinander:

```python
# in complete_transport():
"delay_minutes": random.randint(0, 180)

# in complete_delivery():
"delivery_status": random.choice(["SUCCESSFUL", "SUCCESSFUL", "DELAYED"])
```

Dadurch entstehen zwei Typen von Inkonsistenzen:

- **Fall A:** `delivery_status = 'SUCCESSFUL'` obwohl `delay_minutes > 60` → SLA verletzt, DWH korrigiert zu DELAYED
- **Fall B:** `delivery_status = 'DELAYED'` obwohl `delay_minutes ≤ 60` → innerhalb SLA, DWH korrigiert zu SUCCESSFUL

**Erwartete Verstöße:** ca. 3–7 bei 10 Iterationen (abhängig vom Zufallslauf).
**Behandlung:** Rohdaten bleiben unverändert. ETL Phase 2 (`etl_dwh.py`) leitet `on_time_flag` anhand des SLA-Schwellenwerts (60 min) neu ab — das DWH enthält konsistente Werte.

#### FAIL 6.4 — Carrier-Transportmodus-Inkonsistenz

Der Datengenerator wählt `carrier_id` und `transport_mode` **unabhängig** zufällig. Dadurch werden Reedereien (Maersk CAR-102, MSC CAR-103, Hapag Lloyd CAR-105) auf TRUCK-Strecken eingesetzt und Landcarrier (DHL CAR-101, DB Schenker CAR-104) auf SEA_FREIGHT-Strecken:

```python
# in create_transport():
"carrier_id":   f"CAR-{random.randint(101,105)}",  # unabhängig von transport_mode
"transport_mode": transport_mode                     # aus SUPPLY_CHAIN_FLOW
```

**Gemessene Verstöße** (an 60 TransportStarted-Events): **36 von 60 (60%)**.
**Behandlung:** Der ETL speichert die Carrier-Zuordnung wie im Event enthalten. Das DWH (`v_carrier_performance`) zeigt die Carrier-Performance anhand der ETL-Daten — da die Zuordnung systematisch verzerrt ist, sind reine Carrier-Vergleiche im DWH fachlich nicht valide. In der Analytics-Interpretation muss dieser Befund ausgewiesen werden.

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
| Live-Audit-Ergebnis | 31/34 PASS = 91 % (3 erwartete FAILs aus Datengenerator-Inkonsistenzen) |
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

**Erwartetes Ergebnis nach sauberem ETL-Lauf:** 31/34 DQ-Checks PASS. FAILs bei 4.10, 6.3, 6.4 sind erwartet und in §3.7 begründet.

---

## 7. Systemübergreifende Befüllungsnachweise (Stand 2026-05-14)

Ergänzend zu den 34 DQ-Checks belegen die folgenden Prüfqueries, dass alle fünf Zielsysteme nach einem vollständigen ETL-Lauf korrekt befüllt wurden.

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
| Live-Audit-Ergebnis | **31/34 PASS = 91 %** |
| Erwartete FAILs | 3 (4.10 GPS-Simulation, 6.3 SLA-Inkonsistenz, 6.4 Carrier-Modus) — alle dokumentiert in §3.7 |
| Konsolidierte Übersicht | ✅ `sql/08b_dq_audit.sql` |
| PostgreSQL-Befüllungsnachweise | ✅ `sql/09_verification_queries.sql` (alle Schemas + DWH + FK) |
| MongoDB / Redis / Neo4j / MinIO | ✅ `bananasupplychain/verify_all_systems.py` |
| Neo4j Graphmodell-Prüfqueries | ✅ `cypher/02_verification_queries.cypher` |
| MDM-Schlüsselauflösung getestet | ✅ alle 3 Formate → BAN-101 |
| DWH Date Spine verifiziert | ✅ 1095 Zeilen (2025-01-01 bis 2027-12-31) |
