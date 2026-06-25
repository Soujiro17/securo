# Feature Specification: Fix Fintoc Bank Account Sync

**Feature Branch**: `feat/fintoc-bank-connection`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "Necesitamos corregir la integración de Fintoc en el frontend y backend. Actualmente no sé que estamos creando, pero la idea de sincronizar es crear la cuenta bancaria a sincronizar en nuestro backend y sincronizar los movimientos, saldo e información de la cuenta."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect a Chilean Bank Account (Priority: P1)

A user wants to link their Chilean bank account (e.g., Banco de Chile, BancoEstado, Santander) so that Securo automatically imports their transactions and balance.

The user clicks "Connect bank account", selects Fintoc as the provider, completes the bank authentication flow inside the Fintoc widget, and is redirected back to Securo. At this point, the bank account appears in their account list with the correct name, institution, and current balance.

**Why this priority**: Without this working, the entire Fintoc integration delivers no value. It is the entry point for all subsequent sync operations.

**Independent Test**: Open the bank connection dialog, complete the Fintoc widget with test credentials, and verify that a new bank account entry appears in the Securo account list showing the bank name and current balance.

**Acceptance Scenarios**:

1. **Given** a logged-in user on the Accounts page, **When** they initiate a Fintoc bank connection and successfully authenticate in the widget, **Then** one or more bank accounts appear in their account list with correct name, institution, type (checking/savings), and current balance.
2. **Given** the same user, **When** the bank connection is established, **Then** the system stores the secure credentials needed for future syncs without exposing them in the UI.
3. **Given** the widget flow is interrupted (user closes window or cancels), **When** the dialog closes, **Then** no partial or empty account records are created and no error is shown.

---

### User Story 2 - Sync Movements and Balance (Priority: P1)

After a bank account is connected, the user wants to see their recent transactions in Securo. The system fetches the last 90 days of movements from the bank and displays them as transactions with correct amounts, dates, descriptions, and direction (debit/credit).

**Why this priority**: Seeing transactions is the core value of bank integration. Without this, the account connection is meaningless.

**Independent Test**: After a bank connection is created, trigger a sync manually or verify the initial sync runs automatically. Confirm that transactions appear with correct date, amount (in CLP), description, and type (debit/credit).

**Acceptance Scenarios**:

1. **Given** a connected bank account, **When** the initial sync runs after connection, **Then** transactions from the last 90 days appear in the user's transaction list with correct amounts, dates, and descriptions.
2. **Given** an existing connected account, **When** the user triggers a manual sync, **Then** new transactions since the last sync are added without duplicating existing ones.
3. **Given** an account with many transactions, **When** the sync is performed, **Then** all pages of results are fetched (pagination is handled transparently) and the user sees the complete transaction history.

---

### User Story 3 - View Account Balance and Info (Priority: P2)

The user wants to see up-to-date balance information for each connected bank account. The account card shows the current available balance in Chilean Pesos (CLP) and reflects the account type.

**Why this priority**: Balance accuracy is important but the account connection and transaction sync deliver the primary value first.

**Independent Test**: After sync, verify the account card shows the correct available balance matching what the bank reports, expressed in CLP.

**Acceptance Scenarios**:

1. **Given** a connected bank account after sync, **When** the user views their accounts, **Then** each account displays its available balance in CLP, the institution name, and the account type (checking or savings).
2. **Given** an account with a balance update at the bank, **When** a sync is performed, **Then** the balance shown in Securo is updated to match.

---

### Edge Cases

- What happens when the Fintoc widget token expires before the user completes authentication?
- How does the system handle a bank that returns zero accounts after a successful widget connection?
- What happens when a re-sync is attempted on a connection whose credentials have been revoked by the bank?
- How does the system handle duplicate movement IDs (same transaction returned twice across paginated calls)?
- What happens when the bank returns an amount of zero for a movement?

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST present the Fintoc bank connection widget when a user initiates a bank connection for a Chilean provider.
- **FR-002**: The system MUST exchange the Fintoc widget completion token for a secure, long-lived credential stored server-side.
- **FR-003**: The system MUST create one bank account record per account returned by the bank after a successful connection, with name, type, balance, currency, and institution.
- **FR-004**: The system MUST sync movements (transactions) for each connected account covering the last 90 days on initial connection.
- **FR-005**: Each transaction MUST include: date (settlement date), amount (in account currency), description, and direction (debit or credit).
- **FR-006**: The system MUST handle paginated movement responses from the bank, fetching all pages before completing the sync.
- **FR-007**: The system MUST prevent duplicate transactions — if a movement has already been imported, a re-sync MUST NOT create a second record.
- **FR-008**: The system MUST update the account balance on each successful sync to reflect the current available balance.
- **FR-009**: The system MUST surface a clear error message to the user if the connection flow fails at any step.
- **FR-010**: The system MUST NOT expose the long-lived bank credentials in the frontend or API responses.
- **FR-011**: When a connection's credentials are revoked or expired, the system MUST mark the connection as requiring re-authentication and prompt the user accordingly.

### Key Entities

- **BankConnection**: Represents the link between a user's Securo workspace and a specific bank. Holds institution name, provider identifier, status, and encrypted credentials.
- **Account**: A single bank account within a connection. Has name, type (checking/savings), current balance, currency, and a stable external identifier from the provider.
- **Transaction**: A single movement on an account. Has date, amount, currency, description, direction (debit/credit), status (posted), and a stable external identifier to prevent duplicates.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the full bank connection flow (from clicking "connect" to seeing their accounts and transactions) in under 3 minutes.
- **SC-002**: 100% of movements returned by the bank are imported on initial sync, with no duplicates across repeated syncs.
- **SC-003**: Account balances displayed in Securo match the bank-reported available balance within a single sync cycle.
- **SC-004**: A failed connection attempt (widget cancelled or error) leaves zero orphaned records in the system.
- **SC-005**: Re-sync of an existing connection adds only new movements — existing transaction count does not change if no new movements exist at the bank.

---

## Assumptions

- The Fintoc widget is loaded from Fintoc's CDN at runtime; no local bundling of the widget library is required.
- Only individual accounts (not business accounts) are in scope for this fix.
- Only Chilean banks supported by Fintoc are in scope (`country=cl`).
- The user's Securo workspace already exists before initiating a bank connection.
- CLP (Chilean Peso) is the primary currency; all amounts from Fintoc are whole integers representing pesos with no decimal scaling.
- The Fintoc credentials (public key and secret key) are already configured in the deployment environment.
- Investments, credit card bills, and webhooks are out of scope for this fix.
- The existing transaction deduplication mechanism (keyed on external movement ID) is preserved and extended to cover Fintoc movements.
- Mobile support is out of scope; only the web interface is targeted.
