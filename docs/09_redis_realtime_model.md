# Redis Echtzeit-Modell – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-15

---

## 1. Warum Redis für Echtzeitdaten?

Redis ist eine **In-Memory-Datenbank**, die Daten im Arbeitsspeicher hält und dadurch Sub-Millisekunden-Latenz erreicht. PostgreSQL und MongoDB sind für persistente, vollständige Datenbestände ausgelegt – sie sind für Echtzeitabfragen wie „Wo befindet sich Shipment SHIP-xyz gerade?" zu langsam. Redis übernimmt ausschließlich die **volatile Echtzeitschicht**.

Konkrete Echtzeitanforderungen in der Banana Supply Chain:

- **Shipment-Tracking:** Wo befindet sich Sendung SHIP-bf5d4354 gerade?
- **Order-Status:** Hat Order ORD-9ae0e069 bereits den Status `IN_TRANSIT`?
- **Dashboard-Metriken:** Wie viele aktive Transporte gibt es gerade?
- **Kühlketten-Alerts:** Befindet sich die Containertemperatur von SHIP-67e67f7c außerhalb 10–15 °C?

**Konfiguration (`docker-compose.yml`):**
```
--maxmemory 256mb
--maxmemory-policy allkeys-lru    # älteste Keys werden bei Speicherdruck verdrängt
--appendonly no                   # kein persistentes Write-Ahead-Log → reine Cache-Rolle
```

`allkeys-lru` ist bewusst gewählt: Bei Speicherdruck werden veraltete Echtzeit-Keys automatisch verdrängt. Kritische Stammdaten liegen in PostgreSQL und werden bei Bedarf neu geladen.

---

## 2. Key-Naming-Konvention

```
<namespace>:<entity>:<identifier>[:<attribute>]
```

| Namespace    | Entität       | Beispiel                                        |
|--------------|---------------|-------------------------------------------------|
| `shipment`   | TMS-Sendungen | `shipment:status:SHIP-bf5d4354`                 |
| `order`      | ERP-Bestellung| `order:status:ORD-9ae0e069`                     |
| `cache`      | Stammdaten    | `cache:product:BAN-101`                         |
| `system`     | Zähler        | `system:counter:active_shipments`               |
| `monitoring` | Anomalien     | `monitoring:temp_violations:20260515`           |

---

## 3. Key-Strukturen im Detail

### 3.1 Shipment-Tracking (TMS-Events)

#### Aktueller Shipmentstatus – `TransportStarted` / `DeliveryCompleted`
```
Key:   shipment:status:<shipment_identifier>
Typ:   STRING
Wert:  "IN_TRANSIT" | "DELIVERED" | "COMPLETED" | "DELAYED"
TTL:   7 Tage (IN_TRANSIT) | 30 Tage (nach Abschluss)

Beispiel:
  SET    shipment:status:SHIP-bf5d4354  "IN_TRANSIT"  EX 604800
  GET    shipment:status:SHIP-bf5d4354
  → "IN_TRANSIT"
```

**Begründung TTL-Unterschied:** Ein aktiver Transport ist maximal 7 Tage unterwegs. Nach `DeliveryCompleted` bleibt der Finalstatus 30 Tage für Rückfragen verfügbar, bevor er aus dem Cache fällt und nur noch in MongoDB/PostgreSQL liegt.

#### Transport-Metadaten – `TransportStarted`
```
Key:   shipment:info:<shipment_identifier>
Typ:   HASH
Felder: transport_mode, source_node, target_node, started_at, carrier_id
TTL:   7 Tage

Beispiel:
  HSET  shipment:info:SHIP-bf5d4354
        transport_mode "SEA"
        source_node    "PLANTATION"
        target_node    "PORT_HAMBURG"
        started_at     "2026-05-15T08:00:00"
        carrier_id     "CAR-102"
  EXPIRE shipment:info:SHIP-bf5d4354 604800

  HGET  shipment:info:SHIP-bf5d4354  carrier_id
  → "CAR-102"
```

#### Aktuelle GPS-Position – `ShipmentPositionUpdated`
```
Key:   shipment:position:<shipment_identifier>
Typ:   HASH
Felder: latitude, longitude, temperature, speed_kmh, updated_at
TTL:   1 Stunde (GPS-Daten veralten schnell, neue Updates überschreiben)

Beispiel:
  HSET  shipment:position:SHIP-67e67f7c
        latitude    -77.148118
        longitude   35.913637
        temperature 10.12
        speed_kmh   55.53
        updated_at  "2026-05-15T12:00:00"
  EXPIRE shipment:position:SHIP-67e67f7c 3600

  HGETALL shipment:position:SHIP-67e67f7c
  → { latitude: -77.148118, longitude: 35.913637, temperature: 10.12, ... }
```

#### Positionsverlauf für Live-Map – `ShipmentPositionUpdated`
```
Key:   shipment:route:<shipment_identifier>
Typ:   SORTED SET
Score: Unix-Timestamp des GPS-Updates
Member: JSON-String {"lat", "lon", "temp", "ts"}
TTL:   3 Tage (kurzer Verlauf für Karte reicht)

Zweck: Routen-Replay in der Live-Map ohne MongoDB-Abfrage

Beispiel:
  ZADD  shipment:route:SHIP-67e67f7c
        1715770800  '{"lat":-77.15,"lon":35.91,"temp":10.12,"ts":"2026-05-15T12:00:00"}'
  EXPIRE shipment:route:SHIP-67e67f7c 259200

  ZRANGE shipment:route:SHIP-67e67f7c 0 -1 WITHSCORES
  → alle GPS-Punkte chronologisch sortiert
```

#### Kühlketten-Alert-Flag – `ShipmentPositionUpdated`
```
Key:   shipment:alert:temperature:<shipment_identifier>
Typ:   STRING
Wert:  "ALERT" (nur gesetzt wenn Temperatur außerhalb 10–15 °C)
TTL:   24 Stunden (Alert erlischt automatisch, wenn keine neue Verletzung)

Beispiel:
  SET   shipment:alert:temperature:SHIP-67e67f7c  "ALERT"  EX 86400
  EXISTS shipment:alert:temperature:SHIP-67e67f7c
  → 1 (Alert aktiv) | 0 (kein Alert / abgelaufen)
```

---

### 3.2 Order-Tracking (ERP-Events)

#### Aktueller Order-Status – `OrderCreated`
```
Key:   order:status:<order_reference>
Typ:   STRING
Wert:  "CREATED" | "IN_TRANSIT" | "DELIVERED"
TTL:   30 Tage

Beispiel:
  SET   order:status:ORD-9ae0e069  "CREATED"  EX 2592000
  GET   order:status:ORD-9ae0e069
  → "CREATED"
```

#### Order-Metadaten – `OrderCreated`
```
Key:   order:meta:<order_reference>
Typ:   HASH
Felder: customer_number, customer_name, priority, created_at
TTL:   30 Tage

Beispiel:
  HSET  order:meta:ORD-9ae0e069
        customer_number "CUST-103"
        customer_name   "REWE"
        priority        "LOW"
        created_at      "2026-05-14T15:39:19"

  HGET  order:meta:ORD-9ae0e069  customer_name
  → "REWE"
```

#### Status-Timeline – `OrderCreated`
```
Key:   order:timeline:<order_reference>
Typ:   LIST (RPUSH = neueste Einträge hinten)
Wert:  Chronologische Statusänderungen als Strings
TTL:   30 Tage

Beispiel:
  RPUSH  order:timeline:ORD-9ae0e069  "2026-05-14T15:39:19 – CREATED"
  RPUSH  order:timeline:ORD-9ae0e069  "2026-05-14T16:00:00 – IN_TRANSIT"

  LRANGE order:timeline:ORD-9ae0e069 0 -1
  → ["2026-05-14T15:39:19 – CREATED", "2026-05-14T16:00:00 – IN_TRANSIT"]
```

---

### 3.3 Systemzähler (Counter)

```
Key:   system:counter:active_shipments
Typ:   STRING (Integer)
TTL:   Kein TTL (Dashboard-Counter bleibt aktiv)
Op:    INCR bei TransportStarted | DECR bei DeliveryCompleted

Key:   system:counter:orders_today
Typ:   STRING (Integer)
TTL:   EXPIREAT 23:59:59 (automatischer Reset um Mitternacht)
Op:    INCR bei OrderCreated

Key:   system:counter:deliveries_delivered
Typ:   STRING (Integer)
TTL:   Kein TTL
Op:    INCR bei DeliveryCompleted mit status=DELIVERED

Key:   system:counter:temperature_alerts_active
Typ:   STRING (Integer)
TTL:   Kein TTL
Op:    INCR bei Temperaturverstoß (10–15 °C überschritten)

Key:   system:counter:etl_runs
Typ:   STRING (Integer)
TTL:   Kein TTL
Op:    INCR nach jedem ETL-Lauf

Beispiele:
  GET  system:counter:active_shipments   → "12"
  GET  system:counter:orders_today       → "8"
  GET  system:counter:etl_runs           → "3"
```

---

### 3.4 Produktstammdaten-Cache (ERP-Events)

```
Key:   cache:product:<product_code>
Typ:   HASH
Felder: description, unit_price
TTL:   1 Stunde (Stammdaten ändern sich selten, kurzer Cache reicht)

Zweck: Dashboard-Anzeige von Produktname ohne PostgreSQL-Roundtrip

Beispiel:
  HSET  cache:product:BAN-101
        description  "Cavendish Banana"
        unit_price   "2.85"
  EXPIRE cache:product:BAN-101 3600

  HGET  cache:product:BAN-101  description
  → "Cavendish Banana"
```

---

### 3.5 Temperatur-Monitoring (Tages-Sorted-Set)

```
Key:   monitoring:temp_violations:<YYYYMMDD>
Typ:   SORTED SET
Score: Temperaturwert (Ausreißer als Score → sortierbar nach Schwere)
Member: "<shipment_identifier>:<timestamp>:temp=<wert>"
TTL:   7 Tage

Zweck: Alle Temperaturverstösse des Tages sortiert nach Schwere

Beispiel:
  ZADD  monitoring:temp_violations:20260515
        16.7  "SHIP-abc123:2026-05-15T14:00:temp=16.7"   (zu warm)
        9.1   "SHIP-def456:2026-05-15T14:30:temp=9.1"    (zu kalt)
  EXPIRE monitoring:temp_violations:20260515 604800

  ZRANGEBYSCORE monitoring:temp_violations:20260515 16.0 +inf
  → alle Shipments mit Temperatur > 16 °C heute (kritischste Fälle)

  ZRANGE monitoring:temp_violations:20260515 0 -1 WITHSCORES
  → vollständige Tagesliste aufsteigend nach Temperatur
```

**Begründung Datumskey:** Ein globaler Key ohne Datum wäre ohne TTL ein unbegrenzter Speicherfresser (`allkeys-lru` würde ihn nie automatisch verkleinern, da er zuletzt immer wieder angefasst wird). Der Datumskey erlaubt granulare Abfragen pro Tag und verfällt nach 7 Tagen automatisch.

---

### 3.6 Aktive Sendungen als Menge – `TransportStarted` / `DeliveryCompleted`

```
Key:    active_shipments
Typ:    SET
Member: <shipment_identifier> aller aktuell unterwegs befindlichen Sendungen
TTL:    Kein TTL (bildet den Live-Zustand ab; wird zu Beginn jedes ETL-Laufs geleert)

Zweck:  Zeigt WELCHE Sendungen aktiv sind – Ergänzung zum Zähler
        system:counter:active_shipments (3.3), der nur WIE VIELE zeigt.

Beispiel:
  SADD      active_shipments  SHIP-bf5d4354     (bei TransportStarted)
  SREM      active_shipments  SHIP-bf5d4354     (bei DeliveryCompleted)
  SMEMBERS  active_shipments                    → alle aktiven Sendungs-IDs
  SCARD     active_shipments                    → Anzahl (muss == Zähler sein)
  SISMEMBER active_shipments SHIP-67e67f7c      → 1 (aktiv) | 0 (nicht aktiv)
```

**Warum SET zusätzlich zum Counter:** Der Integer-Zähler `system:counter:active_shipments` beantwortet „wie viele Transporte laufen?", aber nicht „welche?". Das SET liefert beide Antworten (`SCARD` = Anzahl, `SMEMBERS` = IDs) und prüft Mitgliedschaft in O(1) (`SISMEMBER`). Zusätzlich ist es gegen Doppelzählung robust: Ein versehentlich doppeltes `TransportStarted` erhöht den Zähler zweimal, fügt dem SET aber nur einen Member hinzu – `SCARD` bleibt korrekt. Der Name `active_shipments` (ohne Namespace-Präfix) entspricht bewusst der Ziel-Struktur aus Kapitel 5, Folie 7.

**Konsistenz SET ↔ Zähler:** Die ETL verarbeitet die TMS-Events **chronologisch** (nach `timestamp` sortiert). Nur dadurch wird jede Sendung zuerst per `SADD`/`INCR` aufgenommen und erst danach bei `DeliveryCompleted` per `SREM`/`DECR` entfernt – ohne chronologische Reihenfolge (z. B. Dateinamen-Sortierung: `deliverycompleted` vor `transportstarted`) liefe das `SREM` ins Leere und `SCARD` liefe vom Zähler weg. `verify_all_systems.py` prüft die Gleichheit `SCARD active_shipments == system:counter:active_shipments` (und `ZCARD live_etas == SCARD`).

---

### 3.7 Geschätzte Ankunftszeiten – `TransportStarted` / `DeliveryCompleted`

```
Key:    live_etas
Typ:    SORTED SET
Score:  Unix-Timestamp der geschätzten Ankunft (Feld estimated_arrival aus dem Event)
Member: <shipment_identifier>
TTL:    Kein TTL (Live-Zustand; wird zu Beginn jedes ETL-Laufs geleert)

Zweck:  Aktive Sendungen nach Ankunftszeit sortiert – "welche Sendung kommt als nächste an?"

Beispiel:
  ZADD          live_etas  1717866312  SHIP-0ad35c11    (bei TransportStarted)
  ZREM          live_etas  SHIP-0ad35c11                 (bei DeliveryCompleted)
  ZRANGE        live_etas 0 0 WITHSCORES                 → nächste Ankunft
  ZRANGE        live_etas 0 -1 WITHSCORES                → alle Sendungen nach ETA
  ZRANGEBYSCORE live_etas -inf <heute_24h>               → Ankünfte bis heute
```

**Warum SORTED SET:** Die Ankunftszeit (`estimated_arrival`) liegt fertig im `TransportStarted`-Event vor – sie wird **nicht berechnet**, nur als Score abgelegt. Der Score erlaubt zeitlich sortierte Abfragen ohne PostgreSQL-Roundtrip: „nächste Ankunft" (`ZRANGE 0 0`), „alle Ankünfte heute" (`ZRANGEBYSCORE`). `ZCARD live_etas` muss `SCARD active_shipments` entsprechen – beide bilden dieselbe Menge aktiver Sendungen ab und dienen als gegenseitiger Konsistenznachweis.

---

### 3.8 Bewusst nicht modelliert: `warehouse_queue`

Kapitel 5, Folie 7 nennt als Beispiel auch eine `warehouse_queue`. Sie wird **bewusst nicht** umgesetzt: Die WMS-`NodeProcessed`-Events tragen ausschließlich `status: "COMPLETED"` – der Simulator erzeugt keinen Wartezustand (`PENDING`/`QUEUED`) und kein getrenntes „Batch verlässt Station"-Event. Eine echte Warteschlange (*was wartet noch auf Bearbeitung?*) ist aus den Daten nicht ableitbar; eine LIST würde nur als Verarbeitungs-Historie wachsen, ohne definiertes `LPOP`-Signal. Der Wartezustand ließe sich nur durch erfundene Events simulieren – fachlich nicht belegbar. Die Bearbeitungsreihenfolge je Station ist bei Bedarf bereits über MongoDB (`batch_tracking.nodes_processed[]`) und Neo4j (`PROCESSED_AT`) abgedeckt.

---

## 4. TTL-Übersicht

| Key-Pattern                            | TTL          | Begründung                                          |
|----------------------------------------|--------------|-----------------------------------------------------|
| `shipment:status:<id>` (IN_TRANSIT)    | 7 Tage       | Maximale Transportdauer                             |
| `shipment:status:<id>` (final)         | 30 Tage      | Nachweisfähig bis Monatsende                        |
| `shipment:info:<id>`                   | 7 Tage       | Wie Status                                          |
| `shipment:position:<id>`               | 1 Stunde     | GPS-Daten veralten schnell                          |
| `shipment:route:<id>`                  | 3 Tage       | Kurzer Verlauf für Live-Map                         |
| `shipment:alert:temperature:<id>`      | 24 Stunden   | Alert erlischt ohne neue Verletzung automatisch     |
| `order:status:<ref>`                   | 30 Tage      | Order-Lifecycle bis Abschluss                       |
| `order:meta:<ref>`                     | 30 Tage      | Wie Status                                          |
| `order:timeline:<ref>`                 | 30 Tage      | Wie Status                                          |
| `cache:product:<code>`                 | 1 Stunde     | Stammdaten stabil, kurzer Cache spart Speicher      |
| `monitoring:temp_violations:<date>`    | 7 Tage       | Tagesliste → granular löschbar, kein Speicherleak   |
| `system:counter:orders_today`          | bis Mitternacht | EXPIREAT für automatischen Tagesreset            |
| `system:counter:active_shipments`      | kein TTL     | Dashboard-Counter muss persistent sein              |
| `active_shipments` (SET)               | kein TTL     | Live-Zustand; wird zu Beginn jedes ETL-Laufs geleert |
| `live_etas` (SORTED SET)               | kein TTL     | Live-Zustand; wird zu Beginn jedes ETL-Laufs geleert |
| `system:counter:etl_runs`              | kein TTL     | Betriebsnachweis                                    |

---

## 5. Redis-Datentypen – Begründung der Auswahl

| Datentyp    | Eingesetzt für                     | Warum dieser Typ                                                   |
|-------------|------------------------------------|--------------------------------------------------------------------|
| STRING      | Status-Flags, Counter, Alert-Flag  | Atomar; Counter via INCR/DECR ohne Race Conditions                 |
| HASH        | Metadaten (Info, Meta, Position)   | Einzelne Felder gezielt lesbar (HGET), kein JSON-Parsing nötig     |
| LIST        | Status-Timeline                    | Reihenfolge erhalten; RPUSH hängt chronologisch hinten an          |
| SORTED SET  | Positionsverlauf, Temp-Monitoring, Live-ETAs | Score = Timestamp/Temperaturwert/Ankunftszeit → zeitlich/schwerebasiert sortierbar |
| SET         | Aktive Sendungen (`active_shipments`) | Eindeutige Mitgliedschaft; O(1)-Prüfung (SISMEMBER), dedupliziert automatisch |

---

## 6. Redis vs. andere Systeme: Abgrenzung

| Anforderung                  | Redis         | MongoDB         | PostgreSQL      |
|------------------------------|---------------|-----------------|-----------------|
| Aktueller Shipmentstatus     | **✓ (µs)**    | Langsamer       | Langsam         |
| GPS-Positionsverlauf (kurz)  | ✓ (3 Tage)    | **✓ (vollständig)** | Möglich     |
| Historische Analysen         | ✗             | ✓               | **✓**           |
| Komplexe Abfragen            | ✗             | ✓               | **✓**           |
| Dashboard-Counter            | **✓**         | Möglich         | Langsamer       |
| TTL / Auto-Expiry            | **✓ nativ**   | TTL-Index       | Aufwendig       |
| Persistenz                   | Begrenzt      | **✓**           | **✓**           |
| Kühlketten-Alert-Flag        | **✓**         | Überdimensioniert | Überdimensioniert |

**Fazit:** Redis ergänzt MongoDB und PostgreSQL – es ist kein Ersatz. Echtzeitzustände und volatile Flags liegen in Redis, der kurze GPS-Verlauf ebenfalls. Vollständige Shipment-Historien landen in MongoDB (`shipment_events`-Collection). Aggregierte Analysen und KPIs kommen aus dem PostgreSQL-DWH.

---

## 7. ETL-Nachweis

Die Funktion `load_redis(erp_events, tms_events, r)` in `bananasupplychain/etl_load.py` verarbeitet:

| Eventtyp               | Quelle | Redis-Schreiboperationen                                              |
|------------------------|--------|-----------------------------------------------------------------------|
| `OrderCreated`         | ERP    | `order:status`, `order:meta`, `order:timeline`, `cache:product`, INCR `orders_today` |
| `TransportStarted`     | TMS    | `shipment:status` (IN_TRANSIT), `shipment:info`, INCR `system:counter:active_shipments`, SADD `active_shipments` (SET), ZADD `live_etas` (SORTED SET) |
| `ShipmentPositionUpdated` | TMS | `shipment:position`, `shipment:route`, ggf. `shipment:alert:temperature`, `monitoring:temp_violations:<date>`, INCR `temperature_alerts_active` |
| `DeliveryCompleted`    | TMS    | `shipment:status` (final), INCR `deliveries_<status>`, DECR `system:counter:active_shipments`, SREM `active_shipments` (SET), ZREM `live_etas` |

**Prüfabfragen (nach ETL-Lauf via redis-cli):**
```
# Aktive Transporte (Anzahl)
GET system:counter:active_shipments

# Aktive Transporte (welche – SET-Mitglieder)
SMEMBERS active_shipments
SCARD active_shipments          # muss der Zahl oben entsprechen

# Geschätzte Ankunftszeiten (Sendungen nach ETA sortiert)
ZRANGE live_etas 0 -1 WITHSCORES
ZCARD live_etas                 # muss SCARD active_shipments entsprechen

# Bestellungen heute
GET system:counter:orders_today

# Temperaturverstösse heute
ZRANGE monitoring:temp_violations:20260515 0 -1 WITHSCORES

# ETL-Laufzähler
GET system:counter:etl_runs

# Beispiel Shipment-Status
GET shipment:status:SHIP-67e67f7c

# Beispiel GPS-Position
HGETALL shipment:position:SHIP-67e67f7c

# Produktcache
HGETALL cache:product:BAN-101

# Alle Keys im Überblick
KEYS *
```
