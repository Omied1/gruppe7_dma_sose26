# Metadatenmanagement – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-12  
**SQL-Implementierung:** `sql/06_create_metadata_tables.sql`

---

## 1. Zweck des Metadatenmanagements

Metadatenmanagement dokumentiert **Daten über Daten** – es beantwortet Fragen wie:
- Woher kommt diese Spalte?
- Was bedeutet dieser Wert?
- Welches Skalenniveau hat dieses Attribut?
- Welche Qualitätsregel gilt für diesen Wert?

In der Banana Supply Chain ist Metadatenmanagement besonders relevant, weil:
1. Drei Quellsysteme (ERP, WMS, TMS) unterschiedliche Namenskonventionen verwenden
2. Analystenteams und BI-Tools einen Datenkatalog benötigen
3. Skalenniveaus die Wahl der korrekten Analysemethoden bestimmen
4. Qualitätsregeln ohne Dokumentation nicht wiederholbar validiert werden können

---

## 2. Datenmodell

### 2.1 Drei-Ebenen-Hierarchie

```
meta.systems    (1 System)
  └── meta.tables  (N Tabellen pro System)
        └── meta.columns  (M Spalten pro Tabelle)
```

### 2.2 Registrierte Systeme

| System-Code | System-Name | Beschreibung |
|---|---|---|
| `ERP` | Enterprise Resource Planning | Stamm- und Bewegungsdaten |
| `WMS` | Warehouse Management System | Lagerverwaltung |
| `TMS` | Transport Management System | Transportverwaltung |
| `MDM` | Master Data Management | Stammdatenharmonisierung |
| `META` | Metadatenmanagement | Datenkatalog (self-referenziell) |
| `DWH` | Data Warehouse | Analytisches Schema (ETL-getrieben) |

---

## 3. Skalenniveaus nach Stevens (1946)

Das Skalenniveau ist eine der wichtigsten Metadateneigenschaften, weil es bestimmt, **welche statistischen Operationen** auf einem Attribut sinnvoll sind.

| Skalenniveau | Eigenschaft | Beispiele aus der Supply Chain | Erlaubte Operationen |
|---|---|---|---|
| **NOMINAL** | Kategorien ohne Reihenfolge | `delivery_status`, `product_code`, `supplier_name`, `transport_mode`, `node_code` | Häufigkeit, Modus, Chi-Quadrat |
| **ORDINAL** | Kategorien mit Reihenfolge | `delivery_priority` (LOW < NORMAL < HIGH) | Median, Rang, nichtparametrische Tests |
| **INTERVAL** | Numerisch, gleichmäßige Abstände, kein natürlicher Nullpunkt | `temperature` (°C), `timestamp`, `latitude`, `longitude` | Mittelwert, Standardabweichung, Differenzen |
| **RATIO** | Numerisch mit natürlichem Nullpunkt (0 = Nichts) | `quantity`, `unit_price`, `delay_minutes`, `speed_kmh` | Alle Operationen inkl. Verhältnisse |

### Begründung zentraler Skalenniveaus

**`delivery_priority` → ORDINAL:**  
Die Werte HIGH, NORMAL, LOW haben eine klare Reihenfolge (HIGH > NORMAL > LOW), aber der Abstand zwischen den Stufen ist nicht gleichmäßig definiert. Daher ordinal, nicht interval.

**`temperature` (°C) → INTERVAL:**  
Temperatur in Celsius hat keinen natürlichen Nullpunkt (0°C ist nicht „keine Temperatur"). Das Verhältnis 20°C/10°C = 2 ist nicht sinnvoll interpretierbar. Daher interval. (Kelvin wäre ratio.)

**`delay_minutes` → RATIO:**  
0 Minuten Verzögerung bedeutet tatsächlich „keine Verzögerung". Das Verhältnis 60/30 = „doppelte Verzögerung" ist sinnvoll. Daher ratio.

**`latitude` / `longitude` → INTERVAL:**  
Geografische Koordinaten (WGS84) haben keinen natürlichen Nullpunkt für Verhältnisaussagen. 0°/0° ist ein willkürlicher Punkt im Golf von Guinea, nicht „keine Position". Daher interval.

**`product_code`, `supplier_code` → NOMINAL:**  
Business Keys wie `BAN-101` sind Bezeichner ohne inhärente Reihenfolge oder numerischen Wert. Alphabetische Sortierung hat keine fachliche Bedeutung.

---

## 4. Exemplarische Metadaten-Einträge

### 4.1 Tabelle `erp.orders`

| Spalte | Datentyp | Skalenniveau | Datenart | Qualitätsregel |
|---|---|---|---|---|
| `order_id` | SERIAL | NOMINAL | Metadaten | Eindeutig, auto-generiert |
| `order_reference` | VARCHAR(60) | NOMINAL | Bewegungsdaten | Format: ORD-\<uuid\>. Eindeutig. |
| `customer_id` | INT | NOMINAL | Bewegungsdaten | FK auf erp.customers. Pflichtfeld. |
| `delivery_priority` | VARCHAR(10) | **ORDINAL** | Bewegungsdaten | Erlaubt: HIGH > NORMAL > LOW |
| `order_timestamp` | TIMESTAMP | INTERVAL | Bewegungsdaten | Nicht in der Zukunft |

### 4.2 Tabelle `wms.node_processings`

| Spalte | Datentyp | Skalenniveau | Datenart | Qualitätsregel |
|---|---|---|---|---|
| `node_id` | INT | NOMINAL | Bewegungsdaten | FK auf wms.supply_chain_nodes |
| `batch_reference` | VARCHAR(60) | NOMINAL | Bewegungsdaten | Format: BATCH-\<uuid\>. Cross-Schema-Check |
| `sku` | VARCHAR(20) | NOMINAL | Bewegungsdaten | Format: BAN_NNN. MDM-Mapping erforderlich |
| `temperature` | NUMERIC(5,2) | **INTERVAL** | Bewegungsdaten | Kühlkette: 10.0 – 15.0°C |
| `status` | VARCHAR(20) | NOMINAL | Eventdaten | Erlaubt: COMPLETED, PENDING, FAILED |

### 4.3 Tabelle `tms.shipment_positions`

| Spalte | Datentyp | Skalenniveau | Datenart | Qualitätsregel |
|---|---|---|---|---|
| `latitude` | NUMERIC(9,6) | **INTERVAL** | Echtzeitdaten | -90.0 bis 90.0 |
| `longitude` | NUMERIC(9,6) | **INTERVAL** | Echtzeitdaten | -180.0 bis 180.0 |
| `container_temperature` | NUMERIC(5,2) | **INTERVAL** | Echtzeitdaten | Kühlkette: 10.0 – 15.0°C |
| `speed_kmh` | NUMERIC(6,2) | **RATIO** | Echtzeitdaten | 0 – 120 km/h |

### 4.4 Tabelle `tms.deliveries`

| Spalte | Datentyp | Skalenniveau | Datenart | Qualitätsregel |
|---|---|---|---|---|
| `delivery_status` | VARCHAR(20) | **NOMINAL** | Eventdaten | Erlaubt: SUCCESSFUL, DELAYED, FAILED |
| `received_by` | VARCHAR(20) | NOMINAL | Eventdaten | Format: EMP-NNN |
| `delivered_at` | TIMESTAMP | INTERVAL | Eventdaten | Muss nach started_at des Shipments liegen |

---

## 5. Nutzung des Metadatenkatalogs

### Abfragen im Betrieb

```sql
-- Alle Spalten mit INTERVAL-Skalenniveau (für statistische Auswertungen)
SELECT t.schema_name, t.table_name, c.column_name, c.data_type, c.description
FROM   meta.columns  c
JOIN   meta.tables   t ON t.table_id = c.table_id
WHERE  c.scale_level = 'INTERVAL'
ORDER  BY t.schema_name, t.table_name;

-- Alle Qualitätsregeln für ein bestimmtes Schema
SELECT t.table_name, c.column_name, c.quality_rule
FROM   meta.columns c
JOIN   meta.tables  t ON t.table_id = c.table_id
WHERE  t.schema_name = 'tms'
AND    c.quality_rule IS NOT NULL
ORDER  BY t.table_name, c.column_name;

-- Alle Spalten mit Echtzeitdaten
SELECT t.schema_name, t.table_name, c.column_name
FROM   meta.columns c
JOIN   meta.tables  t ON t.table_id = c.table_id
WHERE  c.data_category = 'ECHTZEITDATEN';
```

---

## 6. Skalenniveau-Übersicht aller Schlüsselspalten

| Schema | Tabelle | Spalte | Skalenniveau | Begründung |
|---|---|---|---|---|
| erp | suppliers | country | NOMINAL | Ländername ohne Reihenfolge |
| erp | orders | delivery_priority | ORDINAL | HIGH > NORMAL > LOW |
| erp | orders | order_timestamp | INTERVAL | Zeitpunkt, kein natürlicher Nullpunkt |
| erp | order_items | quantity | RATIO | 0 = keine Menge (nat. Nullpunkt) |
| erp | order_items | unit_price | RATIO | 0 = kein Preis (nat. Nullpunkt) |
| wms | node_processings | temperature | INTERVAL | °C ohne nat. Nullpunkt |
| wms | node_processings | status | NOMINAL | Kategorien ohne Reihenfolge |
| tms | shipments | transport_mode | NOMINAL | TRUCK/SEA_FREIGHT ohne Reihenfolge |
| tms | shipment_positions | latitude | INTERVAL | WGS84, kein nat. Nullpunkt |
| tms | shipment_positions | speed_kmh | RATIO | 0 = stehendes Fahrzeug |
| tms | transport_completions | delay_minutes | RATIO | 0 = keine Verzögerung |
| tms | deliveries | delivery_status | NOMINAL | Kategorien ohne Reihenfolge |
