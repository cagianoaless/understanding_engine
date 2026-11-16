"""Synthetic syntax tests; not recognition accuracy on real scientific papers."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import random

import pytest

from understanding_engine.contracts import ExtractionError, json_bytes, validator
from understanding_engine.formula_structure import ParseSettings, parse_formula
from understanding_engine.formula_structure_contract import validate_formula_structure


@pytest.fixture
def provenance():
    return dict(pdf_sha256='a'*64, page_number=1, bbox=[10., 20., 200., 60.],
                coordinate_system='pdfplumber-native-v1', crop_sha256='b'*64,
                model_name='authored-synthetic', model_revision='fixture-v1', prediction_id='example',
                prediction_record_sha256='c'*64, prediction_artifact_sha256='d'*64)


def parse(text, provenance, **kwargs):
    return parse_formula(text, provenance, termination=kwargs.pop('termination', 'complete'), **kwargs)


def nodes(result, kind):
    return [n for n in result['nodes'] if n['type'] == kind]


def child(result, node, role):
    ref = next(c['node_id'] for c in node['children'] if c['role'] == role)
    return next(n for n in result['nodes'] if n['id'] == ref)


def assert_graph(result):
    text = result['input']['latex']
    by_id = {n['id']: n for n in result['nodes']}
    assert len(by_id) == len(result['nodes'])
    seen = set()
    pending = [result['root_id']]
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        seen.add(key)
        node = by_id[key]
        a, b = node['character_span']
        assert 0 <= a <= b <= len(text) and node['source_text'] == text[a:b]
        pending.extend(c['node_id'] for c in node['children'])
        for c in node['children']:
            ca, cb = by_id[c['node_id']]['character_span']
            assert a <= ca <= cb <= b
            assert result['nodes'].index(by_id[c['node_id']]) < result['nodes'].index(node)
    assert seen == set(by_id)
    if result['tokens']:
        assert ''.join(t['text'] for t in result['tokens']) == text
        for t in result['tokens']:
            assert text[t['start']:t['end']] == t['text']
    validate_formula_structure(result)


def test_nested_fraction_roles_and_exact_substrings(provenance):
    r = parse(r'  \frac{a+1}{\frac{b}{c}}  ', provenance)
    assert r['status']['parsing'] == 'parsed'
    outer, inner = sorted(nodes(r, 'fraction'), key=lambda n: -len(n['source_text']))
    assert child(r, outer, 'numerator')['source_text'] == '{a+1}'
    assert child(r, outer, 'denominator')['source_text'] == r'{\frac{b}{c}}'
    assert child(r, inner, 'numerator')['source_text'] == '{b}'
    assert_graph(r)


def test_radical_scope_and_optional_degree(provenance):
    r = parse(r'\sqrt[3]{x_{i}^{2}+1}', provenance)
    radical = nodes(r, 'radical')[0]
    assert child(r, radical, 'degree')['source_text'] == '[3]'
    assert child(r, radical, 'radicand')['source_text'] == '{x_{i}^{2}+1}'
    assert len(nodes(r, 'subscript')) == len(nodes(r, 'superscript')) == 1
    assert_graph(r)


def test_summation_limits_do_not_infer_binding_or_summand(provenance):
    r = parse(r'\sum_{i=1}^{N}x_i', provenance)
    summation = nodes(r, 'summation')[0]
    assert child(r, summation, 'lower_limit')['source_text'] == '{i=1}'
    assert child(r, summation, 'upper_limit')['source_text'] == '{N}'
    assert {c['role'] for c in summation['children']} == {'operator','lower_limit','upper_limit'}
    assert summation['attributes']['variable_binding'] == 'not_inferred'
    assert_graph(r)


def test_bare_letters_never_become_a_function_or_joined_identifier(provenance):
    r = parse('A t t e n t i o n ( Q , K , V )', provenance)
    assert not nodes(r, 'operator_group')
    assert [n['source_text'] for n in nodes(r, 'symbol')][:9] == list('Attention')
    assert r['status']['acceptance'] == 'inspect_with_ambiguities'
    assert_graph(r)


def test_script_on_spaced_head_attaches_to_final_latex_letter(provenance):
    r = parse('h e a d _1', provenance)
    script = nodes(r, 'subscript')[0]
    assert child(r, script, 'base')['source_text'] == 'd'
    assert script['source_text'] == 'd _1'
    assert r['status']['structural_support'] == 'ambiguous'


def test_explicit_operator_group_is_distinct_from_a_verified_function(provenance):
    r = parse(r'\operatorname{A t t e n t i o n}(x)', provenance)
    operator = nodes(r, 'operator_group')[0]
    assert operator['attributes']['semantic_identity'] == 'not_inferred'
    assert operator['source_text'] == r'\operatorname{A t t e n t i o n}'
    assert nodes(r, 'delimited_group') and len(operator['children']) == 1
    assert r['evidence_status']['mathematical_correctness'] == 'unverified'
    assert_graph(r)


def test_sin_bare_letters_vs_explicit_command_and_bold_typography(provenance):
    bare = parse('s i n(x)', provenance)
    explicit = parse(r'\sin(x)', provenance)
    assert not nodes(bare, 'operator_group') and len(nodes(explicit, 'operator_group')) == 1
    styled = parse(r'x+\mathbf{x}', provenance)
    assert nodes(styled, 'typography_group')[0]['attributes']['command'] == r'\mathbf'
    assert [n['source_text'] for n in nodes(styled, 'symbol')] == ['x','x']
    assert_graph(styled)


def test_text_group_does_not_infer_function_application(provenance):
    r = parse(r'\text{softmax}(x)', provenance)
    assert nodes(r, 'text_group') and not nodes(r, 'operator_group')
    assert child(r, nodes(r, 'text_group')[0], 'body')['source_text'] == 'softmax'
    assert r['status']['structural_support'] == 'ambiguous'


@pytest.mark.parametrize('text', [r'x+\unknown{y}', r'x+\intertext{and}', r'\text{We therefore condition the ceiling}', r'\begin{array}{c}x\end{array}', '{x', '(x]', r'\left(x\right]', 'x^', 'x_1_2', 'x=', 'x++y', 'x+', r'\frac12', 'x_12', r'\frac{x}{}'])
def test_malformed_unsupported_or_empty_arguments_never_full_success(text, provenance):
    r = parse(text, provenance)
    assert r['status']['parsing'] in {'partial','rejected'}
    assert r['status']['acceptance'] == 'reject'
    assert r['input']['latex'] == text
    assert nodes(r, 'unknown') or any(n['status']=='unresolved' for n in r['nodes'])
    assert_graph(r)


def test_parsed_prefix_is_only_an_explicit_fragment(provenance):
    r = parse(r'x=\frac{a}{', provenance)
    assert r['status']['parsing'] == 'partial'
    root = next(n for n in r['nodes'] if n['id'] == r['root_id'])
    assert root['type'] == 'unknown' and root['source_text'] == r'x=\frac{a}{'
    assert all(c['role'] == 'parsed_fragment' for c in root['children'])
    assert not nodes(r, 'fraction')  # Never manufacture the missing denominator.
    assert_graph(r)


def test_incomplete_generation_blocks_acceptance_even_for_balanced_math(provenance):
    r = parse('x=1', provenance, termination='incomplete')
    assert r['status']['syntax'] == 'complete_for_v0_grammar'
    assert r['status']['parsing'] == 'partial' and r['status']['acceptance'] == 'reject'
    assert any(d['code']=='incomplete_model_generation' for d in r['diagnostics'])
    assert next(n for n in r['nodes'] if n['id']==r['root_id'])['status']=='unresolved'


def test_unknown_termination_is_not_guessed_from_balanced_braces(provenance):
    r = parse('x=1', provenance, termination='unknown')
    assert r['input']['termination']=='unknown' and r['status']['acceptance']=='inspect_with_ambiguities'


def test_multiline_does_not_invent_a_relation_chain_across_rows(provenance):
    r = parse(r'x&=1\\y&=2', provenance)
    assert not nodes(r, 'relation')
    assert len(nodes(r, 'operator')) == 2
    assert r['status']['structural_support']=='ambiguous'
    assert_graph(r)


def test_exact_unicode_raw_evidence_and_determinism(provenance):
    text = '𝛼 + e\u0301 = α'
    original = deepcopy(provenance)
    a = parse(text, provenance, raw_model_output='<formula>'+text)
    b = parse(text, provenance, raw_model_output='<formula>'+text)
    assert json_bytes(a)==json_bytes(b) and provenance==original
    assert a['input']['latex']==text and a['input']['raw_model_output']=='<formula>'+text
    assert_graph(a)


@pytest.mark.parametrize('settings,text,code', [
    (ParseSettings(max_input_characters=4),'x'*50,'input_character_limit'),
    (ParseSettings(max_tokens=3),'a + b + c','token_limit'),
    (ParseSettings(max_nodes=2),'x+y','node_limit'),
    (ParseSettings(max_depth=3,repetition_limit=64),'{'*20+'x'+'}'*20,'depth_limit'),
    (ParseSettings(),'x '*50,'excessive_repetition'),
])
def test_resource_guards_preserve_full_input_and_bounded_result(settings,text,code,provenance):
    r = parse(text, provenance, settings=settings)
    assert r['input']['latex']==text and r['status']['acceptance']=='reject'
    assert any(d['code']==code for d in r['diagnostics'])
    assert len(r['nodes']) <= settings.max_nodes+1
    assert_graph(r)


def test_diagnostic_budget_and_error_are_explicit(provenance):
    r = parse('{ab}+{cd}+{ef}+{gh}+{ij}+{kl}+{mn}+{op}+'+r'\bad', provenance, settings=ParseSettings(max_diagnostics=2))
    assert len(r['diagnostics'])<=2 and r['status']['diagnostics']=='bounded'
    assert r['diagnostics'][-1]['code']=='unsupported_command'


@pytest.mark.parametrize('setting', [dict(max_depth=10000),dict(max_tokens=True),dict(max_nodes=0),dict(repetition_limit=2)])
def test_unsafe_settings_rejected(setting):
    with pytest.raises(ValueError):ParseSettings(**setting)


@pytest.mark.parametrize('setting', [{}, False, 0])
def test_invalid_settings_never_silently_use_defaults(provenance, setting):
    with pytest.raises(TypeError):parse('x',provenance,settings=setting)


@pytest.mark.parametrize('field,value', [('pdf_sha256','bad'),('page_number',0),('bbox',[0,0,0,1]),('bbox',[1,0,0,1]),('bbox',[0,0,float('nan'),1]),('coordinate_system','screen'),('prediction_record_sha256','bad')])
def test_invalid_provenance_fails_before_parsing(provenance,field,value):
    provenance[field]=value
    with pytest.raises(ExtractionError):parse('x',provenance)


@pytest.mark.parametrize('corruption', ['text','span','child','unicode','source_verified'])
def test_validator_rejects_corrupted_graph_or_authority_claim(provenance,corruption):
    r=parse(r'x=\frac{a}{b}',provenance)
    if corruption=='text':r['nodes'][0]['source_text']='invented'
    elif corruption=='span':r['nodes'][0]['character_span']=[100,200]
    elif corruption=='child':r['nodes'][-1]['children'][0]['node_id']=r['root_id']
    elif corruption=='unicode':r['input']['latex']='y=1'
    else:r['evidence_status']['source_validation']='source_verified'
    with pytest.raises(ExtractionError):validate_formula_structure(r)


def test_syntactically_wrong_mathematics_never_becomes_source_verified(provenance):
    r=parse('1=2',provenance)
    assert r['status']['parsing']=='parsed'
    assert r['evidence_status']['mathematical_correctness']=='unverified'
    assert r['evidence_status']['source_alignment']=='formula_crop_only'
    assert not any('bbox' in n or 'source_character_ids' in n for n in r['nodes'])


def test_seeded_adversarial_strings_have_total_bounded_behavior(provenance):
    rng=random.Random(39)
    alphabet=['x','+',r'\frac','{','}',r'\input','^','_',r'\sqrt','1','(',')',r'\sum']
    for _ in range(120):
        text=' '.join(rng.choice(alphabet) for _ in range(rng.randrange(1,45)))
        r=parse(text,provenance,settings=ParseSettings(max_tokens=100,max_nodes=120,max_depth=8))
        assert_graph(r)


def test_schema_is_valid():
    assert validator('formula-structure-0.1')


def test_retained_eight_examples_validate_and_preserve_original_hypotheses():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    run=root/'evaluation/experiments/formula_structure_v0'
    original=root/'evaluation/experiments/formula_recognition_v0/runs/2026-11-16-t4-crops/predictions.json'
    records=json.loads(original.read_text())['codeformula']
    artifact_hash=hashlib.sha256(original.read_bytes()).hexdigest()
    for record in records:
        result=json.loads((run/'examples'/f"{record['id']}.json").read_text())
        assert result['input']['latex']==record['cleaned_latex']
        assert result['input']['raw_model_output']==record['raw_model_output']
        assert result['provenance']['prediction_record_sha256']==hashlib.sha256(json_bytes(record)).hexdigest()
        assert result['provenance']['prediction_artifact_sha256']==artifact_hash
        assert_graph(result)
        assert result['evidence_status']['mathematical_correctness']=='unverified'


def test_eight_record_accounting_and_parsing_correctness_diverge():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    result=json.loads((root/'evaluation/experiments/formula_structure_v0/results.json').read_text())
    assert result['selected_denominator']==8
    assert result['parsing_counts']=={'parsed':6,'partial':2}
    assert result['parsing_counts'].get('rejected',0)==0
    assert result['acceptance_counts']['reject']==2
    assert result['unresolved_nodes']==3 and result['identifier_grouping_ambiguities']==27
    assert result['mathematically_unverified']==8 and result['symbol_aligned_to_original_pdf']==0
    rows={r['id']:r for r in result['per_formula']}
    assert rows['nature_softmax']['status']['parsing']=='parsed'
    assert rows['nature_softmax']['provisional_source_full_expression_correct'] is False
    assert rows['log_eq2']['status']['acceptance']=='reject' and rows['log_eq2']['termination']=='incomplete'
    assert result['pp_comparison_only']['parsed'] is False
    assert result['independent_human_verifications']==0


def test_evaluation_candidate_has_no_reference_or_pp_inputs():
    from pathlib import Path
    import runpy
    root=Path(__file__).resolve().parents[1]
    evaluate=runpy.run_path(str(root/'evaluation/experiments/formula_structure_v0/evaluate.py'))
    # Same prediction parsed alone is byte-identical to its cohort result.
    records=json.loads((root/'evaluation/experiments/formula_recognition_v0/runs/2026-11-16-t4-crops/predictions.json').read_text())['codeformula']
    stored=json.loads((root/'evaluation/experiments/formula_structure_v0/examples/attn_fraction.json').read_text())
    outputs,_=evaluate['parse_inputs']([records[0]],stored['provenance']['prediction_artifact_sha256'])
    assert json_bytes(outputs[0])==json_bytes(stored)
