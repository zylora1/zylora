# Motion guidelines

Motion communicates causality, hierarchy, continuity, and feedback. It is not proof of quality.

- Micro state (hover/focus/press): 120–180ms, opacity/color/very small transform.
- Overlay/layout continuity: 180–280ms, stable origin, focus available after entrance.
- Public narrative demo: up to 480ms per step with pause/control and no reading obstruction.
- Indeterminate work uses calm progress; durable job state survives navigation and refresh.

Animate transform/opacity where possible; avoid layout-heavy properties and large simultaneous motion.
No scroll hijacking, cursor followers, perpetual floating, arbitrary parallax, count-up fake metrics,
or animation that delays essential content/actions.

`prefers-reduced-motion` removes parallax/reveal travel, shortens transitions, disables autoplay, and
presents the same information immediately. Hover-only behavior always has focus/touch equivalents.
Animations cannot hide focus, change semantic order, or communicate status by movement alone.

Template interactions use registered presets with bounds and fallbacks. Validation checks keyboard,
touch, reduced-motion, offscreen work, cumulative layout shift, and cleanup after navigation.
