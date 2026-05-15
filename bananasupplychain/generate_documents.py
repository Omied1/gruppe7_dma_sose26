"""
generate_documents.py – Erzeugt echte PDFs für die Banana Supply Chain
und lädt sie in MinIO hoch.

Dokument-Typen:
  - Lieferschein     (delivery-notes)   → für jeden TransportStarted-Event
  - Rechnung         (invoices)         → für jeden erfolgreichen DeliveryCompleted-Event
  - Qualitätszertifikat (batch-certificates) → für jeden NodeProcessed am QUALITY_CONTROL

Ausführung:
    cd bananasupplychain
    python3 generate_documents.py
"""

import json
import glob
import os
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from minio import Minio
import psycopg2

# ── Konfiguration ─────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
SHARED    = os.path.join(BASE_DIR, "..", "shared")

MINIO_EP  = "localhost:9000"
MINIO_KEY = "admin"
MINIO_SEC = "password"
PG_DSN    = "host=localhost port=5432 dbname=logistics user=user password=password"

# Farben (Banana-Supply-Chain Branding)
YELLOW    = HexColor("#F5C518")
DARK_GRAY = HexColor("#2C2C2C")
MID_GRAY  = HexColor("#6C6C6C")
LIGHT_BG  = HexColor("#FAFAFA")
TABLE_HDR = HexColor("#3A3A3A")

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────
def normalize_key(key: str) -> str:
    return key.strip().lower().replace("_", "-").upper()

def fmt_ts(ts: str) -> str:
    if not ts:
        return "–"
    try:
        return datetime.fromisoformat(ts.replace("Z", "")).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return ts

def load_events(system: str) -> list:
    path   = os.path.join(SHARED, system, "*.json")
    events = []
    for f in sorted(glob.glob(path)):
        try:
            events.append(json.load(open(f)))
        except Exception:
            pass
    return events

def base_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("DocTitle",
        fontSize=20, textColor=DARK_GRAY, spaceAfter=4,
        fontName="Helvetica-Bold", alignment=TA_LEFT))
    styles.add(ParagraphStyle("DocSubtitle",
        fontSize=10, textColor=MID_GRAY, spaceAfter=2,
        fontName="Helvetica", alignment=TA_LEFT))
    styles.add(ParagraphStyle("SectionHead",
        fontSize=10, textColor=white, fontName="Helvetica-Bold",
        alignment=TA_LEFT))
    styles.add(ParagraphStyle("FieldLabel",
        fontSize=8, textColor=MID_GRAY, fontName="Helvetica"))
    styles.add(ParagraphStyle("FieldValue",
        fontSize=9, textColor=DARK_GRAY, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle("Footer",
        fontSize=7, textColor=MID_GRAY, fontName="Helvetica",
        alignment=TA_CENTER))
    return styles

def header_table(doc_type: str, doc_id: str, date_str: str, styles):
    """Kopfzeile mit Firmenlogo-Ersatz + Dokumenttitel."""
    logo_para = Paragraph(
        "<b><font color='#F5C518'>●</font> Banana Supply Chain AG</b>",
        ParagraphStyle("Logo", fontSize=13, fontName="Helvetica-Bold",
                       textColor=DARK_GRAY)
    )
    title_para  = Paragraph(doc_type, styles["DocTitle"])
    id_para     = Paragraph(f"Nr: {doc_id}", styles["DocSubtitle"])
    date_para   = Paragraph(f"Datum: {date_str}", styles["DocSubtitle"])

    t = Table(
        [[logo_para, [title_para, id_para, date_para]]],
        colWidths=[8*cm, 10*cm]
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ALIGN",  (1,0), (1,0),  "RIGHT"),
        ("LINEBELOW", (0,0), (-1,0), 1.5, YELLOW),
        ("BOTTOMPADDING", (0,0), (-1,0), 8),
    ]))
    return t

def section_bar(title: str):
    """Farbiger Abschnitts-Header."""
    t = Table([[Paragraph(title, ParagraphStyle(
        "SH", fontSize=9, fontName="Helvetica-Bold",
        textColor=white))]],
        colWidths=[18*cm]
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,-1), TABLE_HDR),
        ("TOPPADDING",     (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 4),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
    ]))
    return t

def kv_table(pairs: list, cols=2):
    """Key-Value Tabelle mit je cols Spaltenpaaren nebeneinander."""
    # pairs = [(label, value), ...]
    rows = []
    row  = []
    for i, (label, value) in enumerate(pairs):
        cell = [
            Paragraph(label, ParagraphStyle("KL", fontSize=8,
                textColor=MID_GRAY, fontName="Helvetica")),
            Paragraph(str(value or "–"), ParagraphStyle("KV", fontSize=9,
                textColor=DARK_GRAY, fontName="Helvetica-Bold",
                spaceAfter=6)),
        ]
        row.append(cell)
        if len(row) == cols or i == len(pairs) - 1:
            while len(row) < cols:
                row.append([Paragraph("", ParagraphStyle("KE", fontSize=8)),
                            Paragraph("", ParagraphStyle("KE2", fontSize=9))])
            rows.append(row)
            row = []

    col_w = 18 * cm / cols
    t = Table(rows, colWidths=[col_w] * cols)
    t.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("BACKGROUND",    (0,0), (-1,-1), LIGHT_BG),
        ("GRID",          (0,0), (-1,-1), 0.3, HexColor("#E0E0E0")),
    ]))
    return t

def data_table(headers: list, rows: list):
    """Datentabelle mit Kopfzeile."""
    col_w = 18 * cm / len(headers)
    hdr_style = ParagraphStyle("DH", fontSize=8, textColor=white, fontName="Helvetica-Bold")
    cell_style = ParagraphStyle("DC", fontSize=8, textColor=DARK_GRAY, fontName="Helvetica")
    headers = [Paragraph(str(h), hdr_style) for h in headers]
    rows = [[Paragraph(str(c), cell_style) for c in row] for row in rows]
    data  = [headers] + rows
    t = Table(data, colWidths=[col_w] * len(headers))
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  TABLE_HDR),
        ("TEXTCOLOR",     (0,0), (-1,0),  white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0),  8),
        ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,1), (-1,-1), 8),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [white, LIGHT_BG]),
        ("GRID",          (0,0), (-1,-1), 0.3, HexColor("#D0D0D0")),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("ALIGN",         (0,0), (-1,-1), "LEFT"),
    ]))
    return t

# =============================================================================
# 1. LIEFERSCHEIN  (delivery note)
# =============================================================================
def generate_delivery_note(ev_start: dict) -> bytes:
    """Erzeugt einen Lieferschein-PDF für ein TransportStarted-Event."""
    styles  = base_styles()
    buf     = io.BytesIO()
    doc     = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=2*cm)

    sid     = ev_start.get("shipment_identifier", "–")
    carrier = ev_start.get("carrier", {})
    mode    = ev_start.get("transport_mode", "–")
    src     = ev_start.get("source_node", "–")
    tgt     = ev_start.get("target_node", "–")
    prod    = normalize_key(ev_start.get("cargo_product_reference", "–"))
    ts      = fmt_ts(ev_start.get("timestamp", ""))
    eta     = fmt_ts(ev_start.get("estimated_arrival", ""))

    story = []
    story.append(header_table("LIEFERSCHEIN", sid, ts, styles))
    story.append(Spacer(1, 0.4*cm))

    story.append(section_bar("TRANSPORT-INFORMATIONEN"))
    story.append(kv_table([
        ("Shipment-ID",         sid),
        ("Transport-Modus",     mode),
        ("Carrier",             carrier.get("carrier_name", "–")),
        ("Carrier-Code",        carrier.get("carrier_id", "–")),
        ("Startdatum",          ts),
        ("Voraussichtl. Ankunft", eta),
    ]))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("ROUTE"))
    story.append(kv_table([
        ("Quellknoten",  src),
        ("Zielknoten",   tgt),
    ], cols=2))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("LADUNG"))
    story.append(kv_table([
        ("Produktcode (ERP)",   prod),
        ("Kühlkette",           "Ja – 10°C bis 15°C"),
        ("Transportdokument",   f"delivery-notes/shipments/{sid}/delivery_note.pdf"),
    ], cols=2))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("TEMPERATURVORSCHRIFT"))
    story.append(data_table(
        ["Parameter", "Mindestwert", "Maximalwert", "Einheit", "Aktion bei Abweichung"],
        [
            ["Lagertemperatur", "10.0", "15.0", "°C", "Transport stoppen, Qualitätskontrolle"],
            ["Luftfeuchtigkeit", "80", "90", "%", "Belüftung anpassen"],
        ]
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(section_bar("UNTERSCHRIFTEN"))
    story.append(kv_table([
        ("Absender (Datum/Unterschrift)", "________________________"),
        ("Empfänger (Datum/Unterschrift)", "________________________"),
    ], cols=2))
    story.append(Spacer(1, 0.3*cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#E0E0E0")))
    story.append(Paragraph(
        f"Banana Supply Chain AG  |  Dokument: {sid}  |  Erstellt: {ts}  |  "
        "Dieses Dokument ist maschinell erstellt und ohne Unterschrift gültig.",
        styles["Footer"]
    ))

    doc.build(story)
    return buf.getvalue()


# =============================================================================
# 2. RECHNUNG  (invoice)
# =============================================================================
def generate_invoice(ev_delivery: dict, ev_transport: dict) -> bytes:
    """Erzeugt eine Rechnung für einen erfolgreichen DeliveryCompleted-Event."""
    styles = base_styles()
    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=A4,
                               leftMargin=1.5*cm, rightMargin=1.5*cm,
                               topMargin=1.5*cm, bottomMargin=2*cm)

    sid     = ev_delivery.get("shipment_identifier", "–")
    prod    = normalize_key(ev_delivery.get("cargo_product_reference", "–"))
    status  = ev_delivery.get("delivery_status", "–")
    recv    = ev_delivery.get("received_by", "–")
    ts      = fmt_ts(ev_delivery.get("timestamp", ""))
    src     = ev_transport.get("source_node", "–") if ev_transport else "–"
    tgt     = ev_transport.get("target_node", "–") if ev_transport else "–"
    carrier = ev_transport.get("carrier", {}).get("carrier_name", "–") if ev_transport else "–"
    mode    = ev_transport.get("transport_mode", "–") if ev_transport else "–"

    story = []
    story.append(header_table("TRANSPORTRECHNUNG", sid, ts, styles))
    story.append(Spacer(1, 0.4*cm))

    story.append(section_bar("LIEFERUNGSDETAILS"))
    story.append(kv_table([
        ("Shipment-ID",      sid),
        ("Lieferstatus",     status),
        ("Produktcode",      prod),
        ("Empfangen von",    recv),
        ("Lieferdatum",      ts),
        ("Carrier",          carrier),
        ("Transport-Modus",  mode),
        ("Route",            f"{src} → {tgt}"),
    ]))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("TRANSPORTLEISTUNG"))
    story.append(data_table(
        ["Position", "Leistung", "Strecke", "Modus", "Status"],
        [
            ["1", "Kühlkettentransport", f"{src} → {tgt}", mode, status],
        ]
    ))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("QUALITÄTSBESTÄTIGUNG"))
    story.append(kv_table([
        ("Kühlkette eingehalten", "Ja (10–15°C)"),
        ("Empfangsbestätigung",   recv),
    ], cols=2))
    story.append(Spacer(1, 0.5*cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#E0E0E0")))
    story.append(Paragraph(
        f"Banana Supply Chain AG  |  Rechnung: {sid}  |  Erstellt: {ts}",
        styles["Footer"]
    ))

    doc.build(story)
    return buf.getvalue()


# =============================================================================
# 3. QUALITÄTSZERTIFIKAT  (batch certificate)
# =============================================================================
def generate_quality_cert(ev_node: dict) -> bytes:
    """Erzeugt ein Qualitätszertifikat für NodeProcessed am QUALITY_CONTROL."""
    styles = base_styles()
    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=A4,
                               leftMargin=1.5*cm, rightMargin=1.5*cm,
                               topMargin=1.5*cm, bottomMargin=2*cm)

    batch   = ev_node.get("batch_reference", "–")
    sku     = normalize_key(ev_node.get("sku", "–"))
    node    = ev_node.get("supply_chain_node", "–")
    temp    = ev_node.get("temperature")
    status  = ev_node.get("status", "–")
    ts      = fmt_ts(ev_node.get("timestamp", ""))

    temp_ok = temp is not None and 10.0 <= float(temp) <= 15.0
    temp_str = f"{temp:.2f} °C" if temp is not None else "–"
    result  = "BESTANDEN ✓" if temp_ok else "NICHT BESTANDEN ✗"

    story = []
    story.append(header_table("QUALITÄTSZERTIFIKAT", batch, ts, styles))
    story.append(Spacer(1, 0.4*cm))

    story.append(section_bar("BATCH-INFORMATIONEN"))
    story.append(kv_table([
        ("Batch-ID",         batch),
        ("Produktcode",      sku),
        ("Kontrollknoten",   node),
        ("Prüfdatum",        ts),
        ("Verarbeitungsst.", status),
    ]))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("TEMPERATURPRÜFUNG"))
    story.append(data_table(
        ["Messung", "Gemessener Wert", "Min (°C)", "Max (°C)", "Ergebnis"],
        [[
            "Lagertemperatur",
            temp_str,
            "10.0",
            "15.0",
            result
        ]]
    ))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("ZERTIFIZIERUNGSERGEBNIS"))
    story.append(kv_table([
        ("Gesamtergebnis",           result),
        ("Freigabe für Transport",   "Ja" if temp_ok else "Nein – Quarantäne"),
        ("Phytosanitäre Freigabe",   "Konform mit EU-Importvorschriften"),
        ("Herkunftsland",            "Ghana"),
    ], cols=2))
    story.append(Spacer(1, 0.5*cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#E0E0E0")))
    story.append(Paragraph(
        f"Banana Supply Chain AG  |  Zertifikat: {batch}  |  Ausgestellt: {ts}",
        styles["Footer"]
    ))

    doc.build(story)
    return buf.getvalue()


# =============================================================================
# 4. FRACHTBRIEF  (bill of lading) – nur SEA_FREIGHT
# =============================================================================
def generate_bill_of_lading(ev_transport: dict) -> bytes:
    """Erzeugt einen Seefrachtbrief (B/L) für SEA_FREIGHT-TransportStarted-Events."""
    styles  = base_styles()
    buf     = io.BytesIO()
    doc     = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=2*cm)

    sid     = ev_transport.get("shipment_identifier", "–")
    carrier = ev_transport.get("carrier", {})
    mode    = ev_transport.get("transport_mode", "SEA_FREIGHT")
    src     = ev_transport.get("source_node", "–")
    tgt     = ev_transport.get("target_node", "–")
    prod    = normalize_key(ev_transport.get("cargo_product_reference", "–"))
    ts      = fmt_ts(ev_transport.get("timestamp", ""))
    eta     = fmt_ts(ev_transport.get("estimated_arrival", ""))
    bl_nr   = f"BL-{sid[-8:]}" if len(sid) >= 8 else f"BL-{sid}"

    story = []
    story.append(header_table("SEEFRACHTBRIEF (BILL OF LADING)", bl_nr, ts, styles))
    story.append(Spacer(1, 0.4*cm))

    story.append(section_bar("VERTRAGSPARTEIEN"))
    story.append(kv_table([
        ("Verlader (Shipper)",        "Banana Supply Chain AG, Ghana"),
        ("Empfänger (Consignee)",     "Banana Supply Chain AG, Europa"),
        ("Notify Party",              "Banana Supply Chain AG Logistics"),
        ("Reederei / Carrier",        carrier.get("carrier_name", "–")),
        ("Carrier-Code",              carrier.get("carrier_id", "–")),
        ("Konnossementnummer (B/L)",   bl_nr),
    ]))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("TRANSPORT-DETAILS"))
    story.append(kv_table([
        ("Verschiffungshafen (PoL)",  src),
        ("Löschhafen (PoD)",          tgt),
        ("Transportmodus",            mode),
        ("Verschiffungsdatum",        ts),
        ("Voraussichtl. Ankunft",     eta),
        ("Shipment-Referenz",         sid),
    ]))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("LADUNGSBESCHREIBUNG"))
    story.append(data_table(
        ["Warenbez.", "Produktcode", "Kühlkette", "Temp. Min (°C)", "Temp. Max (°C)", "HS-Code"],
        [["Frische Bananen", prod, "Ja", "10.0", "15.0", "0803.90"]]
    ))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("BESONDERE KLAUSELN"))
    story.append(kv_table([
        ("Kühlkettenklausel",         "Temperatur 10–15 °C während des gesamten Transports"),
        ("Haftungsausschluss",        "Schäden durch Temperaturabweichung außerhalb des Trägers"),
        ("Anzahl Originale",          "3 (Drei)"),
        ("Ausstellungsort/-datum",    f"Hamburg, {ts}"),
    ]))
    story.append(Spacer(1, 0.5*cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#E0E0E0")))
    story.append(Paragraph(
        f"Banana Supply Chain AG  |  B/L Nr: {bl_nr}  |  Shipment: {sid}  |  Ausgestellt: {ts}  |  "
        "Dieses Konnossement unterliegt den Haager-Visby-Regeln.",
        styles["Footer"]
    ))

    doc.build(story)
    return buf.getvalue()


# =============================================================================
# 5. ZOLLFREIGABE  (customs clearance) – nur SEA_FREIGHT Afrika→Europa
# =============================================================================
def generate_customs_clearance(ev_transport: dict) -> bytes:
    """Erzeugt eine EU-Zollfreigabebescheinigung für SEA_FREIGHT-Importe aus Afrika."""
    styles  = base_styles()
    buf     = io.BytesIO()
    doc     = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=2*cm)

    sid     = ev_transport.get("shipment_identifier", "–")
    carrier = ev_transport.get("carrier", {})
    prod    = normalize_key(ev_transport.get("cargo_product_reference", "–"))
    ts      = fmt_ts(ev_transport.get("timestamp", ""))
    eta     = fmt_ts(ev_transport.get("estimated_arrival", ""))
    cc_nr   = f"CC-EU-{sid[-8:]}" if len(sid) >= 8 else f"CC-EU-{sid}"

    story = []
    story.append(header_table("EU-ZOLLFREIGABEBESCHEINIGUNG", cc_nr, ts, styles))
    story.append(Spacer(1, 0.4*cm))

    story.append(section_bar("IMPORTEUR UND ZOLLBEHÖRDE"))
    story.append(kv_table([
        ("Importeur",                 "Banana Supply Chain AG, Hamburg"),
        ("Zuständige Zollstelle",     "Hauptzollamt Hamburg-Hafen"),
        ("Verfahrenscode",            "4000 – Überführung in den freien Verkehr"),
        ("Einfuhranmeldung (MRN)",    f"DE{sid[-12:].upper().replace('-','')}"),
        ("Ursprungsland",             "Ghana (GH)"),
        ("Bestimmungsland",           "Deutschland (DE) / EU"),
    ]))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("WARENBESCHREIBUNG"))
    story.append(data_table(
        ["Warenbez.", "Produktcode", "HS-Code", "Ursprungsland", "EU-Einfuhrzollsatz"],
        [["Frische Bananen", prod, "0803.90.10", "Ghana (GH)", "0 % (APS+)"]]
    ))
    story.append(Spacer(1, 0.3*cm))

    story.append(section_bar("PHYTOSANITÄRE KONFORMITÄT"))
    story.append(kv_table([
        ("Phytosanit. Zertifikat",    f"PHYTO-{sid[-6:].upper()}"),
        ("Ausstellungsbehörde",       "PPRSD Ghana (Plant Protection)"),
        ("EU-Einfuhrinspektion",      "Bestanden – konform mit EU 2016/2031"),
        ("Carrier",                   carrier.get("carrier_name", "–")),
        ("Schiff / Voyage",           f"{carrier.get('carrier_id', '–')} / {sid[-6:]}"),
        ("Voraussichtl. Ankunft PoD", eta),
        ("Shipment-Referenz",         sid),
        ("Freigabedatum",             ts),
    ]))
    story.append(Spacer(1, 0.5*cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#E0E0E0")))
    story.append(Paragraph(
        f"Banana Supply Chain AG  |  Zollfreigabe: {cc_nr}  |  MRN: DE{sid[-12:].upper().replace('-','')}  |  "
        "Ausgestellt gemäß EU-Zollkodex (UZK) Art. 201.",
        styles["Footer"]
    ))

    doc.build(story)
    return buf.getvalue()


# =============================================================================
# MAIN – alle Dokumente generieren und hochladen
# =============================================================================
def main():
    print("=" * 60)
    print("PDF-Generator: Banana Supply Chain")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    minio = Minio(MINIO_EP, access_key=MINIO_KEY, secret_key=MINIO_SEC, secure=False)
    pg    = psycopg2.connect(PG_DSN)
    cur   = pg.cursor()

    # Buckets sicherstellen
    for bucket in ["invoices", "delivery-notes", "transport-docs", "batch-certificates"]:
        if not minio.bucket_exists(bucket):
            minio.make_bucket(bucket)

    # Events laden
    tms_events = load_events("tms")
    wms_events = load_events("wms")

    transport_map = {}  # shipment_identifier → TransportStarted-Event
    for ev in tms_events:
        if ev.get("event_type") == "TransportStarted":
            transport_map[ev["shipment_identifier"]] = ev

    count_notes = count_invoices = count_certs = count_bl = count_cc = 0

    # ── Lieferscheine ────────────────────────────────────────────────────────
    print("\n[1/4] Lieferscheine generieren...")
    for ev in tms_events:
        if ev.get("event_type") != "TransportStarted":
            continue
        sid  = ev["shipment_identifier"]
        path = f"shipments/{sid}/delivery_note.pdf"
        pdf  = generate_delivery_note(ev)
        minio.put_object(
            "delivery-notes", path,
            io.BytesIO(pdf), len(pdf),
            content_type="application/pdf",
            metadata={
                "shipment_identifier": sid,
                "source_node":        ev.get("source_node", ""),
                "target_node":        ev.get("target_node", ""),
                "carrier":            ev.get("carrier", {}).get("carrier_name", ""),
                "transport_mode":     ev.get("transport_mode", ""),
                "document_type":      "delivery_note",
            }
        )
        cur.execute("""
            INSERT INTO erp.document_references
                (entity_type, entity_key, document_type, bucket, object_path)
            VALUES ('SHIPMENT', %s, 'delivery_note', 'delivery-notes', %s)
            ON CONFLICT (entity_key, document_type) DO UPDATE
                SET object_path = EXCLUDED.object_path
        """, (sid, path))
        count_notes += 1

    print(f"  {count_notes} Lieferscheine hochgeladen")

    # ── Frachtbriefe + Zollfreigaben (nur SEA_FREIGHT) ───────────────────────
    print("[2/4] Frachtbriefe (Bill of Lading) + Zollfreigaben generieren...")
    for ev in tms_events:
        if ev.get("event_type") != "TransportStarted":
            continue
        if ev.get("transport_mode") != "SEA_FREIGHT":
            continue
        sid     = ev["shipment_identifier"]
        carrier = ev.get("carrier", {})
        mode    = ev.get("transport_mode", "")

        # Bill of Lading
        path_bl = f"shipments/{sid}/bill_of_lading.pdf"
        pdf_bl  = generate_bill_of_lading(ev)
        minio.put_object(
            "transport-docs", path_bl,
            io.BytesIO(pdf_bl), len(pdf_bl),
            content_type="application/pdf",
            metadata={
                "shipment_identifier": sid,
                "transport_mode":      mode,
                "carrier":             carrier.get("carrier_name", ""),
                "route":               f"{ev.get('source_node','')}->{ev.get('target_node','')}",
                "document_type":       "bill_of_lading",
            }
        )
        cur.execute("""
            INSERT INTO erp.document_references
                (entity_type, entity_key, document_type, bucket, object_path)
            VALUES ('SHIPMENT', %s, 'bill_of_lading', 'transport-docs', %s)
            ON CONFLICT (entity_key, document_type) DO UPDATE
                SET object_path = EXCLUDED.object_path
        """, (sid, path_bl))
        count_bl += 1

        # Customs Clearance
        path_cc = f"shipments/{sid}/customs_clearance.pdf"
        pdf_cc  = generate_customs_clearance(ev)
        minio.put_object(
            "transport-docs", path_cc,
            io.BytesIO(pdf_cc), len(pdf_cc),
            content_type="application/pdf",
            metadata={
                "shipment_identifier": sid,
                "transport_mode":      mode,
                "origin_country":      "Ghana",
                "destination":         "EU",
                "document_type":       "customs_clearance",
            }
        )
        cur.execute("""
            INSERT INTO erp.document_references
                (entity_type, entity_key, document_type, bucket, object_path)
            VALUES ('SHIPMENT', %s, 'customs_clearance', 'transport-docs', %s)
            ON CONFLICT (entity_key, document_type) DO UPDATE
                SET object_path = EXCLUDED.object_path
        """, (sid, path_cc))
        count_cc += 1

    print(f"  {count_bl} Frachtbriefe (B/L) hochgeladen")
    print(f"  {count_cc} Zollfreigaben hochgeladen")

    # ── Rechnungen ───────────────────────────────────────────────────────────
    print("[3/4] Rechnungen generieren...")
    for ev in tms_events:
        if ev.get("event_type") != "DeliveryCompleted":
            continue
        if ev.get("delivery_status") != "SUCCESSFUL":
            continue
        sid      = ev["shipment_identifier"]
        ev_start = transport_map.get(sid)
        path     = f"shipments/{sid}/invoice.pdf"
        pdf      = generate_invoice(ev, ev_start)
        minio.put_object(
            "invoices", path,
            io.BytesIO(pdf), len(pdf),
            content_type="application/pdf",
            metadata={
                "shipment_identifier": sid,
                "delivery_status":     ev.get("delivery_status", ""),
                "document_type":       "invoice",
            }
        )
        cur.execute("""
            INSERT INTO erp.document_references
                (entity_type, entity_key, document_type, bucket, object_path)
            VALUES ('SHIPMENT', %s, 'invoice', 'invoices', %s)
            ON CONFLICT (entity_key, document_type) DO UPDATE
                SET object_path = EXCLUDED.object_path
        """, (sid, path))
        count_invoices += 1

    print(f"  {count_invoices} Rechnungen hochgeladen")

    # ── Qualitätszertifikate ─────────────────────────────────────────────────
    print("[4/4] Qualitätszertifikate generieren...")
    for ev in wms_events:
        if ev.get("event_type") != "NodeProcessed":
            continue
        if ev.get("supply_chain_node") != "QUALITY_CONTROL":
            continue
        batch = ev["batch_reference"]
        path  = f"batches/{batch}/quality_certificate.pdf"
        pdf   = generate_quality_cert(ev)
        minio.put_object(
            "batch-certificates", path,
            io.BytesIO(pdf), len(pdf),
            content_type="application/pdf",
            metadata={
                "batch_identifier": batch,
                "sku":              normalize_key(ev.get("sku", "")),
                "temperature":      str(ev.get("temperature", "")),
                "document_type":    "quality_certificate",
            }
        )
        cur.execute("""
            INSERT INTO erp.document_references
                (entity_type, entity_key, document_type, bucket, object_path)
            VALUES ('BATCH', %s, 'quality_certificate', 'batch-certificates', %s)
            ON CONFLICT (entity_key, document_type) DO UPDATE
                SET object_path = EXCLUDED.object_path
        """, (batch, path))
        count_certs += 1

    print(f"  {count_certs} Qualitätszertifikate hochgeladen")

    pg.commit()
    cur.close()
    pg.close()

    total = count_notes + count_bl + count_cc + count_invoices + count_certs
    print("\n" + "=" * 60)
    print(f"Fertig: {count_notes} Lieferscheine  |  "
          f"{count_bl} B/L  |  {count_cc} Zollfreigaben  |  "
          f"{count_invoices} Rechnungen  |  {count_certs} Qualitätszertifikate")
    print(f"Gesamt: {total} Dokumente – alle Pfade in erp.document_references gespeichert")
    print(f"MinIO-Konsole: http://localhost:9001")
    print("=" * 60)


if __name__ == "__main__":
    main()
