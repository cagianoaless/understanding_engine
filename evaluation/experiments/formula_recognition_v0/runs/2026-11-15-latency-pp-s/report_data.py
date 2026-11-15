"""Separate diagnostic outcomes from unexecuted mathematical quality evaluation."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
FORMULA=HERE.parents[1]
CAP=7*1024**3
WORK=128*1024**2


def write(path,value):
    with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def progress_status(events):
    if not any(v['event']=='generate_start' for v in events):return 'generation_not_observed'
    if not any(v['event']=='forward_start' for v in events):return 'before_instrumented_top_level_forward_and_no_decode_evidence'
    if any(v['event']=='tokens_observed' for v in events):return 'emission_observed; incomplete output is not full-formula correctness'
    return 'forward_entered_without_observed_token_emission'


def budget_plan(snapshot,parts,model_bytes,model_rounded_bytes=None):
    logical=sum(v['declared_unpacked_logical_bytes'] for v in parts)+model_bytes
    rounded=sum(v['rounded_4KiB_file_estimate_bytes'] for v in parts)+(model_rounded_bytes if model_rounded_bytes is not None else ((model_bytes+4095)//4096)*4096)
    return dict(current_allocation_bytes=snapshot['allocated_bytes'],remaining_cap_bytes=CAP-snapshot['allocated_bytes'],
        component_logical_bytes=logical,component_rounded_estimate_bytes=rounded,
        projection_without_archives_or_work_bytes=snapshot['allocated_bytes']+rounded,
        projection_with_work_margin_bytes=snapshot['allocated_bytes']+rounded+WORK,
        logical_excess_before_remaining_dependencies_bytes=max(0,snapshot['allocated_bytes']+logical-CAP),
        rounded_excess_before_remaining_dependencies_bytes=max(0,snapshot['allocated_bytes']+rounded-CAP),
        admission='FAIL' if snapshot['allocated_bytes']+rounded+WORK>CAP else 'UNKNOWN_FULL_CLOSURE_NOT_RESOLVED',
        measured_installed_fit=False,complete_dependency_closure=False,
        caveat='ZIP-declared logical/4KiB planning estimates, not actual/exclusive APFS allocation. Optimistically excludes remaining dependencies, archives, directory metadata, pyc, staging, runtime images and duplicate model copies.')


def collect(raw,out):
    assert not out.exists();out.mkdir()
    result=json.loads((raw/'max64.result.json').read_text());native=raw/'max64'
    events=[json.loads(l) for l in (native/'events.jsonl').read_text().splitlines()];samples=[json.loads(l) for l in (native/'cgroup.jsonl').read_text().splitlines()]
    assert result['timeout'] and result['state']['ExitCode']==137 and not result['state']['Running']
    assert not (native/'execution.json').exists() and not any(v['event']=='predictor_return' for v in events)
    assert not (raw/'256.started.json').exists() and not (raw/'max256.started.json').exists()
    gen=next(v for v in events if v['event']=='generate_start');load=next(v for v in events if v['event']=='load_success');last=samples[-1]
    cpu={k:int(v) for k,v in (line.split() for line in last['cpu.stat'].splitlines())}
    diagnostic=dict(schema_version='codeformula-latency-diagnostic.1',classification='LATENCY_DIAGNOSTIC_NOT_ACCURACY_EXPERIMENT',cap64_status='TIMEOUT_INCOMPLETE',cap256_status='NOT_EXECUTED_FIRST_DID_NOT_COMPLETE',
        invocations=1,maximum_authorized_invocations=2,model_loaded=True,stage_load_seconds=load['seconds'],generate_start_elapsed=gen['elapsed'],
        generation_observed_seconds_lower_bound=last['elapsed']-gen['elapsed'],external_wall_seconds=result['wall_seconds'],deadline_seconds=120,state=result['state'],
        forward_entries_observed=sum(v['event']=='forward_start' for v in events),forward_returns_observed=sum(v['event']=='forward_end' for v in events),
        prompt_stream_callback_observed=any(v['event']=='prompt_observed' for v in events),streamed_generated_tokens=max([v.get('tokens',0) for v in events if v['event']=='tokens_observed'] or [0]),
        returned_generated_token_count=None,raw_returned_latex=None,cleaned_latex=None,completion_correctness=None,partial_output_available=(native/'progress.json').exists(),
        observed_location=progress_status(events),cause='UNKNOWN; no stack/profile/return establishes exact internal cause. Observations do not measure prefill or decoding throughput.',
        sampled_kernel_memory_peak_bytes=max(int(v['memory.peak']) for v in samples),exact_final_peak_bytes=None,
        cpu_seconds_to_last_sample=cpu['usage_usec']/1e6,average_cores=cpu['usage_usec']/1e6/last['elapsed'],last_memory_events=last['memory.events'],
        kernel_limits={k:last[k] for k in ['memory.max','memory.swap.max','cpu.max']},controller_errors=result['controller_errors'],
        input_crop_sha256='9b9b3cccafa6e482c591d1ad81c52c4d7daade04b5e63a730af286b8508c1e9d',
        model_revision='ecedbe111d15c2dc60bfd4a823cbe80127b58af4',instrumentation='Delegating forward hooks and an official token streamer; no logits, weights, preprocessing, repetition settings or decoder sampling changed.')
    write(out/'codeformula-diagnostic.json',diagnostic)
    metadata=raw/'pp-metadata';model=json.loads((metadata/'model.json').read_text());required=['inference.json','inference.pdiparams','inference.yml'];model_bytes=sum(v['size'] for v in model['siblings'] if v['rfilename'] in required)
    snapshot=json.loads((raw/'current-allocation.json').read_text())
    model_rounded=sum(((v['size']+4095)//4096)*4096 for v in model['siblings'] if v['rfilename'] in required)
    linux_names=['paddle-linux','opencv-linux','numpy-linux','paddlex','modelscope','aiohttp-linux','paddleocr'];mac_names=['paddle','opencv','numpy']
    def parts(names):return [json.loads((metadata/(n+'-wheel-zip.json')).read_text()) for n in names]
    linux,mac=parts(linux_names),parts(mac_names)
    budget=dict(schema_version='pp-formulanet-admission.1',cap_bytes=CAP,host_reserve_bytes=12*1024**3,host_available_bytes=snapshot['host_available_bytes'],
        model_repo='PaddlePaddle/PP-FormulaNet-S',model_revision=model['sha'],minimal_runtime_files=required,model_bytes=model_bytes,
        linux=budget_plan(snapshot,linux,model_bytes,model_rounded),macos=budget_plan(snapshot,mac,model_bytes,model_rounded),
        planned_versions={'paddlepaddle':'3.3.1','paddleocr':'3.7.0','paddlex':'3.7.2','opencv-contrib-python':'4.10.0.84','numpy':'2.3.5','modelscope':'1.40.3','aiohttp':'3.13.2'},
        reused_linux_dependencies='Optimistically assumes other compatible dependencies reusable read-only; existing numpy2.4.6 violates PaddleX<2.4 and existing opencv-python-headless5.0 does not satisfy opencv-contrib4.10. No existing environment changed.',
        linux_cpu_runtime_available=True,linux_runtime_evidence='Official CPU index publishes cp311 linux_aarch64 wheel; absence from PyPI is not absence from official vendor index.',
        installed_abi_operator_compatibility='UNKNOWN; no acquisition/import',native_macos_measurements=None,native_macos_enforcement='NOT_EXECUTED; no claim of Linux-equivalent cgroups/swap enforcement',
        pp_weights_acquired=False,pp_runtime_installed=False,pp_candidate_invocations=0,
        runtime_wheel_metadata=[{k:v for k,v in r.items() if k not in {'entries','largest_members'}} for r in linux+mac])
    assert budget['linux']['admission']=='FAIL' and budget['macos']['admission']=='FAIL'
    write(out/'pp-admission.json',budget)
    selection=json.loads((FORMULA/'selection.json').read_text())['expressions'];predictions=[]
    for row in selection:
        predictions.append(dict(id=row['id'],pdf_sha256=row['pdf_sha256'],page=row['page'],source_target_bbox=row['target_bbox'],
            input_crop_identity='Frozen PR24 crop; first exact SHA verified in diagnostic',pp_status='NOT_EXECUTED_STORAGE_ADMISSION_FAIL',pp_raw_latex=None,
            exact_match=None,formatting_normalized_match=None,numerator_denominator=None,radical_scope=None,scripts=None,summations=None,grouping_symbols=None,
            full_expression_correct=None,processing_seconds=None,process_memory=None,reason='Candidate not acquired/installed; no prediction to score. Incomplete and unexecuted are not incorrect mathematics.'))
    write(out/'predictions.json',dict(schema_version='formula-crop-comparison-predictions.1',codeformula_latency=diagnostic,pp_predictions=predictions,full_document_detection=False))
    write(out/'results.json',dict(schema_version='formula-crop-comparison-results.1',reference_status='agent_visual_checked',human_verified_count=0,
        pp_selected=8,pp_attempted=0,pp_completed=0,pp_unexecuted=8,quality_scoreable=0,mathematical_accuracy=None,
        codeformula_diagnostic_invocations=1,codeformula_complete_diagnostic_returns=0,codeformula_diagnostics_pooled_with_2048_accuracy=False,
        codeformula_vs_pp_mathematical_comparison=None,recommendation='Stop CodeFormulaV2 tests on this pinned CPU stack; PP-FormulaNet-S remains unmeasured because the selected official runtime plans fail the storage gate. No quality winner or Formula Structure v0 justification.',
        reconstructed_images=None,images_reason='No returned LaTeX; never render a reference as if it were a model prediction.'))
    write(out/'pp-model-inventory.json',dict(repo=model['id'],revision=model['sha'],declared_license=model.get('cardData',{}).get('license'),
        files=[dict(file=v['rfilename'],bytes=v['size'],expected_sha256=v.get('lfs',{}).get('sha256'),git_blob_sha1=v['blobId'],
                    url=f"https://huggingface.co/PaddlePaddle/PP-FormulaNet-S/resolve/{model['sha']}/{v['rfilename']}",payload_acquired=v['rfilename']=='README.md',
                    actual_sha256=hashlib.sha256((metadata/'model-card.md').read_bytes()).hexdigest() if v['rfilename']=='README.md' else None) for v in model['siblings']],
        model_card_only_verified=True,weights_verified=False))
    return diagnostic,budget


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d,b=collect(a.raw,a.out)
    print(json.dumps(dict(diagnostic=d,linux_plan=b['linux'],macos_plan=b['macos']),indent=2))
