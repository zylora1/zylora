# Phase 5 Page Manager verification

## Covered behavior

- Tree projection at 1, 5, 30, and 100 Pages, including collapse, search, active selection, compact
  scrolling, keyboard movement, and template-defined hierarchy on first open.
- Owner-authorized add, rename, status/SEO update, reorder, nest, unnest, move-to-root, and navigation
  visibility commands across multiple Drafts without a subscription.
- Server rejection of invalid/empty/reserved slugs, duplicate sibling paths, self/cyclic/cross-Website
  parents, unauthorized access, invalid home changes, and ambiguous parent deletion.
- Explicit parent delete promotion, navigation regeneration, nested canonical paths, descendant path
  history, immutable Template sources, and no collaboration or plan-gating UI.
- Desktop and Pixel 7 Chromium coverage with a 100-Page mutable fixture, Axe WCAG A/AA scan, responsive
  assertions, and screenshot artifacts.

## Focused commands

```powershell
uv run pytest apps/api/tests/unit/test_page_manager_unit.py apps/api/tests/unit/test_website_http.py apps/api/tests/integration/test_page_manager.py --run-integration -q
npm --workspace @zylora/web exec -- vitest run src/components/page-manager.test.tsx
npm --workspace @zylora/web exec -- playwright test e2e/page-manager.spec.ts
```

The phase report records the complete repository-gate commands and final counts. Browser screenshot
artifacts under `apps/web/test-results` are generated evidence and are not committed.
