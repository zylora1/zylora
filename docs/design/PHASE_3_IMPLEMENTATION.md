# Phase 3 design-system implementation

Status: **Implemented; verification evidence is recorded in `docs/PHASE_3_REPORT.md`**

This document maps the frozen Phase 0 design direction to the Phase 3 production implementation. It
does not change product rules or begin Template-platform work.

## Shared visual system

`packages/ui` owns the Zylora semantic tokens and framework-neutral React primitives. The Web
application imports its token stylesheet once from the root layout. Warm limestone and paper
surfaces, botanical ink, restrained vermilion actions, a single blue focus color, compact radii,
quiet borders, limited elevation, and finite motion timings implement the frozen “digital atelier”
direction.

The initial primitive set is intentionally small:

- finite-variant Button and ActionLink;
- StatusBadge and Notice for measured state;
- PageHeader for consistent hierarchy;
- EmptyState, ErrorState, and Skeleton for honest asynchronous states.

Lucide supplies one outline icon family. Icons supplement visible labels; they do not replace names
for navigation or consequential actions. Reduced-motion preferences disable skeleton and shell
movement without hiding information.

## User portal

The authenticated `/app` boundary has one stable navigation model: Home, Websites, Templates, Leads,
Analytics, Credits, Billing, Domains, Notifications, and Settings. Identity is verified against the
existing FastAPI session API before protected content is rendered. Failed verification hides product
content and presents a sign-in recovery action.

The first-use Home screen leads with “Publish your first website,” an approved-Template CTA, and the
Choose → Customize → Publish sequence. It states the multiple-Draft/one-live-Website boundary and
does not fabricate analytics, balances, invoices, health, or other zero-value summaries. Sections
whose owning phases have not run render truthful empty states rather than fake controls.

## Super Admin application

The isolated Admin host retains its own session API, CSRF cookie, navigation, logout destination,
privacy headers, and denser dark shell. Its finite operational navigation covers Users, Websites,
Templates, Commerce, Leads & credits, Domains, Content & email, Health, Audit, and Configuration.

The overview is evidence-led. It explicitly withholds synthetic service, commercial, Website, and
security summaries until authoritative APIs provide measured data. Future operations remain honest
empty states and do not invent alternate backend transitions.

## Responsive and state behavior

Desktop uses a persistent sidebar and restrained content width. At 1024 pixels the content stacks
without losing navigation. At 768 pixels and below, the same navigation DOM becomes a drawer with a
scrim, Escape dismissal, visible focus, 44-pixel controls, and no horizontal overflow. Page headers,
first-use content, and Admin evidence panels reflow to one column on constrained screens.

App-route `loading.tsx` and `error.tsx` boundaries use the shared state language. Shell identity
loading uses skeletons; session verification failures fail closed. Private routes and Admin-host
rewrites emit `noindex, nofollow` and `private, no-store` while the public root remains indexable.

## Verification contract

The production-browser audit covers 390, 768, 1024, 1280, and 1440 pixels. It checks keyboard entry,
drawer interaction, Escape dismissal, reduced motion, deep-link refresh, horizontal overflow,
console warnings/errors, failed requests, WCAG A/AA axe rules, loading, empty, and fail-closed error
states. Named screenshots remain Playwright artifacts and are not committed.
