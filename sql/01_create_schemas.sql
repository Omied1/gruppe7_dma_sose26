-- =============================================================================
-- 01_create_schemas.sql
-- Erstellt alle PostgreSQL-Schemas für die Banana Supply Chain Plattform
--
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
