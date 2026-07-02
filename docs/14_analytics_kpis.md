# Teil 2 – Analytics: KPIs und deskriptive Statistik

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26 – TH Lübeck
**Gruppe:** 7

Dieses Dokument deckt die Teil-2-Aufgaben **A-2 (KPI-Definition)** und
**A-1 (deskriptive Statistik)** ab. Alle Kennzahlen stammen aus dem
DWH-Sternschema (`dwh.*`), Grain = **1 Zeile je Endlieferung** in
`dwh.fact_fulfillment` (**252 Zeilen, 10 Kunden, 13 Monate**, Zeitraum
2025-06-17 bis 2026-06-14).

- SQL-Nachweis: [`sql/10_kpi_queries.sql`](../sql/10_kpi_queries.sql) (gegen die laufende DB ausführbar)
- Python-Nachweis deskriptive Statistik: [`analytics/descriptive_stats.py`](../analytics/descriptive_stats.py) → `analytics/descriptive_stats.txt`

---

## 1. KPI-Katalog

Fünf Business-KPIs plus ein Ursachen-KPI. Jeder KPI: **Name · Formel ·
Datenquelle · Zielwert · Ist-Wert**. Die vorberechnete View
`dwh.v_kpi_summary` liefert die Fulfillment-Kernwerte; Transportdauer und
Batchqualitätsrate werden in `sql/10_kpi_queries.sql` separat aus
`dim_date` bzw. `erp.batches`/`dwh.v_batch_quality` berechnet.

| # | KPI | Formel | Datenquelle | Zielwert | Ist-Wert | Status |
|---|-----|--------|-------------|----------|----------|--------|
| 1 | **Liefertreue (OTD-Rate)** | `100 * COUNT(on_time_flag) / COUNT(*)` | `fact_fulfillment.on_time_flag` (TRUE = `delay_minutes` ≤ 60) | ≥ 95 % | **96,8 %** | ✅ erfüllt |
| 2 | **Ø Transportdauer** | `AVG(delivery_date − order_date)` | `fact_fulfillment` → `dim_date` (order/delivery) | ≤ 18 Tage | **14,92 Tage** (Median 15) | ✅ erfüllt |
| 3 | **Temperaturausreißer-Quote** | `100 * COUNT(temp ∉ [10;15]) / COUNT(*)` | `fact_fulfillment.avg_temperature` | ≤ 10 % | **7,9 %** (20/252) | ✅ erfüllt |
| 4 | **Ø Bestellwert** | `AVG(total_value)` | `fact_fulfillment.total_value` (= `quantity × unit_price`) | ≥ 1.000 € | **1.289,72 €** | ✅ erfüllt |
| 5 | **Batchqualitätsrate** | `100 * COUNT(quality_status='OK') / COUNT(*)` | `erp.batches.quality_status` / `dwh.v_batch_quality` | ≥ 40 % OK | **36,5 %** OK | ⚠️ knapp verfehlt |
| + | **Gesamtumsatz** | `SUM(total_value)` | `fact_fulfillment.total_value` | – (Monitoring) | **325.008,80 €** | – |

**Zielwerte** sind aus dem Supply-Chain-Kontext abgeleitet, nicht extern
vorgegeben (`[ANNAHME]`): 95 % Liefertreue ist ein branchenüblicher
Logistik-SLA; 18 Tage decken Seefracht Ghana → Rotterdam (~15 Tage) plus
Landverteilung; 10 % Temperaturtoleranz und 40 % OK-Batchrate ergeben sich
aus dem generierten Kühlkettenbruch-Niveau (`COLD_CHAIN_BREAK_RATE = 0,15`).

### 1.1 KPI-Details und Interpretation

**KPI 1 – Liefertreue 96,8 %.** Von 252 Endlieferungen sind 244 innerhalb
des 60-Minuten-SLA. Aufschlüsselung je Carrier (View `v_carrier_performance`):

| Carrier | Lieferungen | OTD-Rate | Ø Verzögerung | max |
|---|--:|--:|--:|--:|
| DHL (CAR-101) | 137 | **98,5 %** | 17,6 min | 66 min |
| DB Schenker (CAR-104) | 115 | **94,8 %** | 27,4 min | 69 min |

> Nur die beiden Land-Carrier der Endlieferung erscheinen im Fact (Grain =
> letzte Lieferung an den Retailer). DHL liefert zuverlässiger und schneller
> als DB Schenker – ein direkt handlungsleitender Carrier-Vergleich.

**KPI 2 – Ø Transportdauer 14,92 Tage.** Die Spannweite ist eng (14–16 Tage),
weil die Seefracht den Löwenanteil ausmacht und wenig streut. Diese Kennzahl
misst die *Durchlaufzeit* (Bestell- bis Lieferdatum), nicht die Verspätung.

**KPI 3 – Temperaturausreißer-Quote 7,9 %.** 20 Lieferungen verlassen den
Sollkorridor 10–15 °C (Cavendish-Banane). Diese Kühlkettenbrüche sind die
belegbare Ursache der reduzierten Batchqualität (siehe KPI 5) und werden im
DQ-Report (docs/13) als bewusste FAILs 4.3/4.4 geführt.

**KPI 4 – Ø Bestellwert 1.289,72 €**, Gesamtumsatz 325.008,80 €. Nach
Kundensegment (`dim_customer.customer_type`):

| Segment | Bestellungen | Umsatz | Ø Bestellwert |
|---|--:|--:|--:|
| DISCOUNTER | 114 | 171.655,31 € | 1.505,75 € |
| VOLLSORTIMENTER | 105 | 124.879,89 € | 1.189,33 € |
| PREMIUM | 33 | 28.473,60 € | 862,84 € |

> Discounter erzeugen trotz niedrigerer Stückpreise den höchsten Ø-Bestellwert
> und Umsatz – Großmengen schlagen Marge. Premium bestellt selten und in
> kleinen Mengen. Genau diese Trennung macht das Clustering (A-5) auswertbar.

**KPI 5 – Batchqualitätsrate 36,5 % OK.** Verteilung über alle 252 Batches:

| quality_status | Batches | Anteil | Ø Schwund (spoilage_pct) |
|---|--:|--:|--:|
| OK | 92 | 36,5 % | 0,00 % |
| REDUCED | 144 | 57,1 % | 12,83 % |
| REJECTED | 16 | 6,3 % | 51,22 % |

> Der OK-Anteil verfehlt das 40-%-Ziel knapp; der **Ø-Schwund über alle
> Batches liegt bei 10,58 %** und damit unter der 15-%-Grenze. Kausalität ist
> belegt: OK-Batches haben 0 Kühlkettenbrüche, REJECTED im Schnitt ≥ 3.

**Ursachen-KPI – Verspätungsgründe** (`delay_reason`, Basis 252 Lieferungen):

| Grund | Lieferungen | Anteil |
|---|--:|--:|
| (kein / pünktlich) | 179 | 71,0 % |
| WEATHER | 22 | 8,7 % |
| COLD_CHAIN_INCIDENT | 19 | 7,5 % |
| MECHANICAL | 17 | 6,7 % |
| TRAFFIC | 15 | 6,0 % |

---

## 2. Deskriptive Statistik

Vollständige Kennzahlen für die vier prüfungsrelevanten Felder (plus
`total_value`), berechnet mit `pandas` in
[`analytics/descriptive_stats.py`](../analytics/descriptive_stats.py). Ausreißer
nach der IQR-Methode (Wert < Q1 − 1,5·IQR oder > Q3 + 1,5·IQR).

| Kennzahl | n | Min | Max | Mittelwert | Median | Std | Q1 | Q3 | IQR | Ausreißer |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **delay_minutes** [min] | 252 | 0,00 | 69,00 | 22,10 | 20,00 | 17,00 | 8,75 | 32,00 | 23,25 | 2 (> 66,88) |
| **avg_temperature** [°C] | 252 | 8,49 | 16,88 | 12,97 | 12,89 | 1,28 | 12,20 | 13,67 | 1,46 | 7 (∉ 10,01–15,86) |
| **quantity** [Kartons] | 252 | 101 | 997 | 598,48 | 614,50 | 232,95 | 376,00 | 798,00 | 422,00 | 0 |
| **unit_price** [€] | 252 | 1,51 | 4,67 | 2,32 | 2,02 | 0,73 | 1,79 | 2,81 | 1,02 | 2 (> 4,35) |
| **total_value** [€] | 252 | 295,93 | 2.502,42 | 1.289,72 | 1.288,50 | 431,28 | 982,59 | 1.573,91 | 591,32 | 1 |

### 2.1 Interpretation

- **delay_minutes:** rechtsschiefe Verteilung – Mittelwert (22,1) > Median (20),
  die meisten Lieferungen sind pünktlich, wenige stark verspätet (2 Ausreißer
  > 66,9 min). Deckt sich mit der Liefertreue von 96,8 %.
- **avg_temperature:** Mittelwert 12,97 °C liegt mittig im Sollkorridor
  10–15 °C; geringe Std (1,28) zeigt eine grundsätzlich stabile Kühlkette.
  Die 7 IQR-Ausreißer sind die Kühlkettenbrüche und damit Qualitätstreiber.
- **quantity:** sehr hohe Streuung (Std 232,95, IQR 422) ohne IQR-Ausreißer –
  ein Beleg dafür, dass die Bestellmengen *systematisch* durch die
  Kundensegmente gespreizt sind (Discounter-Großmengen vs. Premium-Kleinmengen),
  nicht durch Einzelausreißer.
- **unit_price:** vier klar getrennte Preisniveaus (1,51–4,67 €) entsprechen den
  Produktkategorien Standard < Sustainable < Specialty < Premium; Median 2,02 €
  zeigt das Übergewicht der Standard-/Sustainable-Ware.

### 2.2 Ausreißer-Analyse (IQR-Methode)

Die IQR-Methode identifiziert genau die fachlich erwarteten Anomalien:
**7 Temperatur-Ausreißer** (Kühlkettenbrüche) und **2 Verzögerungs-Ausreißer**
(Extremverspätungen > 66,9 min). Bei `quantity` gibt es **keine** Ausreißer –
die Spreizung ist gewollt (Segmentverhalten) und kein Datenfehler. Das
bestätigt die Plausibilität des Datengenerators.

---

## 3. Abgleich mit den restlichen Analytics-Bausteinen

| Baustein | Datei | Nutzt KPIs / Statistik |
|---|---|---|
| 5 Python-Charts (A-3) | `analytics/dashboard.py` | Umsatz/Segment, Verspätungsgründe, Bestellwert-Boxplot, Transportkosten, Batchqualität |
| Clustering (A-5) | `analytics/clustering.py` | Bestellhäufigkeit, Ø Bestellwert, Ø Verzögerung → Segmente |
| Absatzprognose (A-6) | `analytics/forecast.py` | Monatliche Menge aus `v_monthly_revenue` |
| PowerBI-Konzept (A-4) | [`docs/15_powerbi_concept.md`](15_powerbi_concept.md) | KPI-Cards aus `v_kpi_summary` |

---

## 4. Prüf-/Nachweisbefehle

```bash
# KPIs aus dem DWH
docker exec -i postgres psql -U user -d logistics < sql/10_kpi_queries.sql

# Deskriptive Statistik (Konsole + analytics/descriptive_stats.txt)
python3 analytics/descriptive_stats.py

# Fulfillment-Kernwerte in einer Zeile
docker exec -i postgres psql -U user -d logistics -c "SELECT * FROM dwh.v_kpi_summary;"
```
