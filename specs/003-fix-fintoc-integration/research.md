# Research: Fix Fintoc Bank Account Sync

**Feature**: 003-fix-fintoc-integration
**Date**: 2026-06-25
**Phase**: 0 — Root-cause analysis

---

## Decision 1: Widget initialization for movements product

**Decision**: For the `movements` product, `Fintoc.create()` must NOT receive a
`widgetToken` parameter. The correct call uses `publicKey`, `product`, `holderType`,
and `country`.

**Rationale**: Per Fintoc's official widget documentation:
> "widgetToken: The widgetToken parameter corresponds to the token created by the
> backend that initializes and configures the widget. **Only the subscriptions product
> uses a widgetToken parameter.**"

The current implementation (from spec 002) was based on research that proposed
`POST /v1/widget_tokens` → `widget_token` for movements. This was incorrect. Fintoc's
documented widget initialization for movements requires only client-side parameters;
no backend round-trip is needed.

**Impact**: The entire `create_connect_token` → `POST /link_intents` pipeline is
unnecessary for Fintoc movements. The frontend must skip the `getConnectToken` call
for the Fintoc provider path.

**Alternatives considered**: None — this is a product-level constraint documented by
Fintoc itself.

---

## Decision 2: `onSuccess` payload field for movements widget

**Decision**: The FintocLink `onSuccess` callback for the movements product fires with
a payload where the bank credential is `data.link_token` (not `data.exchange_token`).

**Rationale**: Spec 002 Decision 2 documents this explicitly:
> "Widget fires `onSuccess(data)` callback containing `link_token` and holder info."

The current implementation destructures `{ exchange_token }` from the callback, which
yields `undefined`. This means the backend callback always receives `undefined` as
`code`, making every connection attempt fail silently.

**Impact**: Frontend `onSuccess` handler must be updated to read `data.link_token`.

---

## Decision 3: Backend does not need to exchange any token

**Decision**: `handle_oauth_callback(code)` must treat `code` as the final `link_token`
and use it directly. The `POST /links` exchange call must be removed.

**Rationale**: For the movements product, the widget delivers the `link_token` directly
(see Decision 2). There is no short-lived "exchange_token" step. The current backend
sends `code` as `{"exchange_token": code}` to `POST /links`, which Fintoc rejects with
a 4xx because `code` is not an exchange token — it is the link_token itself.

**Impact**: `handle_oauth_callback` is rewritten to:
1. Accept `code` = `link_token` directly.
2. Call `GET /v1/accounts?link_token=code` to get institution info + accounts.
3. Store `{"link_token": code}` (encrypted at rest) as credentials.
4. Use `code` (the `link_token`) as `BankConnection.external_id`.

---

## Decision 4: `external_id` field for BankConnection

**Decision**: Use the `link_token` value as `BankConnection.external_id` for Fintoc.

**Rationale**: The `link_token` is globally unique per Fintoc Link (one per user per
institution). It is the natural idempotency key. No additional API call is required
to obtain it.

**Alternative considered**: Calling a Fintoc endpoint to retrieve an internal numeric
Link ID. Rejected — extra latency, additional API scope may be needed, and the
`link_token` string already provides sufficient uniqueness.

---

## Decision 5: Institution name derivation

**Decision**: Derive institution name from `accounts[0].institution_name` in the
`GET /accounts` response. Fallback to `"Chilean Bank"` if the list is empty or the
field is absent.

**Rationale**: The `GET /accounts?link_token=…` call is already required to build
`AccountData` objects. Reusing its response to extract institution name avoids an
additional API call. The existing `_build_account_data` helper already maps the
institution name from the Fintoc account payload.

---

## Decision 6: `create_connect_token` stub

**Decision**: Retain `create_connect_token` on `FintocProvider` but stub it to return
`ConnectTokenData(access_token="")`. The `BankProvider` ABC requires this method.

**Rationale**: Removing the method would require changes to the ABC and all four
existing provider implementations — a disproportionate change for what is a dead-code
path. Stubbing keeps the interface intact and makes the no-op explicit.

---

## Decision 7: No schema changes

**Decision**: No Alembic migrations required.

**Rationale**: `BankConnection.external_id` already exists as a string column.
Changing what value is stored there (from a Fintoc internal Link ID to the `link_token`
itself) requires no schema change.

**Risk**: Existing Fintoc connections (if any) created by the buggy implementation will
have incorrect `external_id` values. Re-connection will create new `BankConnection`
rows with correct values. This is acceptable given the feature has not shipped.

---

## Decision 8: No new test infrastructure

**Decision**: Update `test_providers_fintoc.py` in-place. No new test files or fixtures.

**Rationale**: The existing test file covers `create_connect_token`, `get_accounts`,
`get_transactions`, and `handle_oauth_callback`. Only the mock setup and assertions for
`handle_oauth_callback` need updating to remove the `POST /links` mock and assert the
`GET /accounts` call is used instead.

---
