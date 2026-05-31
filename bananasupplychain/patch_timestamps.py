#!/usr/bin/env python3
"""
Verteilt alle JSON-Timestamps in shared/ auf realistische Supply-Chain-Zeiträume.
Iteration 001 → KW2 2026 (05.01.), Iteration 002 → KW3, ..., 010 → KW11.
Events innerhalb einer Iteration werden entlang der Lieferkette (0–16 Tage) gespreizt.
Idempotent: kann beliebig oft ausgeführt werden.

Reihenfolge: patch_timestamps.py → etl_load.py → etl_dwh.py → Analytics
Ausführung (immer aus Repo-Root): python3 bananasupplychain/patch_timestamps.py
"""

import json
import os
import random
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DIRS = {
    "erp": os.path.join(REPO_ROOT, "shared", "erp"),
    "wms": os.path.join(REPO_ROOT, "shared", "wms"),
    "tms": os.path.join(REPO_ROOT, "shared", "tms"),
}

# Stammdaten (Iteration 000): festes Datum vor dem ersten Supply-Chain-Lauf
STAMMDATEN_BASE = datetime(2026, 1, 1, 8, 0, 0)

# Erster Supply-Chain-Lauf: KW2 2026 (Montag, 05.01.2026)
ITERATION_BASE = datetime(2026, 1, 5, 6, 0, 0)
ITERATION_STEP_DAYS = 7  # eine Woche Abstand zwischen Iterationen

# Wann beginnt ein Transport-Segment (Tage ab Iterations-Basisdate, min/max)
ROUTE_START_DAYS = {
    "banana_plantation_to_collection_center": (0.58, 0.75),   # Tag 0, Nachmittag
    "collection_center_to_quality_control": (1.33, 1.67),     # Tag 1, Mittag
    "quality_control_to_africa_cold_storage": (2.50, 3.00),   # Tag 2-3
    "africa_cold_storage_to_europe_cold_storage": (4.25, 5.00),  # Tag 4-5 (Seeweg)
    "europe_cold_storage_to_central_warehouse": (11.33, 12.00),  # Tag 11-12
    "central_warehouse_to_retail_store": (13.42, 14.00),      # Tag 13-14
}

# Reisedauer je Route in Tagen (für estimated_arrival-Berechnung)
ROUTE_TRAVEL_DAYS = {
    "banana_plantation_to_collection_center": 1.0,
    "collection_center_to_quality_control": 0.75,
    "quality_control_to_africa_cold_storage": 1.25,
    "africa_cold_storage_to_europe_cold_storage": 6.0,
    "europe_cold_storage_to_central_warehouse": 1.5,
    "central_warehouse_to_retail_store": 0.75,
}

# Ankunftszeit an einem Knoten in Tagen ab Iterations-Basisdate (min/max)
NODE_ARRIVAL_DAYS = {
    "banana_plantation": (0.00, 0.25),
    "collection_center": (1.00, 1.33),
    "quality_control": (2.00, 2.50),
    "africa_cold_storage": (3.25, 4.00),
    "europe_cold_storage": (10.33, 11.00),
    "central_warehouse": (12.50, 13.00),
    "retail_store": (14.50, 15.00),
}

TS_FMT = "%Y-%m-%dT%H:%M:%S.%f"


def fmt(dt):
    return dt.strftime(TS_FMT)


def _seed_from_filename(filename):
    """Deterministischer Seed pro Datei, damit das Skript idempotent ist."""
    return sum(ord(c) * (i + 1) for i, c in enumerate(filename)) % 100000


def get_iteration(filename):
    if "_iteration_" not in filename:
        return None
    part = filename.split("_iteration_")[1]
    try:
        return int(part.split("_")[0])
    except (ValueError, IndexError):
        return None


def get_base_date(iteration):
    if iteration == 0:
        return STAMMDATEN_BASE
    return ITERATION_BASE + timedelta(days=(iteration - 1) * ITERATION_STEP_DAYS)


def _find_route(filename):
    lower = filename.lower()
    for route in ROUTE_START_DAYS:
        if route in lower:
            return route
    return None


def _find_node(filename):
    lower = filename.lower()
    for node in NODE_ARRIVAL_DAYS:
        if f"_node_{node}_" in lower:
            return node
    return None


def _days_to_td(days_range, rng):
    d = rng.uniform(*days_range)
    return timedelta(days=d)


def compute_new_timestamps(filename, data, base_date, rng):
    event_type = data.get("event_type", "")

    if event_type in (
        "CustomerCreated", "SupplierCreated", "ProductCreated",
        "WarehouseSKUCreated", "CarrierCreated", "TransportProductReferenceCreated",
    ):
        data["timestamp"] = fmt(base_date + timedelta(minutes=rng.randint(0, 180)))

    elif event_type == "OrderCreated":
        data["timestamp"] = fmt(base_date + timedelta(hours=rng.uniform(7, 10)))

    elif event_type == "BatchHarvested":
        data["timestamp"] = fmt(base_date + timedelta(hours=rng.uniform(10, 15)))

    elif event_type == "TransportStarted":
        route = _find_route(filename)
        if not route:
            src = data.get("source_node", "").lower().replace(" ", "_")
            tgt = data.get("target_node", "").lower().replace(" ", "_")
            route = f"{src}_to_{tgt}"
        start_td = _days_to_td(ROUTE_START_DAYS.get(route, (0.5, 1.0)), rng)
        ts = base_date + start_td + timedelta(minutes=rng.randint(0, 90))
        data["timestamp"] = fmt(ts)
        travel_days = ROUTE_TRAVEL_DAYS.get(route, 2.0)
        est = ts + timedelta(days=travel_days, hours=rng.uniform(-3, 3))
        data["estimated_arrival"] = fmt(est)

    elif event_type == "ShipmentPositionUpdated":
        route_data = data.get("current_route", {})
        src = route_data.get("source", "").lower().replace(" ", "_")
        tgt = route_data.get("target", "").lower().replace(" ", "_")
        route = f"{src}_to_{tgt}"
        start_range = ROUTE_START_DAYS.get(route, (0.5, 1.0))
        travel = ROUTE_TRAVEL_DAYS.get(route, 1.0)
        pos_day = rng.uniform(start_range[0], start_range[0] + travel)
        data["timestamp"] = fmt(base_date + timedelta(days=pos_day, hours=rng.uniform(0, 20)))

    elif event_type == "NodeProcessed":
        node = _find_node(filename)
        if not node:
            node = data.get("supply_chain_node", "").lower().replace(" ", "_")
        arrival_td = _days_to_td(NODE_ARRIVAL_DAYS.get(node, (1.0, 2.0)), rng)
        data["timestamp"] = fmt(base_date + arrival_td + timedelta(hours=rng.uniform(8, 18)))

    elif event_type == "TransportCompleted":
        arrival_raw = data.get("arrival_node", "")
        node = arrival_raw.lower().replace(" ", "_")
        arrival_td = _days_to_td(NODE_ARRIVAL_DAYS.get(node, (2.0, 3.0)), rng)
        data["timestamp"] = fmt(base_date + arrival_td + timedelta(hours=rng.uniform(10, 20)))

    elif event_type == "DeliveryCompleted":
        node = _find_node(filename)
        if not node:
            node = data.get("supply_chain_node", "").lower().replace(" ", "_")
        arrival_td = _days_to_td(NODE_ARRIVAL_DAYS.get(node, (14.5, 15.5)), rng)
        data["timestamp"] = fmt(base_date + arrival_td + timedelta(hours=rng.uniform(8, 18)))

    return data


def patch_directory(path, label):
    if not os.path.isdir(path):
        print(f"  [FEHLER] Verzeichnis nicht gefunden: {path}")
        return 0
    count = 0
    skipped = 0
    for filename in sorted(os.listdir(path)):
        if not filename.endswith(".json"):
            continue
        iteration = get_iteration(filename)
        if iteration is None:
            continue
        rng = random.Random(_seed_from_filename(filename))
        base_date = get_base_date(iteration)
        filepath = os.path.join(path, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                print(f"  [SKIP] Leere Datei: {filename}")
                skipped += 1
                continue
            data = json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [SKIP] Parse-Fehler in {filename}: {e}")
            skipped += 1
            continue
        data = compute_new_timestamps(filename, data, base_date, rng)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        count += 1
    msg = f"  {label.upper():<5}: {count:>4} Dateien gepatcht"
    if skipped:
        msg += f"  ({skipped} übersprungen)"
    print(msg)
    return count


def main():
    end_date = ITERATION_BASE + timedelta(days=9 * ITERATION_STEP_DAYS + 16)
    print("=" * 60)
    print("patch_timestamps.py – Supply-Chain-Zeiträume zuweisen")
    print(f"  Stammdaten (Iter 000): {STAMMDATEN_BASE.date()}")
    print(f"  Iter 001 (KW2):  {ITERATION_BASE.date()}")
    print(f"  Iter 010 (KW11): ~{end_date.date()}")
    print("=" * 60)

    total = 0
    for label, directory in SHARED_DIRS.items():
        total += patch_directory(directory, label)

    print(f"\n  Gesamt: {total} JSON-Dateien aktualisiert")
    print("\nNaechste Schritte (Docker muss laufen):")
    print("  python3 bananasupplychain/etl_load.py")
    print("  python3 bananasupplychain/generate_documents.py")
    print("  python3 bananasupplychain/etl_dwh.py")


if __name__ == "__main__":
    main()
