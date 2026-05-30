- patch_timestamps.py erstellen (MUSS VOR ALLEM ANDEREN LAUFEN):
  Der Datengenerator schreibt alle Events mit datetime.utcnow() → alle 10
  Iterationen liegen innerhalb von 39 Millisekunden auf demselben Tag (2026-05-15).
  Ohne Fix: Zeitreihen-Charts, ARIMA/Prophet und KPI "Ø Transportdauer" sind
  fachlich wertlos (Transportdauer = 0,000000 Tage).
  Lösung: Skript das JSON-Timestamps nachträglich überschreibt:
  Iteration 1 → Woche KW2 2026 (ca. 2026-01-05)
  Iteration 2 → Woche KW3 2026
  ...
  Supply Chain pro Iteration: ~12 Tage (realistisch Ghana → Europa → Retail)
  Reihenfolge dann: patch_timestamps.py → etl_load.py → etl_dwh.py → Charts
  (Risiko R-5 in PROJECT_STATUS.md dokumentiert)

- generate_documents.py ausführen:
  erp.document_references hat aktuell 0 Zeilen obwohl MinIO 98 Dokumente hat.
  Fix: cd bananasupplychain && python3 generate_documents.py
  (Kritisch für Abgabe-Nachweis PostgreSQL ↔ MinIO)

- README.md projektspezifisch befüllen:
  Aktuell Standard-GitLab-Template ohne Projektinhalt.
  Inhalt: Projektbeschreibung, 3-4 Start-Befehle, Verweis auf docs/

- Dokumenten-Cleanup: "28 DQ-Checks" → "34 DQ-Checks" in veralteten Dateien:
  Der DQ-Audit wurde in der letzten Session von 28 auf 34 Checks erweitert.
  docs/13_data_quality_results.md wurde korrekt aktualisiert (34 Checks, 31/34 PASS).
  Folgende 3 Dateien nennen noch die veraltete Zahl "28" und müssen korrigiert werden:
  docs/00_part1_checklist.md:
  Zeile Q-3: "28 Checks über alle 6 Dimensionen" → "34 Checks"
  Dateiliste: "28 SQL-Qualitätsprüfungen (6 Dimensionen)" → "34 SQL-Qualitätsprüfungen"
  docs/Projekt_Gesamtueberblick_Teil1.md:
  3 Stellen (Zeile 180, 519, 1179) jeweils "28 Checks" → "34"
  docs/review_fehler_risiken_teil1.md:
  Abgleich-Tabelle: "28 SQL-Checks über 6 Dimensionen" → "34 SQL-Checks"

- docs/00_part1_checklist.md: MinIO-Status und ETL-Ergebnis korrigieren:
  Aktuell steht ✅ bei Mi-4 (Referenzierungsmuster PostgreSQL ↔ MinIO) obwohl
  erp.document_references = 0 Zeilen (generate_documents.py nicht ausgeführt).
  Fix NACH generate_documents.py:
  Mi-4 Status: wieder ✅ mit Nachweis
  ETL-Ergebnis Tabelle (Zeile 203/214): 0 → 98 Referenzen
  "Offene Punkte"-Tabelle: generate_documents.py als erledigten Punkt kennzeichnen

- Strukturelle Cleanup-Aufgaben (Abgabe-Klarheit):
  a) bananasupplychain/shared/wms/ Leerordner:
  Dieser Ordner ist leer (die echten JSONs liegen in shared/wms/).
  Verwirrungspotenzial wenn ETL aus falschem Verzeichnis gestartet wird.
  Fix: Ordner löschen oder .gitkeep mit erklärendem Kommentar ablegen
  b) Zwei docker-compose.yml Dateien (identische Port-Konflikte):
  bananasupplychain/container/docker-compose.yml → Projektfile (richtig)
  databasemodels_logistics_playground/container/docker-compose.yml → Demo-Vorlage
  Fix: Im README explizit darauf hinweisen welche gestartet werden muss
  c) databasemodels_logistics_playground/ Cleanup-Skripte (cleanup_simulated_data.py,
  cleanup_initialized_db.py) können Projektdaten löschen wenn falsch ausgeführt.
  Fix: Warnung in README / docs/

- Power BI Desktop Quelle aktualisieren, dann avg. Speed kmh KPI Carrier
  aus neuer View
- mehrere Monata simulieren für BI
- Was für Daten/Tabellen im Generator könnte man perspektivisch hinzufügen
- BI-Werte Plausi-Check - Gesamtumsatz runterrechnen auf einzelne Lieferungen

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
  - Glasdesign Power BI
