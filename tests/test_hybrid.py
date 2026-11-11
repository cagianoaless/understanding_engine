"""Authored offline inputs; no real-paper reference labels or model execution."""

from copy import deepcopy
import json

import pytest
from reportlab.pdfgen import canvas

from understanding_engine.contracts import ExtractionError, json_bytes
from understanding_engine.hybrid import build_hybrid, order_hypothesis, source_text
from understanding_engine.hybrid_contract import validate_hybrid
from understanding_engine.pdf_parser import extract_pdf
from understanding_engine.structure_v2 import reconstruct


@pytest.fixture
def source(tmp_path):
    path = tmp_path/'authored.pdf'
    pdf = canvas.Canvas(str(path), pagesize=(200, 200), invariant=1)
    pdf.setFont('Helvetica', 10)
    pdf.drawString(20, 120, 'AB')
    pdf.drawString(120, 70, 'CD')
    pdf.save()
    return extract_pdf(path)


def node(index, label='text', box=None, *, collection='texts', parent='#/body', children=None, text='MODEL'):
    return {'self_ref': f'#/{collection}/{index}', 'label': label, 'parent': {'$ref': parent},
            'children': [{'$ref': ref} for ref in children or []], 'text': text,
            'prov': [] if box is None else [{'page_no': 1, 'bbox': dict(zip(['l', 't', 'r', 'b'], box), coord_origin='TOPLEFT'), 'charspan': [0, 0]}]}


def prediction(source, nodes):
    native = {'body': {'self_ref': '#/body', 'label': 'unspecified',
                      'children': [{'$ref': n['self_ref']} for n in nodes if n['parent']['$ref'] == '#/body']},
              'furniture': {'self_ref': '#/furniture', 'label': 'unspecified', 'children': []},
              'pages': {'1': {'page_no': 1, 'size': {k: source['pages'][0]['geometry'][k] for k in ['width', 'height']}}}}
    for n in nodes:
        key = n['self_ref'].split('/')[1]
        native.setdefault(key, []).append(n)
    by_id = {n['self_ref']: n for n in nodes}
    traversal = []

    def visit(ref):
        n = by_id[ref]
        if not ref.startswith('#/groups/'):
            traversal.append(dict(order_index=len(traversal), self_ref=ref, label=n['label'],
                                  text=n.get('text'), provenance=n['prov']))
        for c in n['children']:
            visit(c['$ref'])
    for c in native['body']['children']:
        visit(c['$ref'])
    return {'provider': 'docling', 'version': '2.148.0', 'source_pdf_sha256': source['source_sha256'],
            'status': 'available', 'native': {'document': native, 'items': traversal},
            'provenance': {'identity_basis': 'authored synthetic fixture, not model inference'}, 'error': None}


def available(result):
    h = result['hypotheses'][0]
    assert h['status'] == 'available', h['issues']
    return h


def test_paragraph_source_conservation_and_no_model_replacement(source):
    p = prediction(source, [node(0, box=[0, 60, 200, 150], text='rewritten ß = 42')])
    original, native = deepcopy(source), deepcopy(p)
    result = build_hybrid(source, [p]); h = available(result)
    assert source == original and p == native and result['source'] == original
    assert source_text(result, 1) == 'ABCD'
    assert h['items'][2]['diagnostic_model_text'] == 'rewritten ß = 42'
    assert h['regions'][0]['geometric_character_ids'] == [c['id'] for c in source['pages'][0]['characters']]
    assert all(c['geometric_status'] == 'unambiguous' and not c['native_region_ids'] for c in h['associations'][0]['characters'])
    validate_hybrid(result, original)
    assert json_bytes(result) == json_bytes(build_hybrid(source, [p]))
    validate_hybrid(json.loads(json_bytes(result)), source)


def test_heading_and_text_keep_native_order_not_source_sorting(source):
    p = prediction(source, [node(0, 'section_header', [0, 60, 80, 90]), node(1, box=[100, 110, 190, 145])])
    result = build_hybrid(source, [p]); h = available(result); a, b = h['regions']
    assert [i['label'] for i in h['items'][-2:]] == ['section_header', 'text']
    assert order_hypothesis(result, h['id'], a['id'], b['id'])['direction'] == 'before'
    assert h['items'][-2]['confidence'] is None


def test_nested_table_group_and_text_children_remain_ambiguous(source):
    rows = [node(0, 'table', [0, 60, 190, 150], collection='tables', children=['#/groups/0'], text=None),
            node(0, 'unspecified', collection='groups', parent='#/tables/0', children=['#/texts/0'], text=None),
            node(0, box=[10, 65, 70, 90], parent='#/groups/0')]
    h = available(build_hybrid(source, [prediction(source, rows)]))
    by_id = {i['native_id']: i for i in h['items']}
    assert by_id['#/texts/0']['parent_id'] == '#/groups/0'
    assert by_id['#/groups/0']['parent_id'] == '#/tables/0'
    assert by_id['#/groups/0']['geometry_status'] == 'unavailable'
    assert len(h['regions']) == 2 and len(h['overlaps']) == 1
    a = h['associations'][0]['characters'][0]
    assert a['geometric_status'] == 'ambiguous' and len(a['geometric_region_ids']) == 2


def test_multi_box_two_columns_never_forces_within_item_order(source):
    n = node(0, box=[0, 60, 80, 90])
    n['prov'].append({'page_no': 1, 'bbox': dict(l=100, t=110, r=190, b=145, coord_origin='TOPLEFT'), 'charspan': [1, 2]})
    result = build_hybrid(source, [prediction(source, [n])]); h = available(result)
    assert len(h['items'][-1]['region_ids']) == 2
    assert order_hypothesis(result, h['id'], *[r['id'] for r in h['regions']])['direction'] == 'unresolved'
    assert h['regions'][0]['native_provenance_index'] == 0 and h['regions'][1]['native_provenance_index'] == 1


def test_merged_equations_and_empty_model_formula_still_resolve_source_glyphs(source):
    n = node(0, 'formula', [0, 60, 190, 150], text='')
    result = build_hybrid(source, [prediction(source, [n])]); h = available(result)
    assert len(h['regions']) == 1 and h['items'][-1]['diagnostic_model_text'] == ''
    assert source_text(result, 1, h['regions'][0]['geometric_character_ids']) == 'ABCD'
    assert h['regions'][0]['status'] == 'unambiguous'  # No inferred equation splitting.


@pytest.mark.parametrize('label,status', [('picture', 'zero_character_visual'), ('table', 'zero_character_visual'), ('text', 'unmatched')])
def test_zero_character_visual_distinct_from_unmatched_text(source, label, status):
    h = available(build_hybrid(source, [prediction(source, [node(0, label, [0, 0, 30, 30])])]))
    assert h['regions'][0]['status'] == status and h['regions'][0]['geometric_character_ids'] == []
    assert all(c['geometric_status'] == 'unmatched' for c in h['associations'][0]['characters'])


def test_conflicting_overlap_has_no_geometry_inferred_hierarchy(source):
    rows = [node(0, 'text', [0, 60, 190, 150]), node(1, 'section_header', [10, 65, 180, 145])]
    h = available(build_hybrid(source, [prediction(source, rows)]))
    assert len(h['overlaps']) == 1
    assert h['items'][-1]['parent_id'] == '#/body'
    assert all(c['geometric_status'] == 'ambiguous' for c in h['associations'][0]['characters'])


def test_false_docling_character_claims_are_contradictory_not_native_membership(source):
    n = node(0, box=[0, 60, 190, 150]); ref = source['pages'][0]['characters'][0]['id']
    n['source_character_ids'] = [ref, 'foreign:c0']
    h = available(build_hybrid(source, [prediction(source, [n])]))
    assert h['regions'][0]['status'] == 'contradictory'
    assert all(c['status'] == 'contradictory' for c in h['regions'][0]['native_membership'])
    assert h['associations'][0]['characters'][0]['contradictory_region_ids']
    assert not any(c['native_region_ids'] for c in h['associations'][0]['characters'])


def test_source_claim_without_geometry_is_rejected_instead_of_hidden(source):
    n = node(0); n['source_character_ids'] = [source['pages'][0]['characters'][0]['id']]
    result = build_hybrid(source, [prediction(source, [n])])
    assert result['hypotheses'][0]['status'] == 'rejected'
    assert 'source claims' in result['hypotheses'][0]['issues'][0]['detail']
    assert result['source'] == source


def test_missing_failed_and_rejected_layout_keep_complete_source(source):
    result = build_hybrid(source)
    assert result['source_only_pages'] == [1] and result['hypotheses'] == []
    p = prediction(source, [])
    p.update(status='failed', native=None, error='previous candidate timeout')
    failed = build_hybrid(source, [p]); assert failed['hypotheses'][0]['status'] == 'failed'
    p['source_pdf_sha256'] = '0'*64
    rejected = build_hybrid(source, [p]); assert rejected['hypotheses'][0]['status'] == 'rejected'
    for d in [result, failed, rejected]:
        assert d['source'] == source and source_text(d, 1) == 'ABCD'
        validate_hybrid(d, source)


@pytest.mark.parametrize('damage', ['crop', 'rotation', 'unit', 'size', 'origin', 'bounds', 'foreign_page', 'cycle', 'parent', 'traversal', 'native_shape'])
def test_bad_coordinate_or_reference_assumptions_reject_evidence(source, damage):
    original = deepcopy(source)
    p = prediction(source, [node(0, box=[0, 60, 190, 150])]); d = p['native']['document']
    if damage == 'crop': source['pages'][0]['geometry']['cropbox'] = [1, 0, 200, 200]
    elif damage == 'rotation': source['pages'][0]['geometry'].update(rotation=90, raw_rotation=90)
    elif damage == 'unit': source['pages'][0]['geometry']['user_unit'] = 2
    elif damage == 'size': d['pages']['1']['size']['width'] = 201
    elif damage == 'origin': d['texts'][0]['prov'][0]['bbox']['coord_origin'] = 'GUESSED'
    elif damage == 'bounds': d['texts'][0]['prov'][0]['bbox']['r'] = 201
    elif damage == 'foreign_page': d['texts'][0]['prov'][0]['page_no'] = 2
    elif damage == 'cycle':
        d['body']['parent'] = {'$ref': '#/texts/0'}; d['texts'][0]['children'] = [{'$ref': '#/body'}]
    elif damage == 'parent': d['texts'][0]['parent'] = {'$ref': '#/missing'}
    elif damage == 'traversal': p['native']['items'][0]['order_index'] = 5
    elif damage == 'native_shape': d['pages'] = None
    result = build_hybrid(source, [p])
    assert result['hypotheses'][0]['status'] == 'rejected'
    assert result['hypotheses'][0]['issues'] and not result['hypotheses'][0]['regions']
    assert result['source'] == source and source_text(result, 1) == source_text(build_hybrid(original), 1)


def test_corrupt_source_ids_and_output_mutations_fail_validation(source):
    bad = deepcopy(source); bad['pages'][0]['characters'][0]['id'] = 'wrong'
    with pytest.raises(ExtractionError): build_hybrid(bad)
    p = prediction(source, [node(0, box=[0, 60, 190, 150])]); result = build_hybrid(source, [p])
    for mutate in ['unicode', 'drop', 'association', 'geometry']:
        changed = deepcopy(result)
        if mutate == 'unicode': changed['source']['pages'][0]['characters'][0]['text'] = 'MODEL'
        elif mutate == 'drop': changed['source']['pages'][0]['characters'].pop()
        elif mutate == 'association': changed['hypotheses'][0]['regions'][0]['geometric_character_ids'].pop()
        else: changed['hypotheses'][0]['regions'][0]['bbox'][0] += 1
        with pytest.raises(ExtractionError): validate_hybrid(changed, source)


def test_native_structure_membership_is_not_geometric_provenance(source):
    native = reconstruct(json_bytes(source))
    p = {'provider': 'structure_0_2', 'version': '0.2.0', 'source_pdf_sha256': source['source_sha256'],
         'status': 'available', 'native': {'document': native}, 'provenance': {}, 'error': None}
    result = build_hybrid(source, [p]); h = available(result)
    refs = [c['character_id'] for r in h['regions'] for c in r['native_membership'] if c['status'] == 'valid']
    assert refs == [c['id'] for c in source['pages'][0]['characters']]
    assert all(c['native_region_ids'] for c in h['associations'][0]['characters'])
    validate_hybrid(result, source)


def test_confidence_only_when_native_evidence_supplies_it(source):
    n = node(0, box=[0, 60, 190, 150]); n['confidence'] = .75
    h = available(build_hybrid(source, [prediction(source, [n])]))
    assert h['items'][-1]['confidence'] == {'value': .75, 'native_pointer': '#/texts/0/confidence'}


def test_json_key_order_does_not_change_canonical_hybrid(source):
    p = prediction(source, [node(0, box=[0, 60, 190, 150])]); original = build_hybrid(source, [p])
    p['native']['document'] = dict(reversed(list(p['native']['document'].items())))
    assert json_bytes(original) == json_bytes(build_hybrid(source, [p]))


def test_native_caption_parent_need_not_geometrically_contain_child(source):
    rows = [node(0, 'table', [0, 100, 190, 150], collection='tables', children=['#/texts/0'], text=None),
            node(0, 'caption', [0, 60, 80, 90], parent='#/tables/0')]
    h = available(build_hybrid(source, [prediction(source, rows)]))
    assert not h['overlaps']
    assert next(i for i in h['items'] if i['native_id'] == '#/texts/0')['parent_id'] == '#/tables/0'


def test_empty_visual_overlap_is_explicit_even_without_character_owners(source):
    rows = [node(0, 'picture', [0, 0, 30, 30]), node(1, 'picture', [10, 10, 40, 40])]
    h = available(build_hybrid(source, [prediction(source, rows)]))
    assert len(h['overlaps']) == 1 and all(r['status'] == 'zero_character_visual' for r in h['regions'])


def test_unavailable_traversal_and_geometry_are_not_invented(source):
    p = prediction(source, [node(0), node(1)]); p['native']['items'] = None
    p['native']['document']['body']['parent'] = None
    h = available(build_hybrid(source, [p]))
    assert h['regions'] == [] and h['reading_order']['kind'] == 'unavailable'
    assert all(i['geometry_status'] == 'unavailable' for i in h['items'])
    assert all(c['geometric_status'] == 'unmatched' for c in h['associations'][0]['characters'])


def test_duplicate_evidence_and_non_json_values_fail_closed(source):
    p = prediction(source, [node(0, box=[0, 60, 190, 150])])
    with pytest.raises(ExtractionError): build_hybrid(source, [p, p])
    p['native']['document']['texts'][0]['confidence'] = float('nan')
    with pytest.raises(ExtractionError): build_hybrid(source, [p])


def test_source_selection_is_original_backend_order_and_rejects_duplicates(source):
    d = build_hybrid(source); refs = [c['id'] for c in source['pages'][0]['characters']]
    assert source_text(d, 1, list(reversed(refs))) == 'ABCD'
    with pytest.raises(ExtractionError): source_text(d, 1, refs+refs)
    with pytest.raises(ExtractionError): source_text(d, 0)


def test_multiple_providers_do_not_create_cross_provider_geometric_ambiguity(source):
    p = prediction(source, [node(0, box=[0, 60, 190, 150])]); other = deepcopy(p)
    other['provenance']['run'] = 'another independent artifact'
    d = build_hybrid(source, [p, other])
    assert len(d['hypotheses']) == 2
    assert all(c['geometric_status'] == 'unambiguous' for h in d['hypotheses'] for c in h['associations'][0]['characters'])


def test_unicode_association_never_uses_model_transcription(fixtures):
    s = extract_pdf(fixtures/'unicode_units.pdf'); g = s['pages'][0]['geometry']
    d = build_hybrid(s, [prediction(s, [node(0, box=g['bbox'], text='ASCII replacement')])])
    h = available(d)
    assert source_text(d, 1, h['regions'][0]['geometric_character_ids']) == ''.join(c['text'] for c in s['pages'][0]['characters'])
    assert d['source']['pages'][0]['characters'] == s['pages'][0]['characters']


@pytest.mark.parametrize('origin', ['BOTTOMLEFT', 'TOPLEFT'])
def test_coordinate_origins_preserved_and_verified(source, origin):
    p = prediction(source, [node(0, box=[0, 60, 80, 90])])
    box = p['native']['document']['texts'][0]['prov'][0]['bbox']
    if origin == 'BOTTOMLEFT':
        box.update(t=140, b=110, coord_origin=origin)
    # The exposed export is native evidence and must agree byte-for-byte.
    p['native']['items'][0]['provenance'] = deepcopy(p['native']['document']['texts'][0]['prov'])
    r = available(build_hybrid(source, [p]))['regions'][0]
    assert r['bbox'] == [0, 60, 80, 90] and r['native_bbox']['coord_origin'] == origin


def test_native_structure_order_and_corrupted_membership(source):
    p = {'provider': 'structure_0_2', 'version': '0.2.0', 'source_pdf_sha256': source['source_sha256'],
         'status': 'available', 'native': {'document': reconstruct(json_bytes(source))}, 'provenance': {}, 'error': None}
    result = build_hybrid(source, [p]); h = available(result)
    assert order_hypothesis(result, h['id'], h['regions'][0]['id'], h['regions'][1]['id'])['direction'] == 'before'
    p['native']['document']['pages'][0]['regions'][0]['source_character_ids'][0] = 'wrong'
    result = build_hybrid(source, [p])
    assert result['hypotheses'][0]['status'] == 'rejected' and result['source'] == source


def test_demo_publication_is_atomic_and_never_overwrites(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('hybrid_demo', Path(__file__).parents[1]/'evaluation/hybrid_v0/demo.py')
    demo = importlib.util.module_from_spec(spec); spec.loader.exec_module(demo)
    output = tmp_path/'success'
    demo.publish(output, {'a.json': b'{}', 'b.json': b'[]'})
    with pytest.raises(FileExistsError): demo.publish(output, {'a.json': b'changed'})
    assert (output/'a.json').read_bytes() == b'{}'
    def fail(*args): raise OSError('authored rename failure')
    monkeypatch.setattr(Path, 'rename', fail)
    with pytest.raises(OSError): demo.publish(tmp_path/'failed', {'a.json': b'{}'})
    assert not (tmp_path/'failed').exists() and not (tmp_path/'.failed.lock').exists()


@pytest.mark.parametrize('name', ['unicode.pdf', 'unicode_units.pdf', 'verbatim.pdf', 'empty.pdf', 'image.pdf', 'multi.pdf', 'rotations.pdf', 'cropped.pdf', 'shifted.pdf', 'whitespace.pdf'])
def test_source_only_fallback_for_existing_authorized_synthetic_pdfs(fixtures, name):
    source = extract_pdf(fixtures/name); result = build_hybrid(source)
    validate_hybrid(result, source)
    assert result['source'] == source
    for page in source['pages']:
        assert source_text(result, page['page_number']) == ''.join(c['text'] for c in page['characters'])
