# Quickstart: Fintoc Integration Validation Guide

**Feature**: 002-fintoc-integration
**Date**: 2026-06-24

This guide validates the Fintoc integration end-to-end using Fintoc's sandbox environment.
All steps assume the development stack is running.

---

## Prerequisites

1. A Fintoc sandbox account at [fintoc.com/dashboard](https://app.fintoc.com).
2. Sandbox credentials:
   - `FINTOC_SECRET_KEY=sk_sandbox_...` (from Fintoc dashboard → API Keys)
   - `VITE_FINTOC_PUBLIC_KEY=pk_sandbox_...` (from Fintoc dashboard → API Keys)
3. Stack running: `docker compose up -d`
4. Environment variables set in `.env` (root, or `backend/.env` and `frontend/.env`).

---

## Scenario 1: Provider appears in provider list

**Goal**: Confirm Fintoc is returned when secret key is configured.

```bash
# Call the providers endpoint
curl -s http://localhost:3000/api/connections/providers \
  -H "Cookie: <auth-cookie>" | jq '.[] | select(.name == "fintoc")'
```

**Expected**:
```json
{
  "name": "fintoc",
  "display_name": "Fintoc",
  "flow_type": "widget",
  "configured": true
}
```

---

## Scenario 2: Widget token is created

**Goal**: Backend generates a valid Fintoc widget token.

```bash
curl -s -X POST http://localhost:3000/api/connections/connect-token \
  -H "Content-Type: application/json" \
  -H "Cookie: <auth-cookie>" \
  -d '{"provider": "fintoc"}'
```

**Expected**: `200 OK` with `{"access_token": "wt_sandbox_..."}`.

---

## Scenario 3: Connect a Chilean bank account (end-to-end via UI)

**Goal**: User connects a Fintoc sandbox bank account and transactions are imported.

1. Open the Securo UI at `http://localhost:3000`.
2. Go to **Accounts** → **Add account** → Select **Fintoc**.
3. FintocLink widget opens.
4. In the widget, select any sandbox institution (e.g., "Banco de Chile (Sandbox)").
5. Enter sandbox credentials (provided in Fintoc dashboard under "Sandbox test accounts").
6. Widget closes with success.

**Verify in UI**:
- A new connection "Banco de Chile" appears in the connections list.
- One or more accounts are imported (checking/savings).
- Transactions are listed in the account view.

**Verify via API**:
```bash
curl -s http://localhost:3000/api/connections \
  -H "Cookie: <auth-cookie>" | jq '.[] | select(.provider == "fintoc")'
```

**Expected**: connection with `status: "active"`, `last_sync_at` set, accounts populated.

---

## Scenario 4: Manual sync fetches new transactions

**Goal**: Subsequent sync does not create duplicate transactions.

```bash
# Get the connection ID from Scenario 3
CONNECTION_ID=<uuid>

# Trigger manual sync
curl -s -X POST http://localhost:3000/api/connections/$CONNECTION_ID/sync \
  -H "Cookie: <auth-cookie>"
```

**Expected**: `200 OK` with `new_transactions: 0` (no duplicates on re-sync of same data).

---

## Scenario 5: Institution list

**Goal**: Supported Chilean banks are returned.

```bash
curl -s "http://localhost:3000/api/connections/fintoc/institutions?country=cl" \
  -H "Cookie: <auth-cookie>" | jq '.institutions | length'
```

**Expected**: number > 0 (Fintoc sandbox exposes at least one institution).

---

## Scenario 6: Expired connection surfaces reconnect prompt

**Goal**: When a Fintoc token becomes invalid, the connection status transitions to `expired`.

1. In Fintoc dashboard, revoke the link for the sandbox account.
2. Trigger a sync: `POST /api/connections/{id}/sync`.
3. Check connection status:

```bash
curl -s http://localhost:3000/api/connections/$CONNECTION_ID \
  -H "Cookie: <auth-cookie>" | jq '.status'
```

**Expected**: `"expired"`. UI should show a "Reconnect" prompt.

---

## Scenario 7: Provider not listed when unconfigured

**Goal**: Fintoc is not registered when `FINTOC_SECRET_KEY` is unset.

1. Temporarily unset `FINTOC_SECRET_KEY` and restart the backend.
2. Call `GET /api/connections/providers`.

**Expected**: Fintoc either absent from the list or present with `"configured": false`.

---

## Scenario 8: Unit tests pass

```bash
docker compose exec backend pytest tests/test_providers_fintoc.py -v
```

**Expected**: All tests pass. Key test cases covered:
- `test_handle_oauth_callback_success`
- `test_get_accounts`
- `test_get_transactions_incremental`
- `test_get_transactions_no_duplicates`
- `test_refresh_credentials_expired_raises`
- `test_list_institutions`
- `test_rate_limited_raises_provider_rate_limited`

---

## Scenario 9: Frontend i18n strings present

**Goal**: Provider description renders in all supported locales.

1. Open the UI in a non-English locale.
2. Navigate to **Add account**.
3. Verify the Fintoc provider shows a localized description (not the translation key).

---

## Cleanup

```bash
# Remove test connection
curl -s -X DELETE http://localhost:3000/api/connections/$CONNECTION_ID \
  -H "Cookie: <auth-cookie>"
```
