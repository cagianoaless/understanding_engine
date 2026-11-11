"""Hybrid Interface v0: JSON-compatible Python contracts and source-aware checks."""

from typing import Any, Literal, TypedDict

from .contracts import ExtractionError, json_bytes, validate_schema

HYBRID_VERSION = "0.1.0"


class LayoutPrediction(TypedDict):
    provider: Literal["docling", "structure_0_2"]
    version: str
    source_pdf_sha256: str
    status: Literal["available", "failed"]
    native: dict[str, Any] | None
    provenance: dict[str, Any]
    error: str | None


class NativeMembership(TypedDict):
    character_id: str
    status: Literal["valid", "contradictory"]
    reason: str | None


class HybridRegion(TypedDict):
    id: str
    native_item_id: str
    native_provenance_index: int
    page_number: int
    native_bbox: dict[str, Any]
    bbox: list[float]
    geometric_character_ids: list[str]
    native_membership: list[NativeMembership]
    status: Literal["unambiguous", "ambiguous", "unmatched", "zero_character_visual", "contradictory"]


class CharacterAssociation(TypedDict):
    character_id: str
    geometric_region_ids: list[str]
    native_region_ids: list[str]
    contradictory_region_ids: list[str]
    geometric_status: Literal["unambiguous", "ambiguous", "unmatched"]


class HybridItem(TypedDict):
    native_id: str
    native_pointer: str
    label: str
    parent_id: str | None
    children_ids: list[str]
    diagnostic_model_text: str | None
    confidence: dict[str, Any] | None
    region_ids: list[str]
    geometry_status: Literal["present", "unavailable"]


class StructuralEvidence(TypedDict):
    id: str
    prediction: LayoutPrediction
    status: Literal["available", "failed", "rejected"]
    issues: list[dict[str, str]]
    page_numbers: list[int]
    items: list[HybridItem]
    regions: list[HybridRegion]
    associations: list[dict[str, Any]]
    overlaps: list[dict[str, Any]]
    reading_order: dict[str, Any]


class HybridDocument(TypedDict):
    hybrid_schema_version: Literal["0.1.0"]
    coordinate_system: Literal["pdfplumber-native-v1"]
    source: dict[str, Any]
    source_canonical_sha256: str
    association_policy: Literal["inclusive_original_character_center_v0"]
    hypotheses: list[StructuralEvidence]
    source_only_pages: list[int]


def validate_hybrid(document: HybridDocument, source_document: dict) -> None:
    """Validate against the independent original extraction, not model text.

    Schema alone cannot establish conservation or the correctness of derived
    links. Rebuild those deterministic links and compare the entire result.
    The PDF itself must already have been verified by the extraction caller.
    """
    from .hybrid import build_hybrid

    validate_schema(document, "hybrid-0.1")
    expected = build_hybrid(source_document, [h["prediction"] for h in document["hypotheses"]])
    if json_bytes(document) != json_bytes(expected):
        raise ExtractionError("invalid_hybrid", "Source conservation, evidence or derived associations differ")
