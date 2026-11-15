"""Frozen PR21 reconstruction, new native evidence, labels read only after predictions."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import resource
import time

from understanding_engine.contracts import json_bytes
from ..svg_math_feasibility import reconstruct as frozen
from ..svg_math_feasibility.experiment import evaluate,crop_units,source_units
from .native import adapt,rules_in_region,require,RULE_POLICY
from .fonts import resolve

HERE=Path(__file__).parent
ROOT=HERE.parents[2]


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save(path,obj):path.write_bytes(json_bytes(obj))


def relation_signature(prediction):
    relations=deepcopy(prediction['relations'])
    relations['fractions']=[dict(numerator=f['numerator'],denominator=f['denominator']) for f in relations['fractions']]
    return dict(relations=relations,equation_number_units=prediction['equation_number_units'],
                unresolved=prediction['unresolved_symbol_ids'],conserved=sorted(prediction['conserved_unit_ids']),ambiguities=prediction['ambiguities'])


def aggregate(rows):
    result={}
    for mode in sorted({m for row in rows for m in row['scores']}):
        available=[row['scores'][mode] for row in rows if mode in row['scores']]
        metrics={}
        for kind in ['fractions','indices','summations','delimiters','operators','expression_parts','equation_number']:
            values=[r[kind] for r in available];ref={k:sum(v['reference'][k] for v in values) for k in ['denominator','correct','incorrect','missing','ambiguous','unscoreable']}
            metrics[kind]=dict(reference=ref,incorrect_proposals=sum(v.get('incorrect_predictions',0) for v in values),
                correct_ratio=ref['correct']/ref['denominator'] if ref['denominator'] else None,
                ratio_reason=None if ref['denominator'] else 'No reference component of this type; not a success')
        result[mode]=metrics
    return result


def execute(inputs_path,out):
    require(not out.exists(),'Refuse to overwrite output');started=time.perf_counter()
    freeze=json.loads((HERE/'freeze.json').read_bytes());manifest=json.loads((HERE/'input-manifest.json').read_bytes())
    require(sha(HERE/'reference.json')==freeze['reference_sha256'],'Reference changed')
    require(sha(HERE/'regions.json')==manifest['regions_sha256'],'Region selection changed')
    require(frozen.CONFIG==freeze['configuration'],'Frozen algorithm settings differ')
    require(all(sha(ROOT/p)==h for p,h in freeze['frozen_parent_files'].items()),'Parent algorithm/reference/scorer changed')
    require(all(RULE_POLICY[k]==freeze['native_rule_policy'][k] for k in RULE_POLICY),'Native rule policy changed')
    local=json.loads(inputs_path.read_bytes());expected={d['id']:d for d in manifest['documents']}
    require(set(d['id'] for d in local['documents'])==set(expected),'Unexpected document set')
    for doc in local['documents']:
        reg=expected[doc['id']]
        require(sha(Path(doc['pdf']))==reg['pdf_sha256'] and sha(Path(doc['source']))==reg['source_sha256'],'PDF/extraction bytes differ')
    retained=Path(local['retained_svg_rules']['path'])
    require(sha(retained)==manifest['retained_svg_rules']['sha256'],'Retained SVG evidence changed')
    old={p['id']:p for p in json.loads(retained.read_bytes())['equations']}
    regions=json.loads((HERE/'regions.json').read_bytes())['regions'];out.mkdir();predictions=[];timings=[];diagnostics={}
    for doc in local['documents']:
        t=time.perf_counter();source=json.loads(Path(doc['source']).read_bytes());selected=[r for r in regions if r['document']==doc['id']];pages=sorted({r['page'] for r in selected})
        require(source['source_sha256']==expected[doc['id']]['pdf_sha256'],'Wrong original identity')
        native=adapt(Path(doc['pdf']),source,pages);glyphs=resolve(Path(doc['pdf']),source,pages);diagnostics[doc['id']]=glyphs
        save(out/(doc['id']+'-native.json'),native);save(out/(doc['id']+'-glyphs.json'),glyphs)
        native_pages={p['page_number']:p for p in native['pages']}
        for region in selected:
            page=source['pages'][region['page']-1];units=crop_units(source_units(page),region['bbox'])
            rules=rules_in_region(native_pages[region['page']],region['bbox']);variants={'characters':[],'native_vectors':rules}
            if region['role']=='exposed_control':
                previous=old[region['parent_id']];require(previous['source_units']==units,'Retained original character inputs differ')
                variants['retained_svg']=previous['shapes']
            candidates={};query_times={}
            for mode,primitives in variants.items():
                tick=time.perf_counter();candidate=frozen.build(units,primitives,page['geometry']['width']);query_times[mode]=time.perf_counter()-tick
                require(Counter(candidate['conserved_unit_ids'])==Counter(u['id'] for u in units),'Frozen candidate lost/duplicated source characters')
                candidates[mode]=candidate
            predictions.append(dict(**region,pdf_sha256=source['source_sha256'],geometry=page['geometry'],units=units,
                native_rules=rules,retained_svg_rules=variants.get('retained_svg'),candidates=candidates))
            timings.append(dict(id=region['id'],candidate_seconds=query_times))
        timings.append(dict(document=doc['id'],load_validate_adapter_font_seconds=time.perf_counter()-t))
    # No reference component file was opened in the candidate path.
    save(out/'predictions.json',dict(schema_version='native-math-predictions.1',configuration=frozen.CONFIG,regions=predictions))
    prediction_sha=sha(out/'predictions.json')
    parent_ref=json.loads((ROOT/'evaluation/experiments/svg_math_feasibility/reference.json').read_bytes())
    new_ref=json.loads((HERE/'reference.json').read_bytes());gold={'log_eq'+str(r['number']):r for r in parent_ref['equations']}
    gold.update({r['id']:r for r in new_ref['equations']});results=[];control_checks=[]
    for row in predictions:
        ref=gold[row['id']];scores={mode:evaluate(ref,candidate,[]) for mode,candidate in row['candidates'].items()}
        selected_ids={u['id'] for u in row['units']}
        font_rows=[g for page in diagnostics[row['document']]['pages'] if page['page_number']==row['page'] for g in page['glyphs'] if g['source_id'] in selected_ids]
        result=dict(id=row['id'],document=row['document'],page=row['page'],role=row['role'],original_units=len(row['units']),
            scores=scores,unresolved={m:c['unresolved_symbol_ids'] for m,c in row['candidates'].items()},
            ambiguities={m:c['ambiguities'] for m,c in row['candidates'].items()},
            fraction_memberships={m:c['relations']['fractions'] for m,c in row['candidates'].items()},
            proposed_indices={m:c['relations']['indices'] for m,c in row['candidates'].items()},
            rules=row['native_rules'],glyph_diagnostics=font_rows,
            unsupported_components=ref.get('unsupported_components',[]),semantic_equivalence=None,
            semantic_reason='Frozen geometric hypotheses; products, radicals, implicit multiplication and full math semantics not implemented')
        results.append(result)
        if row['role']=='exposed_control':
            prior=old[row['parent_id']]['candidates'];a=row['candidates']['characters'];b=row['candidates']['native_vectors'];c=row['candidates']['retained_svg']
            check=dict(id=row['id'],original_only_reproduces_PR21=relation_signature(a)==relation_signature(prior['source_only']),
                retained_svg_reproduces_PR21=relation_signature(c)==relation_signature(prior['combined']),
                native_equals_svg_grouping=relation_signature(b)==relation_signature(c),rule_coordinate_differences=[])
            for native_rule in row['native_rules']:
                differences=[max(abs(x-y) for x,y in zip(native_rule['bbox'],s['bbox'])) for s in row['retained_svg_rules']]
                check['rule_coordinate_differences'].append(min(differences) if differences else None)
            require(check['original_only_reproduces_PR21'] and check['retained_svg_reproduces_PR21'],'Historical baseline did not reproduce')
            control_checks.append(check)
    full=dict(schema_version='native-math-results.1',references='agent_visual_checked',human_verified_count=0,predictions_sha256=prediction_sha,
        reference_sha256=freeze['reference_sha256'],control_checks=control_checks,regions=results,
        control_aggregate=aggregate([r for r in results if r['role']=='exposed_control']),
        generalization_aggregate=aggregate([r for r in results if r['role']=='new_component_evaluation']),
        per_document={doc:aggregate([r for r in results if r['document']==doc]) for doc in expected})
    save(out/'results.json',full)
    # Small export removes duplicated expected IDs; references/full scores remain available.
    small=deepcopy(full)
    for row in small['regions']:
        for metrics in row['scores'].values():
            for metric in metrics.values():
                for item in metric.get('items',[]):item.pop('expected',None)
    save(out/'results.compact.json',small)
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    save(out/'run.local.json',dict(seconds=time.perf_counter()-started,timings=timings,python=platform.python_version(),
        peak_process_memory_bytes=peak if platform.system()=='Darwin' else peak*1024,peak_scope='Whole-process peak, including source JSON/validation, not per reconstruction',
        input_paths=local,predictions_sha256=prediction_sha,reference_loaded_after_prediction_write=True,
        phase2_unicode_never_fed_to_reconstruction=True))
    return full


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();execute(a.inputs,a.out)


if __name__=='__main__':main()
