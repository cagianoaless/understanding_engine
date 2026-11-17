"""Reproduce eight-prediction syntax evaluation offline; references never enter parsing."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
import time

from understanding_engine.contracts import json_bytes
from understanding_engine.formula_structure import ParseSettings, parse_formula
from understanding_engine.formula_structure_contract import validate_formula_structure

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'evaluation/experiments/formula_recognition_v0/runs/2026-11-16-t4-crops'
PP = ROOT / 'evaluation/experiments/formula_recognition_v0/runs/2026-11-16-pp-research-server'
LOGGER = logging.getLogger(__name__)


def publish(destination, artifacts):
    """Same sibling-lock/staging policy as output.py, without PDF extraction."""
    destination = Path(destination).absolute()
    lock = destination.with_name('.' + destination.name + '.lock')
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    staging = None
    try:
        if os.path.lexists(destination):
            raise FileExistsError('Choose a new output directory')
        staging = Path(tempfile.mkdtemp(prefix='.' + destination.name + '.staging-', dir=destination.parent))
        for name, content in artifacts.items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Artifact path escapes staging')
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        if os.path.lexists(destination):
            raise FileExistsError('Output appeared during publication')
        os.rename(staging, destination)
        staging = None
    finally:
        if staging is not None:
            try:
                shutil.rmtree(staging)  # Only our own freshly created temporary tree.
            except OSError:
                LOGGER.warning('Hidden experiment staging could not be removed')
        try:
            lock.unlink()
        except OSError:
            LOGGER.warning('Experiment sibling lock could not be removed')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def termination(record):
    calls = record['generated_calls']
    if not calls:
        return 'unknown'
    return 'complete' if all(c['last_token_id'] == c['eos_token_id'] and not c['token_cap_reached'] for c in calls) else 'incomplete'


def parse_inputs(records, artifact_sha256):
    """No annotations, scores, reference text or PP output are arguments."""
    results, timings = [], []
    for record in records:
        original = record['input']
        if (record['status'] != 'RETURNED' or record['backend_fallback_possible'] or
                original['sha256'] != record['input_crop_sha256'] or
                record['model_revision'] != 'ecedbe111d15c2dc60bfd4a823cbe80127b58af4'):
            raise ValueError('Original prediction identity/status differs')
        provenance = dict(pdf_sha256=original['pdf_sha256'], page_number=original['page'], bbox=original['bbox'],
                          coordinate_system='pdfplumber-native-v1', crop_sha256=original['sha256'],
                          model_name='docling-project/CodeFormulaV2', model_revision=record['model_revision'],
                          prediction_id=record['id'], prediction_record_sha256=hashlib.sha256(json_bytes(record)).hexdigest(),
                          prediction_artifact_sha256=artifact_sha256)
        start = time.perf_counter()
        result = parse_formula(record['cleaned_latex'], provenance,
                               raw_model_output=record['raw_model_output'], termination=termination(record))
        elapsed = time.perf_counter() - start
        validate_formula_structure(result)
        results.append(result)
        timings.append(dict(id=record['id'], parse_seconds=elapsed, serialized_bytes=len(json_bytes(result))))
    return results, timings


def run(destination):
    freeze = json.loads((HERE / 'freeze.json').read_text())
    for name, digest in freeze['files_sha256'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('Frozen implementation/input differs: ' + name)
    if asdict(ParseSettings()) != freeze['settings']:
        raise ValueError('Frozen settings differ')
    baseline = json.loads((BASE / 'predictions.json').read_text())
    records = baseline['codeformula']
    if [r['id'] for r in records] != freeze['prediction_ids'] or len(records) != 8:
        raise ValueError('Frozen eight-record order/denominator differs')
    outputs, timings = parse_inputs(records, sha(BASE / 'predictions.json'))
    # Only after all candidate outputs exist do we inspect earlier review labels.
    review = {r['id']: r for r in json.loads((BASE / 'adjudications.json').read_text())['expressions']}
    pp_review = json.loads((PP / 'results.json').read_text())
    rows = []
    for result in outputs:
        identifier = result['provenance']['prediction_id']
        rows.append(dict(id=identifier, formula_id=result['id'], status=result['status'],
                         termination=result['input']['termination'],
                         node_types=dict(Counter(n['type'] for n in result['nodes'])),
                         unresolved_nodes=sum(n['status'] == 'unresolved' for n in result['nodes']),
                         identifier_grouping_ambiguities=sum(d['code'] in {'ambiguous_identifier_or_numeric_sequence','text_name_not_verified_identifier'} for d in result['diagnostics']),
                         diagnostics=[d['code'] for d in result['diagnostics']],
                         provisional_source_full_expression_correct=review[identifier]['full_expression_correct'],
                         mathematical_correctness='unverified', source_alignment='formula_crop_only'))
    summary = dict(schema_version='formula-structure-evaluation.1', selected_denominator=8,
                   parsing_counts=dict(Counter(r['status']['parsing'] for r in rows)),
                   acceptance_counts=dict(Counter(r['status']['acceptance'] for r in rows)),
                   unresolved_nodes=sum(r['unresolved_nodes'] for r in rows),
                   identifier_grouping_ambiguities=sum(r['identifier_grouping_ambiguities'] for r in rows),
                   structural_node_counts=dict(Counter(n['type'] for out in outputs for n in out['nodes'])),
                   components_role='Syntax recovered from hypotheses, including explicitly retained partial fragments; not source-verified mathematical accuracy',
                   mathematically_unverified=8, symbol_aligned_to_original_pdf=0,
                   reference_status='agent_visual_checked', independent_human_verifications=0,
                   reference_discrepancy='Original Nature alpha-versus-a conflict preserved; not corrected or loaded by parse_inputs',
                   pp_comparison_only=dict(predictions_sha256=sha(PP / 'predictions.json'), results_sha256=sha(PP / 'results.json'),
                                           full_expression=pp_review['pp_full_expression'], parsed=False, ensemble=False),
                   per_formula=rows)
    artifacts = {}
    for result in outputs:
        artifacts['examples/' + result['provenance']['prediction_id'] + '.json'] = json_bytes(result)
    artifacts['results.json'] = json_bytes(summary)
    artifacts['run.json'] = json_bytes(dict(schema_version='formula-structure-run.1', timings=timings,
                                          timing_scope='One local run, parser only; excludes file loading and validation; no scalability claim'))
    publish(destination, artifacts)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    result = run(parser.parse_args().output)
    print(json.dumps({k: result[k] for k in ['selected_denominator','parsing_counts','acceptance_counts','unresolved_nodes','identifier_grouping_ambiguities']}))
