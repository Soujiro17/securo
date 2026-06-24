---

description: "Task list for Fintoc bank integration"
---

# Tasks: Fintoc Bank Integration

**Input**: Design documents from `specs/002-fintoc-integration/`

**Prerequisites**: plan.md âœ… | spec.md âœ… | research.md âœ… | data-model.md âœ… | contracts/fintoc-provider.md âœ…

**Tests**: Unit tests are included (FR-010 and constitution Principle III require parity with existing provider tests).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.
Backend tasks are completed before frontend tasks (per implementation order in plan.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Configuration Infrastructure)

**Purpose**: Environment variables and application config â€” blocks all user stories

- [x] T001 Add `fintoc_secret_key: str = ""` field to the Settings class in `backend/app/core/config.py` (after the SimpleFIN block, sourced from env var `FINTOC_SECRET_KEY`)
- [x] T002 [P] Add Fintoc section to `.env.example` with `# FINTOC_SECRET_KEY=sk_sandbox_...` and `# VITE_FINTOC_PUBLIC_KEY=pk_sandbox_...` (commented, with link to fintoc.com/dashboard)
- [x] T003 [P] Add `# FINTOC_SECRET_KEY=sk_sandbox_...` to `backend/.env.example` (after the SimpleFIN section)
- [x] T004 [P] Add `FINTOC_SECRET_KEY: ${FINTOC_SECRET_KEY:-}` to the backend service `environment:` block in `docker-compose.yml` (after the SIMPLEFIN_ENABLED line)
- [x] T005 [P] Add `FINTOC_SECRET_KEY: ${FINTOC_SECRET_KEY:-}` to the backend service `environment:` block in `docker-compose.prod.yml` (after the SIMPLEFIN_ENABLED line)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core provider skeleton that ALL user story tasks build on

âš ï¸ **CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create `backend/app/providers/fintoc.py` with `FintocProvider(BankProvider)` class skeleton: implement `name` property returning `"fintoc"`, `flow_type` property returning `"widget"`, private `_get_headers() -> dict` returning `{"Authorization": settings.fintoc_secret_key}`, and `_raise_for_fintoc(response)` that maps HTTP 401 â†’ `SessionExpiredError`, 429 â†’ `ProviderRateLimited`, other 4xx/5xx â†’ logged warning or re-raise
- [x] T007 Register `FintocProvider` in `backend/app/providers/__init__.py`: import `FintocProvider` from `app.providers.fintoc`, add `{"name": "fintoc", "display_name": "Fintoc", "flow_type": "widget", "requires_institution_select": False}` to `KNOWN_PROVIDERS`, and in `_auto_register_providers()` add `if settings.fintoc_secret_key: register_provider("fintoc", FintocProvider)`

**Checkpoint**: `GET /api/connections/providers` must return the Fintoc entry (with `configured: true` when env var is set) before proceeding.

---

## Phase 3: User Story 1 â€” Connect a Chilean Bank Account (Priority: P1) ðŸŽ¯ MVP

**Goal**: A Chilean user can connect their bank account via the FintocLink widget and have their accounts imported into Securo.

**Independent Test**: After T015, a user can open the UI, select Fintoc, complete the FintocLink widget with sandbox credentials, and see their accounts appear in Securo.

### Backend Implementation for US1

- [x] T008 [P] [US1] Add `_map_account_type(fintoc_type: str) -> str` and `_build_account_data(acc: dict) -> AccountData` helpers to `backend/app/providers/fintoc.py` â€” map `checking_account`/`vista_account`â†’`"checking"`, `savings_account`â†’`"savings"`, unknownâ†’`"checking"`; extract `id`, `name`, `official_name`, `currency`, balance from `balance.available` (fall back to `balance.current`)
- [x] T009 [P] [US1] Implement `create_connect_token(client_user_id, item_id=None) -> ConnectTokenData` in `backend/app/providers/fintoc.py` â€” `POST {FINTOC_API_BASE}/widget_tokens` with body `{"mode": "link", "product": "movements"}` when `item_id` is None, or `{"mode": "refresh", "link_intent_id": item_id, "product": "movements"}` when reconnecting; return `ConnectTokenData(access_token=response["widget_token"])`
- [x] T010 [US1] Implement `handle_oauth_callback(link_token: str) -> ConnectionData` in `backend/app/providers/fintoc.py` â€” `GET {FINTOC_API_BASE}/accounts?link_token={link_token}` via `httpx.AsyncClient`, extract institution name from first account's `holder_name` or `institution.name`, build list of `AccountData` via `_build_account_data()`, return `ConnectionData(external_id=link_token, institution_name=..., credentials={"link_token": link_token}, accounts=[...])`; call `_raise_for_fintoc()` on non-2xx responses
- [x] T011 [US1] Implement `get_accounts(credentials: dict) -> list[AccountData]` in `backend/app/providers/fintoc.py` â€” extract `link_token` from credentials, `GET {FINTOC_API_BASE}/accounts?link_token={link_token}`, map each account via `_build_account_data()`; call `_raise_for_fintoc()` on errors
- [x] T012 [US1] Implement `refresh_credentials(credentials: dict) -> dict` in `backend/app/providers/fintoc.py` â€” return `credentials` unchanged (Fintoc link tokens do not expire on a timer; 401 responses from any method surface `SessionExpiredError` via `_raise_for_fintoc()`)

**Backend Checkpoint**: `POST /api/connections/connect-token {"provider": "fintoc"}` returns `{"access_token": "wt_sandbox_..."}` and `POST /api/connections/oauth/callback {"provider": "fintoc", "code": "<sandbox_link_token>"}` creates a `BankConnection` with imported accounts.

### Frontend Implementation for US1

- [x] T013 [US1] Add `@fintoc/fintoc-js` to `frontend/package.json` dependencies and run `npm install` in the `frontend/` directory
- [x] T014 [US1] Create `frontend/src/hooks/use-fintoc-widget.ts` â€” export `FintocConnectWidget` component that accepts `{ widgetToken: string, onSuccess: (linkToken: string) => void, onExit: () => void }` props; in a `useEffect`, call `Fintoc.create({ publicKey: import.meta.env.VITE_FINTOC_PUBLIC_KEY, widgetToken, product: "movements", onSuccess: ({ link_token }) => onSuccess(link_token), onExit, onError: onExit })` and immediately calls `.open()`; cleanup calls `.destroy?.()` on unmount; returns `null` (headless component)
- [x] T015 [US1] Extend `frontend/src/components/bank-connect-dialog.tsx` to branch on `provider.name === "fintoc"`: when the provider is Fintoc, render `<FintocConnectWidget widgetToken={connectToken} onSuccess={(linkToken) => handleCallback(linkToken)} onExit={handleClose} />` instead of the PluggyConnect widget; the existing `handleCallback` call already POSTs to `oauth/callback?provider=fintoc&code={linkToken}`

**Checkpoint**: Full end-to-end connection flow works in the UI using Fintoc sandbox credentials.

---

## Phase 4: User Story 2 â€” Automatic Transaction Sync (Priority: P1) ðŸŽ¯ MVP

**Goal**: Connected Fintoc accounts sync transactions automatically; duplicates are not created on repeated syncs.

**Independent Test**: Trigger `POST /api/connections/{id}/sync` twice; second run returns `new_transactions: 0`. Chilean peso (CLP) amounts are stored as whole integers. Both debit (`charge`) and credit (`deposit`) movements import with correct sign.

### Implementation for US2

- [x] T016 [US2] Add `_build_transaction_data(mov: dict) -> TransactionData` helper to `backend/app/providers/fintoc.py` â€” map `mov.id` â†’ `external_id`, `mov.description` â†’ `description`, `Decimal(str(mov["amount"]))` â†’ `amount` (CLP has no decimal places), `mov.post_date` (fall back `transaction_date`) â†’ `date`, `"debit"` if `mov.type == "charge"` else `"credit"` â†’ `type`, `status="posted"` (Fintoc only returns settled movements), full `mov` dict â†’ `raw_data`
- [x] T017 [US2] Implement `get_transactions(credentials, account_external_id, since=None, payee_source="auto") -> list[TransactionData]` in `backend/app/providers/fintoc.py` â€” build params `{"link_token": link_token, "since": since.isoformat() if since else (date.today() - timedelta(days=90)).isoformat()}`; `GET {FINTOC_API_BASE}/accounts/{account_external_id}/movements`; loop cursor pagination via `next_cursor` in response until null; collect and return all `TransactionData` via `_build_transaction_data()`; call `_raise_for_fintoc()` on non-2xx
- [x] T018 [P] [US2] Write `backend/tests/test_providers_fintoc.py` using `pytest` and `respx` (or `httpx.MockTransport`) to mock Fintoc HTTP calls â€” must include: `test_create_connect_token_new`, `test_create_connect_token_refresh_mode`, `test_handle_oauth_callback_success`, `test_handle_oauth_callback_invalid_token_raises_session_expired`, `test_get_accounts_maps_types_correctly`, `test_get_transactions_charge_is_debit`, `test_get_transactions_deposit_is_credit`, `test_get_transactions_cpl_amount_no_scaling`, `test_get_transactions_pagination_follows_next_cursor`, `test_get_transactions_uses_since_param`, `test_list_institutions_returns_cl_banks`, `test_401_raises_session_expired_error`, `test_429_raises_provider_rate_limited`

**Checkpoint**: `pytest backend/tests/test_providers_fintoc.py -v` passes all 13 tests.

---

## Phase 5: User Story 3 â€” List Available Chilean Banks (Priority: P2)

**Goal**: The frontend can display supported Chilean banks before the user starts a connection.

**Independent Test**: `GET /api/connections/fintoc/institutions?country=cl` returns at least one institution with `name`, `display_name`, `country: "cl"`.

### Implementation for US3

- [x] T019 [US3] Implement `list_institutions(country=None) -> InstitutionListData` in `backend/app/providers/fintoc.py` â€” `GET {FINTOC_API_BASE}/institutions?country={country or "cl"}`; map each institution in the response to `InstitutionData(name=inst["id"], display_name=inst["name"], country=inst["country"], logo=inst.get("logo_url"))` and return `InstitutionListData(countries=[country or "cl"], institutions=[...])`

**Checkpoint**: `GET /api/connections/fintoc/institutions` returns a non-empty list when the sandbox key is configured.

---

## Phase 6: User Story 4 â€” View and Manage Fintoc Connections (Priority: P2)

**Goal**: Fintoc connections appear in the connections list with a localized provider description across all supported languages.

**Independent Test**: The `connector-select-dialog.tsx` renders the Fintoc provider entry with a human-readable description (not a raw translation key) in every locale: en, es, it, pl, pt-BR, ru, uk.

### Implementation for US4

- [x] T020 [P] [US4] Add `"fintoc": { "description": "..." }` under `accounts.providers` in all 7 locale files â€” `frontend/src/locales/en.json`, `frontend/src/locales/es.json`, `frontend/src/locales/it.json`, `frontend/src/locales/pl.json`, `frontend/src/locales/pt-BR.json`, `frontend/src/locales/ru.json`, `frontend/src/locales/uk.json` â€” translate appropriately per language (English: "Connect Chilean bank accounts â€” Banco de Chile, Santander, BCI and more"; Spanish: "Conecta cuentas bancarias chilenas â€” Banco de Chile, Santander, BCI y mÃ¡s"; other locales: translate accordingly)

**Checkpoint**: In every locale, the add-connection dialog shows the Fintoc provider with a non-empty, non-key description string.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validation and final integration checks

- [ ] T021 [P] Run end-to-end validation per all scenarios in `specs/002-fintoc-integration/quickstart.md` â€” scenarios 1 (provider listing), 2 (widget token), 3 (connect account via UI), 4 (manual sync, no duplicates), 5 (institution list), 7 (provider absent when unconfigured), 8 (all unit tests pass), 9 (i18n strings present)
- [ ] T022 Verify `connector-select-dialog.tsx` renders the Fintoc provider entry correctly and that clicking it triggers the FintocLink widget (manual UI smoke test in sandbox)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” T002â€“T005 can all run in parallel after T001
- **Foundational (Phase 2)**: Depends on Phase 1 (T001 must be complete for config import in T006)
- **US1 Backend (T008â€“T012)**: Depends on Foundational â€” T008 and T009 can run in parallel; T010 depends on T008; T011 and T012 depend on T010
- **US1 Frontend (T013â€“T015)**: T013 independent (npm install); T014 after T013; T015 after T014
- **US2 (T016â€“T018)**: T016 first; T017 depends on T016; T018 can start in parallel with T017
- **US3 (T019)**: Independent from US2 â€” can run after Foundational
- **US4 (T020)**: Independent from all backend phases â€” can run any time after Phase 1
- **Polish (T021â€“T022)**: Depends on all previous phases complete

### Within-Story Backend Implementation Order

- Account type mapping helpers â†’ connect token â†’ callback handler â†’ get_accounts â†’ refresh_credentials â†’ get_transactions â†’ tests

### Parallel Opportunities

- T002, T003, T004, T005: All edit different files â€” run together
- T008, T009: Different methods â€” run together after T007
- T013: npm install â€” run while backend T008â€“T012 are in progress
- T018 (tests): Can be written in parallel with T017 (test stubs before full implementation)
- T019, T020: Both independent â€” run in parallel during US3/US4 phase

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup (T001â€“T005)
2. Complete Phase 2: Foundational (T006â€“T007)
3. Complete Phase 3: US1 backend (T008â€“T012), then US1 frontend (T013â€“T015)
4. Complete Phase 4: US2 (T016â€“T018)
5. **STOP and VALIDATE**: Full connect + sync flow works end-to-end with Fintoc sandbox
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational â†’ Provider registered
2. US1 backend â†’ Connect token + callback works â†’ Demo to stakeholders
3. US1 frontend â†’ Full connect flow in UI â†’ MVP!
4. US2 â†’ Sync works â†’ Deploy
5. US3 â†’ Institution list â†’ Deploy
6. US4 â†’ i18n complete â†’ Polish release

---

## Notes

- [P] tasks = different files, no dependencies within the same phase
- [Story] label maps each task to the user story it serves
- Backend tasks must be completed before the corresponding frontend tasks (per plan)
- All Fintoc API calls use `httpx.AsyncClient` â€” no Fintoc Python SDK (see research.md Decision 1)
- CLP amounts from Fintoc are whole integers â€” no centavo scaling needed
- `vista_account` (Cuenta Vista / Cuenta RUT) maps to `"checking"` account type
- `create_connect_token` handles both new connections (`item_id=None`) and reconnects (`item_id=link_token`) via Fintoc's `mode: "refresh"` + `link_intent_id`

