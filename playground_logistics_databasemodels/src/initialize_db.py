# ============================================
# IMPORTS
# ============================================

# PostgreSQL:
# -------------------------------------------------
# Relationale Datenbank (OLTP = Online Transaction Processing)
#
# Einsatz im Fulfillment:
# - Verwaltung von Bestellungen (Orders)
# - Kunden (Customers)
# - Produkten (Products)
#
# Eigenschaften:
# - ACID-konform (Atomicity, Consistency, Isolation, Durability)
# - garantiert konsistente und korrekte Daten
#
# Beispiel:
# Eine Bestellung darf nicht halb gespeichert werden
# -------------------------------------------------
import psycopg2


# MongoDB:
# -------------------------------------------------
# Dokumentenorientierte Datenbank (NoSQL)
#
# Einsatz im Fulfillment:
# - Tracking von Sendungen
# - Speicherung von Events (z. B. "shipped", "delivered")
#
# Eigenschaften:
# - flexible Struktur (kein festes Schema)
# - ideal für zeitbasierte Daten
#
# Beispiel:
# Eine Lieferung hat viele Statusänderungen → MongoDB speichert das effizient
# -------------------------------------------------
from pymongo import MongoClient


# Redis:
# -------------------------------------------------
# In-Memory Datenbank (läuft im RAM)
#
# Einsatz im Fulfillment:
# - Caching (z. B. häufig abgefragte Daten)
# - Counter (z. B. Anzahl Bestellungen)
# - Systemstatus
#
# Eigenschaften:
# - extrem schnell
# - nicht primär für persistente Daten gedacht
#
# Beispiel:
# Dashboard zeigt "1000 Orders heute" → kommt aus Redis
# -------------------------------------------------
import redis


# Neo4j:
# -------------------------------------------------
# Graphdatenbank
#
# Einsatz im Fulfillment:
# - Modellierung der Supply Chain
#
# Beispiel:
# Supplier → Warehouse → Customer
#
# Vorteil:
# - Beziehungen sind hier "First-Class Citizens"
# - komplexe Netzwerke leicht analysierbar
# -------------------------------------------------
from neo4j import GraphDatabase


# MinIO:
# -------------------------------------------------
# Object Storage (S3-kompatibel)
#
# Einsatz im Fulfillment:
# - Speicherung von Dokumenten
#   → Rechnungen (Invoice)
#   → Lieferscheine (Delivery Notes)
#
# Wichtig:
# Diese Daten gehören NICHT in eine Datenbank!
# -------------------------------------------------
from minio import Minio


# Hilfsimports
from datetime import datetime
from io import BytesIO  # wichtig für MinIO (File-ähnliche Objekte)


# ============================================
# POSTGRESQL INIT
# ============================================

def init_postgres():

    # Verbindung zur Datenbank herstellen
    conn = psycopg2.connect(
        host="localhost",
        dbname="logistics",
        user="user",
        password="password"
    )

    cur = conn.cursor()

    print("Init PostgreSQL...")

    # -------------------------------------------------
    # Datenmodell (Fulfillment Kern)
    #
    # Supplier → liefert Produkte
    # Products → werden bestellt
    # Customers → geben Orders auf
    # Orders → enthalten Produkte
    #
    # zentrale Frage:
    # "Wer hat was bestellt?"
    # -------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS Suppliers (
        SupplierID SERIAL PRIMARY KEY,
        SupplierName VARCHAR(100),
        Country VARCHAR(50)
    );

    CREATE TABLE IF NOT EXISTS Customers (
        CustomerID SERIAL PRIMARY KEY,
        CustomerName VARCHAR(100),
        City VARCHAR(50),
        Country VARCHAR(50)
    );

    CREATE TABLE IF NOT EXISTS Products (
        ProductID SERIAL PRIMARY KEY,
        ProductName VARCHAR(100),
        Price NUMERIC(10,2),

        -- Fremdschlüssel:
        -- Jedes Produkt gehört zu genau einem Supplier
        SupplierID INT REFERENCES Suppliers(SupplierID)
    );

    CREATE TABLE IF NOT EXISTS Warehouses (
        WarehouseID SERIAL PRIMARY KEY,
        Name VARCHAR(100),
        City VARCHAR(50)
    );

    CREATE TABLE IF NOT EXISTS Shippers (
        ShipperID SERIAL PRIMARY KEY,
        ShipperName VARCHAR(100)
    );

    CREATE TABLE IF NOT EXISTS Orders (
        OrderID INT PRIMARY KEY,

        -- Beziehung: Kunde gibt Bestellung auf
        CustomerID INT,

        -- Bestellung wird aus einem Lager verschickt
        WarehouseID INT,

        OrderDate TIMESTAMP,

        -- Versanddienstleister
        ShipperID INT
    );

    CREATE TABLE IF NOT EXISTS OrderDetails (
        OrderDetailID SERIAL PRIMARY KEY,

        -- welche Bestellung?
        OrderID INT,

        -- welches Produkt?
        ProductID INT,

        Quantity INT
    );
    """)

    # -------------------------------------------------
    # Stammdaten (Master Data)
    # -------------------------------------------------

    # Supplier
    cur.execute("SELECT COUNT(*) FROM Suppliers")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT INTO Suppliers (SupplierName, Country) VALUES
        ('Global Foods','Germany'),
        ('Fresh Farm','France'),
        ('Oceanic Trade','Norway');
        """)

    # Kunden
    cur.execute("SELECT COUNT(*) FROM Customers")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT INTO Customers VALUES
        (DEFAULT,'TechCorp','Munich','Germany'),
        (DEFAULT,'RetailHub','Cologne','Germany'),
        (DEFAULT,'Foodies','Hamburg','Germany'),
        (DEFAULT,'GreenMarket','Berlin','Germany'),
        (DEFAULT,'UrbanShop','Frankfurt','Germany'),
        (DEFAULT,'Nordic AB','Stockholm','Sweden'),
        (DEFAULT,'Paris Store','Paris','France'),
        (DEFAULT,'London Goods','London','UK'),
        (DEFAULT,'Iberia Trade','Madrid','Spain'),
        (DEFAULT,'Roma Market','Rome','Italy');
        """)

    # Produkte
    cur.execute("SELECT COUNT(*) FROM Products")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT INTO Products (ProductName, Price, SupplierID) VALUES
        ('Chai',18,1),
        ('Chang',19,1),
        ('Aniseed Syrup',10,2),
        ('Cajun Seasoning',22,2),
        ('Gumbo Mix',21,2),
        ('Boysenberry Spread',25,3),
        ('Dried Pears',30,3),
        ('Cranberry Sauce',40,3),
        ('Kobe Niku',97,1),
        ('Ikura',31,1);
        """)
        
    # ---------------------------
    # Warehouses (Fulfillment Center)
    # ---------------------------
    cur.execute("SELECT COUNT(*) FROM Warehouses")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT INTO Warehouses (Name, City) VALUES
        ('WH_Hamburg','Hamburg'),
        ('WH_Berlin','Berlin'),
        ('WH_Munich','Munich'),
        ('WH_Paris','Paris');
        """)
        
    # ---------------------------
    # Shippers (Versanddienstleister)
    # ---------------------------
    cur.execute("SELECT COUNT(*) FROM Shippers")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT INTO Shippers (ShipperName) VALUES
        ('DHL'),
        ('UPS'),
        ('FedEx'),
        ('Hermes');
        """)


    conn.commit()
    conn.close()


# ============================================
# MONGODB INIT
# ============================================

def init_mongodb():

    print("Init MongoDB...")

    client = MongoClient("mongodb://localhost:27017")
    db = client["logistics"]
    collection = db["shipments"]

    # -------------------------------------------------
    # Fachlich:
    #
    # MongoDB speichert den LEBENSZYKLUS einer Lieferung
    #
    # Beispiel:
    # Order wird erstellt → verschickt → zugestellt
    #
    # Vorteil:
    # flexible Struktur für Events
    # -------------------------------------------------

    if "createdAt_1" not in collection.index_information():
        collection.create_index("createdAt", expireAfterSeconds=604800)

    if collection.count_documents({}) == 0:
        collection.insert_one({
            "orderId": 1,
            "route": ["Hamburg", "Berlin"],
            "events": [
                {"status": "created", "timestamp": datetime.utcnow()}
            ],
            "createdAt": datetime.utcnow()
        })


# ============================================
# REDIS INIT
# ============================================

def init_redis():

    print("Init Redis...")

    r = redis.Redis(host="localhost", port=6379, decode_responses=True)

    # -------------------------------------------------
    # Redis speichert:
    # - schnelle Werte
    # - temporäre Daten
    # -------------------------------------------------

    r.set("system:status", "ready")
    r.set("orders:counter", 0)


# ============================================
# NEO4J INIT
# ============================================

def init_neo4j():

    print("Init Neo4j...")

    driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "password")
    )

    with driver.session() as session:

        # -------------------------------------------------
        # Graphmodell:
        #
        # Supplier → Warehouse → Customer
        #
        # Ziel:
        # Visualisierung und Analyse der Supply Chain
        # -------------------------------------------------

        session.run("""
        MERGE (s:Supplier {id:1, name:'Global Foods'})
        MERGE (w:Warehouse {id:1, city:'Hamburg'})
        MERGE (c:Customer {id:101, name:'TechCorp'})
        """)

        session.run("""
        MATCH (s:Supplier {id:1}), (w:Warehouse {id:1})
        MERGE (s)-[:SUPPLIES]->(w)
        """)

        session.run("""
        MATCH (c:Customer {id:101}), (w:Warehouse {id:1})
        MERGE (c)-[:ORDERS]->(w)
        """)


# ============================================
# MINIO INIT
# ============================================

def init_minio():

    print("Init MinIO...")

    client = Minio(
        "localhost:9000",
        access_key="admin",
        secret_key="password",
        secure=False
    )

    bucket = "docs"

    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

    # -------------------------------------------------
    # Dokumente im Fulfillment:
    #
    # Rechnung (Invoice):
    # - finanzielles Dokument
    #
    # Lieferschein (Delivery Note):
    # - beschreibt Inhalt der Lieferung
    # - wichtig für Wareneingang
    # -------------------------------------------------

    invoice = BytesIO(b"invoice content")
    delivery = BytesIO(b"delivery note content")

    client.put_object(bucket, "invoice_1.pdf", invoice, len(b"invoice content"))
    client.put_object(bucket, "delivery_note_1.pdf", delivery, len(b"delivery note content"))


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":

    print("=== INITIALIZING SYSTEM ===")

    init_postgres()
    init_mongodb()
    init_redis()
    init_neo4j()
    init_minio()

    print("=== DONE ===")
