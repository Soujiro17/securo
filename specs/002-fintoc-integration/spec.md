# Feature Specification: Fintoc Bank Integration

**Feature**: fintoc-integration
**Version**: 1.0
**Date**: 2026-06-24
**Status**: Draft

## Overview

Integrate Fintoc as a bank account linking provider so that users located in Chile can
connect their bank accounts to Securo, enabling automatic transaction import and balance
tracking for Chilean banks. This mirrors the existing integration pattern used by Pluggy
(Brazil), Enable Banking (Europe), and SimpleFIN (US/Canada).

## Problem Statement

Currently Securo supports bank account linking only for Brazil (Pluggy), Europe (Enable
Banking), and the United States/Canada (SimpleFIN). Users with bank accounts in Chile
have no automatic sync option and must import transactions manually. Fintoc provides a
regulated, consent-based bank data service for Chile that can fill this gap.

## User Stories

### US1 — Connect a Chilean Bank Account (Priority: P1) 🎯 MVP

**As a** Securo user with a Chilean bank account,
**I want to** connect my Chilean bank account to Securo using Fintoc,
**So that** my transactions and balances are automatically imported without manual uploads.

**Acceptance Scenarios**:

1. **When** a Chilean user opens the bank connection flow and selects Fintoc as the provider,
   **And** follows the guided Fintoc connection widget (selects bank, authenticates),
   **Then** their bank accounts are imported into Securo and a first-sync runs automatically.

2. **When** the user's Fintoc session expires or the bank requires re-authentication,
   **Then** the connection is marked as expired, the user is notified, and they can
   reconnect without losing their transaction history.

3. **When** the Fintoc widget flow is aborted or fails (e.g., wrong credentials at the bank),
   **Then** no broken connection is created and the user receives a clear error message.

### US2 — Automatic Transaction Sync (Priority: P1) 🎯 MVP

**As a** user with a connected Chilean bank account,
**I want** my new transactions to be fetched and imported automatically on a recurring basis,
**So that** my Securo account always reflects my up-to-date financial picture.

**Acceptance Scenarios**:

1. **When** a scheduled sync runs for a Fintoc connection,
   **Then** new transactions since the last sync are imported, duplicates are not created,
   and balances are updated.

2. **When** a user manually triggers a sync,
   **Then** the latest transactions are fetched immediately and the user sees the result.

3. **When** a transaction already imported is later posted (transitions from pending to settled),
   **Then** the existing transaction record is updated rather than duplicated.

### US3 — List Available Chilean Banks (Priority: P2)

**As a** user initiating a bank connection,
**I want to** see a list of Chilean banks supported by Fintoc with their logos,
**So that** I can identify and select my bank before starting the connection flow.

**Acceptance Scenarios**:

1. **When** the user navigates to the add-connection screen and selects Chile/Fintoc,
   **Then** a list of supported Chilean banks is displayed with institution names and logos.

2. **When** a bank I use is not listed,
   **Then** the interface communicates clearly that only the listed banks are supported.

### US4 — View and Manage Fintoc Connections (Priority: P2)

**As a** user,
**I want to** see my active Fintoc connections alongside my other provider connections,
**So that** I can manage (rename, reconnect, disconnect) them like any other connection.

**Acceptance Scenarios**:

1. **When** a Fintoc connection is active,
   **Then** it appears in the connections list with the bank's name, logo, last sync time,
   and connection status.

2. **When** a user chooses to disconnect a Fintoc connection,
   **Then** the connection and its linked accounts are removed from Securo; no Fintoc-side
   data is deleted (Securo does not hold the user's bank credentials).

## Functional Requirements

**FR-001**: The system MUST support connecting a Fintoc-powered bank account using the
widget-based connection flow (guided in-product widget, no redirect to an external URL).

**FR-002**: The system MUST store the minimal set of Fintoc credentials required to sync
data on behalf of the user, encrypted at rest.

**FR-003**: The system MUST import accounts returned by Fintoc, mapping them to Securo
account types (checking, savings, credit card, or RUT/vista account as applicable).

**FR-004**: The system MUST import transaction history on first connection and subsequently
fetch only new transactions on each sync (incremental sync).

**FR-005**: The system MUST detect and prevent duplicate transaction imports when the same
transaction is returned by Fintoc on multiple sync runs.

**FR-006**: The system MUST detect pending transactions that later become posted and update
the existing record rather than creating a duplicate.

**FR-007**: The system MUST mark a connection as expired/error when Fintoc credentials
become invalid and surface this state to the user so they can reconnect.

**FR-008**: The system MUST expose the list of Fintoc-supported Chilean institutions so
the frontend can display them before the user initiates a connection.

**FR-009**: The system MUST enable/disable the Fintoc provider based on the presence of
the required API configuration (environment variables), consistent with how other providers
are conditionally registered.

**FR-010**: The backend implementation MUST follow the same abstract provider interface,
error hierarchy, and registration mechanism used by Pluggy, Enable Banking, and SimpleFIN.

## Non-Functional Requirements

**NF-001**: The Fintoc provider integration MUST NOT modify any shared service, ORM model,
or API endpoint that other providers depend on; all Fintoc-specific logic MUST be isolated
to its own provider module.

**NF-002**: Sync latency for a typical Chilean bank account (≤1,000 transactions per sync)
MUST be comparable to the equivalent Pluggy sync under the same infrastructure conditions.

**NF-003**: Credential material (API keys, tokens) MUST be encrypted using the same
encryption mechanism applied to other providers' credentials.

**NF-004**: The integration MUST handle Fintoc API rate limits gracefully (back-off and
retry or skip-and-continue) without surfacing provider internals to the user.

**NF-005**: The implementation MUST include unit tests mirroring the test structure and
coverage level of the existing provider tests (Pluggy, Enable Banking, SimpleFIN).

## Success Criteria

**SC-001**: A user with a Fintoc-supported Chilean bank account can connect their account
and see their transactions in Securo within 5 minutes of starting the flow.

**SC-002**: A connected Fintoc account completes an incremental sync (after initial import)
without user interaction, returning new transactions.

**SC-003**: Zero duplicate transactions are created across multiple sync runs for the same
Fintoc-connected account.

**SC-004**: Connection errors (expired credentials, bank unavailability) are reflected in
the connection status within one sync cycle, and the user receives a recoverable in-product
notification.

**SC-005**: The Fintoc provider passes the same test suite structure used by other providers,
with all happy-path and key error scenarios covered.

## Key Entities

These entities are already modeled in the system; Fintoc uses them without schema changes:

- **BankConnection** — one record per Fintoc link; stores provider = "fintoc", encrypted
  credentials, connection status, institution name, logo URL, and last sync timestamp.
- **Account** — one record per Fintoc account; linked to the BankConnection via
  connection_id; stores type, balance, currency, and external_id (Fintoc account ID).
- **Transaction** — one record per transaction; linked to an Account; stores external_id
  (Fintoc movement ID), amount, date, status (posted/pending), description, payee, and
  raw_data for auditability.

## Out of Scope

- Fintoc support for countries other than Chile (Mexico and others Fintoc may serve are
  explicitly out of scope for this iteration).
- Investment/holding data from Fintoc (no equivalent to Pluggy's investment accounts in
  the initial integration; can be added later if Fintoc exposes it).
- Credit card bill objects (Fintoc does not expose bill-level data; transaction-level
  import covers the use case).
- Fintoc webhook-driven real-time sync (scheduled and manual sync are sufficient for
  this iteration).
- Frontend implementation (UI changes are a follow-on feature after backend is stable).

## Assumptions

- Fintoc uses a widget-based connection flow (FintocLink) similar to Pluggy, not an OAuth
  redirect, making `flow_type = "widget"` the appropriate classification.
- Fintoc's transaction API supports date-range filtering sufficient for incremental sync
  (fetching only transactions since `last_sync_at`).
- Account types returned by Fintoc map onto the system's existing types (checking, savings,
  credit_card); the RUT/vista account (Cuenta Vista/RUT) is treated as checking.
- Fintoc's movement IDs are stable across repeated API calls, enabling reliable
  duplicate detection via `external_id`.
- No database schema changes are required; the existing BankConnection, Account, and
  Transaction models accommodate Fintoc data.
- Fintoc's API key is a long-lived server-side secret; per-link credentials (tokens)
  stored in BankConnection.credentials are sufficient for ongoing sync.

## Dependencies

- Fintoc developer account and sandbox API credentials must be available before backend
  development can begin.
- Fintoc's production API access (Chilean banks) requires approval by Fintoc; sandbox
  testing can proceed in parallel with the approval process.
- The existing abstract provider interface (`BankProvider` in `app/providers/base.py`)
  must remain backward-compatible; no changes to other provider files are permitted.

## Constitution Compliance

| Principle | How this feature complies |
|-----------|--------------------------|
| I. Preserve Existing Behavior | All Fintoc logic is isolated to a new module; no existing provider logic is modified |
| II. Stack & Architecture Fidelity | Follows the existing BankProvider ABC and registration pattern; no new libraries required beyond an HTTP client already in use |
| III. Regression Testing Mandate | Unit tests for Fintoc provider mirroring existing provider test structure |
| IV. API & Database Compatibility | No schema changes; no API contract changes; new provider registered conditionally |
| V. Security, Performance & Maintainability | Credentials encrypted; sync performance comparable to peers; provider isolated for maintainability |
| VI. Decision Documentation | This spec documents the integration approach; implementation plan will document technical decisions |
| VII. Style Consistency | Implementation follows existing provider file conventions |
| VIII. Justified Refactoring | No refactoring; purely additive |
