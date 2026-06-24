# Data Model: Fintoc Bank Integration

**Feature**: 002-fintoc-integration
**Date**: 2026-06-24

## Summary

No new ORM models or Alembic migrations are required. The Fintoc integration reuses all existing
models. This section documents how Fintoc-specific data maps to existing fields.

---

## Existing Models (No Changes)

### BankConnection

**Table**: `bank_connections`

| Field | Fintoc value |
|---|---|
| `provider` | `"fintoc"` |
| `external_id` | Fintoc `link_token` (plain, used as the unique per-connection identifier) |
| `credentials` | `{"link_token_enc": "<encrypted link_token>"}` |
| `institution_name` | From Fintoc `link_intent` or account holder data (e.g., `"Banco de Chile"`) |
| `logo_url` | From Fintoc institution `logo_url` (nullable) |
| `status` | `"active"` | `"expired"` (on 401/410) | `"error"` |
| `settings` | `{"payee_source": "description"}` (default; no Fintoc-specific settings required) |
| `last_sync_at` | Updated after each successful sync |

**Credential encryption**: Uses the existing `fernet`-based encryption applied by `connection_service`
before persisting and decrypting before provider calls.

---

### Account

**Table**: `accounts`

| Field | Fintoc source |
|---|---|
| `connection_id` | FK → `BankConnection.id` |
| `external_id` | Fintoc `account.id` (UUID string) |
| `name` | `account.name` |
| `type` | Mapped from `account.type` (see type mapping below) |
| `balance` | `account.balance.available` (or `current` if `available` is null) |
| `currency` | `account.currency` (always `"CLP"` for Chilean accounts) |
| `credit_limit` | `null` — Fintoc does not expose credit limit for credit accounts |
| `statement_close_day` | `null` — not exposed by Fintoc |
| `payment_due_day` | `null` — not exposed by Fintoc |

#### Account Type Mapping

| Fintoc `account.type` | Securo `Account.type` | Notes |
|---|---|---|
| `checking_account` | `checking` | Standard current account |
| `savings_account` | `savings` | Savings (cuenta de ahorro) |
| `vista_account` | `checking` | Cuenta Vista / Cuenta RUT — demand deposit |
| *(unknown)* | `checking` | Safe default |

---

### Transaction

**Table**: `transactions`

Fintoc calls transactions "movements" (`/movements`).

| Field | Fintoc source |
|---|---|
| `account_id` | FK → `Account.id` (matched via `Account.external_id = movement.account_id`) |
| `external_id` | `movement.id` (string, stable across API calls) |
| `description` | `movement.description` |
| `amount` | `Decimal(str(movement.amount))` — CLP integer, always positive in API |
| `currency` | `movement.currency` (always `"CLP"`) |
| `date` | `movement.post_date` (ISO date string; fall back to `transaction_date`) |
| `type` | `"debit"` if `movement.type == "charge"` else `"credit"` |
| `status` | `"posted"` (Fintoc only returns settled movements; no pending state exposed) |
| `payee` | `null` — Fintoc does not expose structured payee data; description is used directly |
| `source` | `"sync"` |
| `raw_data` | Full movement JSON for auditability |

#### Fintoc Movement Type → Securo Transaction Type

| Fintoc `movement.type` | Securo `Transaction.type` | Meaning |
|---|---|---|
| `charge` | `debit` | Money leaving the account |
| `deposit` | `credit` | Money entering the account |

**Note on amounts**: Securo stores `Transaction.amount` as a signed decimal
(negative for debit, positive for credit). The `connection_service` applies the sign based on
`TransactionData.type`; `FintocProvider.get_transactions()` returns unsigned positive `amount` +
`type` field, letting the service handle sign convention consistently.

---

## New Configuration Fields (not ORM — config.py)

| Setting name | Type | Description |
|---|---|---|
| `fintoc_secret_key` | `str \| None` | Fintoc API secret key (`sk_sandbox_...` or `sk_live_...`) |

The provider self-disables (not registered) when `fintoc_secret_key` is `None`.

---

## Entities NOT needed for this integration

| Entity | Reason not needed |
|---|---|
| `CreditCardBill` | Fintoc does not expose credit card bill/fatura data |
| `Asset` / `AssetValue` | Fintoc does not expose investment/holding data |
| New ORM model | All data fits existing schemas |
| Alembic migration | No schema changes |

---

## Data Flow Diagram

```
FintocLink widget
      │ link_token (on success)
      ▼
POST /api/connections/oauth/callback?provider=fintoc&code={link_token}
      │
      ▼
FintocProvider.handle_oauth_callback(link_token)
      │ GET /v1/accounts?link_token={link_token}
      ▼
ConnectionData {
  external_id: link_token,
  institution_name: "Banco de Chile",
  credentials: {"link_token_enc": "..."},
  accounts: [AccountData, ...]
}
      │
      ▼
connection_service._handle_connection_data()
      ├── BankConnection upsert
      └── Account upsert (per AccountData)

─── Sync run ────────────────────────────────────────────
FintocProvider.get_transactions(credentials, account_id, since)
      │ GET /v1/accounts/{account_id}/movements?link_token={lt}&since={date}
      ▼
[TransactionData, ...]
      │
      ▼
connection_service._sync_transactions()
      └── Transaction upsert + duplicate detection
```
