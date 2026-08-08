# Zylora design system

Status: **Token and behavior contract frozen**

## Color tokens

Initial light theme targets; implementation must verify WCAG contrast for each actual text size/state:

| Token | Value | Use |
| --- | --- | --- |
| `canvas` | `#F3F0E7` | public/page backdrop |
| `surface` | `#FFFEFA` | primary working surface |
| `surface-subtle` | `#EAE6DB` | grouped regions/rows |
| `ink` | `#142A24` | primary text and dark surfaces |
| `ink-muted` | `#52615C` | secondary text |
| `border` | `#CFCBC0` | default rules |
| `border-strong` | `#8E9893` | emphasized separation/input hover |
| `brand` | `#174A3D` | navigation, selected state, dark CTA |
| `brand-hover` | `#103A30` | brand hover |
| `action` | `#A83F27` | high-priority warm action on light surface |
| `action-hover` | `#87321F` | action hover |
| `info` | `#286A67` | informational state |
| `success` | `#23613F` | success |
| `warning` | `#8A5B12` | warning |
| `danger` | `#A33232` | destructive/error |
| `focus` | `#0B68C0` | high-visibility focus outline |

Semantic backgrounds/borders derive as named tokens after contrast testing; components never invent
opacity variants. Dark mode is not assumed until designed and tested as a complete theme.

## Type scale

Fluid public display sizes use `clamp`; application text remains stable and dense. Base line height is
1.55. Named roles: `display-xl`, `display`, `h1`, `h2`, `h3`, `body-lg`, `body`, `body-sm`, `label`,
`caption`, `numeric`, and `code`. Smallest persistent body/caption target is 12–13px only for secondary
metadata with sufficient contrast; controls default to at least 14px.

Heading line height ranges 0.98–1.2, body 1.45–1.7. Headings use balanced wrapping only when it does not
create layout instability. Do not use all caps for paragraphs or long labels.

## Spacing and layout

Base spacing unit is 4px with named steps `1=4`, `2=8`, `3=12`, `4=16`, `5=20`, `6=24`, `8=32`,
`10=40`, `12=48`, `16=64`, `20=80`, `24=96`. Components select named density variants rather than
arbitrary gaps.

Container tokens: `content-narrow=720px`, `content=1120px`, `content-wide=1320px`; page gutters are
16px mobile, 24px tablet, and 32–48px desktop. Application shell columns use explicit min/max and
overflow rules. Readable prose does not span the full content container.

## Shape, border, and elevation

Radii: `sm=4px`, `md=8px`, `lg=12px`, `round=999px` only for circular controls/status chips. Avoid
giant soft card radii. Most structure uses 1px rules and surface contrast. Shadows are `none`, `raised`
(small menu/popover), and `overlay` (dialog); no glow or large diffuse dashboard shadows.

## Motion

Durations: `instant=0`, `fast=120ms`, `standard=180ms`, `deliberate=280ms`, `narrative=480ms` only for
public storytelling. Easings: standard cubic ease-out for entrance/state, ease-in for exit, and a
single emphasized curve. Reduced motion collapses transforms/parallax and preserves immediate state.

## Focus, forms, and states

Focus uses a 2px high-contrast outline plus offset and is never removed without replacement. Inputs
have persistent labels, optional hint, explicit error associated through semantics, and stable height.
Placeholder is example text, not label. Disabled state remains legible and explains why when important.
Read-only and disabled are visually/semantically distinct.

Every component defines default, hover, active, focus-visible, selected, loading, disabled, error,
success where relevant, and reduced-motion behavior. Status never relies only on color.

## Layering

Named z-index layers only: base, sticky, dropdown, popover, modal backdrop, modal, toast. Template
preview/customer content is isolated so its internal z-index cannot escape the frame. Avoid arbitrary
four-digit values.

## Implementation policy

CSS variables express semantic tokens; Tailwind consumes them. shadcn/Radix primitives may supply
behavior but are restyled into these tokens. Arbitrary Tailwind values require review and extraction
when repeated. One icon family, one focus system, one Button/Input/Dialog/Table implementation, and
documented variants prevent utility/component drift.
