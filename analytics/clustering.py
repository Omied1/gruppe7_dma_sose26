"""
=============================================================================
clustering.py – Kundensegmentierung via k-Means
=============================================================================
Aufgabe (Aufgabenstellung.pdf):
  "Führen Sie mit python eine Cluster (über Lieferanden oder Kunden) durch."

Ansatz:
  Kundensegmentierung auf Basis von 4 KPIs aus dwh.fact_fulfillment:
    1. Bestellhäufigkeit      (Anzahl Lieferungen pro Kunde)
    2. Ø Bestellwert (EUR)    (avg total_value)
    3. Ø Verzögerung (min)    (avg delay_minutes)
    4. Liefertreue-Quote      (on_time_flag-Anteil)

Methode:
  - StandardScaler (Features auf gleiche Skala bringen)
  - Elbow-Methode (WSS für k=1..n-1 → optimales k ablesen)
  - k-Means (sklearn)
  - Visualisierung: Elbow-Kurve + Scatter-Plot (2 wichtigste Features)

Datenbasis:
  dwh.fact_fulfillment + dwh.dim_customer (PostgreSQL, logistics-DB)

Ausgabe:
  analytics/clustering.png
  analytics/clustering.pdf

Ausführung:
  python3 analytics/clustering.py
=============================================================================
"""

import sys
import os
import warnings
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Abhängigkeiten
# ---------------------------------------------------------------------------
try:
    import psycopg2
    import psycopg2.extras
    import pandas as pd
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
except ImportError as e:
    print(f"[FEHLER] Fehlendes Paket: {e}")
    print("  pip3 install psycopg2-binary pandas numpy matplotlib scikit-learn")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
PG_DSN     = "host=localhost port=5432 dbname=logistics user=user password=password"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
PNG_PATH   = os.path.join(OUTPUT_DIR, "clustering.png")
PDF_PATH   = os.path.join(OUTPUT_DIR, "clustering.pdf")

# Cluster-Farben und -Labels (werden nach Analyse vergeben)
# [ANPASSUNG 2026-07-02] Palette auf 6 Farben erweitert – mit faithful Daten kann die
# Elbow-/Silhouette-Analyse bis k=5 (theoretisch 6) wählen (vorher IndexError bei k>4).
CLUSTER_COLORS = ["#2563EB", "#DC2626", "#16A34A", "#D97706", "#7C3AED", "#0891B2"]


# ---------------------------------------------------------------------------
# Schritt 1: Kundendaten aus DWH laden
# ---------------------------------------------------------------------------
def load_customer_features() -> pd.DataFrame:
    """Aggregiert 4 KPIs je Kunde aus fact_fulfillment – Basis für k-Means."""
    print("[1/5] Lade Kundendaten aus DWH...")

    conn = psycopg2.connect(PG_DSN)
    sql = """
        SELECT
            dc.customer_name                                            AS kunde,
            dc.country                                                  AS land,
            dc.customer_type                                            AS segment,
            COUNT(*)                                                    AS bestellungen,
            ROUND(AVG(f.total_value)::numeric,    2)                   AS avg_bestellwert,
            ROUND(AVG(f.delay_minutes)::numeric,  1)                   AS avg_verzoegerung,
            ROUND(AVG(CASE WHEN f.on_time_flag THEN 1.0 ELSE 0.0 END)
                  ::numeric, 3)                                         AS liefertreue,
            SUM(f.quantity)                                             AS gesamtmenge
        FROM dwh.fact_fulfillment f
        JOIN dwh.dim_customer dc ON f.customer_sk = dc.customer_sk
        GROUP BY dc.customer_name, dc.country, dc.customer_type
        ORDER BY bestellungen DESC, avg_verzoegerung ASC
    """
    df = pd.read_sql(sql, conn)
    conn.close()

    # Numerische Spalten sicherstellen
    num_cols = ["bestellungen", "avg_bestellwert", "avg_verzoegerung",
                "liefertreue", "gesamtmenge"]
    df[num_cols] = df[num_cols].apply(pd.to_numeric, errors="coerce")

    print(f"  {len(df)} Kunden geladen:")
    for _, row in df.iterrows():
        print(f"  • {row['kunde']:12s} | {row['bestellungen']} Bestellungen | "
              f"Ø {row['avg_verzoegerung']} min | Liefertreue {row['liefertreue']:.0%}")
    return df


# ---------------------------------------------------------------------------
# Schritt 2: Features skalieren
# ---------------------------------------------------------------------------
def scale_features(df: pd.DataFrame):
    """Standardisiert die 4 KPI-Features auf Mittelwert=0, Std=1.
    Notwendig damit kein Feature die Distanzberechnung dominiert
    (z.B. avg_verzoegerung in Minuten vs. liefertreue in 0..1)."""

    features = ["bestellungen", "avg_bestellwert", "avg_verzoegerung", "liefertreue"]
    X = df[features].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print(f"[2/5] Features standardisiert: {features}")
    return X_scaled, features, scaler


# ---------------------------------------------------------------------------
# Schritt 3: Elbow-Methode – optimales k bestimmen
# ---------------------------------------------------------------------------
def elbow_analysis(X_scaled: np.ndarray) -> int:
    """Berechnet WSS (Within-Cluster Sum of Squares) für k=1..n-1.
    Das 'Elbow' (Knick in der Kurve) zeigt das optimale k."""

    n = len(X_scaled)
    max_k = min(n - 1, 5)  # k muss < Anzahl Datenpunkte sein
    ks    = range(1, max_k + 1)
    wss   = []
    silhouettes = []

    for k in ks:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X_scaled)
        wss.append(km.inertia_)
        if k >= 2:
            sil = silhouette_score(X_scaled, km.labels_)
            silhouettes.append((k, round(sil, 3)))

    # Bestes k via Silhouette-Score wählen (objektiver als Elbow-Sicht)
    best_k = max(silhouettes, key=lambda x: x[1])[0] if silhouettes else 2

    print(f"[3/5] Elbow-Analyse (k=1..{max_k}):")
    for i, (k, w) in enumerate(zip(ks, wss)):
        sil_str = f"  Silhouette={silhouettes[i-1][1]}" if i >= 1 else ""
        print(f"  k={k}: WSS={w:.2f}{sil_str}")
    print(f"  → Optimales k = {best_k} (höchster Silhouette-Score)")

    return best_k, list(ks), wss, silhouettes


# ---------------------------------------------------------------------------
# Schritt 4: k-Means fitten
# ---------------------------------------------------------------------------
def fit_kmeans(X_scaled: np.ndarray, k: int, df: pd.DataFrame) -> pd.DataFrame:
    """Führt k-Means mit dem gewählten k durch und fügt Cluster-Labels zum
    DataFrame hinzu. Labels werden nach avg_verzoegerung aufsteigend vergeben,
    damit Cluster 0 = 'bester' Cluster."""

    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    km.fit(X_scaled)
    df = df.copy()
    df["cluster_raw"] = km.labels_

    # Cluster nach avg_verzoegerung sortieren (Cluster 0 = pünktlichster)
    cluster_means = df.groupby("cluster_raw")["avg_verzoegerung"].mean()
    rank_map = {old: new for new, old in enumerate(cluster_means.sort_values().index)}
    df["cluster"] = df["cluster_raw"].map(rank_map)

    print(f"[4/5] k-Means mit k={k} durchgeführt:")
    for c in sorted(df["cluster"].unique()):
        members = df[df["cluster"] == c]["kunde"].tolist()
        avg_d   = df[df["cluster"] == c]["avg_verzoegerung"].mean()
        avg_lt  = df[df["cluster"] == c]["liefertreue"].mean()
        print(f"  Cluster {c}: {members}  |  Ø Delay={avg_d:.0f} min  |  Liefertreue={avg_lt:.0%}")

    return df, km


# ---------------------------------------------------------------------------
# Schritt 5: Visualisierung (3 Subplots)
# ---------------------------------------------------------------------------
def plot_clusters(df: pd.DataFrame, X_scaled: np.ndarray, k: int,
                  ks, wss, silhouettes):
    """Erstellt ein 3-teiliges Dashboard:
      Links:  Elbow-Kurve mit Silhouette-Scores
      Mitte:  Scatter-Plot (Bestellwert vs. Verzögerung)
      Rechts: Cluster-Steckbrief (Ø KPIs je Cluster als Tabelle)"""

    print("[5/5] Erstelle Visualisierung...")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), facecolor="#F8FAFC")
    fig.suptitle("Kundensegmentierung – Banana Supply Chain",
                 fontsize=16, fontweight="bold", color="#1E3A5F", y=1.02)

    colors = [CLUSTER_COLORS[c] for c in df["cluster"]]

    # ── Subplot 1: Elbow-Kurve ──────────────────────────────────────────
    ax1 = axes[0]
    ax1.plot(list(ks), wss, "o-", color="#2563EB", linewidth=2, markersize=8)
    ax1.axvline(x=k, color="#DC2626", linestyle="--", linewidth=1.5,
                label=f"Gewähltes k={k}")
    ax1.set_title("Elbow-Methode\n(WSS je k)", fontweight="bold", color="#1E3A5F")
    ax1.set_xlabel("Anzahl Cluster k")
    ax1.set_ylabel("WSS (Within-Cluster Sum of Squares)")
    ax1.legend(fontsize=9)

    # Silhouette-Scores als Annotation
    for sk, ss in silhouettes:
        ax1.annotate(f"Sil={ss:.2f}", xy=(sk, wss[sk-1]),
                     xytext=(5, 8), textcoords="offset points", fontsize=8, color="#64748B")
    ax1.set_facecolor("#FFFFFF")

    # ── Subplot 2: Scatter (Bestellwert vs. Verzögerung) ───────────────
    ax2 = axes[1]
    for _, row in df.iterrows():
        c = int(row["cluster"])
        ax2.scatter(row["avg_bestellwert"], row["avg_verzoegerung"],
                    color=CLUSTER_COLORS[c], s=180, zorder=5,
                    edgecolors="white", linewidth=1.5)
        ax2.annotate(row["kunde"],
                     xy=(row["avg_bestellwert"], row["avg_verzoegerung"]),
                     xytext=(6, 4), textcoords="offset points",
                     fontsize=9, color="#1E3A5F")

    ax2.set_title("Cluster-Verteilung\n(Ø Bestellwert vs. Ø Verzögerung)",
                  fontweight="bold", color="#1E3A5F")
    ax2.set_xlabel("Ø Bestellwert (EUR)")
    ax2.set_ylabel("Ø Verzögerung (Minuten)")

    # SLA-Linie bei 60 min
    ax2.axhline(y=60, color="#D97706", linestyle=":", linewidth=1.5,
                label="SLA-Grenze (60 min)")

    # Legende für Cluster
    legend_patches = [
        mpatches.Patch(color=CLUSTER_COLORS[c],
                       label=f"Cluster {c}: {get_cluster_label(df, c)}")
        for c in sorted(df["cluster"].unique())
    ]
    legend_patches.append(
        mpatches.Patch(color="#D97706", label="SLA-Grenze (60 min)", fill=False,
                       linestyle="--")
    )
    ax2.legend(handles=legend_patches, fontsize=8, loc="best")
    ax2.set_facecolor("#FFFFFF")

    # ── Subplot 3: Cluster-Steckbrief ──────────────────────────────────
    ax3 = axes[2]
    ax3.axis("off")

    table_data = []
    col_labels = ["Cluster", "Kunden", "Ø Wert (€)", "Ø Delay", "Liefertreue"]
    for c in sorted(df["cluster"].unique()):
        sub = df[df["cluster"] == c]
        kunden = ", ".join(sub["kunde"].tolist())
        table_data.append([
            f"Cluster {c}\n{get_cluster_label(df, c)}",
            kunden,
            f"{sub['avg_bestellwert'].mean():.0f} €",
            f"{sub['avg_verzoegerung'].mean():.0f} min",
            f"{sub['liefertreue'].mean():.0%}",
        ])

    tbl = ax3.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 2.5)

    # Cluster-Zeilen einfärben
    for row_idx, c in enumerate(sorted(df["cluster"].unique())):
        for col_idx in range(len(col_labels)):
            tbl[row_idx + 1, col_idx].set_facecolor(
                CLUSTER_COLORS[c] + "33"  # Transparenz
            )
    for col_idx in range(len(col_labels)):
        tbl[0, col_idx].set_facecolor("#1E3A5F")
        tbl[0, col_idx].set_text_props(color="white", fontweight="bold")

    ax3.set_title("Cluster-Steckbrief", fontweight="bold",
                  color="#1E3A5F", pad=20)

    fig.text(0.5, -0.03,
             "Methode: k-Means (sklearn) | Features: Bestellhäufigkeit, Ø Bestellwert, "
             "Ø Verzögerung, Liefertreue | Gruppe 7 – DMA SoSe 26",
             ha="center", fontsize=8, color="#64748B")

    plt.tight_layout()
    fig.savefig(PNG_PATH, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(PDF_PATH, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Gespeichert: {PNG_PATH}")
    print(f"  Gespeichert: {PDF_PATH}")


def get_cluster_label(df: pd.DataFrame, cluster_id: int) -> str:
    """Vergibt fachliche Cluster-Bezeichnung basierend auf Ø Verzögerung.
    Ermöglicht business-verständliche Segmentierung statt technischer IDs."""
    sub = df[df["cluster"] == cluster_id]
    avg_delay  = sub["avg_verzoegerung"].mean()
    avg_lt     = sub["liefertreue"].mean()

    if avg_delay <= 80 and avg_lt >= 0.4:
        return "Zuverlässige\nKunden"
    elif avg_delay <= 110:
        return "Durchschnitt"
    else:
        return "Risiko-\nKunden"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Kundensegmentierung – k-Means Clustering")
    print("=" * 60)

    df                       = load_customer_features()
    X_scaled, features, _    = scale_features(df)
    k, ks, wss, silhouettes  = elbow_analysis(X_scaled)
    df, km                   = fit_kmeans(X_scaled, k, df)
    plot_clusters(df, X_scaled, k, ks, wss, silhouettes)

    print()
    print("=" * 60)
    print("  Clustering abgeschlossen")
    print(f"  Optimales k = {k} Cluster")
    print(f"  Ausgabe: clustering.png / clustering.pdf")
    print("=" * 60)

    # Prüfnachweis
    print()
    print("Ergebnis-Übersicht:")
    print(df[["kunde", "cluster", "avg_verzoegerung", "liefertreue"]].to_string(index=False))

    # [ANPASSUNG 2026-07-02] Validierung: decken sich die datengetrieben gefundenen Cluster
    # mit den echten Kundensegmenten (customer_type)? Kreuztabelle Cluster x Segment.
    if "segment" in df.columns and df["segment"].notna().any():
        print()
        print("Validierung – Cluster x echtes Segment (customer_type):")
        print(pd.crosstab(df["cluster"], df["segment"]).to_string())


if __name__ == "__main__":
    main()
