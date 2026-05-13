# ============================================
# IMPORTS
# ============================================

import psycopg2
from pymongo import MongoClient
import redis
from neo4j import GraphDatabase
from minio import Minio


# ============================================
# POSTGRESQL RESET
# ============================================

def reset_postgres():
    conn = psycopg2.connect(
        host="localhost",
        dbname="logistics",
        user="user",
        password="password"
    )
    cur = conn.cursor()

    print("Reset PostgreSQL...")

    # -------------------------------------------------
    # Variante 1 (empfohlen):
    # Tabellen leeren, Struktur behalten
    #
    # TRUNCATE:
    # - löscht alle Daten
    # - schneller als DELETE
    # - setzt IDs zurück (RESTART IDENTITY)
    # -------------------------------------------------

    cur.execute("""
    TRUNCATE TABLE
        OrderDetails,
        Orders,
        Products,
        Customers,
        Suppliers,
        Shippers,
        Warehouses
    RESTART IDENTITY CASCADE;
    """)

    # -------------------------------------------------
    # Alternative (komplett löschen):
    # DROP TABLE ... CASCADE
    # -------------------------------------------------

    conn.commit()
    conn.close()


# ============================================
# MONGODB RESET
# ============================================

def reset_mongodb():
    print("Reset MongoDB...")

    client = MongoClient("mongodb://localhost:27017")
    db = client["logistics"]

    # -------------------------------------------------
    # Variante 1:
    # Collection leeren
    # -------------------------------------------------
    db["shipments"].delete_many({})

    # -------------------------------------------------
    # Variante 2 (komplett):
    # ganze DB löschen
    # client.drop_database("logistics")
    # -------------------------------------------------


# ============================================
# REDIS RESET
# ============================================

def reset_redis():
    print("Reset Redis...")

    r = redis.Redis(host="localhost", port=6379, decode_responses=True)

    # -------------------------------------------------
    # ACHTUNG:
    # flushdb = löscht aktuelle DB
    # flushall = löscht ALLE Redis Datenbanken
    # -------------------------------------------------

    r.flushdb()


# ============================================
# NEO4J RESET
# ============================================

def reset_neo4j():
    print("Reset Neo4j...")

    driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "password")
    )

    with driver.session() as session:

        # Alle Nodes löschen
        session.run("MATCH (n) DETACH DELETE n")

        # -------------------------------------------------
        # Alle Constraints dynamisch ermitteln und löschen
        # -------------------------------------------------
        result = session.run("SHOW CONSTRAINTS")

        for record in result:
            name = record["name"]
            print(f"Dropping constraint: {name}")
            session.run(f"DROP CONSTRAINT {name}")
            

# ============================================
# MINIO RESET
# ============================================

def reset_minio():
    print("Reset MinIO...")

    client = Minio(
        "localhost:9000",
        access_key="admin",
        secret_key="password",
        secure=False
    )

    bucket = "docs"

    if client.bucket_exists(bucket):

        # -------------------------------------------------
        # Alle Objekte im Bucket löschen
        # -------------------------------------------------
        objects = client.list_objects(bucket, recursive=True)

        for obj in objects:
            client.remove_object(bucket, obj.object_name)

        # -------------------------------------------------
        # Optional: Bucket komplett löschen
        # -------------------------------------------------
        client.remove_bucket(bucket)


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":

    print("=== RESETTING SYSTEM ===")

    reset_postgres()
    reset_mongodb()
    reset_redis()
    reset_neo4j()
    reset_minio()

    print("=== RESET DONE ===")
