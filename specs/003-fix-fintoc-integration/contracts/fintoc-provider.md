# API Contract: Fintoc Provider (Corrected Flow)

**Feature**: 003-fix-fintoc-integration
**Date**: 2026-06-25

---

## Overview

The Fintoc bank connection flow for the `movements` product uses a **pure client-side
widget** with a single backend callback. There is no server-to-server token exchange
step.

---

## Corrected End-to-End Flow

```
Frontend                              Backend (Securo)             Fintoc API
─────────────────────────────────────────────────────────────────────────────
1. User clicks "Connect bank"
2. Render FintocConnectWidget
   (no server call needed)
3. Widget opens:
   Fintoc.create({
     publicKey,                        ← from VITE_FINTOC_PUBLIC_KEY env var
     product: "movements",
     holderType: "individual",
     country: "cl",
     onSuccess, onExit, onError
   })
4. User authenticates at bank
5. Widget fires onSuccess(data)
   data.link_token = "lt_xxx"

6. POST /api/connections/oauth/callback
   body: { code: "lt_xxx",
           provider: "fintoc" }       → handle_oauth_callback("lt_xxx")
                                         GET /v1/accounts?link_token=lt_xxx ─→
                                         ← [{ id, name, type, balance,
                                              institution: { name, logo_url } }]
                                         Create BankConnection(
                                           external_id="lt_xxx",
                                           credentials={"link_token_enc": enc("lt_xxx")},
                                           institution_name=accounts[0].institution.name
                                         )
                                         Create Account(s)
                                         For each account:
                                           GET /v1/accounts/{id}/movements?
                                             link_token=lt_xxx&since=90d_ago    ─→
                                           ← [{ id, post_date, description,
                                                amount, type, currency }]
                                           Create Transaction(s)

7. ← 201 BankConnectionRead
8. Toast: "Connected"
9. Accounts list refreshes
```

---

## Frontend Widget Initialization (Corrected)

```ts
// use-fintoc-widget.ts
Fintoc.create({
  publicKey: import.meta.env.VITE_FINTOC_PUBLIC_KEY,  // "pk_live_…" or "pk_test_…"
  product: "movements",
  holderType: "individual",
  country: "cl",
  onSuccess: (data: { link_token: string }) => handleSuccess(data.link_token),
  onExit: () => handleExit(),
  onError: () => handleExit(),
})
```

**Removed**: `widgetToken` parameter (subscriptions-only, not valid for movements).
**Added**: `holderType: "individual"`, `country: "cl"`.
**Fixed**: `onSuccess` reads `data.link_token` (was `data.exchange_token` → `undefined`).

---

## Backend: `handle_oauth_callback` (Corrected)

**Receives**: `code` = `link_token` (long-lived Fintoc Link credential)

**Step 1**: Call `GET /v1/accounts?link_token={code}`
- Authorization: `{FINTOC_SECRET_KEY}`
- Returns: array of account objects

**Step 2**: Build `AccountData` list from accounts (existing `_build_account_data`
helper, unchanged)

**Step 3**: Extract institution name from `accounts[0]["institution"]["name"]`

**Step 4**: Return `ConnectionData`:
```python
ConnectionData(
    external_id=code,                     # link_token as stable external ID
    institution_name=institution_name,    # from accounts[0].institution.name
    credentials={"link_token": code},     # encrypted at rest by connection_service
    accounts=accounts,
)
```

**Removed**: `POST /links` exchange call (not needed; `code` IS the link_token).

---

## Backend: `create_connect_token` (Stubbed)

The method is retained to satisfy the `BankProvider` ABC but returns a no-op value.
The frontend Fintoc path no longer calls this endpoint.

```python
async def create_connect_token(self, client_user_id: str, item_id=None) -> ConnectTokenData:
    return ConnectTokenData(access_token="")
```

---

## Fintoc API Endpoints Used

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/v1/accounts?link_token={lt}` | `Authorization: {secret_key}` | List accounts + institution |
| `GET` | `/v1/accounts/{id}/movements?link_token={lt}&since={date}` | `Authorization: {secret_key}` | List movements (paginated) |

**Removed**: `POST /v1/link_intents` (was used to create widget_token — not needed for movements)
**Removed**: `POST /v1/links` (was used to exchange exchange_token → link_token — not applicable)

---

## Securo API Endpoints (Unchanged)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/connections/oauth/callback` | Receive `link_token`, create BankConnection + accounts + transactions |
| `POST` | `/api/connections/connect-token` | No-op for Fintoc (frontend skips this call) |
| `GET` | `/api/connections` | List user's bank connections |
| `POST` | `/api/connections/{id}/sync` | Trigger re-sync for existing connection |

---

## Error Handling

| Fintoc API Response | Action |
|---|---|
| 401 on any call | `SessionExpiredError` → connection marked as `expired`; user prompted to reconnect |
| 404 | `ProviderUserActionRequired` |
| 429 | `ProviderRateLimited` |
| 5xx | Generic exception → connection marked as `error` |
| Empty accounts list | `ConnectionData` with empty accounts; `institution_name = "Chilean Bank"` |
