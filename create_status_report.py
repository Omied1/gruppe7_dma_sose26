from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from datetime import date

OUTPUT = "/Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26/Projektstand_Gruppe7_DMA_SoSe26.pdf"

doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=A4,
    rightMargin=2*cm, leftMargin=2*cm,
    topMargin=2.5*cm, bottomMargin=2*cm,
    title="Projektstand Gruppe 7 – DMA SoSe26"
)

styles = getSampleStyleSheet()

# Custom styles
title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=20, spaceAfter=6, textColor=colors.HexColor("#1a1a2e"))
h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=14, spaceBefore=16, spaceAfter=6, textColor=colors.HexColor("#16213e"))
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#0f3460"))
body = ParagraphStyle("Body2", parent=styles["Normal"], fontSize=9.5, spaceAfter=4, leading=14)
small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#555555"))
code_style = ParagraphStyle("Code", parent=styles["Code"], fontSize=8, leading=12, leftIndent=10, backColor=colors.HexColor("#f4f4f4"))

GREEN = colors.HexColor("#27ae60")
ORANGE = colors.HexColor("#e67e22")
RED = colors.HexColor("#e74c3c")
BLUE = colors.HexColor("#2980b9")
LIGHT_BLUE = colors.HexColor("#ebf5fb")
LIGHT_GREEN = colors.HexColor("#eafaf1")
LIGHT_ORANGE = colors.HexColor("#fef9e7")

def check_row(num, req, status, note):
    if status == "✅":
        bg = LIGHT_GREEN
        sc = GREEN
    elif status == "⚠️":
        bg = LIGHT_ORANGE
        sc = ORANGE
    else:
        bg = colors.HexColor("#fdedec")
        sc = RED
    return [num, req, Paragraph(f'<font color="{sc.hexval()}">{status}</font>', body), note], bg

def make_table(headers, rows_data):
    table_data = [headers]
    row_styles = []
    for i, (row, bg) in enumerate(rows_data):
        table_data.append(row)
        row_styles.append(("BACKGROUND", (0, i+1), (-1, i+1), bg))

    col_widths = [1*cm, 6.5*cm, 1.5*cm, 7.5*cm]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    base_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    t.setStyle(TableStyle(base_style + row_styles))
    return t

def simple_table(data, col_widths, header_bg=colors.HexColor("#16213e")):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t

# ──────────────────────────────────────────────
story = []

# TITLE PAGE
story.append(Spacer(1, 1.5*cm))
story.append(Paragraph("Projektstatusbericht", title_style))
story.append(Paragraph("Gruppe 7 – Datenmanagement und Analytics (M.Sc.) SoSe 26", h1))
story.append(Paragraph("Banana Supply Chain Datenplattform", h2))
story.append(Spacer(1, 0.3*cm))
story.append(HRFlowable(width="100%", thickness=2, color=BLUE))
story.append(Spacer(1, 0.3*cm))

meta = [
    ["Erstellt am:", str(date.today())],
    ["Deadline:", "01.07.2026"],
    ["Modul:", "Datenmanagement und Analytics (M.Sc.), SoSe 26"],
    ["Repository:", "git.mylab.th-luebeck.de/omied.firouzian/gruppe7_dma_sose26"],
    ["Letzte Commits:", "V3 – alle Daten hochgeladen (2026-05-13)"],
]
mt = Table(meta, colWidths=[4*cm, 12.5*cm])
mt.setStyle(TableStyle([
    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ("TEXTCOLOR", (0, 0), (0, -1), BLUE),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
]))
story.append(mt)
story.append(Spacer(1, 0.5*cm))

# Summary box
summary_data = [
    [Paragraph("<b>Gesamtstatus Teil 1: Alle Pflichtanforderungen erfüllt ✅</b>", ParagraphStyle("sb", fontSize=10, textColor=colors.white))]
]
st = Table(summary_data, colWidths=[16.5*cm])
st.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,-1), GREEN),
    ("LEFTPADDING", (0,0), (-1,-1), 12),
    ("TOPPADDING", (0,0), (-1,-1), 8),
    ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ("ROUNDEDCORNERS", (0,0), (-1,-1), 4),
]))
story.append(st)
story.append(Spacer(1, 0.4*cm))
story.append(Paragraph(
    "Dieser Bericht fasst alle erledigten Aufgaben, gelieferten Artefakte und noch offenen Punkte "
    "für das Projekt Banana Supply Chain Datenplattform zusammen.",
    body
))

story.append(PageBreak())

# ──────────────────────────────────────────────
# 1. ERLEDIGTE AUFGABEN
story.append(Paragraph("1. Erledigte Aufgaben – Teil 1: Datenmanagement", h1))
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
story.append(Spacer(1, 0.2*cm))

# 1.1 Infrastruktur
story.append(Paragraph("1.1 Infrastruktur", h2))
hdrs = ["#", "Anforderung", "Status", "Nachweis"]
rows = [
    check_row("I-1", "Gruppe & Repo eingerichtet", "✅", "GitLab-Repo: gruppe7_dma_sose26"),
    check_row("I-2", "Vorgegebene Folderstruktur hochgeladen", "✅", "bananasupplychain/, databasemodels_logistics_playground/"),
    check_row("I-3", "Docker Container startbar", "✅", "docker-compose.yml – 5 Services: PostgreSQL, MongoDB, Redis, Neo4j, MinIO"),
    check_row("I-4", "Datengenerator ausgeführt", "✅", "shared/erp/ (50), shared/wms/ (70), shared/tms/ (263) JSON-Dateien"),
]
story.append(make_table(hdrs, rows))
story.append(Spacer(1, 0.3*cm))

# 1.2 Datenklassifikation
story.append(Paragraph("1.2 Datenklassifikation", h2))
rows = [
    check_row("D-1", "JSON-Dateien nach Stamm-/Bewegungsdaten klassifiziert", "✅", "docs/01_data_classification.md – 13 Eventtypen"),
    check_row("D-2", "JSON-Dateien nach Zieldatenbanken klassifiziert", "✅", "Tabelle mit Primär- und Sekundär-Zielsystem je Event"),
]
story.append(make_table(hdrs, rows))
story.append(Spacer(1, 0.3*cm))

# 1.3 PostgreSQL
story.append(Paragraph("1.3 PostgreSQL Datenmodelle", h2))
rows = [
    check_row("P-1", "Datenmodell ERP mit ER-Modell", "✅", "sql/02_create_erp_tables.sql – 6 Tabellen (suppliers, customers, products, orders, order_items, batches)"),
    check_row("P-2", "Datenmodell WMS mit ER-Modell", "✅", "sql/03_create_wms_tables.sql – 3 Tabellen (warehouse_skus, supply_chain_nodes, node_processings)"),
    check_row("P-3", "Datenmodell TMS mit ER-Modell", "✅", "sql/04_create_tms_tables.sql – 6 Tabellen (carriers, transport_product_refs, shipments, positions, completions, deliveries)"),
    check_row("P-4", "ER-Modell mit Kardinalitäten (Mermaid)", "✅", "docs/03_er_model.md – vollständiges ER-Diagramm mit PKs, FKs, Kardinalitäten"),
]
story.append(make_table(hdrs, rows))
story.append(Spacer(1, 0.3*cm))

# 1.4 MDM
story.append(Paragraph("1.4 Masterdatenmanagement (MDM)", h2))
rows = [
    check_row("M-1", "MDM-Schema entwickelt", "✅", "sql/05_create_mdm_tables.sql – entity_types, golden_records, source_mappings"),
    check_row("M-2", "Inkonsistenz BAN-101 / BAN_101 / ban-101 adressiert", "✅", "docs/04_masterdata_management.md – mdm.resolve_canonical_key() SQL-Funktion"),
    check_row("M-3", "Alle relevanten Entitäten im MDM", "✅", "Produkte, Lieferanten, Kunden, Carrier, Supply-Chain-Knoten"),
]
story.append(make_table(hdrs, rows))
story.append(Spacer(1, 0.3*cm))

# 1.5 Metadaten
story.append(Paragraph("1.5 Metadatenmanagement", h2))
rows = [
    check_row("Me-1", "Metadaten-Schema entwickelt", "✅", "sql/06_create_metadata_tables.sql – systems, tables, columns"),
    check_row("Me-2", "Skalenniveaus für alle Spalten bestimmt", "✅", "docs/05_metadata_management.md – NOMINAL/ORDINAL/INTERVAL/RATIO"),
    check_row("Me-3", "Qualitätsregeln in Metadaten hinterlegt", "✅", "meta.columns.quality_rule für alle wichtigen Spalten"),
    check_row("Me-4", "Skalenniveaus fachlich begründet", "✅", "temperature (INTERVAL), delay_minutes (RATIO), delivery_priority (ORDINAL)"),
]
story.append(make_table(hdrs, rows))
story.append(Spacer(1, 0.3*cm))

# 1.6 DWH
story.append(Paragraph("1.6 Data Warehouse", h2))
rows = [
    check_row("DW-1", "DWH-Schema (Sternschema) entwickelt", "✅", "sql/07_create_dwh_schema.sql – 7 Dimensionen + 1 Faktentabelle"),
    check_row("DW-2", "ETL-Prozess ERP/WMS/TMS → DWH dokumentiert", "✅", "docs/07_dwh_model.md Kap. 5 + docs/12_etl_concept.md Phase 2"),
    check_row("DW-3", "Klare Trennung operative Schemas ≠ DWH", "✅", "Separates dwh-Schema, nur ETL-Schreibzugriff"),
    check_row("DW-4", "Kennzahlen (Measures) definiert", "✅", "quantity, unit_price, total_value, delay_minutes, avg_temperature, num_hops"),
]
story.append(make_table(hdrs, rows))

story.append(PageBreak())

# 1.7 Neo4j
story.append(Paragraph("1.7 Neo4j Graphmodell", h2))
rows = [
    check_row("N-1", "Neo4j Instanz modelliert", "✅", "docs/10_neo4j_graph_model.md + cypher/01_create_graph_model.cypher"),
    check_row("N-2", "Nodes und Beziehungen definiert", "✅", "8 Node-Typen, 12 Relationship-Typen"),
    check_row("N-3", "Begründung für Graphdatenbank", "✅", "SQL vs. Cypher Vergleich für tiefe Pfad-Abfragen"),
    check_row("N-4", "Beispiel-Cypher-Abfragen", "✅", "5 Abfragen inkl. Supply-Chain-Pfad PLANTATION→RETAIL"),
]
story.append(make_table(hdrs, rows))
story.append(Spacer(1, 0.3*cm))

# 1.8 MongoDB
story.append(Paragraph("1.8 MongoDB Eventmodell", h2))
rows = [
    check_row("Mo-1", "MongoDB Instanz modelliert", "✅", "docs/08_mongodb_event_model.md"),
    check_row("Mo-2", "Collections für Events, Tracking, Nodes", "✅", "4 Collections: shipment_events, node_events, batch_tracking, order_events"),
    check_row("Mo-3", "Beispieldokumente und Indizes definiert", "✅", "Vollständige JSON-Beispiele mit Index-Definitionen + TTL-Index"),
    check_row("Mo-4", "Begründung für MongoDB", "✅", "Flexible Schemas, hohe Schreibleistung, embedded Documents"),
]
story.append(make_table(hdrs, rows))
story.append(Spacer(1, 0.3*cm))

# 1.9 MinIO
story.append(Paragraph("1.9 MinIO Dokumentenspeicher", h2))
rows = [
    check_row("Mi-1", "MinIO Instanz für Dokumente modelliert", "✅", "docs/11_minio_document_model.md"),
    check_row("Mi-2", "Bucket-Struktur definiert", "✅", "4 Buckets: invoices, delivery-notes, transport-docs, batch-certificates"),
    check_row("Mi-3", "Begründung Object Store vs. Datenbank", "✅", "BLOBs in DB verlangsamen Backups; S3-kompatible URLs; Horizontal skalierbar"),
    check_row("Mi-4", "Referenzierungsmuster PostgreSQL ↔ MinIO", "✅", "Dokumentreferenz-Tabelle mit Bucket/Objektpfad in PostgreSQL"),
]
story.append(make_table(hdrs, rows))
story.append(Spacer(1, 0.3*cm))

# 1.10 Redis
story.append(Paragraph("1.10 Redis Echtzeitmodell", h2))
rows = [
    check_row("R-1", "Redis Instanz für Echtzeitdaten modelliert", "✅", "docs/09_redis_realtime_model.md"),
    check_row("R-2", "Key-Struktur definiert", "✅", "STRING, HASH, LIST, SORTED SET, COUNTER mit TTL"),
    check_row("R-3", "Begründung für Redis", "✅", "Sub-Millisekunden-Latenz für Shipment-Tracking und GPS-Updates"),
]
story.append(make_table(hdrs, rows))
story.append(Spacer(1, 0.3*cm))

# 1.11 DQ
story.append(Paragraph("1.11 Datenqualitätsmanagement", h2))
rows = [
    check_row("Q-1", "Konkrete DQ-Regeln definiert", "✅", "docs/06_data_quality.md – 6 Dimensionen mit je 2–4 Regeln"),
    check_row("Q-2", "Bezug auf Supply-Chain-Beispiele", "✅", "Kühlkette (PQ-03), Produktcode-Harmonisierung (KQ-01), Zeitlogik (AQ-01/02)"),
    check_row("Q-3", "SQL-Checks implementiert", "✅", "sql/08_data_quality_checks.sql – 20+ Checks über alle 6 Dimensionen"),
    check_row("Q-4", "Python-Validierungsfunktionen", "✅", "docs/06_data_quality.md Kap. 4 + docs/12_etl_concept.md"),
]
story.append(make_table(hdrs, rows))
story.append(Spacer(1, 0.3*cm))

# 1.12 ETL
story.append(Paragraph("1.12 ETL-Konzept und Implementierung", h2))
rows = [
    check_row("E-1", "ETL-Konzept für alle Zielsysteme", "✅", "docs/12_etl_concept.md – Extract, Transform, Load für alle 5 Systeme"),
    check_row("E-2", "Mapping-Tabelle (Quelle → Transformation → Ziel)", "✅", "docs/12_etl_concept.md Kap. 4 – alle 13 Eventtypen gemappt"),
    check_row("E-3", "ERP/WMS/TMS als operative Quellsysteme klar definiert", "✅", "docs/12_etl_concept.md Kap. 3 + Architekturdiagramm"),
    check_row("E-4", "ETL Phase 2: operative Schemas → DWH", "✅", "docs/12_etl_concept.md Kap. 3 mit SQL-ETL-Beispiel"),
]
story.append(make_table(hdrs, rows))

story.append(PageBreak())

# ──────────────────────────────────────────────
# 2. GELIEFERTE ARTEFAKTE
story.append(Paragraph("2. Gelieferte Artefakte", h1))
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
story.append(Spacer(1, 0.2*cm))

artefakte = [
    ["Ordner/Datei", "Inhalt", "Anzahl", "Status"],
    ["shared/erp/", "JSON-Events (Supplier, Customer, Product, Order, Batch)", "50 Dateien", "✅"],
    ["shared/wms/", "JSON-Events (WarehouseSKU, NodeProcessed)", "70 Dateien", "✅"],
    ["shared/tms/", "JSON-Events (Carrier, Transport, GPS, Delivery)", "263 Dateien", "✅"],
    ["docs/", "Markdown-Dokumentation (Architektur, Modelle, Konzepte)", "13 Dateien", "✅"],
    ["sql/", "PostgreSQL DDL-Skripte (Schemas, Tabellen, DWH, DQ)", "8 Dateien", "✅"],
    ["cypher/", "Neo4j Cypher-Skript (Constraints, Stammdaten, Topologie)", "1 Datei", "✅"],
    ["bananasupplychain/etl_load.py", "ETL-Skript – lädt 383 Events in 5 Systeme", "1 Datei", "✅"],
    ["bananasupplychain/generate_documents.py", "MinIO-Dokumentengenerator (PDFs + PostgreSQL-Referenzen)", "1 Datei", "✅"],
    ["bananasupplychain/container/docker-compose.yml", "Docker-Setup (PostgreSQL, MongoDB, Redis, Neo4j, MinIO)", "1 Datei", "✅"],
]
at = simple_table(artefakte, [4.5*cm, 7*cm, 2.5*cm, 2*cm])
story.append(at)
story.append(Spacer(1, 0.5*cm))

# ETL Testergebnisse
story.append(Paragraph("2.1 ETL-Testergebnisse (getestet 2026-05-12)", h2))
story.append(Paragraph("Alle Komponenten wurden gegen die laufenden Docker-Container getestet:", body))
etl_data = [
    ["Komponente", "Test-Ergebnis", "Details"],
    ["PostgreSQL SQL 01–08", "✅ Alle ausgeführt", "6 Schemas, 26 Tabellen inkl. erp.document_references"],
    ["PostgreSQL MDM-Funktion", "✅ Funktioniert", "BAN_101 / ban-101 / BAN-101 → alle → BAN-101"],
    ["PostgreSQL DWH dim_date", "✅ 1095 Zeilen", "2025-01-01 bis 2027-12-31"],
    ["MongoDB Collections", "✅ 4 Collections", "shipment_events (500), node_events (121), batch_tracking (11), order_events (11)"],
    ["Redis Key-Typen", "✅ Alle funktionieren", "STRING, HASH, LIST, SORTED SET, COUNTER"],
    ["Neo4j Graphmodell", "✅ 125 Nodes, 47+ Rels", "Supply-Chain-Pfad PLANTATION→RETAIL in 6 Hops"],
    ["MinIO Buckets + Dokumente", "✅ 4 Buckets", "66 Dokument-Referenzen in PostgreSQL"],
    ["ETL-Skript (etl_load.py)", "✅ Vollständig", "383 Events erfolgreich in alle 5 Systeme geladen"],
]
et = simple_table(etl_data, [4.5*cm, 3*cm, 9*cm])
story.append(et)
story.append(Spacer(1, 0.5*cm))

story.append(Paragraph("2.2 Daten in den Systemen nach ETL", h2))
loaded_data = [
    ["System", "Einträge geladen"],
    ["PostgreSQL", "10 Supplier, 10 Customer, 10 Products, 10 Orders, 10 Batches, 60 Shipments, 118 Positions, 60 Completions, 10 Deliveries"],
    ["MongoDB", "500 shipment_events, 121 node_events, 11 batch_tracking, 11 order_events"],
    ["Redis", "60 Shipment-Status, 118 Position-Updates, 10 Delivery-Status"],
    ["Neo4j", "61 Shipments, 11 Orders, 11 Batches + Stammdaten (Supplier, Customer, Carrier, Nodes)"],
    ["MinIO", "60 Lieferscheine, 6 Rechnungen (66 Referenzen in PostgreSQL)"],
]
lt = simple_table(loaded_data, [3.5*cm, 13*cm])
story.append(lt)

story.append(PageBreak())

# ──────────────────────────────────────────────
# 3. OFFENE PUNKTE
story.append(Paragraph("3. Offene Punkte und Verbesserungspotenzial", h1))
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
story.append(Spacer(1, 0.2*cm))

story.append(Paragraph("3.1 Pflichtaufgaben – Teil 2: Analytics (Deadline: 01.07.2026)", h2))
story.append(Paragraph(
    "Teil 2 des Projekts ist noch vollständig offen. Folgende Aufgaben müssen bis zur Abgabe erledigt werden:",
    body
))

offen_data = [
    ["#", "Aufgabe", "Beschreibung", "Prio"],
    ["A-1", "Deskriptive Statistik", "Kennzahlen aus dem DWH berechnen (Mittelwert, Median, Standardabweichung, Min/Max für delay_minutes, temperature, quantity etc.)", "Hoch"],
    ["A-2", "KPI-Definition", "Mindestens 5 Business-KPIs definieren (z.B. Liefertreue, Ø Transportdauer, Temperaturausreißer-Quote)", "Hoch"],
    ["A-3", "Python-Charts (5 Stück)", "Matplotlib/Seaborn-Visualisierungen: Histogramme, Boxplots, Zeitreihen, Heatmaps o.ä.", "Hoch"],
    ["A-4", "PowerBI-Dashboard", "Mindestens 1 Dashboard mit mehreren Visuals auf Basis der DWH-Daten", "Hoch"],
    ["A-5", "Clusteranalyse", "Kundensegmentierung oder Routen-Cluster (z.B. k-Means auf Shipment-Daten)", "Mittel"],
    ["A-6", "Prognosemodell", "Zeitreihenprognose (z.B. ARIMA oder Prophet für Liefervolumen oder Verzögerungen)", "Mittel"],
    ["A-7", "Abschlussbericht", "Zusammenfassung aller Ergebnisse in einem Bericht (Markdown oder PDF)", "Hoch"],
]
od = Table(offen_data, colWidths=[0.7*cm, 3.5*cm, 9*cm, 1.8*cm], repeatRows=1)
od.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c0392b")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 9),
    ("FONTSIZE", (0, 1), (-1, -1), 8.5),
    ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.HexColor("#fdedec"), colors.HexColor("#fff5f4")]),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(od)
story.append(Spacer(1, 0.5*cm))

story.append(Paragraph("3.2 Verbesserungspotenzial – Teil 1 (optional, aber empfohlen)", h2))

verbesserung_data = [
    ["#", "Bereich", "Was fehlt / was könnte besser sein", "Aufwand"],
    ["V-1", "ETL-Skript", "Fehlerbehandlung: Falls ein JSON-Event ein unbekanntes Format hat, bricht das Skript ab. Try/Except-Blöcke und Logging verbessern die Robustheit.", "Niedrig"],
    ["V-2", "ETL-Skript", "Idempotenz: Mehrfaches Ausführen von etl_load.py erzeugt Duplikate in PostgreSQL. Ein ON CONFLICT DO NOTHING oder Prüfung auf bereits vorhandene Einträge fehlt.", "Mittel"],
    ["V-3", "DWH", "ETL Phase 2 (operative Schemas → DWH) ist konzipiert aber noch nicht als lauffähiges Skript implementiert. Nur SQL-Beispiele dokumentiert.", "Mittel"],
    ["V-4", "Datenqualität", "Die DQ-Checks in sql/08_data_quality_checks.sql laufen manuell. Eine automatisierte Ausführung nach dem ETL (z.B. als Python-Skript) fehlt.", "Mittel"],
    ["V-5", "Neo4j", "Der ETL-Loader befüllt Neo4j nur mit Stammdaten. Tatsächliche Fulfillment-Routen aus den TMS-Daten werden noch nicht automatisch als Graphpfade geladen.", "Mittel"],
    ["V-6", "Dokumentation", "Die Mermaid-Diagramme in den Markdown-Dateien können nicht direkt in PDFs gerendert werden – für Abgaben empfiehlt sich Screenshot oder Export.", "Niedrig"],
    ["V-7", "Git-Workflow", "VS Code erzeugt regelmäßig index.lock-Dateien beim gleichzeitigen Committen. Empfehlung: Git-Operationen nur über Terminal oder Claude Code durchführen.", "Niedrig"],
]
vt = Table(verbesserung_data, colWidths=[0.7*cm, 2.5*cm, 10*cm, 1.8*cm], repeatRows=1)
vt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), ORANGE),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 9),
    ("FONTSIZE", (0, 1), (-1, -1), 8.5),
    ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.HexColor("#fef9e7"), colors.HexColor("#fffde7")]),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
story.append(vt)

story.append(PageBreak())

# ──────────────────────────────────────────────
# 4. ZEITPLAN
story.append(Paragraph("4. Zeitplan bis Abgabe (01.07.2026)", h1))
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
story.append(Spacer(1, 0.2*cm))

timeline_data = [
    ["Zeitraum", "Aufgabe", "Status"],
    ["Bis 13.05.2026", "Teil 1: Infrastruktur, Datenmodelle, ETL, Dokumentation", "✅ Abgeschlossen"],
    ["Mai 2026", "Verbesserungen Teil 1 (ETL-Idempotenz, DQ-Automatisierung)", "⚠️ Optional"],
    ["Jun 2026 – Woche 1", "Deskriptive Statistik & KPI-Berechnung (Python)", "❌ Offen"],
    ["Jun 2026 – Woche 1", "5 Python-Charts erstellen (Matplotlib/Seaborn)", "❌ Offen"],
    ["Jun 2026 – Woche 2", "PowerBI-Dashboard aufbauen", "❌ Offen"],
    ["Jun 2026 – Woche 3", "Clusteranalyse und Prognosemodell", "❌ Offen"],
    ["Jun 2026 – Woche 4", "Abschlussbericht schreiben & finaler Commit", "❌ Offen"],
    ["01.07.2026", "Deadline – Abgabe", "⏳ Frist"],
]
tl = Table(timeline_data, colWidths=[4.5*cm, 8*cm, 4*cm], repeatRows=1)
tl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 9),
    ("FONTSIZE", (0, 1), (-1, -1), 8.5),
    ("BACKGROUND", (0, 1), (-1, 1), LIGHT_GREEN),
    ("BACKGROUND", (0, 2), (-1, 2), LIGHT_ORANGE),
    ("ROWBACKGROUND", (0, 3), (-1, -2), [colors.HexColor("#fdedec"), colors.HexColor("#fff5f4")]),
    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d6eaf8")),
    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(tl)
story.append(Spacer(1, 0.5*cm))

# ──────────────────────────────────────────────
# 5. ZUSAMMENFASSUNG
story.append(Paragraph("5. Zusammenfassung", h1))
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
story.append(Spacer(1, 0.2*cm))

summary_items = [
    ("✅ Komplett erledigt (Teil 1)", GREEN, [
        "Infrastruktur: Docker-Setup mit 5 Datenbanken läuft",
        "Datengenerierung: 383 JSON-Events (ERP 50, WMS 70, TMS 263)",
        "PostgreSQL: 26 Tabellen in 6 Schemas (ERP, WMS, TMS, MDM, Meta, DWH)",
        "ETL-Skript: Alle 383 Events in alle 5 Zielsysteme geladen",
        "Neo4j: 8 Node-Typen, 12 Relationship-Typen, Cypher-Abfragen",
        "MongoDB: 4 Collections, 643 Dokumente",
        "Redis: Vollständige Key-Taxonomie mit TTL",
        "MinIO: 4 Buckets, 66 Dokumentreferenzen in PostgreSQL",
        "Dokumentation: 13 Markdown-Dateien, vollständig",
    ]),
    ("❌ Noch offen (Teil 2 – Analytics)", RED, [
        "Deskriptive Statistik und KPI-Berechnung",
        "5 Python-Visualisierungen (Matplotlib/Seaborn)",
        "PowerBI-Dashboard",
        "Clusteranalyse (z.B. Kundensegmentierung)",
        "Prognosemodell (Zeitreihe)",
        "Abschlussbericht",
    ]),
    ("⚠️ Empfohlene Verbesserungen", ORANGE, [
        "ETL-Idempotenz: ON CONFLICT DO NOTHING in etl_load.py",
        "DQ-Automatisierung: DQ-Checks nach ETL automatisch ausführen",
        "DWH ETL Phase 2: als lauffähiges Python-Skript implementieren",
        "Neo4j ETL: Fulfillment-Routen automatisch aus TMS-Daten laden",
    ]),
]

for title, color, items in summary_items:
    box_data = [[Paragraph(f'<b>{title}</b>', ParagraphStyle("bx", fontSize=10, textColor=colors.white))]]
    bt = Table(box_data, colWidths=[16.5*cm])
    bt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), color),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(bt)
    for item in items:
        story.append(Paragraph(f"• {item}", ParagraphStyle("bullet", parent=body, leftIndent=15, spaceAfter=2)))
    story.append(Spacer(1, 0.3*cm))

story.append(Spacer(1, 0.3*cm))
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
story.append(Spacer(1, 0.2*cm))
story.append(Paragraph(
    f"Erstellt: {date.today()}  |  Gruppe 7  |  Datenmanagement und Analytics M.Sc., SoSe 26  |  TH Lübeck",
    ParagraphStyle("footer", parent=small, alignment=TA_CENTER)
))

doc.build(story)
print(f"PDF erstellt: {OUTPUT}")
