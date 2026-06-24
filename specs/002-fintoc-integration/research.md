# Research: Fintoc Bank Integration

**Feature**: 002-fintoc-integration
**Date**: 2026-06-24
**Phase**: 0 — Pre-design research

## Decision 1: SDK vs. direct HTTP client

**Decision**: Use `httpx.AsyncClient` directly (same as all existing providers), NOT the `fintoc` Python SDK.

**Rationale**: The `fintoc` pip package (v2.23.0) wraps the REST API with a synchronous `requests`-based client. Every existing provider (Pluggy, Enable Banking, SimpleFIN) uses `httpx.AsyncClient` directly. Wrapping a sync SDK via `asyncio.to_thread()` in an async FastAPI app is messy and inconsistent. Using `httpx` directly is a few extra lines of code but keeps the codebase uniform.

**Alternatives considered**:
- `fintoc` SDK: rejected — synchronous, introduces `asyncio.to_thread` pattern absent from all other providers.
- A separate async Fintoc SDK: none exists at the time of writing.

**Impact**: `fintoc` is NOT added to `pyproject.toml`. Implementation uses `httpx.AsyncClient` with `Authorization: {secret_key}` header.

---

## Decision 2: Flow type — Widget (FintocLink)

**Decision**: `flow_type = "widget"`. Fintoc uses FintocLink, a first-party JavaScript widget that handles bank selection, authentication (RUT + bank credentials), and MFA entirely inside the widget modal. This is structurally identical to Pluggy Connect.

**Rationale**: FintocLink is Fintoc's supported connection method. There is no direct OAuth redirect option for end users. The widget-based flow is already supported by the existing backend connect-token → widget → callback pattern (same as Pluggy).

**Flow**:
1. Backend calls `POST /v1/widget_tokens` → returns `widget_token`.
2. Frontend opens FintocLink.js widget with `widget_token`.
3. User selects Chilean bank, authenticates.
4. Widget fires `onSuccess(data)` callback containing `link_token` and holder info.
5. Frontend POSTs `link_token` to `POST /api/connections/oauth/callback?provider=fintoc&code={link_token}`.
6. Backend calls `FintocProvider.handle_oauth_callback(link_token)` → fetches institution + accounts.

**Alternatives considered**:
- OAuth redirect (not offered by Fintoc for end users; available only for specific regulated partners).

---

## Decision 3: Credentials storage

**Decision**: Store the `link_token` in `BankConnection.credentials` using the existing field-level encryption (same pattern as `access_url_enc` in SimpleFIN).

**Stored shape**:
```json
{
  "link_token_enc": "<encrypted link_token>"
}
```

**Rationale**: The `link_token` is a long-lived, per-user-per-institution token. It is the sole credential needed for all subsequent API calls (accounts, movements). No OAuth access/refresh token pair is needed.

**Expiry**: Fintoc `link_token`s do not expire on a timer. They become invalid only if the user revokes access at the bank or Fintoc deactivates the link. Expiry detection is handled by 401 responses → `SessionExpiredError`.

---

## Decision 4: CLP amount handling

**Decision**: Fintoc returns CLP amounts as integers (whole pesos, no cents). Map directly to `Decimal` without any scaling.

**Rationale**: CLP has 0 decimal places (ISO 4217). `Decimal("1500")` = 1500 CLP = correct. No division or multiplication needed.

**Contrast**: Some providers return minor units (e.g., BRL centavos → divide by 100). Fintoc does not.

---

## Decision 5: Transaction type and sign convention

**Decision**: Fintoc movements have `type: "charge"` (debit = money leaving account) or `type: "deposit"` (credit = money entering account). Amounts are always positive in the API response. The sign convention used in Securo's `Transaction.amount` is: debit = negative, credit = positive.

Map:
- `charge` → `type = "debit"`, `amount = Decimal(str(movement.amount))` (service layer handles sign)
- `deposit` → `type = "credit"`, `amount = Decimal(str(movement.amount))`

**Note**: The TransactionData dataclass carries `type` (debit/credit) and positive `amount`; the service layer applies the sign convention to `Transaction.amount` when persisting.

---

## Decision 6: Account type mapping

**Decision**:
- `checking_account` → `"checking"`
- `savings_account` → `"savings"`
- `vista_account` → `"checking"` (Cuenta Vista/RUT is the Chilean current account; no Securo equivalent)
- Any unknown type → `"checking"` (safe default)

**Rationale**: `vista_account` is the dominant account type in Chile (Cuenta RUT offered by all banks). Mapping it to `"checking"` is semantically correct — it is a demand deposit account.

---

## Decision 7: Reconnect / reauth flow

**Decision**: Use Fintoc's widget refresh mode (`mode: "refresh"`) with the existing `link_token` as `link_intent_id`. This maps to the existing `reconnect_token` endpoint pattern.

**Flow**:
1. Backend detects `SessionExpiredError` → marks connection as `status="expired"`.
2. User clicks "Reconnect" → Frontend calls `POST /api/connections/{id}/reconnect-token`.
3. Backend creates widget token with `mode: "refresh"` + `link_intent_id: {link_token}`.
4. Frontend opens FintocLink widget in refresh mode.
5. User re-authenticates; same `link_token` remains valid after refresh.

---

## Decision 8: Institution list

**Decision**: Implement `list_institutions(country=None)` to call `GET /v1/institutions?country=cl` (country defaults to "cl"). The response includes `id`, `name`, `country`, `logo_url`. This serves `GET /api/connections/fintoc/institutions`.

**Rationale**: Matches Enable Banking's pattern where the frontend can display a list of supported banks before the user initiates a connection.

---

## Decision 9: Frontend — FintocLink widget integration

**Decision**: Load FintocLink via CDN script tag (`https://js.fintoc.com/v1`) or install `@fintoc/fintoc-js` npm package. Given the project uses Vite + npm, prefer the npm package for type safety and build control.

**Integration point**: When the user selects Fintoc in `connector-select-dialog.tsx`, the existing flow calls the provider-specific handler. A new `useFintocWidget` hook (or inline in the accounts component that calls `create_connect_token`) initializes FintocLink with the `widget_token` and handles the `onSuccess` / `onClose` / `onError` callbacks.

**No changes to `connector-select-dialog.tsx`**: The dialog already handles provider listing generically. The Fintoc-specific widget invocation lives in the component that handles the selected provider (the same component that handles the Pluggy widget).

---

## Decision 10: Environment variables

**Decision**: One new server-side variable: `FINTOC_SECRET_KEY`.

Files to update:
- `.env.example` (root)
- `backend/.env.example`
- `docker-compose.yml` (backend environment section)
- `docker-compose.prod.yml` (backend environment section)
- `backend/app/core/config.py` (Settings class)

No redirect URI needed (widget-based flow has no server-side OAuth callback URL).

---

## Decision 11: No Alembic migration needed

**Decision**: The existing `BankConnection`, `Account`, and `Transaction` ORM models are sufficient. `credentials` (JSON, encrypted) stores the `link_token`. No new columns or tables.

**Verification**: The Fintoc integration uses the same four fields as other providers:
- `BankConnection.provider = "fintoc"`
- `BankConnection.credentials = {"link_token_enc": "..."}`
- `BankConnection.external_id = link_token` (same as SimpleFIN's access URL usage)
- `Account.external_id = fintoc_account_id`

---

## Decision 12: i18n strings needed

New translation keys needed in all locale JSON files:
- `accounts.providers.fintoc.description` — shown in `connector-select-dialog.tsx`

Existing keys already cover: connect flow labels, error states, sync status, disconnect.

---

## Research Summary

All NEEDS CLARIFICATION items resolved. No schema changes. No new backend API endpoints. One new provider module + config var + frontend widget integration + i18n strings. Ready for Phase 1 design.
