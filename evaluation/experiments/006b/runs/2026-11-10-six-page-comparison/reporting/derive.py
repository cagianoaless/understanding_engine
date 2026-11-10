"""Algebraic reporting only: no prediction, adaptation, matching or inference.

Consumes the already frozen per-page scores. Added after predictions/scoring;
cannot change their decisions. Produces supplemental document macro measures,
explicit fractions and resource summaries in a NEW output directory.
"""

import argparse
import json
from pathlib import Path
import statistics


def fraction(n, d):
    return {'numerator': n, 'denominator': d, 'value': n/d if d else None,
            'undefined_reason': None if d else 'zero frozen denominator'}


def derive(raw, output):
    summary = json.loads((raw/'comparison/summary.json').read_text())
    frozen = json.loads((raw/'predictions-frozen.json').read_text())
    output.mkdir(exist_ok=False)
    for engine, entry in summary['engines'].items():
        docs, macro = entry['documents'], entry['document_macro']
        measures = {'order_correct_fraction': lambda d: d['order_correct_fraction'],
                    'paragraph_accuracy': lambda d: d['paragraph_accuracy'],
                    'paragraph_coverage': lambda d: d['paragraph_coverage'],
                    'unique_geometric_grounding': lambda d: d['grounding_window_counts']['valid']/d['grounding_window_characters'] if d['grounding_window_characters'] else None}
        for label in sorted(entry['micro']['classification']):
            for metric in ['precision', 'recall', 'f1']:
                measures[label+'_'+metric] = lambda d, label=label, metric=metric: d['classification'].get(label, {}).get(metric)
        for name, function in measures.items():
            values = {k: function(d) for k, d in docs.items()}
            valid = [v for v in values.values() if v is not None]
            macro[name] = {'value': statistics.mean(valid) if valid else None,
                'defined_documents': len(valid), 'all_documents': len(docs), 'document_values': values,
                'undefined_reason': None if len(valid) == len(docs) else 'Undefined document denominators are null and listed; never silently zero-filled'}
        for group in [entry['micro'], *docs.values(), *entry['layouts'].values()]:
            group['order_accuracy_full_denominator'] = fraction(group['order']['correct'], group['order_denominator'])
            group['order_scoreable_coverage'] = fraction(group['order_denominator']-group['order']['unscoreable'], group['order_denominator'])
            group['paragraph_accuracy_full_denominator'] = fraction(group['paragraph_correct'], group['paragraph_denominator'])
            group['paragraph_coverage_full_denominator'] = fraction(group['paragraph_scoreable'], group['paragraph_denominator'])
            group['grounding_unique_fraction'] = fraction(group['grounding_window_counts']['valid'], group['grounding_window_characters'])
            group['classification_micro'] = {k: sum(x[k] for x in group['classification'].values()) for k in ['tp', 'fp', 'fn']}
        entry['native_source_traceability'] = {
            'pages_with_all_original_ids_exactly_once': sum(p['grounding_whole_page'].get('native_ids_once') is True for p in entry['page_results']) if engine == 'structure' else None,
            'page_denominator': 6, 'reason': None if engine == 'structure' else 'Docling exposes no original-character crosswalk; geometry adapter is a separate association',
            'all_source_character_count': sum(p['grounding_whole_page']['source_characters'] for p in entry['page_results'])}
    summary['baseline_environment_note'] = 'Original code/parameters unchanged; Linux jsonschema4.26.0 reused. All six full-page structural decisions, geometry, source IDs and Unicode exactly equivalent to original host jsonschema4.25.1 after excluding only environment-derived structure ID prefixes. Both native outputs retained.'
    summary['scientific_claim'] = 'Provisional six-page development comparison with zero human verification; no superiority or generalization established.'
    summary['supplementary_aggregation'] = 'Document macros and explicit fractions are algebraic summaries of immutable raw page scores; no predictions, mappings, references, matches or scoring decisions changed.'
    resources = {'schema_version': '006b.stage-d-resources.1', 'per_page': [], 'engines': {},
        'scope': 'Fresh measured Linux container/cgroup per candidate/page. Frozen full-cache validation/serialization included for baseline; original-PDF selected-page conversion for Docling. Host equivalence checks excluded from comparative cost, included in retained evidence/storage. Filesystem caches warm; no warm-repeat inference.'}
    for x in frozen['executions']:
        e = x['execution']; initial, final = e['initial_cgroup'], e['final_cgroup']
        parse = lambda text: {k: int(v) for k, v in (line.split() for line in text.splitlines())}
        cpu = parse(final['cpu.stat'])['usage_usec']-parse(initial['cpu.stat'])['usage_usec']
        seconds = e.get('total_wall_seconds', e.get('process_seconds'))
        path = raw/x['output_relative_path']
        resources['per_page'].append({'engine': x['engine'], 'page_id': x['page_id'], 'status': e['status'],
            'exit_code': x['resource']['exit_code'], 'timeout': x['resource']['timeout'],
            'external_seconds': x['resource']['external_wall_seconds'], 'process_seconds': seconds,
            'conversion_or_reconstruction_seconds': e.get('conversion_wall_seconds', e.get('reconstruction_validation_serialization_seconds')),
            'cgroup_peak_bytes': int(final['memory.peak']), 'cpu_seconds': cpu/1e6,
            'average_cpu_percent_one_core': cpu/1e6/seconds*100, 'initial_cgroup': initial, 'final_cgroup': final,
            'native_output_bytes': sum(p.stat().st_size for p in path.rglob('*') if p.is_file()),
            'adapter_seconds': next(p['adapter_seconds'] for p in summary['engines'][x['engine']]['page_results'] if p['page_id'] == x['page_id']),
            'model_prediction_batches': e.get('model_prediction_batches'),
            'effective_computation_threads': e.get('torch_threads', e.get('effective_computation_threads')),
            'torch_interop_threads': e.get('torch_interop_threads'), 'pure_initialization_seconds': None,
            'initialization_reason': 'Not separately instrumented; conversion includes lazy model/pipeline initialization and PDF processing',
            'warm_repeat_seconds': None, 'warm_repeat_reason': 'No extra inference or warm repetitions performed'})
    for engine in summary['engines']:
        rows = [x for x in resources['per_page'] if x['engine'] == engine]
        resources['engines'][engine] = {'external_total_seconds': sum(x['external_seconds'] for x in rows),
            'external_mean_seconds': statistics.mean(x['external_seconds'] for x in rows),
            'external_min_seconds': min(x['external_seconds'] for x in rows), 'external_max_seconds': max(x['external_seconds'] for x in rows),
            'max_cgroup_peak_bytes': max(x['cgroup_peak_bytes'] for x in rows), 'cpu_total_seconds': sum(x['cpu_seconds'] for x in rows),
            'native_output_total_bytes': sum(x['native_output_bytes'] for x in rows),
            'adapter_total_seconds': sum(x['adapter_seconds'] for x in rows), 'pages': 6, 'timeouts': sum(x['timeout'] for x in rows)}
    resources.update(guest_before=frozen['guest_before'], guest_after=frozen['guest_after'], historical_provisioning_peak='UNKNOWN')
    for name, data in [('summary.json', summary), ('resources.json', resources)]:
        with (output/name).open('x') as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    derive(args.raw, args.output)
