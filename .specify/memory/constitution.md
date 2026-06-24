<!--
SYNC IMPACT REPORT
==================
Version change: [TEMPLATE] → 1.0.0
Modified principles: N/A (initial ratification — all principles are new)
Added sections:
  - Core Principles (8 principles)
  - Mandatory Acceptance Criteria
  - Development Workflow
  - Governance
Removed sections: N/A (template placeholders replaced)
Templates updated:
  - .specify/templates/plan-template.md ✅ (Constitution Check section aligns with principles)
  - .specify/templates/spec-template.md ✅ (no structural changes required)
  - .specify/templates/tasks-template.md ✅ (no structural changes required)
Deferred TODOs:
  - RATIFICATION_DATE: set to 2026-06-24 (today); confirm with team if a prior governance date applies.
  - Quantitative thresholds for performance and security (SC criteria from spec) are deferred
    until the team defines specific benchmarks. Currently evaluated qualitatively in code review.
-->

# Securo Constitution

## Core Principles

### I. Preserve Existing Behavior

Every change to existing code MUST preserve observable behavior unless the change is
explicitly and intentionally modifying that behavior. Unintended regressions are
constitution violations, not "acceptable side effects."

New contributors MUST read this principle as: "if it worked before, it MUST work after."

### II. Stack & Architecture Fidelity

The established technology stack and architecture MUST be respected in every change:

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, Alembic, Celery, PostgreSQL
- **Frontend**: React 19, TypeScript, Vite, TanStack Query, React Router, Tailwind CSS, shadcn/ui
- **Infrastructure**: Docker, docker-compose

Introducing a new library, framework, or architectural pattern requires a formal written
proposal (ADR or equivalent) reviewed and approved before any code is written. The proposal
MUST explain why the existing stack is insufficient and what migration burden the change
introduces.

### III. Regression Testing Mandate

Any change that modifies the functional behavior of existing code MUST include regression
tests that cover the previous behavior. This is non-negotiable.

Rules:
- Regression tests MUST be written before or alongside the change, never after.
- Tests MUST fail on the old code path being modified to confirm they actually exercise it.
- Backend tests use `pytest`; frontend tests use `vitest`.
- A PR that changes behavior without regression tests MUST be rejected in review.

### IV. API & Database Compatibility

Public API contracts and database schemas are stability boundaries:

- **Breaking API changes** (removed endpoints, changed response shapes, renamed fields) MUST
  be versioned. The old version MUST remain operational through a documented deprecation window.
- **Database schema changes** MUST be delivered as Alembic migrations that are both
  upgrade and downgrade safe.
- **Any breaking change** (API or schema) MUST include a migration plan in the PR description
  before review begins.

### V. Security, Performance, and Maintainability (SPM)

These three criteria are mandatory acceptance gates for every change — not optional
quality signals:

- **Security**: Changes MUST not introduce known vulnerability classes (injection, broken
  auth, insecure defaults, etc.). Security regressions block merge unconditionally, even
  when they conflict with compatibility obligations (security supersedes compatibility).
- **Performance**: Changes to hot paths MUST demonstrate no measurable regression.
  Algorithmic complexity increases require explicit justification.
- **Maintainability**: Code MUST remain readable, testable, and localizable. Increases in
  cyclomatic complexity, hidden coupling, or test surface area require justification.

### VI. Decision Documentation

Technical decisions of consequence MUST leave a recoverable trace. Acceptable forms:
an ADR in `docs/`, a detailed PR description, or a comment referencing the rationale
in a long-lived issue. Decisions made verbally or in ephemeral chat are not compliant.

Decisions that MUST be documented: architectural changes, new dependencies, API contract
changes, security trade-offs, performance trade-offs, and any exception to a constitution
principle.

### VII. Style Consistency

Code style MUST be consistent with the surrounding code in the same file or module.
Personal style preferences are not a valid basis for style changes.

Rules:
- Style-only changes MUST be in a separate PR from functional changes.
- Mass reformatting (entire files or modules) requires explicit team approval.
- Linting and formatting tools (ESLint, Biome, Ruff, or equivalent) govern automated
  style enforcement; manual overrides require a comment explaining why.

### VIII. Justified Refactoring

Large refactors and rewrites of existing modules are high-risk, high-cost operations:

- A "large refactor" is any change that touches more than one module's public interface
  or restructures more than ~20% of a file's lines.
- Large refactors MUST be proposed (ADR or equivalent), approved before coding begins,
  and broken into reviewable increments.
- Rewrites from scratch of existing, working modules are prohibited unless the existing
  code has been demonstrated to be unfit for purpose and incremental improvement is
  provably insufficient.

## Mandatory Acceptance Criteria

Every PR that touches production code MUST satisfy ALL of the following before merge:

| Criterion | Requirement |
|-----------|-------------|
| Regression coverage | Functional changes have regression tests that fail on the old path |
| API/Schema safety | Breaking changes have a migration plan and versioning strategy |
| Security gate | No new vulnerability classes introduced; security issues block unconditionally |
| Performance gate | Hot-path changes show no measurable regression |
| Decision trace | Significant decisions are documented in a recoverable artifact |
| Style compliance | Code matches surrounding style; style changes are in a separate PR |
| Refactor justification | Large refactors have prior written approval |

## Development Workflow

1. **Before coding**: consult this constitution to identify which principles apply.
2. **During coding**: write regression tests alongside (or before) functional changes.
3. **PR description**: state which principles were checked and how the change satisfies them.
4. **Code review**: reviewers MUST verify constitution compliance, not just code correctness.
   A reviewer may reject a PR citing a specific principle without further justification.
5. **Exceptions**: if a legitimate exception to a principle is required, document the
   reason explicitly in the PR or ADR. Undocumented exceptions are violations.
6. **Conflict resolution**: when two principles conflict, the order of precedence is:
   Security > API/Schema Compatibility > Behavior Preservation > Refactor restrictions.

## Governance

This constitution supersedes informal team conventions. Amendments require:

1. A written proposal describing the change and its rationale.
2. Review by at least one other contributor familiar with the affected area.
3. An updated `LAST_AMENDED_DATE` and a version bump following semantic versioning:
   - **MAJOR**: principle removed, redefined, or made less restrictive in a backward-incompatible way.
   - **MINOR**: new principle or section added; existing principles clarified with new obligations.
   - **PATCH**: wording, formatting, or typo corrections with no semantic change.
4. A commit with message `docs: amend constitution to vX.Y.Z — <summary>`.

All PRs and reviews MUST verify compliance with this constitution. The constitution
applies from the ratification date; pre-existing code is not retroactively non-compliant,
but becomes subject to these principles the moment it is modified.

**Version**: 1.0.0 | **Ratified**: 2026-06-24 | **Last Amended**: 2026-06-24
