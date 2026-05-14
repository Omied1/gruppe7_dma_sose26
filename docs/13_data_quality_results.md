# Datenqualitäts-Audit – Ergebnisse

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26
**Stand:** 2026-05-14
**SQL-Skripte:** `sql/08_data_quality_checks.sql` (Einzelchecks) · `sql/08b_dq_audit.sql` (konsolidierte Übersicht)

---

## 1. Methodik

Die Banana-Supply-Chain-Datenbank wurde gegen **26 Qualitätsregeln** in den **6 Dimensionen** nach DAMA-Standard geprüft. Jede Regel liefert eine Zahl `verstoesse` (Anzahl Datensätze, die die Regel verletzen) und einen Status (`PASS` = 0 Verstöße, `FAIL` = ≥ 1 Verstoß).

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
| 2.1 | Eindeutigkeit | `erp.suppliers` | supplier_code Duplikat | 0 | ✅ PASS |
| 2.2 | Eindeutigkeit | `erp.orders` | order_reference Duplikat | 0 | ✅ PASS |
| 2.3 | Eindeutigkeit | `erp.batches` | batch_identifier Duplikat | 0 | ✅ PASS |
| 2.4 | Eindeutigkeit | `tms.shipments` | shipment_identifier Duplikat | 0 | ✅ PASS |
| 3.1 | Konsistenz | `wms.warehouse_skus` | SKU ohne MDM-Mapping (über normalized_key) | 0 | ✅ PASS |
| 3.2 | Konsistenz | `tms.transport_product_references` | TMS-Referenz ohne MDM-Mapping (über normalized_key) | 0 | ✅ PASS |
| 3.3 | Konsistenz | `erp.batches` | wms_sku passt nicht zu product_code | 0 | ✅ PASS |
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
| 5.2 | Aktualität | `erp` | BatchHarvested vor OrderCreated | 0 | ✅ PASS |
| 5.3 | Aktualität | `erp.orders` | Order > 90 Tage ohne Delivery | 0 | ✅ PASS |
| 6.1 | Ref. Integrität | `wms.node_processings` | batch_reference ohne erp.batches | 0 | ✅ PASS |
| 6.2 | Ref. Integrität | `tms.shipments` | cargo_product_reference ohne tms.transport_product_references | 0 | ✅ PASS |
| 6.3 | Ref. Integrität | `tms.shipments` | Shipment ohne Carrier (carrier_id NULL) | 0 | ✅ PASS |

**Score:** 26 / 26 = **100 % PASS** über alle sechs Dimensionen.

---

## 3. Befunde nach Dimension

### 3.1 Vollständigkeit (4/4 PASS)
Alle Pflichtfelder sind gefüllt. Besonders bemerkenswert: `temperature` ist in **allen 60** `wms.node_processings`-Einträgen vorhanden — der Datengenerator simuliert eine lückenlose Kühlkettenüberwachung.

### 3.2 Eindeutigkeit (4/4 PASS)
Alle Business Keys (`supplier_code`, `order_reference`, `batch_identifier`, `shipment_identifier`) sind eindeutig. Das bestätigt, dass die in K1 behobenen Idempotenz-Bugs vollständig ausgeräumt sind.

### 3.3 Konsistenz (3/3 PASS)
**Wichtiger Hinweis zur ursprünglichen Implementation:** Die erste Version von Check 3.1/3.2 prüfte `wms.warehouse_skus.sku = mdm.source_mappings.source_key`. Das schlug fehl, weil das ETL die WMS-SKUs bereits beim Laden über `normalize_key()` auf das ERP-Format kanonisiert (`BAN_101` → `BAN-101`). Die korrigierte Variante joint über `normalized_key`, das stets im kanonischen Format vorliegt:

```sql
WHERE sm.source_system  = 'WMS'
  AND sm.normalized_key = LOWER(REPLACE(w.sku, '_', '-'))
```

Damit greift der Check auch dann, wenn das ETL die Schlüssel vorab normalisiert. Diese Korrektur wurde in `08_data_quality_checks.sql` und `08b_dq_audit.sql` umgesetzt.

### 3.4 Plausibilität (9/9 PASS)
Alle Wertebereiche werden eingehalten, insbesondere:
- Kühlkette: 0 Verstöße über 60 Knotenprozessierungen + 118 GPS-Updates
- GPS-Bereich: 0 Verstöße über 118 Positionen
- Verzögerungen: 60/60 Completions ≤ 180 min

### 3.5 Aktualität (3/3 PASS)
- Keine Transportabschlüsse vor Transportstart
- Keine Batches vor Bestellungen geerntet
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
| Anzahl Checks | 26 (über Mindestanforderung „2 pro Dimension" hinaus) |
| Funktionsnachweis | ✅ Sanity-Test zeigt korrekte FAIL-Detektion |
| Live-Audit-Ergebnis | 26/26 PASS = 100 % |
| Konsolidierte Übersicht | ✅ `sql/08b_dq_audit.sql` liefert Single-Result-Set |

---

## 6. Ausführungsanleitung

**Audit ausführen:**
```bash
docker exec -i postgres psql -U user -d logistics < sql/08b_dq_audit.sql
```

**Detail-Einzelchecks (mit zusätzlichen Spalten wie betroffenen IDs):**
```bash
docker exec -i postgres psql -U user -d logistics < sql/08_data_quality_checks.sql
```

**Erwartetes Ergebnis nach sauberem ETL-Lauf:** Alle 26 Checks PASS.
