-- =============================================================================
-- 01_create_schemas.sql
-- Erstellt alle PostgreSQL-Schemas für die Banana Supply Chain Plattform
-- Die Datei sql/01_create_schemas.sql erstellt die Grundbereiche/Schemas in PostgreSQL. 
-- Ein Schema ist wie ein Ordner innerhalb der Datenbank. Damit werden Tabellen logisch getrennt. 
-- Diese Datei erstellt noch keine Tabellen. Sie erstellt nur die leeren Bereiche.
-- Kurz gesagt: 01_create_schemas.sql legt die Datenbank-Struktur auf oberster Ebene an, damit später Tabellen wie tms.shipment_positions, erp.orders oder dwh.fact_fulfillment überhaupt angelegt werden können

-- Schemas:
--   erp   - Enterprise Resource Planning (Lieferanten, Kunden, Produkte, Orders)
--   wms   - Warehouse Management System (SKUs, Knotenverarbeitungen)
--   tms   - Transport Management System (Carrier, Shipments, GPS, Lieferungen)
--   mdm   - Master Data Management (Golden Records, Source Mappings)
--   meta  - Metadatenmanagement (Tabellen-, Spalten-Metadaten, Skalenniveaus)
--   dwh   - Data Warehouse (Sternschema, ETL-getrieben, kein direkter Zugriff aus operativen Schemas)
--
-- Ausführung: psql -h localhost -U user -d logistics -f 01_create_schemas.sql
-- =============================================================================

-- Operative Quellsystem-Schemas
CREATE SCHEMA IF NOT EXISTS erp;
CREATE SCHEMA IF NOT EXISTS wms;
CREATE SCHEMA IF NOT EXISTS tms;

-- Querschnitts-Schemas
CREATE SCHEMA IF NOT EXISTS mdm;
CREATE SCHEMA IF NOT EXISTS meta;

-- Analytics-Schema (wird ausschließlich durch ETL-Prozesse befüllt)
CREATE SCHEMA IF NOT EXISTS dwh;

-- Bestätigung
DO $$
BEGIN
    RAISE NOTICE 'Schemas erstellt: erp, wms, tms, mdm, meta, dwh';
END $$;
