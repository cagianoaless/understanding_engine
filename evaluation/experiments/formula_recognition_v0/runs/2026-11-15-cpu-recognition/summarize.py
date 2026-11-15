"""Report the stopped first invocation without inventing mathematical scores."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from control import FORMULA,HERE,save,sha
from scoring import compare,relationships


def collect(raw,out):
    assert not out.exists();out.mkdir()
    frozen=json.loads((raw/'prediction-code-freeze.json').read_text())
    assert sha(FORMULA/'selection.json')==frozen['selection_sha256'] and sha(FORMULA/'references.json')==frozen['references_sha256']
    assert all(sha(HERE/n)==h for n,h in frozen['code_sha256'].items()),'Prediction or scoring code changed after freeze'
    selection=json.loads((FORMULA/'selection.json').read_text())['expressions']
    refs={v['id']:v for v in json.loads((FORMULA/'references.json').read_text())['expressions']}
    complete=json.loads((raw/'crop-attn_fraction.complete.json').read_text());native=raw/'native/crop-attn_fraction'
    events=[json.loads(l) for l in (native/'events.jsonl').read_text().splitlines()]
    samples=[json.loads(l) for l in (native/'cgroup-samples.jsonl').read_text().splitlines()]
    assert complete['resource']['timeout'] and complete['state']['ExitCode']==137 and not complete['state']['Running']
    assert not (native/'execution.json').exists(),'Unexpected completed worker result requires a different report'
    assert len([v for v in events if v['event']=='generate_start'])==1
    assert len([v for v in events if v['event']=='predictor_start'])==1
    assert not any(v['event']=='generate_success' for v in events)
    init=next(v for v in events if v['event']=='model_initialization_success');gen=next(v for v in events if v['event']=='generate_start');last=samples[-1]
    cpu={k:int(v) for k,v in (l.split() for l in last['cpu.stat'].splitlines())}
    resource=dict(external_deadline_seconds=120,external_wall_seconds=complete['resource']['external_wall_seconds'],container_state=complete['state'],
        model_initialization_seconds=init['seconds'],generate_entered_seconds=gen['elapsed'],last_observed_elapsed_seconds=last['elapsed'],
        generation_seconds_lower_bound=last['elapsed']-gen['elapsed'],initialization_success=True,predictor_invocations=1,generate_invocations=1,generate_completions=0,
        observed_kernel_memory_peak_bytes=max(int(s['memory.peak']) for s in samples),exact_final_kernel_memory_peak_bytes=None,
        memory_peak_reason='Highest sampled kernel high-water counter; killed worker could not write final counter; not process RSS/VM RAM or cold-start bound',
        last_memory_events={k:int(v) for k,v in (l.split() for l in last['memory.events'].splitlines())},
        last_cpu_stat=cpu,cpu_seconds_to_last_sample=cpu['usage_usec']/1e6,average_cores_to_last_sample=cpu['usage_usec']/1e6/last['elapsed'],
        sample_count=len(samples),kernel_limits={k:last[k] for k in ['memory.max','memory.swap.max','cpu.max']},host_config=complete['host_config'],
        warning='Host watchdog also logged PermissionError signaling its Docker CLI process group after Docker kill; container PID=0/exited, and attached CLI returned 137. No orphan inference or retry.')
    crops={r['id']:r for r in json.loads((raw/'crops-frozen.json').read_text())['crops']}
    predictions=[];results=[]
    for row in selection:
        attempted=row['id']=='attn_fraction';status='TIMEOUT' if attempted else 'NOT_EXECUTED_AFTER_FIRST_FAILURE'
        provenance=dict(pdf_sha256=row['pdf_sha256'],page=row['page'],source_geometry=row['geometry'],original_source_character_ids=row['source_character_ids'],
                        original_source_role='Authoritative extraction unchanged; no generated-text/source-symbol alignment',crop=crops[row['id']],model_revision='ecedbe111d15c2dc60bfd4a823cbe80127b58af4')
        predictions.append(dict(id=row['id'],scenario='crop',status=status,raw_generated_text=None,cleaned_latex=None,provenance=provenance,
             neural_call_observed=attempted,resource=resource if attempted else None,native_docling_formula_item=None,
             reason='No model return before deadline' if attempted else 'User stop condition: first invocation failed'))
        diagnostic=compare(refs[row['id']]['latex'],None);reference=relationships(refs[row['id']]['latex'])
        results.append(dict(id=row['id'],crop_status=status,end_to_end_status='NOT_EXECUTED_AFTER_FIRST_FAILURE',
            references='agent_visual_checked',independent_human_verifications=0,quality=diagnostic,
            reference_diagnostic_component_denominators={k:len(v) for k,v in reference['features'].items()} if reference['features'] else None,
            component_correctness=None,complete_expression_correct=None,unscoreable_reason='No generated LaTeX; do not classify as incorrect fraction/operator/index',
            syntax_validity=None,syntax_reason='No prediction to compile',visual_comparison=None,visual_reason='No prediction to render'))
    pages=sorted({(r['document'],r['page']) for r in selection})
    save(out/'predictions.json',dict(schema_version='formula-continuation-predictions.1',crop_predictions=predictions,
        end_to_end_predictions=[],end_to_end_pages=[dict(document=d,page=p,status='NOT_EXECUTED_AFTER_FIRST_FAILURE') for d,p in pages],raw_model_outputs=0))
    save(out/'results.json',dict(schema_version='formula-continuation-results.1',references='agent_visual_checked',human_verified_count=0,
        selected_targets=8,crop_attempted=1,crop_attempted_denominator=8,crop_completed=0,crop_completed_denominator=8,crop_timeout=1,crop_unexecuted=7,
        end_to_end_target_attempted=0,end_to_end_target_denominator=8,end_to_end_page_attempted=0,end_to_end_page_denominator=len(pages),
        quality_scoreable_predictions=0,correctly_recognized_complete_outputs=0,mathematical_accuracy=None,
        mathematical_accuracy_reason='No complete prediction; seven targets unexecuted, never claim 0/8 mathematical accuracy',
        crop_vs_end_to_end_comparison=None,crop_vs_end_to_end_reason='First crop timed out; no end-to-end inference permitted',expressions=results,
        decision='TIME_BUDGET_FAILURE; mathematical quality INDETERMINATE',formula_structure_v0='Not justified from this candidate run; no LaTeX available',
        next_candidate='A separately authorized bounded PP-FormulaNet-S resource/compatibility comparison is justified; no accuracy advantage established'))
    save(out/'first-invocation.json',resource)
    save(out/'model-manifest.json',json.loads((raw/'model-manifest.json').read_text()))
    save(out/'crops-frozen.json',json.loads((raw/'crops-frozen.json').read_text()))
    save(out/'prediction-code-freeze.json',frozen)
    save(out/'effective-options.json',json.loads((native/'formula-options.json').read_text()))
    (out/'first-events.jsonl').write_bytes((native/'events.jsonl').read_bytes())
    return resource


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(collect(a.raw,a.out),indent=2))
