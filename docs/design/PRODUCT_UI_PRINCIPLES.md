# Product UI principles

## One coherent workspace

The User portal is one product with selected Website context, not a dashboard per Website. Navigation
stays stable: Home, Websites, Templates, Leads, Analytics, Credits, Billing, Domains, Notifications,
Settings. Super Admin is a separate operational application and never appears as a User menu mode.

## State before decoration

Every screen answers: what exists, what state is it in, what changed, what can happen next, why might
it be unavailable, and how can the User recover? State names and timestamps come from canonical API
data. Do not reduce deployment/payment/domain failures to generic toasts.

## First use is a path, not empty analytics

A User without meaningful data sees “Publish your first website” and “Choose a Template → Customize →
Publish.” Empty graphs, zero-metric tiles, fake samples, and decorative activity are prohibited.
Empty Leads/Drafts/notifications explain value and offer the relevant action without pretending data.

## Progressive density

Public discovery is visual; Portal management is calm; Editor is focused; Admin is information-dense.
Tables and lists are preferred where users compare many records. Cards are reserved for distinct
objects or decisions, not every piece of text. Search/filter/pagination are server-backed and preserve
URL state/deep links.

## Actions and consequence

One primary action per region. Destructive/financial/ownership actions show scope, consequence, current
state, and recovery before confirmation. Disabled actions explain exact canonical reason. Async actions
show queued/running/success/failure and survive refresh; success appears only after server truth.

## Editor clarity

Canvas, selection, property controls, responsive preview, save status, version history, and Manual/AI
mode share one document context. AI proposes visible structured changes with scope/warnings; it is not a
separate Website generator. Desktop is primary, while essential management/version recovery remains
usable at practical smaller sizes.

## Accessibility and resilience

Semantic elements first, predictable keyboard order, visible focus, labeled controls, logical reading
order, adequate targets/contrast, dialog focus lifecycle, announcements for async state, reduced
motion, and 200% zoom/reflow are component requirements. Refresh, back, deep link, offline/retry,
conflict, and expired session behavior are intentionally designed.

## Trust language

Prices show currency/interval/source timing. Eligibility explains capability evidence. Payment shows
pending until verified. Domain errors show expected and observed DNS. Deployment failure states that
the previous live version remains safe when true. Never imply a provider action succeeded before proof.
