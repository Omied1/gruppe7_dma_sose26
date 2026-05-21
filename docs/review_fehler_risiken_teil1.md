# Review: Fehler, Risiken und Lücken — Teil 1 Abgabe
**Erstellt:** 2026-05-21  
**Reviewer:** Unabhängige Analyse (ohne Projekt_Gesamtueberblick_Teil1.md)  
**Grundlage:** Direktes Lesen aller Quelldateien + Live-Checks gegen laufende Docker-Container  
**Deadline Abgabe:** 01.07.2026

---

## Legende

| Symbol | Bedeutung |
|--------|-----------|
| 🔴 KRITISCH | Muss vor Abgabe behoben werden — direkte Auswirkung auf Bewertung |
| 🟡 WARNUNG | Sollte behoben werden — Inkonsistenz oder Risiko |
| 🟢 OK | Funktioniert korrekt |
| ℹ️ INFO | Hinweis ohne direkten Handlungsbedarf |

---

## 1. Datenkonsistenz-Fehler

### 🔴 FEHLER 1: `erp.document_references` ist leer — MinIO hat aber 98 Dokumente

**Problem:**  
`generate_documents.py` wurde zu einem früheren Zeitpunkt ausgeführt (MinIO hat 98 PDF-Objekte in den Buckets), aber die Tabelle `erp.document_references` hat **0 Zeilen**.

**Ursache:**  
Die Datenbank wurde nach dem Ausführen von `generate_documents.py` zurückgesetzt (oder `generate_documents.py` wurde nie korrekt mit dem aktuellen Datenbankstand ausgeführt).

**Konsequenz:**  
- `09_verification_queries.sql` zeigt für `erp.document_references`: Wert = 0, Erwartung = ≥66 → **visuell sichtbarer FAIL in der Abgabe**
- Die Verbindung PostgreSQL ↔ MinIO (Referenzierungsmuster) ist nicht nachweisbar

**Prüfbefehl:**
```bash
docker exec postgres psql -U user -d logistics -c "SELECT COUNT(*) FROM erp.document_references;"
# Erwartet: ≥ 66, Aktuell: 0
```

**Fix:**
```bash
cd bananasupplychain
python3 generate_documents.py
```

---

### 🟡 WARNUNG 2: MongoDB `batch_tracking` hat 10 Einträge — Dokumentation behauptet 60

**Problem:**  
Die Datei `docs/00_part1_checklist.md` schreibt: *"batch_tracking (60)"*  
Der Live-Stand zeigt: **10 Einträge**

**Prüfbefehl:**
```bash
docker exec mongodb mongosh --quiet --eval "db=db.getSiblingDB('logistics'); print(db.batch_tracking.countDocuments())"
# Aktuell: 10
```

**Ursache:**  
Der ETL lädt 1 Tracking-Eintrag pro Bestellung (10 Iterationen = 10 Einträge). Der Wert 60 in der Checklist ist falsch. Es gibt 60 Shipments, aber Batch-Tracking ist auf Bestellungsebene, nicht Shipment-Ebene.

**Konsequenz:**  
Checklist-Dokument enthält falsche Zahlen → Glaubwürdigkeitsproblem bei der Abgabe.

**Fix:** In `docs/00_part1_checklist.md` Zeile 200 und 211 korrigieren: `batch_tracking (60)` → `batch_tracking (10)`

---

### 🟡 WARNUNG 3: TMS JSON-Dateien — Checklist sagt 263, tatsächlich sind es 257

**Problem:**  
- `docs/00_part1_checklist.md`: *"shared/tms/ | 257 JSON-Dateien"* (Tabelle unten korrekt)
- Aber Zeile 211 im ETL-Ergebnis-Block: *"shared/tms/: 263 Dateien"*
- Tatsächlicher Bestand: **257 Dateien**

**Prüfbefehl:**
```bash
ls shared/tms/ | wc -l
# Aktuell: 257
```

**Fix:** Überall einheitlich 257 verwenden. Die 263 in Zeile 200 der Checklist ist falsch.

---

### 🟡 WARNUNG 4: `09_verification_queries.sql` hatte Spaltenfehler (`date_actual`)

**Problem:**  
Das Script referenzierte `date_actual`, die Spalte heißt aber `full_date` in `dwh.dim_date`.

**Status:** ✅ Bereits in dieser Session behoben.  
**Prüfbefehl:**
```bash
cat sql/09_verification_queries.sql | docker exec -i postgres psql -U user -d logistics 2>&1 | grep ERROR
# Erwartet: keine Ausgabe
```

---

## 2. Strukturelle Risiken

### 🔴 RISIKO 1: Zwei `docker-compose.yml` Dateien mit identischen Container-Namen und Ports

**Problem:**  
Es gibt **zwei** Docker-Compose-Dateien im Projekt:
- `bananasupplychain/container/docker-compose.yml` → Das eigentliche Projektfile
- `databasemodels_logistics_playground/container/docker-compose.yml` → Demo/Vorlage

Beide definieren Container mit **identischen Namen** (`postgres`, `mongodb`, `redis`, `neo4j`, `minio`) und **identischen Ports** (5432, 27017, 6379, 7474, 9000).

**Konsequenz:**  
Wenn versehentlich das falsche `docker-compose.yml` gestartet wird, entstehen Port-Konflikte und die Projektdatenbanken werden überschrieben oder die Container starten nicht.

**Risiko-Szenario:**  
Jemand führt im falschen Verzeichnis `docker-compose up -d` aus und löscht damit alle Projektdaten.

**Prüfbefehl:**
```bash
# Welche Container laufen aktuell?
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}"
```

**Empfehlung:**  
In der Abgabe-Dokumentation klar kennzeichnen: "Immer aus `bananasupplychain/container/` starten."

---

### 🔴 RISIKO 2: `databasemodels_logistics_playground/` enthält Cleanup-Skripte, die Projektdaten löschen können

**Problem:**  
Im Ordner `databasemodels_logistics_playground/src/` liegen:
- `cleanup_simulated_data.py`
- `cleanup_initialized_db.py`

Diese Skripte löschen Daten aus PostgreSQL. Wenn sie versehentlich gegen den Projekt-Container ausgeführt werden, sind alle ETL-Daten verloren.

**Empfehlung:**  
Im README oder in der Dokumentation explizit warnen, dass `databasemodels_logistics_playground/` nur ein Demo-Ordner ist und nicht für das eigentliche Projekt verwendet werden soll.

---

### 🟡 RISIKO 3: Leerer Ordner `bananasupplychain/shared/wms/`

**Problem:**  
Es existiert ein leerer Ordner `bananasupplychain/shared/wms/`, der verwirrt. Die echten JSON-Dateien liegen in `shared/wms/` (Projektroot), nicht hier.

**Prüfbefehl:**
```bash
ls bananasupplychain/shared/wms/ | wc -l
# Erwartet/Aktuell: 0 (leer)
ls shared/wms/ | wc -l
# Aktuell: 70 (korrekt)
```

**Konsequenz:**  
Wenn `etl_load.py` aus dem falschen Verzeichnis gestartet wird und `SHARED` falsch aufgelöst wird, findet es keine JSON-Dateien.

**Aktueller Status:** Der SHARED-Pfad in `etl_load.py` ist korrekt (`../shared`), aber der leere Ordner ist ein Verwirrungspotenzial.

---

### 🟡 RISIKO 4: `etl_load.py` muss zwingend aus `bananasupplychain/` gestartet werden

**Problem:**  
`etl_load.py` baut den SHARED-Pfad relativ zu seiner eigenen Position auf:
```python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED   = os.path.join(BASE_DIR, "..", "shared")
```

Das funktioniert **nur**, wenn das Skript aus dem `bananasupplychain/`-Ordner oder mit absolutem Pfad gestartet wird. Ein Start aus dem Projektroot (`python3 bananasupplychain/etl_load.py`) würde zwar auch funktionieren, aber aus anderen Verzeichnissen nicht.

**Empfehlung:**  
In der Ausführungsanleitung immer explizit schreiben:
```bash
cd bananasupplychain
python3 etl_load.py
```

---

## 3. Dokumentationsprobleme

### 🟡 PROBLEM 1: `README.md` enthält keinen projektspezifischen Inhalt

**Problem:**  
Die `README.md` im Projektroot ist der **Standard-GitLab-Template-Text** ohne jeglichen Projektbezug. Ein Korrektor, der das Repo öffnet, sieht zuerst diese nichtssagende Datei.

**Empfehlung:**  
README.md durch eine kurze Projektbeschreibung ersetzen:
- Was ist das Projekt?
- Wie starte ich es? (3-4 Befehle)
- Wo finde ich die Dokumentation?

---

### 🟡 PROBLEM 2: `docs/00_part1_checklist.md` enthält mehrere falsche Zahlen

**Konkret falsch:**

| Stelle | Falscher Wert | Korrekter Wert |
|--------|---------------|----------------|
| Zeile 200: MongoDB batch_tracking | 60 | 10 |
| Zeile 211: batch_tracking | 60 | 10 |
| Projektanleitung-PDF: TMS-Dateien | 263 | 257 |

**Risiko:** Ein Korrektor, der die Zahlen in der Checklist gegen die echten Datenbankwerte prüft, findet Diskrepanzen — das wirkt unprofessionell.

---

### ℹ️ HINWEIS 1: `docs/13_data_quality_results.md` — Inhalt prüfen

**Achtung:** Diese Datei enthält vermutlich die Ergebnisse der DQ-Checks. Da die operativen Tabellen zum Zeitpunkt der Analyse **Daten enthalten** (10 Zeilen je), sollten die DQ-Check-Ergebnisse mit der tatsächlichen Datenlage übereinstimmen.

**Prüfbefehl:**
```bash
cat sql/08_data_quality_checks.sql | docker exec -i postgres psql -U user -d logistics 2>&1 | grep -E "verstösse|FAIL|ERROR"
```

---

## 4. ETL und Datenbankzustand

### 🟡 WARNUNG 5: ETL-Zustand nach Neustart der Docker-Container

**Beobachtung:**  
Nach einem Docker-Neustart sind die operativen PostgreSQL-Tabellen weiterhin befüllt (Daten persistent via Volume), aber `erp.document_references = 0`. Das deutet darauf hin, dass `generate_documents.py` zu einem anderen Zeitpunkt als der ETL ausgeführt wurde.

**Reihenfolge für einen sauberen, reproduzierbaren Stand:**
```bash
# 1. Docker starten
cd bananasupplychain/container
docker-compose up -d

# 2. SQL Schemas anlegen (nur einmal nötig)
# Über psql oder DBeaver: sql/01 bis sql/08 ausführen

# 3. Datengenerator (falls shared/ leer)
cd ../bananasupplychain
python3 test_data_generator.py

# 4. ETL Phase 1: operative DBs befüllen
python3 etl_load.py

# 5. ETL Phase 2: DWH befüllen
python3 etl_dwh.py

# 6. MinIO-Dokumente generieren UND PostgreSQL-Referenzen schreiben
python3 generate_documents.py

# 7. Verifizierung
python3 verify_all_systems.py
```

**Wichtig:** Schritt 6 (`generate_documents.py`) wird aktuell übersprungen — deshalb `erp.document_references = 0`.

---

### ℹ️ HINWEIS 2: `dwh.fact_fulfillment` hat nur 10 Zeilen

**Aktueller Stand:** 10 Zeilen (entspricht 10 Iterationen im Datengenerator)  
**Auswirkung auf Analytics (Teil 2):** Für aussagekräftige Visualisierungen, Clustering und Zeitreihenanalysen sind mehr Datenpunkte empfehlenswert.

**Empfehlung:** Vor Teil-2-Arbeiten `iterations` in `test_data_generator.py` auf 50–100 erhöhen und ETL neu durchlaufen.

```python
# test_data_generator.py, letzte Zeile:
iterations = 10  # → auf 50 oder 100 erhöhen
```

---

## 5. Abgleich mit der offiziellen Aufgabenstellung

**Quelle:** `Aufgabenstellung.pdf` (Entwicklung einer DM&A-Plattform, Prof. A. Drews, SoSe 26)

### Teil 1 — Datenmanagement

| Anforderung | Status | Anmerkung |
|-------------|--------|-----------|
| Docker Container starten | 🟢 OK | 5 Container laufen korrekt |
| Datengenerator ausführen + JSON-Dateien | 🟢 OK | 377 Dateien in shared/ |
| JSON-Klassifikation nach Stamm-/Bewegungsdaten | 🟢 OK | docs/01_data_classification.md |
| PostgreSQL ERP-Schema | 🟢 OK | 6 Tabellen, befüllt |
| PostgreSQL WMS-Schema | 🟢 OK | 3 Tabellen, befüllt |
| PostgreSQL TMS-Schema | 🟢 OK | 6 Tabellen, befüllt |
| ER-Modell | 🟢 OK | docs/03_er_model.md mit Mermaid |
| MDM-Schema | 🟢 OK | 3 Tabellen, Golden Records befüllt |
| Metadatenmanagement (Skalenniveaus) | 🟢 OK | docs/05_metadata_management.md, meta.columns befüllt |
| DWH-Schema (Sternschema) | 🟢 OK | 7 Dimensionen + fact_fulfillment |
| ETL-Prozesse (ERP/WMS/TMS → DWH) | 🟢 OK | etl_load.py + etl_dwh.py |
| Neo4j Graphmodellierung | 🟢 OK | 122 Nodes, 419 Relationships |
| MongoDB Eventmodellierung | 🟢 OK | 4 Collections, 140 Dokumente |
| MinIO (Lieferscheine als PDF) | 🟡 TEILWEISE | Buckets und PDFs vorhanden, aber erp.document_references = 0 |
| Redis Echtzeitdaten | 🟢 OK | 154 Keys, alle Key-Typen belegt |
| Datenqualitätsmanagement | 🟢 OK | 28 SQL-Checks über 6 Dimensionen |

### Teil 2 — Analytics (noch offen, Deadline 01.07.2026)

| Anforderung | Status | Anmerkung |
|-------------|--------|-----------|
| Deskriptive Statistik / KPIs | 🔴 OFFEN | Nicht implementiert |
| Skalenniveaus in Metadatentabelle | 🟢 OK | Bereits in Teil 1 erledigt |
| 5 Python-Charts (Matplotlib/Seaborn) | 🔴 OFFEN | Nicht implementiert |
| PowerBI-Dashboard | 🟡 IN ARBEIT | Verbindung hergestellt, Dashboard im Aufbau |
| Clustering (Lieferanten oder Kunden) | 🔴 OFFEN | Nicht implementiert |
| Absatzprognose (ARIMA/Prophet) | 🔴 OFFEN | Nicht implementiert |

---

## 6. Prioritätsliste: Was muss vor Abgabe gemacht werden?

### Sofort (vor nächstem Test)
1. **`generate_documents.py` ausführen** → behebt `erp.document_references = 0`
2. **Checklist-Zahlen korrigieren** → batch_tracking: 60 → 10

### Vor Abgabe (Teil 1 abschließen)
3. **README.md** projektspezifisch befüllen
4. **Zwei docker-compose.yml Dateien** klar dokumentieren/kommentieren (welche ist die richtige)
5. **`bananasupplychain/shared/wms/`** Leerordner entfernen oder kommentieren

### Für Teil 2 (bis 01.07.2026)
6. Mehr Testdaten generieren (`iterations = 50+`)
7. 5 Python-Charts implementieren
8. PowerBI-Dashboard fertigstellen
9. Clustering implementieren (k-Means auf Kunden/Lieferanten)
10. Absatzprognose implementieren (ARIMA oder Prophet)

---

## 7. Reproduzierbarkeitsprüfung

**Kann das Projekt von Null auf einem neuen Rechner aufgebaut werden?**

| Schritt | Dokumentiert? | Funktioniert? |
|---------|--------------|---------------|
| Docker installieren | ✅ | ✅ |
| Container starten | ✅ | ✅ |
| SQL-Schemas anlegen | ✅ | ✅ (Reihenfolge 01-08 beachten) |
| Python-Abhängigkeiten installieren | ✅ (in Projektanleitung) | ✅ |
| Datengenerator ausführen | ✅ | ✅ |
| ETL Phase 1 ausführen | ✅ | ✅ |
| ETL Phase 2 ausführen | ✅ | ✅ |
| generate_documents.py ausführen | ⚠️ oft vergessen | ✅ (wenn ausgeführt) |
| Verifizierung | ✅ | ✅ |

**Fazit Reproduzierbarkeit:** Das Projekt ist grundsätzlich reproduzierbar, aber `generate_documents.py` wird in der Praxis oft vergessen, weil es in der Hauptanleitung nicht gleichwertig mit ETL-Phase 1+2 behandelt wird.

---

## 8. Gesamtbewertung Teil 1

**Stand: 2026-05-21**

| Bereich | Bewertung |
|---------|-----------|
| Infrastruktur (Docker) | 🟢 Vollständig |
| Datenmodelle (SQL) | 🟢 Vollständig |
| ETL-Prozesse | 🟢 Vollständig |
| MDM | 🟢 Vollständig |
| Metadatenmanagement | 🟢 Vollständig |
| DWH | 🟢 Vollständig |
| Neo4j | 🟢 Vollständig |
| MongoDB | 🟢 Vollständig |
| Redis | 🟢 Vollständig |
| MinIO | 🟡 1 Fix nötig (document_references) |
| Datenqualität | 🟢 Vollständig |
| Dokumentation | 🟡 README leer, Checklist-Zahlen falsch |

**Abgabebereit Teil 1:** JA — nach Behebung der 2 kritischen Punkte (generate_documents.py ausführen + README.md befüllen)

**Offenes Risiko:** Teil 2 (Analytics) ist vollständig offen mit ca. 6 Wochen bis Deadline.
