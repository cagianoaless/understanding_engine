"""Authored source/Docling-shaped fixtures; no annotations or neural execution."""

from copy import deepcopy
import json

import pytest
from reportlab.pdfgen import canvas

from test_hybrid import node, prediction, source
from understanding_engine.contracts import ExtractionError, json_bytes
from understanding_engine.hybrid import build_hybrid, order_hypothesis, source_text
from understanding_engine.pdf_parser import extract_pdf
from understanding_engine.selection import SelectionIndex
from understanding_engine.selection_contract import validate_selection
from understanding_engine.structure_v2 import reconstruct

FRAME = 'pdfplumber-native-v1'


def index(source, nodes=None):
    h = build_hybrid(source, None if nodes is None else [prediction(source, nodes)])
    return SelectionIndex(h, source, expected_pdf_sha256=source['source_sha256']), h


def candidates(result):
    return [r for h in result['hypotheses'] for r in h['regions']]


def test_explicit_ids_are_exact_original_backend_order(source):
    i, h = index(source, [node(0, box=[0, 60, 190, 150], text='WRONG')])
    refs = [c['id'] for c in source['pages'][0]['characters']][:2]
    r = i.by_character_ids(1, list(reversed(refs)))
    assert r['source_text'] == 'AB' == source_text(h, 1, refs)
    assert [c['id'] for c in r['characters']] == refs
    assert r['characters'][0]['bbox'] == source['pages'][0]['characters'][0]['bbox']
    assert r['text_order'] == 'backend_extraction_order_not_verified_human_reading_order'
    validate_selection(r, i)


def test_rectangle_center_rule_and_positive_area_region_intersection(source):
    i, h = index(source, [node(0, box=[0, 60, 80, 90])])
    char = source['pages'][0]['characters'][0]; x, top, right, bottom = char['bbox']
    cx, cy = (x+right)/2, (top+bottom)/2
    r = i.by_rectangle(1, [cx, cy, cx+1, cy+1], coordinate_system=FRAME)
    assert [c['id'] for c in r['characters']] == [char['id']]
    assert r['characters'][0]['bbox'] == char['bbox']  # Never clipped/reconstructed.
    # A tiny glyph-edge clip does not imply center selection, but still exposes
    # the intersecting structural region for the caller to inspect.
    r = i.by_rectangle(1, [x, top, x+.01, bottom], coordinate_system=FRAME)
    assert not r['characters'] and len(candidates(r)) == 1
    r = i.by_rectangle(1, [80, 60, 90, 90], coordinate_system=FRAME)
    assert not candidates(r)  # Edge contact is not positive-area intersection.


def test_point_discovery_retains_every_overprinted_glyph(tmp_path):
    p = tmp_path/'overprint.pdf'; pdf = canvas.Canvas(str(p), pagesize=(200, 200), invariant=1)
    pdf.drawString(20, 120, 'X'); pdf.drawString(20, 120, 'X'); pdf.save()
    s = extract_pdf(p); i, h = index(s); c = s['pages'][0]['characters'][0]
    r = i.at_point(1, c['bbox'][:2], coordinate_system=FRAME)
    assert len(r['characters']) == 2 and r['source_text'] == 'XX'
    assert r['status']['ambiguous'] and r['text_role'] == 'candidate_units_not_resolved_selection'


def test_point_region_boundary_tie_never_selects_a_winner(source):
    i, h = index(source, [node(0, 'picture', [0, 0, 100, 50]), node(1, 'picture', [100, 0, 200, 50])])
    r = i.at_point(1, [100, 10], coordinate_system=FRAME)
    assert len(candidates(r)) == 2 and not r['characters']
    assert r['status']['ambiguous'] and not r['status']['overlapping_regions']


def test_nested_table_child_and_relevant_group_hierarchy(source):
    rows = [node(0, 'table', [0, 60, 190, 150], collection='tables', children=['#/groups/0'], text=None),
            node(0, 'unspecified', collection='groups', parent='#/tables/0', children=['#/texts/0'], text=None),
            node(0, box=[0, 60, 80, 90], parent='#/groups/0')]
    i, h = index(source, rows)
    r = i.by_character_ids(1, [source['pages'][0]['characters'][0]['id']])
    assert {c['native_item_id'] for c in candidates(r)} == {'#/tables/0', '#/texts/0'}
    assert r['status']['ambiguous'] and r['status']['overlapping_regions']
    hierarchy = {n['native_item_id']: n for n in r['hypotheses'][0]['hierarchy']}
    assert hierarchy['#/texts/0']['native_parent_id'] == '#/groups/0'
    assert hierarchy['#/groups/0']['native_parent_id'] == '#/tables/0'
    assert '#/furniture' not in hierarchy


def test_formula_empty_model_text_and_merged_lines_do_not_erase_glyphs(source):
    i, h = index(source, [node(0, 'formula', [0, 60, 190, 150], text='')])
    hyp = h['hypotheses'][0]; region = hyp['regions'][0]
    r = i.by_region(1, hyp['id'], region['id'])
    assert r['source_text'] == 'ABCD' and len(r['characters']) == 4
    assert len(candidates(r)) == 1 and candidates(r)[0]['label'] == 'formula'
    assert r['math_transcription'] == 'not_performed' and not r['status']['textless_visual']
    native = i.by_region(1, hyp['id'], region['id'], basis='native')
    assert not native['characters'] and not native['status']['textless_visual']
    assert candidates(native)[0]['geometric_character_count'] == 4


def test_raster_object_empty_source_text_is_not_unmatched(source):
    i, h = index(source, [node(0, 'picture', [0, 0, 40, 40], text=None)])
    r = i.at_point(1, [10, 10], coordinate_system=FRAME)
    assert r['source_text'] == '' and r['characters'] == []
    assert r['status']['textless_visual'] and not r['status']['unmatched']


def test_multi_box_cross_column_preserves_unresolved_item_order(source):
    n = node(0, box=[0, 60, 80, 90])
    n['prov'].append({'page_no': 1, 'bbox': dict(l=100, t=110, r=190, b=150, coord_origin='TOPLEFT'), 'charspan': [1, 2]})
    i, h = index(source, [n]); r = i.by_rectangle(1, [0, 60, 190, 150], coordinate_system=FRAME)
    cs = candidates(r)
    assert len(cs) == 2 and cs[0]['native_item_id'] == cs[1]['native_item_id']
    assert cs[0]['native_item_region_ids'] == cs[1]['native_item_region_ids']
    assert all(c['within_item_order'] == 'unresolved' for c in cs)
    assert len(r['hypotheses'][0]['reading_order']['native_item_positions']) == 1
    assert order_hypothesis(h, h['hypotheses'][0]['id'], *[c['region_id'] for c in cs])['direction'] == 'unresolved'


def test_native_structure_membership_and_order_subset(source):
    native = reconstruct(json_bytes(source))
    p = {'provider': 'structure_0_2', 'version': '0.2.0', 'source_pdf_sha256': source['source_sha256'],
         'status': 'available', 'native': {'document': native}, 'provenance': {}, 'error': None}
    h = build_hybrid(source, [p]); i = SelectionIndex(h, source, expected_pdf_sha256=source['source_sha256'])
    hyp = h['hypotheses'][0]
    r = i.by_region(1, hyp['id'], hyp['regions'][0]['id'], basis='native')
    assert r['characters'] and all(m['status'] == 'valid' for c in candidates(r) for m in c['native_membership'])
    both = i.by_character_ids(1, [c['id'] for c in source['pages'][0]['characters']])
    assert both['hypotheses'][0]['reading_order']['direct_native_relations'] == native['pages'][0]['relations']
    assert both['hypotheses'][0]['reading_order']['subset_only'] is True


def test_source_only_and_failed_layout_are_explicit(source):
    i, h = index(source); r = i.by_character_ids(1, [c['id'] for c in source['pages'][0]['characters']])
    assert r['source_text'] == 'ABCD' and r['status']['source_only'] and r['hypotheses'] == []
    p = prediction(source, []); p.update(status='failed', native=None, error='retained failure')
    h = build_hybrid(source, [p]); i = SelectionIndex(h, source, expected_pdf_sha256=source['source_sha256'])
    r = i.at_point(1, [10, 10], coordinate_system=FRAME)
    assert r['status']['source_only'] and r['status']['unmatched']
    assert r['hypotheses'][0]['candidate_status'] == 'failed'


def test_contradictory_claims_stay_visible_without_inventing_source(source):
    n = node(0, 'text', [0, 0, 50, 50]); n['source_character_ids'] = ['foreign:c0']
    i, h = index(source, [n]); r = i.at_point(1, [10, 10], coordinate_system=FRAME)
    assert r['status']['contradictory'] and not r['characters']
    assert candidates(r)[0]['native_membership'][0]['character_id'] == 'foreign:c0'


@pytest.mark.parametrize('fixture', ['unicode.pdf', 'unicode_units.pdf', 'verbatim.pdf', 'whitespace.pdf'])
def test_original_unicode_and_ids_preserved(fixtures, fixture):
    s = extract_pdf(fixtures/fixture); i, h = index(s); refs = [c['id'] for c in s['pages'][0]['characters']]
    r = i.by_character_ids(1, refs)
    assert [c['id'] for c in r['characters']] == refs
    assert r['source_text'] == source_text(h, 1) and r['characters'] == [{k: c[k] for k in ['id', 'backend_index', 'text', 'bbox']} for c in s['pages'][0]['characters']]


@pytest.mark.parametrize('box', [[-1, 0, 10, 10], [0, 0, 201, 10], [10, 10, 1, 1], [0, 0, 0, 1], [0, 0, float('nan'), 1], [0, 0, float('inf'), 1], [False, 0, 10, 10], [1, 2, 3], None])
def test_invalid_rectangle_rejected(source, box):
    i, h = index(source)
    with pytest.raises(ExtractionError): i.by_rectangle(1, box, coordinate_system=FRAME)


@pytest.mark.parametrize('point', [[-1, 0], [201, 0], [float('nan'), 0], [True, 0], [1], None])
def test_invalid_point_rejected(source, point):
    i, h = index(source)
    with pytest.raises(ExtractionError): i.at_point(1, point, coordinate_system=FRAME)


def test_wrong_pages_source_identities_and_region_ids_rejected(source):
    i, h = index(source)
    with pytest.raises(ExtractionError): SelectionIndex(h, source, expected_pdf_sha256='0'*64)
    for page in [0, 2, True, 1.0]:
        with pytest.raises(ExtractionError): i.by_character_ids(page, [])
    for refs in [['foreign:c0'], [source['pages'][0]['characters'][0]['id']]*2, None]:
        with pytest.raises(ExtractionError): i.by_character_ids(1, refs)
    with pytest.raises(ExtractionError): i.by_region(1, 'wrong evidence', 'wrong region')
    with pytest.raises(ExtractionError): i.at_point(1, [10, 10], coordinate_system='screen')
    altered = deepcopy(source); altered['pages'][0]['characters'][0]['text'] = 'bad'
    with pytest.raises(ExtractionError): SelectionIndex(h, altered, expected_pdf_sha256=source['source_sha256'])


def test_strict_spatial_frame_but_ids_remain_available(fixtures):
    s = extract_pdf(fixtures/'rotations.pdf'); i, h = index(s)
    page = next(p for p in s['pages'] if p['geometry']['rotation'] != 0)
    refs = [c['id'] for c in page['characters']]
    assert i.by_character_ids(page['page_number'], refs)['source_text'] == source_text(h, page['page_number'])
    with pytest.raises(ExtractionError): i.at_point(page['page_number'], [1, 1], coordinate_system=FRAME)


def test_read_only_compact_and_deterministic_response(source):
    p = prediction(source, [node(0, box=[0, 60, 190, 150], text='MODEL'*20000)])
    h = build_hybrid(source, [p]); before = json_bytes(h)
    i = SelectionIndex(h, source, expected_pdf_sha256=source['source_sha256'])
    refs = [source['pages'][0]['characters'][0]['id']]
    r = i.by_character_ids(1, refs); payload = json_bytes(r)
    assert len(payload) < 12000 and len(before) > 300000
    assert b'MODELMODEL' not in payload and 'source' not in r and 'prediction' not in payload.decode()
    assert payload == json_bytes(i.by_character_ids(1, refs))
    validate_selection(r, i)
    changed = deepcopy(r); changed['characters'][0]['text'] = 'rewritten'
    with pytest.raises(ExtractionError): validate_selection(changed, i)
    r['characters'][0]['bbox'][0] = -1
    assert payload == json_bytes(i.by_character_ids(1, refs)) and before == json_bytes(h)


def test_conflicting_labels_and_confidences_do_not_rank_a_winner(source):
    a, b = node(0, 'text', [0, 60, 80, 90]), node(1, 'section_header', [0, 60, 80, 90])
    a['confidence'] = .01; b['confidence'] = .99
    i, h = index(source, [a, b])
    c = source['pages'][0]['characters'][0]; x, y, r, bottom = c['bbox']
    result = i.at_point(1, [(x+r)/2, (y+bottom)/2], coordinate_system=FRAME)
    assert [m['label'] for m in candidates(result)] == ['text', 'section_header']
    assert result['status']['ambiguous'] and result['status']['overlapping_regions']


def test_validation_is_once_per_context_not_per_query(source, monkeypatch):
    import understanding_engine.selection as selection
    original = selection.validate_hybrid
    calls = []
    def validate(*args):
        calls.append(1); return original(*args)
    monkeypatch.setattr(selection, 'validate_hybrid', validate)
    i, h = index(source)
    for _ in range(3):
        i.by_character_ids(1, [source['pages'][0]['characters'][0]['id']])
    assert calls == [1]


@pytest.mark.parametrize('fixture', ['image.pdf', 'empty.pdf'])
def test_source_only_textless_pages_do_not_invent_visual_regions(fixtures, fixture):
    s = extract_pdf(fixtures/fixture); i, h = index(s)
    r = i.by_rectangle(1, s['pages'][0]['geometry']['bbox'], coordinate_system=FRAME)
    assert r['characters'] == [] and r['source_text'] == '' and r['hypotheses'] == []
    assert r['status']['unmatched'] and r['status']['source_only']
    assert not r['status']['textless_visual']
