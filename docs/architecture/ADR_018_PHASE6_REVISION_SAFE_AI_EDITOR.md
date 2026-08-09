# ADR 018: Phase 6 uses validated edit plans, immutable revisions, and one AI credit ledger

Status: accepted

Date: 2026-08-12
Authority: the user-approved "Phase 6 - AI Editing + Page-Graph Awareness" amendment

## Context

Phase 4 established independent Template-derived Website Pages and Phase 5 established the persisted
page graph. AI must modify that existing Draft, share the manual editor's data model and invariants,
remain recoverable, and provide a bounded Free experience before subscription selection. A provider
response cannot be trusted as a database command or as evidence that credits should be consumed.

## Decision

- `WebsiteVersion` is the immutable, self-contained validated Website document revision. `Website`
  holds a monotonic revision and current valid-version pointer; each revision also snapshots the
  authoritative Page rows required to restore hierarchy and content.
- Template instantiation, Page Manager commands, manual component/theme edits, validated AI edits,
  and restores all create revisions through `RevisionService`. Restore creates a new revision rather
  than changing history.
- Manual and AI edits use the same strict operation union and `EditorService`. Operations resolve the
  owner-authorized locked Website aggregate, check the client's base revision, enforce PAGE versus
  WEBSITE scope, invoke the canonical Page hierarchy/slug/path validators, validate the complete
  document, and advance the pointer atomically.
- AI follows `plan -> parse -> scope/invariant validation -> atomic apply -> immutable revision`.
  Provider or validation failure records a safe failed operation but neither advances the Draft nor
  consumes credits. Prompts are not persisted; only a SHA-256 digest, safe summary, provider/model,
  usage, latency, status, and safe error are retained.
- `ai_credit_accounts` is the single monthly AI wallet. `ai_credit_ledger` is append-only and uniquely
  keyed per User/operation. Free grants 15 credits per calendar month in Phase 6. Validated operation
  weights are bounded to 1-15 credits; row locking and database constraints prevent a negative
  balance. Manual editing remains available at zero AI balance.
- The real provider adapter uses OpenAI's Responses API with strict JSON-schema structured output,
  `store: false`, a pseudonymous safety identifier, the narrow supplied document/page graph, and the
  `gpt-5.6-terra` default. Development defaults to `disabled`; production requires the server-only API
  key and official OpenAI endpoint. The provider remains behind `AiPlanner` for deterministic tests.
- The editor presents content/AI and Pages/navigation as two views of one portal editor. It offers
  supported-field autosave, responsive preview, explicit PAGE/WEBSITE AI scope, credit balance, and
  revision restore. It does not add blank-canvas placement, collaboration, or plan gating.

The provider choices follow OpenAI's current primary documentation for the
[Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses),
[structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs), and
[GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra).

## Failure and concurrency semantics

Planning occurs without holding database locks. Apply reacquires the aggregate lock and rejects a
stale base revision. All Page/document changes, credit debit, operation success, revision insert, and
current pointer advance commit together. An apply exception rolls that transaction back before a
separate zero-cost failure record is committed. Idempotent operation IDs return the existing result
and cannot debit twice.

## Migration

`20260812_0007_editor_revisions_ai_credits.py` is additive. It copies each Website's source Template
theme, deterministically builds a valid revision from existing Website/Page rows, points the Website
to that revision, and seeds existing Users' 15-credit Free accounts and grants. It preserves valid
Website/Page data. Website revisions reject updates while still allowing an owning Website deletion
to cascade; AI ledger rows reject update and delete.

## Consequences

AI cannot bypass manual invariants, mutate another User's Website, make an invalid home/page graph,
or leave a partial Draft. A User can recover any accepted AI edit. The Phase 7 entitlement service
may change the monthly allowance on this one account/ledger; it must not create another wallet.
Publishing, pricing, final plan resets, analytics, and collaboration cleanup remain outside Phase 6.
