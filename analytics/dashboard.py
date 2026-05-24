"""
=============================================================================
dashboard.py – BI-Dashboard Banana Supply Chain
=============================================================================
Erstellt 5 wirtschaftlich getriebene Charts als:
  - dashboard.pdf / dashboard.png  (statisch, matplotlib + seaborn)
  - dashboard.html                 (interaktiv, plotly)

Charts:
  1. Umsatz-Zeitreihe nach Kunde        (Line Chart)
  2. Carrier-Performance: Liefertreue   (Stacked Bar)
  3. Umsatz nach Produktsorte           (Horizontal Bar)
  4. Ø Verzögerung pro Supply-Chain-Knoten (Horizontal Bar)
  5. Kühlkettenqualität vs. Lieferstatus   (Box Plot)

Voraussetzung:
  - PostgreSQL läuft auf localhost:5432, DB: logistics
  - dwh.fact_fulfillment + Dimensionen sind via ETL befüllt
  - pip install psycopg2-binary pandas matplotlib seaborn plotly kaleido

Ausführung:
  cd analytics
  python dashboard.py
=============================================================================
"""

import sys
import os
import decimal
import warnings
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Abhängigkeiten prüfen
# ---------------------------------------------------------------------------
MISSING = []
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    MISSING.append("psycopg2-binary")
try:
    import pandas as pd
except ImportError:
    MISSING.append("pandas")
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import seaborn as sns
except ImportError:
    MISSING.append("matplotlib seaborn")
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
except ImportError:
    MISSING.append("plotly")

if MISSING:
    print(f"[FEHLER] Fehlende Pakete: {', '.join(MISSING)}")
    print(f"         pip install {' '.join(MISSING)}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
PG_DSN      = "host=localhost port=5432 dbname=logistics user=user password=password"
OUTPUT_DIR  = os.path.dirname(os.path.abspath(__file__))
PDF_PATH    = os.path.join(OUTPUT_DIR, "dashboard.pdf")
PNG_PATH    = os.path.join(OUTPUT_DIR, "dashboard.png")
HTML_PATH   = os.path.join(OUTPUT_DIR, "dashboard.html")

# Farben: Corporate Look (Banana-Gelb + Blau)
COLOR_PALETTE   = ["#2563EB", "#16A34A", "#DC2626", "#D97706", "#7C3AED"]
COLOR_SUCCESS   = "#16A34A"
COLOR_DELAYED   = "#D97706"
COLOR_FAILED    = "#DC2626"
STATUS_COLORS   = {"SUCCESSFUL": COLOR_SUCCESS, "DELAYED": COLOR_DELAYED, "FAILED": COLOR_FAILED}

# ---------------------------------------------------------------------------
# Datenbankverbindung & Queries
# ---------------------------------------------------------------------------

def connect():
    try:
        conn = psycopg2.connect(PG_DSN)
        print("[OK] Datenbankverbindung hergestellt.")
        return conn
    except Exception as e:
        print(f"[FEHLER] DB-Verbindung fehlgeschlagen: {e}")
        sys.exit(1)


def load_data(conn):
    """Alle 5 Datasets in einem Schritt laden."""
    print("[...] Lade Daten aus DWH...")
    datasets = {}
    queries = {

        # Chart 1: Umsatz nach Kunde pro Monat
        "umsatz_zeitreihe": """
            SELECT
                dd.year                     AS jahr,
                dd.month                    AS monat,
                dc.customer_name            AS kunde,
                SUM(f.total_value)          AS umsatz
            FROM dwh.fact_fulfillment f
            JOIN dwh.dim_customer        dc  ON f.customer_sk       = dc.customer_sk
            JOIN dwh.dim_date            dd  ON f.order_date_sk     = dd.date_sk
            GROUP BY dd.year, dd.month, dc.customer_name
            ORDER BY dd.year, dd.month, dc.customer_name
        """,

        # Chart 2: Carrier-Performance (Lieferstatus-Verteilung)
        "carrier_performance": """
            SELECT
                dcar.carrier_name           AS carrier,
                ds.status_code              AS status,
                COUNT(*)                    AS anzahl
            FROM dwh.fact_fulfillment f
            JOIN dwh.dim_carrier         dcar ON f.carrier_sk          = dcar.carrier_sk
            JOIN dwh.dim_delivery_status ds   ON f.delivery_status_sk  = ds.status_sk
            GROUP BY dcar.carrier_name, ds.status_code
            ORDER BY dcar.carrier_name, ds.status_code
        """,

        # Chart 3: Umsatz nach Produktsorte
        "umsatz_produkt": """
            SELECT
                dp.product_name             AS produkt,
                SUM(f.total_value)          AS umsatz,
                SUM(f.quantity)             AS menge
            FROM dwh.fact_fulfillment f
            JOIN dwh.dim_product         dp  ON f.product_sk          = dp.product_sk
            GROUP BY dp.product_name
            ORDER BY umsatz DESC
        """,

        # Chart 4: Ø Verzögerung pro Supply-Chain-Knoten
        "verzoegerung_knoten": """
            SELECT
                dn.node_name                AS knoten,
                dn.node_type                AS knotentyp,
                ROUND(AVG(f.delay_minutes), 1) AS avg_verzoegerung,
                COUNT(*)                    AS anzahl_lieferungen
            FROM dwh.fact_fulfillment f
            JOIN dwh.dim_supply_chain_node dn ON f.destination_node_sk = dn.node_sk
            GROUP BY dn.node_name, dn.node_type
            ORDER BY avg_verzoegerung DESC
        """,

        # Chart 5: Kühlkettentemperatur nach Lieferstatus
        "kuehlkette_status": """
            SELECT
                ds.status_code              AS status,
                f.avg_temperature           AS temperatur
            FROM dwh.fact_fulfillment f
            JOIN dwh.dim_delivery_status ds ON f.delivery_status_sk = ds.status_sk
            WHERE f.avg_temperature IS NOT NULL
            ORDER BY ds.status_code
        """,
    }

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        for name, sql in queries.items():
            cur.execute(sql)
            rows = cur.fetchall()
            df = pd.DataFrame(rows, columns=[d[0] for d in cur.description])
            # PostgreSQL NUMERIC/DECIMAL → float
            for col in df.columns:
                df[col] = df[col].apply(
                    lambda x: float(x) if isinstance(x, decimal.Decimal) else x
                )
            datasets[name] = df
            print(f"  [{name}]: {len(datasets[name])} Zeilen")

    return datasets


# ---------------------------------------------------------------------------
# Statisches Dashboard (matplotlib + seaborn → PDF + PNG)
# ---------------------------------------------------------------------------

def build_static_dashboard(datasets):
    print("[...] Erstelle statisches Dashboard (PDF/PNG)...")

    sns.set_theme(style="whitegrid", font_scale=0.9)
    fig = plt.figure(figsize=(20, 14), facecolor="#F8FAFC")
    fig.suptitle(
        "Banana Supply Chain – BI Dashboard",
        fontsize=18, fontweight="bold", color="#1E3A5F", y=0.98
    )

    gs = gridspec.GridSpec(
        2, 3,
        figure=fig,
        hspace=0.45,
        wspace=0.35,
        top=0.93, bottom=0.07,
        left=0.06, right=0.97
    )

    ax1 = fig.add_subplot(gs[0, :2])   # Chart 1: breiter oben links
    ax2 = fig.add_subplot(gs[0, 2])    # Chart 2: oben rechts
    ax3 = fig.add_subplot(gs[1, 0])    # Chart 3: unten links
    ax4 = fig.add_subplot(gs[1, 1])    # Chart 4: unten mitte
    ax5 = fig.add_subplot(gs[1, 2])    # Chart 5: unten rechts

    # -- Chart 1: Umsatz-Zeitreihe nach Kunde --
    df1 = datasets["umsatz_zeitreihe"].copy()
    if not df1.empty:
        df1["periode"] = df1["jahr"].astype(str) + "-" + df1["monat"].astype(str).str.zfill(2)
        pivot = df1.pivot_table(index="periode", columns="kunde", values="umsatz", aggfunc="sum").fillna(0)
        pivot = pivot.sort_index()
        colors = COLOR_PALETTE[:len(pivot.columns)]
        for col, color in zip(pivot.columns, colors):
            ax1.plot(pivot.index, pivot[col], marker="o", linewidth=2,
                     markersize=4, label=col, color=color)
        ax1.set_title("① Monatlicher Umsatz nach Kunde (EUR)", fontweight="bold", color="#1E3A5F")
        ax1.set_xlabel("Monat")
        ax1.set_ylabel("Umsatz (EUR)")
        ax1.tick_params(axis="x", rotation=45)
        ax1.legend(loc="upper left", fontsize=7, ncol=2)
        ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    else:
        ax1.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_title("① Monatlicher Umsatz nach Kunde", fontweight="bold")

    # -- Chart 2: Carrier-Performance --
    df2 = datasets["carrier_performance"].copy()
    if not df2.empty:
        pivot2 = df2.pivot_table(index="carrier", columns="status", values="anzahl", aggfunc="sum").fillna(0)
        # Reihenfolge: SUCCESSFUL, DELAYED, FAILED
        cols_order = [c for c in ["SUCCESSFUL", "DELAYED", "FAILED"] if c in pivot2.columns]
        pivot2 = pivot2[cols_order]
        bottom = pd.Series([0.0] * len(pivot2), index=pivot2.index)
        for col in cols_order:
            ax2.barh(pivot2.index, pivot2[col], left=bottom,
                     color=STATUS_COLORS.get(col, "#999"),
                     label=col, height=0.6)
            bottom += pivot2[col]
        ax2.set_title("② Carrier-Performance\n(Lieferstatus)", fontweight="bold", color="#1E3A5F")
        ax2.set_xlabel("Anzahl Lieferungen")
        ax2.legend(loc="lower right", fontsize=7)
        ax2.invert_yaxis()
    else:
        ax2.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax2.transAxes)
        ax2.set_title("② Carrier-Performance", fontweight="bold")

    # -- Chart 3: Umsatz nach Produktsorte --
    df3 = datasets["umsatz_produkt"].copy()
    if not df3.empty:
        df3 = df3.sort_values("umsatz", ascending=True)
        bars = ax3.barh(df3["produkt"], df3["umsatz"],
                        color=COLOR_PALETTE[:len(df3)], height=0.65)
        ax3.set_title("③ Umsatz nach Produktsorte\n(EUR)", fontweight="bold", color="#1E3A5F")
        ax3.set_xlabel("Umsatz (EUR)")
        ax3.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}k"))
        for bar, val in zip(bars, df3["umsatz"]):
            ax3.text(val * 1.01, bar.get_y() + bar.get_height() / 2,
                     f"{val/1000:.1f}k", va="center", fontsize=7)
    else:
        ax3.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax3.transAxes)
        ax3.set_title("③ Umsatz nach Produktsorte", fontweight="bold")

    # -- Chart 4: Ø Verzögerung pro Knoten --
    df4 = datasets["verzoegerung_knoten"].copy()
    if not df4.empty:
        df4 = df4.sort_values("avg_verzoegerung", ascending=True)
        palette4 = [COLOR_FAILED if v > 30 else COLOR_DELAYED if v > 10 else COLOR_SUCCESS
                    for v in df4["avg_verzoegerung"]]
        bars4 = ax4.barh(df4["knoten"], df4["avg_verzoegerung"], color=palette4, height=0.65)
        ax4.axvline(x=30, color="#DC2626", linestyle="--", linewidth=1.2, label="SLA-Grenze (30 min)")
        ax4.set_title("④ Ø Verzögerung pro\nSupply-Chain-Knoten (min)", fontweight="bold", color="#1E3A5F")
        ax4.set_xlabel("Ø Verzögerung (Minuten)")
        ax4.legend(fontsize=7)
        for bar, val in zip(bars4, df4["avg_verzoegerung"]):
            ax4.text(val + 0.5, bar.get_y() + bar.get_height() / 2,
                     f"{val:.1f}", va="center", fontsize=7)
    else:
        ax4.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax4.transAxes)
        ax4.set_title("④ Verzögerung pro Knoten", fontweight="bold")

    # -- Chart 5: Kühlkette vs. Lieferstatus (Box Plot) --
    df5 = datasets["kuehlkette_status"].copy()
    if not df5.empty:
        status_order = [s for s in ["SUCCESSFUL", "DELAYED", "FAILED"] if s in df5["status"].unique()]
        colors5 = [STATUS_COLORS[s] for s in status_order]
        data_grouped = [df5[df5["status"] == s]["temperatur"].values for s in status_order]
        bp = ax5.boxplot(data_grouped, labels=status_order, patch_artist=True,
                         medianprops={"color": "black", "linewidth": 2})
        for patch, color in zip(bp["boxes"], colors5):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        ax5.axhline(y=10, color="#1D4ED8", linestyle="--", linewidth=1, label="Soll-Min (10°C)")
        ax5.axhline(y=15, color="#1D4ED8", linestyle=":",  linewidth=1, label="Soll-Max (15°C)")
        ax5.set_title("⑤ Kühlkettentemperatur\nvs. Lieferstatus (°C)", fontweight="bold", color="#1E3A5F")
        ax5.set_ylabel("Temperatur (°C)")
        ax5.legend(fontsize=7)
    else:
        ax5.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax5.transAxes)
        ax5.set_title("⑤ Kühlkette vs. Lieferstatus", fontweight="bold")

    # Fußzeile
    fig.text(0.5, 0.01,
             "Datenquelle: dwh.fact_fulfillment | Gruppe 7 – DMA SoSe 26 | TH Lübeck",
             ha="center", fontsize=8, color="#64748B")

    # Speichern
    fig.savefig(PNG_PATH, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(PDF_PATH, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[OK] Statisches Dashboard gespeichert:")
    print(f"     {PNG_PATH}")
    print(f"     {PDF_PATH}")


# ---------------------------------------------------------------------------
# Interaktives Dashboard (plotly → HTML)
# ---------------------------------------------------------------------------

def build_interactive_dashboard(datasets):
    print("[...] Erstelle interaktives Dashboard (HTML)...")

    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=(
            "① Monatlicher Umsatz nach Kunde (EUR)",
            "② Carrier-Performance (Lieferstatus)",
            "③ Umsatz nach Produktsorte",
            "④ Ø Verzögerung pro Knoten (min)",
            "⑤ Kühlkette vs. Lieferstatus (°C)",
            ""
        ),
        specs=[
            [{"colspan": 2}, None, {"type": "bar"}],
            [{"type": "bar"},  {"type": "bar"}, {"type": "box"}],
        ],
        vertical_spacing=0.18,
        horizontal_spacing=0.1,
    )

    # -- Chart 1 --
    df1 = datasets["umsatz_zeitreihe"].copy()
    if not df1.empty:
        df1["periode"] = df1["jahr"].astype(str) + "-" + df1["monat"].astype(str).str.zfill(2)
        pivot = df1.pivot_table(index="periode", columns="kunde", values="umsatz", aggfunc="sum").fillna(0)
        pivot = pivot.sort_index()
        for i, col in enumerate(pivot.columns):
            fig.add_trace(
                go.Scatter(
                    x=pivot.index, y=pivot[col], mode="lines+markers",
                    name=col, line={"color": COLOR_PALETTE[i % len(COLOR_PALETTE)], "width": 2},
                    hovertemplate=f"<b>{col}</b><br>%{{x}}<br>EUR %{{y:,.0f}}<extra></extra>",
                ),
                row=1, col=1
            )

    # -- Chart 2 --
    df2 = datasets["carrier_performance"].copy()
    if not df2.empty:
        pivot2 = df2.pivot_table(index="carrier", columns="status", values="anzahl", aggfunc="sum").fillna(0)
        for status in ["SUCCESSFUL", "DELAYED", "FAILED"]:
            if status in pivot2.columns:
                fig.add_trace(
                    go.Bar(
                        y=pivot2.index, x=pivot2[status], name=status,
                        orientation="h",
                        marker_color=STATUS_COLORS[status],
                        hovertemplate=f"<b>{status}</b><br>%{{y}}: %{{x}} Lieferungen<extra></extra>",
                        legendgroup=status,
                        showlegend=(df2 is not None),
                    ),
                    row=1, col=3
                )

    # -- Chart 3 --
    df3 = datasets["umsatz_produkt"].copy()
    if not df3.empty:
        df3 = df3.sort_values("umsatz", ascending=True)
        fig.add_trace(
            go.Bar(
                y=df3["produkt"], x=df3["umsatz"], orientation="h",
                marker_color=COLOR_PALETTE[2],
                hovertemplate="<b>%{y}</b><br>Umsatz: EUR %{x:,.0f}<extra></extra>",
                name="Umsatz",
                showlegend=False,
            ),
            row=2, col=1
        )

    # -- Chart 4 --
    df4 = datasets["verzoegerung_knoten"].copy()
    if not df4.empty:
        df4 = df4.sort_values("avg_verzoegerung", ascending=True)
        bar_colors = [COLOR_FAILED if v > 30 else COLOR_DELAYED if v > 10 else COLOR_SUCCESS
                      for v in df4["avg_verzoegerung"]]
        fig.add_trace(
            go.Bar(
                y=df4["knoten"], x=df4["avg_verzoegerung"], orientation="h",
                marker_color=bar_colors,
                hovertemplate="<b>%{y}</b><br>Ø Verzögerung: %{x:.1f} min<extra></extra>",
                name="Verzögerung",
                showlegend=False,
            ),
            row=2, col=2
        )
        # SLA-Linie
        fig.add_vline(x=30, line_dash="dash", line_color="#DC2626",
                      annotation_text="SLA 30 min", row=2, col=2)

    # -- Chart 5 --
    df5 = datasets["kuehlkette_status"].copy()
    if not df5.empty:
        for status in ["SUCCESSFUL", "DELAYED", "FAILED"]:
            subset = df5[df5["status"] == status]["temperatur"]
            if not subset.empty:
                fig.add_trace(
                    go.Box(
                        y=subset, name=status,
                        marker_color=STATUS_COLORS[status],
                        boxmean=True,
                        hovertemplate=f"<b>{status}</b><br>Temperatur: %{{y:.1f}}°C<extra></extra>",
                        showlegend=False,
                    ),
                    row=2, col=3
                )
        # Soll-Bereich
        fig.add_hrect(y0=10, y1=15, fillcolor="rgba(37,99,235,0.08)",
                      line_width=0, row=2, col=3,
                      annotation_text="Soll 10–15°C", annotation_position="top right")

    # Layout
    fig.update_layout(
        title={
            "text": "🍌 Banana Supply Chain – BI Dashboard",
            "x": 0.5, "xanchor": "center",
            "font": {"size": 22, "color": "#1E3A5F"}
        },
        barmode="stack",
        height=800,
        paper_bgcolor="#F8FAFC",
        plot_bgcolor="#FFFFFF",
        font={"family": "Inter, Arial, sans-serif", "size": 11},
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.08, "x": 0.5, "xanchor": "center"},
        margin={"t": 100, "b": 80},
        annotations=[
            {
                "text": "Datenquelle: dwh.fact_fulfillment | Gruppe 7 – DMA SoSe 26 | TH Lübeck",
                "x": 0.5, "y": -0.06, "xref": "paper", "yref": "paper",
                "showarrow": False, "font": {"size": 10, "color": "#64748B"}
            }
        ]
    )

    fig.write_html(
        HTML_PATH,
        include_plotlyjs="cdn",
        full_html=True,
        config={"displayModeBar": True, "scrollZoom": True}
    )
    print(f"[OK] Interaktives Dashboard gespeichert:")
    print(f"     {HTML_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Banana Supply Chain – BI Dashboard Generator")
    print("=" * 60)

    conn = connect()
    try:
        datasets = load_data(conn)

        # Prüfe ob Daten vorhanden
        total_rows = sum(len(df) for df in datasets.values())
        if total_rows == 0:
            print("[WARNUNG] Alle Datasets sind leer – DWH befüllt?")
            print("          Führe zuerst: python bananasupplychain/etl_dwh.py aus")

        build_static_dashboard(datasets)
        build_interactive_dashboard(datasets)

    finally:
        conn.close()

    print()
    print("=" * 60)
    print("  Fertig! Ausgabedateien:")
    print(f"  - {os.path.basename(PDF_PATH)}")
    print(f"  - {os.path.basename(PNG_PATH)}")
    print(f"  - {os.path.basename(HTML_PATH)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
