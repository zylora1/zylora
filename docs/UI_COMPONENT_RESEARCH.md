# Zylora UI component and motion research

Status: Approved implementation direction  
Reviewed: 2026-08-12  
Scope: World-class UI/UX and motion rebuild

## Decision summary

Zylora will keep its existing React 19, Next.js 16, CSS Modules, and `@zylora/ui` architecture.
The rebuild will add only two runtime dependencies:

- **Motion for React** for entrance, layout, scroll-linked, and state-transition motion.
- **Embla Carousel** for the landing-page and template-discovery carousels.

Zylora will not install a second broad visual component system. Accessible product primitives remain
owned in `@zylora/ui`, using semantic HTML and the existing design tokens. shadcn/ui and Base UI are
reference implementations for composition and accessibility, not styling sources for this rebuild.
Community component registries are used for technique research only unless a specific component is
separately reviewed and recorded here.

This direction gives Zylora one visual language, a small bundle footprint, predictable ownership,
commercially clear licensing, and a realistic reduced-motion path.

## Evaluation criteria

Each candidate was assessed for:

1. Fit with Zylora's dark-first SaaS shell and structured Website editor.
2. Accessibility, keyboard behavior, and reduced-motion support.
3. React 19 and Next.js App Router compatibility.
4. Runtime and maintenance cost.
5. License clarity for a commercial Website builder.
6. Ability to adapt the technique without copying another product's identity.

## Ecosystem review

| Ecosystem | What was reviewed | License / commercial status | Decision |
| --- | --- | --- | --- |
| [shadcn/ui](https://ui.shadcn.com/docs) | Open-code composition, forms, dialogs, menus, tabs, and token conventions | [MIT](https://github.com/shadcn-ui/ui/blob/main/LICENSE.md); notices must be retained for copied substantial portions | Reference only. Zylora already owns a small primitive layer and does not use Tailwind. Copying the full system would add parallel conventions. |
| [Base UI](https://base-ui.com/) | Headless accessible primitives for dialogs, menus, popovers, tooltips, and forms | MIT | Candidate for a future primitive-by-primitive adoption. Not required for the current public-page motion work, so it is not added speculatively. |
| [React Bits](https://github.com/DavidHDev/react-bits) | Text reveals, animated backgrounds, cards, and cursor effects | MIT plus Commons Clause restrictions in the current repository license | Inspiration only. Zylora is itself a Website/template product, so source reuse presents avoidable redistribution ambiguity. No React Bits code will be copied. |
| [Magic UI](https://github.com/magicuidesign/magicui) | Marquees, beams, borders, number tickers, and animated cards | MIT | Inspiration only. Effects are useful, but importing many copy-owned components would fragment Zylora's motion language. |
| [Motion Primitives](https://github.com/ibelick/motion-primitives) | Disclosure, text, layout, and transition primitives | MIT; project describes itself as beta | Technique reference. Zylora will build a smaller stable set on Motion rather than copy beta primitives wholesale. |
| [Animate UI](https://github.com/imskyleen/animate-ui) | Motion-enhanced shadcn-style controls and disclosures | MIT | Technique reference. Tailwind/shadcn assumptions overlap with the current CSS Modules system. |
| [Aceternity UI](https://ui.aceternity.com/) | Hero highlights, background beams, sticky reveal, bento layouts, and hover cards | Per-item verification required; free and paid registries coexist | Inspiration only. No source is accepted without a component-level license audit, and the signature effects would risk a derivative visual identity. |
| [21st.dev](https://21st.dev/) | Community discovery across thousands of independently authored components and templates | Registry-wide licensing is not uniform; author/template terms can differ | Discovery only. Every item would require its own provenance and license review, so no source is copied during this rebuild. |
| [Motion](https://motion.dev/docs/react) | React animation API, layout animations, gestures, scroll transforms, MotionConfig, and `useReducedMotion` | [MIT](https://github.com/motiondivision/motion/blob/main/LICENSE.md) | **Adopt.** One coherent API covers nearly all required motion with strong React integration and reduced-motion controls. |
| [GSAP / ScrollTrigger](https://gsap.com/docs/v3/Plugins/ScrollTrigger/) | Pinned storytelling, scrubbed timelines, and complex scroll choreography | [GSAP standard license](https://gsap.com/community/standard-license/) is free for permitted commercial use but restricts use in certain visual animation builders | Reject for this phase. Motion and CSS can implement the required sequences, and Zylora should avoid license ambiguity as a visual Website builder. |
| [Embla Carousel](https://www.embla-carousel.com/) | Small composable carousel engine, drag/swipe behavior, plugins, and React wrapper | [MIT](https://github.com/davidjerleke/embla-carousel/blob/master/LICENSE) | **Adopt.** The headless API lets Zylora own markup, focus behavior, controls, and styling while keeping the runtime small. |
| [Swiper](https://swiperjs.com/) | Feature-rich slider, virtual slides, autoplay, effects, and breakpoints | [MIT](https://github.com/nolimits4web/swiper/blob/master/LICENSE) | Reject. It solves more than Zylora needs and duplicates Embla; the larger API and CSS surface would increase maintenance. |

## Dependency, performance, and accessibility review

| Source | Dependencies / integration cost | Performance | Accessibility | Zylora use case and disposition |
| --- | --- | --- | --- | --- |
| shadcn/ui | Tailwind-oriented copied source plus per-primitive Radix dependencies | Good when adopted selectively; a full import would duplicate styles | Strong patterns, but copied implementations remain Zylora's responsibility | Application navigation/forms reference; **reject wholesale adoption**. |
| Base UI | One headless primitive dependency if adopted | Good and tree-shakeable | Accessibility-first headless behavior | Future complex menu/dialog candidate; **not required now**. |
| React Bits | Copy-owned components plus Motion/utility assumptions depending on item | Varies; several canvas/cursor effects are continuous | Varies by community component | Effect research only; **reject source reuse** due builder-license ambiguity and inconsistent needs. |
| Magic UI | Copy-owned Tailwind components, frequently Motion | Generally good per component, but cumulative effect cost is easy to hide | Must be audited per copied component | Technique research for reveals/bento/rails; **reject direct integration**. |
| Motion Primitives | Motion plus copied component source | Good for restrained primitives; project remains beta | Per-component semantics are generally deliberate but still need audit | Disclosure/layout reference; **reject beta source dependency**. |
| Animate UI | Tailwind/shadcn conventions plus Motion | Good for isolated controls | Strong starting patterns, not a substitute for product testing | Application motion reference; **reject parallel styling stack**. |
| Aceternity UI | Per-component and sometimes canvas/WebGL/utility dependencies | Highly variable; signature effects can be expensive | Variable and must be audited item-by-item | Marketing technique research only; **reject source integration**. |
| 21st.dev | Varies by independent author and package | Unknown until item-level audit | Unknown until item-level audit | Discovery only; **reject unverified registry imports**. |
| Motion | One React animation runtime (`motion`) | Good with transform/opacity and small client boundaries | Native reduced-motion policy; semantics remain owned by Zylora | Shared motion, layout, gesture, and scroll system; **use**. |
| GSAP / ScrollTrigger | GSAP runtime and imperative timeline ownership | Excellent runtime, but unnecessary payload/complexity here | Reduced-motion and semantic fallbacks are application work | Complex cinematic scroll candidate; **reject because Motion/CSS meets the need and licensing is ambiguous for a Website builder**. |
| Embla Carousel | One headless carousel runtime (`embla-carousel-react`) | Small, focused, no imposed visual CSS | Zylora owns controls, focus, labels, and keyboard path | Template discovery rail; **use**. |
| Swiper | Larger slider runtime and optional effect modules/CSS | Strong but more capability and CSS than required | Has accessibility facilities but would duplicate Embla ownership | Specialized slider candidate; **reject overlapping dependency**. |

## Component quality gate

Scores apply the required 100-point gate: visual fit /20, UX /15, accessibility /15,
performance /15, maintainability /15, responsiveness /10, dependency cost /5, and license
confidence /5. Anything below 80 is rejected or rebuilt.

| Capability | Visual | UX | A11y | Perf | Maintain | Responsive | Dependency | License | Total | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Motion system | 19 | 15 | 14 | 13 | 15 | 10 | 5 | 5 | **96** | USE |
| Embla template carousel | 19 | 15 | 14 | 15 | 15 | 10 | 5 | 5 | **98** | USE |
| Zylora CSS ambient system | 19 | 14 | 15 | 15 | 15 | 10 | 5 | 5 | **98** | USE |
| Zylora-owned application primitives | 18 | 15 | 14 | 15 | 15 | 10 | 5 | 5 | **97** | USE |
| GSAP / ScrollTrigger for this release | 16 | 13 | 9 | 12 | 9 | 8 | 2 | 2 | **71** | REJECT |
| Unverified 21st.dev component | 14 | 10 | 5 | 7 | 6 | 6 | 2 | 1 | **51** | REJECT |
## Selected components and scoring

Scores are 1–5, where 5 is strongest.

| Selected capability | UX fit | Accessibility | Performance | Adaptability | Maintenance | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Motion reveal / layout primitives | 5 | 5 | 4 | 5 | 5 | Shared durations and easings; transform/opacity first; global reduced-motion policy. |
| Motion scroll-linked product story | 5 | 4 | 4 | 5 | 4 | Used selectively. Sticky layout remains CSS-driven so content still works without JavaScript. |
| Embla template carousel | 5 | 5 | 5 | 5 | 5 | Zylora-owned buttons, labels, live status, focus order, and no forced autoplay. |
| CSS ambient background system | 5 | 5 | 5 | 5 | 5 | Original gradients/noise/grid treatment; decorative layers are hidden from assistive technology. |
| Zylora-owned primitive layer | 5 | 4 | 5 | 5 | 5 | Existing buttons, notices, status, empty/error/loading states remain canonical and gain tokens rather than wrappers. |

## Performance and accessibility constraints

- Default motion uses `transform` and `opacity`; layout-affecting animation is exceptional.
- No mandatory autoplay. Any ambient loop pauses or becomes static under `prefers-reduced-motion`.
- Carousel controls are real buttons with accessible names, visible focus, deterministic order, and a
  non-gesture path.
- Scroll storytelling is progressive enhancement; all content remains readable in document order.
- Heavy motion modules are client components at the smallest practical boundary.
- Decorative light fields, grids, and orbit lines do not receive focus and are `aria-hidden`.
- Focus rings, error messages, labels, and validation state remain visible on the dark surface system.
- No animation may delay authentication, saving, publishing, destructive confirmation, or emergency
  Super Admin actions.

## License and provenance rules

- Motion and Embla are package dependencies governed by their upstream licenses and the repository's
  dependency attribution process.
- No community registry source is copied in this change.
- Visual techniques are re-authored with Zylora tokens, copy, component structure, and interaction
  semantics; named third-party products are never reproduced pixel-for-pixel.
- Any future copied component requires a new row in this document with the exact source revision,
  license, modifications, accessibility review, and dependency footprint before integration.

## Implementation boundary

The approved stack changes presentation only. It must not create alternate Website documents,
client-side entitlement logic, alternate authentication paths, collaboration concepts, or a
blank-canvas editor. Public, User, editor, and Super Admin surfaces continue to consume the existing
authoritative API and structured Website model.
