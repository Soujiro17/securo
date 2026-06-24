# API Contracts: Fintoc Provider

**Feature**: 002-fintoc-integration
**Date**: 2026-06-24

No new API endpoints are introduced. The Fintoc provider plugs into all existing connection
endpoints. This document describes how each existing endpoint behaves for `provider=fintoc`.

---

## Existing Endpoints — Fintoc Behavior

### GET /api/connections/providers

Returns the Fintoc provider entry when `FINTOC_SECRET_KEY` is set.

**Response (Fintoc entry)**:
```json
{
  "name": "fintoc",
  "display_name": "Fintoc",
  "flow_type": "widget",
  "requires_institution_select": false,
  "configured": true,
  "description": "Connect Chilean bank accounts via Fintoc"
}
```

`configured: false` when `FINTOC_SECRET_KEY` is unset (provider still listed, just disabled).

---

### POST /api/connections/connect-token

Creates a FintocLink widget token for initiating a new connection.

**Request body**:
```json
{
  "provider": "fintoc"
}
```

**Response**:
```json
{
  "access_token": "wt_sandbox_xxxxxxxxxx"
}
```

The frontend uses `access_token` as the `widgetToken` when initializing FintocLink.js.

---

### POST /api/connections/{connection_id}/reconnect-token

Creates a FintocLink widget token in refresh mode (for re-authenticating an expired connection).

**Request body**: none

**Response**:
```json
{
  "access_token": "wt_sandbox_xxxxxxxxxx"
}
```

The frontend uses `access_token` to open FintocLink in `mode: "refresh"` with the existing
`link_token` passed as `link_intent_id`.

---

### POST /api/connections/oauth/callback

Exchanges the `link_token` from the FintocLink widget for a persisted connection.

**Request body**:
```json
{
  "provider": "fintoc",
  "code": "lt_sandbox_xxxxxxxxxxxx"
}
```

`code` is the `link_token` returned by the FintocLink `onSuccess` callback.

**Response** (success):
```json
{
  "id": "uuid",
  "provider": "fintoc",
  "institution_name": "Banco de Chile",
  "logo_url": "https://cdn.fintoc.com/institutions/banco_de_chile.png",
  "status": "active",
  "last_sync_at": null,
  "accounts": [
    {
      "id": "uuid",
      "name": "Cuenta Corriente",
      "type": "checking",
      "balance": "1500000.00",
      "currency": "CLP"
    }
  ]
}
```

**Response** (already-used token or invalid):
```json
{
  "detail": "Cannot connect: the Fintoc link token is invalid or has already been used."
}
```

---

### POST /api/connections/{connection_id}/sync

Triggers a manual sync for a Fintoc connection.

**Request**: no body

**Response** (success):
```json
{
  "connection_id": "uuid",
  "new_transactions": 42,
  "status": "active"
}
```

---

### GET /api/connections/fintoc/institutions

Lists Fintoc-supported Chilean institutions. Delegates to `FintocProvider.list_institutions(country="cl")`.

**Request**: `GET /api/connections/fintoc/institutions?country=cl`

**Response**:
```json
{
  "countries": ["cl"],
  "institutions": [
    {
      "name": "banco_de_chile",
      "display_name": "Banco de Chile",
      "country": "cl",
      "logo": "https://cdn.fintoc.com/institutions/banco_de_chile.png",
      "bic": null,
      "psu_types": ["personal"],
      "max_consent_days": null,
      "max_history_days": 90
    }
  ]
}
```

---

## Fintoc Upstream API — Summary

The FintocProvider communicates with these Fintoc REST endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/widget_tokens` | Create widget token (connect or refresh) |
| `GET` | `/v1/accounts?link_token={lt}` | List accounts after widget success |
| `GET` | `/v1/accounts/{account_id}/movements?link_token={lt}&since={date}` | Fetch transactions |
| `GET` | `/v1/institutions?country=cl` | List supported Chilean banks |

**Base URL**: `https://api.fintoc.com/v1`
**Authentication**: `Authorization: {FINTOC_SECRET_KEY}` header on every request.

---

## FintocLink Widget Contract (Frontend)

The frontend initializes FintocLink using the `widget_token` from `POST /api/connections/connect-token`.

```javascript
// Initialization
const fintoc = Fintoc.create({
  publicKey: 'pk_sandbox_xxxx',  // Fintoc public key (VITE_FINTOC_PUBLIC_KEY)
  widgetToken: data.access_token,  // from POST /api/connections/connect-token
  product: 'movements',
  onSuccess: (linkToken) => {
    // POST /api/connections/oauth/callback with code=linkToken
  },
  onExit: () => { /* close modal */ },
  onError: (error) => { /* surface error to user */ },
});
fintoc.open();
```

**New frontend environment variable**:
- `VITE_FINTOC_PUBLIC_KEY` — Fintoc public key (safe to expose to the browser; distinct from the secret key which stays server-side only).

---

## Error States

| HTTP status from Fintoc | Mapped exception | User-facing behaviour |
|---|---|---|
| 401 | `SessionExpiredError` | Connection marked expired; reconnect prompt shown |
| 403 (already-claimed token) | `ProviderUserActionRequired` | Error shown; no connection created |
| 429 | `ProviderRateLimited` | Sync skipped silently; retried on next scheduled run |
| 5xx | logged, soft-fail | Sync marked as failed; connection remains active |
