# MinIO Dokumentenmodell – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-12

---

## 1. Warum MinIO für Dokumente?

Lieferscheine, Rechnungen und Transportdokumente sind **unstrukturierte Binärdateien** (PDF). Sie in eine relationale Datenbank zu speichern (als BLOB) ist aus mehreren Gründen problematisch:

| Problem bei DB-Speicherung | Lösung mit MinIO |
|---|---|
| BLOBs verlangsamen Backups und Replikation | Dokumente sind getrennt vom Transaktionssystem |
| Datenbankgröße wächst unkontrolliert | Object Storage skaliert horizontal |
| Kein HTTP-basierter Download | MinIO bietet S3-kompatible URL-basierte Downloads |
| Versionierung von Dokumenten aufwendig | MinIO unterstützt Bucket Versioning |
| Metadata-Suche über Dokumentinhalt schwierig | Object-Tags für Metadaten |

**MinIO** ist ein S3-kompatibler Object Store, der sich transparent durch AWS S3 ersetzen lässt. PostgreSQL speichert nur die **Referenz** auf das Dokument (Bucket + Objektpfad), nicht die Datei selbst.

---

## 2. Bucket-Struktur

### Übersicht

```
minio/
├── invoices/                   → Rechnungen pro Bestellung
│   └── orders/{order_ref}/invoice.pdf
├── delivery-notes/             → Lieferscheine pro Shipment
│   └── shipments/{ship_id}/delivery_note.pdf
├── transport-docs/             → Frachtbriefe und Zolldokumente
│   └── shipments/{ship_id}/bill_of_lading.pdf
│   └── shipments/{ship_id}/customs_clearance.pdf
└── batch-certificates/         → Qualitätszertifikate pro Batch
    └── batches/{batch_id}/quality_certificate.pdf
    └── batches/{batch_id}/phytosanitary_certificate.pdf
```

### Namenskonvention für Objekte

```
Format: <entity_type>/<identifier>/<document_type>.pdf

Beispiele:
  orders/ORD-0f7dc974/invoice.pdf
  shipments/SHIP-bf5d4354/delivery_note.pdf
  shipments/SHIP-bf5d4354/bill_of_lading.pdf
  batches/BATCH-9c6818ad/quality_certificate.pdf
```

---

## 3. Buckets im Detail

### 3.1 Bucket `invoices` – Rechnungen

**Inhalt:** Rechnungen an Einzelhandelskunden (ALDI, LIDL, etc.) pro Bestellung.

**Auslöser:** Nach `DeliveryCompleted` mit `delivery_status = "SUCCESSFUL"` wird die Rechnung generiert.

**Pflichtfelder im Dokument:**
- Rechnungsnummer (= `order_reference`)
- Kunde (Name, Adresse)
- Positionen (Produkt, Menge, Einzelpreis, Gesamtpreis)
- Rechnungsbetrag (Summe)
- Datum, Fälligkeit

**Object-Tags (Metadaten):**
```
order_reference  = "ORD-0f7dc974"
customer_number  = "CUST-109"
customer_name    = "AUCHAN"
total_value      = "2348.40"
currency         = "EUR"
created_at       = "2026-05-14T09:30:00"
document_type    = "invoice"
```

**PostgreSQL-Referenz (nur Pfad, kein BLOB):**
```sql
-- Erweiterung erp.orders um Referenz auf MinIO-Objekt
-- (konzeptuell, als separate Tabelle oder Spalte):
SELECT 'invoices/orders/' || order_reference || '/invoice.pdf' AS minio_path
FROM   erp.orders
WHERE  order_reference = 'ORD-0f7dc974';
```

---

### 3.2 Bucket `delivery-notes` – Lieferscheine

**Inhalt:** Lieferscheine für jeden Transportvorgang zur Warenkontrolle beim Empfänger.

**Auslöser:** Bei `TransportStarted` wird der Lieferschein generiert und beim Empfänger nach `TransportCompleted` bestätigt.

**Pflichtfelder im Dokument:**
- Lieferscheinnummer (= `shipment_identifier`)
- Absender-Knoten, Empfänger-Knoten
- Carrier
- Produktcode, Menge, Batch-Identifier
- Temperaturfreigabe (Kühlkette-Bestätigung)
- Empfänger-Unterschrift bei Annahme

**Object-Tags:**
```
shipment_identifier = "SHIP-bf5d4354"
source_node         = "AFRICA_COLD_STORAGE"
target_node         = "EUROPE_COLD_STORAGE"
carrier_name        = "DB Schenker"
transport_mode      = "SEA_FREIGHT"
document_type       = "delivery_note"
```

---

### 3.3 Bucket `transport-docs` – Transportdokumente

**Inhalt:** Frachtbriefe (Bill of Lading für Seefracht) und Zollfreigaben.

**Unterordner:**
- `bill_of_lading.pdf`: Seefracht-Frachtbrief (nur für `SEA_FREIGHT`-Shipments)
- `customs_clearance.pdf`: Zollfreigabe für EU-Einfuhr (Afrika→Europa)
- `atr_certificate.pdf`: Warenverkehrsbescheinigung (optional)

**Auslöser:** Bei `TransportStarted` für `SEA_FREIGHT`-Transporte.

**Object-Tags:**
```
shipment_identifier = "SHIP-bf5d4354"
transport_mode      = "SEA_FREIGHT"
route               = "AFRICA_COLD_STORAGE_to_EUROPE_COLD_STORAGE"
document_type       = "bill_of_lading"
created_at          = "2026-05-12T14:00:00"
```

---

### 3.4 Bucket `batch-certificates` – Qualitätszertifikate

**Inhalt:** Phytosanitäre Zertifikate (Pflanzenschutz) und Qualitätsprüfberichte pro Batch.

**Unterordner:**
- `quality_certificate.pdf`: Qualitätsprüfbericht aus dem Quality Control Node
- `phytosanitary_certificate.pdf`: Pflanzenschutzzertifikat für Export aus Ghana

**Auslöser:** Nach `NodeProcessed` am Knoten `QUALITY_CONTROL`.

**Object-Tags:**
```
batch_identifier    = "BATCH-9c6818ad"
product_code        = "BAN-108"
origin_country      = "Ghana"
inspection_passed   = "true"
temperature_ok      = "true"
document_type       = "phytosanitary_certificate"
```

---

## 4. Referenzierungsmuster: PostgreSQL ↔ MinIO

MinIO-Objekte werden in PostgreSQL **nur als Pfad-String** referenziert:

```sql
-- Konzept: Dokumentreferenz-Tabelle (optional, für vollständigen Katalog)
CREATE TABLE IF NOT EXISTS erp.document_references (
    ref_id          SERIAL      PRIMARY KEY,
    entity_type     VARCHAR(20) NOT NULL, -- 'ORDER', 'SHIPMENT', 'BATCH'
    entity_key      VARCHAR(60) NOT NULL, -- z.B. order_reference
    document_type   VARCHAR(30) NOT NULL, -- 'invoice', 'delivery_note', ...
    bucket          VARCHAR(50) NOT NULL, -- MinIO-Bucket
    object_path     VARCHAR(200)NOT NULL, -- Pfad im Bucket
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

-- Beispiel-Eintrag:
INSERT INTO erp.document_references (entity_type, entity_key, document_type, bucket, object_path)
VALUES ('ORDER', 'ORD-0f7dc974', 'invoice', 'invoices', 'orders/ORD-0f7dc974/invoice.pdf');

-- Abruf des MinIO-Pfads:
SELECT bucket || '/' || object_path AS full_path
FROM   erp.document_references
WHERE  entity_type = 'ORDER'
AND    entity_key  = 'ORD-0f7dc974'
AND    document_type = 'invoice';
-- → invoices/orders/ORD-0f7dc974/invoice.pdf
```

---

## 5. MinIO-Konfiguration (aus docker-compose.yml)

```yaml
minio:
  image: minio/minio
  command: server /data --console-address ":9001"
  environment:
    MINIO_ROOT_USER: admin
    MINIO_ROOT_PASSWORD: password
  ports:
    - "9000:9000"    # API-Port (S3-kompatibel)
    - "9001:9001"    # Web-Console
```

**Bucket-Erstellung per Python (MinIO-SDK):**
```python
from minio import Minio

client = Minio("localhost:9000", access_key="admin", secret_key="password", secure=False)

for bucket in ["invoices", "delivery-notes", "transport-docs", "batch-certificates"]:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f"Bucket '{bucket}' erstellt")
```
