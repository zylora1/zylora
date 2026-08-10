# ruff: noqa: E501
from __future__ import annotations

from typing import Any


def curated_document(
    *, name: str, description: str, primary: str, accent: str, industry: str, voice: str
) -> dict[str, Any]:
    """Return the compact, text-first foundation shared by vetted legacy templates."""
    return {
        "schema_version": "1.0.0",
        "registry_version": "1.0.0",
        "metadata": {"name": name, "description": description, "language": "en"},
        "theme": {
            "primary": primary,
            "accent": accent,
            "surface": "#FFFDF8",
            "ink": "#17211D",
            "heading_font": "MANROPE",
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
                "seo": {"title": f"{name} - {industry.title()}", "description": description[:160]},
                "components": [
                    {
                        "id": "main-navigation",
                        "type": "NAVIGATION",
                        "props": {
                            "brand": name,
                            "links": [
                                {
                                    "label": "Services",
                                    "link": {"kind": "SECTION", "target": "services"},
                                },
                                {
                                    "label": "Contact",
                                    "link": {"kind": "SECTION", "target": "contact"},
                                },
                            ],
                        },
                        "children": [],
                        "responsive": {},
                        "interactions": [],
                    },
                    {
                        "id": "opening-hero",
                        "type": "HERO",
                        "props": {
                            "eyebrow": industry.upper(),
                            "heading": voice,
                            "body": description,
                            "primaryCta": {
                                "label": "Start a conversation",
                                "link": {"kind": "SECTION", "target": "contact"},
                            },
                            "align": "left",
                        },
                        "children": [],
                        "responsive": {"desktop": {"spacing": "generous"}},
                        "interactions": [
                            {"trigger": "CLICK", "action": "SCROLL", "target": "contact"}
                        ],
                    },
                    {
                        "id": "services",
                        "type": "SERVICES",
                        "props": {
                            "heading": "Built around what matters",
                            "items": [
                                {
                                    "heading": "Clear expertise",
                                    "body": "Explain value in language visitors understand.",
                                },
                                {
                                    "heading": "Considered details",
                                    "body": "A structured system that adapts across screens.",
                                },
                                {
                                    "heading": "Direct next step",
                                    "body": "Guide visitors toward a useful conversation.",
                                },
                            ],
                        },
                        "children": [],
                        "responsive": {},
                        "interactions": [],
                    },
                    {
                        "id": "questions",
                        "type": "FAQ",
                        "props": {
                            "heading": "Good questions, answered",
                            "items": [
                                {
                                    "question": "How do we begin?",
                                    "answer": "Send a short note and choose the clearest next step.",
                                },
                                {
                                    "question": "Can this grow with us?",
                                    "answer": "Add structured content without losing coherence.",
                                },
                            ],
                        },
                        "children": [],
                        "responsive": {},
                        "interactions": [],
                    },
                    {
                        "id": "contact",
                        "type": "LEAD_FORM",
                        "props": {
                            "heading": "Make something useful",
                            "body": "Tell us what you are working toward.",
                            "fields": [
                                {"name": "name", "label": "Name", "type": "text"},
                                {"name": "email", "label": "Email", "type": "email"},
                                {"name": "message", "label": "Message", "type": "text"},
                            ],
                            "consentText": "I agree that this business may respond to my enquiry.",
                            "submitLabel": "Send enquiry",
                        },
                        "children": [],
                        "responsive": {},
                        "interactions": [{"trigger": "SUBMIT", "action": "SUBMIT_LEAD"}],
                    },
                    {
                        "id": "site-footer",
                        "type": "FOOTER",
                        "props": {
                            "brand": name,
                            "body": "Independent work, presented with care.",
                            "links": [],
                        },
                        "children": [],
                        "responsive": {},
                        "interactions": [],
                    },
                ],
            }
        ],
        "features": ["LEAD_CAPTURE", "RESPONSIVE_PREVIEW"],
        "requirements": ["LEAD_CAPTURE"],
        "provenance": "CURATED",
    }


INITIAL_CATALOG: list[dict[str, Any]] = [
    {
        "slug": "haven-health",
        "name": "Haven Health",
        "summary": "A calm, trust-first clinic presence with clear services and an accessible enquiry path.",
        "category_slug": "health-wellness",
        "category_name": "Health & Wellness",
        "category_description": "Professional sites for care, wellbeing, and trusted local services.",
        "tags": ["calm", "clinic", "lead-ready"],
        "featured_order": 10,
        "document": curated_document(
            name="Haven Health",
            description="Care that starts by listening, with a reassuring path from first question to appointment.",
            primary="#164E46",
            accent="#E37A5F",
            industry="Community clinic",
            voice="Thoughtful care, close to home",
        ),
    },
    {
        "slug": "atelier-north",
        "name": "Atelier North",
        "summary": "An editorial portfolio for architecture and design studios where restraint lets the work lead.",
        "category_slug": "creative-studios",
        "category_name": "Creative Studios",
        "category_description": "Editorial portfolios for architecture, design, and independent practices.",
        "tags": ["architectural", "editorial", "minimal"],
        "featured_order": 20,
        "document": curated_document(
            name="Atelier North",
            description="Architecture shaped by place, material, and the everyday rituals of the people within it.",
            primary="#2C342F",
            accent="#C46A42",
            industry="Architecture studio",
            voice="Spaces with a sense of belonging",
        ),
    },
    {
        "slug": "saffron-table",
        "name": "Saffron Table",
        "summary": "A warm restaurant story balancing atmosphere, seasonal cooking, and direct reservations enquiries.",
        "category_slug": "food-hospitality",
        "category_name": "Food & Hospitality",
        "category_description": "Inviting digital homes for restaurants, cafes, and hospitality businesses.",
        "tags": ["restaurant", "warm", "seasonal"],
        "featured_order": 30,
        "document": curated_document(
            name="Saffron Table",
            description="Season-led plates, generous hospitality, and a neighbourhood table made for lingering.",
            primary="#6B2E24",
            accent="#E3A13B",
            industry="Neighbourhood restaurant",
            voice="A table worth gathering around",
        ),
    },
]

# Import after the shared document factory and initial set to avoid a circular module dependency.
from zylora_api.modules.templates.scaling import build_scaled_catalogue  # noqa: E402

CURATED_CATALOG: list[dict[str, Any]] = [*INITIAL_CATALOG, *build_scaled_catalogue()]
