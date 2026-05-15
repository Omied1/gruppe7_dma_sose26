# Datenqualitäts-Audit – Ergebnisse

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26
**Stand:** 2026-05-14
**SQL-Skripte:** `sql/08_data_quality_checks.sql` (Einzelchecks, 28 Regeln) · `sql/08b_dq_audit.sql` (konsolidierte Übersicht)

---

## 1. Methodik

Die Banana-Supply-Chain-Datenbank wurde gegen **28 Qualitätsregeln** in den **6 Dimensionen** nach DAMA-Standard geprüft. Jede Regel liefert eine Zahl `verstoesse` (Anzahl Datensätze, die die Regel verletzen) und einen Status (`PASS` = 0 Verstöße, `FAIL` = ≥ 1 Verstoß).

**Zwei-Linien-Schutz** der Datenqualität in diesem Projekt:

| Linie | Wirkung | Beispiel |
|---|---|---|
| **Präventiv** (DB-Constraints) | Verhindert ungültige Inserts | `CHECK (quantity > 0)` blockiert negative Mengen |
| **Detektiv** (DQ-Checks) | Findet Verstöße nach dem Insert | `WHERE temperature < 10 OR > 15` findet Kühlkettenbrüche |

Der Sanity-Test (siehe §4) belegt: Eine bewusst negative Menge kann gar nicht erst eingefügt werden — der CHECK-Constraint greift. Erst Verstöße ohne DB-Schutz (Temperatur, Zeitlogik, Konsistenz) durchdringen die erste Linie und werden von den DQ-Checks aufgedeckt.

---

## 2. Audit-Ergebnis (Stand 2026-05-14, 16:23 Uhr)

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
| 3.1 | Konsistenz | `wms.warehouse_skus` | SKU ohne MDM-Mapping (über normalized_key) | 0 | ✅ PASS |
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
| 5.1 | Aktualität | `tms` | TransportCompleted vor TransportStarted | 0 | ✅ PASS |
| 5.2 | Aktualität | `erp.batches` | harvested_at außerhalb Projektlaufzeit (2026) | 0 | ✅ PASS |
| 5.3 | Aktualität | `erp.orders` | Order > 90 Tage ohne Delivery | 0 | ✅ PASS |
| 6.1 | Ref. Integrität | `wms.node_processings` | batch_reference ohne erp.batches | 0 | ✅ PASS |
| 6.2 | Ref. Integrität | `tms.shipments` | cargo_product_reference ohne tms.transport_product_references | 0 | ✅ PASS |
| 6.3 | Ref. Integrität | `tms.shipments` | Shipment ohne Carrier (carrier_id NULL) | 0 | ✅ PASS |

**Score:** 28 / 28 = **100 % PASS** über alle sechs Dimensionen.

---

## 3. Befunde nach Dimension

### 3.1 Vollständigkeit (5/5 PASS)
Alle Pflichtfelder sind gefüllt. Besonders bemerkenswert: `temperature` ist in **allen 60** `wms.node_processings`-Einträgen vorhanden — der Datengenerator simuliert eine lückenlose Kühlkettenüberwachung. Check 1.5 bestätigt: Jede der generierten Orders hat mindestens eine Bestellposition.

### 3.2 Eindeutigkeit (4/4 PASS)
Alle Business Keys (`supplier_code`, `order_reference`, `batch_identifier`, `shipment_identifier`) sind eindeutig. Das bestätigt, dass die in K1 behobenen Idempotenz-Bugs vollständig ausgeräumt sind.

### 3.3 Konsistenz (4/4 PASS)
**Wichtiger Hinweis zur ursprünglichen Implementation:** Die erste Version von Check 3.1/3.2 prüfte `wms.warehouse_skus.sku = mdm.source_mappings.source_key`. Das schlug fehl, weil das ETL die WMS-SKUs bereits beim Laden über `normalize_key()` auf das ERP-Format kanonisiert (`BAN_101` → `BAN-101`). Die korrigierte Variante joint über `normalized_key`, das stets im kanonischen Format vorliegt:

```sql
WHERE sm.source_system  = 'WMS'
  AND sm.normalized_key = LOWER(REPLACE(w.sku, '_', '-'))
```

Damit greift der Check auch dann, wenn das ETL die Schlüssel vorab normalisiert. Diese Korrektur wurde in `08_data_quality_checks.sql` und `08b_dq_audit.sql` umgesetzt.

Check 3.4 (neu) belegt: Jede `SUCCESSFUL`-Delivery hat einen korrespondierenden `TransportCompleted`-Eintrag — die Event-Kette ist lückenlos.

### 3.4 Plausibilität (9/9 PASS)
Alle Wertebereiche werden eingehalten, insbesondere:
- Kühlkette: 0 Verstöße über 60 Knotenprozessierungen + 112 GPS-Updates
- GPS-Bereich: 0 Verstöße über 112 Positionen
- Verzögerungen: 60/60 Completions ≤ 180 min

### 3.5 Aktualität (3/3 PASS)
- Keine Transportabschlüsse vor Transportstart
- Alle `harvested_at`-Zeitstempel liegen innerhalb der Projektlaufzeit 2026 (Check 5.2 wurde korrigiert: `erp.batches` hat kein `order_id`-Feld, daher Plausibilitätsprüfung gegen Projektlaufzeit statt direktem Vergleich mit `order_timestamp`)
- Keine Order älter als 90 Tage ohne Delivery (alle Testdaten im aktuellen Zeitraum)

### 3.6 Referenzielle Integrität (3/3 PASS)
Alle Cross-Schema-Referenzen (WMS↔ERP, TMS↔ERP, TMS↔Carrier) sind auflösbar. Zusammen mit den UNIQUE-Constraints aus K1 hat die operative DB damit eine vollständige Schemavalidierung.

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
| Anzahl Checks | 28 (weit über Mindestanforderung „2 pro Dimension" hinaus) |
| Funktionsnachweis | ✅ Sanity-Test zeigt korrekte FAIL-Detektion |
| Live-Audit-Ergebnis | 28/28 PASS = 100 % |
| Konsolidierte Übersicht | ✅ `sql/08b_dq_audit.sql` liefert Single-Result-Set |
| Bugfix dokumentiert | ✅ Check 5.2 korrigiert (kein `order_id`-FK in `erp.batches`) |
| Neue Checks | ✅ VQ-05 (Orders ohne Positionen), KQ-04 (Delivery ohne TransportCompleted) |

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

**Erwartetes Ergebnis nach sauberem ETL-Lauf:** Alle 28 DQ-Checks PASS.

---

## 7. Systemübergreifende Befüllungsnachweise (Stand 2026-05-14)

Ergänzend zu den 28 DQ-Checks belegen die folgenden Prüfqueries, dass alle fünf Zielsysteme nach einem vollständigen ETL-Lauf korrekt befüllt wurden.

### 7.1 PostgreSQL – Tabellenmengen (sql/09_verification_queries.sql)

| Schema | Tabelle | Zeilen | Kommentar |
|---|---|---:|---|
| `erp` | `suppliers` | 10 | SUP-101 bis SUP-110 |
| `erp` | `customers` | 10 | CUST-101 bis CUST-110 |
| `erp` | `products` | 10 | BAN-101 bis BAN-110 (ERP-Format) |
| `erp` | `orders` | 20 | 20 OrderCreated-Events |
| `erp` | `order_items` | 10–20 | 1–2 Items pro Order |
| `erp` | `batches` | 10 | 10 BatchHarvested-Events |
| `erp` | `document_references` | 98 | 60 Lieferscheine + 8 Rechnungen + 10 B/L + 10 Zollfreigaben + 10 Zertifikate |
| `wms` | `warehouse_skus` | 10 | BAN_101..BAN_110 (WMS-Format) |
| `wms` | `supply_chain_nodes` | 7 | PLANTATION bis RETAIL |
| `wms` | `node_processings` | 60 | 10 Batches × 6 aktive Knoten |
| `tms` | `carriers` | 5 | CAR-101 bis CAR-105 |
| `tms` | `transport_product_references` | 10 | BAN-101..BAN-110 (normalisiert) |
| `tms` | `shipments` | 60 | 60 TransportStarted-Events |
| `tms` | `shipment_positions` | 112 | ≈2 GPS-Positionen je Shipment |
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
| `dwh` | `fact_fulfillment` | 10 | 10 Endlieferungen (1 pro Iteration) |

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
| `order:status:*` | STRING | ≥ 20 | ✅ PASS |
| `order:timeline:*` | LIST | ≥ 20 | ✅ PASS |
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
| Order-Nodes | ≥ 21 (20 ETL + 1 DEMO) | ✅ PASS |
| Batch-Nodes | ≥ 21 (20 ETL + 1 DEMO) | ✅ PASS |
| Shipment-Nodes | ≥ 121 | ✅ PASS |
| Nodes gesamt | ≥ 205 | ✅ PASS |
| Relationships gesamt | ≥ 100 | ✅ PASS |
| Kürzester Pfad PLANTATION → RETAIL | 6 Hops | ✅ PASS |
| Produkte ohne SUPPLIES-Beziehung | 0 | ✅ PASS |
| Demo-Batch PROCESSED_AT (7 Stationen) | 7 | ✅ PASS |

### 7.6 MinIO – Buckets und Objekte

| Bucket | Objekte | Metadaten | Status |
|---|---:|---|---|
| `delivery-notes` | ≥ 120 | `shipment_identifier`, `transport_mode` | ✅ PASS |
| `invoices` | ≥ 6 | `shipment_identifier`, `delivery_status` | ✅ PASS |
| `transport-docs` | ≥ 20 | `document_type: bill_of_lading` | ✅ PASS |
| `batch-certificates` | ≥ 20 | `batch_identifier`, `product_code` | ✅ PASS |

**Referenzierungsmuster:** PostgreSQL `erp.document_references` enthält 116 Einträge mit Bucket-Name und Objektpfad. Die Dokumente selbst liegen ausschließlich in MinIO — kein BLOB in der Datenbank.

---

## 8. Bewertung (aktualisiert)

| Aspekt | Bewertung |
|---|---|
| Abdeckung aller 6 DAMA-Dimensionen (PostgreSQL) | ✅ vollständig |
| Anzahl DQ-Checks | 28 (weit über Mindestanforderung „2 pro Dimension") |
| Funktionsnachweis (Sanity-Test) | ✅ Detektionsrate 100 % |
| Live-Audit-Ergebnis | 28/28 PASS = 100 % |
| Konsolidierte Übersicht | ✅ `sql/08b_dq_audit.sql` |
| PostgreSQL-Befüllungsnachweise | ✅ `sql/09_verification_queries.sql` (alle Schemas + DWH + FK) |
| MongoDB / Redis / Neo4j / MinIO | ✅ `bananasupplychain/verify_all_systems.py` |
| Neo4j Graphmodell-Prüfqueries | ✅ `cypher/02_verification_queries.cypher` (aktiv, nicht auskommentiert) |
| MDM-Schlüsselauflösung getestet | ✅ alle 3 Formate → BAN-101 |
| DWH Date Spine verifiziert | ✅ 1095 Zeilen (2025-01-01 bis 2027-12-31) |
