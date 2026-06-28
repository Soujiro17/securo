# Tasks: Fintoc Callback Fix

**Feature**: 004-fintoc-callback-fix
**Generated**: 2026-06-27
**Spec**: spec.md | **Plan**: plan.md

## Overview

Three files need surgical changes to switch from the wrong token-exchange flow to the
correct direct `link_token` flow. No new files, no migrations, no dependencies to add.

```
Total tasks: 8
User Story 1 (P1 – Connect bank): T003, T004, T005
User Story 2 (P2 – Reconnect):    T006 (verify only, covered by US1 fixes)
Foundational (backend):            T001, T002
Validation:                        T007, T008
```

**MVP scope**: T001 + T002 + T003 + T004 = working connect flow.
T005 and T006 are safety checks; T007–T008 are end-to-end validation.

---

## Phase 1: Foundational — Backend Provider Fix

> **Goal**: Make the backend `FintocProvider` accept a `link_token` directly and stop
> calling the `POST /link_intents` and `GET /links/exchange` Fintoc endpoints.
>
> **Blocks**: All frontend work (the frontend callback hits this backend code).

- [x] T001 Keep `create_connect_token` in `backend/app/providers/fintoc.py` calling `POST /link_intents` to obtain a `widget_token`. The Fintoc JS SDK REQUIRES a server-issued `widget_token` — without one it calls an internal endpoint that requires a `callback_url` and fails. *(Earlier attempt to make this a no-op was reverted after reading docs.)*

- [x] T002 Clean up `handle_oauth_callback` in `backend/app/providers/fintoc.py`: keep `GET /links/exchange?exchange_token=code` (correct endpoint), remove duplicate `institution_name` assignment, read `institution_name` from `link_data.get("institution")["name"]` at the Link object level. The exchange endpoint returns the full Link object including `link_token`, `accounts`, and `institution`.

---

## Phase 2 (US1): Frontend Widget Fix — New Connection Flow

> **Story**: User clicks "Conectar banco", completes Fintoc widget, account appears.
>
> **Independent test**: Open app, click connect, complete Fintoc sandbox widget (use test
> credentials from `specs/003-fix-fintoc-integration/quickstart.md`), verify accounts list
> refreshes with ≥1 account and no error toast.

- [x] T003 [US1] Fix `onSuccess` in `frontend/src/hooks/use-fintoc-widget.ts`: replace the multi-fallback chain `data?.exchange_token || data?.id || ...` with `data?.exchangeToken` (camelCase). The Fintoc JS SDK returns the Link Intent object in camelCase — `exchange_token` (snake_case) is always `undefined`, causing the fallback to capture `data.id` (the Link Intent ID like `li_xxx`), which the backend cannot exchange. Keep `widgetToken` prop and all other code unchanged.

- [x] T004 [US1] Restore `frontend/src/components/bank-connect-dialog.tsx` Fintoc path: keep `if (!connectToken) return null` guard, keep `widgetToken={connectToken}` prop. *(Earlier attempt to remove these was reverted.)*

- [x] T005 [P] [US1] Confirmed: `fetchToken` runs correctly for Fintoc (calls `getConnectToken('fintoc')` → `POST /link_intents` server-side → `widget_token`). No guard needed. The server token fetch is required.

---

## Phase 3 (US2): Reconnect Path Verification

> **Story**: User with expired connection clicks "Reconectar" and refreshes their link.
>
> **Independent test**: Set a connection's `status = "expired"` in the DB, trigger reconnect
> dialog, complete widget, verify `BankConnection.status` returns to `"active"`.

- [x] T006 [US2] Verify the reconnect code path in `frontend/src/components/bank-connect-dialog.tsx`. When `reconnectConnectionId` is set, the dialog calls `connections.sync(reconnectConnectionId)` instead of `handleCallback`. Confirm: (1) the Fintoc branch for reconnect also renders `<FintocConnectWidget>` without requiring `connectToken`, and (2) `onSuccess` correctly passes the new `link_token` to `connections.sync` or the appropriate reconnect handler. If `connections.sync` doesn't accept a new `link_token`, check whether `handleCallback` should be called to update credentials — verify against `backend/app/api/connections.py` and adjust if needed.
  > **Note (pre-existing limitation)**: `sync` uses the stored link_token — it does not receive the new link_token produced by the widget. If Fintoc issues a brand-new link_token on re-auth (rather than refreshing the existing one), the reconnect sync will still fail with 401. Fixing this requires a backend endpoint to update stored credentials and is tracked as a follow-up.

---

## Phase 4: Validation

> **Goal**: Confirm the full end-to-end flow works in the sandbox before marking complete.

- [ ] T007 Run the Fintoc sandbox validation described in `specs/003-fix-fintoc-integration/quickstart.md`. Start the app (`docker-compose up`), open the frontend, click "Conectar banco", select a Chilean bank in the widget, enter sandbox credentials, complete authentication. Verify: (a) no console errors in the browser DevTools during `onSuccess`, (b) backend logs show `GET /v1/accounts?link_token=...` request (not an exchange request), (c) accounts appear in the UI, (d) transactions are visible for at least one account.

- [ ] T008 [P] Test the cancel / exit path: open the widget and click "Cancelar" or close it without completing auth. Verify: (a) no new `BankConnection` record is created in the database, (b) no error toast is shown to the user, (c) the dialog closes cleanly.

---

## Dependencies

```
T001 ──┐
T002 ──┤── T003 ── T004 ── T005 ──── T007
                                T006 ─┘
                                T008  (independent, can run after T003+T004)
```

- T001 and T002 can be done in parallel (different methods in the same file — be careful of conflicts if editing simultaneously).
- T003 must complete before T004 (T004 calls into the updated component).
- T005 depends on T004 (audits the dialog after the change).
- T006 depends on T003 + T004 (reconnect uses the same widget component).
- T007 and T008 are final validation — run after T001–T006.

---

## Parallel Execution Guide

**Batch 1** (can run in parallel):
- T001: `fintoc.py` — `create_connect_token` method
- T002: `fintoc.py` — `handle_oauth_callback` method
  > Both are in the same file but different methods. Safe to do sequentially in one editing session.

**Batch 2** (sequential, order matters):
- T003 → T004 → T005

**Batch 3** (after Batch 2):
- T006, T007, T008 (T006 and T008 can run in parallel)

---

## Implementation Strategy

**MVP (minimum to unblock manual testing)**:
Complete T001 → T002 → T003 → T004 in order. This gives a working connect flow end-to-end.

**Full story**:
Add T005 (audit), T006 (reconnect), T007 + T008 (validation). These catch edge cases but are not required to prove the main flow works.

**Do not**:
- Introduce new dependencies or libraries.
- Change the Pluggy or Enable Banking paths.
- Add migration files (schema is unchanged).
- Create new files (all changes are modifications to existing files).
