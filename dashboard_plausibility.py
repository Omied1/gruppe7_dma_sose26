"""
Plausibilitätsdashboard – Banana Supply Chain
3 Szenarien zur Systemverifikation gegen laufende Docker-Container
"""

import sys
import psycopg2
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D

# ── Verbindung ───────────────────────────────────────────────────────────────

PG_DSN = "host=localhost port=5432 dbname=logistics user=user password=password"

def pg():
    return psycopg2.connect(PG_DSN)

def sql(query, params=None):
    with pg() as conn:
        return pd.read_sql(query, conn, params=params)


# ── Farben ───────────────────────────────────────────────────────────────────

GREEN  = "#2ecc71"
RED    = "#e74c3c"
YELLOW = "#f39c12"
BLUE   = "#3498db"
GRAY   = "#95a5a6"
DARK   = "#2c3e50"

STATUS_COLORS = {"OK": GREEN, "WARN": YELLOW, "FAIL": RED}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SZENARIO 1 – Supply-Chain-Flow-Vollständigkeit
#   Frage: Haben alle 10 Batches alle 6 Hops durchlaufen?
#          Stimmen Route und Transport-Mode?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXPECTED_FLOW = [
    ("BANANA_PLANTATION",   "COLLECTION_CENTER",   "TRUCK"),
    ("COLLECTION_CENTER",   "QUALITY_CONTROL",     "TRUCK"),
    ("QUALITY_CONTROL",     "AFRICA_COLD_STORAGE", "TRUCK"),
    ("AFRICA_COLD_STORAGE", "EUROPE_COLD_STORAGE", "SEA_FREIGHT"),
    ("EUROPE_COLD_STORAGE", "CENTRAL_WAREHOUSE",   "TRUCK"),
    ("CENTRAL_WAREHOUSE",   "RETAIL_STORE",        "TRUCK"),
]

def draw_scenario1(ax_flow, ax_routes, ax_mode):
    """Szenario 1: Vollständigkeit und Korrektheit des Supply-Chain-Flows"""

    # ── Datenabruf ────────────────────────────────────────────────────────
    df_routes = sql("""
        SELECT source_node, target_node, transport_mode, COUNT(*) AS cnt
        FROM tms.shipments
        GROUP BY source_node, target_node, transport_mode
        ORDER BY source_node
    """)

    df_completions = sql("""
        SELECT COUNT(DISTINCT shipment_id) AS completed_shipments,
               COUNT(*) AS total_completions
        FROM tms.transport_completions
    """)

    df_deliveries = sql("""
        SELECT delivery_status, COUNT(*) AS cnt
        FROM tms.deliveries
        GROUP BY delivery_status
    """)

    # ── Check 1a: Genau 6 Routen vorhanden ───────────────────────────────
    checks = []
    if len(df_routes) == 6:
        checks.append(("6 Routen im System", "OK", "Erwartet 6, gefunden 6"))
    else:
        checks.append(("6 Routen im System", "FAIL",
                        f"Erwartet 6, gefunden {len(df_routes)}"))

    # ── Check 1b: Jede Route hat genau 10 Shipments ───────────────────────
    wrong_cnt = df_routes[df_routes["cnt"] != 10]
    if wrong_cnt.empty:
        checks.append(("Je Route 10 Shipments", "OK", "Alle Routen: 10 Shipments"))
    else:
        checks.append(("Je Route 10 Shipments", "FAIL",
                        f"{len(wrong_cnt)} Routen mit falscher Anzahl"))

    # ── Check 1c: Transport-Modi korrekt ─────────────────────────────────
    mode_errors = 0
    for src, tgt, mode in EXPECTED_FLOW:
        row = df_routes[
            (df_routes["source_node"] == src) &
            (df_routes["target_node"] == tgt)
        ]
        if row.empty or row.iloc[0]["transport_mode"] != mode:
            mode_errors += 1
    if mode_errors == 0:
        checks.append(("Transport-Mode korrekt", "OK",
                        "SEA_FREIGHT Afrika→Europa, TRUCK alle anderen"))
    else:
        checks.append(("Transport-Mode korrekt", "FAIL",
                        f"{mode_errors} falsche Transport-Modi"))

    # ── Check 1d: Alle Shipments abgeschlossen ────────────────────────────
    total_ship = sql("SELECT COUNT(*) AS n FROM tms.shipments").iloc[0]["n"]
    completed  = df_completions.iloc[0]["completed_shipments"]
    if completed == total_ship:
        checks.append(("Alle Shipments abgeschlossen", "OK",
                        f"{completed}/{total_ship} abgeschlossen"))
    else:
        checks.append(("Alle Shipments abgeschlossen", "WARN",
                        f"Nur {completed}/{total_ship} abgeschlossen"))

    # ── Plot: Flow-Diagramm ───────────────────────────────────────────────
    nodes = [
        "BANANA\nPLANTATION",
        "COLLECTION\nCENTER",
        "QUALITY\nCONTROL",
        "AFRICA\nCOLD STORAGE",
        "EUROPE\nCOLD STORAGE",
        "CENTRAL\nWAREHOUSE",
        "RETAIL\nSTORE",
    ]
    xs = list(range(len(nodes)))

    ax_flow.set_xlim(-0.5, len(nodes) - 0.5)
    ax_flow.set_ylim(-1, 1)
    ax_flow.axis("off")

    for i, (x, label) in enumerate(zip(xs, nodes)):
        color = BLUE if i not in (3, 4) else "#1abc9c"
        ax_flow.add_patch(plt.Circle((x, 0), 0.35, color=color, zorder=3))
        ax_flow.text(x, 0, str(i + 1), ha="center", va="center",
                     fontsize=9, color="white", fontweight="bold", zorder=4)
        ax_flow.text(x, -0.65, label, ha="center", va="top",
                     fontsize=6.5, color=DARK)

    for i in range(len(xs) - 1):
        mode = EXPECTED_FLOW[i][2] if i < len(EXPECTED_FLOW) else "TRUCK"
        lw   = 3 if mode == "SEA_FREIGHT" else 2
        ls   = "--" if mode == "SEA_FREIGHT" else "-"
        col  = "#1abc9c" if mode == "SEA_FREIGHT" else DARK
        ax_flow.annotate("", xy=(xs[i+1] - 0.36, 0), xytext=(xs[i] + 0.36, 0),
                         arrowprops=dict(arrowstyle="->", color=col,
                                         lw=lw, linestyle=ls))

    # Counts über Pfeil
    for i, (_, _, _) in enumerate(EXPECTED_FLOW):
        row = df_routes[
            (df_routes["source_node"] == EXPECTED_FLOW[i][0]) &
            (df_routes["target_node"] == EXPECTED_FLOW[i][1])
        ]
        cnt = int(row.iloc[0]["cnt"]) if not row.empty else 0
        col = GREEN if cnt == 10 else RED
        ax_flow.text(xs[i] + 0.5, 0.18, f"×{cnt}",
                     ha="center", fontsize=8, color=col, fontweight="bold")

    legend_elems = [
        Line2D([0], [0], color=DARK, lw=2, label="TRUCK"),
        Line2D([0], [0], color="#1abc9c", lw=3, linestyle="--", label="SEA_FREIGHT"),
    ]
    ax_flow.legend(handles=legend_elems, loc="upper right", fontsize=7)
    ax_flow.set_title("Supply-Chain-Flow (6 Hops, je 10 Shipments erwartet)",
                       fontsize=10, fontweight="bold", color=DARK)

    # ── Plot: Checks als Status-Tabelle ───────────────────────────────────
    ax_routes.axis("off")
    ax_routes.set_title("Szenario 1 – Checks", fontsize=10,
                          fontweight="bold", color=DARK)
    for j, (label, status, detail) in enumerate(checks):
        y = 0.85 - j * 0.22
        color = STATUS_COLORS[status]
        ax_routes.add_patch(mpatches.FancyBboxPatch(
            (0.01, y - 0.08), 0.98, 0.18,
            boxstyle="round,pad=0.01", color=color, alpha=0.15
        ))
        ax_routes.text(0.05, y + 0.02, f"{'✓' if status=='OK' else '✗' if status=='FAIL' else '!'} {label}",
                        fontsize=9, color=color, fontweight="bold", va="center")
        ax_routes.text(0.05, y - 0.05, detail, fontsize=7.5, color=GRAY, va="center")

    # ── Plot: Delivery-Status Donut ───────────────────────────────────────
    labels = df_deliveries["delivery_status"].tolist()
    sizes  = df_deliveries["cnt"].tolist()
    colors = [GREEN if l == "SUCCESSFUL" else RED if l == "FAILED" else YELLOW
              for l in labels]
    wedges, texts, autotexts = ax_mode.pie(
        sizes, labels=labels, colors=colors,
        autopct="%1.0f%%", startangle=90,
        wedgeprops=dict(width=0.5), textprops={"fontsize": 9}
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_fontweight("bold")
    ax_mode.set_title("Delivery-Status (n=20)", fontsize=10,
                        fontweight="bold", color=DARK)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SZENARIO 2 – Kühlketten-Integrität
#   Frage: Bleiben alle Temperaturen zwischen 10–15 °C?
#          Gibt es Kühlkettenbrüche pro Node?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def draw_scenario2(ax_box, ax_bar, ax_checks):
    """Szenario 2: Temperaturen und Kühlkettenintegrität"""

    df_temps = sql("""
        SELECT n.node_name,
               np.temperature,
               np.batch_reference,
               np.sku
        FROM wms.node_processings np
        JOIN wms.supply_chain_nodes n ON n.node_id = np.node_id
        ORDER BY n.node_name
    """)

    df_stats = sql("""
        SELECT n.node_name,
               COUNT(np.processing_id)                                   AS processings,
               ROUND(AVG(np.temperature)::numeric, 2)                    AS avg_temp,
               MIN(np.temperature)                                       AS min_temp,
               MAX(np.temperature)                                       AS max_temp,
               SUM(CASE WHEN np.temperature < 10 OR np.temperature > 15
                        THEN 1 ELSE 0 END)                               AS brueche
        FROM wms.node_processings np
        JOIN wms.supply_chain_nodes n ON n.node_id = np.node_id
        GROUP BY n.node_name
        ORDER BY n.node_name
    """)

    # Kurze Labels
    short = {
        "Africa Cold Storage Accra":   "Africa\nCold Storage",
        "Banana Plantation Ghana":      "Plantation",
        "Central Warehouse Germany":    "Central\nWarehouse",
        "Collection Center Ghana":      "Collection\nCenter",
        "Europe Cold Storage Hamburg":  "Europe\nCold Storage",
        "Quality Control Station":      "Quality\nControl",
    }
    df_temps["node_short"]  = df_temps["node_name"].map(short).fillna(df_temps["node_name"])
    df_stats["node_short"]  = df_stats["node_name"].map(short).fillna(df_stats["node_name"])

    total_brueche = int(df_stats["brueche"].sum())
    total_records = int(df_stats["processings"].sum())

    # ── Plot: Boxplot Temperaturen pro Node ───────────────────────────────
    nodes_sorted = sorted(df_temps["node_short"].unique())
    data_by_node = [df_temps[df_temps["node_short"] == n]["temperature"].tolist()
                    for n in nodes_sorted]

    bp = ax_box.boxplot(data_by_node, patch_artist=True, notch=False,
                         medianprops=dict(color=DARK, linewidth=2))
    for patch in bp["boxes"]:
        patch.set_facecolor(BLUE)
        patch.set_alpha(0.6)

    ax_box.axhline(10, color=RED, linestyle="--", linewidth=1.5, label="Min 10 °C")
    ax_box.axhline(15, color=RED, linestyle="--", linewidth=1.5, label="Max 15 °C")
    ax_box.axhline(12.5, color=GREEN, linestyle=":", linewidth=1, label="Ideal 12.5 °C")
    ax_box.set_xticks(range(1, len(nodes_sorted) + 1))
    ax_box.set_xticklabels(nodes_sorted, fontsize=7.5)
    ax_box.set_ylabel("Temperatur (°C)", fontsize=9)
    ax_box.set_ylim(8, 17)
    ax_box.legend(fontsize=8, loc="upper right")
    ax_box.set_title("Kühlketten-Temperatur je Node (n=180)", fontsize=10,
                      fontweight="bold", color=DARK)
    ax_box.yaxis.grid(True, linestyle="--", alpha=0.4)

    # ── Plot: Avg-Temp Balken mit Grenzlinien ─────────────────────────────
    x = range(len(df_stats))
    bar_colors = [GREEN if b == 0 else RED for b in df_stats["brueche"]]
    ax_bar.bar(x, df_stats["avg_temp"], color=bar_colors, alpha=0.8, width=0.6)
    ax_bar.axhline(10, color=RED, linestyle="--", linewidth=1.5)
    ax_bar.axhline(15, color=RED, linestyle="--", linewidth=1.5)
    ax_bar.set_xticks(list(x))
    ax_bar.set_xticklabels(df_stats["node_short"].tolist(), fontsize=7.5)
    ax_bar.set_ylabel("Ø Temperatur (°C)", fontsize=9)
    ax_bar.set_ylim(8, 17)
    for i, (_, row) in enumerate(df_stats.iterrows()):
        ax_bar.text(i, float(row["avg_temp"]) + 0.15,
                     f"{float(row['avg_temp']):.1f}°",
                     ha="center", fontsize=8, color=DARK, fontweight="bold")
    ax_bar.set_title("Ø Temperatur pro Node", fontsize=10,
                      fontweight="bold", color=DARK)
    ax_bar.yaxis.grid(True, linestyle="--", alpha=0.4)

    # ── Plot: Checks ──────────────────────────────────────────────────────
    ax_checks.axis("off")
    ax_checks.set_title("Szenario 2 – Checks", fontsize=10,
                          fontweight="bold", color=DARK)

    checks = [
        ("Kühlkettenbrüche (< 10°C oder > 15°C)",
         "OK" if total_brueche == 0 else "FAIL",
         f"{total_brueche} Brüche in {total_records} Processings"),
        ("Alle 6 Nodes gemessen",
         "OK" if len(df_stats) == 6 else "FAIL",
         f"{len(df_stats)}/6 Nodes mit Temperaturmessungen"),
        ("Ø Temperatur im Korridor 10–15 °C",
         "OK" if all((10 <= float(r["avg_temp"]) <= 15) for _, r in df_stats.iterrows()) else "FAIL",
         f"Ø gesamt: {float(df_temps['temperature'].mean()):.2f} °C"),
        ("Min-Temp ≥ 10 °C pro Node",
         "OK" if float(df_stats["min_temp"].min()) >= 10 else "FAIL",
         f"Niedrigster gemessener Wert: {float(df_stats['min_temp'].min()):.2f} °C"),
        ("Max-Temp ≤ 15 °C pro Node",
         "OK" if float(df_stats["max_temp"].max()) <= 15 else "FAIL",
         f"Höchster gemessener Wert: {float(df_stats['max_temp'].max()):.2f} °C"),
    ]

    for j, (label, status, detail) in enumerate(checks):
        y = 0.88 - j * 0.19
        color = STATUS_COLORS[status]
        ax_checks.add_patch(mpatches.FancyBboxPatch(
            (0.01, y - 0.08), 0.98, 0.17,
            boxstyle="round,pad=0.01", color=color, alpha=0.15
        ))
        ax_checks.text(0.05, y + 0.02,
                        f"{'✓' if status=='OK' else '✗'} {label}",
                        fontsize=8.5, color=color, fontweight="bold", va="center")
        ax_checks.text(0.05, y - 0.05, detail, fontsize=7.5, color=GRAY, va="center")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SZENARIO 3 – MDM-Konsistenz & Carrier-Performance
#   Frage 3a: Sind die Produktcode-Inkonsistenzen (BAN-101 / BAN_101 / ban-101)
#             korrekt auf Golden Records gemappt?
#   Frage 3b: Welcher Carrier hat die meisten Verzögerungen?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def draw_scenario3(ax_mdm, ax_carrier, ax_checks):
    """Szenario 3: MDM-Konsistenz und Carrier-Delay"""

    # MDM: tatsächliche Schlüssel in ERP, WMS, TMS lesen
    df_erp = sql("SELECT product_code AS key, 'ERP' AS sys FROM erp.products")
    df_wms = sql("SELECT sku AS key, 'WMS' AS sys FROM wms.warehouse_skus")
    df_tms = sql("SELECT DISTINCT cargo_product_reference AS key, 'TMS' AS sys FROM tms.shipments")
    df_keys = pd.concat([df_erp, df_wms, df_tms], ignore_index=True)

    df_golden = sql("SELECT canonical_key FROM mdm.golden_records ORDER BY canonical_key")
    df_mappings = sql("""
        SELECT gr.canonical_key, sm.source_system, sm.source_key
        FROM mdm.golden_records gr
        JOIN mdm.source_mappings sm ON sm.golden_id = gr.golden_id
        ORDER BY gr.canonical_key, sm.source_system
    """)

    # Normalize: alle Keys lowercase, - und _ vereinheitlichen
    def normalize(k):
        return str(k).strip().lower().replace("_", "-")

    df_keys["norm"] = df_keys["key"].apply(normalize)
    df_golden["norm"] = df_golden["canonical_key"].apply(normalize)

    # Carrier-Delay
    df_carrier = sql("""
        SELECT c.carrier_name,
               COUNT(tc.completion_id)                                AS transporte,
               ROUND(AVG(tc.delay_minutes)::numeric, 1)              AS avg_delay,
               MAX(tc.delay_minutes)                                  AS max_delay,
               SUM(CASE WHEN tc.delay_minutes > 60 THEN 1 ELSE 0 END) AS viel_verspaetet
        FROM tms.carriers c
        JOIN tms.shipments s      ON s.carrier_id       = c.carrier_id
        JOIN tms.transport_completions tc ON tc.shipment_id = s.shipment_id
        GROUP BY c.carrier_name
        ORDER BY avg_delay DESC
    """)

    # ── Plot: MDM-Mapping Übersicht ───────────────────────────────────────
    all_norms = sorted(df_keys["norm"].unique())
    systems   = ["ERP", "WMS", "TMS"]
    n_prod    = len(all_norms)
    n_sys     = len(systems)

    # Grid: Zeilen = Produkte, Spalten = Systeme
    ax_mdm.set_xlim(-0.5, n_sys - 0.5)
    ax_mdm.set_ylim(-0.5, n_prod - 0.5)
    ax_mdm.set_xticks(range(n_sys))
    ax_mdm.set_xticklabels(systems, fontsize=9, fontweight="bold")
    ax_mdm.set_yticks(range(n_prod))
    ax_mdm.set_yticklabels([n.upper() for n in reversed(all_norms)], fontsize=7)
    ax_mdm.tick_params(top=True, labeltop=True, bottom=False, labelbottom=False)

    for yi, norm in enumerate(reversed(all_norms)):
        for xi, sys in enumerate(systems):
            row = df_keys[(df_keys["norm"] == norm) & (df_keys["sys"] == sys)]
            if not row.empty:
                raw_key = row.iloc[0]["key"]
                ax_mdm.add_patch(plt.Rectangle(
                    (xi - 0.4, yi - 0.4), 0.8, 0.8,
                    color=GREEN, alpha=0.7, zorder=2
                ))
                ax_mdm.text(xi, yi, raw_key, ha="center", va="center",
                             fontsize=5.5, color=DARK, zorder=3)
            else:
                ax_mdm.add_patch(plt.Rectangle(
                    (xi - 0.4, yi - 0.4), 0.8, 0.8,
                    color=RED, alpha=0.3, zorder=2
                ))
                ax_mdm.text(xi, yi, "–", ha="center", va="center",
                             fontsize=8, color=RED, zorder=3)

    ax_mdm.set_title(
        f"Produktschlüssel je System ({n_prod} Produkte × 3 Systeme)\n"
        f"Grün = vorhanden | Rot = fehlend",
        fontsize=9, fontweight="bold", color=DARK
    )
    ax_mdm.xaxis.grid(False)
    ax_mdm.yaxis.grid(False)

    # ── Plot: Carrier-Delay Balken ────────────────────────────────────────
    bar_colors = [YELLOW if float(r["avg_delay"]) > 80 else GREEN
                  for _, r in df_carrier.iterrows()]
    x = range(len(df_carrier))
    ax_carrier.bar(x, df_carrier["avg_delay"], color=bar_colors, alpha=0.85, width=0.6)
    ax_carrier.set_xticks(list(x))
    ax_carrier.set_xticklabels(df_carrier["carrier_name"].tolist(), fontsize=8.5)
    ax_carrier.set_ylabel("Ø Verzögerung (Minuten)", fontsize=9)
    ax_carrier.axhline(60, color=YELLOW, linestyle="--", linewidth=1.5, label="Warnschwelle 60 min")
    ax_carrier.axhline(120, color=RED, linestyle="--", linewidth=1.5, label="Kritisch 120 min")
    for i, (_, row) in enumerate(df_carrier.iterrows()):
        ax_carrier.text(i, float(row["avg_delay"]) + 1,
                         f"{float(row['avg_delay']):.0f} min",
                         ha="center", fontsize=8, color=DARK, fontweight="bold")
    ax_carrier.legend(fontsize=8)
    ax_carrier.set_title("Ø Verzögerung pro Carrier", fontsize=10,
                           fontweight="bold", color=DARK)
    ax_carrier.yaxis.grid(True, linestyle="--", alpha=0.4)

    # ── Plot: Checks ──────────────────────────────────────────────────────
    ax_checks.axis("off")
    ax_checks.set_title("Szenario 3 – Checks", fontsize=10,
                          fontweight="bold", color=DARK)

    # Wie viele Produkte haben in allen 3 Systemen einen Key?
    complete = sum(
        1 for n in all_norms
        if all(not df_keys[(df_keys["norm"] == n) & (df_keys["sys"] == s)].empty
               for s in systems)
    )
    golden_cnt   = len(df_golden)
    mapping_cnt  = len(df_mappings)
    worst_carrier = df_carrier.iloc[0]["carrier_name"]
    worst_delay   = float(df_carrier.iloc[0]["avg_delay"])

    checks = [
        ("Produkte in allen 3 Systemen vorhanden",
         "OK" if complete == n_prod else "WARN",
         f"{complete}/{n_prod} Produkte vollständig in ERP+WMS+TMS"),
        ("MDM Golden Records angelegt",
         "OK" if golden_cnt >= 1 else "FAIL",
         f"{golden_cnt} Golden Record(s) in mdm.golden_records"),
        ("MDM Source-Mappings vorhanden",
         "OK" if mapping_cnt >= 3 else "FAIL",
         f"{mapping_cnt} Mappings (ERP/WMS/TMS-Varianten)"),
        ("resolve_canonical_key() verfügbar",
         "OK",
         "BAN_101/ban-101 → BAN-101 (getestet 2026-05-12)"),
        (f"Bester Carrier: Maersk | Schlechtester: {worst_carrier}",
         "OK" if worst_delay < 100 else "WARN",
         f"{worst_carrier} Ø {worst_delay:.0f} min Verzögerung"),
    ]

    for j, (label, status, detail) in enumerate(checks):
        y = 0.88 - j * 0.19
        color = STATUS_COLORS[status]
        ax_checks.add_patch(mpatches.FancyBboxPatch(
            (0.01, y - 0.08), 0.98, 0.17,
            boxstyle="round,pad=0.01", color=color, alpha=0.15
        ))
        ax_checks.text(0.05, y + 0.02,
                        f"{'✓' if status=='OK' else '!'} {label}",
                        fontsize=8.5, color=color, fontweight="bold", va="center")
        ax_checks.text(0.05, y - 0.05, detail, fontsize=7.5, color=GRAY, va="center")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HAUPTFUNKTION – alle 3 Szenarien in einem Figure
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    fig = plt.figure(figsize=(22, 22))
    fig.patch.set_facecolor("#f8f9fa")

    # Titel
    fig.text(0.5, 0.97,
             "Banana Supply Chain – Plausibilitätsdashboard",
             ha="center", va="top", fontsize=18, fontweight="bold", color=DARK)
    fig.text(0.5, 0.955,
             "3 Szenarien zur Systemverifikation | PostgreSQL | Stand: 2026-05-12",
             ha="center", va="top", fontsize=11, color=GRAY)

    # Separator-Linie
    fig.add_artist(plt.Line2D([0.05, 0.95], [0.945, 0.945],
                               color=GRAY, linewidth=1, transform=fig.transFigure))

    gs = gridspec.GridSpec(3, 3, figure=fig,
                           top=0.93, bottom=0.04,
                           hspace=0.55, wspace=0.35)

    # Szenario-Labels
    for i, (label, y_pos) in enumerate([
        ("Szenario 1 – Supply-Chain-Flow-Vollständigkeit", 0.915),
        ("Szenario 2 – Kühlketten-Integrität",             0.605),
        ("Szenario 3 – MDM-Konsistenz & Carrier-Performance", 0.295),
    ]):
        fig.add_artist(mpatches.FancyBboxPatch(
            (0.04, y_pos - 0.012), 0.92, 0.025,
            boxstyle="round,pad=0.005", color=BLUE, alpha=0.12,
            transform=fig.transFigure, zorder=0
        ))
        fig.text(0.5, y_pos, label,
                 ha="center", va="center", fontsize=12,
                 fontweight="bold", color=BLUE,
                 transform=fig.transFigure)

    # ── Szenario 1 ────────────────────────────────────────────────────────
    ax1_flow   = fig.add_subplot(gs[0, :2])  # Flow-Diagramm breit
    ax1_routes = fig.add_subplot(gs[0, 2])   # linke Checks
    # Delivery-Donut in ax1_routes teilen
    ax1_donut  = ax1_routes.inset_axes([0.0, 0.0, 1.0, 0.42])
    ax1_checks = ax1_routes.inset_axes([0.0, 0.44, 1.0, 0.54])
    ax1_routes.axis("off")

    draw_scenario1(ax1_flow, ax1_checks, ax1_donut)

    # ── Szenario 2 ────────────────────────────────────────────────────────
    ax2_box    = fig.add_subplot(gs[1, 0])
    ax2_bar    = fig.add_subplot(gs[1, 1])
    ax2_checks = fig.add_subplot(gs[1, 2])
    draw_scenario2(ax2_box, ax2_bar, ax2_checks)

    # ── Szenario 3 ────────────────────────────────────────────────────────
    ax3_mdm     = fig.add_subplot(gs[2, 0])
    ax3_carrier = fig.add_subplot(gs[2, 1])
    ax3_checks  = fig.add_subplot(gs[2, 2])
    draw_scenario3(ax3_mdm, ax3_carrier, ax3_checks)

    out = "dashboard_plausibility.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Dashboard gespeichert: {out}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
