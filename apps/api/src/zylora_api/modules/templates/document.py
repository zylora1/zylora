from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"
REGISTRY_VERSION = "1.0.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Metadata(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(min_length=1, max_length=500)]
    language: Annotated[str, Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")] = "en"


class Theme(StrictModel):
    primary: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    accent: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    surface: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    ink: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    heading_font: Literal["INTER", "MANROPE", "PLAYFAIR", "DM_SERIF"] = "MANROPE"
    body_font: Literal["INTER", "MANROPE", "SOURCE_SANS"] = "INTER"


class AssetReference(StrictModel):
    id: Annotated[str, Field(pattern=r"^[0-9a-fA-F-]{36}$")]
    alt: Annotated[str, Field(min_length=1, max_length=240)]


class Link(StrictModel):
    kind: Literal["PAGE", "SECTION", "EXTERNAL", "EMAIL", "PHONE"]
    target: Annotated[str, Field(min_length=1, max_length=500)]


class Interaction(StrictModel):
    trigger: Literal["CLICK", "SUBMIT"]
    action: Literal["NAVIGATE", "SCROLL", "OPEN_MODAL", "SUBMIT_LEAD"]
    target: Annotated[str | None, Field(max_length=160)] = None


class Component(StrictModel):
    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")]
    type: Annotated[str, Field(min_length=1, max_length=40)]
    props: dict[str, Any] = Field(default_factory=dict)
    children: Annotated[list[Component], Field(max_length=40)] = Field(default_factory=list)
    responsive: dict[Literal["tablet", "desktop"], dict[str, Any]] = Field(default_factory=dict)
    interactions: Annotated[list[Interaction], Field(max_length=4)] = Field(default_factory=list)


class Seo(StrictModel):
    title: Annotated[str, Field(min_length=1, max_length=60)]
    description: Annotated[str, Field(min_length=1, max_length=160)]


class Page(StrictModel):
    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")]
    slug: Annotated[str, Field(pattern=r"^(home|[a-z0-9]+(?:-[a-z0-9]+)*)$")]
    label: Annotated[str, Field(min_length=1, max_length=80)]
    parent_page_id: Annotated[str | None, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")] = None
    sort_order: Annotated[int, Field(ge=0, le=10000)] = 0
    is_home: bool = False
    show_in_navigation: bool = True
    status: Literal["ACTIVE", "HIDDEN"] = "ACTIVE"
    seo: Seo
    components: Annotated[list[Component], Field(min_length=1, max_length=80)]


class TemplateDocument(StrictModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    registry_version: Literal["1.0.0"] = "1.0.0"
    metadata: Metadata
    theme: Theme
    assets: Annotated[list[AssetReference], Field(max_length=100)] = Field(default_factory=list)
    pages: Annotated[list[Page], Field(min_length=1, max_length=200)]
    features: Annotated[list[str], Field(max_length=30)] = Field(default_factory=list)
    requirements: Annotated[list[str], Field(max_length=30)] = Field(default_factory=list)
    provenance: Literal["CURATED", "LICENSED", "CUSTOM"]

    @model_validator(mode="after")
    def unique_pages(self) -> TemplateDocument:
        page_ids = {page.id for page in self.pages}
        if len(page_ids) != len(self.pages):
            raise ValueError("page IDs must be unique")
        homes = [page for page in self.pages if page.is_home]
        if len(homes) != 1 or homes[0].slug != "home" or homes[0].parent_page_id is not None:
            raise ValueError("exactly one root home page is required")
        home_id = homes[0].id
        if any(page.parent_page_id == home_id for page in self.pages):
            raise ValueError("the home page cannot be a hierarchy parent")
        sibling_keys = {(page.parent_page_id, page.slug) for page in self.pages}
        if len(sibling_keys) != len(self.pages):
            raise ValueError("sibling page slugs must be unique")
        by_id = {page.id: page for page in self.pages}
        for page in self.pages:
            if page.parent_page_id is not None and page.parent_page_id not in page_ids:
                raise ValueError("page parent must exist in the same Template")
            current = page
            seen: set[str] = set()
            while current.parent_page_id is not None:
                if current.id in seen or len(seen) >= 12:
                    raise ValueError("page hierarchy is cyclic or too deep")
                seen.add(current.id)
                current = by_id[current.parent_page_id]
        return self


class RegistryEntry(StrictModel):
    allowed_props: frozenset[str]
    required_props: frozenset[str] = frozenset()
    min_children: int = 0
    max_children: int = 0
    required_feature: str | None = None


COMPONENT_REGISTRY: dict[str, RegistryEntry] = {
    "NAVIGATION": RegistryEntry(
        allowed_props=frozenset({"brand", "links"}), required_props=frozenset({"brand", "links"})
    ),
    "HERO": RegistryEntry(
        allowed_props=frozenset(
            {"eyebrow", "heading", "body", "primaryCta", "secondaryCta", "align", "treatment"}
        ),
        required_props=frozenset({"heading", "body"}),
    ),
    "SECTION": RegistryEntry(
        allowed_props=frozenset({"eyebrow", "heading", "body", "tone"}), max_children=20
    ),
    "HEADING": RegistryEntry(
        allowed_props=frozenset({"text", "level"}), required_props=frozenset({"text", "level"})
    ),
    "RICH_TEXT": RegistryEntry(
        allowed_props=frozenset({"text"}), required_props=frozenset({"text"})
    ),
    "MEDIA": RegistryEntry(
        allowed_props=frozenset({"mode", "heading", "body"}),
        required_props=frozenset({"mode", "heading"}),
    ),
    "IMAGE": RegistryEntry(
        allowed_props=frozenset({"assetId", "caption", "fit"}),
        required_props=frozenset({"assetId"}),
    ),
    "BUTTONS": RegistryEntry(
        allowed_props=frozenset({"items"}), required_props=frozenset({"items"})
    ),
    "GRID": RegistryEntry(
        allowed_props=frozenset({"columns", "gap"}), min_children=1, max_children=12
    ),
    "CARD": RegistryEntry(
        allowed_props=frozenset({"eyebrow", "heading", "body", "link"}),
        required_props=frozenset({"heading", "body"}),
        max_children=2,
    ),
    "SERVICES": RegistryEntry(
        allowed_props=frozenset({"heading", "items"}),
        required_props=frozenset({"heading", "items"}),
    ),
    "TESTIMONIALS": RegistryEntry(
        allowed_props=frozenset({"heading", "items"}), required_props=frozenset({"items"})
    ),
    "GALLERY": RegistryEntry(
        allowed_props=frozenset({"heading", "assetIds", "columns"}),
        required_props=frozenset({"assetIds"}),
    ),
    "LEAD_FORM": RegistryEntry(
        allowed_props=frozenset({"heading", "body", "fields", "consentText", "submitLabel"}),
        required_props=frozenset({"fields", "consentText", "submitLabel"}),
        required_feature="LEAD_CAPTURE",
    ),
    "FAQ": RegistryEntry(
        allowed_props=frozenset({"heading", "items"}), required_props=frozenset({"items"})
    ),
    "CONTACT": RegistryEntry(allowed_props=frozenset({"heading", "email", "phone", "address"})),
    "SOCIAL_LINKS": RegistryEntry(
        allowed_props=frozenset({"links"}), required_props=frozenset({"links"})
    ),
    "FOOTER": RegistryEntry(allowed_props=frozenset({"brand", "body", "links"})),
    "CHATBOT_MOUNT": RegistryEntry(
        allowed_props=frozenset({"label", "position"}), required_feature="CHATBOT"
    ),
}
