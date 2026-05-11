# ============================================
# IMPORTS
# ============================================

import psycopg2
from pymongo import MongoClient
import redis
from neo4j import GraphDatabase
from minio import Minio

from datetime import datetime
from io import BytesIO
import random


# ============================================
# REDIS SERVICE
# ============================================

class RedisService:

    def __init__(self):
        self.r = redis.Redis(host="localhost", port=6379, decode_responses=True)

    def next_order_id(self):
        return self.r.incr("orders:counter")

    def track_status(self, order_id, status):
        self.r.set(f"order:{order_id}:status", status)
        self.r.rpush(f"order:{order_id}:timeline",
                     f"{datetime.utcnow()} - {status}")

    def cache_order(self, order_id, customer):
        self.r.hset(f"order:{order_id}:meta", mapping={
            "customer": customer,
            "created": str(datetime.utcnow())
        })


# ============================================
# POSTGRES SERVICE
# ============================================

class PostgresService:

    def __init__(self):
        self.conn = psycopg2.connect(
            host="localhost",
            dbname="logistics",
            user="user",
            password="password"
        )
        self.cur = self.conn.cursor()

    def get_ids(self):
        self.cur.execute("SELECT CustomerID FROM Customers")
        customers = [x[0] for x in self.cur.fetchall()]

        self.cur.execute("SELECT ProductID FROM Products")
        products = [x[0] for x in self.cur.fetchall()]

        self.cur.execute("SELECT WarehouseID FROM Warehouses")
        warehouses = [x[0] for x in self.cur.fetchall()]

        self.cur.execute("SELECT ShipperID FROM Shippers")
        shippers = [x[0] for x in self.cur.fetchall()]

        return customers, products, warehouses, shippers

    def get_supplier_map(self):
        self.cur.execute("SELECT ProductID, SupplierID FROM Products")
        return dict(self.cur.fetchall())

    def create_order(self, order_id, customer, warehouse, shipper):
        self.cur.execute("""
        INSERT INTO Orders (OrderID, CustomerID, WarehouseID, OrderDate, ShipperID)
        VALUES (%s, %s, %s, %s, %s)
        """, (order_id, customer, warehouse, datetime.utcnow(), shipper))

    def add_order_details(self, order_id, products):
        for p in products:
            self.cur.execute("""
            INSERT INTO OrderDetails (OrderID, ProductID, Quantity)
            VALUES (%s, %s, %s)
            """, (order_id, p, random.randint(1, 10)))

    def get_order_data(self, order_id):
        self.cur.execute("""
        SELECT o.OrderID, c.CustomerName, c.City, c.Country,
               w.Name, w.City
        FROM Orders o
        JOIN Customers c ON o.CustomerID = c.CustomerID
        JOIN Warehouses w ON o.WarehouseID = w.WarehouseID
        WHERE o.OrderID = %s
        """, (order_id,))
        order_info = self.cur.fetchone()

        self.cur.execute("""
        SELECT p.ProductName, p.Price, od.Quantity, p.ProductID
        FROM OrderDetails od
        JOIN Products p ON od.ProductID = p.ProductID
        WHERE od.OrderID = %s
        """, (order_id,))
        products = self.cur.fetchall()

        return order_info, products

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================
# MONGODB SERVICE
# ============================================

class MongoService:

    def __init__(self):
        client = MongoClient("mongodb://localhost:27017")
        self.collection = client["logistics"]["shipments"]

    def create_shipment(self, order_id, customer, warehouse):
        self.collection.insert_one({
            "orderId": order_id,
            "customerId": customer,
            "warehouseId": warehouse,
            "status": "created",
            "events": [
                {"status": "created", "timestamp": datetime.utcnow()}
            ],
            "createdAt": datetime.utcnow()
        })


# ============================================
# NEO4J SERVICE (ANALYTICS!)
# ============================================

class Neo4jService:

    def __init__(self):
        self.driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "password")
        )

    def create_graph(self, order_id, customer, warehouse, products, supplier_map):

        with self.driver.session() as session:

            # Nodes
            session.run("""
            MERGE (c:Customer {id:$c})
            MERGE (w:Warehouse {id:$w})
            MERGE (o:Order {id:$o})
            """, {"c": customer, "w": warehouse, "o": order_id})

            # Core relationships
            session.run("""
            MATCH (c:Customer {id:$c}), (o:Order {id:$o})
            MERGE (c)-[:PLACED]->(o)
            """, {"c": customer, "o": order_id})

            session.run("""
            MATCH (w:Warehouse {id:$w}), (o:Order {id:$o})
            MERGE (w)-[:FULFILLS]->(o)
            """, {"w": warehouse, "o": order_id})

            # Products + Suppliers
            for name, price, qty, pid in products:

                sid = supplier_map.get(pid)

                session.run("""
                MERGE (p:Product {id:$p})
                MERGE (s:Supplier {id:$s})
                """, {"p": pid, "s": sid})

                session.run("""
                MATCH (o:Order {id:$o}), (p:Product {id:$p})
                MERGE (o)-[:CONTAINS]->(p)
                """, {"o": order_id, "p": pid})

                session.run("""
                MATCH (p:Product {id:$p}), (s:Supplier {id:$s})
                MERGE (p)-[:SUPPLIED_BY]->(s)
                """, {"p": pid, "s": sid})

                session.run("""
                MATCH (s:Supplier {id:$s}), (w:Warehouse {id:$w})
                MERGE (s)-[:SUPPLIES]->(w)
                """, {"s": sid, "w": warehouse})


# ============================================
# MINIO SERVICE (ECHTE DOKUMENTE)
# ============================================

class MinIOService:

    def __init__(self):
        self.client = Minio(
            "localhost:9000",
            access_key="admin",
            secret_key="password",
            secure=False
        )
        self.bucket = "docs"

        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def create_documents(self, order_info, products):

        oid, customer, city, country, warehouse, wh_city = order_info

        # Invoice
        total = 0
        lines = [f"INVOICE {oid}", f"{customer} ({city})", ""]

        for name, price, qty, _ in products:
            subtotal = price * qty
            total += subtotal
            lines.append(f"{name} x {qty} = {subtotal}")

        lines.append(f"\nTOTAL: {total}")

        invoice = BytesIO("\n".join(map(str, lines)).encode())

        # Delivery Note
        dlines = [f"DELIVERY {oid}", f"Warehouse: {warehouse}", ""]

        for name, _, qty, _ in products:
            dlines.append(f"{name} -> {qty}")

        delivery = BytesIO("\n".join(dlines).encode())

        self.client.put_object(self.bucket, f"orders/{oid}/invoice.txt",
                               invoice, len(invoice.getvalue()))

        self.client.put_object(self.bucket, f"orders/{oid}/delivery.txt",
                               delivery, len(delivery.getvalue()))


# ============================================
# SIMULATOR
# ============================================

class Simulator:

    def __init__(self):
        self.pg = PostgresService()
        self.mongo = MongoService()
        self.redis = RedisService()
        self.neo = Neo4jService()
        self.minio = MinIOService()

        self.customers, self.products, self.warehouses, self.shippers = self.pg.get_ids()
        self.supplier_map = self.pg.get_supplier_map()

    def simulate(self):

        oid = self.redis.next_order_id()

        c = random.choice(self.customers)
        w = random.choice(self.warehouses)
        s = random.choice(self.shippers)

        self.pg.create_order(oid, c, w, s)

        chosen = random.sample(self.products, random.randint(1, 3))
        self.pg.add_order_details(oid, chosen)

        self.redis.track_status(oid, "created")
        self.redis.cache_order(oid, c)

        self.mongo.create_shipment(oid, c, w)

        order_info, product_data = self.pg.get_order_data(oid)

        self.neo.create_graph(oid, c, w, product_data, self.supplier_map)

        self.minio.create_documents(order_info, product_data)

        print(f"Order {oid} created")

    def run(self, n=10):
        for _ in range(n):
            self.simulate()

        self.pg.commit()
        self.pg.close()


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":

    sim = Simulator()
    sim.run(20)
