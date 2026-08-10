"""Deterministic, reviewed Template catalogue generation for Phase 16 scale-up."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from zylora_api.modules.templates.validation import document_checksum, validate_document

SCALE_TARGET = 1_000
SCALE_MILESTONES = (50, 100, 250, 500, SCALE_TARGET)


@dataclass(frozen=True)
class CategoryProfile:
    slug: str
    name: str
    description: str
    industry: str
    audience: str
    stems: tuple[str, ...]


@dataclass(frozen=True)
class Archetype:
    slug: str
    theme: str
    promise: str
    service_angle: str
    page_mode: int


@dataclass(frozen=True)
class Layout:
    slug: str
    sequence: tuple[str, ...]
    palette: tuple[str, str]
    heading_font: str


@dataclass(frozen=True)
class ScaleQualityReport:
    count: int
    categories: int
    archetypes: int
    layouts: int
    page_counts: tuple[int, ...]
    valid: bool
    errors: tuple[str, ...]


CATEGORY_PROFILES = (
    CategoryProfile(
        "health-wellness",
        "Health & Wellness",
        "Professional sites for care, wellbeing, and trusted local services.",
        "care practice",
        "people seeking considered care",
        (
            "Aster",
            "Cedar",
            "Juniper",
            "Meadow",
            "Northstar",
            "Orchard",
            "River",
            "Solace",
            "Tamarind",
            "Willow",
        ),
    ),
    CategoryProfile(
        "creative-studios",
        "Creative Studios",
        "Editorial portfolios for architecture, design, and independent practices.",
        "creative studio",
        "clients considering a distinctive practice",
        (
            "Arc",
            "Atelier",
            "Canvas",
            "Form",
            "Grain",
            "Linework",
            "Morrow",
            "North",
            "Studio",
            "Vernacular",
        ),
    ),
    CategoryProfile(
        "food-hospitality",
        "Food & Hospitality",
        "Inviting digital homes for restaurants, cafes, and hospitality businesses.",
        "hospitality business",
        "guests planning a visit",
        (
            "Amber",
            "Basil",
            "Cinder",
            "Ember",
            "Field",
            "Juniper",
            "Larder",
            "Marrow",
            "Olive",
            "Saffron",
        ),
    ),
    CategoryProfile(
        "professional-services",
        "Professional Services",
        "Clear, credible websites for advisory, legal, and specialist service firms.",
        "advisory practice",
        "people making an important decision",
        (
            "Alder",
            "Beacon",
            "Civic",
            "Dovetail",
            "Elm",
            "Factual",
            "Grove",
            "Harbor",
            "Meridian",
            "Northfield",
        ),
    ),
    CategoryProfile(
        "fitness-movement",
        "Fitness & Movement",
        "Energetic but focused sites for coaches, studios, and movement practices.",
        "movement practice",
        "people ready to build a consistent habit",
        (
            "Anchor",
            "Cadence",
            "Form",
            "Kinetic",
            "Motion",
            "Pace",
            "Peak",
            "Pulse",
            "Steady",
            "Summit",
        ),
    ),
    CategoryProfile(
        "home-trades",
        "Home & Trades",
        "Practical, reassuring websites for local crafts, property, and home services.",
        "home service",
        "households planning a practical project",
        (
            "Brick",
            "Craft",
            "Fieldstone",
            "Frame",
            "Hearth",
            "Oak",
            "Porch",
            "Ridge",
            "Stone",
            "Workshop",
        ),
    ),
    CategoryProfile(
        "nonprofit-community",
        "Nonprofit & Community",
        "Open, action-led websites for community organisations and mission-driven groups.",
        "community organisation",
        "people looking for a meaningful way to participate",
        (
            "Common",
            "Gather",
            "Harbor",
            "Kin",
            "Local",
            "Mosaic",
            "Neighbour",
            "Openhand",
            "Shared",
            "Tomorrow",
        ),
    ),
    CategoryProfile(
        "retail-lifestyle",
        "Retail & Lifestyle",
        "Distinctive storefronts for independent retail, makers, and lifestyle brands.",
        "independent brand",
        "people choosing something with character",
        (
            "Alloy",
            "Bramble",
            "Cove",
            "Fable",
            "Hearth",
            "Morrow",
            "Nook",
            "Rowan",
            "Sable",
            "Woven",
        ),
    ),
    CategoryProfile(
        "education-coaching",
        "Education & Coaching",
        "Clear learning paths for educators, coaches, and specialist programs.",
        "learning practice",
        "people ready to make steady progress",
        (
            "Ahead",
            "Brightpath",
            "Compass",
            "Flourish",
            "Lesson",
            "Mindset",
            "Northstar",
            "Practice",
            "Stepwise",
            "Thrive",
        ),
    ),
    CategoryProfile(
        "technology-saas",
        "Technology & SaaS",
        "Focused product marketing sites for practical software and digital services.",
        "software product",
        "teams looking for a practical next step",
        (
            "Atlas",
            "Circuit",
            "Current",
            "Field",
            "Layer",
            "Lumen",
            "Metric",
            "Signal",
            "Stack",
            "Vector",
        ),
    ),
)

ARCHETYPES = (
    Archetype(
        "clarity",
        "Clear direction",
        "Make the next decision easier.",
        "A concise path from question to action.",
        1,
    ),
    Archetype(
        "editorial",
        "Editorial point of view",
        "A point of view worth spending time with.",
        "Context, craft, and useful detail.",
        2,
    ),
    Archetype(
        "service",
        "Service-led",
        "Expertise, made easy to understand.",
        "Practical offers with a direct next step.",
        1,
    ),
    Archetype(
        "local",
        "Grounded locally",
        "Made for the rhythms of this place.",
        "Local knowledge and a welcoming first conversation.",
        2,
    ),
    Archetype(
        "premium",
        "Quiet confidence",
        "Considered work speaks for itself.",
        "Careful detail without unnecessary noise.",
        3,
    ),
    Archetype(
        "growth",
        "Built to grow",
        "A strong foundation for what comes next.",
        "A structured path that can evolve with the work.",
        1,
    ),
    Archetype(
        "community",
        "People first",
        "Bring the right people together.",
        "Participation, practical support, and a clear invitation.",
        2,
    ),
    Archetype(
        "craft",
        "Craft in focus",
        "Details that reward a closer look.",
        "Method, material, and thoughtful delivery.",
        3,
    ),
    Archetype(
        "outcomes",
        "Useful outcomes",
        "Turn a complex need into progress.",
        "Specific help and a simpler route forward.",
        1,
    ),
    Archetype(
        "modern",
        "Modern essentials",
        "Everything useful, nothing distracting.",
        "A focused digital experience for everyday decisions.",
        2,
    ),
)

BRAND_SUFFIXES = {
    "health-wellness": "Care",
    "creative-studios": "Studio",
    "food-hospitality": "House",
    "professional-services": "Advisory",
    "fitness-movement": "Movement",
    "home-trades": "Works",
    "nonprofit-community": "Collective",
    "retail-lifestyle": "Goods",
    "education-coaching": "Learning",
    "technology-saas": "Systems",
}

LAYOUTS = (
    Layout("split-hero", ("services", "faq"), ("#164E46", "#E37A5F"), "MANROPE"),
    Layout("editorial-grid", ("editorial", "services", "faq"), ("#203D63", "#D68B49"), "DM_SERIF"),
    Layout("service-stack", ("services", "story", "faq"), ("#2C342F", "#C46A42"), "MANROPE"),
    Layout("faq-first", ("faq", "services", "story"), ("#5E3B26", "#E3A13B"), "PLAYFAIR"),
    Layout("method-grid", ("editorial", "story", "services"), ("#4D3C64", "#D6A7D8"), "DM_SERIF"),
    Layout("outcome-led", ("services", "faq", "editorial"), ("#174C5A", "#9ED5CC"), "MANROPE"),
    Layout("story-led", ("story", "services", "faq"), ("#6B2E24", "#EAB37A"), "PLAYFAIR"),
    Layout("compact-grid", ("editorial", "faq"), ("#314C3A", "#B5CD83"), "INTER"),
    Layout("guided-steps", ("story", "faq", "services"), ("#3E435F", "#AFC2FF"), "DM_SERIF"),
    Layout(
        "calm-conversion",
        ("services", "editorial", "story", "faq"),
        ("#34414B", "#F0B38B"),
        "MANROPE",
    ),
)


def _slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.casefold())).strip("-")


def _component(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
    *,
    children: list[dict[str, Any]] | None = None,
    interactions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "type": component_type,
        "props": props,
        "children": children or [],
        "responsive": {},
        "interactions": interactions or [],
    }


def _services(profile: CategoryProfile, archetype: Archetype, prefix: str) -> dict[str, Any]:
    return _component(
        f"{prefix}-services",
        "SERVICES",
        {
            "heading": "A useful path forward",
            "items": [
                {
                    "heading": "Start with context",
                    "body": f"Understand what {profile.audience} need before choosing a direction.",
                },
                {
                    "heading": "Focus on the work",
                    "body": f"{archetype.service_angle} for a {profile.industry}.",
                },
                {
                    "heading": "Leave with momentum",
                    "body": "Make the next step clear, specific, and easy to act on.",
                },
            ],
        },
    )


def _editorial(profile: CategoryProfile, archetype: Archetype, prefix: str) -> dict[str, Any]:
    cards = [
        _component(
            f"{prefix}-card-{index}", "CARD", {"eyebrow": eyebrow, "heading": heading, "body": body}
        )
        for index, (eyebrow, heading, body) in enumerate(
            (
                (
                    "Perspective",
                    archetype.theme,
                    f"A {profile.industry} that gives visitors a clear reason to continue.",
                ),
                (
                    "Method",
                    "A considered approach",
                    "Explain how the work happens without making promises you cannot support.",
                ),
                (
                    "Next step",
                    "An open invitation",
                    "Offer a direct, low-friction way to begin a useful conversation.",
                ),
            ),
            start=1,
        )
    ]
    return _component(
        f"{prefix}-editorial",
        "SECTION",
        {
            "eyebrow": "A better starting point",
            "heading": "The details that shape a decision",
            "body": "Use a few precise ideas to build confidence and context.",
        },
        children=[
            _component(f"{prefix}-grid", "GRID", {"columns": 3, "gap": "medium"}, children=cards)
        ],
    )


def _story(profile: CategoryProfile, archetype: Archetype, prefix: str) -> dict[str, Any]:
    return _component(
        f"{prefix}-story",
        "SECTION",
        {
            "eyebrow": archetype.theme,
            "heading": "Make the work easier to understand",
            "body": (
                f"This {profile.industry} is designed for {profile.audience}. "
                "Keep the language direct, the hierarchy useful, and the next action clear."
            ),
        },
    )


def _faq(prefix: str) -> dict[str, Any]:
    return _component(
        f"{prefix}-faq",
        "FAQ",
        {
            "heading": "Questions before you begin",
            "items": [
                {
                    "question": "Where should we start?",
                    "answer": (
                        "Begin with the outcome that matters most, then choose the smallest "
                        "useful next step."
                    ),
                },
                {
                    "question": "Can this change over time?",
                    "answer": (
                        "Yes. The structured Website can grow without losing its hierarchy "
                        "or clear navigation."
                    ),
                },
            ],
        },
    )


def _lead_form(prefix: str) -> dict[str, Any]:
    return _component(
        f"{prefix}-contact",
        "LEAD_FORM",
        {
            "heading": "Start a useful conversation",
            "body": "Share a little context and we will help identify the next step.",
            "fields": [
                {"name": "name", "label": "Name", "type": "text"},
                {"name": "email", "label": "Email", "type": "email"},
                {"name": "message", "label": "What are you working on?", "type": "text"},
            ],
            "consentText": "I agree that this business may respond to my enquiry.",
            "submitLabel": "Send enquiry",
        },
        interactions=[{"trigger": "SUBMIT", "action": "SUBMIT_LEAD"}],
    )


def _footer(name: str, prefix: str) -> dict[str, Any]:
    return _component(
        f"{prefix}-footer",
        "FOOTER",
        {"brand": name, "body": "Clear work, presented with care.", "links": []},
    )


def _home_components(
    profile: CategoryProfile, name: str, archetype: Archetype, layout: Layout
) -> list[dict[str, Any]]:
    prefix = "home"
    components = [
        _component(
            f"{prefix}-navigation",
            "NAVIGATION",
            {
                "brand": name,
                "links": [
                    {"label": "What we do", "link": {"kind": "SECTION", "target": "services"}},
                    {"label": "Start here", "link": {"kind": "SECTION", "target": "contact"}},
                ],
            },
        ),
        _component(
            f"{prefix}-hero",
            "HERO",
            {
                "eyebrow": profile.industry.upper(),
                "heading": archetype.promise,
                "body": f"{name} is a {profile.industry} for {profile.audience}.",
                "primaryCta": {
                    "label": "Start a conversation",
                    "link": {"kind": "SECTION", "target": "contact"},
                },
                "align": "left" if layout.slug not in {"editorial-grid", "story-led"} else "center",
            },
            interactions=[{"trigger": "CLICK", "action": "SCROLL", "target": "contact"}],
        ),
    ]
    fragments = {
        "services": _services(profile, archetype, prefix),
        "editorial": _editorial(profile, archetype, prefix),
        "story": _story(profile, archetype, prefix),
        "faq": _faq(prefix),
    }
    components.extend(fragments[key] for key in layout.sequence)
    components.extend([_lead_form(prefix), _footer(name, prefix)])
    return components


def _supporting_pages(
    profile: CategoryProfile, name: str, archetype: Archetype
) -> list[dict[str, Any]]:
    if archetype.page_mode == 1:
        return []
    about = {
        "id": "about-page",
        "slug": "about",
        "label": "About",
        "parent_page_id": None,
        "sort_order": 1,
        "is_home": False,
        "show_in_navigation": True,
        "status": "ACTIVE",
        "seo": {"title": f"About {name}", "description": f"Learn how {name} approaches its work."},
        "components": [
            _component("about-heading", "HEADING", {"level": 1, "text": "A clearer way to begin"}),
            _component(
                "about-copy",
                "RICH_TEXT",
                {
                    "text": (
                        f"{name} helps {profile.audience} make thoughtful progress through "
                        f"a considered {profile.industry}."
                    )
                },
            ),
            _footer(name, "about"),
        ],
    }
    if archetype.page_mode == 2:
        return [about]
    services = {
        "id": "services-page",
        "slug": "services",
        "label": "Services",
        "parent_page_id": None,
        "sort_order": 1,
        "is_home": False,
        "show_in_navigation": True,
        "status": "ACTIVE",
        "seo": {
            "title": f"Services - {name}",
            "description": f"Explore the services available from {name}.",
        },
        "components": [
            _component(
                "services-heading",
                "HEADING",
                {"level": 1, "text": "Practical support, clearly framed"},
            ),
            _services(profile, archetype, "services-page"),
            _footer(name, "services-page"),
        ],
    }
    approach = {
        "id": "approach-page",
        "slug": "approach",
        "label": "Approach",
        "parent_page_id": "services-page",
        "sort_order": 0,
        "is_home": False,
        "show_in_navigation": True,
        "status": "ACTIVE",
        "seo": {
            "title": f"Approach - {name}",
            "description": f"How {name} turns context into a useful next step.",
        },
        "components": [
            _component(
                "approach-heading", "HEADING", {"level": 1, "text": "Method with room for context"}
            ),
            _story(profile, archetype, "approach-page"),
            _lead_form("approach-page"),
            _footer(name, "approach-page"),
        ],
    }
    return [services, approach]


def _document(
    profile: CategoryProfile, name: str, archetype: Archetype, layout: Layout
) -> dict[str, Any]:
    primary, accent = layout.palette
    return {
        "schema_version": "1.0.0",
        "registry_version": "1.0.0",
        "metadata": {
            "name": name,
            "description": (
                f"{archetype.theme} for a {profile.industry} serving {profile.audience}."
            ),
            "language": "en",
        },
        "theme": {
            "primary": primary,
            "accent": accent,
            "surface": "#FFFDF8",
            "ink": "#17211D",
            "heading_font": layout.heading_font,
            "body_font": "INTER",
        },
        "assets": [],
        "pages": [
            {
                "id": "home-page",
                "slug": "home",
                "label": "Home",
                "parent_page_id": None,
                "sort_order": 0,
                "is_home": True,
                "show_in_navigation": True,
                "status": "ACTIVE",
                "seo": {
                    "title": name[:60],
                    "description": (
                        f"{archetype.promise} {profile.industry.capitalize()} support with a "
                        "clear next step."
                    )[:160],
                },
                "components": _home_components(profile, name, archetype, layout),
            },
            *_supporting_pages(profile, name, archetype),
        ],
        "features": ["LEAD_CAPTURE", "RESPONSIVE_PREVIEW"],
        "requirements": ["LEAD_CAPTURE"],
        "provenance": "CURATED",
    }


def build_scaled_catalogue(limit: int = SCALE_TARGET) -> list[dict[str, Any]]:
    """Build up to 1,000 category-balanced, semantically distinct curated Templates."""
    if not 1 <= limit <= SCALE_TARGET:
        raise ValueError(f"limit must be between 1 and {SCALE_TARGET}")
    catalogue: list[dict[str, Any]] = []
    for group in range(10):
        for archetype_index, archetype in enumerate(ARCHETYPES):
            layout_index = (archetype_index + group) % len(LAYOUTS)
            layout = LAYOUTS[layout_index]
            name_index = (layout_index + 2 * group) % len(LAYOUTS)
            for profile in CATEGORY_PROFILES:
                name = (
                    f"{profile.stems[archetype_index]} {profile.stems[name_index]} "
                    f"{BRAND_SUFFIXES[profile.slug]}"
                )
                slug = _slug(f"{profile.slug}-{name}-{archetype.slug}")
                catalogue.append(
                    {
                        "slug": slug,
                        "name": name,
                        "summary": (
                            f"{archetype.theme} for a {profile.industry}, with "
                            f"{archetype.service_angle.casefold()}"
                        ),
                        "category_slug": profile.slug,
                        "category_name": profile.name,
                        "category_description": profile.description,
                        "tags": [profile.slug, f"voice-{archetype.slug}", f"layout-{layout.slug}"],
                        "featured_order": 100 + len(catalogue),
                        "document": _document(profile, name, archetype, layout),
                    }
                )
                if len(catalogue) == limit:
                    return catalogue
    return catalogue


def _all_components(document: dict[str, Any]) -> Iterable[dict[str, Any]]:
    def visit(component: dict[str, Any]) -> Iterable[dict[str, Any]]:
        yield component
        for child in component.get("children", []):
            yield from visit(child)

    for page in document["pages"]:
        for component in page["components"]:
            yield from visit(component)


def assess_scale_quality(catalogue: list[dict[str, Any]]) -> ScaleQualityReport:
    errors: list[str] = []
    if not catalogue:
        return ScaleQualityReport(0, 0, 0, 0, (), False, ("catalogue_empty",))
    slugs = [str(item["slug"]) for item in catalogue]
    names = [str(item["name"]) for item in catalogue]
    documents = [item["document"] for item in catalogue]
    checksums = [document_checksum(document) for document in documents]
    categories = {str(item["category_slug"]) for item in catalogue}
    archetypes = {
        tag for item in catalogue for tag in item["tags"] if str(tag).startswith("voice-")
    }
    layouts = {tag for item in catalogue for tag in item["tags"] if str(tag).startswith("layout-")}
    page_counts = tuple(sorted({len(document["pages"]) for document in documents}))
    minimum_layouts = min(len(LAYOUTS), max(1, len(catalogue) // len(CATEGORY_PROFILES)))
    minimum_archetypes = min(len(ARCHETYPES), max(1, len(catalogue) // len(CATEGORY_PROFILES)))
    if len(set(slugs)) != len(slugs):
        errors.append("duplicate_slug")
    if len(set(names)) != len(names):
        errors.append("duplicate_name")
    if len(set(checksums)) != len(checksums):
        errors.append("duplicate_document")
    if len(categories) != min(len(CATEGORY_PROFILES), len(catalogue)):
        errors.append("insufficient_category_coverage")
    if len(archetypes) < minimum_archetypes:
        errors.append("insufficient_content_archetypes")
    if len(layouts) < minimum_layouts:
        errors.append("insufficient_layout_variation")
    if len(page_counts) < (2 if len(catalogue) >= 50 else 1):
        errors.append("insufficient_site_map_variation")
    for document in documents:
        validation = validate_document(document)
        if not validation.valid:
            errors.append("invalid_document")
            break
        content = json.dumps(document, sort_keys=True).casefold()
        if any(
            token in content
            for token in ("testimonial", "a happy customer", "<script", "javascript:")
        ):
            errors.append("unsubstantiated_or_unsafe_content")
            break
    return ScaleQualityReport(
        count=len(catalogue),
        categories=len(categories),
        archetypes=len(archetypes),
        layouts=len(layouts),
        page_counts=page_counts,
        valid=not errors,
        errors=tuple(errors),
    )


def assert_scale_quality(catalogue: list[dict[str, Any]]) -> ScaleQualityReport:
    report = assess_scale_quality(catalogue)
    if not report.valid:
        raise ValueError(f"template scale quality gate failed: {', '.join(report.errors)}")
    return report
