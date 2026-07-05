"""
ETL Phase 2: Operative PostgreSQL-Schemas → DWH-Sternschema
Banana Supply Chain – Datenmanagement und Analytics, SoSe 26

Ausführung:
    cd bananasupplychain
    python3 etl_dwh.py

Voraussetzung: etl_load.py muss vorher vollständig durchgelaufen sein
(erp/wms/tms-Schemas müssen befüllt sein).

Reihenfolge:
    1. Dimensionen befüllen (idempotent via ON CONFLICT DO NOTHING)
    2. fact_fulfillment leeren und neu befüllen (via DELETE + INSERT)
"""

import sys
from datetime import datetime

try:
    import psycopg2
except ImportError:
    print("Fehlende Abhängigkeit: psycopg2")
    print("Installieren mit: pip install psycopg2-binary")
    sys.exit(1)

PG_DSN = "host=localhost port=5432 dbname=logistics user=user password=password"

stats = {}

def count(label, n=1):
    stats[label] = stats.get(label, 0) + n

def connect():
    try:
        conn = psycopg2.connect(PG_DSN)
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"  FEHLER: PostgreSQL-Verbindung fehlgeschlagen: {e}")
        sys.exit(1)


# =============================================================================
# DIMENSIONEN
# =============================================================================

def fill_dim_customer(cur):
    """Kunden aus erp.customers in dwh.dim_customer kopieren."""
    cur.execute("""
        INSERT INTO dwh.dim_customer (customer_number, customer_name, customer_type, city, country, source_created_at)
        SELECT customer_number, customer_name, customer_type, city, country, event_timestamp
        FROM   erp.customers
        ON CONFLICT (customer_number) DO NOTHING
    """)
    count("dim_customer", cur.rowcount)


def fill_dim_supplier(cur):
    """Lieferanten aus erp.suppliers in dwh.dim_supplier kopieren."""
    cur.execute("""
        INSERT INTO dwh.dim_supplier (supplier_code, supplier_name, country, source_created_at)
        SELECT supplier_code, supplier_name, country, event_timestamp
        FROM   erp.suppliers
        ON CONFLICT (supplier_code) DO NOTHING
    """)
    count("dim_supplier", cur.rowcount)


def fill_dim_product(cur):
    """
    Produkte aus erp.products + denormalisierte Lieferantenattribute.
    dim_product enthält supplier_name/country eingefaltet, damit Analytics-Abfragen
    ohne zusätzlichen JOIN auf dim_supplier auskommen.
    """
    cur.execute("""
        INSERT INTO dwh.dim_product
            (product_code, product_name, category,
             supplier_code, supplier_name, supplier_country)
        SELECT
            p.product_code,
            p.product_name,
            p.category,
            s.supplier_code,
            s.supplier_name,
            s.country
        FROM  erp.products  p
        LEFT JOIN erp.suppliers s ON s.supplier_id = p.supplier_id
        ON CONFLICT (product_code) DO NOTHING
    """)
    count("dim_product", cur.rowcount)


def fill_dim_carrier(cur):
    """Carrier aus tms.carriers in dwh.dim_carrier kopieren."""
    cur.execute("""
        INSERT INTO dwh.dim_carrier (carrier_code, carrier_name, source_created_at)
        SELECT carrier_code, carrier_name, event_timestamp
        FROM   tms.carriers
        ON CONFLICT (carrier_code) DO NOTHING
    """)
    count("dim_carrier", cur.rowcount)


def fill_dim_supply_chain_node(cur):
    """Supply-Chain-Knoten aus wms.supply_chain_nodes kopieren."""
    cur.execute("""
        INSERT INTO dwh.dim_supply_chain_node
            (node_code, node_name, node_type, region, sequence_order)
        SELECT node_code, node_name, node_type, region, sequence_order
        FROM   wms.supply_chain_nodes
        ON CONFLICT (node_code) DO NOTHING
    """)
    count("dim_supply_chain_node", cur.rowcount)


# =============================================================================
# FAKTENTABELLE
# =============================================================================

def fill_fact_fulfillment(cur):
    """
    Befüllt fact_fulfillment aus den operativen Schemas.

    Grain: 1 Endlieferung (= 1 DeliveryCompleted an RETAIL_STORE) = 1 Fact-Zeile.

    [ANPASSUNG 2026-07-02] Faithful Mapping: Shipments tragen die echte order_reference und
    batch_identifier. Jede Endlieferung wird ihrer TATSÄCHLICHEN Bestellung/Batch zugeordnet
    (kein "erste Order pro Produkt / order_rn=1" mehr). Dadurch entsprechen Bestelldatum,
    Kunde, Wert, Menge, Batch und Transportkosten der realen Verteilung über die 52 Wochen.

    Verknüpfung:
      Shipment (finales Leg) JOIN deliveries (INNER) -> nur Endlieferungen
      Shipment.order_reference == erp.orders.order_reference
        -> echter Customer, Supplier, Produkt, quantity, unit_price, total_value, Bestelldatum
      Shipment.batch_identifier == erp.batches.batch_identifier -> echter Batch (Ø Temperatur)
      SUM(transport_cost/distance_km) je order_reference -> exakte Fulfillment-Kosten/-Distanz
      transport_completions.delay_minutes -> Liefertreue (SLA 60 min) + delay_reason

    Idempotenz: fact_fulfillment wird vor dem Laden geleert.
    """
    cur.execute("DELETE FROM dwh.fact_fulfillment")
    deleted = cur.rowcount

    cur.execute("""
        WITH
        -- [ANPASSUNG 2026-07-02] Faithful Mapping: Shipments tragen jetzt die echte order_reference
        -- und batch_identifier. Jede Endlieferung wird ihrer TATSÄCHLICHEN Bestellung zugeordnet
        -- (statt der früheren Vereinfachung "erste Bestellung je Produkt"). Dadurch spiegeln
        -- Bestelldatum, Kunde, Wert, Menge, Batch und Kosten die reale Verteilung über die 52 Wochen.

        -- Endlieferung je Fulfillment (finales Leg = DeliveryCompleted am RETAIL_STORE).
        -- delivery_status wird im DWH per SLA (<= 60 min) neu abgeleitet (Cleaning der bewussten
        -- Roh-Inkonsistenz aus dem Generator: delivery_status wird dort unabhängig gewürfelt).
        delivery_leg AS (
            SELECT
                sh.order_reference,
                sh.batch_identifier,
                sh.shipment_identifier,
                sh.target_node,
                ca.carrier_code,
                CASE WHEN COALESCE(tc.delay_minutes, 0) <= 60
                     THEN 'SUCCESSFUL' ELSE 'DELAYED' END       AS delivery_status,
                TO_CHAR(d.delivered_at, 'YYYYMMDD')::INT        AS delivery_date_sk,
                COALESCE(tc.delay_minutes, 0)                   AS delay_minutes,
                tc.delay_reason                                 AS delay_reason
            FROM  tms.shipments                 sh
            JOIN  tms.deliveries                d  ON d.shipment_id  = sh.shipment_id
            LEFT JOIN tms.carriers              ca ON ca.carrier_id  = sh.carrier_id
            LEFT JOIN tms.transport_completions tc ON tc.shipment_id = sh.shipment_id
        ),

        -- Echte Bestellung (in diesen Daten genau 1 Position je Order) via order_reference.
        order_facts AS (
            SELECT
                o.order_reference,
                o.delivery_priority,
                TO_CHAR(o.order_timestamp, 'YYYYMMDD')::INT     AS order_date_sk,
                c.customer_number,
                s.supplier_code,
                p.product_code,
                oi.quantity,
                oi.unit_price,
                (oi.quantity * oi.unit_price)                   AS total_value,
                p.unit_cost                                     -- [ANPASSUNG 2026-07-05] COGS-Basis
            FROM  erp.orders      o
            JOIN  erp.order_items oi ON oi.order_id    = o.order_id
            JOIN  erp.customers   c  ON c.customer_id  = o.customer_id
            JOIN  erp.products    p  ON p.product_id   = oi.product_id
            JOIN  erp.suppliers   s  ON s.supplier_id  = p.supplier_id
        ),

        -- Transportkosten/-distanz je Fulfillment = Summe der 6 Legs derselben order_reference (exakt).
        route_metrics AS (
            SELECT
                order_reference,
                ROUND(SUM(transport_cost), 2) AS transport_cost,
                ROUND(SUM(distance_km), 2)    AS distance_km
            FROM tms.shipments
            WHERE order_reference IS NOT NULL
            GROUP BY order_reference
        ),

        -- Ø Temperatur je (echtem) Batch über alle NodeProcessings.
        batch_temp AS (
            SELECT
                b.batch_identifier,
                ROUND(AVG(np.temperature)::NUMERIC, 2) AS avg_temperature
            FROM  erp.batches             b
            LEFT JOIN wms.node_processings np ON np.batch_reference = b.batch_identifier
            GROUP BY b.batch_identifier
        ),

        -- [ANPASSUNG 2026-07-05] Lagerkosten je Batch aus ECHTEN WMS-Zeitstempeln:
        -- Verweildauer an Lagerknoten (COLD_STORAGE/WAREHOUSE) = Ankunft
        -- (node_processings.processed_at) bis Abgang (started_at des TMS-Legs, das den
        -- Knoten verlässt). GREATEST(0, ...) fängt Zeitjitter des Generators ab.
        -- Kostensatz je Knoten: wms.supply_chain_nodes.storage_cost_per_unit_day ([ANNAHME]).
        storage AS (
            SELECT
                np.batch_reference,
                ROUND(SUM(GREATEST(
                    EXTRACT(EPOCH FROM (dep.departed_at - np.processed_at)) / 86400.0, 0
                ))::NUMERIC, 2)                                            AS storage_days,
                SUM(GREATEST(
                    EXTRACT(EPOCH FROM (dep.departed_at - np.processed_at)) / 86400.0, 0
                ) * n.storage_cost_per_unit_day)                           AS storage_cost_per_unit
            FROM  wms.node_processings   np
            JOIN  wms.supply_chain_nodes n ON n.node_id = np.node_id
            LEFT JOIN LATERAL (
                SELECT MIN(sh.started_at) AS departed_at
                FROM   tms.shipments sh
                WHERE  sh.batch_identifier = np.batch_reference
                  AND  UPPER(sh.source_node) = n.node_code
            ) dep ON TRUE
            WHERE n.node_type IN ('COLD_STORAGE', 'WAREHOUSE')
              AND dep.departed_at IS NOT NULL
            GROUP BY np.batch_reference
        )

        INSERT INTO dwh.fact_fulfillment (
            customer_sk, product_sk, supplier_sk, carrier_sk,
            destination_node_sk, order_date_sk, delivery_date_sk, delivery_status_sk,
            order_reference, batch_identifier, shipment_identifier,
            quantity, unit_price, total_value,
            delay_minutes, avg_temperature, num_supply_chain_hops, delivery_priority_code,
            transport_cost, distance_km, delay_reason,
            unit_cost, cogs_total, gross_profit, storage_days, storage_cost, contribution_margin,
            on_time_flag
        )
        SELECT
            dc.customer_sk,
            dp.product_sk,
            ds.supplier_sk,
            dca.carrier_sk,
            dn.node_sk                              AS destination_node_sk,
            ofa.order_date_sk,
            dl.delivery_date_sk,
            dds.status_sk                           AS delivery_status_sk,
            ofa.order_reference,
            dl.batch_identifier,
            dl.shipment_identifier,
            ofa.quantity,
            ofa.unit_price,
            ofa.total_value,
            dl.delay_minutes,
            bt.avg_temperature,
            6                                       AS num_supply_chain_hops,
            ofa.delivery_priority                   AS delivery_priority_code,
            rm.transport_cost,
            rm.distance_km,
            dl.delay_reason,
            -- [ANPASSUNG 2026-07-05] Profitabilität: COGS (simuliert), Bruttogewinn,
            -- Lagerkosten (Verweildauer × Knotensatz) und vereinfachter LOGISTISCHER
            -- Deckungsbeitrag (kein Unternehmensgewinn: ohne Personal/Verwaltung/Vertrieb).
            ofa.unit_cost,
            ROUND(ofa.quantity * ofa.unit_cost, 2)                          AS cogs_total,
            ROUND(ofa.total_value - ofa.quantity * ofa.unit_cost, 2)        AS gross_profit,
            COALESCE(st.storage_days, 0)                                    AS storage_days,
            ROUND(COALESCE(st.storage_cost_per_unit, 0) * ofa.quantity, 2)  AS storage_cost,
            ROUND(ofa.total_value
                  - ofa.quantity * ofa.unit_cost
                  - COALESCE(rm.transport_cost, 0)
                  - COALESCE(st.storage_cost_per_unit, 0) * ofa.quantity, 2) AS contribution_margin,
            -- Liefertreue-Flag: TRUE wenn delay_minutes <= 60 (SLA-Schwellenwert),
            -- gleiche Logik wie die delivery_status-Ableitung oben.
            (dl.delay_minutes <= 60) AS on_time_flag
        -- [ANPASSUNG 2026-07-02] Endlieferung -> echte Bestellung via order_reference (1:1),
        -- echter Batch via batch_identifier. Kein order_per_product/rn=1 mehr.
        FROM  delivery_leg      dl
        JOIN  order_facts       ofa ON ofa.order_reference  = dl.order_reference
        LEFT JOIN route_metrics rm  ON rm.order_reference   = dl.order_reference
        LEFT JOIN batch_temp    bt  ON bt.batch_identifier  = dl.batch_identifier
        LEFT JOIN storage       st  ON st.batch_reference   = dl.batch_identifier
        JOIN  dwh.dim_customer  dc  ON dc.customer_number    = ofa.customer_number
        JOIN  dwh.dim_product   dp  ON dp.product_code       = ofa.product_code
        JOIN  dwh.dim_supplier  ds  ON ds.supplier_code      = ofa.supplier_code
        LEFT JOIN dwh.dim_carrier dca ON dca.carrier_code    = dl.carrier_code
        LEFT JOIN dwh.dim_supply_chain_node dn ON dn.node_code = dl.target_node
        JOIN  dwh.dim_delivery_status dds ON dds.status_code  = dl.delivery_status
    """)

    inserted = cur.rowcount
    count("fact_fulfillment_deleted", deleted)
    count("fact_fulfillment_inserted", inserted)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("ETL Phase 2 – Operative Schemas → DWH")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    pg = connect()
    cur = pg.cursor()

    # [ANPASSUNG 2026-07-01] Dimensionen vor dem Neuladen leeren, damit Quelländerungen
    # (neue Produktkategorie, customer_type ...) auch bei bereits vorhandenen Business-Keys
    # übernommen werden. Zuvor verhinderte ON CONFLICT DO NOTHING jede Aktualisierung ->
    # veraltete Dimensionswerte. dim_date/dim_delivery_status sind statisch (DDL) und bleiben.
    print("[0/6] DWH-Dimensionen + Fakt zurücksetzen...")
    cur.execute("""
        TRUNCATE dwh.dim_customer, dwh.dim_supplier, dwh.dim_product,
                 dwh.dim_carrier, dwh.dim_supply_chain_node, dwh.fact_fulfillment
        RESTART IDENTITY CASCADE
    """)

    print("[1/6] dim_customer befüllen...")
    fill_dim_customer(cur)

    print("[2/6] dim_supplier befüllen...")
    fill_dim_supplier(cur)

    print("[3/6] dim_product befüllen (inkl. Lieferantenattribute)...")
    fill_dim_product(cur)

    print("[4/6] dim_carrier befüllen...")
    fill_dim_carrier(cur)

    print("[5/6] dim_supply_chain_node befüllen...")
    fill_dim_supply_chain_node(cur)

    print("[6/6] fact_fulfillment befüllen...")
    fill_fact_fulfillment(cur)

    pg.commit()
    cur.close()
    pg.close()

    print()
    print("=" * 60)
    print("ETL Phase 2 abgeschlossen")
    print("=" * 60)
    print(f"  dim_customer       : {stats.get('dim_customer', 0):>6} neue Zeilen")
    print(f"  dim_supplier       : {stats.get('dim_supplier', 0):>6} neue Zeilen")
    print(f"  dim_product        : {stats.get('dim_product', 0):>6} neue Zeilen")
    print(f"  dim_carrier        : {stats.get('dim_carrier', 0):>6} neue Zeilen")
    print(f"  dim_supply_chain_node: {stats.get('dim_supply_chain_node', 0):>4} neue Zeilen")
    print(f"  fact_fulfillment   : {stats.get('fact_fulfillment_deleted', 0):>6} gelöscht, "
          f"{stats.get('fact_fulfillment_inserted', 0):>6} neu geladen")
    print()
    print("Nachweis-Queries:")
    print("  SELECT COUNT(*) FROM dwh.dim_customer;")
    print("  SELECT COUNT(*) FROM dwh.dim_product;")
    print("  SELECT COUNT(*) FROM dwh.dim_supplier;")
    print("  SELECT COUNT(*) FROM dwh.dim_carrier;")
    print("  SELECT COUNT(*) FROM dwh.dim_supply_chain_node;")
    print("  SELECT COUNT(*) FROM dwh.fact_fulfillment;")


if __name__ == "__main__":
    main()
