# Datenqualitätsmanagement – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-15  
**SQL-Implementierung:** `sql/08_data_quality_checks.sql`

---

## 1. Datenqualitätsdimensionen

Für die Banana Supply Chain werden sechs Qualitätsdimensionen definiert und mit konkreten Regeln hinterlegt:

| Dimension | Frage | Relevanz für Banana Supply Chain |
|---|---|---|
| **Vollständigkeit** | Sind alle Pflichtfelder befüllt? | Fehlendes `temperature` = Kühlkette nicht dokumentiert |
| **Eindeutigkeit** | Gibt es keine Duplikate? | Doppelter `batch_identifier` = falsche Mengenbuchungen |
| **Konsistenz** | Stimmen systemübergreifende Werte überein? | WMS-SKU ohne MDM-Mapping = Produkt nicht zuordenbar |
| **Plausibilität** | Liegen Werte im gültigen Bereich? | Temperatur außerhalb 10-15°C = Kühlkettenbruch |
| **Aktualität** | Sind Zeitstempel logisch geordnet? | Ernte vor Bestellung = unmöglich, fachlicher Fehler |
| **Ref. Integrität** | Lassen sich FKs auflösen? | Batch-Referenz ohne ERP-Batch = Daten verloren |

---

## 2. Datenqualitätsregeln im Detail

### 2.1 Vollständigkeit (Completeness)

#### Regel VQ-01: Produkte müssen Lieferant haben
```sql
-- Fehler: erp.products.supplier_id IS NULL
-- Fachlich: Ohne Lieferant kann nicht nachverfolgt werden, wer die Bananen geliefert hat
-- Erwartung: 0 Verstösse (supplier_id ist NOT NULL im Schema)
```

#### Regel VQ-02: Bestellpositionen müssen Menge und Preis haben
```sql
-- Fehler: erp.order_items.quantity IS NULL OR unit_price IS NULL
-- Fachlich: Ohne Menge/Preis kann kein Rechnungswert berechnet werden
-- Erwartung: 0 Verstösse
```

#### Regel VQ-03: Knotenverarbeitungen sollen Temperatur haben (Kühlkette)
```sql
-- Fehler: wms.node_processings.temperature IS NULL
-- Fachlich: Für Kühlkettennachweise (HACCP) muss jede Station die Temperatur protokollieren
-- Erwartung: 0 Verstösse (Pflichtfeld in Produktion, nullable im Modell für Flexibilität)
```

#### Regel VQ-04: Empfänger bei erfolgreicher Lieferung
```sql
-- Fehler: tms.deliveries.received_by IS NULL WHERE delivery_status = 'SUCCESSFUL'
-- Fachlich: Jede erfolgreiche Lieferung muss einem Empfänger zugewiesen sein
-- Erwartung: 0 Verstösse
```

#### Regel VQ-05: Bestellungen ohne Positionen
```sql
-- Fehler: erp.orders ohne zugehörige erp.order_items
-- Fachlich: Eine Order ohne Bestellpositionen hat keinen Rechnungswert – kein valider Geschäftsvorfall
-- Erwartung: 0 Verstösse
```

---

### 2.2 Eindeutigkeit (Uniqueness)

#### Regel EQ-01: Eindeutige Business Keys
```
Tabelle              | Spalte              | Erwartung
---------------------|---------------------|----------
erp.suppliers        | supplier_code       | Kein Duplikat (UNIQUE-Constraint)
erp.customers        | customer_number     | Kein Duplikat (UNIQUE-Constraint)
erp.products         | product_code        | Kein Duplikat (UNIQUE-Constraint)
erp.orders           | order_reference     | Kein Duplikat (UNIQUE-Constraint)
erp.batches          | batch_identifier    | Kein Duplikat (UNIQUE-Constraint)
tms.shipments        | shipment_identifier | Kein Duplikat (UNIQUE-Constraint)
wms.warehouse_skus   | sku                 | Kein Duplikat (UNIQUE-Constraint)
tms.carriers         | carrier_code        | Kein Duplikat (UNIQUE-Constraint)
```

> Die UNIQUE-Constraints im Schema verhindern Duplikate auf DB-Ebene. SQL-Checks dienen der **retrospektiven Verifikation** (z. B. nach Migration oder manuellem Import).

---

### 2.3 Konsistenz (Consistency)

#### Regel KQ-01: WMS-SKUs müssen MDM-Mapping haben
```
Problem: WMS verwendet BAN_101, ERP verwendet BAN-101
Prüfung: Jede sku in wms.warehouse_skus muss als source_key in mdm.source_mappings (WMS) existieren
Grund: Ohne Mapping können WMS-Knotenverarbeitungen nicht mit ERP-Bestellungen verknüpft werden
```

#### Regel KQ-02: TMS-Produktreferenzen müssen MDM-Mapping haben
```
Problem: TMS verwendet ban-101, ERP verwendet BAN-101
Prüfung: Jede transport_product_reference muss als source_key in mdm.source_mappings (TMS) existieren
Grund: Ohne Mapping können TMS-Shipments nicht mit ERP-Produkten verknüpft werden
```

#### Regel KQ-03: Batch-WMS-SKU konsistent mit Produktcode
```
Problem: batch.wms_sku = "BAN_108" muss zu batch.product_code = "BAN-108" passen
Formel:  REPLACE(product_code, '-', '_') = wms_sku
Grund: Inkonsistenter Batch kann nicht korrekt durch das WMS verfolgt werden
```

#### Regel KQ-04: Erfolgreiche Delivery muss TransportCompleted haben
```
Problem: tms.deliveries.delivery_status = 'SUCCESSFUL' ohne Eintrag in tms.transport_completions
Prüfung: Für jede SUCCESSFUL-Delivery muss ein korrespondierender TransportCompleted-Datensatz existieren
Grund: DeliveryCompleted und TransportCompleted sind logisch abhängige Events – ohne Transportabschluss
       ist die Delivery-Buchung ein Nachweis-Waise
```

---

### 2.4 Plausibilität (Validity)

#### Regel PQ-01: Bestellmengen müssen positiv sein
```
Spalte:    erp.order_items.quantity
Regel:     quantity > 0 (CHECK-Constraint im Schema)
Bereich:   100 – 1000 Einheiten laut Datengenerator
Verstoß:   Menge ≤ 0 → ungültige Bestellung
```

#### Regel PQ-02: Preise im plausiblen Bereich
```
Spalte:    erp.order_items.unit_price
Regel:     unit_price BETWEEN 1.50 AND 5.00 EUR
Bereich:   Aus Datengenerator: uniform(1.5, 5.0) EUR
Verstoß:   Preis > 5.00 EUR → ungewöhnlich teuer für Bananen
           Preis < 1.50 EUR → unter Marktpreis, möglicher Fehler
```

#### Regel PQ-03: Kühlkette (kritisch!)
```
Spalten:   wms.node_processings.temperature
           tms.shipment_positions.container_temperature
Regel:     temperature BETWEEN 10.0 AND 15.0°C
Grund:     Bananen werden bei 13°C ±2°C transportiert (Standard-Kühlkette)
           Zu kalt: Kälteschaden, Reifehemmung
           Zu warm: Überreife, Verderb
Verstoß:   Qualitätsproblem → Charge ggf. nicht verkehrsfähig
```

#### Regel PQ-04: Transportverzögerungen im erwarteten Bereich
```
Spalte:    tms.transport_completions.delay_minutes
Regel:     delay_minutes BETWEEN 0 AND 180 Min
Bereich:   Aus Datengenerator: randint(0, 180) Minuten
Verstoß:   delay_minutes > 180 → außerhalb erwarteter Domäne
           delay_minutes < 0  → unmöglich (CHECK-Constraint)
```

#### Regel PQ-05: GPS-Koordinaten im Wertebereich
```
Spalte:    tms.shipment_positions.latitude / longitude
Regel:     latitude BETWEEN -90 AND 90
           longitude BETWEEN -180 AND 180
Verstoß:   Ungültige WGS84-Koordinaten (z.B. latitude = 999.0)
           CHECK-Constraints im Schema verhindern dies bereits
```

#### Regel PQ-06: Gültige Status-Werte
```
Spalten:   erp.orders.delivery_priority → CHECK IN ('HIGH', 'NORMAL', 'LOW')
           wms.node_processings.status  → CHECK IN ('COMPLETED', 'PENDING', 'FAILED')
           tms.deliveries.delivery_status → CHECK IN ('SUCCESSFUL', 'DELAYED', 'FAILED')
           tms.shipments.transport_mode   → CHECK IN ('TRUCK', 'SEA_FREIGHT')
```

---

### 2.5 Aktualität (Timeliness)

#### Regel AQ-01: Erntezeitpunkt innerhalb der Projektlaufzeit
```
Logik:     erp.batches.harvested_at BETWEEN '2026-01-01' AND NOW() + INTERVAL '1 day'
Grund:     BatchHarvested-Events enthalten keine Bestellreferenz (kein order_id-FK in erp.batches).
           Der direkte Vergleich harvested_at < order_timestamp ist daher nicht umsetzbar.
           Stattdessen: Plausibilitätsprüfung des Erntezeitpunkts gegen Projektlaufzeit 2026.
Verstoß:   Datum vor 2026 → vermutlich fehlerhafter Datengenerator oder Timezone-Problem beim ETL
           Datum in der Zukunft → unmöglich, Systemuhren-Problem
```

#### Regel AQ-02: Transportabschluss nach Transportstart
```
Logik:     tms.transport_completions.completed_at >= tms.shipments.started_at
Grund:     Ein Transport kann nicht abgeschlossen werden, bevor er begonnen hat
Verstoß:   Datumsfehler im Event-Stream
```

#### Regel AQ-03: Keine verwaisten offenen Bestellungen
```
Logik:     Orders > 90 Tage ohne zugehörige Delivery
Grund:     Jede Bestellung sollte innerhalb von ~90 Tagen geliefert werden
           (Seefracht Afrika→Europa: ~10-14 Tage, Gesamtprozess: ~21 Tage)
Aktion:    Manuelle Prüfung, ob Order storniert oder im Prozess hängen geblieben
```

---

### 2.6 Referenzielle Integrität (Referential Integrity)

#### Regel RI-01: WMS Batch-Referenzen auflösbar
```
Cross-Schema: wms.node_processings.batch_reference → erp.batches.batch_identifier
Kein DB-FK (Cross-Schema), daher via ETL-Prüfung
Verstoß: Knotenverarbeitung für unbekannten Batch → Daten nicht zuordenbar
```

#### Regel RI-02: TMS Cargo-Referenzen auflösbar
```
Prüfung: tms.shipments.cargo_product_reference → tms.transport_product_references
Verstoß: Shipment mit unbekanntem Produkt → MDM-Mapping fehlt
```

---

## 3. Datenqualitäts-Dashboard (konzeptuell)

Ein einfaches DQ-Monitoring führt die SQL-Checks regelmäßig aus und speichert die Ergebnisse.
Konsolidierte Ausführung: `docker exec -i postgres psql -U user -d logistics < sql/08b_dq_audit.sql`

```
DQ-Dimension     | Regeln | Verstösse (nach ETL) | Status
-----------------|--------|----------------------|--------
Vollständigkeit  |   5    | 0                    | PASS
Eindeutigkeit    |   4    | 0                    | PASS
Konsistenz       |   4    | 0                    | PASS
Plausibilität    |   9    | 0                    | PASS
Aktualität       |   3    | 0                    | PASS
Ref. Integrität  |   3    | 0                    | PASS
─────────────────────────────────────────────────────────
Gesamt           |  28    | 0                    | 100 %
```

Detailanzeige mit FAIL-Hervorhebung und fachlicher Interpretation: `docs/13_data_quality_results.md`

---

## 4. Qualitätsregel-Implementierung in Python (ETL-Phase)

Neben SQL-Checks lassen sich Qualitätsregeln auch im ETL-Prozess implementieren:

```python
def validate_temperature(temp: float, context: str) -> bool:
    """Kühlketten-Validierung: 10.0 – 15.0°C"""
    if temp is None:
        return False  # VQ-03: Vollständigkeit
    if not (10.0 <= temp <= 15.0):
        print(f"[DQ-WARNUNG] {context}: Temperatur {temp}°C außerhalb Kühlkette [10-15°C]")
        return False  # PQ-03: Plausibilität
    return True

def validate_product_code_format(code: str, system: str) -> bool:
    """Produktcode-Format je nach Quellsystem"""
    if system == 'ERP':
        return bool(__import__('re').match(r'^BAN-\d{3}$', code))
    if system == 'WMS':
        return bool(__import__('re').match(r'^BAN_\d{3}$', code))
    if system == 'TMS':
        return bool(__import__('re').match(r'^ban-\d{3}$', code))
    return False

def validate_order_quantity(qty: int) -> bool:
    """Bestellmenge: 100 – 1000 Einheiten"""
    return isinstance(qty, int) and 100 <= qty <= 1000
```

Diese Funktionen werden im ETL-Prozess (siehe `docs/12_etl_concept.md`) vor dem Load-Schritt ausgeführt. Daten, die gegen kritische Regeln verstoßen (Kühlkette, Duplikate), werden in eine **Quarantäne-Tabelle** verschoben und manuell geprüft.
