"""Source Selection v0: compact JSON response contract, not a source document."""

from typing import Any, TypedDict

from .contracts import ExtractionError, json_bytes, validator, validate_schema

SELECTION_VERSION = "0.1.0"


class SelectedCharacter(TypedDict):
    id: str
    backend_index: int
    text: str
    bbox: list[float]


class SelectionResult(TypedDict):
    selection_schema_version: str
    pdf_sha256: str
    page_number: int
    coordinate_system: str
    page_geometry: dict[str, Any]
    source_provenance: dict[str, str]
    query: dict[str, Any]
    characters: list[SelectedCharacter]
    source_text: str
    text_role: str
    text_order: str
    candidate_order: str
    math_transcription: str
    status: dict[str, Any]
    hypotheses: list[dict[str, Any]]


def validate_request(query):
    base = validator("selection-0.1")
    schema = {"$defs": base.schema["$defs"], "$ref": "#/$defs/query"}
    error = next(base.evolve(schema=schema).iter_errors(query), None)
    if error:
        raise ExtractionError("invalid_selection", "Invalid selection request: "+error.message)


def validate_selection(result: SelectionResult, index) -> None:
    """Validate schema and exact source/evidence content against a validated index."""
    validate_schema(result, "selection-0.1")
    if json_bytes(result) != json_bytes(index.select(result["query"])):
        raise ExtractionError("invalid_selection", "Selection source, geometry or evidence differs")
