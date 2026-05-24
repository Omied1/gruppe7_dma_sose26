- Power BI Desktop Quelle aktualisieren, dann avg. Speed kmh KPI Carrier
  aus neuer View
- mehrere Monata simulieren für BI
- Was für Daten/Tabellen im Generator könnte man perspektivisch hinzufügen

- Datengenerator mehrmals ausführen für mehr Datenbasis (Dashboard/Charts):
  1. test_data_generator.py (mehrmals, z.B. 5x)
  2. etl_load.py
  3. etl_dwh.py
  4. dashboard.py
     → Timestamps vorher auf Monats-Verteilung anpassen (aktuell alles 2026-05)
     damit Chart 1 (Umsatz-Zeitreihe) echte Monate zeigt

- [NACH Datengenerator-Mehrfachlauf] Clustering + Prognose neu ausführen:
  Skripte: analytics/clustering.py und analytics/forecast.py
  Beide laufen bereits fehlerfrei, aber mit sehr wenig Datenbasis (10 Zeilen,
  6 Kunden, 1 Monat). Konkrete Schwächen, die sich nach mehr Daten verbessern:

  Clustering (analytics/clustering.py):
  → Aktuell nur 6 Kunden-Datenpunkte → k=2 ist statistisches Maximum
  → Mit mehr Lieferungen pro Kunde werden die 4 Features (Bestellhäufigkeit,
     Ø Bestellwert, Ø Verzögerung, Liefertreue) stabiler und repräsentativer
  → Silhouette-Score von 0.40 ist akzeptabel, aber nicht stark
     (Ziel: > 0.5 für klare Cluster-Trennung)
  → Kein Code-Änderung nötig – einfach neu ausführen

  Absatzprognose (analytics/forecast.py):
  → Aktuell nur 1 echter Datenpunkt (Mai 2026, 4.949 Einheiten)
  → ARIMA trainiert deshalb auf synthetisch generierter History
     (24 Monate, basierend auf realen Statistiken – transparent markiert)
  → Nach mehreren Generator-Läufen MIT Monats-Timestamps (→ separates To-Do)
     ersetzt das Skript die synthetischen Punkte automatisch durch echte Daten
  → RMSE von 35 Einheiten klingt gut, ist aber irreführend: das Modell
     wurde auf den einzigen echten Punkt quasi "gesehen" (kein echter Test-Split)
  → Ziel nach mehr Daten: Train/Test-Split (z.B. letzte 3 Monate = Test),
     dann ist RMSE/MAE aussagekräftig
