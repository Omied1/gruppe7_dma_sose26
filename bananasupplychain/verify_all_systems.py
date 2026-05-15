"""
Technische Nachweise – systemübergreifende Verifikation
Banana Supply Chain, Datenmanagement und Analytics, SoSe 26

Prüft nach einem ETL-Lauf, ob alle 5 Systeme korrekt befüllt wurden.
Für PostgreSQL-Checks: sql/09_verification_queries.sql (vollständiger FK-Test).
Dieses Skript deckt MongoDB, Redis, Neo4j und MinIO ab.

Ausführung:
    cd bananasupplychain
    python3 verify_all_systems.py

Voraussetzungen: Docker-Container laufen (docker-compose up -d),
    ETL wurde ausgeführt (etl_load.py)
"""

import sys

try:
    from pymongo import MongoClient
    import redis as redis_lib
    from neo4j import GraphDatabase
    from minio import Minio
except ImportError as e:
    print(f"Fehlende Abhängigkeit: {e}")
    print("Installieren mit: pip install pymongo redis neo4j minio")
    sys.exit(1)

MONGO_URI  = "mongodb://localhost:27017"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
NEO4J_URI  = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "password"
MINIO_EP   = "localhost:9000"
MINIO_KEY  = "admin"
MINIO_SEC  = "password"

# Sammelt alle Prüfergebnisse; PASS = 0 Verstöße / korrekte Zahl
results: list[dict] = []

def check(system: str, name: str, actual, expected, op: str = "eq"):
    """Registriert ein Prüfergebnis und gibt es sofort aus."""
    if op == "eq":
        passed = actual == expected
        exp_str = str(expected)
    elif op == "ge":
        passed = actual >= expected
        exp_str = f"≥ {expected}"
    elif op == "in":
        passed = actual in expected
        exp_str = str(expected)
    else:
        passed = bool(actual)
        exp_str = "truthy"

    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}: {actual} (erwartet {exp_str})")
    results.append({"system": system, "name": name, "status": status,
                    "actual": actual, "expected": exp_str})


# =============================================================================
# MongoDB
# =============================================================================
def verify_mongodb():
    print("\n--- MongoDB ---")
    db = MongoClient(MONGO_URI)["logistics"]

    # Collection-Counts
    check("MongoDB", "shipment_events (Anzahl Shipments)", db["shipment_events"].count_documents({}),   60, "ge")
    check("MongoDB", "node_events (WMS NodeProcessed)",    db["node_events"].count_documents({}),       60, "ge")
    check("MongoDB", "batch_tracking (Batches)",           db["batch_tracking"].count_documents({}),    10, "ge")
    check("MongoDB", "order_events (Orders)",              db["order_events"].count_documents({}),      10, "ge")

    # Index-Prüfung: shipment_events muss unique-Index auf shipment_identifier haben
    idx_names = [i["name"] for i in db["shipment_events"].list_indexes()]
    has_unique = any("shipment_identifier" in n for n in idx_names)
    check("MongoDB", "shipment_events unique-Index vorhanden", has_unique, True, "eq")

    # TTL-Index auf shipment_events (Ablauf nach 90 Tagen)
    ttl_idx = [i for i in db["shipment_events"].list_indexes()
               if i.get("expireAfterSeconds") is not None]
    check("MongoDB", "shipment_events TTL-Index vorhanden", len(ttl_idx), 1, "ge")

    # Strukturprüfung: ein Shipment-Dokument muss ein events[]-Array enthalten
    sample = db["shipment_events"].find_one({"events": {"$exists": True, "$ne": []}})
    check("MongoDB", "shipment_events enthält events[]-Array", sample is not None, True, "eq")

    # Strukturprüfung: batch_tracking muss nodes_processed enthalten
    bt_sample = db["batch_tracking"].find_one({"nodes_processed": {"$exists": True}})
    check("MongoDB", "batch_tracking enthält nodes_processed[]", bt_sample is not None, True, "eq")

    # Kühlketten-Flag: temperature_within_range vorhanden
    flag_sample = db["node_events"].find_one({"quality_flags": {"$exists": True}})
    check("MongoDB", "node_events enthält quality_flags", flag_sample is not None, True, "eq")


# =============================================================================
# Redis
# =============================================================================
def verify_redis():
    print("\n--- Redis ---")
    r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    # Key-Pattern-Counts
    shipment_keys = len(r.keys("shipment:status:*"))
    check("Redis", "shipment:status:* (Anzahl)", shipment_keys, 60, "ge")

    order_keys = len(r.keys("order:status:*"))
    check("Redis", "order:status:* (Anzahl)", order_keys, 10, "ge")

    position_keys = len(r.keys("shipment:position:*"))
    check("Redis", "shipment:position:* (aktuelle GPS-Positionen)", position_keys, 1, "ge")

    route_keys = len(r.keys("shipment:route:*"))
    check("Redis", "shipment:route:* (GPS-Verlauf Sorted Sets)", route_keys, 1, "ge")

    product_cache = len(r.keys("cache:product:*"))
    check("Redis", "cache:product:* (Produktcache)", product_cache, 10, "ge")

    # System-Counter vorhanden?
    etl_runs = r.get("system:counter:etl_runs")
    check("Redis", "system:counter:etl_runs gesetzt", etl_runs is not None, True, "eq")

    # Key-Typen prüfen
    sample_sid = None
    for key in r.keys("shipment:status:*")[:1]:
        sample_sid = key.replace("shipment:status:", "")

    if sample_sid:
        ktype = r.type(f"shipment:status:{sample_sid}")
        check("Redis", f"shipment:status:{sample_sid} ist STRING", ktype, "string", "eq")

        ktype_info = r.type(f"shipment:info:{sample_sid}")
        check("Redis", f"shipment:info:{sample_sid} ist HASH", ktype_info, "hash", "eq")

    # Sorted-Set-Typ für Route prüfen
    for key in r.keys("shipment:route:*")[:1]:
        ktype_route = r.type(key)
        check("Redis", f"{key} ist ZSET", ktype_route, "zset", "eq")

    # Order-Timeline (LIST) prüfen
    for key in r.keys("order:timeline:*")[:1]:
        ktype_tl = r.type(key)
        check("Redis", f"{key} ist LIST", ktype_tl, "list", "eq")


# =============================================================================
# Neo4j
# =============================================================================
def verify_neo4j():
    print("\n--- Neo4j ---")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as s:

        # Node-Counts je Typ
        result = s.run("MATCH (n) RETURN labels(n)[0] AS typ, COUNT(n) AS cnt")
        node_counts = {row["typ"]: row["cnt"] for row in result}

        check("Neo4j", "Supplier-Nodes",        node_counts.get("Supplier", 0),          10, "ge")
        check("Neo4j", "Customer-Nodes",         node_counts.get("Customer", 0),          10, "ge")
        check("Neo4j", "Product-Nodes",          node_counts.get("Product", 0),           10, "ge")
        check("Neo4j", "SupplyChainNode-Nodes",  node_counts.get("SupplyChainNode", 0),    7, "ge")
        check("Neo4j", "Carrier-Nodes",          node_counts.get("Carrier", 0),            5, "ge")
        check("Neo4j", "Order-Nodes",            node_counts.get("Order", 0),             21, "ge")
        check("Neo4j", "Batch-Nodes",            node_counts.get("Batch", 0),             20, "ge")
        check("Neo4j", "Shipment-Nodes",         node_counts.get("Shipment", 0),         121, "ge")

        total_nodes = sum(node_counts.values())
        check("Neo4j", "Nodes gesamt", total_nodes, 200, "ge")

        # Relationship-Counts
        rel_result = s.run("MATCH ()-[r]->() RETURN COUNT(r) AS cnt")
        total_rels = rel_result.single()["cnt"]
        check("Neo4j", "Relationships gesamt", total_rels, 47, "ge")

        # 6-Hop-Pfad Plantation → Retail
        path_result = s.run("""
            MATCH (start:SupplyChainNode {node_code: "BANANA_PLANTATION"}),
                  (end:SupplyChainNode   {node_code: "RETAIL_STORE"}),
                  path = shortestPath((start)-[:CONNECTED_TO*]->(end))
            RETURN length(path) AS hops
        """)
        row = path_result.single()
        hops = row["hops"] if row else 0
        check("Neo4j", "Kürzester Pfad PLANTATION→RETAIL (Hops)", hops, 6, "eq")

        # Alle Produkte haben einen Lieferanten (SUPPLIES)
        orphan_result = s.run("""
            MATCH (p:Product)
            WHERE NOT EXISTS { MATCH (:Supplier)-[:SUPPLIES]->(p) }
            RETURN COUNT(p) AS cnt
        """)
        orphans = orphan_result.single()["cnt"]
        check("Neo4j", "Produkte ohne SUPPLIES-Beziehung (Soll: 0)", orphans, 0, "eq")

        # Demo-Batch: alle 7 Stationen PROCESSED_AT
        batch_result = s.run("""
            MATCH (b:Batch {batch_identifier: "BATCH-9c6818ad-29fb-4896-922b-b56bb2b2086b"})
                  -[:PROCESSED_AT]->(n:SupplyChainNode)
            RETURN COUNT(n) AS stationen
        """)
        stationen = batch_result.single()["stationen"]
        check("Neo4j", "Demo-Batch PROCESSED_AT (alle 7 Stationen)", stationen, 7, "eq")

    driver.close()


# =============================================================================
# MinIO
# =============================================================================
def verify_minio():
    print("\n--- MinIO ---")
    client = Minio(MINIO_EP, access_key=MINIO_KEY, secret_key=MINIO_SEC, secure=False)

    # Buckets vorhanden?
    expected_buckets = {"invoices", "delivery-notes", "transport-docs", "batch-certificates"}
    existing_buckets = {b.name for b in client.list_buckets()}

    for bucket in expected_buckets:
        check("MinIO", f"Bucket '{bucket}' vorhanden", bucket in existing_buckets, True, "eq")

    # Objekt-Counts je Bucket
    for bucket in ["delivery-notes", "invoices"]:
        if bucket not in existing_buckets:
            continue
        count = sum(1 for _ in client.list_objects(bucket, recursive=True))
        if bucket == "delivery-notes":
            check("MinIO", f"{bucket}: Anzahl Objekte", count, 60, "ge")
        elif bucket == "invoices":
            check("MinIO", f"{bucket}: Anzahl Objekte", count, 1, "ge")

    # Objekt-Metadaten: ein Lieferschein muss shipment_identifier-Tag haben
    for bucket in ["delivery-notes"]:
        if bucket not in existing_buckets:
            continue
        for obj in client.list_objects(bucket, recursive=True):
            stat = client.stat_object(bucket, obj.object_name)
            has_meta = "x-amz-meta-shipment-identifier" in stat.metadata or \
                       "shipment_identifier" in str(stat.metadata)
            check("MinIO", f"{bucket}: Objekt hat Metadaten", has_meta, True, "eq")
            break  # ein Objekt reicht als Stichprobe


# =============================================================================
# Zusammenfassung
# =============================================================================
def summarize():
    print("\n" + "=" * 60)
    print("VERIFIKATIONS-ZUSAMMENFASSUNG")
    print("=" * 60)
    total  = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed
    print(f"  Gesamt:    {total}")
    print(f"  PASS:      {passed}")
    print(f"  FAIL:      {failed}")
    if failed > 0:
        print("\n  Fehlgeschlagene Checks:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    [{r['system']}] {r['name']}: {r['actual']} (erwartet {r['expected']})")
    print("=" * 60)
    return failed == 0


def main():
    print("=" * 60)
    print("Technische Nachweise – Banana Supply Chain")
    print("Systeme: MongoDB · Redis · Neo4j · MinIO")
    print("=" * 60)

    verify_mongodb()
    verify_redis()
    verify_neo4j()
    verify_minio()

    success = summarize()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
