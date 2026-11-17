"""Verify retained inputs; derive a labelled source-only hybrid, no PDF extraction."""
import argparse
import hashlib
import json
from pathlib import Path

from understanding_engine.contracts import json_bytes
from understanding_engine.hybrid import build_hybrid
from understanding_engine.viewer import verified_bytes
from understanding_engine.viewer_formula import FormulaDemo, MAX_GRAPH_BYTES
from evaluation.experiments.formula_structure_v0.evaluate import publish


def prepare(pdf, extraction, graph, identity, destination):
    if set(identity) != {'schema_version','pdf','extraction','graph'} or identity['schema_version'] != 'formula-explorer-source-inputs.1':
        raise ValueError('Unexpected source-input manifest')
    pdf_data = verified_bytes(pdf, identity['pdf'], 64*1024**2)
    source_data = verified_bytes(extraction, identity['extraction'], 128*1024**2)
    graph_data = verified_bytes(graph, identity['graph'], MAX_GRAPH_BYTES)
    source = json.loads(source_data)
    if source['source_sha256'] != hashlib.sha256(pdf_data).hexdigest():
        raise ValueError('Original PDF/source identity differs')
    FormulaDemo(json.loads(graph_data), source)
    hybrid = build_hybrid(source, [])
    hybrid_data = json_bytes(hybrid)
    manifest = {'schema_version':'local-viewer-inputs.1', 'pdf':identity['pdf'], 'extraction':identity['extraction'],
                'hybrid':{'bytes':len(hybrid_data),'sha256':hashlib.sha256(hybrid_data).hexdigest()}}
    formula_manifest = {'schema_version':'local-formula-demo-inputs.1','graph':identity['graph']}
    local = {'pdf':str(Path(pdf).absolute()),'extraction':str(Path(extraction).absolute()),
             'hybrid':str(Path(destination).absolute()/'source-only-hybrid.json'),
             'manifest':str(Path(destination).absolute()/'viewer-manifest.json'),
             'formula_graph':str(Path(graph).absolute()),
             'formula_manifest':str(Path(destination).absolute()/'formula-manifest.json')}
    provenance = {'schema_version':'formula-demo-preparation.1','basis':'Existing deterministic extraction, existing build_hybrid(source, [])',
                  'source_only':True,'new_layout_predictions':0,'pdf_extraction_calls':0,'neural_calls':0,
                  'original_identities':identity,'new_hybrid':manifest['hybrid']}
    publish(destination, {'source-only-hybrid.json':hybrid_data, 'viewer-manifest.json':json_bytes(manifest),
                          'formula-manifest.json':json_bytes(formula_manifest), 'launch.local.json':json_bytes(local),
                          'preparation.json':json_bytes(provenance)})
    return provenance


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['pdf','extraction','graph','identity','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    result = prepare(args.pdf,args.extraction,args.graph,json.loads(args.identity.read_text()),args.output)
    print(json.dumps(result))
