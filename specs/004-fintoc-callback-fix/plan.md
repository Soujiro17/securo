# Implementation Plan: Fintoc Callback Fix

**Feature**: 004-fintoc-callback-fix
**Created**: 2026-06-27
**Spec**: spec.md

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, httpx (async HTTP client)
- **Frontend**: React 19, TypeScript, Vite, `@fintoc/fintoc-js` SDK
- **Infrastructure**: Docker, docker-compose

## Project Structure

```
backend/
  app/
    providers/
      fintoc.py           ← handle_oauth_callback + create_connect_token (MODIFY)
frontend/
  src/
    hooks/
      use-fintoc-widget.ts  ← FintocConnectWidget component (MODIFY)
    components/
      bank-connect-dialog.tsx  ← dialog rendering Fintoc path (MODIFY)
```

## Design Decisions

### D1: Widget initialization — no server token required

The Fintoc `movements` widget does NOT need a server-side `widget_token`. Initializing with only `publicKey`, `product: "movements"`, `holderType: "individual"`, and `country: "cl"` is the correct approach for data aggregation. The `widget_token` pattern applies to subscriptions (direct debit) only.

**Impact**: Remove `create_connect_token` Fintoc API call; skip `getConnectToken` call in frontend for Fintoc path.

### D2: onSuccess delivers link_token directly

For the movements product, the Fintoc widget fires `onSuccess(data)` where `data.link_token` is the long-lived credential. There is no intermediate `exchange_token` step. The fallback chain `data?.exchange_token || data?.id || ...` is wrong because `data.id` may resolve to the wrong value.

**Impact**: Replace fallback chain with `data.link_token` exclusively.

### D3: Backend uses link_token directly — no POST /links exchange

The backend `handle_oauth_callback(code)` receives `code = link_token`. It calls `GET /v1/accounts?link_token={code}` directly. No `GET /links/exchange` call. The `link_token` is stored as the credential and `external_id`.

**Impact**: Rewrite `handle_oauth_callback` to remove exchange step.

### D4: institution_name extraction

The Fintoc accounts response includes `institution: { name: str, logo_url: str }`. Institution name is extracted from `accounts[0]["institution"]["name"]`, with `"Chilean Bank"` as fallback for empty lists.

**Impact**: Fix `handle_oauth_callback` to read from the nested institution object.

### D5: Reconnect path unchanged in shape

For reconnect (existing `BankConnection`), the same Fintoc widget path is used — no server token needed. The widget issues a fresh `link_token` on success. The reconnect sync endpoint already exists; the task is to ensure `bank-connect-dialog.tsx` routes the Fintoc reconnect path consistently.

## File Change Summary

| File | Change Type | Description |
|---|---|---|
| `frontend/src/hooks/use-fintoc-widget.ts` | Modify | Remove `widgetToken` prop, fix `Fintoc.create()` params, fix `onSuccess` |
| `frontend/src/components/bank-connect-dialog.tsx` | Modify | Skip `getConnectToken` for Fintoc path, pass no `widgetToken` |
| `backend/app/providers/fintoc.py` | Modify | `create_connect_token` → no-op; `handle_oauth_callback` → direct link_token usage |

## Contract Reference

Full API contract is documented in `../003-fix-fintoc-integration/contracts/fintoc-provider.md`.

## No Schema Changes

No Alembic migrations required. `BankConnection.credentials` already stores arbitrary JSON (encrypted). Changing the stored dict from `{"link_token": x}` to `{"link_token": x}` (same key, different source) requires no migration.
