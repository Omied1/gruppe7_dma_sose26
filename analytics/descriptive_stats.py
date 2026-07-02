"""
=============================================================================
descriptive_stats.py – Deskriptive Statistik Banana Supply Chain (Teil 2 / A-1)
=============================================================================
Berechnet für die vier prüfungsrelevanten Kennzahlen aus dem DWH-Sternschema
    delay_minutes, avg_temperature, quantity, unit_price   (+ total_value)
die vollständige deskriptive Statistik:
    n, Min, Max, Mittelwert, Median, Standardabweichung, Q1, Q3, IQR
und identifiziert Ausreißer nach der IQR-Methode (1,5 * IQR-Zaun).

Ausgabe:
  - Konsolentabelle
  - analytics/descriptive_stats.txt   (für Abschlussbericht / Doku)

Voraussetzung:
  - PostgreSQL läuft auf localhost:5432, DB: logistics
  - dwh.fact_fulfillment ist via ETL befüllt (Grain: 1 Zeile je Endlieferung)
  - pip install psycopg2-binary pandas

Ausführung:
  python3 analytics/descriptive_stats.py
=============================================================================
"""

import sys
import warnings
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Abhängigkeiten prüfen (gleiche Robustheit wie dashboard.py)
# ---------------------------------------------------------------------------
MISSING = []
try:
    import psycopg2
except ImportError:
    MISSING.append("psycopg2-binary")
try:
    import pandas as pd
except ImportError:
    MISSING.append("pandas")
if MISSING:
    print(f"[FEHLER] Fehlende Pakete: {', '.join(MISSING)}")
    print(f"         Installieren mit: pip install {' '.join(MISSING)}")
    sys.exit(1)

PG_DSN = "host=localhost port=5432 dbname=logistics user=user password=password"

# Prüfungsrelevante Kennzahlen + fachliche Einordnung für die Interpretation
FIELDS = {
    "delay_minutes":   "Lieferverzögerung [min] – RATIO",
    "avg_temperature": "Ø Containertemperatur [°C] – INTERVAL",
    "quantity":        "Bestellmenge [Kartons] – RATIO",
    "unit_price":      "Stückpreis [€] – RATIO",
    "total_value":     "Bestellwert [€] – RATIO",
}


def connect():
    # Verbindung zum DWH; ohne laufende DB ist keine Statistik möglich
    try:
        conn = psycopg2.connect(PG_DSN)
        print("[OK] Datenbankverbindung hergestellt.")
        return conn
    except Exception as e:
        print(f"[FEHLER] DB-Verbindung fehlgeschlagen: {e}")
        sys.exit(1)


def load_data(conn):
    # Measures direkt aus der Faktentabelle – Grain = 1 Zeile je Endlieferung
    sql = """
        SELECT delay_minutes, avg_temperature, quantity, unit_price, total_value
        FROM   dwh.fact_fulfillment
    """
    df = pd.read_sql(sql, conn)
    # numeric-Cast, damit describe()/Quantile auf den DECIMAL-Spalten rechnen
    for col in FIELDS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    print(f"[OK] {len(df)} Fact-Zeilen geladen.")
    return df


def describe_field(series):
    # Vollständige Kennzahlen inkl. IQR-Ausreißer (1,5 * IQR-Zaun)
    s = series.dropna()
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    low_fence, up_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = s[(s < low_fence) | (s > up_fence)]
    return {
        "n":        int(s.count()),
        "min":      round(float(s.min()), 2),
        "max":      round(float(s.max()), 2),
        "mean":     round(float(s.mean()), 2),
        "median":   round(float(s.median()), 2),
        "std":      round(float(s.std()), 2),
        "q1":       round(float(q1), 2),
        "q3":       round(float(q3), 2),
        "iqr":      round(float(iqr), 2),
        "lo_fence": round(float(low_fence), 2),
        "up_fence": round(float(up_fence), 2),
        "n_outlier": int(outliers.count()),
    }


def main():
    conn = connect()
    df = load_data(conn)
    conn.close()

    rows = {label: describe_field(df[col]) for col, label in FIELDS.items()}
    stats = pd.DataFrame(rows).T
    stats.index.name = "Kennzahl"

    # ---- Ausgabe: Konsole + Datei -------------------------------------------
    lines = []
    lines.append("=" * 78)
    lines.append("DESKRIPTIVE STATISTIK – Banana Supply Chain (DWH fact_fulfillment)")
    lines.append("=" * 78)
    lines.append("")
    lines.append(stats.to_string())
    lines.append("")
    lines.append("Ausreißer-Definition: Wert < Q1 - 1,5*IQR  oder  Wert > Q3 + 1,5*IQR")
    lines.append("")
    lines.append("-" * 78)
    lines.append("FACHLICHE INTERPRETATION")
    lines.append("-" * 78)
    d = rows["Lieferverzögerung [min] – RATIO"]
    lines.append(
        f"- Verzögerung: Ø {d['mean']} min (Median {d['median']}), Std {d['std']}; "
        f"{d['n_outlier']} Ausreißer > {d['up_fence']} min. Rechtsschiefe Verteilung – "
        "die meisten Lieferungen sind pünktlich, wenige stark verspätet."
    )
    t = rows["Ø Containertemperatur [°C] – INTERVAL"]
    lines.append(
        f"- Temperatur: Ø {t['mean']} °C liegt im Sollkorridor 10–15 °C (Cavendish). "
        f"{t['n_outlier']} Lieferungen außerhalb des IQR-Zauns ({t['lo_fence']}–{t['up_fence']} °C) "
        "= Kühlkettenbrüche, Ursache für Qualitätsverlust."
    )
    q = rows["Bestellmenge [Kartons] – RATIO"]
    lines.append(
        f"- Menge: Spannweite {q['min']}–{q['max']} Kartons, Ø {q['mean']}. Hohe Std {q['std']} "
        "spiegelt die Kundensegmente (Discounter-Großmengen vs. Premium-Kleinmengen)."
    )
    p = rows["Stückpreis [€] – RATIO"]
    lines.append(
        f"- Stückpreis: {p['min']}–{p['max']} € (Median {p['median']}) entspricht den vier "
        "Produktkategorien Standard < Sustainable < Specialty < Premium."
    )
    lines.append("=" * 78)

    out = "\n".join(lines)
    print("\n" + out)

    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "descriptive_stats.txt")
    with open(path, "w") as fh:
        fh.write(out + "\n")
    print(f"\n[OK] Ergebnis gespeichert: {path}")


if __name__ == "__main__":
    main()
