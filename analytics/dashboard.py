"""
=============================================================================
dashboard.py – BI-Dashboard Banana Supply Chain
=============================================================================
Erstellt 5 wirtschaftlich getriebene Charts als:
  - dashboard.pdf / dashboard.png  (statisch, matplotlib + seaborn)
  - dashboard.html                 (interaktiv, plotly – dieselben 5 Visuals)

Charts [ANPASSUNG 2026-07-05 – Auswahl neu geschnitten, Profitabilität integriert]:
  1. Umsatzentwicklung nach Kundensegment       (Line Chart, customer_type)
  2. Pareto Top-Kunden nach Umsatz              (Bar + kumulative %-Linie, EINE %-Achse)
  3. Verzögerungsverteilung mit SLA-Grenze      (Histogramm delay_minutes, SLA 60 min)
  4. Verspätungsgründe je Transportabschnitt    (Horizontal Bar, delay_reason > 30 Min.)
  5. Profitabilitäts-Wasserfall                 (Umsatz → COGS → Transport → Lager → log. DB)

Begriffliche Einordnung (bewusst): COGS sind SIMULIERT, Transportkosten
KAPAZITÄTSALLOKIERT; der Wasserfall endet im vereinfachten LOGISTISCHEN
Deckungsbeitrag – kein Unternehmensgewinn (ohne Personal/Verwaltung/Vertrieb).

Voraussetzung:
  - PostgreSQL läuft auf localhost:5432, DB: logistics
  - dwh.fact_fulfillment inkl. Profitabilitäts-Spalten via etl_dwh.py befüllt
  - pip install psycopg2-binary pandas matplotlib seaborn plotly

Ausführung:
  python3 analytics/dashboard.py
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

# Serienfarben (Segmente, feste Reihenfolge) + Funktionsfarben
COLOR_PALETTE  = ["#2563EB", "#16A34A", "#DC2626", "#D97706", "#7C3AED"]
C_SERIES       = "#2563EB"   # Einzelserien-Blau
C_TOTAL        = "#3B6BA5"   # Wasserfall: Summe (dataviz-validiert)
C_COST         = "#C2410C"   # Wasserfall: Kostenabzug
C_RESULT       = "#15803D"   # Wasserfall: Ergebnis
C_SLA          = "#DC2626"   # SLA-Grenzlinie
C_INK, C_MUTED = "#1E293B", "#64748B"

SLA_MINUTES    = 60          # Fulfillment-SLA (on_time_flag-Schwelle)

FOOTER = ("COGS simuliert · Transportkosten allokiert · logistischer Deckungsbeitrag, "
          "kein Unternehmensgewinn  |  Datenquelle: dwh.fact_fulfillment + tms.transport_completions  |  "
          "Gruppe 7 – DMA SoSe 26 | TH Lübeck")


def fmt_eur(v):
    # Deutsche Tausendertrennung für Direktbeschriftungen (z. B. 325.009 €)
    return f"{v:,.0f} €".replace(",", ".")


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

        # Chart 2: Pareto Top-Kunden nach Umsatz [ANPASSUNG 2026-07-05]
        "pareto_kunden": """
            SELECT
                dc.customer_name            AS kunde,
                dc.customer_type            AS segment,
                SUM(f.total_value)          AS umsatz
            FROM dwh.fact_fulfillment f
            JOIN dwh.dim_customer dc ON f.customer_sk = dc.customer_sk
            GROUP BY dc.customer_name, dc.customer_type
            ORDER BY umsatz DESC
        """,

        # Chart 3: Verzögerungsverteilung (Fulfillment-Grain) [ANPASSUNG 2026-07-05]
        "delay_verteilung": """
            SELECT delay_minutes
            FROM dwh.fact_fulfillment
            WHERE delay_minutes IS NOT NULL
        """,

        # Chart 4: Verspätungsgründe je Transportabschnitt (Generator setzt
        # delay_reason nur bei Leg-Verspätung > 30 Min.)
        "verspaetungsgruende": """
            SELECT delay_reason AS grund, COUNT(*) AS anzahl
            FROM tms.transport_completions
            WHERE delay_reason IS NOT NULL
            GROUP BY delay_reason
            ORDER BY anzahl DESC
        """,

        # Chart 5: Profitabilitäts-Wasserfall [ANPASSUNG 2026-07-05]
        "profitabilitaet": """
            SELECT
                ROUND(SUM(total_value), 2)         AS umsatz,
                ROUND(SUM(cogs_total), 2)          AS cogs,
                ROUND(SUM(transport_cost), 2)      AS transport,
                ROUND(SUM(storage_cost), 2)        AS lager,
                ROUND(SUM(contribution_margin), 2) AS deckungsbeitrag
            FROM dwh.fact_fulfillment
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

    sns.set_theme(style="whitegrid", font_scale=1.0)
    fig = plt.figure(figsize=(19, 16), facecolor="#F8FAFC")
    fig.suptitle(
        "Banana Supply Chain – BI Dashboard",
        fontsize=19, fontweight="bold", color="#1E3A5F", y=0.985
    )

    # 3 Zeilen: oben Zeitreihe + Pareto, Mitte Histogramm + Gründe,
    # unten Wasserfall über die volle Breite (braucht die 5 Stufen nebeneinander)
    gs = gridspec.GridSpec(
        3, 2,
        figure=fig,
        height_ratios=[1.0, 1.0, 1.15],
        hspace=0.42, wspace=0.22,
        top=0.94, bottom=0.055,
        left=0.06, right=0.97
    )

    ax1 = fig.add_subplot(gs[0, 0])   # 1. Umsatzentwicklung
    ax2 = fig.add_subplot(gs[0, 1])   # 2. Pareto Top-Kunden
    ax3 = fig.add_subplot(gs[1, 0])   # 3. Verzögerungsverteilung + SLA
    ax4 = fig.add_subplot(gs[1, 1])   # 4. Verspätungsgründe
    ax5 = fig.add_subplot(gs[2, :])   # 5. Wasserfall (volle Breite)

    # -- Chart 1: Umsatzentwicklung nach Kundensegment (beibehalten) ----------
    df1 = datasets["umsatz_segment"].copy()
    if not df1.empty:
        df1["periode"] = df1["jahr"].astype(str) + "-" + df1["monat"].astype(str).str.zfill(2)
        pivot = df1.pivot_table(index="periode", columns="segment", values="umsatz", aggfunc="sum").fillna(0)
        pivot = pivot.sort_index()
        for col, color in zip(pivot.columns, COLOR_PALETTE):
            ax1.plot(pivot.index, pivot[col], marker="o", linewidth=2,
                     markersize=4, label=col, color=color)
        ax1.set_title("1. Umsatzentwicklung nach Kundensegment (EUR/Monat)",
                      fontweight="bold", color="#1E3A5F", fontsize=12)
        ax1.set_xlabel("Monat")
        ax1.set_ylabel("Umsatz (EUR)")
        ax1.tick_params(axis="x", rotation=45, labelsize=8)
        ax1.legend(loc="upper left", fontsize=9, ncol=3)
        ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    else:
        ax1.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_title("1. Umsatzentwicklung nach Kundensegment", fontweight="bold")

    # -- Chart 2: Pareto Top-Kunden nach Umsatz --------------------------------
    # dataviz-konform mit EINER Achse: Balken = Umsatzanteil %, Linie = kumulierter
    # Anteil % (gleiche Skala 0-100). Absolute EUR als Direktbeschriftung.
    df2 = datasets["pareto_kunden"].copy()
    if not df2.empty:
        total = df2["umsatz"].sum()
        df2["anteil_pct"] = 100.0 * df2["umsatz"] / total
        df2["kum_pct"]    = df2["anteil_pct"].cumsum()
        x2 = range(len(df2))

        bars2 = ax2.bar(x2, df2["anteil_pct"], color=C_SERIES, width=0.62,
                        edgecolor="#F8FAFC", linewidth=1.5, label="Umsatzanteil je Kunde")
        ax2.plot(x2, df2["kum_pct"], color=C_INK, marker="o", markersize=5,
                 linewidth=2, label="kumuliert")
        ax2.axhline(80, color=C_MUTED, linestyle="--", linewidth=1)
        ax2.text(len(df2) - 0.4, 81.5, "80 %", fontsize=8, color=C_MUTED, ha="right")

        # Direktbeschriftung: EUR am Balken, kumulierte % an ausgewählten Punkten
        for i, (rect, (_, row)) in enumerate(zip(bars2, df2.iterrows())):
            ax2.annotate(f"{row['umsatz']/1000:,.0f}k".replace(",", "."),
                         xy=(rect.get_x() + rect.get_width() / 2, rect.get_height()),
                         xytext=(0, 3), textcoords="offset points",
                         ha="center", fontsize=8, color=C_INK)
        # Kumulierte %: nur selektiv beschriften (80 %-Überschreitung + Endpunkt);
        # der erste Punkt entfällt, weil er auf dem EUR-Balkenlabel läge (Kollision).
        over80 = (df2["kum_pct"] >= 80).idxmax()
        for i in {int(over80), len(df2) - 1}:
            ax2.annotate(f"{df2['kum_pct'].iloc[i]:.0f} %",
                         xy=(i, df2["kum_pct"].iloc[i]), xytext=(0, 8),
                         textcoords="offset points", ha="center",
                         fontsize=8, fontweight="bold", color=C_INK)

        ax2.set_xticks(list(x2))
        ax2.set_xticklabels(df2["kunde"], rotation=35, ha="right", fontsize=8)
        ax2.set_ylim(0, 112)
        ax2.set_ylabel("Anteil am Gesamtumsatz (%)")
        ax2.set_title("2. Pareto: Top-Kunden nach Umsatz\n(Balken = Anteil, Linie = kumuliert; Beschriftung in EUR)",
                      fontweight="bold", color="#1E3A5F", fontsize=12)
        ax2.legend(loc="center right", fontsize=9)
    else:
        ax2.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax2.transAxes)
        ax2.set_title("2. Pareto: Top-Kunden nach Umsatz", fontweight="bold")

    # -- Chart 3: Verzögerungsverteilung mit SLA-Grenze ------------------------
    df3 = datasets["delay_verteilung"].copy()
    if not df3.empty:
        delays = df3["delay_minutes"].astype(float)
        bins = range(0, int(delays.max()) + 10, 5)
        ax3.hist(delays, bins=bins, color=C_SERIES, edgecolor="#F8FAFC", linewidth=1.2)
        ax3.axvline(SLA_MINUTES, color=C_SLA, linestyle="--", linewidth=2)
        n_over = int((delays > SLA_MINUTES).sum())
        ax3.annotate(f"SLA {SLA_MINUTES} min\n({n_over} von {len(delays)} = "
                     f"{100 * n_over / len(delays):.1f} % darüber)",
                     xy=(SLA_MINUTES, ax3.get_ylim()[1] * 0.82),
                     xytext=(-8, 0), textcoords="offset points",
                     ha="right", fontsize=9, fontweight="bold", color=C_SLA)
        ax3.set_title(f"3. Verzögerungsverteilung der Endlieferungen\n(Fulfillment-SLA: {SLA_MINUTES} Minuten)",
                      fontweight="bold", color="#1E3A5F", fontsize=12)
        ax3.set_xlabel("Verzögerung (Minuten)")
        ax3.set_ylabel("Anzahl Lieferungen")
    else:
        ax3.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax3.transAxes)
        ax3.set_title("3. Verzögerungsverteilung", fontweight="bold")

    # -- Chart 4: Verspätungsgründe je Transportabschnitt (beibehalten) --------
    df4 = datasets["verspaetungsgruende"].copy()
    if not df4.empty:
        df4 = df4.sort_values("anzahl", ascending=True)
        bars4 = ax4.barh(df4["grund"], df4["anzahl"], color="#D97706", height=0.55,
                         edgecolor="#F8FAFC", linewidth=1.5)
        ax4.set_title("4. Verspätungsgründe je Transportabschnitt (>30 Min.)\n"
                      "(tms.transport_completions, nur Legs mit gesetztem Grund)",
                      fontweight="bold", color="#1E3A5F", fontsize=12)
        ax4.set_xlabel("Anzahl Transportabschnitte")
        ax4.tick_params(axis="y", labelsize=9)
        for bar, val in zip(bars4, df4["anzahl"]):
            ax4.text(val, bar.get_y() + bar.get_height() / 2, f" {int(val)}",
                     va="center", fontsize=9, fontweight="bold", color=C_INK)
    else:
        ax4.text(0.5, 0.5, "Keine Daten", ha="center", va="center", transform=ax4.transAxes)
        ax4.set_title("4. Verspätungsgründe je Transportabschnitt (>30 Min.)", fontweight="bold")

    # -- Chart 5: Profitabilitäts-Wasserfall (volle Breite) --------------------
    df5 = datasets["profitabilitaet"]
    if not df5.empty and df5.iloc[0]["umsatz"]:
        rev   = float(df5.iloc[0]["umsatz"])
        cogs  = float(df5.iloc[0]["cogs"])
        trans = float(df5.iloc[0]["transport"])
        stor  = float(df5.iloc[0]["lager"])
        cm    = float(df5.iloc[0]["deckungsbeitrag"])

        labels  = ["Umsatz", "− COGS\n(simuliert)", "− Transport\n(allokiert)",
                   "− Lager", "= Logistischer\nDeckungsbeitrag"]
        bottoms = [0, rev - cogs, rev - cogs - trans, rev - cogs - trans - stor, 0]
        heights = [rev, cogs, trans, stor, cm]
        colors  = [C_TOTAL, C_COST, C_COST, C_COST, C_RESULT]

        bars5 = ax5.bar(labels, heights, bottom=bottoms, color=colors, width=0.6,
                        edgecolor="#F8FAFC", linewidth=2)
        # Verbindungslinien zwischen den Stufen
        running = [rev, rev - cogs, rev - cogs - trans, rev - cogs - trans - stor]
        for i, lvl in enumerate(running):
            ax5.plot([i + 0.3, i + 1 - 0.3], [lvl, lvl],
                     color=C_MUTED, linewidth=1, linestyle="--", zorder=1)
        # Direktbeschriftung: Betrag + Anteil am Umsatz
        for i, (h, b) in enumerate(zip(heights, bottoms)):
            ax5.annotate(f"{fmt_eur(h)}  ({100 * h / rev:.1f} %)",
                         xy=(i, b + h), xytext=(0, 6), textcoords="offset points",
                         ha="center", fontsize=10, fontweight="bold", color=C_INK)

        ax5.set_ylim(0, rev * 1.14)
        ax5.set_ylabel("EUR")
        ax5.set_title("5. Profitabilitäts-Wasserfall: Umsatz → COGS → Transportkosten → Lagerkosten → logistischer Deckungsbeitrag",
                      fontweight="bold", color="#1E3A5F", fontsize=12)
        ax5.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
        ax5.tick_params(axis="x", labelsize=10)
    else:
        ax5.text(0.5, 0.5, "Keine Daten (Profitabilitäts-Spalten via etl_dwh.py befüllen)",
                 ha="center", va="center", transform=ax5.transAxes)
        ax5.set_title("5. Profitabilitäts-Wasserfall", fontweight="bold")

    # Fußzeile (Annahmenhinweis, prüfungsrelevant)
    fig.text(0.5, 0.012, FOOTER, ha="center", fontsize=9, color=C_MUTED)

    # Speichern
    fig.savefig(PNG_PATH, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(PDF_PATH, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[OK] Statisches Dashboard gespeichert:")
    print(f"     {PNG_PATH}")
    print(f"     {PDF_PATH}")


# ---------------------------------------------------------------------------
# Interaktives Dashboard (plotly → HTML, dieselben 5 Visuals)
# ---------------------------------------------------------------------------

def build_interactive_dashboard(datasets):
    print("[...] Erstelle interaktives Dashboard (HTML)...")

    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=(
            "1. Umsatzentwicklung nach Kundensegment (EUR/Monat)",
            "2. Pareto: Top-Kunden nach Umsatz (% + kumuliert)",
            "3. Verzögerungsverteilung (Fulfillment-SLA: 60 Minuten)",
            "4. Verspätungsgründe je Transportabschnitt (>30 Min.)",
            "5. Profitabilitäts-Wasserfall: Umsatz → COGS → Transport → Lager → log. Deckungsbeitrag",
        ),
        specs=[
            [{}, {}],
            [{}, {}],
            [{"colspan": 2}, None],
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.09,
    )

    # -- Chart 1: Umsatzentwicklung nach Kundensegment --
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

    # -- Chart 2: Pareto (eine %-Achse: Balken Anteil, Linie kumuliert) --
    df2 = datasets["pareto_kunden"].copy()
    if not df2.empty:
        total = df2["umsatz"].sum()
        df2["anteil_pct"] = 100.0 * df2["umsatz"] / total
        df2["kum_pct"]    = df2["anteil_pct"].cumsum()
        fig.add_trace(
            go.Bar(
                x=df2["kunde"], y=df2["anteil_pct"], name="Umsatzanteil je Kunde",
                marker_color=C_SERIES,
                customdata=df2["umsatz"],
                hovertemplate="<b>%{x}</b><br>Anteil %{y:.1f} %<br>EUR %{customdata:,.0f}<extra></extra>",
                showlegend=False,
            ),
            row=1, col=2
        )
        fig.add_trace(
            go.Scatter(
                x=df2["kunde"], y=df2["kum_pct"], mode="lines+markers",
                name="kumuliert", line={"color": C_INK, "width": 2},
                hovertemplate="<b>%{x}</b><br>kumuliert %{y:.1f} %<extra></extra>",
                showlegend=False,
            ),
            row=1, col=2
        )
        fig.add_hline(y=80, line_dash="dash", line_color=C_MUTED, row=1, col=2)

    # -- Chart 3: Verzögerungshistogramm + SLA-Linie --
    df3 = datasets["delay_verteilung"].copy()
    if not df3.empty:
        fig.add_trace(
            go.Histogram(
                x=df3["delay_minutes"].astype(float), xbins={"size": 5},
                marker_color=C_SERIES, name="Lieferungen",
                hovertemplate="%{x} min: %{y} Lieferungen<extra></extra>",
                showlegend=False,
            ),
            row=2, col=1
        )
        fig.add_vline(x=SLA_MINUTES, line_dash="dash", line_color=C_SLA,
                      annotation_text=f"SLA {SLA_MINUTES} min",
                      annotation_font_color=C_SLA, row=2, col=1)

    # -- Chart 4: Verspätungsgründe --
    df4 = datasets["verspaetungsgruende"].copy()
    if not df4.empty:
        df4 = df4.sort_values("anzahl", ascending=True)
        fig.add_trace(
            go.Bar(
                y=df4["grund"], x=df4["anzahl"], orientation="h",
                marker_color="#D97706",
                hovertemplate="<b>%{y}</b><br>%{x} Transportabschnitte<extra></extra>",
                name="Gründe", showlegend=False,
            ),
            row=2, col=2
        )

    # -- Chart 5: Wasserfall (natives plotly-Waterfall-Visual) --
    df5 = datasets["profitabilitaet"]
    if not df5.empty and df5.iloc[0]["umsatz"]:
        rev   = float(df5.iloc[0]["umsatz"])
        cogs  = float(df5.iloc[0]["cogs"])
        trans = float(df5.iloc[0]["transport"])
        stor  = float(df5.iloc[0]["lager"])
        cm    = float(df5.iloc[0]["deckungsbeitrag"])
        fig.add_trace(
            go.Waterfall(
                x=["Umsatz", "− COGS (simuliert)", "− Transport (allokiert)",
                   "− Lager", "= Logistischer Deckungsbeitrag"],
                measure=["absolute", "relative", "relative", "relative", "total"],
                y=[rev, -cogs, -trans, -stor, 0],
                text=[f"{v:,.0f} € ({100 * v / rev:.1f} %)" for v in [rev, cogs, trans, stor, cm]],
                textposition="outside",
                decreasing={"marker": {"color": C_COST}},
                increasing={"marker": {"color": C_TOTAL}},
                totals={"marker": {"color": C_RESULT}},
                connector={"line": {"color": C_MUTED, "dash": "dot", "width": 1}},
                showlegend=False,
            ),
            row=3, col=1
        )

    # Layout
    fig.update_layout(
        title={
            "text": "🍌 Banana Supply Chain – BI Dashboard",
            "x": 0.5, "xanchor": "center",
            "font": {"size": 22, "color": "#1E3A5F"}
        },
        height=1150,
        paper_bgcolor="#F8FAFC",
        plot_bgcolor="#FFFFFF",
        font={"family": "Inter, Arial, sans-serif", "size": 11},
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.06, "x": 0.5, "xanchor": "center"},
        margin={"t": 100, "b": 90},
    )
    fig.update_yaxes(title_text="Anteil am Gesamtumsatz (%)", row=1, col=2)
    fig.update_yaxes(title_text="Anzahl Lieferungen", row=2, col=1)
    fig.update_xaxes(title_text="Verzögerung (Minuten)", row=2, col=1)
    fig.update_yaxes(title_text="EUR", row=3, col=1)
    fig.add_annotation(
        text=FOOTER,
        x=0.5, y=-0.075, xref="paper", yref="paper",
        showarrow=False, font={"size": 10, "color": C_MUTED}
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
