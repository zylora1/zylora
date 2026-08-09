# Phase 6 AI editor verification

## Covered behavior

- Template-derived Website documents are revisioned from instantiation onward; Page Manager, manual,
  AI, and restore operations share the same current document and immutable history.
- Manual heading/component updates, structured section insertion, supported theme changes, responsive
  preview, autosave state, optimistic revision conflicts, and restore-as-new-revision.
- AI nested Page creation, Page moves, navigation visibility, canonical hierarchy paths, 100-Page
  graph handling, and PAGE-scope isolation.
- Server rejection of invalid/duplicate slugs, cycles, cross-Website parents, home violations, stale
  revisions, unauthorized/cross-User access, unsupported component properties, and invalid documents.
- Provider, parse, validation, and insufficient-credit failures leave the Draft and balance unchanged;
  success creates one operation, one ledger debit, and one valid revision.
- Free accounts receive an auditable 15-credit monthly grant. Concurrency-safe debit never permits a
  negative balance, and manual editing remains available after exhaustion.
- No plan/subscription is required to edit a Draft or use the bounded Free allowance. No
  collaboration, shared AI session, blank canvas, pricing, publishing, analytics, or billing is added.

## Focused commands

```powershell
npm run migrate:check
npm run migrate
uv run pytest apps/api/tests/integration/test_editor_phase6.py --run-integration -q
uv run pytest apps/api/tests/unit apps/api/tests/integration/test_template_instantiation.py apps/api/tests/integration/test_page_manager.py --run-integration -q
npm --workspace @zylora/web exec -- vitest run src/components/website-editor.test.tsx src/components/page-manager.test.tsx
npm run typecheck
npm run lint
npm run contracts:check
git diff --check
```

The Phase 6 report records final repository-gate, coverage, build, security, and E2E counts.
