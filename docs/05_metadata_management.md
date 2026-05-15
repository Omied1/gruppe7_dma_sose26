# Metadatenmanagement – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-14  
**SQL-Implementierung:** `sql/06_create_metadata_tables.sql` (Grundstruktur) + `sql/06b_metadata_complete.sql` (Vollabdeckung)

> **Vollständigkeitsnachweis:** Alle Spalten der SQL-Datenbank (ERP, WMS, TMS, MDM, DWH) sind in `meta.columns` mit Skalenniveau klassifiziert. `06_create_metadata_tables.sql` liefert die explizit dokumentierten Kernspalten; `06b_metadata_complete.sql` ergänzt alle verbleibenden Spalten dynamisch via `information_schema`. Verteilung exemplarisch: NOMINAL (Codes, IDs, Status, Namen) · INTERVAL (Temperaturen, Zeitstempel, Koordinaten) · RATIO (Mengen, Preise, Verzögerungsminuten) · ORDINAL (delivery_priority, Datumsbestandteile).

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
| `delivery_id` | SERIAL | NOMINAL | Metadaten | Eindeutig, auto-generiert |
| `shipment_id` | INT | NOMINAL | Eventdaten | FK auf tms.shipments. Eindeutig (1 Delivery pro Shipment) |
| `supply_chain_node` | VARCHAR(50) | NOMINAL | Eventdaten | Wert: RETAIL_STORE (Standardfall) |
| `delivery_status` | VARCHAR(20) | **NOMINAL** | Eventdaten | Erlaubt: SUCCESSFUL, DELAYED, FAILED. Haupt-KPI Liefertreue |
| `received_by` | VARCHAR(20) | NOMINAL | Eventdaten | Format: EMP-NNN. Nullable, Pflicht bei SUCCESSFUL |
| `cargo_product_reference` | VARCHAR(30) | NOMINAL | Eventdaten | Format: ban-nnn. MDM-Mapping zu BAN-NNN erforderlich |
| `delivered_at` | TIMESTAMP | **INTERVAL** | Eventdaten | Nicht in der Zukunft. Muss nach shipments.started_at liegen |

### 4.5 Tabelle `erp.customers`

| Spalte | Datentyp | Skalenniveau | Datenart | Qualitätsregel |
|---|---|---|---|---|
| `customer_id` | SERIAL | NOMINAL | Metadaten | Eindeutig, auto-generiert |
| `customer_number` | VARCHAR(20) | **NOMINAL** | Stammdaten | Format: CUST-NNN. Eindeutig. Keine inhärente Reihenfolge |
| `customer_name` | VARCHAR(100) | NOMINAL | Stammdaten | Nicht leer. Bekannte Werte: ALDI, LIDL, REWE, Carrefour, Tesco |
| `city` | VARCHAR(50) | NOMINAL | Stammdaten | Nullable. Stadtname ohne Reihenfolge |
| `country` | VARCHAR(50) | NOMINAL | Stammdaten | ISO-Ländername. Europäische Märkte. Pflichtfeld |
| `event_timestamp` | TIMESTAMP | **INTERVAL** | Metadaten | Nicht in der Zukunft. Zeitstempel ohne natürlichen Nullpunkt |

### 4.6 Tabelle `erp.batches`

| Spalte | Datentyp | Skalenniveau | Datenart | Qualitätsregel |
|---|---|---|---|---|
| `batch_id` | SERIAL | NOMINAL | Metadaten | Eindeutig, auto-generiert |
| `batch_identifier` | VARCHAR(60) | NOMINAL | Bewegungsdaten | Format: BATCH-\<uuid\>. Verbindet ERP-Batch mit WMS-NodeProcessed |
| `product_id` | INT | NOMINAL | Bewegungsdaten | FK auf erp.products. Pflichtfeld |
| `origin_country` | VARCHAR(50) | NOMINAL | Bewegungsdaten | Z.B. Ghana, Ecuador. ISO-Ländername. NOMINAL: keine Reihenfolge |
| `quantity` | INT | **RATIO** | Bewegungsdaten | > 0 (CHECK). 0 = kein Batch. Verhältnis 400/200 = doppeltes Volumen |
| `wms_sku` | VARCHAR(30) | NOMINAL | Bewegungsdaten | Format: BAN_NNN (Unterstriche). Nullable |
| `tms_product_reference` | VARCHAR(30) | NOMINAL | Bewegungsdaten | Format: ban-nnn (Kleinbuchstaben). Nullable |
| `harvested_at` | TIMESTAMP | **INTERVAL** | Bewegungsdaten | Nicht in der Zukunft. Erntezeitpunkt = event_timestamp |

### 4.7 Tabelle `wms.supply_chain_nodes`

| Spalte | Datentyp | Skalenniveau | Datenart | Qualitätsregel |
|---|---|---|---|---|
| `node_id` | SERIAL | NOMINAL | Metadaten | Eindeutig, auto-generiert |
| `node_code` | VARCHAR(50) | NOMINAL | Stammdaten | Erlaubt: BANANA_PLANTATION bis RETAIL_STORE. CHECK-Constraint |
| `node_type` | VARCHAR(30) | NOMINAL | Stammdaten | Erlaubt: PLANTATION, COLLECTION_CENTER, QUALITY_CONTROL, COLD_STORAGE, WAREHOUSE, RETAIL |
| `region` | VARCHAR(50) | NOMINAL | Stammdaten | Erlaubt: Africa, Europe. Nullable |
| `sequence_order` | INT | **RATIO** | Stammdaten | 1 (Plantation) – 7 (Retail). 0 = kein Knoten. Abstände gleichmäßig |

### 4.8 Tabelle `dwh.fact_fulfillment` (Faktentabelle)

| Spalte | Datentyp | Skalenniveau | Datenart | Qualitätsregel |
|---|---|---|---|---|
| `fulfillment_sk` | SERIAL | NOMINAL | Analytik | Surrogate Key. Eindeutig, auto-generiert |
| `quantity` | INT | **RATIO** | Analytik | > 0. Basismaß für Volumenanalysen |
| `unit_price` | NUMERIC(10,2) | **RATIO** | Analytik | > 0 EUR. 2 Dezimalstellen. Plausibel: 1.50 – 5.00 EUR |
| `total_value` | NUMERIC(12,2) | **RATIO** | Analytik | = quantity × unit_price. Berechnete Kennzahl. > 0 |
| `delay_minutes` | INT | **RATIO** | Analytik | >= 0 (CHECK). 0 = pünktlich. > 30 min = SLA-Verletzung |
| `avg_temperature` | NUMERIC(5,2) | **INTERVAL** | Analytik | Soll 10–15°C. °C ohne natürlichen Nullpunkt → INTERVAL (nicht RATIO) |
| `num_supply_chain_hops` | INT | **RATIO** | Analytik | Standard: 6. 0 = kein Transport. Abweichungen = Prozessänderung |
| `delivery_priority_code` | VARCHAR(10) | **ORDINAL** | Analytik | HIGH > NORMAL > LOW. Ungleiche Abstände → ORDINAL (nicht INTERVAL) |

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

Die drei explizit in der Aufgabenstellung geforderten Spalten sind **fett** markiert.

| Schema | Tabelle | Spalte | Skalenniveau | Begründung |
|---|---|---|---|---|
| erp | suppliers | supplier_code | NOMINAL | Business Key BAN-NNN; alphabetische Sortierung hat keine fachliche Bedeutung |
| erp | suppliers | country | NOMINAL | Ländername ohne Reihenfolge (Ghana ≠ > Ecuador) |
| erp | customers | customer_number | NOMINAL | Business Key CUST-NNN; kein numerischer Wert |
| erp | customers | city | NOMINAL | Stadtname; keine inhärente Reihenfolge |
| erp | customers | country | NOMINAL | ISO-Ländername; Europa-Märkte ohne Reihenfolge |
| erp | products | product_code | NOMINAL | Business Key BAN-101; alphabetisch ohne fachliche Bedeutung |
| erp | products | category | NOMINAL | Z.B. „Fresh Fruit"; Kategorien ohne Reihenfolge |
| erp | orders | order_reference | NOMINAL | UUID-basierter Key ORD-\<uuid\>; kein numerischer Wert |
| erp | orders | **delivery_priority** | **ORDINAL** | HIGH > NORMAL > LOW – klare Reihenfolge, aber Abstände nicht gleichmäßig |
| erp | orders | order_timestamp | INTERVAL | Zeitstempel; 0 = 1970-01-01 00:00 (willkürlich), kein nat. Nullpunkt |
| erp | order_items | quantity | RATIO | 0 = keine Menge; Verhältnis 400/200 = doppeltes Volumen sinnvoll |
| erp | order_items | unit_price | RATIO | 0 = kein Preis; Verhältnis 4.00/2.00 EUR interpretierbar |
| erp | batches | batch_identifier | NOMINAL | UUID-basierter Key BATCH-\<uuid\>; Bezeichner ohne Wert |
| erp | batches | origin_country | NOMINAL | Ernteherkunft (Ghana, Ecuador); keine Reihenfolge |
| erp | batches | quantity | RATIO | 0 = keine Ernte; Verhältnisse sinnvoll |
| erp | batches | harvested_at | INTERVAL | Erntezeitpunkt; kein natürlicher Nullpunkt |
| wms | warehouse_skus | sku | NOMINAL | WMS-Format BAN_101; Bezeichner ohne Wert |
| wms | warehouse_skus | erp_product_code | NOMINAL | Cross-Referenz BAN-101; NOMINAL wie alle Business Keys |
| wms | supply_chain_nodes | node_code | NOMINAL | BANANA_PLANTATION etc.; Bezeichner ohne numerischen Wert |
| wms | supply_chain_nodes | node_type | NOMINAL | PLANTATION/WAREHOUSE/RETAIL etc.; keine inhärente Reihenfolge |
| wms | supply_chain_nodes | sequence_order | RATIO | 1–7 = Position im Flow; 0 = vor der Supply Chain; Abstände gleichmäßig |
| wms | node_processings | sku | NOMINAL | WMS-SKU BAN_NNN; Bezeichner ohne Wert |
| wms | node_processings | **temperature** | **INTERVAL** | °C hat keinen natürlichen Nullpunkt; 0°C ≠ „keine Temperatur"; 20°C/10°C = 2 ist bedeutungslos |
| wms | node_processings | status | NOMINAL | COMPLETED/PENDING/FAILED; keine inhärente Reihenfolge |
| tms | carriers | carrier_code | NOMINAL | Business Key CAR-101; kein numerischer Wert |
| tms | transport_product_references | transport_product_reference | NOMINAL | TMS-Format ban-101; Bezeichner |
| tms | shipments | shipment_identifier | NOMINAL | SHIP-\<uuid\>; Bezeichner |
| tms | shipments | transport_mode | NOMINAL | TRUCK/SEA_FREIGHT; keine Reihenfolge |
| tms | shipments | cargo_product_reference | NOMINAL | TMS-Format ban-nnn; Bezeichner |
| tms | shipments | estimated_arrival | INTERVAL | Geplante Ankunft; Zeitstempel ohne natürlichen Nullpunkt |
| tms | shipment_positions | latitude | INTERVAL | WGS84 -90 bis 90; 0° = Golf von Guinea (willkürlich), kein nat. Nullpunkt |
| tms | shipment_positions | longitude | INTERVAL | WGS84 -180 bis 180; 0° = Greenwich Meridian (willkürlich) |
| tms | shipment_positions | container_temperature | INTERVAL | °C ohne natürlichen Nullpunkt (wie wms.node_processings.temperature) |
| tms | shipment_positions | speed_kmh | RATIO | 0 km/h = stehendes Fahrzeug; Verhältnis 100/50 = doppelte Geschwindigkeit |
| tms | transport_completions | arrival_node | NOMINAL | Knotencode z.B. RETAIL_STORE; Bezeichner ohne Wert |
| tms | transport_completions | **delay_minutes** | **RATIO** | 0 min = pünktlich (natürlicher Nullpunkt); 60/30 = doppelte Verzögerung sinnvoll |
| tms | transport_completions | completed_at | INTERVAL | Abschlusszeitpunkt; kein natürlicher Nullpunkt |
| tms | deliveries | supply_chain_node | NOMINAL | RETAIL_STORE; Knotenbezeichner |
| tms | deliveries | delivery_status | NOMINAL | SUCCESSFUL/DELAYED/FAILED; Kategorien ohne Reihenfolge |
| tms | deliveries | received_by | NOMINAL | EMP-NNN; Mitarbeiterbezeichner ohne Wert |
| tms | deliveries | cargo_product_reference | NOMINAL | TMS-Format ban-nnn; Bezeichner |
| tms | deliveries | delivered_at | INTERVAL | Lieferzeitpunkt; kein natürlicher Nullpunkt |
| dwh | fact_fulfillment | quantity | RATIO | Bestellmenge; 0 = keine Menge |
| dwh | fact_fulfillment | unit_price | RATIO | Einzelpreis EUR; 0 = kostenlos |
| dwh | fact_fulfillment | total_value | RATIO | Umsatz EUR; 0 = kein Umsatz |
| dwh | fact_fulfillment | delay_minutes | RATIO | 0 = pünktlich; Verhältnisse sinnvoll |
| dwh | fact_fulfillment | avg_temperature | INTERVAL | °C ohne natürlichen Nullpunkt – INTERVAL, nicht RATIO (Kelvin wäre RATIO) |
| dwh | fact_fulfillment | num_supply_chain_hops | RATIO | 0 = kein Transport; 6/3 = doppelt so viele Stationen |
| dwh | fact_fulfillment | delivery_priority_code | ORDINAL | HIGH > NORMAL > LOW; ungleiche Abstände → ORDINAL, nicht INTERVAL |
| dwh | dim_date | year | ORDINAL | 2025 < 2026 < 2027; Abstände zwar gleich, aber als Datumsteil geordnet |
| dwh | dim_date | quarter | ORDINAL | Q1 < Q2 < Q3 < Q4; geordnet, aber kein ratio-sinnvoller Nullpunkt |
| dwh | dim_date | month | ORDINAL | 1–12; geordnet, aber kein ratio-sinnvoller Nullpunkt |
| dwh | dim_date | is_weekend | NOMINAL | TRUE/FALSE; boolescher Indikator ohne Reihenfolge |
