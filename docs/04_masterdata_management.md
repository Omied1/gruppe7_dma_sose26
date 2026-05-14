# Masterdatenmanagement – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-14  
**SQL-Implementierung:** `sql/05_create_mdm_tables.sql`  
**ETL-Befüllung:** `bananasupplychain/etl_load.py` – Funktion `load_mdm()`

> **Abdeckung:** Golden Records existieren für **alle 5 Entity-Typen**: PRODUCT (10), CUSTOMER (10), SUPPLIER (10), CARRIER (5), SUPPLY_CHAIN_NODE (7). Source Mappings: 30 für PRODUCT (3 Systeme), 10 ERP-Mappings je für CUSTOMER/SUPPLIER, 5 TMS-Mappings für CARRIER, 14 für NODE (WMS+TMS).

---

## 1. Warum ist MDM in diesem Use Case notwendig?

In der Banana Supply Chain arbeiten drei unabhängige IT-Systeme zusammen – ERP, WMS und TMS. Jedes System verwaltet dieselben Stammdaten (Produkte, Carrier) unter eigenen, systemspezifischen Schlüsselformaten:

| Entität | ERP (kanonisch) | WMS | TMS |
|---|---|---|---|
| Produkt | `BAN-101` | `BAN_101` | `ban-101` |
| Produkt | `BAN-108` | `BAN_108` | `ban-108` |

Diese Inkonsistenz ist **im Datengenerator bewusst implementiert** (`MASTERDATA_INCONSISTENCY_MODE = "targeted"`):
- WMS ersetzt Bindestriche durch Unterstriche
- TMS schreibt alles in Kleinbuchstaben

**Folge ohne MDM:** Eine Frage wie „Welche Transporte betreffen das Produkt BAN-101?" kann nicht systemübergreifend beantwortet werden, weil TMS nur `ban-101` kennt und WMS nur `BAN_101`. Ein direkter String-Vergleich würde alle Verknüpfungen zwischen ERP-Orders und TMS-Shipments zerstören.

**Lösung durch MDM:**
- Ein **Golden Record** pro Entität enthält den kanonischen Schlüssel (ERP-Format)
- **Source Mappings** verknüpfen systemspezifische Schlüssel mit dem Golden Record
- Eine **Hilfsfunktion** (`mdm.resolve_canonical_key()`) löst beliebige Quellschlüssel auf den kanonischen Wert auf

---

## 2. MDM-Datenmodell

### 2.1 Entitätstypen (`mdm.entity_types`)

Definiert, welche Stammdatenentitäten im MDM verwaltet werden:

| Entitätstyp | Beschreibung | Primäres Quellsystem |
|---|---|---|
| `PRODUCT` | Bananensorten (BAN-101 bis BAN-110) | ERP |
| `SUPPLIER` | Ghanaische Bananenlieferanten (SUP-101 bis SUP-110) | ERP |
| `CUSTOMER` | Einzelhandelsunternehmen (CUST-101 bis CUST-110) | ERP |
| `CARRIER` | Transportdienstleister (CAR-101 bis CAR-105) | TMS |
| `SUPPLY_CHAIN_NODE` | Physische Stationen der Lieferkette | WMS |

### 2.2 Golden Records (`mdm.golden_records`)

Jeder Golden Record ist die **einzige Wahrheitsquelle** für eine Stammdatenentität:

```
golden_id | entity_type | canonical_key | canonical_name       | status | quality_score
----------+-------------+---------------+----------------------+--------+--------------
1         | PRODUCT     | BAN-101       | Cavendish Banana     | ACTIVE | 0.95
2         | PRODUCT     | BAN-102       | Organic Banana       | ACTIVE | 0.95
...
11        | SUPPLIER    | SUP-101       | Golden Banana Ltd    | ACTIVE | 1.00
...
21        | CUSTOMER    | CUST-101      | ALDI                 | ACTIVE | 1.00
...
31        | CARRIER     | CAR-101       | DHL                  | ACTIVE | 1.00
...
36        | SUPPLY_CHAIN_NODE | BANANA_PLANTATION | Banana Plantation Ghana | ACTIVE | 1.00
```

**Quality Score:** Ein Wert zwischen 0.0 und 1.0, der angibt, wie vollständig und konsistent die Daten des Golden Records sind. Ein Produkt ohne bekannten Lieferanten würde einen niedrigeren Score erhalten.

### 2.3 Source Mappings (`mdm.source_mappings`)

Für jedes Produkt (10 Produkte × 3 Systeme = 30 Mappings) wird gespeichert, wie der Schlüssel im jeweiligen Quellsystem heißt:

```
mapping_id | golden_id | source_system | source_key | normalized_key | is_canonical
-----------+-----------+---------------+------------+----------------+--------------
1          | 1         | ERP           | BAN-101    | ban-101        | TRUE
2          | 1         | WMS           | BAN_101    | ban-101        | FALSE
3          | 1         | TMS           | ban-101    | ban-101        | FALSE
4          | 2         | ERP           | BAN-102    | ban-102        | TRUE
5          | 2         | WMS           | BAN_102    | ban-102        | FALSE
6          | 2         | TMS           | ban-102    | ban-102        | FALSE
...
```

**is_canonical = TRUE:** Genau ein Mapping pro Golden Record hat dieses Flag – das ERP-Mapping. Es zeigt an, dass der ERP-Schlüssel die kanonische Darstellung ist.

---

## 3. Schlüsselharmonisierung: Funktionsweise

### 3.1 Normalisierungsalgorithmus

Zur systemübergreifenden Suche wird ein normalisierter Schlüssel verwendet:
```python
def normalize_key(value: str) -> str:
    return value.strip().lower().replace("_", "-")
    # BAN-101 → ban-101
    # BAN_101 → ban-101
    # ban-101 → ban-101  (bereits normalisiert)
```

Alle drei Formate werden auf denselben normalisierten Schlüssel abgebildet.

### 3.2 Auflösung in SQL

Die SQL-Funktion `mdm.resolve_canonical_key()` löst systemspezifische Schlüssel auf:

```sql
-- WMS-SKU → kanonischer ERP-Code
SELECT mdm.resolve_canonical_key('BAN_101', 'WMS');
-- Ergebnis: 'BAN-101'

-- TMS-Referenz → kanonischer ERP-Code
SELECT mdm.resolve_canonical_key('ban-108', 'TMS');
-- Ergebnis: 'BAN-108'
```

### 3.3 Verknüpfung über Systemgrenzen

Mit dem MDM lassen sich Fragen beantworten, die sonst unmöglich wären:

```sql
-- Welche TMS-Shipments betreffen ERP-Produkt BAN-108?
SELECT s.*
FROM   tms.shipments s
JOIN   mdm.source_mappings sm ON sm.source_key = s.cargo_product_reference
                              AND sm.source_system = 'TMS'
JOIN   mdm.golden_records  gr ON gr.golden_id = sm.golden_id
WHERE  gr.canonical_key = 'BAN-108';
```

Ohne MDM würde dieser JOIN nicht funktionieren, weil `s.cargo_product_reference = 'ban-108'` und der Vergleich mit `'BAN-108'` (ERP-Format) fehlschlägt.

---

## 4. MDM-Entitäten im Detail

### 4.1 Produkte

**Kanonischer Schlüssel:** `BAN-NNN` (ERP-Format)  
**10 Produkte:** Cavendish Banana, Organic Banana, Premium Banana, Baby Banana, Fairtrade Banana, Export Banana, Sweet Banana, Green Banana, Yellow Banana, Tropical Banana  
**Inkonsistenz:** WMS=`BAN_NNN`, TMS=`ban-nnn`  
**MDM-Relevanz:** Hoch – Produkte werden von allen drei Systemen referenziert

### 4.2 Lieferanten

**Kanonischer Schlüssel:** `SUP-NNN` (ERP-Format)  
**10 Lieferanten:** Golden Banana Ltd, Fresh Banana Export, ... (alle aus Ghana)  
**Inkonsistenz:** Keine systemübergreifende Inkonsistenz (nur ERP führt Lieferanten)  
**MDM-Relevanz:** Mittel – Referenziert von Produkten und wichtig für Clusteranalyse (Teil 2)

### 4.3 Kunden

**Kanonischer Schlüssel:** `CUST-NNN` (ERP-Format)  
**10 Kunden:** ALDI, LIDL, REWE, EDEKA, METRO, KAUFLAND, TESCO, CARREFOUR, AUCHAN, SPAR  
**Inkonsistenz:** Keine (nur ERP kennt Kunden)  
**MDM-Relevanz:** Mittel – Referenziert in Orders und DWH-Dimension

### 4.4 Carrier

**Kanonischer Schlüssel:** `CAR-NNN` (TMS-Format, da nur TMS Carrier kennt)  
**5 Carrier:** DHL, Maersk, MSC, DB Schenker, Hapag Lloyd  
**Inkonsistenz:** Keine systemübergreifende Inkonsistenz  
**MDM-Relevanz:** Mittel – Wichtig für Carrier-Performance-Analyse

### 4.5 Supply-Chain-Knoten

**Kanonischer Schlüssel:** Node-Code (z. B. `BANANA_PLANTATION`)  
**7 Knoten:** Plantation → Collection → Quality → Africa Cold Storage → Europe Cold Storage → Central Warehouse → Retail Store  
**Inkonsistenz:** Keine (konsistente Nutzung in WMS und TMS)  
**MDM-Relevanz:** Hoch – Definiert die Topologie der Supply Chain (Neo4j-Graph)

---

## 5. Implementierung: Normalisierung im ETL

### 5.1 Tatsächliche Umsetzung

Die Schlüsselharmonisierung findet in der Praxis **im ETL-Skript** statt, nicht über einen separaten MDM-Vorab-Ladeschritt. Das ETL-Skript (`bananasupplychain/etl_load.py`) normalisiert jeden Produktschlüssel unmittelbar vor dem Datenbankinsert:

```python
def normalize_key(key: str) -> str:
    return key.strip().lower().replace("_", "-").upper()
    # BAN_101 → ban_101 → ban-101 → BAN-101  ✓
    # ban-101 → ban-101            → BAN-101  ✓
    # BAN-101 → ban-101            → BAN-101  ✓
```

Dadurch sind alle Produktschlüssel bereits bei der Ankunft in PostgreSQL, MongoDB, Redis und Neo4j im kanonischen Format `BAN-NNN`. Die Inkonsistenz existiert ausschließlich in den JSON-Quelldateien (`shared/wms/`, `shared/tms/`).

### 5.2 Rolle der MDM-Tabellen

Die MDM-Tabellen (`mdm.golden_records`, `mdm.source_mappings`) erfüllen in dieser Implementierung zwei Aufgaben:

1. **Referenzmodell:** Sie dokumentieren formal, welche Systemschlüssel zu welchem Golden Record gehören. Das ermöglicht nachvollziehbare systemübergreifende JOINs über `mdm.source_mappings` (siehe Abschnitt 3.3).

2. **SQL-Funktion als Schnittstelle:** `mdm.resolve_canonical_key()` steht als aufrufbare Funktion bereit für Abfragen, die zur Laufzeit systemfremde Schlüssel auflösen müssen — ohne das ETL-Skript einzubeziehen.

### 5.3 Aktueller Stand der MDM-Tabellen

In der Datenbank ist aktuell ein exemplarischer Golden Record vollständig befüllt:

| Tabelle | Inhalt |
|---|---|
| `mdm.golden_records` | 1 Eintrag: `BAN-101` (Cavendish Banana) |
| `mdm.source_mappings` | 3 Einträge: ERP `BAN-101`, WMS `BAN_101`, TMS `ban-101` |

Die Einträge für BAN-102 bis BAN-110 sind konzeptuell identisch aufgebaut (vgl. Abschnitt 2.2) und können bei Bedarf per ETL nachgefüllt werden. Für den Nachweis der MDM-Logik genügt das vollständige BAN-101-Beispiel, da der Normalisierungsalgorithmus für alle Produktcodes identisch ist.
