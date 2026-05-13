# Redis Echtzeit-Modell – Banana Supply Chain

**Modul:** Datenmanagement und Analytics (M.Sc.), SoSe 26  
**Stand:** 2026-05-12

---

## 1. Warum Redis für Echtzeitdaten?

Redis ist eine **In-Memory-Datenbank**, die Daten im Arbeitsspeicher hält und dadurch Sub-Millisekunden-Latenz erreicht. In der Banana Supply Chain sind Echtzeitanforderungen vor allem im Bereich:

- **Shipment-Tracking**: Wo befindet sich Sendung SHIP-xyz gerade?
- **Order-Status-Monitoring**: Welchen Status hat Order ORD-abc?
- **Dashboard-Metriken**: Wie viele aktive Transporte gibt es gerade?
- **Kühlketten-Alerts**: Ist die Containertemperatur gerade außerhalb des Grenzwerts?

Diese Anforderungen können mit PostgreSQL oder MongoDB nicht mit Sub-Millisekunden-Latenz beantwortet werden. Redis ist dafür ausgelegt.

**Konfiguration laut `docker-compose.yml`:**
```
--maxmemory 256mb
--maxmemory-policy allkeys-lru   (least recently used: älteste Keys werden verdrängt)
--appendonly no                  (kein persistentes Log → reine Echtzeit-Cache-Rolle)
```

---

## 2. Key-Naming-Konvention

```
<namespace>:<entity>:<identifier>:<attribute>

Beispiele:
  shipment:status:SHIP-abc123           → aktueller Shipment-Status
  shipment:position:SHIP-abc123         → aktuelle GPS-Position
  order:status:ORD-xyz456               → aktueller Order-Status
  system:counter:active_shipments       → Anzahl aktiver Transporte
  cache:product:BAN-101                 → gecachtes Produktobjekt
```

---

## 3. Key-Strukturen im Detail

### 3.1 Shipment-Tracking

#### Aktueller Shipmentstatus
```
Key:     shipment:status:<shipment_identifier>
Type:    STRING
Value:   "IN_TRANSIT" | "DELIVERED" | "COMPLETED" | "DELAYED"
TTL:     7 Tage (nach Delivery automatisch verfallend)

Beispiel:
  SET    shipment:status:SHIP-bf5d4354 "IN_TRANSIT"  EX 604800
  GET    shipment:status:SHIP-bf5d4354
  → "IN_TRANSIT"
```

#### Aktuelle GPS-Position (Hash)
```
Key:     shipment:position:<shipment_identifier>
Type:    HASH
Fields:  latitude, longitude, temperature, speed_kmh, updated_at
TTL:     1 Stunde (GPS-Position wird regelmäßig überschrieben)

Beispiel:
  HSET   shipment:position:SHIP-bf5d4354
         latitude   -13.286561
         longitude  174.034529
         temperature 13.39
         speed_kmh  59.85
         updated_at "2026-05-12T12:00:00"
  EX     3600

  HGETALL shipment:position:SHIP-bf5d4354
  → { latitude: -13.286561, longitude: 174.034529, temperature: 13.39, ... }
```

#### Kühlketten-Alert-Flag
```
Key:     shipment:alert:temperature:<shipment_identifier>
Type:    STRING
Value:   "ALERT" (nur gesetzt wenn Temperatur außerhalb 10-15°C)
TTL:     24 Stunden

Beispiel:
  SET    shipment:alert:temperature:SHIP-bf5d4354 "ALERT"  EX 86400
  EXISTS shipment:alert:temperature:SHIP-bf5d4354
  → 1 (Alert aktiv) oder 0 (kein Alert)
```

#### Positionsverlauf (Sorted Set)
```
Key:     shipment:route:<shipment_identifier>
Type:    SORTED SET
Score:   Unix-Timestamp des GPS-Updates
Member:  JSON-String mit {lat, lon, temp, ts}
TTL:     3 Tage

Zweck:   Kurzer Positionsverlauf für Live-Map ohne DB-Abfrage

Beispiel:
  ZADD   shipment:route:SHIP-bf5d4354
         1715514000 '{"lat":-13.29,"lon":174.03,"temp":13.39}'
  ZRANGE shipment:route:SHIP-bf5d4354 0 -1 WITHSCORES
  → alle GPS-Punkte chronologisch sortiert
```

---

### 3.2 Order-Tracking

#### Aktueller Order-Status
```
Key:     order:status:<order_reference>
Type:    STRING
Value:   "CREATED" | "HARVESTED" | "IN_TRANSIT" | "DELIVERED"
TTL:     30 Tage

Beispiel:
  SET    order:status:ORD-0f7dc974 "IN_TRANSIT"  EX 2592000
  GET    order:status:ORD-0f7dc974
  → "IN_TRANSIT"
```

#### Order-Metadaten (Hash)
```
Key:     order:meta:<order_reference>
Type:    HASH
Fields:  customer_number, customer_name, product_code, quantity, priority, created_at
TTL:     30 Tage

Beispiel:
  HSET   order:meta:ORD-0f7dc974
         customer_number "CUST-109"
         customer_name   "AUCHAN"
         product_code    "BAN-108"
         quantity        760
         priority        "NORMAL"
         created_at      "2026-05-12T11:50:40"

  HGET   order:meta:ORD-0f7dc974  customer_name
  → "AUCHAN"
```

#### Status-Timeline (List)
```
Key:     order:timeline:<order_reference>
Type:    LIST
Value:   Chronologische Status-Änderungen
TTL:     30 Tage

Beispiel:
  RPUSH  order:timeline:ORD-0f7dc974  "2026-05-12T11:50 - CREATED"
  RPUSH  order:timeline:ORD-0f7dc974  "2026-05-12T11:51 - HARVESTED"
  RPUSH  order:timeline:ORD-0f7dc974  "2026-05-12T12:00 - IN_TRANSIT"

  LRANGE order:timeline:ORD-0f7dc974 0 -1
  → ["2026-05-12T11:50 - CREATED", "2026-05-12T11:51 - HARVESTED", ...]
```

---

### 3.3 Systemzähler (Counter)

```
Key:     system:counter:active_shipments
Type:    STRING (Integer)
Value:   Anzahl aktiver Transporte
TTL:     Kein TTL (persistent für Dashboard)

Key:     system:counter:orders_today
Type:    STRING (Integer)
Value:   Anzahl Bestellungen heute
TTL:     Automatischer Reset um Mitternacht (via EXPIREAT auf Tagesende)

Key:     system:counter:deliveries_successful_today
Type:    STRING (Integer)
Value:   Erfolgreiche Lieferungen heute

Key:     system:counter:temperature_alerts_active
Type:    STRING (Integer)
Value:   Aktuell aktive Kühlketten-Alerts

Beispiel:
  INCR   system:counter:active_shipments
  DECR   system:counter:active_shipments    (bei Abschluss)
  GET    system:counter:active_shipments
  → "12"
```

---

### 3.4 Produktstammdaten-Cache

```
Key:     cache:product:<product_code>
Type:    HASH
Fields:  product_name, category, supplier_code, supplier_name
TTL:     1 Stunde (Stammdaten ändern sich selten)

Zweck:   Schneller Zugriff auf Produktnamen ohne PostgreSQL-Abfrage
         (für Dashboard-Anzeige von Shipment-Details)

Beispiel:
  HSET   cache:product:BAN-101
         product_name  "Cavendish Banana"
         category      "Fresh Fruit"
         supplier_code "SUP-104"
         supplier_name "Banana Kingdom"
  EX     3600

  HGET   cache:product:BAN-101  product_name
  → "Cavendish Banana"
```

---

### 3.5 Temperatur-Monitoring (Sorted Set)

```
Key:     monitoring:temp_violations:<date>
Type:    SORTED SET
Score:   Temperaturwert
Member:  "<shipment_identifier>:<timestamp>"
TTL:     7 Tage

Zweck:   Alle Temperaturverstösse des Tages sortiert nach Schwere

Beispiel:
  ZADD   monitoring:temp_violations:20260512
         16.5  "SHIP-abc123:2026-05-12T12:00"    (zu warm)
         9.2   "SHIP-def456:2026-05-12T13:00"    (zu kalt)

  ZRANGEBYSCORE monitoring:temp_violations:20260512 16.0 +inf
  → alle Shipments mit Temperatur > 16°C heute
```

---

## 4. Redis vs. andere Systeme: Abgrenzung

| Anforderung | Redis | MongoDB | PostgreSQL |
|---|---|---|---|
| Aktueller Shipmentstatus | **✓ (µs)** | Langsamer | Langsam |
| GPS-Positionsverlauf | ✓ (begrenzt) | **✓ (vollständig)** | Möglich |
| Historische Analysen | ✗ | ✓ | ✓ |
| Komplexe Abfragen | ✗ | ✓ | **✓** |
| Dashboard-Counter | **✓** | Möglich | Langsamer |
| TTL/Auto-Expiry | **✓** | Möglich | Aufwendig |
| Persistenz | Begrenzt | **✓** | **✓** |

**Fazit:** Redis ergänzt MongoDB und PostgreSQL – es ist kein Ersatz. Echtzeitzustände liegen in Redis, historische Daten in MongoDB/PostgreSQL. Bei hoher Last werden PostgreSQL-Abfragen durch Redis-Cache beschleunigt.
