---
description: "Task list for Fix Fintoc Bank Account Sync"
---

# Tasks: Fix Fintoc Bank Account Sync

**Input**: Design documents from `specs/003-fix-fintoc-integration/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅

**Tests**: Included for the backend fix only (existing test file update required).

**Organization**: Tasks follow the 4 root-cause bugs from plan.md. Bugs A+B share a file and are combined into one task. Bug C (backend) can be done in parallel with Bugs A+B+D (frontend).

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on each other)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

No project initialization needed — all dependencies and infrastructure already exist.
This fix is purely corrective changes to 4 existing files.

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Fix the backend `handle_oauth_callback` so it correctly processes the
`link_token` received from the widget. All user stories depend on a working backend
connection handler.

**⚠️ CRITICAL**: US2 and US3 cannot be validated until this fix is in place.

- [X] T001 Fix `create_connect_token` in `backend/app/providers/fintoc.py`: remove the `POST /link_intents` HTTP call and return `ConnectTokenData(access_token="")` immediately. The method must still exist (required by the `BankProvider` ABC) but is now a no-op stub since the movements widget does not need a server-side token.

- [X] T002 Fix `handle_oauth_callback` in `backend/app/providers/fintoc.py`: (a) remove the `POST {FINTOC_API_BASE}/links` HTTP call and the `{"exchange_token": code}` payload entirely; (b) treat `code` as the `link_token` directly; (c) call `self.get_accounts({"link_token": code})` to obtain the accounts list; (d) extract `institution_name` from `accounts[0].institution_name` with fallback `"Chilean Bank"`; (e) return `ConnectionData(external_id=code, institution_name=institution_name, credentials={"link_token": code}, accounts=accounts)`.

- [X] T003 Update `backend/tests/test_providers_fintoc.py` to match the corrected `handle_oauth_callback` and `create_connect_token` behaviour: (a) remove any mock for `POST .*/links` in the `handle_oauth_callback` test; (b) add/update mock for `GET .*/accounts` to return a list with at least one account (use existing `_build_account_data` shape); (c) assert that `ConnectionData.external_id` equals the input `link_token`; (d) assert that no `POST /links` call is made; (e) update `test_create_connect_token` to assert the method returns an empty `access_token` with no HTTP calls made.

**Checkpoint**: `pytest backend/tests/test_providers_fintoc.py` passes green.

---

## Phase 3: User Story 1 - Connect a Chilean Bank Account (Priority: P1) 🎯 MVP

**Goal**: User opens the bank connect dialog, the Fintoc widget launches correctly, user
authenticates at their bank, and the resulting `link_token` is sent to the backend which
creates the `BankConnection` and `Account` records.

**Independent Test**: Open `BankConnectDialog` with `provider="fintoc"`, verify the
Fintoc JS widget loads with bank selection (no `widgetToken` error), complete authentication
with sandbox credentials, confirm accounts appear in the Accounts list.

### Implementation for User Story 1

- [X] T004 [P] [US1] Fix `FintocConnectWidget` in `frontend/src/hooks/use-fintoc-widget.ts`:
  (a) Update the component props — remove the `widgetToken: string` prop; the component reads `import.meta.env.VITE_FINTOC_PUBLIC_KEY` internally already;
  (b) In the `Fintoc.create()` call: remove the `widgetToken` field; add `holderType: 'individual'` and `country: 'cl'`;
  (c) Fix the `onSuccess` callback: change `({ exchange_token }) => onSuccessRef.current(exchange_token)` to `(data: { link_token: string }) => onSuccessRef.current(data.link_token)`;
  (d) Update the TypeScript global `Window.Fintoc.create` signature to reflect the correct parameters (remove `widgetToken`, add `holderType`, `country`; change `onSuccess` payload type from `{ exchange_token: string }` to `{ link_token: string }`).

- [X] T005 [P] [US1] Fix `BankConnectDialog` in `frontend/src/components/bank-connect-dialog.tsx`:
  (a) In the `useEffect` that fetches the connect token, add an early return for Fintoc: `if (!open || provider === 'fintoc') { setConnectToken(null); return; }` — Fintoc does not need a server-side token to open the widget;
  (b) In the render section, move the `provider === 'fintoc'` branch BEFORE the `!connectToken` guard so it renders without waiting for a token: `if (provider === 'fintoc' && open) { return <FintocConnectWidget onSuccess={...} onExit={handleClose} /> }`;
  (c) Remove the `widgetToken={connectToken}` prop from the `<FintocConnectWidget>` usage (the prop no longer exists after T004);
  (d) The `handleSuccess` callback already calls `connections.handleCallback(data.item.id, provider)` where `data.item.id` will now be the `link_token` — this is correct, no change needed there.

**Checkpoint**: After T004 + T005, the Fintoc widget opens without a `widgetToken`
error, user can authenticate, and `connections.handleCallback(linkToken, 'fintoc')` is
called with the actual `link_token` string (not `undefined`).

---

## Phase 4: User Story 2 - Sync Movements (Priority: P1)

**Goal**: After a successful connection (Phase 3), the backend syncs 90 days of
movements for each account. The `get_transactions` implementation is already correct
(pagination, `since` date, `link_token` auth header). No new code needed.

**Independent Test**: After Phase 3 checkpoint, verify that `Transaction` rows exist in
the database for the connected account covering the last 90 days.

### Verification for User Story 2

- [X] T006 [US2] Verify `get_transactions` in `backend/tests/test_providers_fintoc.py`:
  confirm the existing `get_transactions` test mocks `GET .*/accounts/.*/movements` with a
  paginated response and asserts all pages are fetched. If this test does not exist or
  covers only the non-paginated path, add a test for the cursor-based pagination path
  (mock two pages: first response includes `next_cursor`, second includes empty `next_cursor`).

**Checkpoint**: `pytest backend/tests/test_providers_fintoc.py -k transactions` passes.
After running the full flow (Phases 2+3), the Accounts page shows transaction history.

---

## Phase 5: User Story 3 - View Account Balance and Info (Priority: P2)

**Goal**: Each connected account shows the correct available balance in CLP, institution
name, and account type. The `_build_account_data` helper and the `data-model.md` account
type mapping already handle this. No new code needed.

**Independent Test**: After Phases 3+4, verify the Accounts card for a connected Fintoc
account shows a non-zero CLP balance, the institution name (e.g., "Banco de Chile"),
and account type (checking or savings).

### Verification for User Story 3

- [X] T007 [US3] Verify `_build_account_data` in `backend/tests/test_providers_fintoc.py`:
  confirm a test exists (or add one) that asserts: (a) `account.type` maps `vista_account`
  and `checking_account` → `"checking"`, and `savings_account` → `"savings"`; (b)
  `account.balance` uses `available` with fallback to `current`; (c) `account.institution_name`
  is populated from the `institution.name` field in the Fintoc API response.

**Checkpoint**: `pytest backend/tests/test_providers_fintoc.py -k account` passes.
The Accounts UI shows correct balance, name, and type for sandbox-connected accounts.

---

## Final Phase: Polish & Validation

**Purpose**: End-to-end sandbox validation and cleanup.

- [ ] T008 Run sandbox validation per `specs/003-fix-fintoc-integration/quickstart.md`:
  execute Scenario 1 (full connection), Scenario 2 (re-sync no duplicates), Scenario 3
  (widget cancelled → no orphan records). Document any failures and fix before closing
  the feature.

- [X] T009 [P] Clean up dead code in `backend/app/providers/fintoc.py`: if the `POST
  /link_intents` import or any helper function was used exclusively for the old
  exchange flow and is no longer referenced after T001+T002, remove it.

- [X] T010 [P] Run the full backend test suite to confirm no regressions in Pluggy,
  Enable Banking, or SimpleFIN providers: `pytest backend/tests/ -v --ignore=backend/tests/test_providers_fintoc.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Nothing — start immediately
- **Phase 2 (Foundational)**: Start immediately (independent of frontend changes)
- **Phase 3 (US1 — Frontend)**: Can start immediately in parallel with Phase 2
- **Phase 4 (US2 — Verify sync)**: Depends on Phase 2 complete
- **Phase 5 (US3 — Verify balance)**: Depends on Phase 2 complete
- **Final Phase**: Depends on Phases 3, 4, 5 complete

### Within-Phase Dependencies

```
T001 → T002 (both in fintoc.py; do T001 first to avoid conflicts)
T002 → T003 (test update follows implementation)
T004 → T005 (T005 removes widgetToken prop added by T004)
T002 → T006 (T006 tests correct behavior from T002)
T002 → T007 (T007 tests _build_account_data called by T002)
```

### Parallel Opportunities

T001/T002/T003 (backend) can run completely in parallel with T004/T005 (frontend) since
they touch different files:

```
Worker A (backend):  T001 → T002 → T003 → T006 → T007
Worker B (frontend): T004 → T005
                     ↓
                  T008 → T009 → T010  (validation, after both workers done)
```

---

## Parallel Example: Phase 2 + Phase 3 simultaneously

```
# Backend worker:
T001: Stub create_connect_token in backend/app/providers/fintoc.py
T002: Fix handle_oauth_callback in backend/app/providers/fintoc.py
T003: Update backend/tests/test_providers_fintoc.py

# Frontend worker (simultaneously):
T004: Fix FintocConnectWidget in frontend/src/hooks/use-fintoc-widget.ts
T005: Fix BankConnectDialog in frontend/src/components/bank-connect-dialog.tsx
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete T001 + T002 (backend fix)
2. Complete T003 (backend test update)
3. Complete T004 + T005 (frontend fix)
4. **STOP and VALIDATE**: run Scenario 1 from quickstart.md with sandbox credentials
5. If Scenario 1 passes → US1 is done, proceed to US2/US3 verification

### Full Delivery (All Stories)

1. MVP steps above
2. T006: verify movements sync test
3. T007: verify balance mapping test
4. T008–T010: sandbox validation + cleanup

---

## Notes

- **No schema changes**: `BankConnection.external_id` already exists as a string column
- **No new dependencies**: Frontend CDN widget already in use; backend uses existing httpx
- **Pluggy path must remain green**: T010 verifies this
- **[P] tasks**: touch different files; safe to implement simultaneously
- **Commit after T002+T003** (backend green), then after **T004+T005** (frontend complete)
