import json
import random
import uuid
import os

from datetime import datetime, timedelta
import math


# ============================================================
# OUTPUT CONFIG
# ============================================================

# "stdout" -> Ausgabe auf Konsole
# "files"  -> Ausgabe in shared/erp, shared/wms, shared/tms
OUTPUT_MODE = "files"
# OUTPUT_MODE = "stdout"

BASE_SHARED_DIR = "shared"


# ============================================================
# MASTER DATA CONFIG
# ============================================================

MASTERDATA_INCONSISTENCY_MODE = "targeted"

# Optionen:
#
# "none"
# -> keine Inkonsistenzen
#
# "random"
# -> zufällige Inkonsistenzen
#
# "targeted"
# -> gezielte Inkonsistenzen
#    WMS -> underscores
#    TMS -> lowercase


# ============================================================
# SUPPLY CHAIN FLOW
# ============================================================

SUPPLY_CHAIN_FLOW = [

    (
        "BANANA_PLANTATION",
        "COLLECTION_CENTER",
        "TRUCK"
    ),

    (
        "COLLECTION_CENTER",
        "QUALITY_CONTROL",
        "TRUCK"
    ),

    (
        "QUALITY_CONTROL",
        "AFRICA_COLD_STORAGE",
        "TRUCK"
    ),

    (
        "AFRICA_COLD_STORAGE",
        "EUROPE_COLD_STORAGE",
        "SEA_FREIGHT"
    ),

    (
        "EUROPE_COLD_STORAGE",
        "CENTRAL_WAREHOUSE",
        "TRUCK"
    ),

    (
        "CENTRAL_WAREHOUSE",
        "RETAIL_STORE",
        "TRUCK"
    )
]


# ============================================================
# UTILITIES
# ============================================================

def timestamp():

    return datetime.utcnow().isoformat()


def future_timestamp(hours=24):

    return (
        datetime.utcnow() +
        timedelta(hours=hours)
    ).isoformat()


# [ANPASSUNG 2026-06-30] Kühlkette mit Brüchen: ~15 % der Messungen außerhalb 10-15 °C
# (~70 % zu warm = Reifung/Verderb, ~30 % zu kalt = Kälteschaden); zuvor konstant 10-15 °C.
COLD_CHAIN_BREAK_RATE = 0.15
COLD_CHAIN_WARM_SHARE = 0.70


def random_temperature():
    if random.random() < COLD_CHAIN_BREAK_RATE:          # Kühlkettenbruch
        if random.random() < COLD_CHAIN_WARM_SHARE:
            return round(random.uniform(15.5, 24.0), 2)  # zu warm
        return round(random.uniform(2.0, 9.5), 2)        # zu kalt
    return round(random.uniform(10.0, 15.0), 2)          # intakt


def normalize(value):

    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
    )


# ============================================================
# MASTER DATA TRANSFORMATION
# ============================================================

def transform_masterdata(
    value,
    system_name
):

    if MASTERDATA_INCONSISTENCY_MODE == "none":
        return value

    if MASTERDATA_INCONSISTENCY_MODE == "random":

        variants = [

            value,

            value.replace("-", "_"),

            value.lower(),

            value.upper(),

            value.replace(
                "BAN",
                "BANANA"
            ),

            value + " "
        ]

        return random.choice(
            variants
        )

    if MASTERDATA_INCONSISTENCY_MODE == "targeted":

        if system_name == "WMS":

            return (
                value
                .replace("-", "_")
            )

        if system_name == "TMS":

            return value.lower()

    return value


# ============================================================
# OUTPUT HANDLING
# ============================================================

ERP_EVENTS = {

    "SupplierCreated",
    "CustomerCreated",
    "ProductCreated",

    "OrderCreated",
    "BatchHarvested"
}

WMS_EVENTS = {

    "WarehouseSKUCreated",
    "NodeProcessed"
}

TMS_EVENTS = {

    "CarrierCreated",
    "TransportProductReferenceCreated",

    "TransportStarted",
    "ShipmentPositionUpdated",
    "TransportCompleted",
    "DeliveryCompleted"
}


def ensure_directories():

    os.makedirs(
        os.path.join(BASE_SHARED_DIR, "erp"),
        exist_ok=True
    )

    os.makedirs(
        os.path.join(BASE_SHARED_DIR, "wms"),
        exist_ok=True
    )

    os.makedirs(
        os.path.join(BASE_SHARED_DIR, "tms"),
        exist_ok=True
    )


def get_target_folder(event):

    event_type = event["event_type"]

    if event_type in ERP_EVENTS:

        return os.path.join(
            BASE_SHARED_DIR,
            "erp"
        )

    if event_type in WMS_EVENTS:

        return os.path.join(
            BASE_SHARED_DIR,
            "wms"
        )

    if event_type in TMS_EVENTS:

        return os.path.join(
            BASE_SHARED_DIR,
            "tms"
        )

    return BASE_SHARED_DIR


# ============================================================
# FILE NAMING
# ============================================================

def build_filename(
    iteration,
    event
):

    event_type = normalize(
        event["event_type"]
    )

    # ========================================================
    # CUSTOMER CREATED
    # ========================================================

    if event["event_type"] == "CustomerCreated":

        customer_number = normalize(
            event["customer_number"]
        )

        return (
            f"supplychain_iteration_"
            f"{iteration:03d}_"
            f"customer_"
            f"{customer_number}_"
            f"customer_created.json"
        )

    # ========================================================
    # SUPPLIER CREATED
    # ========================================================

    if event["event_type"] == "SupplierCreated":

        supplier_code = normalize(
            event["supplier_code"]
        )

        return (
            f"supplychain_iteration_"
            f"{iteration:03d}_"
            f"supplier_"
            f"{supplier_code}_"
            f"supplier_created.json"
        )

    # ========================================================
    # PRODUCT CREATED
    # ========================================================

    if event["event_type"] == "ProductCreated":

        product_code = normalize(
            event["product_code"]
        )

        return (
            f"supplychain_iteration_"
            f"{iteration:03d}_"
            f"product_"
            f"{product_code}_"
            f"product_created.json"
        )

    # ========================================================
    # WMS SKU CREATED
    # ========================================================

    if event["event_type"] == "WarehouseSKUCreated":

        sku = normalize(
            event["sku"]
        )

        return (
            f"supplychain_iteration_"
            f"{iteration:03d}_"
            f"warehouse_sku_"
            f"{sku}_"
            f"warehouse_sku_created.json"
        )

    # ========================================================
    # TMS PRODUCT REFERENCE CREATED
    # ========================================================

    if (
        event["event_type"] ==
        "TransportProductReferenceCreated"
    ):

        ref = normalize(
            event[
                "transport_product_reference"
            ]
        )

        return (
            f"supplychain_iteration_"
            f"{iteration:03d}_"
            f"transport_product_reference_"
            f"{ref}_"
            f"transport_product_reference_created.json"
        )

    # ========================================================
    # CARRIER CREATED
    # ========================================================

    if event["event_type"] == "CarrierCreated":

        carrier_id = normalize(
            event["carrier_id"]
        )

        return (
            f"supplychain_iteration_"
            f"{iteration:03d}_"
            f"carrier_"
            f"{carrier_id}_"
            f"carrier_created.json"
        )

    # ========================================================
    # TRANSPORT EVENTS
    # ========================================================

    if (
        "source_node" in event and
        "target_node" in event
    ):

        source_node = normalize(
            event["source_node"]
        )

        target_node = normalize(
            event["target_node"]
        )

        transport_mode = normalize(
            event.get(
                "transport_mode",
                "transport"
            )
        )

        return (
            f"supplychain_iteration_"
            f"{iteration:03d}_"
            f"transport_"
            f"{transport_mode}_"
            f"{source_node}_to_"
            f"{target_node}_"
            f"{event_type}_"
            f"{uuid.uuid4()}.json"
        )

    # ========================================================
    # NODE EVENTS
    # ========================================================

    if "supply_chain_node" in event:

        node = normalize(
            event["supply_chain_node"]
        )

        return (
            f"supplychain_iteration_"
            f"{iteration:03d}_"
            f"supplychain_node_"
            f"{node}_"
            f"{event_type}_"
            f"{uuid.uuid4()}.json"
        )

    # ========================================================
    # FALLBACK
    # ========================================================

    return (
        f"supplychain_iteration_"
        f"{iteration:03d}_"
        f"{event_type}_"
        f"{uuid.uuid4()}.json"
    )


# ── [ANPASSUNG 2026-07-01] Echte Event-Zeitstempel direkt im Generator ─────────
# Zuvor: Generator stempelte utcnow(), die ETL verteilte nachträglich (_apply_ts_offset).
# Jetzt: die Quelle (shared/) enthält echte Zeiten. Woche N -> _ITER_BASE + (N-1)*7 Tage;
# pro Bestellung zusätzlich ein Tages-Offset (über die Woche gestreut). Reproduzierbar
# über random.seed(42). Stammdaten (iteration 0) -> Start der Zeitachse.
_ITER_BASE = datetime(2025, 6, 16, 6, 0, 0)   # [ANPASSUNG 2026-07-01] Anker so gesetzt, dass die 52-Wochen-Historie ~heute endet (alle Daten <= heute, kein Zukunftsdatum); Span ~Jun 2025 -> Jun 2026

_ROUTE_START_DAYS = {
    "banana_plantation_to_collection_center":      (0.58, 0.75),
    "collection_center_to_quality_control":        (1.33, 1.67),
    "quality_control_to_africa_cold_storage":      (2.50, 3.00),
    "africa_cold_storage_to_europe_cold_storage":  (4.25, 5.00),
    "europe_cold_storage_to_central_warehouse":    (11.33, 12.00),
    "central_warehouse_to_retail_store":           (13.42, 14.00),
}

_ROUTE_TRAVEL_DAYS = {
    "banana_plantation_to_collection_center":      1.0,
    "collection_center_to_quality_control":        0.75,
    "quality_control_to_africa_cold_storage":      1.25,
    "africa_cold_storage_to_europe_cold_storage":  6.0,
    "europe_cold_storage_to_central_warehouse":    1.5,
    "central_warehouse_to_retail_store":           0.75,
}

_NODE_ARRIVAL_DAYS = {
    "banana_plantation":    (0.00, 0.25),
    "collection_center":    (1.00, 1.33),
    "quality_control":      (2.00, 2.50),
    "africa_cold_storage":  (3.25, 4.00),
    "europe_cold_storage":  (10.33, 11.00),
    "central_warehouse":    (12.50, 13.00),
    "retail_store":         (14.50, 15.00),
}


def _find_route(filename):
    lower = filename.lower()
    for route in _ROUTE_START_DAYS:
        if route in lower:
            return route
    return None


def _find_node(filename):
    lower = filename.lower()
    for node in _NODE_ARRIVAL_DAYS:
        if f"_node_{node}_" in lower or node in lower:
            return node
    return None


def _assign_timestamp(event, iteration, filename, day_offset=0.0):
    # Setzt event["timestamp"] auf die echte Supply-Chain-Zeit (Woche + Routen-/Knoten-Offset).
    if iteration <= 0:
        base = _ITER_BASE                                      # Stammdaten: Start der Zeitachse
    else:
        base = _ITER_BASE + timedelta(days=(iteration - 1) * 7 + day_offset)
    et = event.get("event_type", "")

    if et in ("SupplierCreated", "CustomerCreated", "ProductCreated",
              "WarehouseSKUCreated", "CarrierCreated", "TransportProductReferenceCreated"):
        event["timestamp"] = (base + timedelta(minutes=random.randint(0, 180))).isoformat()

    elif et == "OrderCreated":
        event["timestamp"] = (base + timedelta(hours=random.uniform(7, 10))).isoformat()

    elif et == "BatchHarvested":
        event["timestamp"] = (base + timedelta(hours=random.uniform(10, 15))).isoformat()

    elif et == "TransportStarted":
        route = _find_route(filename)
        if not route:
            src = event.get("source_node", "").lower().replace(" ", "_")
            tgt = event.get("target_node", "").lower().replace(" ", "_")
            route = f"{src}_to_{tgt}"
        start_days = random.uniform(*_ROUTE_START_DAYS.get(route, (0.5, 1.0)))
        ts = base + timedelta(days=start_days, minutes=random.randint(0, 90))
        event["timestamp"] = ts.isoformat()
        if "estimated_arrival" in event:
            travel = _ROUTE_TRAVEL_DAYS.get(route, 2.0)
            event["estimated_arrival"] = (ts + timedelta(days=travel, hours=random.uniform(-3, 3))).isoformat()

    elif et == "ShipmentPositionUpdated":
        rd = event.get("current_route", {})
        src = rd.get("source", "").lower().replace(" ", "_")
        tgt = rd.get("target", "").lower().replace(" ", "_")
        route = f"{src}_to_{tgt}"
        day_range = _ROUTE_START_DAYS.get(route, (0.5, 1.0))
        travel = _ROUTE_TRAVEL_DAYS.get(route, 1.0)
        pos_day = random.uniform(day_range[0], day_range[0] + travel)
        event["timestamp"] = (base + timedelta(days=pos_day, hours=random.uniform(0, 20))).isoformat()

    elif et == "NodeProcessed":
        node = _find_node(filename) or event.get("supply_chain_node", "").lower().replace(" ", "_")
        days = random.uniform(*_NODE_ARRIVAL_DAYS.get(node, (1.0, 2.0)))
        event["timestamp"] = (base + timedelta(days=days, hours=random.uniform(8, 18))).isoformat()

    elif et == "TransportCompleted":
        node = event.get("arrival_node", "").lower().replace(" ", "_")
        days = random.uniform(*_NODE_ARRIVAL_DAYS.get(node, (2.0, 3.0)))
        event["timestamp"] = (base + timedelta(days=days, hours=random.uniform(10, 20))).isoformat()

    elif et == "DeliveryCompleted":
        node = _find_node(filename) or event.get("supply_chain_node", "").lower().replace(" ", "_")
        days = random.uniform(*_NODE_ARRIVAL_DAYS.get(node, (14.5, 15.5)))
        event["timestamp"] = (base + timedelta(days=days, hours=random.uniform(8, 18))).isoformat()

    return event


def output_event(
    event,
    iteration,
    day_offset=0.0
):

    if OUTPUT_MODE == "stdout":

        _assign_timestamp(event, iteration, "", day_offset)

        print(
            json.dumps(
                event,
                indent=2
            )
        )

        print()

        return

    folder = get_target_folder(
        event
    )

    filename = build_filename(
        iteration,
        event
    )

    # [ANPASSUNG 2026-07-01] echte Eventzeit direkt setzen (zuvor utcnow() + ETL _apply_ts_offset)
    _assign_timestamp(event, iteration, filename, day_offset)

    filepath = os.path.join(
        folder,
        filename
    )

    with open(filepath, "w") as f:

        json.dump(
            event,
            f,
            indent=2
        )

    print(
        f"[WRITTEN] {filepath}"
    )


# ============================================================
# ERP SERVICE
# ============================================================

class ERPService:

    def __init__(self):

        self.suppliers = {}

        self.products = {}

        self.customers = {}

        self.masterdata_events = []

        self.initialize_suppliers()

        self.initialize_customers()

        self.initialize_products()

    def initialize_suppliers(self):

        supplier_names = [

            "Golden Banana Ltd",
            "Fresh Banana Export",
            "Tropical Banana Group",
            "Banana Kingdom",
            "West Africa Fruits",
            "Premium Banana Farms",
            "Green Harvest Export",
            "Sunshine Produce",
            "Eco Banana Trading",
            "Global Banana Source"
        ]

        for i, name in enumerate(
            supplier_names,
            start=1
        ):

            supplier = {

                "event_type":
                    "SupplierCreated",

                "supplier_code":
                    f"SUP-{100+i}",

                "supplier_name":
                    name,

                "country":
                    "Ghana",

                "timestamp":
                    timestamp()
            }

            self.suppliers[
                supplier["supplier_code"]
            ] = supplier

            self.masterdata_events.append(
                supplier
            )

    def initialize_customers(self):

        customer_names = [

            "ALDI",
            "LIDL",
            "REWE",
            "EDEKA",
            "METRO",
            "KAUFLAND",
            "TESCO",
            "CARREFOUR",
            "AUCHAN",
            "SPAR"
        ]

        for i, name in enumerate(
            customer_names,
            start=1
        ):

            customer = {

                "event_type":
                    "CustomerCreated",

                "customer_number":
                    f"CUST-{100+i}",

                "customer_name":
                    name,

                "city":
                    random.choice([
                        "Hamburg",
                        "Berlin",
                        "Munich",
                        "Frankfurt",
                        "Cologne"
                    ]),

                "country":
                    "Germany",

                "timestamp":
                    timestamp()
            }

            self.customers[
                customer["customer_number"]
            ] = customer

            self.masterdata_events.append(
                customer
            )

    def initialize_products(self):

        # [ANPASSUNG 2026-07-01] Produktkategorien von einem generischen
        # "Fresh Fruit" auf analytisch nutzbare Segmente erweitert.
        product_catalog = [

            ("Cavendish Banana", "Standard"),
            ("Organic Banana", "Sustainable"),
            ("Premium Banana", "Premium"),
            ("Baby Banana", "Specialty"),
            ("Fairtrade Banana", "Sustainable"),
            ("Export Banana", "Standard"),
            ("Sweet Banana", "Standard"),
            ("Green Banana", "Standard"),
            ("Yellow Banana", "Standard"),
            ("Tropical Banana", "Specialty")
        ]

        supplier_codes = list(
            self.suppliers.keys()
        )

        for i, (name, category) in enumerate(
            product_catalog,
            start=1
        ):

            supplier_code = random.choice(
                supplier_codes
            )

            product = {

                "event_type":
                    "ProductCreated",

                "product_code":
                    f"BAN-{100+i}",

                "product_name":
                    name,

                "category":
                    category,

                "supplier_reference":
                    supplier_code,

                "timestamp":
                    timestamp()
            }

            self.products[
                product["product_code"]
            ] = product

            self.masterdata_events.append(
                product
            )

    def get_random_supplier(self):

        return random.choice(
            list(
                self.suppliers.values()
            )
        )

    def get_random_product(
        self,
        supplier
    ):

        supplier_products = [

            product

            for product in self.products.values()

            if product[
                "supplier_reference"
            ] == supplier[
                "supplier_code"
            ]
        ]

        if supplier_products:

            return random.choice(
                supplier_products
            )

        return random.choice(
            list(
                self.products.values()
            )
        )

    def get_random_customer(self):

        return random.choice(
            list(
                self.customers.values()
            )
        )

    def create_order(
        self,
        customer,
        product
    ):

        quantity = random.randint(
            100,
            1000
        )

        return {

            "event_type":
                "OrderCreated",

            "order_reference":
                f"ORD-{uuid.uuid4()}",

            "customer":
                customer,

            "items": [

                {

                    "product_code":
                        product[
                            "product_code"
                        ],

                    "description":
                        product[
                            "product_name"
                        ],

                    "quantity":
                        quantity,

                    "unit_price":
                        round(
                            random.uniform(
                                1.5,
                                5.0
                            ),
                            2
                        )
                }
            ],

            "delivery_priority":
                random.choice([
                    "HIGH",
                    "NORMAL",
                    "LOW"
                ]),

            "timestamp":
                timestamp()
        }

    def harvest_batch(
        self,
        order,
        product
    ):

        return {

            "event_type":
                "BatchHarvested",

            "supply_chain_node":
                "BANANA_PLANTATION",

            "product_code":
                product[
                    "product_code"
                ],

            "wms_sku":
                transform_masterdata(
                    product[
                        "product_code"
                    ],
                    "WMS"
                ),

            "tms_product_reference":
                transform_masterdata(
                    product[
                        "product_code"
                    ],
                    "TMS"
                ),

            "batch_identifier":
                f"BATCH-{uuid.uuid4()}",

            "origin_country":
                "Ghana",

            "quantity":
                order[
                    "items"
                ][0][
                    "quantity"
                ],

            "timestamp":
                timestamp()
        }


# ============================================================
# WMS SERVICE
# ============================================================

class WMSService:

    def __init__(
        self,
        products
    ):

        self.masterdata_events = []

        self.initialize_wms_products(
            products
        )

    def initialize_wms_products(
        self,
        products
    ):

        for product in products.values():

            event = {

                "event_type":
                    "WarehouseSKUCreated",

                "erp_product_code":
                    product[
                        "product_code"
                    ],

                "sku":
                    transform_masterdata(
                        product[
                            "product_code"
                        ],
                        "WMS"
                    ),

                "timestamp":
                    timestamp()
            }

            self.masterdata_events.append(
                event
            )

    def create_node_event(
        self,
        node_name,
        batch_event
    ):

        return {

            "event_type":
                "NodeProcessed",

            "supply_chain_node":
                node_name,

            "batch_reference":
                batch_event[
                    "batch_identifier"
                ],

            "sku":
                batch_event[
                    "wms_sku"
                ],

            "temperature":
                random_temperature(),

            "status":
                "COMPLETED",

            "timestamp":
                timestamp()
        }


# ============================================================
# TMS SERVICE
# ============================================================

class TMSService:

    def __init__(
        self,
        products
    ):

        self.masterdata_events = []

        self.initialize_transport_products(
            products
        )

        self.initialize_carriers()

    def initialize_transport_products(
        self,
        products
    ):

        for product in products.values():

            event = {

                "event_type":
                    "TransportProductReferenceCreated",

                "erp_product_code":
                    product[
                        "product_code"
                    ],

                "transport_product_reference":
                    transform_masterdata(
                        product[
                            "product_code"
                        ],
                        "TMS"
                    ),

                "timestamp":
                    timestamp()
            }

            self.masterdata_events.append(
                event
            )

    def initialize_carriers(self):

        carriers = [

            "DHL",
            "Maersk",
            "MSC",
            "DB Schenker",
            "Hapag Lloyd"
        ]

        for i, carrier_name in enumerate(
            carriers,
            start=1
        ):

            event = {

                "event_type":
                    "CarrierCreated",

                "carrier_id":
                    f"CAR-{100+i}",

                "carrier_name":
                    carrier_name,

                "timestamp":
                    timestamp()
            }

            self.masterdata_events.append(
                event
            )

    def create_transport(
        self,
        source_node,
        target_node,
        cargo_reference,
        transport_mode
    ):

        return {

            "event_type":
                "TransportStarted",

            "shipment_identifier":
                f"SHIP-{uuid.uuid4()}",

            "source_node":
                source_node,

            "target_node":
                target_node,

            "transport_mode":
                transport_mode,

            "cargo_product_reference":
                transform_masterdata(
                    cargo_reference,
                    "TMS"
                ),

            "carrier": {

                "carrier_id":
                    f"CAR-{random.randint(101,105)}",

                "carrier_name":
                    random.choice([
                        "DHL",
                        "Maersk",
                        "MSC",
                        "DB Schenker",
                        "Hapag Lloyd"
                    ])
            },

            "estimated_arrival":
                future_timestamp(
                    random.randint(2, 240)
                ),

            "timestamp":
                timestamp()
        }

    def create_gps_event(
        self,
        shipment_event
    ):

        return {

            "event_type":
                "ShipmentPositionUpdated",

            "shipment_identifier":
                shipment_event[
                    "shipment_identifier"
                ],

            "cargo_product_reference":
                shipment_event[
                    "cargo_product_reference"
                ],

            "current_route": {

                "source":
                    shipment_event[
                        "source_node"
                    ],

                "target":
                    shipment_event[
                        "target_node"
                    ]
            },

            "coordinates": {

                "latitude":
                    round(
                        random.uniform(
                            -90,
                            90
                        ),
                        6
                    ),

                "longitude":
                    round(
                        random.uniform(
                            -180,
                            180
                        ),
                        6
                    )
            },

            "container_temperature":
                random_temperature(),

            "speed_kmh":
                round(
                    random.uniform(
                        30,
                        120
                    ),
                    2
                ),

            "timestamp":
                timestamp()
        }

    def complete_transport(
        self,
        shipment_event
    ):

        return {

            "event_type":
                "TransportCompleted",

            "shipment_identifier":
                shipment_event[
                    "shipment_identifier"
                ],

            "cargo_product_reference":
                shipment_event[
                    "cargo_product_reference"
                ],

            "arrival_node":
                shipment_event[
                    "target_node"
                ],

            "delay_minutes":
                random.randint(0, 180),

            "timestamp":
                timestamp()
        }

    def complete_delivery(
        self,
        shipment_event
    ):

        return {

            "event_type":
                "DeliveryCompleted",

            "supply_chain_node":
                "RETAIL_STORE",

            "shipment_identifier":
                shipment_event[
                    "shipment_identifier"
                ],

            "cargo_product_reference":
                shipment_event[
                    "cargo_product_reference"
                ],

            "delivery_status":
                random.choice([
                    "SUCCESSFUL",
                    "SUCCESSFUL",
                    "DELAYED"
                ]),

            "received_by":
                f"EMP-{random.randint(1,99)}",

            "timestamp":
                timestamp()
        }


# ============================================================
# FULL SUPPLY CHAIN PROCESS
# ============================================================

class BananaSupplyChainProcess:

    def __init__(self):

        self.erp = ERPService()

        self.wms = WMSService(
            self.erp.products
        )

        self.tms = TMSService(
            self.erp.products
        )

    def get_masterdata_events(self):

        events = []

        events.extend(
            self.erp.masterdata_events
        )

        events.extend(
            self.wms.masterdata_events
        )

        events.extend(
            self.tms.masterdata_events
        )

        return events

    def run(self):

        events = []

        supplier = (
            self.erp.get_random_supplier()
        )

        product = (
            self.erp.get_random_product(
                supplier
            )
        )

        customer = (
            self.erp.get_random_customer()
        )

        # ====================================================
        # ERP
        # ====================================================

        order_event = (
            self.erp.create_order(
                customer,
                product
            )
        )

        batch_event = (
            self.erp.harvest_batch(
                order_event,
                product
            )
        )

        events.extend([
            order_event,
            batch_event
        ])

        # ====================================================
        # FULL FULFILLMENT FLOW
        # ====================================================

        last_transport = None

        for flow in SUPPLY_CHAIN_FLOW:

            source_node = flow[0]

            target_node = flow[1]

            transport_mode = flow[2]

            # ================================================
            # WMS PROCESSING
            # ================================================

            wms_event = (
                self.wms.create_node_event(
                    source_node,
                    batch_event
                )
            )

            events.append(
                wms_event
            )

            # ================================================
            # TRANSPORT START
            # ================================================

            transport_event = (
                self.tms.create_transport(
                    source_node=source_node,
                    target_node=target_node,
                    cargo_reference=product[
                        "product_code"
                    ],
                    transport_mode=transport_mode
                )
            )

            events.append(
                transport_event
            )

            # ================================================
            # GPS EVENTS
            # ================================================

            gps_updates = random.randint(
                1,
                3
            )

            for _ in range(gps_updates):

                gps_event = (
                    self.tms.create_gps_event(
                        transport_event
                    )
                )

                events.append(
                    gps_event
                )

            # ================================================
            # TRANSPORT COMPLETE
            # ================================================

            transport_complete = (
                self.tms.complete_transport(
                    transport_event
                )
            )

            events.append(
                transport_complete
            )

            last_transport = transport_event

        # ====================================================
        # DELIVERY
        # ====================================================

        if last_transport:

            delivery_event = (
                self.tms.complete_delivery(
                    last_transport
                )
            )

            events.append(
                delivery_event
            )

        return events


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    # [ANPASSUNG 2026-06-30] Fester Seed für reproduzierbare Generierung
    # (gleiche random-Werte je Lauf: Temperatur, delay, Carrier, Mengen ...; UUIDs bleiben zufällig)
    random.seed(42)

    if OUTPUT_MODE == "files":

        ensure_directories()

    process = BananaSupplyChainProcess()

    # ========================================================
    # MASTER DATA EVENTS
    # -> EINMALIG
    # ========================================================

    masterdata_events = (
        process.get_masterdata_events()
    )

    for event in masterdata_events:

        output_event(
            event,
            0
        )

    # ========================================================
    # OPERATIONAL EVENTS
    # -> PERMANENT
    # ========================================================

    # [ANPASSUNG 2026-07-01] Entkopplung Zeit/Menge: WEEKS = Zeitachse (1 Woche je Schritt),
    # Bestellungen pro Woche variabel (Trend + Jahres-Saison + Rauschen) -> echte Nachfrage-
    # Zeitreihe für den Forecast; mehrere Orders/Woche -> Dichte fürs Clustering. Bleibt in 2026.
    WEEKS            = 52    # Zeitspanne
    BASE_ORDERS_WEEK = 4     # mittlere Bestellungen pro Woche

    for week in range(1, WEEKS + 1):

        demand   = BASE_ORDERS_WEEK + (week - 1) * 0.04 + 1.5 * math.sin(2 * math.pi * week / 52) + random.gauss(0, 1)
        n_orders = max(1, round(demand))

        print("=" * 80)
        print(f"WOCHE {week} / {WEEKS}  ->  {n_orders} Bestellung(en)")
        print("=" * 80)

        for _ in range(n_orders):

            events     = process.run()
            day_offset = random.uniform(0, 6)   # diese Bestellung irgendwann in der Woche

            for event in events:

                output_event(
                    event,
                    week,
                    day_offset
                )
