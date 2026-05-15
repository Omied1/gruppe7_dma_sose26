"""
ETL-Skript: JSON-Events → PostgreSQL / MongoDB / Redis / Neo4j
Banana Supply Chain – Datenmanagement und Analytics, SoSe 26

Ausführung:
    cd bananasupplychain
    python3 etl_load.py
    python3 generate_documents.py   # MinIO-Dokumente (PDFs) separat

Voraussetzungen:
    pip install psycopg2-binary pymongo redis neo4j
    Docker-Container müssen laufen (docker-compose up -d)
"""

import json
import glob
import os
import sys
from datetime import datetime

# ── Abhängigkeiten ────────────────────────────────────────────────────────────
try:
    import psycopg2
    from pymongo import MongoClient
    import redis as redis_lib
    from neo4j import GraphDatabase
except ImportError as e:
    print(f"Fehlende Abhängigkeit: {e}")
    print("Installieren mit: pip install psycopg2-binary pymongo redis neo4j")
    sys.exit(1)

# ── Verbindungs-Konfiguration ────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
SHARED    = os.path.join(BASE_DIR, "..", "shared")

PG_DSN    = "host=localhost port=5432 dbname=logistics user=user password=password"
MONGO_URI = "mongodb://localhost:27017"
REDIS_HOST, REDIS_PORT = "localhost", 6379
NEO4J_URI, NEO4J_USER, NEO4J_PASS = "bolt://localhost:7687", "neo4j", "password"

# ── MDM-Schlüsselharmonisierung ──────────────────────────────────────────────
def normalize_key(key: str) -> str:
    """BAN_101 / ban-101 / BAN-101  →  BAN-101"""
    return key.strip().lower().replace("_", "-").upper()

# ── Typkonvertierungen ────────────────────────────────────────────────────────
def safe_float(val):
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None

def safe_int(val):
    try:
        return int(val) if val is not None else None
    except (ValueError, TypeError):
        return None

# ── Extract ──────────────────────────────────────────────────────────────────
def extract_events(system: str) -> list:
    """Liest alle JSON-Events eines Systems. Iteration 000 (Stammdaten) zuerst."""
    path    = os.path.join(SHARED, system, "*.json")
    files   = sorted(glob.glob(path))
    events  = []
    for f in files:
        try:
            events.append(json.load(open(f, encoding='utf-8')))
        except Exception as exc:
            print(f"  WARNUNG: {f} konnte nicht gelesen werden: {exc}")
    return events

# ── Statistik-Zähler ─────────────────────────────────────────────────────────
stats = {}
def count(label):
    stats[label] = stats.get(label, 0) + 1

# =============================================================================
# LOAD – PostgreSQL
# =============================================================================
def load_postgres(erp_events, wms_events, tms_events, pg):
    cur = pg.cursor()

    # ── Schritt 1: ERP-Stammdaten ─────────────────────────────────────────────
    for ev in erp_events:
        et = ev.get("event_type")

        if et == "SupplierCreated":
            cur.execute("""
                INSERT INTO erp.suppliers (supplier_code, supplier_name, country, event_timestamp)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (supplier_code) DO NOTHING
            """, (ev["supplier_code"], ev["supplier_name"], ev.get("country"),
                  ev.get("timestamp")))
            count("pg.suppliers")

        elif et == "CustomerCreated":
            cur.execute("""
                INSERT INTO erp.customers (customer_number, customer_name, city, country, event_timestamp)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (customer_number) DO NOTHING
            """, (ev["customer_number"], ev["customer_name"],
                  ev.get("city"), ev.get("country"), ev.get("timestamp")))
            count("pg.customers")

        elif et == "ProductCreated":
            canonical = normalize_key(ev["product_code"])
            # Supplier-FK nachschlagen
            cur.execute("SELECT supplier_id FROM erp.suppliers WHERE supplier_code = %s",
                        (ev.get("supplier_reference"),))
            row = cur.fetchone()
            supplier_id = row[0] if row else None
            cur.execute("""
                INSERT INTO erp.products (product_code, product_name, category, supplier_id, event_timestamp)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (product_code) DO NOTHING
            """, (canonical, ev["product_name"], ev.get("category"), supplier_id,
                  ev.get("timestamp")))
            count("pg.products")

    # ── Schritt 2: WMS-Stammdaten ─────────────────────────────────────────────
    for ev in wms_events:
        if ev.get("event_type") == "WarehouseSKUCreated":
            # sku bleibt im WMS-Format (BAN_101), erp_product_code wird normalisiert (BAN-101)
            raw_sku  = ev["sku"]
            erp_code = normalize_key(ev["erp_product_code"])
            cur.execute("""
                INSERT INTO wms.warehouse_skus (sku, erp_product_code, event_timestamp)
                VALUES (%s, %s, %s)
                ON CONFLICT (sku) DO NOTHING
            """, (raw_sku, erp_code, ev.get("timestamp")))
            count("pg.warehouse_skus")

    # ── Schritt 3: TMS-Stammdaten ─────────────────────────────────────────────
    for ev in tms_events:
        et = ev.get("event_type")

        if et == "CarrierCreated":
            # JSON-Feld "carrier_id" hält den Business Key (z.B. "CAR-101") → carrier_code
            cur.execute("""
                INSERT INTO tms.carriers (carrier_code, carrier_name, event_timestamp)
                VALUES (%s, %s, %s)
                ON CONFLICT (carrier_code) DO NOTHING
            """, (ev["carrier_id"], ev["carrier_name"], ev.get("timestamp")))
            count("pg.carriers")

        elif et == "TransportProductReferenceCreated":
            erp_code  = normalize_key(ev["erp_product_code"])
            tms_ref   = ev["transport_product_reference"]  # TMS-Format beibehalten: ban-101
            cur.execute("""
                INSERT INTO tms.transport_product_references
                    (transport_product_reference, erp_product_code, event_timestamp)
                VALUES (%s, %s, %s)
                ON CONFLICT (transport_product_reference) DO NOTHING
            """, (tms_ref, erp_code, ev.get("timestamp")))
            count("pg.transport_refs")

    pg.commit()

    # ── Reparatur-Pass: supplier_id für Produkte setzen ───────────────────────
    # Notwendig, weil ProductCreated alphabetisch vor SupplierCreated verarbeitet
    # wird und der Supplier-Lookup daher im ersten Durchlauf fehlschlägt.
    for ev in erp_events:
        if ev.get("event_type") == "ProductCreated" and ev.get("supplier_reference"):
            cur.execute("""
                UPDATE erp.products
                SET supplier_id = s.supplier_id
                FROM erp.suppliers s
                WHERE erp.products.product_code = %s
                  AND s.supplier_code           = %s
                  AND erp.products.supplier_id IS NULL
            """, (normalize_key(ev["product_code"]), ev.get("supplier_reference")))
    pg.commit()

    # ── Schritt 4: ERP-Bewegungsdaten ─────────────────────────────────────────
    for ev in erp_events:
        et = ev.get("event_type")

        if et == "OrderCreated":
            cust_num = ev["customer"]["customer_number"]
            cur.execute("SELECT customer_id FROM erp.customers WHERE customer_number = %s",
                        (cust_num,))
            row = cur.fetchone()
            if not row:
                count("pg.orders_skipped_no_customer")
                continue
            customer_id = row[0]
            cur.execute("""
                INSERT INTO erp.orders
                    (order_reference, customer_id, delivery_priority, order_timestamp)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (order_reference) DO NOTHING
                RETURNING order_id
            """, (ev["order_reference"], customer_id,
                  ev.get("delivery_priority", "NORMAL"),
                  ev.get("timestamp")))
            res = cur.fetchone()
            if res:
                order_id = res[0]
                for item in ev.get("items", []):
                    canonical = normalize_key(item["product_code"])
                    cur.execute("SELECT product_id FROM erp.products WHERE product_code = %s",
                                (canonical,))
                    prow = cur.fetchone()
                    if prow:
                        cur.execute("""
                            INSERT INTO erp.order_items
                                (order_id, product_id, quantity, unit_price)
                            SELECT %s, %s, %s, %s
                            WHERE NOT EXISTS (
                                SELECT 1 FROM erp.order_items
                                WHERE order_id = %s AND product_id = %s
                            )
                        """, (order_id, prow[0], item["quantity"],
                              safe_float(item.get("unit_price")),
                              order_id, prow[0]))
                count("pg.orders")

        elif et == "BatchHarvested":
            canonical = normalize_key(ev["product_code"])
            cur.execute("SELECT product_id FROM erp.products WHERE product_code = %s",
                        (canonical,))
            prow = cur.fetchone()
            product_id = prow[0] if prow else None
            cur.execute("""
                INSERT INTO erp.batches
                    (batch_identifier, product_id, quantity, origin_country,
                     supply_chain_node, harvested_at, wms_sku, tms_product_reference)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (batch_identifier) DO NOTHING
            """, (ev["batch_identifier"], product_id,
                  safe_int(ev.get("quantity")), ev.get("origin_country"),
                  ev.get("supply_chain_node"), ev.get("timestamp"),
                  canonical.replace("-", "_"),
                  canonical.lower()))
            count("pg.batches")

    # ── Schritt 5: WMS-Eventdaten ─────────────────────────────────────────────
    for ev in wms_events:
        if ev.get("event_type") == "NodeProcessed":
            cur.execute("""
                SELECT node_id FROM wms.supply_chain_nodes
                WHERE node_code = %s
            """, (ev["supply_chain_node"],))
            nrow = cur.fetchone()
            if not nrow:
                count("pg.nodeprocessings_skipped")
                continue
            # sku bleibt im WMS-Format (z.B. BAN_108); Harmonisierung via mdm.source_mappings
            cur.execute("""
                INSERT INTO wms.node_processings
                    (node_id, batch_reference, sku, temperature, status, processed_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (batch_reference, node_id) DO NOTHING
            """, (nrow[0], ev["batch_reference"],
                  ev["sku"],
                  safe_float(ev.get("temperature")),
                  ev.get("status"), ev.get("timestamp")))
            count("pg.node_processings")

    # ── Schritt 6: TMS-Eventdaten ─────────────────────────────────────────────
    # Reihenfolge: zuerst TransportStarted (erzeugt shipments), erst danach
    # die Folge-Events. Sonst werden Positions/Completions/Deliveries
    # geskippt, weil das Shipment im Lookup noch nicht existiert.
    tms_sorted = sorted(
        tms_events,
        key=lambda e: 0 if e.get("event_type") == "TransportStarted" else 1
    )
    for ev in tms_sorted:
        et = ev.get("event_type")

        if et == "TransportStarted":
            carrier_code = ev["carrier"]["carrier_id"]
            cur.execute("SELECT carrier_id FROM tms.carriers WHERE carrier_code = %s",
                        (carrier_code,))
            crow = cur.fetchone()
            carrier_id = crow[0] if crow else None
            tms_ref = ev["cargo_product_reference"]  # TMS-Format beibehalten: ban-101
            cur.execute("""
                INSERT INTO tms.shipments
                    (shipment_identifier, carrier_id, cargo_product_reference,
                     source_node, target_node, transport_mode,
                     started_at, estimated_arrival)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (shipment_identifier) DO NOTHING
            """, (ev["shipment_identifier"], carrier_id, tms_ref,
                  ev.get("source_node"), ev.get("target_node"),
                  ev.get("transport_mode"),
                  ev.get("timestamp"), ev.get("estimated_arrival")))
            count("pg.shipments")

        elif et == "ShipmentPositionUpdated":
            cur.execute("SELECT shipment_id FROM tms.shipments WHERE shipment_identifier = %s",
                        (ev["shipment_identifier"],))
            srow = cur.fetchone()
            if not srow:
                count("pg.positions_skipped")
                continue
            coords = ev.get("coordinates", {})
            cur.execute("""
                INSERT INTO tms.shipment_positions
                    (shipment_id, latitude, longitude,
                     container_temperature, speed_kmh, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (shipment_id, recorded_at) DO NOTHING
            """, (srow[0],
                  safe_float(coords.get("latitude")),
                  safe_float(coords.get("longitude")),
                  safe_float(ev.get("container_temperature")),
                  safe_float(ev.get("speed_kmh")),
                  ev.get("timestamp")))
            count("pg.positions")

        elif et == "TransportCompleted":
            cur.execute("SELECT shipment_id FROM tms.shipments WHERE shipment_identifier = %s",
                        (ev["shipment_identifier"],))
            srow = cur.fetchone()
            if not srow:
                count("pg.completions_skipped")
                continue
            cur.execute("""
                INSERT INTO tms.transport_completions
                    (shipment_id, arrival_node, delay_minutes, completed_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (shipment_id) DO NOTHING
            """, (srow[0], ev.get("arrival_node"),
                  safe_int(ev.get("delay_minutes")),
                  ev.get("timestamp")))
            count("pg.completions")

        elif et == "DeliveryCompleted":
            cur.execute("SELECT shipment_id FROM tms.shipments WHERE shipment_identifier = %s",
                        (ev["shipment_identifier"],))
            srow = cur.fetchone()
            if not srow:
                count("pg.deliveries_skipped")
                continue
            cur.execute("""
                INSERT INTO tms.deliveries
                    (shipment_id, delivery_status, received_by,
                     cargo_product_reference, delivered_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (shipment_id) DO NOTHING
            """, (srow[0], ev.get("delivery_status"),
                  ev.get("received_by"),
                  ev.get("cargo_product_reference"),
                  ev.get("timestamp")))
            count("pg.deliveries")

    pg.commit()
    cur.close()


# =============================================================================
# LOAD – MDM Golden Records + Source Mappings
# Läuft nach den Stammdaten-Schritten, da erp.products bereits befüllt sein muss.
# Erzeugt für jedes Produkt 1 Golden Record + 3 Source Mappings (ERP/WMS/TMS).
# =============================================================================
def _upsert_golden(cur, entity_type_id, canonical_key, canonical_name, score=0.95):
    """Legt einen Golden Record an oder gibt die existierende golden_id zurück."""
    cur.execute("""
        INSERT INTO mdm.golden_records
            (entity_type_id, canonical_key, canonical_name, status, quality_score)
        VALUES (%s, %s, %s, 'ACTIVE', %s)
        ON CONFLICT (entity_type_id, canonical_key) DO NOTHING
        RETURNING golden_id
    """, (entity_type_id, canonical_key, canonical_name, score))
    res = cur.fetchone()
    if res:
        return res[0]
    cur.execute("""
        SELECT golden_id FROM mdm.golden_records
        WHERE entity_type_id = %s AND canonical_key = %s
    """, (entity_type_id, canonical_key))
    return cur.fetchone()[0]


def _upsert_mapping(cur, golden_id, source_system, source_key, is_canonical):
    """Registriert ein Quellsystem-Schlüsselmapping (idempotent)."""
    cur.execute("""
        INSERT INTO mdm.source_mappings
            (golden_id, source_system, source_key, normalized_key, is_canonical)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_system, source_key) DO NOTHING
    """, (golden_id, source_system, source_key,
          source_key.strip().lower().replace("_", "-"), is_canonical))


def load_mdm(pg):
    cur = pg.cursor()

    # Entity-Type-Lookups
    cur.execute("SELECT entity_type_code, entity_type_id FROM mdm.entity_types")
    type_ids = dict(cur.fetchall())

    # ── PRODUCT (3 Quellsysteme, echte Schlüsselharmonisierung) ─────────────
    if "PRODUCT" in type_ids:
        cur.execute("SELECT product_code, product_name FROM erp.products ORDER BY product_code")
        for product_code, product_name in cur.fetchall():
            gid = _upsert_golden(cur, type_ids["PRODUCT"], product_code, product_name, 0.95)
            _upsert_mapping(cur, gid, "ERP", product_code,                 True)
            _upsert_mapping(cur, gid, "WMS", product_code.replace("-","_"), False)
            _upsert_mapping(cur, gid, "TMS", product_code.lower(),          False)
            count("mdm.golden_records.product")

    # ── CUSTOMER (Single-Source: ERP) ───────────────────────────────────────
    # Mapping nur für ERP, da Kunden ausschließlich im ERP entstehen.
    # Score 1.00, weil keine Schlüssel-Konflikte existieren.
    if "CUSTOMER" in type_ids:
        cur.execute("SELECT customer_number, customer_name FROM erp.customers ORDER BY customer_number")
        for cust_num, cust_name in cur.fetchall():
            gid = _upsert_golden(cur, type_ids["CUSTOMER"], cust_num, cust_name, 1.00)
            _upsert_mapping(cur, gid, "ERP", cust_num, True)
            count("mdm.golden_records.customer")

    # ── SUPPLIER (Single-Source: ERP) ───────────────────────────────────────
    if "SUPPLIER" in type_ids:
        cur.execute("SELECT supplier_code, supplier_name FROM erp.suppliers ORDER BY supplier_code")
        for sup_code, sup_name in cur.fetchall():
            gid = _upsert_golden(cur, type_ids["SUPPLIER"], sup_code, sup_name, 1.00)
            _upsert_mapping(cur, gid, "ERP", sup_code, True)
            count("mdm.golden_records.supplier")

    # ── CARRIER (Single-Source: TMS) ────────────────────────────────────────
    if "CARRIER" in type_ids:
        cur.execute("SELECT carrier_code, carrier_name FROM tms.carriers ORDER BY carrier_code")
        for car_code, car_name in cur.fetchall():
            gid = _upsert_golden(cur, type_ids["CARRIER"], car_code, car_name, 1.00)
            _upsert_mapping(cur, gid, "TMS", car_code, True)
            count("mdm.golden_records.carrier")

    # ── SUPPLY_CHAIN_NODE (Multi-Source: WMS und TMS, identische Codes) ─────
    # WMS und TMS verwenden denselben node_code, registrieren wird trotzdem
    # für Vollständigkeit des Datenkatalogs.
    if "SUPPLY_CHAIN_NODE" in type_ids:
        cur.execute("SELECT node_code, node_name FROM wms.supply_chain_nodes ORDER BY sequence_order")
        for node_code, node_name in cur.fetchall():
            gid = _upsert_golden(cur, type_ids["SUPPLY_CHAIN_NODE"], node_code, node_name, 1.00)
            _upsert_mapping(cur, gid, "WMS", node_code, True)
            _upsert_mapping(cur, gid, "TMS", node_code, False)
            count("mdm.golden_records.node")

    pg.commit()
    cur.close()


# =============================================================================
# LOAD – MongoDB
# =============================================================================
def load_mongodb(erp_events, wms_events, tms_events, mongo_db):
    se  = mongo_db["shipment_events"]
    ne  = mongo_db["node_events"]
    bt  = mongo_db["batch_tracking"]
    oe  = mongo_db["order_events"]

    # Idempotentes Index-Setup: bestehende benannte Indizes erst droppen, dann neu anlegen.
    def _safe_create_index(coll, keys, **kwargs):
        name = kwargs.get("name")
        if name:
            try:
                coll.drop_index(name)
            except Exception:
                pass
        coll.create_index(keys, **kwargs)

    _safe_create_index(oe, "order_reference", unique=True)
    _safe_create_index(ne, [("batch_reference", 1), ("supply_chain_node", 1)],
                       unique=True, name="uq_node_event")
    _safe_create_index(se, "shipment_identifier", unique=True)
    _safe_create_index(bt, "batch_identifier", unique=True)
    _safe_create_index(se, "created_at", expireAfterSeconds=7_776_000,
                       name="ttl_shipment_lifecycle")

    # ── order_events: OrderCreated als Basis-Dokument ─────────────────────────
    for ev in erp_events:
        if ev.get("event_type") == "OrderCreated":
            res = oe.update_one(
                {"order_reference": ev["order_reference"]},
                {"$setOnInsert": ev.copy()},
                upsert=True
            )
            if res.upserted_id is not None:
                count("mongo.order_events")

    # ── node_events: 1 Dokument pro batch+node mit Quality-Flags ─────────────
    for ev in wms_events:
        if ev.get("event_type") == "NodeProcessed":
            temp    = safe_float(ev.get("temperature"))
            temp_ok = temp is not None and 10.0 <= temp <= 15.0
            doc = {
                "batch_reference":        ev["batch_reference"],
                "supply_chain_node":      ev["supply_chain_node"],
                "sku":                    ev.get("sku"),
                "canonical_product_code": normalize_key(ev.get("sku", "")),
                "temperature":            temp,
                "temperature_within_range": temp_ok,
                "status":                 ev.get("status"),
                "processed_at":           ev.get("timestamp"),
                "quality_flags": {
                    "temperature_ok": temp_ok,
                    "min_allowed":    10.0,
                    "max_allowed":    15.0
                }
            }
            res = ne.update_one(
                {"batch_reference":   ev["batch_reference"],
                 "supply_chain_node": ev["supply_chain_node"]},
                {"$setOnInsert": doc},
                upsert=True
            )
            if res.upserted_id is not None:
                count("mongo.node_events")

    # ── batch_tracking: BatchHarvested als Basis-Dokument ────────────────────
    # Muss vor dem NodeProcessed-Pass laufen, damit das Basis-Dokument existiert.
    for ev in erp_events:
        if ev.get("event_type") == "BatchHarvested":
            bt.update_one(
                {"batch_identifier": ev["batch_identifier"]},
                {"$setOnInsert": {
                    "batch_identifier":       ev["batch_identifier"],
                    "erp_product_code":       normalize_key(ev["product_code"]),
                    "wms_sku":                ev.get("wms_sku"),
                    "tms_product_reference":  ev.get("tms_product_reference"),
                    "origin_country":         ev.get("origin_country"),
                    "quantity":               safe_int(ev.get("quantity")),
                    "harvested_at":           ev.get("timestamp"),
                    "current_node":           ev.get("supply_chain_node"),
                    "nodes_processed":        []
                }},
                upsert=True
            )

    # ── batch_tracking: vollständige Node-Objekte einbetten ──────────────────
    for ev in wms_events:
        if ev.get("event_type") == "NodeProcessed":
            temp = safe_float(ev.get("temperature"))
            node_entry = {
                "node":         ev["supply_chain_node"],
                "temperature":  temp,
                "status":       ev.get("status"),
                "processed_at": ev.get("timestamp")
            }
            # $addToSet verhindert Duplikate bei idempotenten Mehrfach-Läufen
            bt.update_one(
                {"batch_identifier": ev["batch_reference"]},
                {
                    "$addToSet": {"nodes_processed": node_entry},
                    "$set":      {"current_node": ev["supply_chain_node"],
                                  "updated_at":   ev.get("timestamp")}
                },
                upsert=True
            )
            count("mongo.batch_tracking")

    # ── shipment_events: Lifecycle-Modell, TransportStarted zuerst ───────────
    # TransportStarted erzeugt das Basis-Dokument; alle Folge-Events werden
    # per $push in das events[]-Array des bestehenden Dokuments eingebettet.
    tms_sorted = sorted(
        tms_events,
        key=lambda e: 0 if e.get("event_type") == "TransportStarted" else 1
    )
    for ev in tms_sorted:
        et  = ev.get("event_type")
        sid = ev.get("shipment_identifier")
        if not sid:
            continue

        if et == "TransportStarted":
            doc = {
                "shipment_identifier":      sid,
                "cargo_product_reference":  normalize_key(ev.get("cargo_product_reference", "")),
                "source_node":              ev.get("source_node"),
                "target_node":              ev.get("target_node"),
                "transport_mode":           ev.get("transport_mode"),
                "carrier":                  ev.get("carrier"),
                "estimated_arrival":        ev.get("estimated_arrival"),
                "started_at":               ev.get("timestamp"),
                "delivery_status":          "IN_TRANSIT",
                "events": [{"event_type": "TransportStarted",
                            "timestamp":  ev.get("timestamp")}],
                "created_at": ev.get("timestamp"),
                "updated_at": ev.get("timestamp")
            }
            res = se.update_one(
                {"shipment_identifier": sid},
                {"$setOnInsert": doc},
                upsert=True
            )
            if res.upserted_id is not None:
                count("mongo.shipment_events")

        elif et == "ShipmentPositionUpdated":
            event_entry = {
                "event_type":            "ShipmentPositionUpdated",
                "coordinates":           ev.get("coordinates"),
                "container_temperature": safe_float(ev.get("container_temperature")),
                "speed_kmh":             safe_float(ev.get("speed_kmh")),
                "timestamp":             ev.get("timestamp")
            }
            # Idempotenz: nur einfügen wenn dieser GPS-Zeitstempel noch nicht existiert
            se.update_one(
                {"shipment_identifier": sid,
                 "events": {"$not": {"$elemMatch": {
                     "event_type": "ShipmentPositionUpdated",
                     "timestamp":  ev.get("timestamp")}}}},
                {
                    "$push": {"events": event_entry},
                    "$set":  {"updated_at": ev.get("timestamp")}
                }
            )
            count("mongo.shipment_positions")

        elif et == "TransportCompleted":
            event_entry = {
                "event_type":    "TransportCompleted",
                "arrival_node":  ev.get("arrival_node"),
                "delay_minutes": safe_int(ev.get("delay_minutes")),
                "timestamp":     ev.get("timestamp")
            }
            se.update_one(
                {"shipment_identifier": sid,
                 "events": {"$not": {"$elemMatch": {"event_type": "TransportCompleted"}}}},
                {
                    "$push": {"events": event_entry},
                    "$set": {
                        "delay_minutes": safe_int(ev.get("delay_minutes")),
                        "completed_at":  ev.get("timestamp"),
                        "updated_at":    ev.get("timestamp")
                    }
                }
            )
            count("mongo.shipment_completions")

        elif et == "DeliveryCompleted":
            event_entry = {
                "event_type":      "DeliveryCompleted",
                "delivery_status": ev.get("delivery_status"),
                "received_by":     ev.get("received_by"),
                "timestamp":       ev.get("timestamp")
            }
            se.update_one(
                {"shipment_identifier": sid,
                 "events": {"$not": {"$elemMatch": {"event_type": "DeliveryCompleted"}}}},
                {
                    "$push": {"events": event_entry},
                    "$set": {
                        "delivery_status": ev.get("delivery_status"),
                        "updated_at":      ev.get("timestamp")
                    }
                }
            )
            count("mongo.shipment_deliveries")


# =============================================================================
# LOAD – Redis
# =============================================================================
def load_redis(erp_events, tms_events, r):
    """Befüllt Redis mit Echtzeitstatus, GPS-Verlauf, Alerts und Countern."""

    # ── ERP: ProductCreated → Produktcache (alle 10 Produkte, unabhängig von Orders) ──
    for ev in erp_events:
        if ev.get("event_type") != "ProductCreated":
            continue
        pcode = normalize_key(ev.get("product_code", ""))
        if pcode and not r.exists(f"cache:product:{pcode}"):
            r.hset(f"cache:product:{pcode}", mapping={
                "description": ev.get("product_name", ""),
                "unit_price":  str(ev.get("unit_price", "")),
            })
            r.expire(f"cache:product:{pcode}", 3600)

    # ── ERP: OrderCreated → Order-Status, Metadaten, Timeline, Produktcache ───
    for ev in erp_events:
        if ev.get("event_type") != "OrderCreated":
            continue
        ref      = ev.get("order_reference", "")
        customer = ev.get("customer", {})
        ts       = ev.get("timestamp", "")
        priority = ev.get("delivery_priority", "NORMAL")
        TTL_ORDER = 86400 * 30  # 30 Tage: Orders bleiben bis Abschluss relevant

        r.set(f"order:status:{ref}", "CREATED", ex=TTL_ORDER)

        r.hset(f"order:meta:{ref}", mapping={
            "customer_number": customer.get("customer_number", ""),
            "customer_name":   customer.get("customer_name", ""),
            "priority":        priority,
            "created_at":      ts,
        })
        r.expire(f"order:meta:{ref}", TTL_ORDER)

        r.rpush(f"order:timeline:{ref}", f"{ts} – CREATED")
        r.expire(f"order:timeline:{ref}", TTL_ORDER)

        # Tages-Counter mit automatischem Ablauf um Mitternacht
        r.incr("system:counter:orders_today")
        midnight = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
        r.expireat("system:counter:orders_today",
                   int(midnight.timestamp()))

        # Produktstammdaten aus OrderItems cachen (vermeidet PostgreSQL-Roundtrip)
        for item in ev.get("items", []):
            pcode = normalize_key(item.get("product_code", ""))
            if pcode and not r.exists(f"cache:product:{pcode}"):
                r.hset(f"cache:product:{pcode}", mapping={
                    "description": item.get("description", ""),
                    "unit_price":  str(item.get("unit_price", "")),
                })
                r.expire(f"cache:product:{pcode}", 3600)  # 1 Stunde
        count("redis.orders")

    # ── TMS-Events ────────────────────────────────────────────────────────────
    for ev in tms_events:
        et  = ev.get("event_type")
        sid = ev.get("shipment_identifier", "")

        if et == "TransportStarted":
            carrier = ev.get("carrier", {})
            r.set(f"shipment:status:{sid}", "IN_TRANSIT", ex=86400 * 7)
            r.hset(f"shipment:info:{sid}", mapping={
                "transport_mode": ev.get("transport_mode", ""),
                "source_node":    ev.get("source_node", ""),
                "target_node":    ev.get("target_node", ""),
                "started_at":     ev.get("timestamp", ""),
                "carrier_id":     carrier.get("carrier_id", ""),
            })
            r.expire(f"shipment:info:{sid}", 86400 * 7)
            # Aktive Transporte für Dashboard-Counter hochzählen
            r.incr("system:counter:active_shipments")
            count("redis.status_set")

        elif et == "ShipmentPositionUpdated":
            coords = ev.get("coordinates", {})
            lat    = coords.get("latitude", "")
            lon    = coords.get("longitude", "")
            temp   = safe_float(ev.get("container_temperature"))
            ts     = ev.get("timestamp", "")

            # Aktuellste Position (wird bei jedem Update überschrieben)
            r.hset(f"shipment:position:{sid}", mapping={
                "latitude":    str(lat),
                "longitude":   str(lon),
                "temperature": str(temp) if temp is not None else "",
                "speed_kmh":   str(ev.get("speed_kmh", "")),
                "updated_at":  ts,
            })
            r.expire(f"shipment:position:{sid}", 3600)  # 1 Stunde: GPS veraltet schnell

            # Kurzer Positionsverlauf für Live-Map (letzten 3 Tage reichen)
            import json as _json
            score = int(datetime.fromisoformat(ts).timestamp()) if ts else 0
            r.zadd(f"shipment:route:{sid}",
                   {_json.dumps({"lat": lat, "lon": lon, "temp": temp, "ts": ts}): score})
            r.expire(f"shipment:route:{sid}", 86400 * 3)

            # Kühlketten-Alert: Bananen müssen zwischen 10 °C und 15 °C bleiben
            if temp is not None and not (10.0 <= temp <= 15.0):
                r.set(f"shipment:alert:temperature:{sid}", "ALERT", ex=86400)
                r.incr("system:counter:temperature_alerts_active")

                # Tages-Verletzungsliste sortiert nach Temperaturwert für Priorisierung
                date_key = datetime.now().strftime("%Y%m%d")
                member   = f"{sid}:{ts}:temp={temp}"
                r.zadd(f"monitoring:temp_violations:{date_key}", {member: temp})
                r.expire(f"monitoring:temp_violations:{date_key}", 86400 * 7)
                count("redis.temp_violations")
            count("redis.positions")

        elif et == "DeliveryCompleted":
            status = ev.get("delivery_status", "UNKNOWN")
            r.set(f"shipment:status:{sid}", status, ex=86400 * 30)
            r.incr(f"system:counter:deliveries_{status.lower()}")
            # Aktiven Transport abmelden; nicht unter 0 fallen
            current = r.get("system:counter:active_shipments")
            if current and int(current) > 0:
                r.decr("system:counter:active_shipments")
            count("redis.delivery_status")

    r.incr("system:counter:etl_runs")


# =============================================================================
# LOAD – Neo4j
# =============================================================================
def load_neo4j(erp_events, tms_events, driver):
    with driver.session() as session:
        for ev in erp_events:
            if ev.get("event_type") == "OrderCreated":
                order_ref  = ev["order_reference"]
                cust_num   = ev["customer"]["customer_number"]
                cust_name  = ev["customer"]["customer_name"]
                priority   = ev.get("delivery_priority", "NORMAL")
                ts         = ev.get("timestamp", "")
                session.run("""
                    MERGE (c:Customer {customer_number: $cn})
                      SET c.customer_name = $name
                    MERGE (o:Order {order_reference: $ref})
                      SET o.delivery_priority = $prio, o.order_date = $ts
                    MERGE (c)-[:PLACED {timestamp: $ts}]->(o)
                """, cn=cust_num, name=cust_name, ref=order_ref, prio=priority, ts=ts)
                for item in ev.get("items", []):
                    session.run("""
                        MERGE (p:Product {product_code: $pc})
                        MERGE (o:Order {order_reference: $ref})
                        MERGE (o)-[:CONTAINS {quantity: $qty, unit_price: $price}]->(p)
                    """, pc=normalize_key(item["product_code"]),
                         ref=order_ref, qty=item["quantity"],
                         price=safe_float(item.get("unit_price")))
                count("neo4j.orders")

            elif ev.get("event_type") == "BatchHarvested":
                session.run("""
                    MERGE (b:Batch {batch_identifier: $bid})
                      SET b.quantity = $qty, b.origin_country = $oc, b.product_code = $pc
                    WITH b
                    OPTIONAL MATCH (o:Order)
                    WHERE EXISTS { MATCH (o)-[:CONTAINS]->(p:Product {product_code: $pc}) }
                    FOREACH (_ IN CASE WHEN o IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (o)-[:TRIGGERED]->(b)
                    )
                """, bid=ev["batch_identifier"],
                     qty=safe_int(ev.get("quantity")),
                     oc=ev.get("origin_country"),
                     pc=normalize_key(ev["product_code"]))
                count("neo4j.batches")

        for ev in tms_events:
            et = ev.get("event_type")
            if et == "TransportStarted":
                sid = ev["shipment_identifier"]
                prod_code = normalize_key(ev.get("cargo_product_reference", ""))
                session.run("""
                    MERGE (s:Shipment {shipment_identifier: $sid})
                      SET s.transport_mode = $mode, s.started_at = $ts,
                          s.cargo_product_reference = $prod
                    WITH s
                    MATCH (from:SupplyChainNode {node_code: $src})
                    MATCH (to:SupplyChainNode   {node_code: $tgt})
                    MERGE (s)-[:FROM]->(from)
                    MERGE (s)-[:TO]->(to)
                    WITH s
                    MATCH (c:Carrier {carrier_code: $cid})
                    MERGE (s)-[:TRANSPORTED_BY]->(c)
                """, sid=sid, mode=ev.get("transport_mode"),
                     ts=ev.get("timestamp"), prod=prod_code,
                     src=ev.get("source_node"), tgt=ev.get("target_node"),
                     cid=ev["carrier"]["carrier_id"])
                # TRANSPORTED_VIA: Batch → Shipment (ermöglicht DeliveryCompleted-Pfad)
                session.run("""
                    MATCH (b:Batch {product_code: $prod})
                    MATCH (s:Shipment {shipment_identifier: $sid})
                    MERGE (b)-[:TRANSPORTED_VIA]->(s)
                """, prod=prod_code, sid=sid)
                count("neo4j.shipments")

            elif et == "DeliveryCompleted":
                session.run("""
                    MATCH (s:Shipment {shipment_identifier: $sid})
                    MATCH (c:Customer)
                    WHERE EXISTS {
                        MATCH (c)-[:PLACED]->(o:Order)-[:TRIGGERED]->(b:Batch)
                              -[:TRANSPORTED_VIA]->(s)
                    }
                    MERGE (s)-[:DELIVERED_TO {
                        delivery_status: $status,
                        received_by: $recv,
                        delivered_at: $ts
                    }]->(c)
                """, sid=ev["shipment_identifier"],
                     status=ev.get("delivery_status"),
                     recv=ev.get("received_by"),
                     ts=ev.get("timestamp"))
                count("neo4j.deliveries")


# =============================================================================
# MAIN
# =============================================================================
def main():
    print("=" * 60)
    print("ETL-Prozess: Banana Supply Chain")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ── Verbindungen aufbauen ─────────────────────────────────────────────────
    print("\n[1/7] Verbindungen aufbauen...")
    pg    = psycopg2.connect(PG_DSN)
    mongo = MongoClient(MONGO_URI)["logistics"]
    r     = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    print("  PostgreSQL, MongoDB, Redis, Neo4j – OK")

    # ── Extract ───────────────────────────────────────────────────────────────
    print("\n[2/7] Events laden (Extract)...")
    erp_events = extract_events("erp")
    wms_events = extract_events("wms")
    tms_events = extract_events("tms")
    print(f"  ERP: {len(erp_events)} Events")
    print(f"  WMS: {len(wms_events)} Events")
    print(f"  TMS: {len(tms_events)} Events")

    # ── Load: PostgreSQL ──────────────────────────────────────────────────────
    print("\n[3/7] PostgreSQL laden...")
    load_postgres(erp_events, wms_events, tms_events, pg)

    # ── Load: MDM ─────────────────────────────────────────────────────────────
    print("[4/7] MDM Golden Records + Source Mappings laden...")
    load_mdm(pg)

    # ── Load: MongoDB ─────────────────────────────────────────────────────────
    print("[5/7] MongoDB laden...")
    load_mongodb(erp_events, wms_events, tms_events, mongo)

    # ── Load: Redis ───────────────────────────────────────────────────────────
    print("[6/7] Redis laden...")
    load_redis(erp_events, tms_events, r)

    # ── Load: Neo4j ───────────────────────────────────────────────────────────
    print("[7/7] Neo4j laden...")
    load_neo4j(erp_events, tms_events, neo4j_driver)

    # ── Verbindungen schließen ─────────────────────────────────────────────────
    pg.close()
    neo4j_driver.close()

    # ── Statistik ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ETL-Statistik:")
    print("=" * 60)
    for k, v in sorted(stats.items()):
        system = k.split(".")[0].upper()
        label  = k.split(".")[1]
        print(f"  {system:12s}  {label:30s}  {v:5d}")
    print(f"\nFertig: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
