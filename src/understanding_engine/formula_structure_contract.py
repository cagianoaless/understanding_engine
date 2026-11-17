"""Experimental Formula Structure 0.1: syntax hypotheses, never PDF truth."""
from typing import Any, TypedDict

from .contracts import ExtractionError, check_box, json_bytes, validate_schema, validator

FORMULA_STRUCTURE_VERSION = "0.1.0"
PARSER_VERSION = "latex-subset-v0.1.0"


class FormulaProvenance(TypedDict):
    pdf_sha256: str
    page_number: int
    bbox: list[float]
    coordinate_system: str
    crop_sha256: str
    model_name: str
    model_revision: str
    prediction_id: str
    prediction_record_sha256: str
    prediction_artifact_sha256: str


class FormulaNode(TypedDict):
    id: str
    type: str
    token_span: list[int]
    character_span: list[int]
    token_span_complete: bool
    source_text: str
    children: list[dict[str, str]]
    status: str
    attributes: dict[str, Any]
    diagnostics: list[dict[str, Any]]


class FormulaStructure(TypedDict):
    formula_structure_version: str
    id: str
    parser: dict[str, Any]
    provenance: FormulaProvenance
    input: dict[str, Any]
    evidence_status: dict[str, str]
    tokens: list[dict[str, Any]]
    nodes: list[FormulaNode]
    root_id: str
    status: dict[str, str]
    diagnostics: list[dict[str, Any]]


def validate_provenance(provenance: FormulaProvenance) -> None:
    base = validator("formula-structure-0.1")
    schema = {"$defs": base.schema["$defs"], "$ref": "#/$defs/provenance"}
    error = next(base.evolve(schema=schema).iter_errors(provenance), None)
    if error:
        raise ExtractionError("invalid_formula_provenance", error.message)
    check_box(provenance["bbox"], "formula region")
    if provenance["bbox"][0] >= provenance["bbox"][2] or provenance["bbox"][1] >= provenance["bbox"][3]:
        raise ExtractionError("invalid_formula_provenance", "Formula crop must have positive area")


def validate_formula_structure(result: FormulaStructure) -> None:
    """Rebuild against stored exact input; does not verify a PDF/model claim.

    Independently checked artifact/crop identity must be supplied by the caller.
    A consistent self-contained result is not proof that its provenance is true.
    """
    from .formula_structure import ParseSettings, parse_formula

    validate_schema(result, "formula-structure-0.1")
    expected = parse_formula(result["input"]["latex"], result["provenance"],
                             raw_model_output=result["input"]["raw_model_output"],
                             termination=result["input"]["termination"],
                             settings=ParseSettings(**result["parser"]["settings"]))
    if json_bytes(result) != json_bytes(expected):
        raise ExtractionError("invalid_formula_structure", "Input spans, graph, identity or parsing claims differ")
