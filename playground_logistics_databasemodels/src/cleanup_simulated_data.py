# ============================================
# IMPORTS
# ============================================

import psycopg2
from pymongo import MongoClient
import redis
from neo4j import GraphDatabase
from minio import Minio


# ============================================
# POSTGRES CLEANUP (nur Simulation!)
# ============================================

def clean_postgres():
    print("Cleaning PostgreSQL (orders only)...")

    conn = psycopg2.connect(
        host="localhost",
        dbname="logistics",
        user="user",
        password="password"
    )
    cur = conn.cursor()

    # Reihenfolge wichtig wegen FK
    cur.execute("DELETE FROM OrderDetails")
    cur.execute("DELETE FROM Orders")

    conn.commit()
    conn.close()


# ============================================
# MONGODB CLEANUP
# ============================================

def clean_mongodb():
    print("Cleaning MongoDB shipments...")

    client = MongoClient("mongodb://localhost:27017")
    db = client["logistics"]

    db["shipments"].delete_many({})


# ============================================
# REDIS CLEANUP (gezielt!)
# ============================================

def clean_redis():
    print("Cleaning Redis simulation keys...")

    r = redis.Redis(host="localhost", port=6379, decode_responses=True)

    keys = r.keys("order:*")

    for k in keys:
        r.delete(k)

    # Counter zurücksetzen
    r.set("orders:counter", 0)


# ============================================
# NEO4J CLEANUP (nur Simulation Graph)
# ============================================

def clean_neo4j():
    print("Cleaning Neo4j simulation graph...")

    driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "password")
    )

    with driver.session() as session:

        # Nur Order-basierte Daten löschen
        session.run("""
        MATCH (o:Order)
        DETACH DELETE o
        """)


# ============================================
# MINIO CLEANUP (nur Simulation Docs)
# ============================================

def clean_minio():
    print("Cleaning MinIO order documents...")

    client = Minio(
        "localhost:9000",
        access_key="admin",
        secret_key="password",
        secure=False
    )

    bucket = "docs"

    if client.bucket_exists(bucket):

        objects = client.list_objects(bucket, recursive=True)

        for obj in objects:
            # nur simulated orders löschen
            if obj.object_name.startswith("orders/"):
                client.remove_object(bucket, obj.object_name)


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":

    print("=== CLEANING SIMULATED DATA ===")

    clean_postgres()
    clean_mongodb()
    clean_redis()
    clean_neo4j()
    clean_minio()

    print("=== CLEANUP DONE ===")
