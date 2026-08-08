# Component rules

## Primitive ownership

`packages/ui` owns Button, Link, IconButton, Input, Textarea, Select, Checkbox, Radio, Switch, Field,
FormError, Dialog, Drawer, Popover, Tooltip, Menu, Tabs, Accordion, Toast/Notice, Badge/Status, Table,
Pagination, Skeleton, EmptyState, ErrorState, and layout primitives. Feature code composes them and may
not fork behavior casually.

## Variant policy

Variants are semantic and finite: action hierarchy (`primary`, `secondary`, `quiet`, `danger`), size,
density, and state. Avoid variants named after pages or raw colors. Icon-only buttons require accessible
name and tooltip where meaning is not universally obvious. Pills are limited to compact status/filter
chips; ordinary buttons and containers use modest radii.

## Forms

Persistent label, input, optional hint, error, and requirement belong to one Field. Validation occurs
on sensible interaction and submit; server errors map to fields or a clear form summary. Loading never
clears User input. Password/verification controls support paste, password managers, visible resend
cooldown, and recovery. Financial/transfer confirmations restate exact consequence.

## Overlays

Use dialogs only for focused decisions, not primary navigation or long workflows. They trap focus,
label title/description, close safely, restore focus, handle escape/backdrop according to consequence,
and prevent duplicate submission. Mobile may use a designed drawer when content/action order remains
accessible.

## Data display

Tables provide semantic headers, sortable/filterable labels, loading/empty/error states, responsive
priority or alternate record view, and cursor pagination. Status pairs text/icon with semantic color.
Dates clarify timezone; money never omits currency; identifiers can be copied without dominating UI.

## Async feedback

Inline persistent state handles publish/payment/domain/export/deployment and other durable operations;
toasts only acknowledge transient low-risk actions. Skeletons match final geometry. Progress does not
invent percentages. Retry preserves correlation/reference details when useful.

## Component quality gate

Each primitive has typed API, token-only styling, keyboard/focus tests, accessible-name/state tests,
responsive behavior, reduced-motion behavior, Storybook or equivalent state fixtures when introduced,
and no critical console warnings. New one-off values/behaviors trigger design-system review.
