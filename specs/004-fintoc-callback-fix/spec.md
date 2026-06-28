# Feature Specification: Fintoc Callback Fix

**Feature Branch**: `feat/fintoc-bank-connection`

**Created**: 2026-06-27

**Status**: Draft

**Input**: User description: "Soluciona el problema de la implementación de Fintoc. Actualmente hay cosas implementadas, pero no funciona al 100% todo. Generalmente falla con el oauth/callback si mal no recuerdo. El widget funciona bien, pero falla cuando cierro el widget."

## Context

Spec `003-fix-fintoc-integration` documented the correct Fintoc flow and generated tasks that were marked complete, but the actual code was **not updated to match the spec**. The widget opens correctly (the UI renders), but after the user completes bank authentication the success callback silently fails to create the bank connection — so closing the widget leaves the user with no connected account.

### Root Cause (Current Broken State)

The implementation uses a **three-step token exchange flow** (wrong for the Fintoc `movements` product):

1. Frontend calls server → `POST /v1/link_intents` → receives `widget_token`
2. Widget fires `onSuccess(data)` → code tries `data.exchange_token || data.id || data.token || data.link_token` (priority order is wrong)
3. Backend calls `GET /v1/links/exchange?exchange_token=…` (endpoint not applicable to movements)

The correct flow (per spec 003 contracts) is **two-step, link_token-direct**:

1. Widget is opened with only `publicKey` (no server-side token needed)
2. `onSuccess(data)` delivers `data.link_token` directly → backend uses it as-is for all Fintoc API calls

The code diverges from the contract in **three files**: `use-fintoc-widget.ts`, `bank-connect-dialog.tsx`, and `fintoc.py`.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Connect a Chilean bank account (Priority: P1)

A user with no connected bank clicks "Conectar banco", completes the Fintoc widget flow (selects their bank, authenticates), and the widget closes. After closing, the user can see their Chilean bank accounts and recent transactions in Securo without any error message.

**Why this priority**: This is the entire purpose of the Fintoc integration. Without it, no bank data flows into the app.

**Independent Test**: Open the app with a fresh user, click the connect-bank button, complete the Fintoc sandbox widget, and verify the accounts list refreshes with at least one account.

**Acceptance Scenarios**:

1. **Given** the user is on the accounts page and has no connections, **When** they click "Conectar banco" and complete the Fintoc widget, **Then** a success toast appears and at least one bank account is visible in the accounts list within 30 seconds.
2. **Given** the widget is open and the user cancels (clicks the X or back), **When** the widget closes, **Then** no error is shown, no connection is created, and the accounts page remains unchanged.
3. **Given** the user successfully connected an account, **When** they view transactions, **Then** at least 90 days of movements are visible for each connected account.

---

### User Story 2 — Reconnect an expired connection (Priority: P2)

A user with an existing Fintoc connection whose `link_token` expired is prompted to reconnect. They click "Reconectar", complete the widget again, and the connection is refreshed with a new `link_token`.

**Why this priority**: Connections expire. Without reconnect, users permanently lose data sync after token expiry.

**Independent Test**: Mark an existing connection as expired in the database, trigger the reconnect flow, and verify the connection's credentials are updated.

**Acceptance Scenarios**:

1. **Given** a connection has `status = "expired"`, **When** the user clicks "Reconectar" and completes the widget, **Then** the connection status returns to `"active"` and transactions sync resumes.

---

### Edge Cases

- What happens when the Fintoc API returns 401 (token revoked mid-session)?
- What happens when the Fintoc API returns an empty accounts list?
- What happens when the widget fires `onError` instead of `onSuccess`?
- What happens when `VITE_FINTOC_PUBLIC_KEY` is missing from the environment?

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The frontend MUST open the Fintoc widget using only `publicKey`, `product: "movements"`, `holderType: "individual"`, and `country: "cl"` — no `widgetToken` parameter.
- **FR-002**: The `FintocConnectWidget` component MUST NOT accept or use a `widgetToken` prop.
- **FR-003**: The `onSuccess` callback MUST read `data.link_token` exclusively (no fallback chain).
- **FR-004**: `bank-connect-dialog.tsx` MUST NOT call `getConnectToken` for the Fintoc path; the widget MUST render immediately.
- **FR-005**: The backend `create_connect_token()` for Fintoc MUST return a no-op `ConnectTokenData(access_token="")` without calling any Fintoc API.
- **FR-006**: The backend `handle_oauth_callback(code)` MUST use `code` as the `link_token` directly and call `GET /v1/accounts?link_token={code}` — no token exchange step.
- **FR-007**: The backend MUST set `external_id = code` (the link_token) and `credentials = {"link_token": code}` on the created `BankConnection`.
- **FR-008**: The backend MUST extract `institution_name` from `accounts[0]["institution"]["name"]`; if the accounts list is empty, use `"Chilean Bank"` as fallback.
- **FR-009**: When `onExit` or `onError` fires (user cancels or widget errors), NO bank connection record MUST be created; the dialog closes cleanly.
- **FR-010**: All existing functionality for other providers (Pluggy, Enable Banking) MUST remain unaffected.

### Key Entities

- **BankConnection**: `external_id` = `link_token` string; `credentials` = `{"link_token": encrypted_value}`; `institution_name` = from Fintoc API.
- **FintocConnectWidget**: Stateless React component that opens the Fintoc widget. Props: `onSuccess(linkToken: string)`, `onExit()` only.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the full connect-bank flow (open widget → authenticate → close) in under 3 minutes and see their accounts immediately.
- **SC-002**: 100% of successful widget completions result in a `BankConnection` record in `status = "active"`.
- **SC-003**: 100% of widget cancellations or errors result in zero new `BankConnection` records created.
- **SC-004**: Pluggy and Enable Banking connect flows continue to work without regression.
- **SC-005**: The backend handles the case where Fintoc returns zero accounts gracefully (no unhandled exception, connection created with empty account list).

---

## Assumptions

- The Fintoc `movements` widget does not require a server-issued `widget_token`; it is initialized with `publicKey` only.
- `onSuccess` for the `movements` product always delivers `{ link_token: string }` — `exchange_token` is not returned for this product.
- The `VITE_FINTOC_PUBLIC_KEY` and `FINTOC_SECRET_KEY` environment variables are already correctly configured in `docker-compose.yml`.
- Reconnect flow (for existing `BankConnection`) reuses the same Fintoc widget path; the widget issues a fresh `link_token`.
- No Alembic migration is required — schema is unchanged.
- The existing encrypted-credentials helper in `connection_service.py` is used as-is; only the `credentials` dict shape changes to `{"link_token": value}`.
