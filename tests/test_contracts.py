import copy

import pytest

from understanding_engine.contracts import ExtractionError, validate_extraction, validator
from understanding_engine.pdf_parser import extract_pdf


@pytest.mark.parametrize("name", ["extraction", "run"])
def test_schemas_are_valid(name):
    assert validator(name)


@pytest.mark.parametrize("bbox", [[3, 0, 2, 1], [0, 3, 1, 2], [0, 0, float('nan'), 1],
                                  [0, 0, float('inf'), 1]])
def test_malformed_geometry_rejected(fixtures, bbox):
    data = extract_pdf(fixtures / "single.pdf")
    data["pages"][0]["characters"][0]["bbox"] = bbox
    with pytest.raises(ExtractionError) as caught:
        validate_extraction(data)
    assert caught.value.code == "malformed_geometry"


@pytest.mark.parametrize("mutation", ["id", "reference", "page_count", "page_number", "text", "status", "extra"])
def test_contract_invariants(fixtures, mutation):
    data = copy.deepcopy(extract_pdf(fixtures / "single.pdf"))
    page = data["pages"][0]
    if mutation == "id":
        page["characters"][0]["id"] = page["characters"][1]["id"]
    elif mutation == "reference":
        page["derived"]["lines"][0]["source_character_ids"] = ["unknown"]
    elif mutation == "page_count":
        data["page_count"] = 3
    elif mutation == "page_number":
        page["page_number"] = 2
    elif mutation == "text":
        page["derived"]["text"] = "different"
    elif mutation == "status":
        data["status"] = "textless"
    else:
        data["unexpected"] = True
    with pytest.raises(ExtractionError) as caught:
        validate_extraction(data)
    assert caught.value.code == "invalid_contract"
