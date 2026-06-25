# Quickstart: Validate Fintoc Bank Account Sync

**Feature**: 003-fix-fintoc-integration
**Date**: 2026-06-25

Use this guide to validate the corrected Fintoc integration end-to-end in the sandbox
environment before promoting to production.

---

## Prerequisites

1. `FINTOC_PUBLIC_KEY` set to a `pk_test_…` sandbox key
2. `FINTOC_SECRET_KEY` set to the corresponding sandbox secret
3. `VITE_FINTOC_PUBLIC_KEY` set to the same `pk_test_…` key in the frontend build
4. Backend running (`docker-compose up` or `uvicorn app.main:app`)
5. Frontend running (`pnpm dev` in `frontend/`)
6. A test user account in Securo
7. Fintoc sandbox credentials for a Chilean bank (e.g., Banco de Chile test user)

---

## Scenario 1: Full Connection Flow (Happy Path)

### Steps

1. Log in to Securo as the test user
2. Navigate to **Accounts**
3. Click **"Connect bank account"** and select the Fintoc / Chilean bank option
4. The Fintoc widget should open with a bank selection screen (no error about `widgetToken`)
5. Select **Banco de Chile** (or any sandbox-supported institution)
6. Enter the test credentials provided by Fintoc for the sandbox
7. Complete any MFA step shown by the widget
8. The widget closes automatically

### Expected outcome

- A toast notification: "Connected" (or equivalent i18n string)
- One or more accounts appear in the Accounts list within 5–10 seconds
- Each account shows: bank name, account type (checking/savings), and current balance in CLP
- No error toast; no blank/empty account cards

### Verify in the database

```sql
SELECT id, provider, external_id, institution_name, status, last_sync_at
FROM bank_connections
WHERE provider = 'fintoc'
ORDER BY created_at DESC
LIMIT 1;
```

Expected:
- `provider = 'fintoc'`
- `external_id` = a Fintoc `link_token` string (starts with `lt_…` in sandbox)
- `status = 'active'`
- `institution_name` = e.g., `"Banco de Chile"`

```sql
SELECT id, external_id, name, type, balance, currency
FROM accounts
WHERE connection_id = '<id from above>';
```

Expected: One or more rows with non-null balance and `currency = 'CLP'`.

```sql
SELECT COUNT(*), MIN(date), MAX(date)
FROM transactions
WHERE account_id IN (
  SELECT id FROM accounts WHERE connection_id = '<connection_id>'
);
```

Expected: `COUNT` > 0, `MIN(date)` ≥ today − 90 days.

---

## Scenario 2: Re-sync Does Not Duplicate Transactions

### Steps

1. Record the transaction count from Scenario 1
2. Navigate to **Accounts** → click the connected bank account → **Sync**
   (or POST `/api/connections/{id}/sync`)
3. Wait for the sync to complete

### Expected outcome

- Transaction count is unchanged (no new rows if no new movements at the bank)
- No error toast

---

## Scenario 3: Widget Cancelled — No Orphan Records

### Steps

1. Click **"Connect bank account"**
2. When the Fintoc widget opens, click **Close / X** immediately (do not authenticate)

### Expected outcome

- The dialog closes with no error toast
- No new `bank_connections` or `accounts` rows in the database

---

## Scenario 4: Backend Unit Tests Pass

```bash
cd backend
pytest tests/test_providers_fintoc.py -v
```

Expected: All tests pass, including:
- `test_handle_oauth_callback_uses_link_token_directly` (new/updated)
- `test_create_connect_token_returns_stub` (updated)
- `test_get_accounts_*`
- `test_get_transactions_*`

---

## Common Problems

| Symptom | Likely cause |
|---|---|
| Widget shows "Invalid public key" | `VITE_FINTOC_PUBLIC_KEY` not set or wrong env |
| Widget opens but spinner never resolves | `widgetToken` was passed (Bug A) — check fix is deployed |
| Backend 422 / "Invalid exchange_token" | `POST /links` exchange call still present (Bug C) |
| Transaction count = 0 after connection | `link_token` arrived as `undefined` (Bug B) — check `onSuccess` fix |
| "Chilean Bank" as institution name | `accounts` list was empty at `GET /accounts` time (check Fintoc sandbox connectivity) |
