"""Reusable, deterministic visual families for the curated Template catalogue."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateFamily:
    """A structural visual system shared by a bounded set of industry Templates."""

    slug: str
    name: str
    layout_slug: str
    sequence: tuple[str, ...]
    palette: tuple[str, str]
    surface: str
    ink: str
    heading_font: str
    hero_align: str
    grid_columns: int
    section_tone: str
    secondary_cta: bool
    media_mode: str


@dataclass(frozen=True)
class _LayoutSeed:
    slug: str
    name: str
    sequence: tuple[str, ...]
    palette: tuple[str, str]
    heading_font: str


@dataclass(frozen=True)
class _Treatment:
    slug: str
    name: str
    surface: str
    ink: str
    hero_align: str
    grid_columns: int
    section_tone: str
    secondary_cta: bool
    media_mode: str


_LAYOUT_SEEDS = (
    _LayoutSeed("split-hero", "Split Hero", ("services", "faq"), ("#164E46", "#E37A5F"), "MANROPE"),
    _LayoutSeed(
        "editorial-grid",
        "Editorial Grid",
        ("editorial", "services", "faq"),
        ("#203D63", "#D68B49"),
        "DM_SERIF",
    ),
    _LayoutSeed(
        "service-stack",
        "Service Stack",
        ("services", "story", "faq"),
        ("#2C342F", "#C46A42"),
        "MANROPE",
    ),
    _LayoutSeed(
        "faq-first",
        "Question Led",
        ("faq", "services", "story"),
        ("#5E3B26", "#E3A13B"),
        "PLAYFAIR",
    ),
    _LayoutSeed(
        "method-grid",
        "Method Grid",
        ("editorial", "story", "services"),
        ("#4D3C64", "#D6A7D8"),
        "DM_SERIF",
    ),
    _LayoutSeed(
        "outcome-led",
        "Outcome Led",
        ("services", "faq", "editorial"),
        ("#174C5A", "#9ED5CC"),
        "MANROPE",
    ),
    _LayoutSeed(
        "story-led", "Story Led", ("story", "services", "faq"), ("#6B2E24", "#EAB37A"), "PLAYFAIR"
    ),
    _LayoutSeed(
        "compact-grid", "Compact Grid", ("editorial", "faq"), ("#314C3A", "#B5CD83"), "INTER"
    ),
    _LayoutSeed(
        "guided-steps",
        "Guided Steps",
        ("story", "faq", "services"),
        ("#3E435F", "#AFC2FF"),
        "DM_SERIF",
    ),
    _LayoutSeed(
        "calm-conversion",
        "Calm Conversion",
        ("services", "editorial", "story", "faq"),
        ("#34414B", "#F0B38B"),
        "MANROPE",
    ),
)

_TREATMENTS = (
    _Treatment("studio", "Studio", "#FFFDF8", "#17211D", "left", 3, "studio", False, "split"),
    _Treatment("journal", "Journal", "#F3EFE7", "#241D19", "center", 2, "journal", True, "gallery"),
    _Treatment("signal", "Signal", "#F3F6FA", "#13233A", "left", 4, "signal", True, "band"),
    _Treatment(
        "atelier", "Atelier", "#F4F0EA", "#29251F", "center", 3, "atelier", False, "portrait"
    ),
    _Treatment("compact", "Compact", "#F7F8F4", "#1D2722", "left", 2, "compact", True, "minimal"),
)


TEMPLATE_FAMILIES = tuple(
    TemplateFamily(
        slug=f"{layout.slug}-{treatment.slug}",
        name=f"{layout.name} / {treatment.name}",
        layout_slug=layout.slug,
        sequence=layout.sequence,
        palette=layout.palette,
        surface=treatment.surface,
        ink=treatment.ink,
        heading_font=layout.heading_font,
        hero_align=treatment.hero_align,
        grid_columns=treatment.grid_columns,
        section_tone=treatment.section_tone,
        secondary_cta=treatment.secondary_cta,
        media_mode=treatment.media_mode,
    )
    for treatment in _TREATMENTS
    for layout in _LAYOUT_SEEDS
)

assert 40 <= len(TEMPLATE_FAMILIES) <= 60
