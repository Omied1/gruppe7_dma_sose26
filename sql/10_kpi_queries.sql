-- ============================================================================
-- 10_kpi_queries.sql  –  Teil 2 / Analytics: Business-KPIs aus dem DWH
-- ----------------------------------------------------------------------------
-- Alle Kennzahlen werden ausschließlich aus dem Sternschema (dwh.*) berechnet,
-- Grain = 1 Zeile je Endlieferung in dwh.fact_fulfillment (252 Zeilen,
-- 13 Monate, 10 Kunden). Ausführbar gegen die laufende PostgreSQL-Instanz:
--   docker exec -i postgres psql -U user -d logistics < sql/10_kpi_queries.sql
--
-- Jeder KPI hat: Name · Formel · Datenquelle · Zielwert (siehe docs/14).
-- ============================================================================


-- ============================================================================
-- KPI-Übersicht (Fulfillment-Kernwerte via vorberechnete View)
-- ============================================================================
-- Liefertreue, Ø Verzögerung, Temperaturausreißer-Quote, Ø Bestellwert, Umsatz.
-- Transportdauer und Batchqualitätsrate werden darunter separat berechnet.
SELECT * FROM dwh.v_kpi_summary;


-- ============================================================================
-- KPI 1 – Liefertreue / On-Time-Delivery-Rate (%)
-- Formel:   100 * COUNT(on_time_flag = TRUE) / COUNT(*)
-- Quelle:   dwh.fact_fulfillment.on_time_flag  (TRUE = delay_minutes <= 60)
-- Zielwert: >= 95 %
-- ============================================================================
SELECT
    COUNT(*)                                                  AS lieferungen,
    COUNT(*) FILTER (WHERE on_time_flag)                      AS puenktlich,
    ROUND(100.0 * COUNT(*) FILTER (WHERE on_time_flag)
                / COUNT(*), 1)                                AS liefertreue_pct
FROM dwh.fact_fulfillment;

-- Aufschlüsselung je Carrier (identisch zu dwh.v_carrier_performance)
SELECT carrier_name, total_fulfillments, otd_rate_pct, avg_delay_minutes, max_delay_minutes
FROM   dwh.v_carrier_performance
ORDER  BY otd_rate_pct DESC;


-- ============================================================================
-- KPI 2 – Ø Transportdauer (Tage)
-- Formel:   AVG(delivery_date - order_date)
-- Quelle:   fact_fulfillment.order_date_sk / delivery_date_sk -> dwh.dim_date
-- Zielwert: <= 18 Tage (Seefracht Ghana -> Rotterdam + Landverteilung)
-- ============================================================================
SELECT
    ROUND(AVG(dd.full_date - od.full_date), 2)                             AS avg_transportdauer_tage,
    MIN(dd.full_date - od.full_date)                                       AS min_tage,
    MAX(dd.full_date - od.full_date)                                       AS max_tage,
    ROUND(percentile_cont(0.5) WITHIN GROUP
          (ORDER BY (dd.full_date - od.full_date))::numeric, 1)            AS median_tage
FROM dwh.fact_fulfillment f
JOIN dwh.dim_date od ON od.date_sk = f.order_date_sk
JOIN dwh.dim_date dd ON dd.date_sk = f.delivery_date_sk;


-- ============================================================================
-- KPI 3 – Temperaturausreißer-Quote / Kühlkettenbruch-Rate (%)
-- Formel:   100 * COUNT(avg_temperature NOT BETWEEN 10 AND 15) / COUNT(*)
-- Quelle:   dwh.fact_fulfillment.avg_temperature
-- Zielwert: <= 10 %  (Cavendish-Banane: Transport-Sollkorridor 10–15 °C)
-- ============================================================================
SELECT
    COUNT(*)                                                              AS lieferungen,
    COUNT(*) FILTER (WHERE avg_temperature NOT BETWEEN 10 AND 15)         AS kuehlkettenbrueche,
    ROUND(100.0 * COUNT(*) FILTER (WHERE avg_temperature NOT BETWEEN 10 AND 15)
                / COUNT(*), 1)                                            AS temp_ausreisser_pct
FROM dwh.fact_fulfillment
WHERE avg_temperature IS NOT NULL;


-- ============================================================================
-- KPI 4 – Ø Bestellwert (€)  +  Gesamtumsatz (€)
-- Formel:   AVG(total_value)  bzw.  SUM(total_value)
-- Quelle:   dwh.fact_fulfillment.total_value  (= quantity * unit_price)
-- Zielwert: Ø-Bestellwert >= 1.000 € (Deckungsbeitrag je Lieferung)
-- ============================================================================
SELECT
    COUNT(*)                          AS lieferungen,
    ROUND(AVG(total_value), 2)        AS avg_bestellwert_eur,
    ROUND(SUM(total_value), 2)        AS gesamtumsatz_eur
FROM dwh.fact_fulfillment;

-- Umsatz nach Kundensegment (nutzt dim_customer.customer_type)
SELECT
    c.customer_type,
    COUNT(*)                          AS bestellungen,
    ROUND(SUM(f.total_value), 2)      AS umsatz_eur,
    ROUND(AVG(f.total_value), 2)      AS avg_bestellwert_eur
FROM dwh.fact_fulfillment f
JOIN dwh.dim_customer     c ON c.customer_sk = f.customer_sk
GROUP BY c.customer_type
ORDER BY umsatz_eur DESC;


-- ============================================================================
-- KPI 5 – Batchqualitätsrate (%)
-- Formel:   100 * COUNT(quality_status = 'OK') / COUNT(*)
-- Quelle:   erp.batches.quality_status  (OK / REDUCED / REJECTED aus Kühlkette)
--           bzw. Wochenaggregat in dwh.v_batch_quality
-- Zielwert: >= 40 % OK-Batches; Ø-Schwund (spoilage_pct) <= 15 %
-- ============================================================================
SELECT
    quality_status,
    COUNT(*)                                                    AS batches,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)          AS anteil_pct,
    ROUND(AVG(spoilage_pct), 2)                                 AS avg_schwund_pct
FROM erp.batches
GROUP BY quality_status
ORDER BY batches DESC;

-- Gesamt-Qualitätsrate (OK-Anteil) + Ø-Schwund über alle Batches
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE quality_status = 'OK')
                / COUNT(*), 1)                                  AS batchqualitaetsrate_pct,
    ROUND(AVG(spoilage_pct), 2)                                 AS avg_schwund_pct
FROM erp.batches;


-- ============================================================================
-- Zusatz-KPI – Verspätungsgründe (delay_reason) für Ursachenanalyse
-- Quelle:   dwh.fact_fulfillment.delay_reason (NULL = pünktlich/kein Grund)
-- ============================================================================
SELECT
    COALESCE(delay_reason, '(kein)')                            AS verspaetungsgrund,
    COUNT(*)                                                    AS lieferungen,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)          AS anteil_pct
FROM dwh.fact_fulfillment
GROUP BY delay_reason
ORDER BY lieferungen DESC;


-- ============================================================================
-- [ANPASSUNG 2026-07-05] KPI 6 – Bruttomarge (%)
-- Formel:   100 * SUM(gross_profit) / SUM(total_value)
-- Quelle:   fact_fulfillment.gross_profit (= total_value − cogs_total;
--           unit_cost ist SIMULIERTER Wareneinsatz, [ANNAHME] 50-65 % der
--           Preisband-Untergrenze je Kategorie – kein realer Beschaffungspreis)
-- Zielwert: >= 40 %
-- ============================================================================
SELECT
    ROUND(SUM(cogs_total), 2)                                            AS cogs_gesamt_eur,
    ROUND(SUM(gross_profit), 2)                                          AS bruttogewinn_eur,
    ROUND(100.0 * SUM(gross_profit) / SUM(total_value), 1)               AS bruttomarge_pct
FROM dwh.fact_fulfillment;

-- Bruttomarge je Produktkategorie
SELECT
    p.category,
    ROUND(SUM(f.total_value), 2)                                         AS umsatz_eur,
    ROUND(SUM(f.gross_profit), 2)                                        AS bruttogewinn_eur,
    ROUND(100.0 * SUM(f.gross_profit) / SUM(f.total_value), 1)           AS bruttomarge_pct
FROM dwh.fact_fulfillment f
JOIN dwh.dim_product p ON p.product_sk = f.product_sk
GROUP BY p.category
ORDER BY bruttomarge_pct DESC;


-- ============================================================================
-- [ANPASSUNG 2026-07-05] KPI 7 – Logistischer Deckungsbeitrag (EUR und %)
-- Formel:   Umsatz − COGS − allokierte Transportkosten − Lagerkosten
-- Quelle:   fact_fulfillment.contribution_margin
-- Hinweis:  VEREINFACHTER logistischer Deckungsbeitrag aus Supply-Chain-Sicht,
--           KEIN vollständiger Unternehmensgewinn (ohne Personal-/Verwaltungs-/
--           Vertriebskosten). Transportkosten sind kapazitätsallokiert.
-- Zielwert: > 0 (positiv); Orientierung 15–30 % Quote
-- ============================================================================
SELECT
    ROUND(SUM(total_value), 2)                                           AS umsatz_eur,
    ROUND(SUM(cogs_total), 2)                                            AS cogs_eur,
    ROUND(SUM(transport_cost), 2)                                        AS transportkosten_eur,
    ROUND(SUM(storage_cost), 2)                                          AS lagerkosten_eur,
    ROUND(SUM(contribution_margin), 2)                                   AS deckungsbeitrag_eur,
    ROUND(100.0 * SUM(contribution_margin) / SUM(total_value), 1)        AS deckungsbeitragsquote_pct,
    ROUND(100.0 * SUM(transport_cost) / SUM(total_value), 1)             AS transportkostenquote_pct,
    ROUND(100.0 * SUM(storage_cost) / SUM(total_value), 1)               AS lagerkostenquote_pct
FROM dwh.fact_fulfillment;

-- Deckungsbeitrag je Kundensegment (via vorberechnete View dwh.v_profitability)
SELECT customer_type,
       SUM(revenue_eur)                                                  AS umsatz_eur,
       SUM(contribution_margin_eur)                                      AS deckungsbeitrag_eur,
       ROUND(100.0 * SUM(contribution_margin_eur) / SUM(revenue_eur), 1) AS db_quote_pct
FROM dwh.v_profitability
GROUP BY customer_type
ORDER BY deckungsbeitrag_eur DESC;


-- ============================================================================
-- [ANPASSUNG 2026-07-05] Zusatz – Lagerkosten je Knoten + Bestandsverlauf
-- Quelle:   WMS-Zeitstempel (Ankunft node_processings.processed_at bis Abgang
--           tms.shipments.started_at) × Knotensatz; dwh.v_stock_by_node
-- ============================================================================
SELECT
    n.node_code,
    n.storage_cost_per_unit_day                                          AS satz_eur_einheit_tag,
    ROUND(SUM(GREATEST(EXTRACT(EPOCH FROM (dep.departed_at - np.processed_at)) / 86400.0, 0)
              * b.quantity * n.storage_cost_per_unit_day)::NUMERIC, 2)   AS lagerkosten_eur
FROM  wms.node_processings   np
JOIN  wms.supply_chain_nodes n ON n.node_id = np.node_id
JOIN  erp.batches            b ON b.batch_identifier = np.batch_reference
LEFT JOIN LATERAL (
    SELECT MIN(sh.started_at) AS departed_at
    FROM   tms.shipments sh
    WHERE  sh.batch_identifier = np.batch_reference
      AND  UPPER(sh.source_node) = n.node_code
) dep ON TRUE
WHERE n.node_type IN ('COLD_STORAGE', 'WAREHOUSE')
  AND dep.departed_at IS NOT NULL
GROUP BY n.node_code, n.storage_cost_per_unit_day, n.sequence_order
ORDER BY n.sequence_order;

-- Wochen-Peak des Bestandsverlaufs je Knoten (Inventory-Nachweis)
SELECT node_code, MAX(balance_end_of_week) AS max_wochenbestand
FROM dwh.v_stock_by_node
GROUP BY node_code
ORDER BY max_wochenbestand DESC;


-- ============================================================================
-- Nachweis: erwartete Fact-Zeilen und Zeitraum
-- ============================================================================
SELECT
    COUNT(*)                                    AS fact_zeilen,
    COUNT(DISTINCT customer_sk)                 AS kunden,
    MIN(od.full_date)                           AS erste_bestellung,
    MAX(od.full_date)                           AS letzte_bestellung
FROM dwh.fact_fulfillment f
JOIN dwh.dim_date od ON od.date_sk = f.order_date_sk;
