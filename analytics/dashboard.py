"""
=============================================================================
dashboard.py – BI-Dashboard Banana Supply Chain
=============================================================================
Erstellt 5 wirtschaftlich getriebene Charts als:
  - dashboard.pdf / dashboard.png  (statisch, matplotlib + seaborn)
  - dashboard.html                 (interaktiv, plotly)

Charts [ANPASSUNG 2026-07-02 – auf neue Generator-Felder gehoben]:
  1. Umsatz-Zeitreihe nach Kundensegment    (Line Chart, customer_type)
  2. Verspätungsgründe je Transport-Leg     (Horizontal Bar, delay_reason)
  3. Bestellwert nach Kundentyp             (Box Plot, customer_type)
  4. Ø Transportkosten je Route             (Horizontal Bar, transport_cost/distance)
  5. Batchqualität über Zeit                (Line Chart, v_batch_quality)

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
import tempfile
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
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib"))
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
    # [ANPASSUNG 2026-07-02] Dashboard auf die neuen Generator-Felder gehoben:
    # Kundensegmente (customer_type), Verspätungsgründe (delay_reason), Transportkosten,
    # Batchqualität (v_batch_quality).
    queries = {

        # Chart 1: Monatlicher Umsatz nach Kundensegment
        "umsatz_segment": """
            SELECT
                dd.year                     AS jahr,
                dd.month                    AS monat,
                dc.customer_type            AS segment,
                SUM(f.total_value)          AS umsatz
            FROM dwh.fact_fulfillment f
            JOIN dwh.dim_customer        dc  ON f.customer_sk   = dc.customer_sk
            JOIN dwh.dim_date            dd  ON f.order_date_sk = dd.date_sk
            GROUP BY dd.year, dd.month, dc.customer_type
            ORDER BY dd.year, dd.month, dc.customer_type
        """,

        # Chart 2: Verspätungsgründe (delay_reason je Transport-Leg)
        "verspaetungsgruende": """
            SELECT delay_reason AS grund, COUNT(*) AS anzahl
            FROM tms.transport_completions
            WHERE delay_reason IS NOT NULL
            GROUP BY delay_reason
            ORDER BY anzahl DESC
        """,

        # Chart 3: Bestellwert-Verteilung nach Kundentyp (Boxplot)
        "bestellwert_segment": """
            SELECT dc.customer_type AS segment, f.total_value AS bestellwert
            FROM dwh.fact_fulfillment f
            JOIN dwh.dim_customer dc ON f.customer_sk = dc.customer_sk
            WHERE dc.customer_type IS NOT NULL
        """,

        # Chart 4: Ø Transportkosten je Route
        "transportkosten_route": """
            SELECT
                source_node || ' -> ' || target_node AS route,
                ROUND(AVG(transport_cost), 2)        AS avg_kosten,
                ROUND(AVG(distance_km), 1)           AS avg_distanz
            FROM tms.shipments
            GROUP BY source_node, target_node
            ORDER BY avg_kosten DESC
        """,

        # Chart 5: Batchqualität über Zeit (Kühlkette -> Qualität)
        "batchqualitaet_zeit": """
            SELECT kalenderwoche, qualitaetsrate_pct, avg_schwund_pct, batches
            FROM dwh.v_batch_quality
            ORDER BY kalenderwoche
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

    # -- Chart 1: Umsatz-Zeitreihe nach Kundensegment --
    df1 = datasets["umsatz_segment"].copy()
    if not df1.empty:
        df1["periode"] = df1["jahr"].astype(str) + "-" + df1["monat"].astype(str).str.zfill(2)
        pivot = df1.pivot_table(index="periode", columns="segment", values="umsatz", aggfunc="sum").fillna(0)
        pivot = pivot.sort_index()
        for col, color in zip(pivot.columns, COLOR_PALETTE):
            ax1.plot(pivot.index, pivot[col], marker="o", linewidth=2,
                     markersize=4, label=col, color=color)
        ax1.set_title("① Monatlicher Umsatz nach Kundensegment (EUR)", fontweight="bold", color="#1E3A5F")
        ax1.set_xlabel("Monat")
        ax1.set_ylabel("Umsatz (EUR)")
        ax1.tick_params(axis="x", rotation=45)
        ax1.legend(loc="upper left", fontsize=7, ncol=3)
        ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    else:
        ax1.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_title("① Monatlicher Umsatz nach Kundensegment", fontweight="bold")

    # -- Chart 2: Verspätungsgründe (delay_reason) --
    df2 = datasets["verspaetungsgruende"].copy()
    if not df2.empty:
        df2 = df2.sort_values("anzahl", ascending=True)
        bars2 = ax2.barh(df2["grund"], df2["anzahl"], color=COLOR_PALETTE[:len(df2)], height=0.6)
        ax2.set_title("② Verspätungsgründe\n(Transport-Legs)", fontweight="bold", color="#1E3A5F")
        ax2.set_xlabel("Anzahl Legs")
        for bar, val in zip(bars2, df2["anzahl"]):
            ax2.text(val, bar.get_y() + bar.get_height() / 2, f" {int(val)}", va="center", fontsize=7)
    else:
        ax2.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax2.transAxes)
        ax2.set_title("② Verspätungsgründe", fontweight="bold")

    # -- Chart 3: Bestellwert nach Kundentyp (Boxplot) --
    df3 = datasets["bestellwert_segment"].copy()
    if not df3.empty:
        order3 = [s for s in ["DISCOUNTER", "VOLLSORTIMENTER", "PREMIUM"] if s in df3["segment"].unique()]
        data3 = [df3[df3["segment"] == s]["bestellwert"].astype(float).values for s in order3]
        bp3 = ax3.boxplot(data3, labels=order3, patch_artist=True,
                          medianprops={"color": "black", "linewidth": 2})
        for patch, color in zip(bp3["boxes"], COLOR_PALETTE):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        ax3.set_title("③ Bestellwert nach Kundentyp\n(EUR)", fontweight="bold", color="#1E3A5F")
        ax3.set_ylabel("Bestellwert (EUR)")
        ax3.tick_params(axis="x", rotation=15, labelsize=7)
        ax3.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}k"))
    else:
        ax3.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax3.transAxes)
        ax3.set_title("③ Bestellwert nach Kundentyp", fontweight="bold")

    # -- Chart 4: Ø Transportkosten je Route --
    df4 = datasets["transportkosten_route"].copy()
    if not df4.empty:
        df4 = df4.sort_values("avg_kosten", ascending=True)
        bars4 = ax4.barh(df4["route"], df4["avg_kosten"].astype(float),
                         color=COLOR_PALETTE[3], height=0.6)
        ax4.set_title("④ Ø Transportkosten je Route\n(EUR)", fontweight="bold", color="#1E3A5F")
        ax4.set_xlabel("Ø Kosten (EUR)")
        ax4.tick_params(axis="y", labelsize=6)
        for bar, val in zip(bars4, df4["avg_kosten"].astype(float)):
            ax4.text(val, bar.get_y() + bar.get_height() / 2, f" {val:,.0f}", va="center", fontsize=6)
    else:
        ax4.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax4.transAxes)
        ax4.set_title("④ Ø Transportkosten je Route", fontweight="bold")

    # -- Chart 5: Batchqualität über Zeit --
    df5 = datasets["batchqualitaet_zeit"].copy()
    if not df5.empty:
        df5 = df5.sort_values("kalenderwoche")
        x5 = pd.to_datetime(df5["kalenderwoche"])
        ax5.plot(x5, df5["qualitaetsrate_pct"].astype(float), marker="o", linewidth=2,
                 markersize=3, color=COLOR_SUCCESS, label="Qualitätsrate %")
        ax5.plot(x5, df5["avg_schwund_pct"].astype(float), marker="s", linewidth=1.5,
                 markersize=3, color=COLOR_FAILED, label="Ø Schwund %")
        ax5.set_title("⑤ Batchqualität über Zeit\n(Kühlkette → Qualität)", fontweight="bold", color="#1E3A5F")
        ax5.set_ylabel("Prozent")
        ax5.tick_params(axis="x", rotation=45, labelsize=7)
        ax5.legend(fontsize=7)
    else:
        ax5.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax5.transAxes)
        ax5.set_title("⑤ Batchqualität über Zeit", fontweight="bold")

    # Fußzeile
    fig.text(0.5, 0.01,
             "Datenquelle: DWH + operative Schemas (tms, v_batch_quality) | Gruppe 7 – DMA SoSe 26 | TH Lübeck",
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
            "① Monatlicher Umsatz nach Kundensegment (EUR)",
            "② Verspätungsgründe (Transport-Legs)",
            "③ Bestellwert nach Kundentyp (EUR)",
            "④ Ø Transportkosten je Route (EUR)",
            "⑤ Batchqualität über Zeit (%)",
            ""
        ),
        specs=[
            [{"colspan": 2}, None, {}],
            [{}, {}, {}],
        ],
        vertical_spacing=0.18,
        horizontal_spacing=0.1,
    )

    # -- Chart 1: Umsatz nach Kundensegment --
    df1 = datasets["umsatz_segment"].copy()
    if not df1.empty:
        df1["periode"] = df1["jahr"].astype(str) + "-" + df1["monat"].astype(str).str.zfill(2)
        pivot = df1.pivot_table(index="periode", columns="segment", values="umsatz", aggfunc="sum").fillna(0)
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

    # -- Chart 2: Verspätungsgründe --
    df2 = datasets["verspaetungsgruende"].copy()
    if not df2.empty:
        df2 = df2.sort_values("anzahl", ascending=True)
        fig.add_trace(
            go.Bar(
                y=df2["grund"], x=df2["anzahl"], orientation="h",
                marker_color=COLOR_PALETTE[1],
                hovertemplate="<b>%{y}</b><br>%{x} Legs<extra></extra>",
                name="Gründe", showlegend=False,
            ),
            row=1, col=3
        )

    # -- Chart 3: Bestellwert nach Kundentyp (Box) --
    df3 = datasets["bestellwert_segment"].copy()
    if not df3.empty:
        segs3 = [s for s in ["DISCOUNTER", "VOLLSORTIMENTER", "PREMIUM"] if s in df3["segment"].unique()]
        for i, seg in enumerate(segs3):
            fig.add_trace(
                go.Box(
                    y=df3[df3["segment"] == seg]["bestellwert"].astype(float), name=seg,
                    marker_color=COLOR_PALETTE[i % len(COLOR_PALETTE)], boxmean=True,
                    hovertemplate=f"<b>{seg}</b><br>EUR %{{y:,.0f}}<extra></extra>", showlegend=False,
                ),
                row=2, col=1
            )

    # -- Chart 4: Ø Transportkosten je Route --
    df4 = datasets["transportkosten_route"].copy()
    if not df4.empty:
        df4 = df4.sort_values("avg_kosten", ascending=True)
        fig.add_trace(
            go.Bar(
                y=df4["route"], x=df4["avg_kosten"].astype(float), orientation="h",
                marker_color=COLOR_PALETTE[3],
                hovertemplate="<b>%{y}</b><br>Ø EUR %{x:,.0f}<extra></extra>",
                name="Kosten", showlegend=False,
            ),
            row=2, col=2
        )

    # -- Chart 5: Batchqualität über Zeit --
    df5 = datasets["batchqualitaet_zeit"].copy()
    if not df5.empty:
        df5 = df5.sort_values("kalenderwoche")
        x5 = pd.to_datetime(df5["kalenderwoche"])
        fig.add_trace(
            go.Scatter(x=x5, y=df5["qualitaetsrate_pct"].astype(float), mode="lines+markers",
                       name="Qualitätsrate %", line={"color": COLOR_SUCCESS, "width": 2},
                       hovertemplate="%{x}<br>Qualität %{y:.1f}%<extra></extra>", showlegend=False),
            row=2, col=3
        )
        fig.add_trace(
            go.Scatter(x=x5, y=df5["avg_schwund_pct"].astype(float), mode="lines+markers",
                       name="Ø Schwund %", line={"color": COLOR_FAILED, "width": 1.5},
                       hovertemplate="%{x}<br>Schwund %{y:.1f}%<extra></extra>", showlegend=False),
            row=2, col=3
        )

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
    )
    fig.add_annotation(
        text="Datenquelle: DWH + operative Schemas (tms, v_batch_quality) | Gruppe 7 – DMA SoSe 26 | TH Lübeck",
        x=0.5, y=-0.06, xref="paper", yref="paper",
        showarrow=False, font={"size": 10, "color": "#64748B"}
    )

    fig.write_html(
        HTML_PATH,
        include_plotlyjs="cdn",
        full_html=True,
        div_id="banana-supply-chain-dashboard",
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
