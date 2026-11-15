"""Export small inspection evidence. No reconstruction, parameter changes or text repair."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil

from understanding_engine.contracts import json_bytes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ['run','source','svg-render','font-evidence','reference','figures','out']:parser.add_argument('--'+k,type=Path,required=True)
    a=parser.parse_args();assert not a.out.exists();a.out.mkdir()
    load=lambda p:json.loads(p.read_bytes())
    source=load(a.source);predictions=load(a.run/'predictions.json')['equations'];results=load(a.run/'equation-results.json')
    fonts=load(a.font_evidence);render=load(a.svg_render/'render.json');reference=load(a.reference)
    assert results['reference_sha256']==hashlib.sha256(a.reference.read_bytes()).hexdigest() and render['complete']
    inventory=load(a.run/'input-manifest.json');inspection=load(a.run/'svg-inspection.json');native=load(a.run/'pdf-native-lines.json')
    native_by_id={r['id']:r for r in native['regions']}
    for pred,result,ref in zip(predictions,results['equations'],reference['equations']):
        if result['status']!='comparable_region':continue
        pdf_native=native_by_id[pred['id']]
        bindings={b['svg_id']:b['source_ids'][0] for b in pred['bindings'] if len(b['source_ids'])==1}
        formula_ids={g['source_id'] for g in result['glyphs']}
        result['native_font_diagnostic']=[g for g in fonts['glyphs'] if g['source_id'] in formula_ids]
        result['native_font_diagnostic_note']='Glyph names retained in original PDF font program; not consumed by candidate, no Unicode correction or generic font decoder implemented.'
        result['native_character_contract_check']=dict(matches=pdf_native['native_character_exact_matches'],denominator=pdf_native['native_character_denominator'],fields=['Unicode','bbox','matrix','backend index'])
        bar_differences=[]
        for shape,line in zip(pred['shapes'],pdf_native['lines']):bar_differences.append(max(abs(x-y) for x,y in zip(shape['bbox'],line['bbox'])))
        result['fraction_bar_geometry']=dict(svg_primitives=len(pred['shapes']),native_pdf_lines=len(pdf_native['lines']),
           max_coordinate_difference=max(bar_differences,default=None),native_pdf_lines_not_serialized_in_existing_contract=True)
        result['visual_fidelity']=dict(status='not_faithful_for_summations_or_exact_fonts',verification='agent_visual_checked',
          replacement_glyphs=sum(g['svg_text']=='\ufffd' for g in result['glyphs']),equivalent_presentation_count=None,
          equivalent_presentation_reason='No automatic Unicode equivalence/normalization and no per-glyph pixel scoring protocol',
          renderer_fonts=[x for row in render['fonts'] for x in row['fonts']],font_programs_embedded_in_target_svg=0,
          note='Native anchors are preserved; different glyph/font extents are visible. Full pixel accuracy remains null.')
        result['proposed_indices']={}
        for mode,candidate in pred['candidates'].items():
            result['proposed_indices'][mode]=[dict(kind=r['kind'],base=[bindings.get(x,x) for x in r['base']],script=[bindings.get(x,x) for x in r['script']]) for r in candidate['relations']['indices']]
            bykind={}
            for kind in ['subscript','superscript']:
                items=[item for item in result['scores'][mode]['indices']['items'] if item['expected']['kind']==kind]
                c=Counter(item['status'] for item in items)
                bykind[kind]=dict(denominator=len(items),**{status:c[status] for status in ['correct','incorrect','missing','ambiguous','unscoreable']})
            result['scores'][mode]['indices']['by_kind']=bykind
        result['unsupported']=dict(complete_verified_expression_tree=None,mathematical_equivalence=None,verified_reading_order=None,
             summation_variable_domain_semantics=None,glyph_bbox_iou=None,
             reason='Partial geometric hypotheses; missing sum identity, wrong index links, no mathematical semantics/pixel/linear-order oracle')
        result['fraction_memberships']=[dict(numerator_units=len(f['numerator']),denominator_units=len(f['denominator']),svg_bar_id=f['bar_id']) for f in pred['candidates']['svg_only']['relations']['fractions']]
    results['aggregate']={}
    for mode in ['svg_only','source_only','combined']:
        by={}
        for kind in ['fractions','indices','summations','delimiters','operators','expression_parts','equation_number']:
            rows=[e['scores'][mode][kind] for e in results['equations']]
            by[kind]={'reference':{k:sum(row['reference'][k] for row in rows) for k in ['denominator','correct','incorrect','missing','ambiguous','unscoreable']},
                      'incorrect_proposals':sum(row.get('incorrect_predictions',0) for row in rows)}
        results['aggregate'][mode]=by
    results['interpretation']='Two controlled development equations; provisional agent-reference counts, not independent/generalization evidence.'
    (a.out/'equation-results.json').write_bytes(json_bytes(results))
    inventory['source_extraction']['warnings']=source['warnings']
    inventory['pdf']['geometry_by_page']=[dict(page=p['page_number'],geometry=p['geometry']) for p in source['pages']]
    inventory['document_identity_limit']='The originally requested clean_preview PDF is absent. Comparisons use the explicitly user-confirmed final_preview PDF only; no claim about the absent revision.'
    (a.out/'input-manifest.json').write_bytes(json_bytes(inventory))
    inspection['aggregate']=dict(svg_pages=len(inspection['pages']),replacement_characters=sum(p['replacement_characters'] for p in inspection['pages']),
        literal_whitespace=sum(p['literal_whitespace'] for p in inspection['pages']),replacement_pages=[p['page'] for p in inspection['pages'] if p['replacement_characters']],
        font_program_elements=sum(p['tags'].get('font',0)+p['tags'].get('font-face',0) for p in inspection['pages']),
        note='Paths are not assumed to be glyphs. Curves/references/clipping are explicitly unresolved; no path OCR.')
    inspection['aggregate']['original_source_whitespace_units']=sum(c['text'].isspace() for p in source['pages'] for c in p['characters'])
    for row in inspection['pages']:
        raw=load(a.run/f"page-{row['page']}-inspection.json")
        matrices=Counter(tuple(u['matrix']) for u in raw['text'])
        row['positioning']=dict(text_anchors=dict(Counter(u['text_anchor'] for u in raw['text'])),distinct_composed_matrices=len(matrices),
           most_frequent_matrices=[dict(matrix=list(m),units=n) for m,n in matrices.most_common(3)],
           note='All per-unit raw positions, inherited presentation and matrices retained in hashed external inspection files; unresolved advances are not guessed.')
    (a.out/'svg-inspection.json').write_bytes(json_bytes(inspection))
    # One small source-linked partial tree example, never the whole paper.
    available=[p for p in predictions if p['status']=='candidate_predictions_frozen']
    if not available:
        (a.out/'partial-expression-example.json').write_bytes(json_bytes(dict(tree=None,reason='No comparable prediction region')))
        return
    pred=available[0];mapping={b['svg_id']:b['source_ids'] for b in pred['bindings']};s={u['id']:u['text'] for u in pred['source_units']}
    def compact(n):
        value={k:v for k,v in n.items() if k in {'kind','operator','implicit_operations','script_kinds','bar_id'}}
        if 'text' in n:value['svg_text_diagnostic']=n['text']
        if 'unit_ids' in n:
            value['svg_units']=n['unit_ids'];value['source_character_ids']=[x for u in n['unit_ids'] for x in mapping.get(u,[])]
            value['original_unicode']=[s[x] for x in value['source_character_ids']]
        if n.get('children'):value['children']=[compact(c) for c in n['children']]
        return value
    example=dict(schema_version='svg-math-example.1',status='partial_unresolved',pdf_sha256=source['source_sha256'],page=4,
        svg_sha256=inventory['svgs'][3]['sha256'],provenance='Unique geometric associations, no native membership or text correction',
        tree=compact(pred['candidates']['svg_only']['expression_tree']))
    (a.out/'partial-expression-example.json').write_bytes(json_bytes(example))
    (a.out/'font-evidence.json').write_bytes(json_bytes(fonts))
    for name in ['eq2.png','eq4.png']:shutil.copy2(a.figures/name,a.out/name)


if __name__=='__main__':main()
