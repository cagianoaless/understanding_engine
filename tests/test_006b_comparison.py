"""Offline synthetic checks of the frozen comparison, never model inference."""

import importlib.util
from pathlib import Path

import pytest


PATH = Path(__file__).parents[1] / 'evaluation/experiments/006b/runs/2026-11-10-six-page-comparison/comparison.py'
SPEC = importlib.util.spec_from_file_location('compare006b', PATH)
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


def geometry():
    return dict(width=100, height=200, rotation=0, raw_rotation=0, user_unit=1,
                bbox=[0, 0, 100, 200], mediabox=[0, 0, 100, 200],
                cropbox=[0, 0, 100, 200], raw_cropbox=None)


def source():
    return {'page_number': 6, 'geometry': geometry(), 'characters': [
        {'id': 'a', 'text': 'α', 'bbox': [1, 1, 2, 2]},
        {'id': 'b', 'text': '(cid:80)', 'bbox': [3, 1, 4, 2]}]}


def prediction(rid, box=None, label='text', order=0, native=None):
    return {'id': rid, 'bbox': box or [0, 0, 10, 10], 'type': label,
            'order_index': order, 'text': 'α', 'native_source_character_ids': native}


def truth():
    return {'id': 'p', 'document_id': 'd', 'layout': 'synthetic', 'windows': [[0, 0, 100, 200]],
        'regions': [{'id': 't', 'bbox': [0, 0, 10, 10], 'type': 'text',
                     'classification_scoreable': True, 'category': 'body'}],
        'order_pairs': [], 'paragraph_decisions': []}


def test_origins_and_fail_closed_transforms():
    assert C.convert_box(dict(l=10, r=30, t=180, b=160, coord_origin='BOTTOMLEFT'), geometry()) == [10, 20, 30, 40]
    assert C.convert_box(dict(l=10, r=30, t=20, b=40, coord_origin='TOPLEFT'), geometry()) == [10, 20, 30, 40]
    for key, value in [('rotation', 90), ('user_unit', 2), ('cropbox', [1, 0, 100, 200])]:
        g = geometry(); g[key] = value
        with pytest.raises(ValueError):
            C.validate_geometry(g)
    with pytest.raises(ValueError):
        C.convert_box(dict(l=0, r=1, t=0, b=1, coord_origin='unknown'), geometry())


def test_greedy_ties_duplicates_and_window_center():
    refs = [dict(id='t2', bbox=[0, 0, 10, 10]), dict(id='t1', bbox=[0, 0, 10, 10])]
    predictions = [prediction('p2'), prediction('p1'), prediction('outside', [90, 90, 99, 99])]
    eligible, matches = C.match(predictions, refs, [[0, 0, 10, 10]])
    assert len(eligible) == 2
    assert matches == [dict(truth_id='t1', prediction_id='p1', iou=1), dict(truth_id='t2', prediction_id='p2', iou=1)]
    refs = [refs[0]]
    assert len(C.match(predictions, refs, [[0, 0, 10, 10]])[1]) == 1


def test_original_unicode_and_many_to_many_grounding():
    adapted = {'engine': 'docling', 'regions': [prediction('p1'), prediction('p2')], 'relations': None}
    C.ground(adapted, source())
    assert adapted['grounding']['status_counts'] == {'ambiguous': 2}
    assert adapted['regions'][0]['source_unicode_backend_order'] == 'α(cid:80)'
    assert adapted['regions'][0]['native_text_equals_source_backend_order'] is False
    assert adapted['grounding']['native_ids_once'] is None
    adapted = {'engine': 'structure', 'regions': [prediction('p', native=['a', 'foreign'])]}
    C.ground(adapted, source())
    assert adapted['grounding']['foreign_native_ids'] == ['foreign']
    assert adapted['grounding']['native_ids_once'] is False


def test_order_reachability_cycle_and_same_item_abstention():
    regions = [prediction(x, order=i) for i, x in enumerate('abc')]
    adapted = {'engine': 'structure', 'regions': regions, 'relations': [
        dict(before='a', after='b'), dict(before='b', after='c')]}
    assert C.relation_status(adapted, 'a', 'c') == 'correct'
    assert C.relation_status(adapted, 'c', 'a') == 'inversion'
    adapted['relations'].append(dict(before='c', after='a'))
    assert C.relation_status(adapted, 'a', 'c') == 'abstention'
    adapted['engine'] = 'docling'; regions[1]['order_index'] = 0
    assert C.relation_status(adapted, 'a', 'b') == 'abstention'


def test_paragraph_half_coverage_and_ambiguous_overlap():
    p = prediction('p1', [0, 0, 2, 3])
    result = C.strip_owner(['a', 'b'], [p], source())
    assert result['owner'] == 'p1' and result['candidates'][0]['covered'] == 1
    assert C.strip_owner(['a', 'b'], [p, prediction('p2')], source())['status'] == 'ambiguous'
    assert C.strip_owner(['a', 'b'], [prediction('caption', label='caption')], source())['status'] == 'unmatched'


def test_failures_remain_in_all_denominators():
    t = truth()
    t['regions'].append(dict(t['regions'][0], id='t2', bbox=[10, 10, 20, 20]))
    t['order_pairs'] = [dict(id='pair', before='t', after='t2')]
    t['paragraph_decisions'] = [dict(id='para', same_paragraph=True, source_character_ids=[['a'], ['b']])]
    result = C.score({'engine': 'docling', 'regions': [], 'relations': None}, t, source())
    assert result['localization']['fn'] == 2
    assert result['order'] == dict(correct=0, inversion=0, abstention=0, unscoreable=1)
    assert result['paragraph_denominator'] == 1 and result['paragraph_correct'] == 0
    assert result['grounding_window_counts']['unmatched'] == 2


def test_ambiguous_type_exclusion_does_not_exclude_localization():
    t = truth(); t['regions'][0]['classification_scoreable'] = False
    result = C.score({'engine': 'docling', 'regions': [prediction('p', label='heading')], 'relations': None}, t, source())
    assert result['localization']['tp'] == 1
    assert result['classification_truth_denominator'] == 0
    assert result['classification']['heading']['fp'] == 0
    assert result['confusion'] == {}


def test_wrong_class_is_end_to_end_fp_and_fn():
    result = C.score({'engine': 'docling', 'regions': [prediction('p', label='heading')], 'relations': None}, truth(), source())
    assert result['classification']['text']['fn'] == 1
    assert result['classification']['heading']['fp'] == 1
    assert result['localization']['tp'] == 1
    micro = C.aggregate([result, result])
    assert micro['localization']['tp'] == 2 and micro['order_correct_fraction'] is None


def test_docling_page_dimensions_and_provenance():
    item = dict(self_ref='#/texts/0', label='text', text='α', order_index=0,
                provenance=[dict(page_no=6, bbox=dict(l=0, r=10, t=200, b=190, coord_origin='BOTTOMLEFT'))])
    doc = {'pages': {'6': {'size': {'width': 100, 'height': 200}}}}
    adapted = C.adapt_docling([item], doc, source(), {'text': 'text'})
    assert adapted['regions'][0]['bbox'] == [0, 0, 10, 10]
    doc['pages']['6']['size']['width'] = 101
    with pytest.raises(ValueError):
        C.adapt_docling([item], doc, source(), {'text': 'text'})


def test_baseline_equivalence_never_renames_original_character_ids():
    def native(prefix, source_id='original:c0'):
        return {'pages': [{'page_number': 6, 'regions': [
            {'id': prefix+'r0', 'source_character_ids': [source_id], 'line_ids': [prefix+'l0'], 'bbox': [0, 0, 1, 1]}],
            'lines': [{'id': prefix+'l0', 'column_id': prefix+'c0'}],
            'columns': [{'id': prefix+'c0'}], 'relations': []}]}
    assert C.semantic_structure(native('host')) == C.semantic_structure(native('linux'))
    assert C.semantic_structure(native('host')) != C.semantic_structure(native('linux', 'changed:c0'))
