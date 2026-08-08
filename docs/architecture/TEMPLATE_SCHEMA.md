# Zylora V2 Template and Website document schema

Status: **Conceptual schema v1 frozen; machine-readable JSON Schema is Phase 4 work**

## Purpose

Templates and Websites share one safe, structured, versioned document. A Website begins as a deep
copy/reference-resolved snapshot of an approved Template version. Manual controls and AI commands
apply the same typed patch vocabulary. The renderer interprets registered components; it never
executes stored JavaScript or trusts arbitrary HTML/CSS.

## Root document

```json
{
  "schema_version": "1.0.0",
  "document_id": "opaque-id",
  "metadata": {},
  "theme": {},
  "assets": {},
  "pages": [],
  "features": {},
  "requirements": {},
  "provenance": {}
}
```

Unknown root fields are rejected for the current major version. Documents have bounded serialized
size, page count, component count, tree depth, text length, asset count, animation count, and reference
fan-out to protect render/editor/AI cost.

## Metadata

Required Template metadata:

- stable internal title and unique catalog slug;
- industry/category and tags by referenced IDs;
- concise, realistic description and demo-content disclosure;
- supported pages, component capabilities, interactions, animations, and editor controls;
- desktop/tablet/mobile preview assets;
- license/provenance summary;
- minimum renderer/editor versions and schema version;
- locale/direction support and accessibility notes;
- quality attributes and computed Website requirement keys.

Website metadata adds User-controlled safe display name and editing provenance; it does not add an
account container or arbitrary execution configuration.

## Theme and tokens

```json
{
  "theme": {
    "tokens": {
      "color": {"surface": {}, "text": {}, "brand": {}, "semantic": {}},
      "typography": {"families": {}, "sizes": {}, "weights": {}, "line_heights": {}},
      "spacing": {},
      "radii": {},
      "borders": {},
      "shadows": {},
      "layout": {},
      "motion": {},
      "breakpoints": {"mobile": 0, "tablet": 768, "desktop": 1024}
    },
    "modes": {"default": {}, "dark": null}
  }
}
```

Token keys follow a registry and values use safe typed formats. Colors are parsed/normalized; lengths
use allowed units/ranges; font families come from an approved licensed registry; URLs are not allowed
inside generic token values. Responsive overrides reference semantic breakpoints, not arbitrary media
queries.

## Pages and tree

```json
{
  "id": "page_home",
  "name": "Home",
  "slug": "/",
  "status": "enabled",
  "seo": {},
  "root": {
    "id": "section_hero",
    "type": "section.hero.split.v1",
    "props": {},
    "style": {},
    "responsive": {},
    "interactions": [],
    "children": []
  }
}
```

IDs are unique within the document and generated independently from text. The tree is acyclic and has
bounded depth. Component types are exact registry names with version. A parent type declares allowed
child slots/cardinality. Links between pages reference page IDs plus validated anchors so slug changes
can be migrated safely.

## Component registry

Each registered component declares:

- versioned type ID and compatible renderer/editor versions;
- props JSON Schema with defaults, ranges, formats, and localization behavior;
- named child slots and allowed child types/cardinality;
- editable property map and which roles/surfaces may edit it;
- style capabilities and token bindings;
- responsive override capabilities;
- accessibility contract and generated semantics;
- allowed interactions/animations;
- Website requirement contributions;
- migration functions and deprecation policy;
- deterministic server/client rendering test fixtures.

Initial families support navigation, hero, rich text, headings, images, buttons/links, containers,
grids, cards, services, testimonials, galleries, forms, FAQ/accordion, tabs, carousel, counters,
modal triggers, contact details, maps through an approved adapter, social links, footer, and chatbot
mount. More specific industry components require the same registry process.

No component accepts raw `<script>`, inline event handlers, `dangerouslySetInnerHTML`, arbitrary CSS,
unbounded iframe origins, or executable URL schemes. Rich text uses a constrained structured AST and
sanitized renderer.

## Props and editable fields

Editable fields are explicit paths with control metadata:

```json
{
  "path": "/pages/page_home/components/hero/title",
  "kind": "text",
  "label": "Headline",
  "constraints": {"min_length": 1, "max_length": 120},
  "responsive": false,
  "ai_editable": true
}
```

Supported controls cover text content/typography/alignment/color, buttons/links/appearance, validated
images/crop/alt/dimensions, supported container spacing/background/border/layout, navigation labels and
menus, form fields/validation, card/media/CTA, section visibility/style, footer business/social data,
and page SEO. Controls can constrain rather than expose every underlying prop.

## Responsive model

Base props target mobile-first behavior. A component may contain registry-approved overrides for
`tablet` and `desktop`; optional explicit mobile overrides exist only when the base cannot express the
design. Breakpoint keys are semantic, values are platform tokens, and Templates cannot inject raw
media queries.

Layout validation checks min/max widths, overflow, touch targets, typography, image aspect behavior,
navigation collapse, interaction alternatives, and ordered content at representative widths 390,
768, 1024, 1280, and 1440 pixels.

## Assets

The document asset map references asset IDs, not arbitrary storage keys:

```json
{
  "asset_hero": {
    "kind": "image",
    "source_id": "asset-record-id",
    "alt": "A clinician speaking with a patient",
    "width": 1600,
    "height": 1067,
    "variants": ["640w", "960w", "1600w"],
    "focal_point": {"x": 0.6, "y": 0.42}
  }
}
```

Server records own detected MIME, checksum, dimensions, processing/provenance/license state, and
public/private policy. Documents cannot reference local paths, credentials, data URLs above a tiny
allowlist, or unapproved remote origins. Missing/failed assets block Template publication.

## Links, navigation, and forms

Links use typed destinations: internal page, same-page anchor, external HTTPS URL, `mailto`, or `tel`.
Protocols, host policy, `rel`, target, and accessible labels are validated. Navigation describes menus
as structured items with bounded depth; mobile behavior is a registered variant.

Forms use registered fields, labels, validation, consent text/version, spam controls, success/error
copy, and one destination: the Website-scoped Lead service. They cannot configure arbitrary webhook
URLs, notification recipients, database targets, or credit amounts. The server derives Website and
owner from the published site context.

## Interactions and motion

Interactions are declarative allowlisted commands:

- open/close a registered dialog;
- select tab/accordion/carousel item;
- navigate to a validated link/anchor;
- submit a registered form;
- toggle an approved menu/disclosure;
- start/pause a media/gallery behavior within policy.

Animations reference named presets plus bounded duration/delay/distance/easing. Scroll reveal,
hover/focus, parallax, sticky, counter, carousel, and transition behavior must define reduced-motion
and keyboard/touch alternatives. Animation cannot change authorization, fetch arbitrary URLs, execute
code, hijack scrolling, or hide essential content indefinitely.

## SEO model

Each page stores validated title, meta description, slug, canonical policy, Open Graph title/
description/image, sitemap inclusion, robots directives, and structured-data descriptors. Headings are
derived from semantic component roles and validated for hierarchy. Structured data uses approved
schema types and typed fields; arbitrary JSON-LD/script strings are rejected.

## Feature requirements

Components emit normalized capabilities, for example:

```json
{
  "page_count": 7,
  "capabilities": ["custom_domain", "advanced_carousel", "lead_form"],
  "quantities": {"forms": 2, "asset_bytes": 4200000}
}
```

This stored block is a cache for display/build planning. `WebsiteRequirementService` recomputes it
from the authoritative document and registry version before publish. Clients cannot lower it.

## Safe patch vocabulary

Patches are not unrestricted RFC 6902. Allowed commands include:

```text
set_prop(component_id, property, typed_value)
set_style_token(component_id, property, token_or_validated_value)
set_responsive_prop(component_id, breakpoint, property, typed_value)
replace_asset(component_id, property, asset_id, crop, alt)
insert_component(parent_id, slot, position, registered_component)
remove_component(component_id)
move_component(component_id, new_parent_id, slot, position)
set_page_seo(page_id, typed_seo_fields)
add_page(from_registered_page_pattern, slug)
remove_page(page_id)
rename_navigation_item(item_id, label)
set_link(target_id, typed_destination)
```

Every request includes base WebsiteVersion, operation IDs, and scope. The server:

1. authorizes current ownership and edit state;
2. verifies operation count/size/rate limits;
3. resolves IDs and editable-property policy;
4. applies commands to an isolated copy;
5. validates component, document, accessibility, link, asset, responsive, and requirement rules;
6. computes checksum/diff and rejects no-op or unsafe changes;
7. creates one immutable WebsiteVersion and advances the draft pointer atomically.

AI output is parsed into this exact command set and cannot request a bypass. AI provenance stores
provider/model, prompt-template version, token/usage/cost estimate, latency, safety result, operation
IDs, and final accepted diff without logging secrets or unnecessary personal data.

## Schema versioning and migration

Schema version uses semantic major/minor/patch semantics:

- patch: validation clarification/default with identical meaning;
- minor: backward-compatible fields/components;
- major: incompatible document shape requiring explicit migration.

Migrations are pure, deterministic functions from exact source version to next version, producing a
new immutable Template/Website version and migration report. They never mutate published history.
The renderer supports a documented compatibility window; a version outside it is migrated in a
staging copy and validated before publish/edit. Migration is idempotent by source checksum + target
schema + migrator version.

Component deprecation stages are announce, prevent new Template use, migrate compatible documents,
validate, then retire renderer support. Security-critical retirement can block republish and trigger
admin-visible remediation.

## Template validation pipeline

Publication requires all blocking checks:

1. JSON/schema/component registry validation and document limits.
2. Asset existence, checksum, MIME/dimensions, license/provenance, and malware state.
3. Link/protocol/anchor and form destination validation.
4. Server and browser rendering across required viewports/pages/states.
5. Editor load, representative manual patch, AI-patch fixture, autosave, and restore compatibility.
6. Accessibility baseline: semantics, headings, names, focus, keyboard, contrast, reduced motion.
7. Runtime: no console error, failed required request, unsafe CSP violation, hydration failure, or
   unsupported component.
8. SEO metadata/canonical/sitemap/structured-data validation.
9. Performance budgets for JS, CSS, image weight, DOM/component count, layout shift, and severe Web
   Vitals regressions.
10. Visual review for industry fit, typography, hierarchy, realism, meaningful differentiation, and
    desktop/tablet/mobile quality.

Validation output is versioned by document checksum, registry, renderer, validator, browser, and
viewport matrix. Approval cannot reuse stale results after any relevant input changes.

## Export contract

The paid ZIP generator consumes one immutable validated WebsiteVersion and a public-runtime export
profile. It emits only documented static/runtime files, content-hashed assets, metadata, instructions,
and an artifact manifest. It strips internal IDs where unnecessary, private API endpoints, admin
controls, secrets, provider credentials, logs, other Websites' assets, Draft history, analytics raw
data, Leads, chatbot conversations, and platform-only deployment artifacts.

Archive entry paths are generated by the server, normalized, bounded, and scanned to prevent absolute
paths, `..`, symlinks, device names, archive bombs, and executable surprises.
