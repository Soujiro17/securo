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

- [x] T001 Fix `create_connect_token` in `backend/app/providers/fintoc.py` to return a no-op `ConnectTokenData(access_token="")` without making any HTTP request to Fintoc. Remove or comment out the `POST /link_intents` call. Keep the method signature intact to satisfy the `BankProvider` ABC.

- [x] T002 Fix `handle_oauth_callback` in `backend/app/providers/fintoc.py` so it treats `code` as the `link_token` directly. Remove the `GET /links/exchange?exchange_token=code` step. The method should: (1) call `GET /v1/accounts?link_token={code}` with `Authorization: {FINTOC_SECRET_KEY}` header, (2) build `AccountData` list via the existing `_build_account_data` helper, (3) extract `institution_name` from `accounts[0]["institution"]["name"]` with fallback `"Chilean Bank"` if accounts list is empty, (4) return `ConnectionData(external_id=code, institution_name=institution_name, credentials={"link_token": code}, accounts=accounts)`. Remove any imports or helpers used only by the old exchange flow.

---

## Phase 2 (US1): Frontend Widget Fix — New Connection Flow

> **Story**: User clicks "Conectar banco", completes Fintoc widget, account appears.
>
> **Independent test**: Open app, click connect, complete Fintoc sandbox widget (use test
> credentials from `specs/003-fix-fintoc-integration/quickstart.md`), verify accounts list
> refreshes with ≥1 account and no error toast.

- [x] T003 [US1] Rewrite `FintocConnectWidget` in `frontend/src/hooks/use-fintoc-widget.ts`:
  - Remove `widgetToken: string` from the props interface and destructured params.
  - In `Fintoc.create({...})`, remove the `widgetToken` field entirely.
  - Add `product: "movements"`, `holderType: "individual"`, `country: "cl"` to the `Fintoc.create()` call.
  - Replace the multi-fallback `onSuccess` callback `(data: any) => { const token = data?.exchange_token || data?.id || ...` with `(data: { link_token: string }) => { if (data?.link_token) { onSuccessRef.current(data.link_token) } else { onExitRef.current() } }`.
  - Remove the `console.log` that logged `widgetToken`.

- [x] T004 [US1] Fix the Fintoc rendering path in `frontend/src/components/bank-connect-dialog.tsx`:
  - In the `if (provider === 'fintoc')` branch, remove the `if (!connectToken) return null` guard (the widget no longer needs a server-issued token).
  - Remove `widgetToken={connectToken}` from the `<FintocConnectWidget ...>` JSX — the component no longer accepts this prop.
  - Ensure `<FintocConnectWidget>` renders immediately when `provider === 'fintoc'`, regardless of `connectToken` state.
  - Keep `onSuccess` and `onExit` handlers unchanged.

- [x] T005 [P] [US1] Audit `frontend/src/components/bank-connect-dialog.tsx` to confirm the `fetchToken` / `getConnectToken` call path is NOT invoked for Fintoc. Trace how `connectToken` gets set (via `useEffect` + `fetchToken`) and ensure the Fintoc branch short-circuits before that effect runs, OR that the effect is guarded by `provider !== 'fintoc'`. If `fetchToken` is called for Fintoc, add a guard: `if (provider === 'fintoc') return` at the top of the `fetchToken` call site.

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
