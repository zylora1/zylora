# Responsive guidelines

Representative review widths are 390, 768, 1024, 1280, and 1440 pixels, plus content-driven checks
between them. Breakpoints respond to layout failure, not named devices.

## Public pages

Preserve narrative order and readable measure. Product screenshots crop/recompose intentionally rather
than shrink into illegibility. Navigation becomes a keyboard-safe disclosure; CTAs remain visible but
do not cover content. Editorial asymmetry simplifies on small screens without becoming a stack of
identical cards.

## Portal and Admin

Primary navigation collapses to a labeled drawer/bottom-safe pattern without duplicating DOM focus.
Tables define priority columns and a deliberate record layout at narrow widths; horizontal scrolling is
reserved for genuinely matrix-like data and visibly signaled. Filters become a controlled sheet while
active filters remain evident. Dense Admin operations may state desktop preference but essential
diagnosis/approval remains practical on tablet.

## Editor

Desktop/laptop is the full editing surface. Tablet supports selection, content/style edits, preview,
save state, and history with reorganized panels. Mobile supports preview, safe content edits, save/
history/recovery, and explicit guidance for desktop-only precision tasks—never a broken squeezed canvas.
Device preview width is isolated from browser viewport and labeled accurately.

## Layout safeguards

- Use min/max/clamp and grid/flex intrinsic sizing; avoid fixed heights for text containers.
- Set `min-width: 0` on flexible children and define overflow at the owning component.
- Reserve image/media dimensions and test long names, email, URLs, translations, currency and errors.
- Minimum practical touch target is about 44×44 CSS px; adjacent actions have separation.
- At 200% zoom, content and actions reflow without two-dimensional scrolling except legitimate data
  grids/canvas.
- Safe-area insets, virtual keyboard, sticky headers/footers, dialogs and toast placement are tested.

Responsive completion requires screenshots plus interaction, keyboard, console/network, orientation,
refresh/deep-link and reduced-motion checks—not visual stacking alone.
