# CityPulse Sync API

All protected endpoints require header:

- `X-CityPulse-Secret: <CITYPULSE_API_SECRET>`

Content type for POST JSON:

- `Content-Type: application/json`

## Health

### `GET /api/health/`

Response:

```json
{
  "ok": true,
  "service": "citypulse-web",
  "timestamp": "2026-05-09T08:00:00Z"
}
```

## Sync clients

### `POST /api/sync/clients/`

Example request:

```json
{
  "clients": [
    {"id": 1, "name": "Acme"}
  ]
}
```

Response:

```json
{
  "ok": true,
  "message": "clients synced",
  "received": 1
}
```

## Sync routes

### `POST /api/sync/routes/`

Example request:

```json
{
  "routes": [
    {
      "vehicle_id": "VEH-1",
      "driver_id": "DRV-8",
      "planned_date": "2026-05-09",
      "stops": ["Stop A", "Stop B"]
    }
  ]
}
```

Response:

```json
{
  "ok": true,
  "message": "routes synced",
  "received": 1
}
```

## Pull confirmations

### `GET /api/deliveries/confirmations/`

Response:

```json
{
  "ok": true,
  "data": [
    {
      "order_id_ext": "ORD-1",
      "order_ref": "ORD-20260509-0001",
      "status": "delivered",
      "eta": "2026-05-09T11:00:00Z",
      "last_update": "2026-05-09T10:45:00Z"
    }
  ],
  "count": 1
}
```

## Pull proofs

### `GET /api/deliveries/proofs/`

Response:

```json
{
  "ok": true,
  "data": [
    {
      "order_id_ext": "ORD-1",
      "photo_url": "/media/proofs/example.jpg",
      "signature": "Signed by client",
      "confirmed_at": "2026-05-09T10:45:00Z"
    }
  ],
  "count": 1
}
```

## Push delivery confirmation

### `POST /api/deliveries/confirm/`

Example request:

```json
{
  "order_id_ext": "ORD-1",
  "order_ref": "ORD-20260509-0001",
  "status": "delivered",
  "eta": "2026-05-09T11:00:00",
  "signature": "Delivered to reception"
}
```

Response:

```json
{
  "ok": true,
  "message": "delivery confirmation stored",
  "order_ref": "ORD-20260509-0001"
}
```

## Error schema

Unauthorized:

```json
{
  "ok": false,
  "error": "unauthorized"
}
```
