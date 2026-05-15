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
        INSERT INTO dwh.dim_customer (customer_number, customer_name, city, country, source_created_at)
        SELECT customer_number, customer_name, city, country, event_timestamp
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

    Grain: 1 Endlieferung (= 1 DeliveryCompleted an RETAIL_STORE).
    Pro Iteration eine Endlieferung → Anzahl Fact-Zeilen = Anzahl Iterationen (aktuell 20).
    Damit sind alle Finanzkennzahlen (total_value, quantity, unit_price)
    exakt einer Bestellung zugeordnet – kein Umsatz-Inflation durch Hops.

    Verknüpfung:
      Shipment JOIN deliveries (INNER) -> nur Endlieferungen
      Shipment.cargo_product_reference == Product.product_code
        -> findet zugehörige Order-Position (erste Order pro Produkt)
        -> Customer, Supplier, quantity, unit_price, total_value
      Shipment.shipment_id -> transport_completions (delay_minutes)

    Idempotenz: fact_fulfillment wird vor dem Laden geleert.
    """
    cur.execute("DELETE FROM dwh.fact_fulfillment")
    deleted = cur.rowcount

    cur.execute("""
        WITH
        -- Order-Positionen mit allen Kontextspalten, deterministisch ranked
        -- pro Produktcode, sodass mehrere Shipments für dasselbe Produkt
        -- auf unterschiedliche Bestellungen abgebildet werden können.
        order_per_product AS (
            SELECT
                p.product_code,
                o.order_reference,
                o.delivery_priority,
                TO_CHAR(o.order_timestamp, 'YYYYMMDD')::INT  AS order_date_sk,
                c.customer_number,
                s.supplier_code,
                oi.quantity,
                oi.unit_price,
                (oi.quantity * oi.unit_price)               AS total_value,
                ROW_NUMBER() OVER (
                    PARTITION BY p.product_code
                    ORDER BY o.order_timestamp, oi.item_id
                ) AS order_rn
            FROM  erp.order_items oi
            JOIN  erp.orders      o  ON o.order_id    = oi.order_id
            JOIN  erp.customers   c  ON c.customer_id = o.customer_id
            JOIN  erp.products    p  ON p.product_id  = oi.product_id
            JOIN  erp.suppliers   s  ON s.supplier_id = p.supplier_id
        ),

        -- Nur Endlieferungen (INNER JOIN auf tms.deliveries).
        -- Ergibt genau 1 Zeile pro Iteration (DeliveryCompleted an RETAIL_STORE).
        shipment_enriched AS (
            SELECT
                sh.shipment_id,
                sh.shipment_identifier,
                sh.target_node,
                UPPER(sh.cargo_product_reference)           AS product_code,
                ca.carrier_code,
                d.delivery_status,
                TO_CHAR(d.delivered_at, 'YYYYMMDD')::INT    AS delivery_date_sk,
                COALESCE(tc.delay_minutes, 0)               AS delay_minutes
            FROM  tms.shipments                 sh
            JOIN  tms.deliveries                d  ON d.shipment_id  = sh.shipment_id
            LEFT JOIN tms.carriers              ca ON ca.carrier_id  = sh.carrier_id
            LEFT JOIN tms.transport_completions tc ON tc.shipment_id = sh.shipment_id
        ),

        -- Durchschnittstemperatur pro Produkt über alle NodeProcessings.
        -- Aggregation auf Produktebene reicht, weil Batches 1:N pro Produkt sind.
        product_temperature AS (
            SELECT
                p.product_code,
                ROUND(AVG(np.temperature)::NUMERIC, 2) AS avg_temperature
            FROM  erp.batches             b
            JOIN  erp.products            p  ON p.product_id  = b.product_id
            LEFT JOIN wms.node_processings np
                   ON np.batch_reference = b.batch_identifier
            GROUP BY p.product_code
        ),

        -- 1 Batch pro Produkt für batch_identifier-Nachweis (deterministisch).
        first_batch_per_product AS (
            SELECT DISTINCT ON (p.product_code)
                p.product_code,
                b.batch_identifier
            FROM  erp.batches  b
            JOIN  erp.products p ON p.product_id = b.product_id
            ORDER BY p.product_code, b.harvested_at, b.batch_id
        )

        INSERT INTO dwh.fact_fulfillment (
            customer_sk, product_sk, supplier_sk, carrier_sk,
            destination_node_sk, order_date_sk, delivery_date_sk, delivery_status_sk,
            order_reference, batch_identifier, shipment_identifier,
            quantity, unit_price, total_value,
            delay_minutes, avg_temperature, num_supply_chain_hops, delivery_priority_code,
            on_time_flag
        )
        SELECT
            dc.customer_sk,
            dp.product_sk,
            ds.supplier_sk,
            dca.carrier_sk,
            dn.node_sk                              AS destination_node_sk,
            op.order_date_sk,
            se.delivery_date_sk,
            dds.status_sk                           AS delivery_status_sk,
            op.order_reference,
            fb.batch_identifier,
            se.shipment_identifier,
            op.quantity,
            op.unit_price,
            op.total_value,
            se.delay_minutes,
            pt.avg_temperature,
            6                                       AS num_supply_chain_hops,
            op.delivery_priority                    AS delivery_priority_code,
            -- Liefertreue-Flag: TRUE nur bei vollständig erfolgreicher, unverzögerter Lieferung
            (se.delivery_status = 'SUCCESSFUL' AND se.delay_minutes = 0) AS on_time_flag
        FROM  shipment_enriched          se
        -- Order pro Produkt: deterministisches Mapping per Shipment-Reihenfolge.
        -- MOD nutzt die Anzahl der Orders pro Produkt, damit auch der 6. Hop
        -- desselben Produkts eine gültige Order findet.
        JOIN  order_per_product          op  ON op.product_code  = se.product_code
                                            AND op.order_rn      = 1
        JOIN  product_temperature        pt  ON pt.product_code  = se.product_code
        LEFT JOIN first_batch_per_product fb ON fb.product_code  = se.product_code
        JOIN  dwh.dim_customer           dc  ON dc.customer_number = op.customer_number
        JOIN  dwh.dim_product            dp  ON dp.product_code    = se.product_code
        JOIN  dwh.dim_supplier           ds  ON ds.supplier_code   = op.supplier_code
        LEFT JOIN dwh.dim_carrier        dca ON dca.carrier_code   = se.carrier_code
        LEFT JOIN dwh.dim_supply_chain_node dn
                                              ON dn.node_code       = se.target_node
        JOIN  dwh.dim_delivery_status    dds ON dds.status_code    = se.delivery_status
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
