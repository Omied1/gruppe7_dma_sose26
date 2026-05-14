from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

OUTPUT = "/Users/omiedfirouzian/Desktop/DM/gruppe7_dma_sose26/Projektanleitung_Gruppe7_DMA_SoSe26.pdf"

doc = SimpleDocTemplate(
    OUTPUT, pagesize=A4,
    rightMargin=2.2*cm, leftMargin=2.2*cm,
    topMargin=2.5*cm, bottomMargin=2.2*cm,
    title="Projektanleitung – DMA Banana Supply Chain"
)

styles = getSampleStyleSheet()
W = 17.1*cm  # usable width

# ── Stile ────────────────────────────────────────────────────────────────────
DARK   = colors.HexColor("#1a1a2e")
BLUE   = colors.HexColor("#2980b9")
GREEN  = colors.HexColor("#27ae60")
ORANGE = colors.HexColor("#e67e22")
RED    = colors.HexColor("#c0392b")
LGREY  = colors.HexColor("#f4f6f7")
LBLUE  = colors.HexColor("#ebf5fb")
LGREEN = colors.HexColor("#eafaf1")

title_s  = ParagraphStyle("T", parent=styles["Title"],  fontSize=22, textColor=DARK, spaceAfter=4)
sub_s    = ParagraphStyle("S", parent=styles["Normal"], fontSize=13, textColor=BLUE, spaceAfter=10)
h1_s     = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=14, textColor=DARK, spaceBefore=18, spaceAfter=6)
h2_s     = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, textColor=BLUE, spaceBefore=12, spaceAfter=4)
h3_s     = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=10, textColor=colors.HexColor("#0f3460"), spaceBefore=8, spaceAfter=3)
body_s   = ParagraphStyle("B",  parent=styles["Normal"], fontSize=9.5, leading=15, spaceAfter=4, alignment=TA_JUSTIFY)
bull_s   = ParagraphStyle("BU", parent=styles["Normal"], fontSize=9.5, leading=15, leftIndent=14, spaceAfter=2)
code_s   = ParagraphStyle("C",  parent=styles["Code"],   fontSize=8.5, leading=13, leftIndent=10,
                           backColor=colors.HexColor("#f0f0f0"), borderPadding=6)
note_s   = ParagraphStyle("N",  parent=styles["Normal"], fontSize=8.5, leading=13,
                           textColor=colors.HexColor("#555"), leftIndent=10, spaceAfter=4)
foot_s   = ParagraphStyle("F",  parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#888"), alignment=TA_CENTER)
step_s   = ParagraphStyle("ST", parent=styles["Normal"], fontSize=10, textColor=colors.white, leading=14)

def hr(): return HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#cccccc"), spaceAfter=4)
def sp(h=0.25): return Spacer(1, h*cm)

def box(text, bg=LBLUE, fg=DARK, size=9.5):
    p = ParagraphStyle("bx", fontSize=size, textColor=fg, leading=size*1.5)
    t = Table([[Paragraph(text, p)]], colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), bg),
        ("LEFTPADDING", (0,0),(-1,-1), 10),
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
        ("TOPPADDING", (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
    ]))
    return t

def step_box(num, title, desc):
    left = Table([[Paragraph(f"<b>{num}</b>", ParagraphStyle("sn", fontSize=14, textColor=colors.white, alignment=TA_CENTER))]],
                 colWidths=[1*cm])
    left.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),BLUE),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                               ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    right = Table([[Paragraph(f"<b>{title}</b>", ParagraphStyle("st", fontSize=10, textColor=DARK)),
                    Paragraph(desc, ParagraphStyle("sd", fontSize=9, textColor=colors.HexColor("#444"), leading=13))]],
                  colWidths=[4.5*cm, 11.6*cm])
    right.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LBLUE),
                                ("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),6),
                                ("BOTTOMPADDING",(0,0),(-1,-1),6),("VALIGN",(0,0),(-1,-1),"TOP")]))
    outer = Table([[left, right]], colWidths=[1*cm, 16.1*cm])
    outer.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                                ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    return outer

def two_col(left_items, right_items, title_l, title_r):
    def make_cell(title, items, bg):
        content = [Paragraph(f"<b>{title}</b>", ParagraphStyle("ch", fontSize=9.5, textColor=colors.white))]
        for item in items:
            content.append(Paragraph(f"• {item}", ParagraphStyle("ci", fontSize=8.5, textColor=DARK, leading=13, leftIndent=4)))
        t = Table([[p] for p in content], colWidths=[8*cm])
        style = [("BACKGROUND",(0,0),(0,0), BLUE),
                 ("BACKGROUND",(0,1),(-1,-1), bg),
                 ("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),5),
                 ("BOTTOMPADDING",(0,0),(-1,-1),4),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ddd"))]
        t.setStyle(TableStyle(style))
        return t
    outer = Table([[make_cell(title_l, left_items, LGREEN), make_cell(title_r, right_items, colors.HexColor("#fef9e7"))]],
                  colWidths=[8.3*cm, 8.3*cm], hAlign="LEFT")
    outer.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                                ("VALIGN",(0,0),(-1,-1),"TOP"),("INNERGRID",(0,0),(-1,-1),0,colors.white),
                                ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    return outer

def db_card(name, port, farbe, zweck, wofuer, beispiel):
    title_p = ParagraphStyle("dbt", fontSize=10, textColor=colors.white, leading=14)
    body_p  = ParagraphStyle("dbb", fontSize=8.5, textColor=DARK, leading=13)
    rows = [
        [Paragraph(f"<b>{name}</b>  (Port {port})", title_p)],
        [Paragraph(f"<b>Zweck:</b> {zweck}", body_p)],
        [Paragraph(f"<b>Wofür:</b> {wofuer}", body_p)],
        [Paragraph(f"<b>Beispiel:</b> {beispiel}", body_p)],
    ]
    t = Table(rows, colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,0), farbe),
        ("BACKGROUND",(0,1),(-1,-1), LGREY),
        ("LEFTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LINEBELOW",(0,0),(-1,-1),0.3,colors.HexColor("#ccc")),
    ]))
    return t

def file_table(rows):
    data = [["Datei / Ordner", "Was ist das?", "Status"]]
    for r in rows:
        data.append(r)
    t = Table(data, colWidths=[5.5*cm, 9.5*cm, 2.1*cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),8.5),
        ("FONTSIZE",(0,1),(-1,-1),8.5),
        ("ROWBACKGROUND",(0,1),(-1,-1),[colors.white, LGREY]),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ccc")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    return t

# ══════════════════════════════════════════════════════════════════════════════
story = []

# ── TITELSEITE ────────────────────────────────────────────────────────────────
story += [sp(2), Paragraph("Projektanleitung", title_s),
          Paragraph("Banana Supply Chain Datenplattform – Schritt-für-Schritt", sub_s),
          hr(), sp(0.3)]

meta = [["Modul:", "Datenmanagement und Analytics (M.Sc.), SoSe 26 – TH Lübeck"],
        ["Deadline:", "01.07.2026"],
        ["Stand:", "2026-05-13"],
        ["Zweck:", "Erklärt das gesamte Projekt: Aufgabe, Dateien, Datenbanken, Datenfluss und nächste Schritte"]]
mt = Table(meta, colWidths=[3*cm, 14.1*cm])
mt.setStyle(TableStyle([("FONTSIZE",(0,0),(-1,-1),9.5),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
                         ("TEXTCOLOR",(0,0),(0,-1),BLUE),("BOTTOMPADDING",(0,0),(-1,-1),5),
                         ("TOPPADDING",(0,0),(-1,-1),5)]))
story += [mt, sp(0.5)]
story.append(box("<b>Fuer wen ist diese Anleitung?</b> Fuer alle Projektmitglieder, die verstehen wollen, "
                 "was das Projekt macht, wie die Dateien zusammenhaengen und wie man das System starten, "
                 "befuellen und pruefen kann.", LBLUE))
story.append(PageBreak())

# ── INHALTSVERZEICHNIS ────────────────────────────────────────────────────────
story.append(Paragraph("Inhaltsverzeichnis", h1_s))
story.append(hr())
toc = [
    ("1", "Was ist das Projekt?",              "Aufgabenstellung, Use Case, Ziel"),
    ("2", "Wie ist das Projekt aufgebaut?",    "Ordnerstruktur, alle Dateien erklaert"),
    ("3", "Die Infrastruktur (Docker)",        "Welche Datenbanken laufen, Ports, Passwörter"),
    ("4", "Datenfluss – von A nach B",         "Wie Daten erzeugt, verarbeitet und gespeichert werden"),
    ("5", "Die 5 Datenbanken im Detail",       "PostgreSQL, MongoDB, Redis, Neo4j, MinIO"),
    ("6", "Teil 1 – Was wurde erledigt?",      "Alle Artefakte und ihr Status"),
    ("7", "Wie starte ich das Projekt?",       "Schritt-fuer-Schritt-Anleitung zum Ausfuehren"),
    ("8", "Teil 2 – Was kommt noch?",          "Analytics-Aufgaben und naechste Schritte"),
    ("9", "Haeufige Fehler und Loesungen",     "Bekannte Probleme mit Workaround"),
]
for num, title, desc in toc:
    row_data = [[Paragraph(f"<b>{num}</b>", ParagraphStyle("tn", fontSize=10, textColor=BLUE, alignment=TA_CENTER)),
                 Paragraph(f"<b>{title}</b>", ParagraphStyle("tt", fontSize=10, textColor=DARK)),
                 Paragraph(desc, ParagraphStyle("td", fontSize=9, textColor=colors.HexColor("#555")))]]
    t = Table(row_data, colWidths=[0.8*cm, 6.5*cm, 9.8*cm])
    t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("BOTTOMPADDING",(0,0),(-1,-1),4),
                            ("TOPPADDING",(0,0),(-1,-1),4),("LINEBELOW",(0,0),(-1,-1),0.3,colors.HexColor("#eee"))]))
    story.append(t)
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 1. WAS IST DAS PROJEKT?
story.append(Paragraph("1. Was ist das Projekt?", h1_s))
story.append(hr())
story.append(Paragraph(
    "Das Projekt ist eine Studienleistung im Modul <b>Datenmanagement und Analytics (M.Sc.)</b>. "
    "Ziel ist es, eine vollstaendige Datenplattform fuer eine <b>Banana Supply Chain</b> zu entwerfen, "
    "zu implementieren und zu dokumentieren.", body_s))
story.append(sp(0.3))

story.append(Paragraph("1.1 Der Use Case – Banana Supply Chain", h2_s))
story.append(Paragraph(
    "Eine Bananenfarm in Ghana (Lieferant) verkauft Bananen an europaeische Supermaerkte (Kunden). "
    "Zwischen Ernte und Verkauf durchlaufen die Bananen mehrere Stationen:", body_s))

stationen = [
    ["Station", "Beschreibung", "System"],
    ["Plantage (Ghana)", "Ernte, Batches bilden, Qualitaetskontrolle", "ERP"],
    ["Sammelzentrum", "Bananen von Plantagen buendeln", "WMS"],
    ["Qualitaetskontrolle", "Temperatur und Qualitaet pruefen", "WMS"],
    ["Afrika Kuehlhaus", "Tiefkuehlung vor Seetransport", "WMS"],
    ["Seetransport (Container)", "GPS-Tracking, Temperaturueberwachung", "TMS"],
    ["Europa Kuehlhaus", "Ankunft Europa, Zwischenlager", "WMS"],
    ["Zentrallager (DE)", "Verteilung auf Regionen", "WMS"],
    ["Retail Store", "Supermarkt, Abgabe an Kunden", "ERP + TMS"],
]
st = Table(stationen, colWidths=[4.5*cm, 8.5*cm, 4.1*cm], repeatRows=1)
st.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
    ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8.5),
    ("ROWBACKGROUND",(0,1),(-1,-1),[colors.white, LGREY]),
    ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ccc")),
    ("LEFTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
]))
story += [st, sp(0.4)]

story.append(Paragraph("1.2 Die Aufgabenstellung (Zusammenfassung)", h2_s))
story.append(box(
    "<b>Teil 1 – Datenmanagement (aktuell):</b> Infrastruktur aufsetzen, Daten klassifizieren, "
    "Datenbanken modellieren, ETL implementieren, Qualitaet sichern. "
    "<b>Teil 2 – Analytics (noch offen):</b> KPIs berechnen, Python-Charts erstellen, "
    "PowerBI-Dashboard, Clustering, Absatzprognose.", LGREEN))
story.append(sp(0.3))
story.append(Paragraph(
    "Die vollstaendige Aufgabenstellung steht in <b>Aufgabenstellung.pdf</b> im Projektroot. "
    "Diese Datei ist die primaere Quelle – bei Unklarheiten immer dort nachschauen.", body_s))
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 2. PROJEKTSTRUKTUR
story.append(Paragraph("2. Wie ist das Projekt aufgebaut?", h1_s))
story.append(hr())
story.append(Paragraph(
    "Der gesamte Projektordner liegt unter <b>gruppe7_dma_sose26/</b>. "
    "Hier ist eine Uebersicht aller wichtigen Ordner und Dateien:", body_s))
story.append(sp(0.3))

story.append(Paragraph("2.1 Hauptordner auf einen Blick", h2_s))
ordner = [
    ["Ordner / Datei", "Was steckt darin?"],
    ["bananasupplychain/", "Das Herzstuck: Docker-Setup, ETL-Skript, Datengenerator"],
    ["shared/erp/", "50 JSON-Dateien vom ERP-System (Lieferanten, Kunden, Produkte, Bestellungen)"],
    ["shared/wms/", "70 JSON-Dateien vom WMS-System (Lager, Stationen)"],
    ["shared/tms/", "263 JSON-Dateien vom TMS-System (Carrier, Transporte, GPS, Lieferungen)"],
    ["docs/", "13 Markdown-Dokumente – die gesamte fachliche Dokumentation"],
    ["sql/", "8 SQL-Dateien – PostgreSQL-Schemas, Tabellen, DWH, Qualitaetschecks"],
    ["cypher/", "1 Cypher-Datei – das Neo4j-Graphmodell"],
    ["Aufgabenstellung.pdf", "Die originale Pruefungsaufgabe – immer zuerst lesen"],
    ["PROJECT_STATUS.md", "Aktueller Projektstatus (was ist fertig, was fehlt)"],
]
ot = Table(ordner, colWidths=[5.5*cm, 11.6*cm], repeatRows=1)
ot.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
    ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8.5),
    ("ROWBACKGROUND",(0,1),(-1,-1),[colors.white, LGREY]),
    ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ccc")),
    ("LEFTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
]))
story += [ot, sp(0.5)]

story.append(Paragraph("2.2 Alle wichtigen Dateien erklaert", h2_s))
story.append(Paragraph("<b>Python-Skripte:</b>", h3_s))
story.append(file_table([
    ["test_data_generator.py", "Erzeugt die JSON-Dateien in shared/. Muss einmalig ausgefuehrt werden. Simuliert ERP, WMS und TMS.", "getestet"],
    ["etl_load.py", "Liest die JSON-Dateien und laedt sie in alle 5 Datenbanken. Das Kernstuck des Projekts.", "getestet"],
    ["generate_documents.py", "Erstellt PDF-Dokumente (Lieferscheine, Rechnungen) in MinIO und speichert Referenzen in PostgreSQL.", "getestet"],
    ["reorgFolders.py", "Hilfsskript zum Reorganisieren der Ordnerstruktur.", "erstellt"],
]))
story.append(sp(0.3))

story.append(Paragraph("<b>SQL-Dateien (Reihenfolge beachten!):</b>", h3_s))
story.append(file_table([
    ["sql/01_create_schemas.sql", "Erstellt die 6 PostgreSQL-Schemas: erp, wms, tms, mdm, meta, dwh", "getestet"],
    ["sql/02_create_erp_tables.sql", "Erstellt die 6 ERP-Tabellen (suppliers, customers, products, orders, order_items, batches)", "getestet"],
    ["sql/03_create_wms_tables.sql", "Erstellt die 3 WMS-Tabellen + 7 Supply-Chain-Knoten als Stammdaten", "getestet"],
    ["sql/04_create_tms_tables.sql", "Erstellt die 6 TMS-Tabellen (carriers, shipments, positions usw.)", "getestet"],
    ["sql/05_create_mdm_tables.sql", "Erstellt das MDM-System (Golden Records, Source Mappings, Hilfsfunktion)", "getestet"],
    ["sql/06_create_metadata_tables.sql", "Erstellt den Metadaten-Katalog (Skalenniveaus, Qualitaetsregeln)", "getestet"],
    ["sql/07_create_dwh_schema.sql", "Erstellt das Sternschema fuer Analytics (7 Dimensionen + 1 Faktentabelle)", "getestet"],
    ["sql/08_data_quality_checks.sql", "20+ SQL-Abfragen zur Datenpruefung (Vollstaendigkeit, Konsistenz usw.)", "erstellt"],
]))
story.append(sp(0.3))

story.append(Paragraph("<b>Dokumentation (docs/):</b>", h3_s))
story.append(file_table([
    ["docs/01_data_classification.md", "Klassifikation aller 13 Eventtypen (Stamm-/Bewegungs-/Ereignisdaten)", "abgabefaehig"],
    ["docs/02_target_architecture.md", "Architekturdiagramm der gesamten Plattform", "abgabefaehig"],
    ["docs/03_er_model.md", "Entity-Relationship-Modell mit Mermaid (PKs, FKs, Kardinalitaeten)", "abgabefaehig"],
    ["docs/04_masterdata_management.md", "MDM-Konzept: wie BAN-101/BAN_101/ban-101 harmonisiert werden", "abgabefaehig"],
    ["docs/05_metadata_management.md", "Metadaten-Konzept: Skalenniveaus fuer alle Kernspalten", "abgabefaehig"],
    ["docs/06_data_quality.md", "6 Datenqualitaets-Dimensionen mit konkreten Regeln", "abgabefaehig"],
    ["docs/07_dwh_model.md", "Data-Warehouse-Modell: Sternschema, Measures, ETL-Konzept", "abgabefaehig"],
    ["docs/08_mongodb_event_model.md", "MongoDB: 4 Collections fuer Event-Daten", "abgabefaehig"],
    ["docs/09_redis_realtime_model.md", "Redis: Key-Struktur fuer Echtzeit-Tracking", "abgabefaehig"],
    ["docs/10_neo4j_graph_model.md", "Neo4j: Graphmodell mit 8 Node-Typen und 12 Beziehungen", "abgabefaehig"],
    ["docs/11_minio_document_model.md", "MinIO: 4 Buckets fuer Lieferscheine, Rechnungen, Dokumente", "abgabefaehig"],
    ["docs/12_etl_concept.md", "ETL-Konzept: Mapping-Tabelle fuer alle 13 Eventtypen", "abgabefaehig"],
]))
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 3. INFRASTRUKTUR
story.append(Paragraph("3. Die Infrastruktur (Docker)", h1_s))
story.append(hr())
story.append(Paragraph(
    "Das Projekt laeuft vollstaendig in Docker-Containern. Die Konfiguration liegt in "
    "<b>bananasupplychain/container/docker-compose.yml</b>. "
    "Mit einem einzigen Befehl starten alle 5 Datenbanken:", body_s))
story.append(sp(0.2))
story.append(box("cd bananasupplychain/container\ndocker-compose up -d", colors.HexColor("#2c3e50"),
                 colors.HexColor("#a8d8ea"), 9))
story.append(sp(0.4))

story.append(Paragraph("3.1 Die laufenden Dienste", h2_s))
for name, port, farbe, zweck, wofuer, beispiel in [
    ("PostgreSQL", "5432", colors.HexColor("#336791"),
     "Relationale Datenbank fuer strukturierte Stamm- und Bewegungsdaten",
     "ERP-Tabellen (suppliers, orders), WMS, TMS, MDM, Metadaten, DWH",
     "SELECT * FROM erp.suppliers;  →  zeigt alle Lieferanten"),
    ("MongoDB", "27017", colors.HexColor("#4db33d"),
     "Dokumentendatenbank fuer Events mit flexibler Struktur",
     "Shipment-Events, GPS-Updates, Node-Events, Batch-Tracking",
     "db.shipment_events.find({shipment_id: 'SHIP-001'})"),
    ("Redis", "6379", colors.HexColor("#dc382d"),
     "In-Memory-Cache fuer Echtzeit-Daten mit sub-Millisekunden-Latenz",
     "Aktueller Shipment-Status, GPS-Position, aktive Transporte zaehlen",
     "GET shipment:SHIP-001:status  →  'IN_TRANSIT'"),
    ("Neo4j", "7474 (Browser) / 7687 (API)", colors.HexColor("#008cc1"),
     "Graphdatenbank fuer Beziehungsnetzwerke und Pfadabfragen",
     "Supply-Chain-Routen, wer liefert an wen, kuerzeste Pfade",
     "MATCH p=(s:Supplier)-[*]->(c:Customer) RETURN p"),
    ("MinIO", "9000 (API) / 9001 (Web)", colors.HexColor("#c72a38"),
     "S3-kompatibler Object-Store fuer Binaerdokumente",
     "PDFs: Lieferscheine, Rechnungen, Transportdokumente, Batch-Zertifikate",
     "Browser: http://localhost:9001  (admin / password)"),
]:
    story.append(db_card(name, port, farbe, zweck, wofuer, beispiel))
    story.append(sp(0.2))

story.append(sp(0.3))
story.append(box(
    "<b>Zugangsdaten (lokal):</b>  User: user | Password: password | Database: logistics  "
    "(PostgreSQL)  |  Neo4j: neo4j / password  |  MinIO: admin / password",
    colors.HexColor("#fef9e7")))
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 4. DATENFLUSS
story.append(Paragraph("4. Datenfluss – von A nach B", h1_s))
story.append(hr())
story.append(Paragraph(
    "Hier erklaert, wie Daten von der Simulation bis in die Datenbanken fliessen – "
    "in vier klar getrennten Phasen:", body_s))
story.append(sp(0.3))

for num, title, desc in [
    ("1", "Datengenerator (Simulation)",
     "test_data_generator.py laeuft einmalig und erzeugt 383 JSON-Dateien in shared/. "
     "Er simuliert drei Quellsysteme: ERP (50 Dateien), WMS (70 Dateien), TMS (263 Dateien). "
     "Absichtlich eingebaute Inkonsistenz: Produktcode BAN-101 heisst in WMS 'BAN_101' und in TMS 'ban-101'."),
    ("2", "Extract – JSON lesen und validieren",
     "etl_load.py liest alle JSON-Dateien mit glob.glob(). Jede Datei wird geoeffnet, "
     "der Eventtyp identifiziert (z.B. 'SupplierCreated', 'ShipmentStarted') und "
     "die Pflichtfelder validiert. Ungueltige Dateien werden uebersprungen."),
    ("3", "Transform – Harmonisieren und konvertieren",
     "Schluesselproblem: BAN_101 (WMS) muss zu BAN-101 (kanonisch) werden. "
     "Die Funktion normalize_key() macht: strip().lower().replace('_','-').upper(). "
     "Ausserdem: Strings zu Zahlen konvertieren, Timestamps vereinheitlichen, "
     "fehlende Felder mit None befuellen."),
    ("4", "Load – In alle 5 Systeme laden",
     "Jedes Event geht in das passende Zielsystem: Stammdaten (Supplier, Customer) → PostgreSQL erp-Schema. "
     "GPS-Events → MongoDB shipment_events + Redis Echtzeit-Key. "
     "Alle Shipments → Neo4j als Graph-Knoten. "
     "Dokumente → MinIO mit Referenz in PostgreSQL erp.document_references."),
]:
    story.append(step_box(num, title, desc))
    story.append(sp(0.15))

story.append(sp(0.4))
story.append(Paragraph("4.1 Welches Event geht wohin?", h2_s))
mapping = [
    ["Eventtyp", "Quellsystem", "Primaer-Ziel", "Sekundaer-Ziel"],
    ["SupplierCreated", "ERP", "PostgreSQL erp.suppliers", "Neo4j Supplier-Node"],
    ["CustomerCreated", "ERP", "PostgreSQL erp.customers", "Neo4j Customer-Node"],
    ["ProductCreated", "ERP", "PostgreSQL erp.products", "MDM Golden Record"],
    ["OrderCreated", "ERP", "PostgreSQL erp.orders", "MongoDB order_events"],
    ["BatchCreated", "ERP", "PostgreSQL erp.batches", "Neo4j Batch-Node"],
    ["WarehouseSKUCreated", "WMS", "PostgreSQL wms.warehouse_skus", "MDM Mapping (BAN_101)"],
    ["NodeProcessed", "WMS", "PostgreSQL wms.node_processings", "MongoDB node_events"],
    ["CarrierCreated", "TMS", "PostgreSQL tms.carriers", "Neo4j Carrier-Node"],
    ["TransportProductRefCreated", "TMS", "PostgreSQL tms.transport_product_refs", "MDM Mapping (ban-101)"],
    ["ShipmentStarted", "TMS", "PostgreSQL tms.shipments", "MongoDB shipment_events, Neo4j"],
    ["ShipmentPositionUpdated", "TMS", "Redis (Echtzeit)", "MongoDB shipment_events"],
    ["TransportCompleted", "TMS", "PostgreSQL tms.completions", "MongoDB update"],
    ["DeliveryCompleted", "TMS", "PostgreSQL tms.deliveries", "MinIO Lieferschein"],
]
mt2 = Table(mapping, colWidths=[4.3*cm, 2.5*cm, 5.5*cm, 4.8*cm], repeatRows=1)
mt2.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
    ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
    ("ROWBACKGROUND",(0,1),(-1,-1),[colors.white, LGREY]),
    ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ccc")),
    ("LEFTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
]))
story.append(mt2)
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 5. DATENBANKEN IM DETAIL
story.append(Paragraph("5. Die 5 Datenbanken im Detail", h1_s))
story.append(hr())

story.append(Paragraph("5.1 PostgreSQL – der operative Kern", h2_s))
story.append(Paragraph(
    "PostgreSQL ist die zentrale relationale Datenbank. Sie enthaelt 6 Schemas, "
    "26 Tabellen und eine DWH-Schicht. Reihenfolge beim Ausfuehren wichtig:", body_s))
schemas = [
    ["Schema", "Enthaelt", "Tabellen"],
    ["erp", "Enterprise Resource Planning – Stammdaten und Bestellungen", "suppliers, customers, products, orders, order_items, batches, document_references"],
    ["wms", "Warehouse Management – Lager und Stationsverarbeitung", "warehouse_skus, supply_chain_nodes (7 Knoten vorbefuellt), node_processings"],
    ["tms", "Transport Management – Carrier und Transporte", "carriers, transport_product_refs, shipments, positions, completions, deliveries"],
    ["mdm", "Master Data Management – Schluesselharmonisierung", "entity_types, golden_records, source_mappings + Funktion resolve_canonical_key()"],
    ["meta", "Metadaten-Katalog – Skalenniveaus und Qualitaetsregeln", "systems, tables, columns (mit quality_rule und scale_level)"],
    ["dwh", "Data Warehouse – Sternschema fuer Analytics", "dim_date (1095 Zeilen), dim_supplier, dim_customer, dim_product, dim_carrier, dim_route, dim_node, fact_fulfillment"],
]
st = Table(schemas, colWidths=[1.8*cm, 6*cm, 9.3*cm], repeatRows=1)
st.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#336791")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
    ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
    ("ROWBACKGROUND",(0,1),(-1,-1),[colors.white, LGREY]),
    ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ccc")),
    ("VALIGN",(0,0),(-1,-1),"TOP"),
    ("LEFTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
]))
story += [st, sp(0.5)]

story.append(Paragraph("5.2 MDM – das Schluesselproblem", h2_s))
story.append(box(
    "<b>Problem:</b> Das Produkt 'Cavendish Bananen' hat in ERP den Code BAN-101, "
    "in WMS den Code BAN_101 und in TMS den Code ban-101. Ohne MDM koennen diese Systeme "
    "nicht miteinander kommunizieren – ein JOIN auf Produktebene wuerde nichts finden.\n\n"
    "<b>Loesung:</b> Die Funktion mdm.resolve_canonical_key('BAN_101', 'WMS') "
    "gibt immer BAN-101 (den kanonischen ERP-Schluessel) zurueck.",
    LGREEN))
story.append(sp(0.4))

story.append(Paragraph("5.3 MongoDB – Events mit flexibler Struktur", h2_s))
story.append(Paragraph(
    "MongoDB speichert Events als JSON-Dokumente. Der Vorteil: Jeder Eventtyp hat andere Felder "
    "– GPS-Events haben Koordinaten, Delivery-Events haben Empfaenger. In PostgreSQL muesste man "
    "fuer jeden Typ eine eigene Tabelle anlegen oder mit NULL-Spalten arbeiten. "
    "MongoDB loest das elegant durch flexible Schemas.", body_s))
story.append(Paragraph("4 Collections: <b>shipment_events</b> (500 Dokumente), <b>node_events</b> (121), "
                        "<b>batch_tracking</b> (11), <b>order_events</b> (11)", note_s))
story.append(sp(0.3))

story.append(Paragraph("5.4 Redis – Echtzeit in Millisekunden", h2_s))
story.append(Paragraph(
    "Redis speichert Daten im Arbeitsspeicher (RAM). Daher ist er 100x schneller als PostgreSQL "
    "fuer Lese-Anfragen. Typische Anfrage: 'Wo ist Shipment SHIP-001 gerade?' "
    "Redis antwortet in < 1 ms. Konfiguration: max 256 MB, aelteste Keys werden automatisch geloescht (allkeys-lru).", body_s))
story.append(sp(0.3))

story.append(Paragraph("5.5 Neo4j – Beziehungen als Graph", h2_s))
story.append(Paragraph(
    "Neo4j modelliert die Supply Chain als Netzwerk aus Knoten (Supplier, Customer, Carrier, "
    "Batch etc.) und Beziehungen (SUPPLIES, TRANSPORTS, PROCESSED_AT). "
    "Die Frage 'Welchen Weg hat Batch B-001 durch die Supply Chain genommen?' "
    "beantwortet Neo4j mit einer einzigen Cypher-Zeile. In SQL brauchte man 6+ JOINs.", body_s))
story.append(Paragraph("Ergebnis nach ETL: 125 Nodes, 47+ Relationships. "
                        "Pfad PLANTATION -> RETAIL: 6 Hops.", note_s))
story.append(sp(0.3))

story.append(Paragraph("5.6 MinIO – Dokumente ausserhalb der Datenbank", h2_s))
story.append(Paragraph(
    "PDFs (Lieferscheine, Rechnungen) gehoeren nicht in eine relationale Datenbank – "
    "das wuerde Backups und Replikation verlangsamen. MinIO ist ein S3-kompatibler Object Store: "
    "Die PDFs liegen in Buckets, PostgreSQL speichert nur den Verweis (Bucket + Dateiname). "
    "Web-Interface unter http://localhost:9001", body_s))
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 6. WAS WURDE ERLEDIGT?
story.append(Paragraph("6. Teil 1 – Was wurde erledigt?", h1_s))
story.append(hr())
story.append(box(
    "Alle Pflichtanforderungen aus Teil 1 der Aufgabenstellung sind erfuellt. "
    "35 von 35 Anforderungen haben Status abgabefaehig oder getestet.",
    LGREEN))
story.append(sp(0.3))

bereiche = [
    ("Infrastruktur", ["Docker: 5 Container laufen (PostgreSQL, MongoDB, Redis, Neo4j, MinIO)",
                       "Datengenerator: 383 JSON-Events erzeugt (ERP 50, WMS 70, TMS 263)",
                       "GitLab-Repo eingerichtet und befuellt"]),
    ("Datenmodelle", ["PostgreSQL: 26 Tabellen in 6 Schemas",
                       "ER-Modell mit PKs, FKs, Kardinalitaeten (Mermaid)",
                       "MDM: Golden Records fuer Produkte, Carrier, Supplier"]),
    ("Spezial-Systeme", ["MongoDB: 4 Collections, 643 Dokumente",
                          "Redis: STRING, HASH, SORTED SET, COUNTER – alle getestet",
                          "Neo4j: 125 Nodes, Pfad PLANTATION->RETAIL in 6 Hops",
                          "MinIO: 4 Buckets, 66 Dokument-Referenzen"]),
    ("ETL & Qualitaet", ["etl_load.py: 383 Events vollstaendig geladen",
                           "20+ DQ-Checks fuer 6 Qualitaets-Dimensionen",
                           "Metadaten-Katalog mit Skalenniveaus fuer alle Kernspalten"]),
]
for titel, items in bereiche:
    story.append(Paragraph(titel, h2_s))
    for item in items:
        story.append(Paragraph(f"✓  {item}", ParagraphStyle("ok", fontSize=9.5, leftIndent=10,
                                                              textColor=GREEN, leading=14, spaceAfter=2)))
    story.append(sp(0.2))
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 7. WIE STARTE ICH DAS PROJEKT?
story.append(Paragraph("7. Wie starte ich das Projekt?", h1_s))
story.append(hr())
story.append(Paragraph(
    "Vollstaendige Anleitung zum Ausfuehren aller Projektkomponenten auf einem neuen Rechner:", body_s))
story.append(sp(0.3))

for num, title, desc in [
    ("1", "Voraussetzungen pruefen",
     "Docker Desktop muss installiert und gestartet sein. "
     "Python 3.10+ muss installiert sein. "
     "Befehl: docker --version && python3 --version"),
    ("2", "Abhaengigkeiten installieren",
     "pip install psycopg2-binary pymongo redis neo4j minio\n"
     "Diese Pakete benoetigt etl_load.py fuer alle Datenbankverbindungen."),
    ("3", "Docker-Container starten",
     "cd bananasupplychain/container\n"
     "docker-compose up -d\n"
     "Warten bis alle 5 Container den Status 'healthy' haben. "
     "Pruefen: docker ps"),
    ("4", "SQL-Schemas anlegen (Reihenfolge 01 bis 08)",
     "In psql oder einem SQL-Tool (z.B. DBeaver) verbinden:\n"
     "Host: localhost | Port: 5432 | DB: logistics | User: user | PW: password\n"
     "Dann ausfuehren: sql/01... bis sql/08... in dieser Reihenfolge."),
    ("5", "Datengenerator ausfuehren (falls shared/ noch leer)",
     "cd bananasupplychain\n"
     "python3 test_data_generator.py\n"
     "Erzeugt: 50 ERP + 70 WMS + 263 TMS JSON-Dateien in shared/"),
    ("6", "ETL-Skript ausfuehren",
     "cd bananasupplychain\n"
     "python3 etl_load.py\n"
     "Laedt alle 383 Events in PostgreSQL, MongoDB, Redis, Neo4j und MinIO.\n"
     "Erwartete Ausgabe: Zusammenfassung mit Anzahl geladener Datensaetze pro System."),
    ("7", "Dokumente generieren (MinIO befuellen)",
     "python3 generate_documents.py\n"
     "Erstellt 60 Lieferscheine + 6 Rechnungen als PDFs in MinIO.\n"
     "Speichert 66 Referenzen in PostgreSQL erp.document_references."),
    ("8", "Ergebnis pruefen",
     "PostgreSQL: SELECT COUNT(*) FROM erp.suppliers;  -- erwartet: 10\n"
     "MongoDB: db.shipment_events.countDocuments()  -- erwartet: 500\n"
     "Redis: KEYS shipment:*  -- zeigt alle Shipment-Keys\n"
     "Neo4j Browser: http://localhost:7474  -- MATCH (n) RETURN COUNT(n)\n"
     "MinIO: http://localhost:9001  -- Buckets mit Dokumenten sehen"),
]:
    story.append(step_box(num, title, desc))
    story.append(sp(0.2))

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 8. TEIL 2 – ANALYTICS
story.append(Paragraph("8. Teil 2 – Was kommt noch?", h1_s))
story.append(hr())
story.append(box(
    "Teil 2 (Analytics) ist vollstaendig offen. Deadline: 01.07.2026. "
    "Voraussetzung: ETL Phase 2 muss zuerst implementiert werden (PostgreSQL -> DWH befuellen).",
    colors.HexColor("#fdedec")))
story.append(sp(0.3))

analytics = [
    ["#", "Aufgabe", "Beschreibung", "Priori."],
    ["A-0", "ETL Phase 2 (Blocker)", "Python-Skript: operative Schemas -> DWH-Schema befuellen. Ohne das koennen A-1 bis A-6 nicht starten.", "Hoch"],
    ["A-1", "Deskriptive Statistik", "Min, Max, Mittelwert, Median, Std fuer delay_minutes, temperature, quantity. Python + pandas.", "Hoch"],
    ["A-2", "KPI-Berechnung", "5 KPIs: Liefertreue (%), Transportdauer (Tage), Temperaturausreisser-Quote, Bestellwert, Batchqualitaet.", "Hoch"],
    ["A-3", "5 Python-Charts", "Matplotlib/Seaborn: Histogramm, Zeitreihe, Boxplot, Heatmap, Liniendiagramm. Je Chart: fachliche Interpretation.", "Hoch"],
    ["A-4", "PowerBI-Dashboard", "Verbindung zu PostgreSQL DWH. KPI-Cards, Zeitreihe, Slicer fuer Datum/Carrier/Route.", "Hoch"],
    ["A-5", "Clustering", "k-Means auf Kunden (Bestellhaeufigkeit, Bestellwert, Verzoegerung). Elbow-Methode fuer k.", "Mittel"],
    ["A-6", "Absatzprognose", "ARIMA oder Prophet: Bestellvolumen pro Woche prognostizieren. RMSE/MAE angeben.", "Mittel"],
    ["A-7", "Abschlussbericht", "Zusammenfassung Teil 1 + Teil 2 in einem Dokument.", "Hoch"],
]
at = Table(analytics, colWidths=[1.2*cm, 3.8*cm, 9.5*cm, 1.9*cm], repeatRows=1)
at.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),RED),("TEXTCOLOR",(0,0),(-1,0),colors.white),
    ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8.5),
    ("BACKGROUND",(0,1),(-1,1),colors.HexColor("#fde8e8")),
    ("ROWBACKGROUND",(0,2),(-1,-1),[colors.white, LGREY]),
    ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ccc")),
    ("VALIGN",(0,0),(-1,-1),"TOP"),
    ("LEFTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
]))
story.append(at)
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# 9. FEHLER UND LOESUNGEN
story.append(Paragraph("9. Haeufige Fehler und Loesungen", h1_s))
story.append(hr())
story.append(sp(0.2))

fehler = [
    ("F-1", RED, "git: Unable to create index.lock",
     "VS Code und Terminal versuchen gleichzeitig auf git zuzugreifen.",
     "rm .git/index.lock\nDanach normal committen."),
    ("F-2", ORANGE, "etl_load.py: Duplicate key violation in PostgreSQL",
     "Das ETL-Skript wurde mehrfach ausgefuehrt. ON CONFLICT DO NOTHING fehlt noch.",
     "Datenbank zuruecksetzen:\npsql -h localhost -U user -d logistics -c 'DROP SCHEMA erp CASCADE;'\n"
     "Dann SQL 01-08 neu ausfuehren, danach etl_load.py einmal laufen lassen."),
    ("F-3", ORANGE, "pip install schlaegt fehl (psycopg2)",
     "Auf macOS fehlen oft PostgreSQL-Bibliotheken.",
     "pip install psycopg2-binary  (nicht psycopg2!)"),
    ("F-4", ORANGE, "Neo4j: ServiceUnavailable",
     "Neo4j braucht nach docker-compose up ca. 30-60 Sekunden zum Starten.",
     "docker logs neo4j  -- auf 'Started.' warten, dann etl_load.py nochmal starten."),
    ("F-5", colors.HexColor("#555"), "MinIO: NoSuchBucket",
     "generate_documents.py wurde vor etl_load.py ausgefuehrt. ETL legt Buckets an.",
     "Reihenfolge: 1. etl_load.py  2. generate_documents.py"),
]

for fid, farbe, titel, ursache, loesung in fehler:
    rows = [
        [Paragraph(f"<b>{fid}: {titel}</b>", ParagraphStyle("fh", fontSize=9.5, textColor=colors.white))],
        [Paragraph(f"<b>Ursache:</b> {ursache}", ParagraphStyle("fu", fontSize=8.5, textColor=DARK, leading=13))],
        [Paragraph(f"<b>Loesung:</b>\n{loesung}", ParagraphStyle("fl", fontSize=8.5, textColor=colors.HexColor("#006600"), leading=13, fontName="Courier"))],
    ]
    ft = Table(rows, colWidths=[W])
    ft.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,0), farbe),
        ("BACKGROUND",(0,1),(-1,-1), LGREY),
        ("LEFTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LINEBELOW",(0,0),(-1,-1),0.3,colors.HexColor("#ccc")),
    ]))
    story.append(ft)
    story.append(sp(0.25))

story.append(sp(0.5))
story.append(hr())
story.append(Paragraph(
    "Projektanleitung Gruppe 7  |  Datenmanagement und Analytics M.Sc., SoSe 26  |  TH Luebeck  |  Stand: 2026-05-13",
    foot_s))

# ── Bauen ─────────────────────────────────────────────────────────────────────
doc.build(story)
print(f"PDF erstellt: {OUTPUT}")
