# Data Model: Fix Fintoc Bank Account Sync

**Feature**: 003-fix-fintoc-integration
**Date**: 2026-06-25

## Summary

No schema changes required. This fix reuses all existing models unchanged.
The only data-model difference from spec 002 is a clarification to `external_id`:
the `link_token` is stored directly (it is the unique Fintoc Link identifier).

---

## Existing Models (No Changes)

### BankConnection

**Table**: `bank_connections`

| Field | Fintoc value |
|---|---|
| `provider` | `"fintoc"` |
| `external_id` | Fintoc `link_token` (unique per user per institution) |
| `credentials` | `{"link_token_enc": "<encrypted link_token>"}` |
| `institution_name` | From `accounts[0].institution_name` returned by `GET /accounts` |
| `logo_url` | From Fintoc account's institution `logo_url` (nullable) |
| `status` | `"active"` on success; `"expired"` on 401/410; `"error"` on other failures |
| `last_sync_at` | Updated after each successful sync |

**Credential encryption**: Uses the existing `fernet`-based encryption in `connection_service`.

---

### Account

**Table**: `accounts`

| Field | Fintoc source |
|---|---|
| `connection_id` | FK → `BankConnection.id` |
| `external_id` | Fintoc `account.id` (UUID string) |
| `name` | `account.name` |
| `type` | Mapped from `account.type` (see mapping below) |
| `balance` | `account.balance.available` (fallback: `account.balance.current`) |
| `currency` | `account.currency` (always `"CLP"` for Chilean accounts) |
| `credit_limit` | `null` — not exposed by Fintoc |
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

| Field | Fintoc source |
|---|---|
| `account_id` | FK → `Account.id` |
| `external_id` | Fintoc `movement.id` (unique per movement) |
| `date` | `movement.post_date` (settlement date) |
| `amount` | Signed decimal: negative for `type=charge`, positive for `type=deposit` |
| `currency` | `movement.currency` (always `"CLP"` for Chilean accounts) |
| `description` | `movement.description` |
| `status` | `"posted"` (Fintoc only returns posted movements) |

#### Amount Sign Convention

| Fintoc `movement.type` | `amount` sign | Meaning |
|---|---|---|
| `charge` | Negative | Money leaving the account (debit) |
| `deposit` | Positive | Money entering the account (credit) |

CLP amounts from Fintoc are whole integers (no decimal scaling needed).
