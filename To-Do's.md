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
