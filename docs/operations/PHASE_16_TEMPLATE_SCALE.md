# Phase 16 template scale operation

## Preconditions

Run this operation only after migrations are current and a verified active Super Admin exists. The
catalogue is Template-first: every record must be validated, approved, and published before users
can select it. Do not import rows directly into the Template tables.

## Release workflow

1. Run `npm run templates:validate-scale`. It must report passing 50, 100, 250, 500, and 1,000
   candidate milestones.
2. Run `npm run seed:templates`. The operation is idempotent, validates the same gates before it
   contacts the database, and commits only bounded batches of 50 canonical lifecycle operations.
3. Confirm the active published total, category count, and each of the five page of results from
   `GET /api/v1/templates?limit=24` in the production-like environment.
4. In the public gallery, visually inspect a representative Template from every category, voice
   (`voice-*`) and layout (`layout-*`) tag family at desktop, tablet, and mobile widths. Check
   hierarchy, readable copy, category fit, responsive spacing, real lead-form fields, and the
   absence of fabricated testimonials or unsupported claims.
5. Exercise category, capability, search, sort, and Load more controls with keyboard navigation.
   The grid must remain bounded and must not create horizontal overflow.

## Failure handling

A failed scale gate or lifecycle validation blocks the seed; correct the generator or source data,
then rerun the full milestone validation. Do not patch hundreds of generated records individually.
If a visual sample reveals systematic repetition, weak hierarchy, poor category fit, or a mobile
problem, correct the relevant profile, archetype, or layout method and regenerate deterministically.

The seed never deletes or overwrites an existing Template. To remove a published Template, use the
normal Super Admin lifecycle and document the release decision separately.
