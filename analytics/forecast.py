"""
=============================================================================
forecast.py – Absatzprognose Banana Supply Chain
=============================================================================
Aufgabe (Aufgabenstellung.pdf):
  "Führen Sie mit python [...] eine Absatzprognose durch."

Methode: ARIMA (AutoRegressive Integrated Moving Average)
  - Klassische Zeitreihen-Methode für Absatzprognosen
  - Geeignet für saisonale Muster (Bananenabsatz: Sommer-Peak)

Datenbasis:
  - Echte Monatsdaten aus dwh.v_monthly_revenue
    (aktueller Generatorstand: 13 Monate, 252 Fulfillments)
  - Synthetische Vorlauf-History: 24 Monate vor dem ersten echten Monat
    → generiert auf Basis der echten Statistiken (Mittelwert, Saisonalität)
    → TRANSPARENZ: synthetisch generierte Punkte sind im Chart markiert

Begründung synthetische History:
  Der umgebaute Datengenerator liefert bereits 13 echte Monate. Für ein
  stabileres ARIMA-Training wird die kurze echte Historie transparent um
  synthetische Vorlaufmonate ergänzt. Sobald mehr reale Historie vorliegt,
  kann SYNTHETIC_MONTHS reduziert oder auf 0 gesetzt werden.

Ausgabe:
  analytics/forecast.png
  analytics/forecast.pdf
  analytics/forecast_model_summary.txt

Ausführung:
  python3 analytics/forecast.py
=============================================================================
"""

import sys
import os
import tempfile
import warnings
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Abhängigkeiten
# ---------------------------------------------------------------------------
try:
    import psycopg2
    import pandas as pd
    import numpy as np
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.stattools import adfuller
except ImportError as e:
    print(f"[FEHLER] Fehlendes Paket: {e}")
    print("  pip3 install psycopg2-binary pandas numpy matplotlib statsmodels")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
PG_DSN       = "host=localhost port=5432 dbname=logistics user=user password=password"
OUTPUT_DIR   = os.path.dirname(os.path.abspath(__file__))
PNG_PATH     = os.path.join(OUTPUT_DIR, "forecast.png")
PDF_PATH     = os.path.join(OUTPUT_DIR, "forecast.pdf")
TXT_PATH     = os.path.join(OUTPUT_DIR, "forecast_model_summary.txt")

FORECAST_MONTHS = 3          # 3 Monate nach der letzten echten DWH-Periode
SYNTHETIC_MONTHS = 24        # Vorlaufmonate vor der ersten echten DWH-Periode
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# Bananenabsatz-Saisonalität: Index 1..12 → relativer Faktor
# Sommer-Peak (Jul/Aug), Weihnachts-Senke (Dez), Frühlings-Anstieg
SEASONAL_PATTERN = {
    1: 0.88, 2: 0.85, 3: 0.92, 4: 0.97,
    5: 1.05, 6: 1.10, 7: 1.18, 8: 1.15,
    9: 1.08, 10: 1.02, 11: 0.95, 12: 0.85
}


# ---------------------------------------------------------------------------
# Schritt 1: Echte Zeitreihendaten aus DWH laden
# ---------------------------------------------------------------------------
def load_real_timeseries() -> pd.DataFrame:
    """Lädt monatlich aggregierte Absatzdaten aus dwh.v_monthly_revenue."""
    print("[1/5] Lade echte Zeitreihendaten aus DWH...")

    conn = psycopg2.connect(PG_DSN)
    sql = """
        SELECT
            year                           AS jahr,
            month                          AS monat,
            SUM(total_quantity)            AS menge,
            ROUND(SUM(total_revenue_eur)::numeric, 2) AS umsatz,
            SUM(num_shipments)             AS auftraege
        FROM dwh.v_monthly_revenue
        GROUP BY year, month
        ORDER BY year, month
    """
    df = pd.read_sql(sql, conn)
    conn.close()

    df["datum"] = pd.to_datetime(
        df["jahr"].astype(str) + "-" + df["monat"].astype(str).str.zfill(2) + "-01"
    )
    df["menge"]   = pd.to_numeric(df["menge"], errors="coerce")
    df["umsatz"]  = pd.to_numeric(df["umsatz"], errors="coerce")
    df["auftraege"] = pd.to_numeric(df["auftraege"], errors="coerce").astype(int)
    df["synthetisch"] = False

    print(f"  {len(df)} echte Monate geladen:")
    for _, row in df.iterrows():
        print(f"  • {row['datum'].strftime('%Y-%m')}: {row['menge']:.0f} Einheiten "
              f"({row['auftraege']} Aufträge)")
    return df


# ---------------------------------------------------------------------------
# Schritt 2: Synthetische History generieren
# ---------------------------------------------------------------------------
def generate_synthetic_history(real_df: pd.DataFrame,
                                n_months: int = SYNTHETIC_MONTHS) -> pd.DataFrame:
    """Generiert eine plausible Absatz-History basierend auf den echten Statistiken.
    Verwendet Saisonalität + stochastischen Trend damit ARIMA sinnvoll trainiert
    werden kann. Alle generierten Punkte werden als synthetisch markiert."""

    print(f"[2/5] Generiere {n_months} Monate synthetische History...")
    print(f"  Basis: realer Mittelwert = {real_df['menge'].mean():.0f} Einheiten/Monat")

    real_mean = float(real_df["menge"].mean())
    std_val   = real_df["menge"].std()
    # Bei 1 Datenpunkt gibt std() NaN zurück → Fallback auf 15% des Mittelwerts
    real_std  = real_mean * 0.15 if (pd.isna(std_val) or std_val == 0) else max(float(std_val), real_mean * 0.15)

    # Start: n_months vor dem ersten echten Datenpunkt
    first_real_date = real_df["datum"].min()
    start_date = first_real_date - pd.DateOffset(months=n_months)

    rows = []
    # Leichter Aufwärtstrend über 24 Monate (+10% gesamt)
    trend_monthly = (real_mean * 1.10 - real_mean * 0.90) / n_months

    for i in range(n_months):
        datum  = start_date + pd.DateOffset(months=i)
        monat  = datum.month
        trend_val = real_mean * 0.90 + trend_monthly * i
        saisonal  = SEASONAL_PATTERN[monat]
        noise     = np.random.normal(0, real_std * 0.20)  # 20% Rauschen

        menge = max(1, trend_val * saisonal + noise)
        rows.append({
            "datum":       datum,
            "menge":       round(menge),
            "umsatz":      round(menge * (real_df["umsatz"] / real_df["menge"]).mean(), 2),
            "synthetisch": True,
        })

    synth_df = pd.DataFrame(rows)
    print(f"  Synthetisch: {synth_df['menge'].min():.0f} – {synth_df['menge'].max():.0f} "
          f"Einheiten (Min/Max)")
    return synth_df


# ---------------------------------------------------------------------------
# Schritt 3: Stationarität prüfen und ARIMA fitten
# ---------------------------------------------------------------------------
def fit_arima(ts: pd.Series):
    """Prüft Stationarität (ADF-Test) und fittet ARIMA(p,d,q).
    Automatische Wahl von d (Differenzierungsgrad) basierend auf ADF-Test."""

    print("[3/5] Prüfe Stationarität + Fitte ARIMA-Modell...")

    # ADF-Test: H0 = Nicht-stationär; p < 0.05 → stationär
    adf_result = adfuller(ts.dropna())
    p_value    = adf_result[1]
    d          = 0 if p_value < 0.05 else 1
    print(f"  ADF-Test: p-Wert = {p_value:.4f} → d = {d} "
          f"({'stationär' if d == 0 else 'nicht-stationär → 1x differenzieren'})")

    # ARIMA(1,d,1) als solider Standardansatz für Absatzdaten
    # p=1: AR-Term (Autokorrelation mit Vormonat)
    # d: Differenzierung (aus ADF-Test)
    # q=1: MA-Term (Moving Average des Fehlers)
    model  = ARIMA(ts, order=(1, d, 1))
    fitted = model.fit()

    print(f"  ARIMA(1,{d},1) gefittet:")
    print(f"  AIC = {fitted.aic:.2f} | BIC = {fitted.bic:.2f}")
    return fitted, d


# ---------------------------------------------------------------------------
# Schritt 4: Prognose erstellen
# ---------------------------------------------------------------------------
def make_forecast(fitted_model, last_date: pd.Timestamp,
                  n: int = FORECAST_MONTHS):
    """Erstellt Prognose für n Monate mit 95%-Konfidenzintervall."""

    print(f"[4/5] Erstelle {n}-Monats-Prognose...")
    forecast_result = fitted_model.get_forecast(steps=n)
    mean_forecast   = forecast_result.predicted_mean
    conf_int        = forecast_result.conf_int(alpha=0.05)  # 95% KI

    # Datums-Index für Prognosemonate
    forecast_dates = [last_date + pd.DateOffset(months=i+1) for i in range(n)]

    forecast_df = pd.DataFrame({
        "datum":      forecast_dates,
        "prognose":   mean_forecast.values,
        "lower_95":   conf_int.iloc[:, 0].values,
        "upper_95":   conf_int.iloc[:, 1].values,
    })
    # Negative Werte vermeiden (Absatz ≥ 0)
    forecast_df[["prognose", "lower_95", "upper_95"]] = \
        forecast_df[["prognose", "lower_95", "upper_95"]].clip(lower=0)

    print(f"  Prognosemonate:")
    for _, row in forecast_df.iterrows():
        print(f"  • {row['datum'].strftime('%Y-%m')}: {row['prognose']:.0f} Einheiten "
              f"[95%-KI: {row['lower_95']:.0f} – {row['upper_95']:.0f}]")
    return forecast_df


# ---------------------------------------------------------------------------
# Schritt 5: Modellbewertung + Visualisierung
# ---------------------------------------------------------------------------
def evaluate_and_plot(full_df: pd.DataFrame, forecast_df: pd.DataFrame,
                      real_df: pd.DataFrame, fitted_model, d: int):
    """Berechnet den In-Sample-Fit-Fehler auf echten Monaten und erstellt den Chart."""

    # In-Sample-Fehler gegen echte Monatswerte aus dem DWH.
    # Das ist kein echter Holdout-Test, weil alle realen Monate im Training enthalten sind.
    real_vals   = real_df.set_index("datum")["menge"]
    fitted_vals = fitted_model.fittedvalues

    # Nur Punkte bewerten, die sowohl in real als auch im Fit vorhanden sind
    common_idx  = real_vals.index.intersection(fitted_vals.index)
    if len(common_idx) > 0:
        rmse = float(np.sqrt(((real_vals[common_idx] - fitted_vals[common_idx])**2).mean()))
        mae  = float((real_vals[common_idx] - fitted_vals[common_idx]).abs().mean())
        print(f"[5/5] Modellbewertung (In-Sample, n={len(common_idx)} echte Punkte):")
        print(f"  RMSE = {rmse:.1f} Einheiten")
        print(f"  MAE  = {mae:.1f} Einheiten")
    else:
        rmse, mae = None, None
        print("[5/5] Modellbewertung: keine Überschneidung echte/gefittete Punkte")

    # ── Plot ────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(
        1, 2,
        figsize=(17, 6.4),
        facecolor="#F8FAFC",
        gridspec_kw={"width_ratios": [1.08, 1.0]},
    )
    fig.suptitle("Absatzprognose – Banana Supply Chain (Monatsmengen)",
                 fontsize=16, fontweight="bold", color="#1E3A5F", y=1.02)

    # -- Subplot 1: Zeitreihe + Prognose ---------------------------------
    ax1 = axes[0]

    synth = full_df[full_df["synthetisch"] == True]
    real  = full_df[full_df["synthetisch"] == False]

    # Synthetische History (gestrichelt, grau)
    ax1.plot(synth["datum"], synth["menge"],
             color="#94A3B8", linewidth=1.5, linestyle="--",
             label="Synthetische History (Simulation)")
    ax1.fill_between(synth["datum"], synth["menge"] * 0.85, synth["menge"] * 1.15,
                     color="#94A3B8", alpha=0.15)

    # Echte Monatswerte
    ax1.scatter(real["datum"], real["menge"],
                color="#1E3A5F", s=120, zorder=10, label="Echte Monatswerte (DWH)")
    ax1.plot(real["datum"], real["menge"], color="#1E3A5F", linewidth=2)

    # Prognose
    ax1.plot(forecast_df["datum"], forecast_df["prognose"],
             color="#2563EB", linewidth=2.5, marker="o", markersize=7,
             label=f"ARIMA(1,{d},1)-Prognose")
    ax1.fill_between(forecast_df["datum"],
                     forecast_df["lower_95"], forecast_df["upper_95"],
                     color="#2563EB", alpha=0.15, label="95%-Konfidenzintervall")

    # Trennlinie Vergangenheit / Zukunft
    last_real = full_df["datum"].max()
    ax1.axvline(x=last_real, color="#DC2626", linestyle=":", linewidth=1.5,
                label="Prognosestart")

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")
    ax1.set_title("Monatlicher Absatz + 3-Monats-Prognose\n(Menge in Einheiten)",
                  fontweight="bold", color="#1E3A5F")
    ax1.set_xlabel("Monat")
    ax1.set_ylabel("Absatzmenge (Einheiten)")
    ax1.legend(fontsize=8, loc="upper left")
    ax1.set_facecolor("#FFFFFF")

    # Prognose-Werte annotieren
    for _, row in forecast_df.iterrows():
        ax1.annotate(f"{row['prognose']:.0f}",
                     xy=(row["datum"], row["prognose"]),
                     xytext=(0, 12), textcoords="offset points",
                     ha="center", fontsize=8, color="#2563EB", fontweight="bold")

    # -- Subplot 2: Modell-Info + Prognose-Tabelle -----------------------
    ax2 = axes[1]
    ax2.axis("off")

    # Prognose-Tabelle
    table_rows = []
    for _, row in forecast_df.iterrows():
        table_rows.append([
            row["datum"].strftime("%b %Y"),
            f"{row['prognose']:.0f}",
            f"{row['lower_95']:.0f} – {row['upper_95']:.0f}",
        ])

    tbl = ax2.table(
        cellText=table_rows,
        colLabels=["Monat", "Prognose\n(Einheiten)", "95%-Konfidenz\nintervall"],
        loc="center",
        cellLoc="center",
        bbox=[0.02, 0.58, 0.96, 0.34],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 2)
    for col in range(3):
        tbl[0, col].set_facecolor("#1E3A5F")
        tbl[0, col].set_text_props(color="white", fontweight="bold")
    for row_i in range(1, len(table_rows) + 1):
        for col in range(3):
            tbl[row_i, col].set_facecolor("#EFF6FF")

    # Modell-Info-Box
    info_lines = [
        "Modell-Details",
        "─" * 30,
        f"Methode:   ARIMA(1,{d},1)",
        f"Stationarität: d={d} {'✓ stationär' if d == 0 else '→ 1x diff.'}",
        f"Training:  {SYNTHETIC_MONTHS} Monate (synth.)",
        f"           + {len(real_df)} Monat(e) real",
        "",
        f"Prognose:  {FORECAST_MONTHS} Monate voraus",
        f"KI-Niveau: 95%",
        "",
    ]
    if rmse is not None:
        info_lines += [
            "Fit-Fehler (echte Monate):",
            f"  RMSE = {rmse:.1f} Einheiten",
            f"  MAE  = {mae:.1f} Einheiten",
            "  Hinweis: In-Sample,",
            "  kein Holdout-Test.",
        ]

    info_lines += [
        "",
        "Hinweis:",
        "Synthetische History wurde auf",
        "Basis realer Statistiken erzeugt.",
        "Erster/letzter Realmonat sind",
        "Randmonate der 52-Wochen-Reihe.",
        "Prognose verbessert sich deutlich",
        "mit längerer echter Historie.",
    ]

    ax2.text(0.05, 0.52, "\n".join(info_lines),
             transform=ax2.transAxes,
             verticalalignment="top", fontsize=9,
             fontfamily="monospace",
             bbox=dict(boxstyle="round", facecolor="#F0F9FF",
                       edgecolor="#2563EB", alpha=0.8))

    fig.text(0.5, -0.04,
             "Methode: ARIMA(statsmodels) | Saisonales Muster: Bananen-Sommer-Peak "
             "| Gruppe 7 – DMA SoSe 26 | TH Lübeck",
             ha="center", fontsize=8, color="#64748B")

    plt.tight_layout()
    fig.savefig(PNG_PATH, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(PDF_PATH, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Gespeichert: {PNG_PATH}")
    print(f"  Gespeichert: {PDF_PATH}")

    # Modell-Summary als Text speichern
    with open(TXT_PATH, "w") as f:
        f.write(str(fitted_model.summary()))
    print(f"  Modell-Summary: {TXT_PATH}")

    return rmse, mae


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Absatzprognose – ARIMA-Zeitreihenmodell")
    print("=" * 60)

    real_df   = load_real_timeseries()
    synth_df  = generate_synthetic_history(real_df)

    # Zeitreihe zusammenführen: synthetische History + echte Daten
    full_df   = pd.concat([synth_df, real_df[["datum", "menge", "synthetisch"]]],
                          ignore_index=True).sort_values("datum").reset_index(drop=True)

    ts = full_df.set_index("datum")["menge"].asfreq("MS")  # Monthly Start frequency

    fitted_model, d = fit_arima(ts)
    forecast_df     = make_forecast(fitted_model, full_df["datum"].max())
    rmse, mae       = evaluate_and_plot(full_df, forecast_df, real_df, fitted_model, d)

    print()
    print("=" * 60)
    print("  Absatzprognose abgeschlossen")
    print(f"  Ausgabe: forecast.png / forecast.pdf")
    print(f"  Modell-Summary: forecast_model_summary.txt")
    print("=" * 60)


if __name__ == "__main__":
    main()
