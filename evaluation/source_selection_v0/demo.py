"""Source-selection measurements, not model/quality evaluation. No inference."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import runpy
import statistics
import time

from understanding_engine.contracts import json_bytes
from understanding_engine.hybrid import build_hybrid, _center
from understanding_engine.pdf_parser import extract_pdf
from understanding_engine.selection import SelectionIndex
from understanding_engine.structure import _box as character_union_box

REPO = Path(__file__).resolve().parents[2]
PUBLISH = runpy.run_path(str(REPO/'evaluation/hybrid_v0/demo.py'))['publish']
FRAME = 'pdfplumber-native-v1'


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def measure(index, name, query, repeats):
    start = time.perf_counter(); result = index.select(query); cold = time.perf_counter()-start
    payload = json_bytes(result)
    query_times, serialization_times = [], []
    for _ in range(repeats):
        start = time.perf_counter(); current = index.select(query); query_times.append(time.perf_counter()-start)
        start = time.perf_counter(); data = json_bytes(current); serialization_times.append(time.perf_counter()-start)
        assert data == payload, 'Selection changed under identical input'
    return result, {'name': name, 'query': query, 'response_bytes': len(payload), 'response_sha256': sha(payload),
        'selected_source_units': len(result['characters']), 'structural_candidates': sum(len(h['regions']) for h in result['hypotheses']),
        'first_query_seconds': cold, 'repeats': repeats, 'warm_query_seconds': query_times,
        'warm_query_median_seconds': statistics.median(query_times), 'warm_query_max_seconds': max(query_times),
        'serialization_seconds': serialization_times, 'serialization_median_seconds': statistics.median(serialization_times),
        'deterministic': True}


def synthetic(directory):
    from reportlab.pdfgen import canvas

    path = directory/'authored-selection.pdf'
    pdf = canvas.Canvas(str(path), pagesize=(200, 200), invariant=1)
    pdf.setFont('Helvetica', 10); pdf.drawString(20, 120, 'AB'); pdf.drawString(120, 70, 'CD'); pdf.save()
    source = extract_pdf(path)
    def item(i, label, bbox, text):
        return {'self_ref': f'#/texts/{i}', 'parent': {'$ref': '#/body'}, 'children': [], 'label': label, 'text': text,
                'prov': [{'page_no': 1, 'bbox': dict(zip(['l','t','r','b'],bbox),coord_origin='TOPLEFT'), 'charspan': [0, 0]}]}
    native = {'body': {'self_ref': '#/body','label':'unspecified','children':[{'$ref':'#/texts/0'},{'$ref':'#/texts/1'}]},
              'furniture': {'self_ref':'#/furniture','label':'unspecified','children':[]},
              'texts':[item(0,'formula',[0,60,190,150],''), item(1,'picture',[0,0,40,40],None)],
              'pages':{'1':{'page_no':1,'size':{'width':200,'height':200}}}}
    p = {'provider':'docling','version':'2.148.0','source_pdf_sha256':source['source_sha256'],'status':'available',
         'native':{'document':native,'items':None},'provenance':{'basis':'authored synthetic fixture; no inference'},'error':None}
    return source, build_hybrid(source,[p])


def main(args):
    assert args.repeats >= 1 and args.repeats <= 100
    assert args.work.is_dir() and not args.output.exists()
    records = json.loads((REPO/'evaluation/hybrid_v0/evidence-manifest.json').read_text())['records']
    expected_hybrid = next(r for r in records if r['path']=='hybrid.json')
    expected_source = json.loads((REPO/'evaluation/hybrid_v0/demonstration.json').read_text())['inputs'][0]
    inputs = []
    def load(path, expected):
        assert path.is_file() and not path.is_symlink()
        data = path.read_bytes(); assert len(data)==expected['bytes'] and sha(data)==expected['sha256']
        inputs.append({'bytes':len(data),'sha256':sha(data)})
        return json.loads(data)
    hybrid = load(args.hybrid_root/'hybrid.json',expected_hybrid)
    source = load(args.source_root/'sources/bert-extraction.json',expected_source)
    summary = {'schema_version':'source-selection-demo.1','python':platform.python_version(),
        'system':platform.system(),'architecture':platform.machine(),'input_records':inputs,
        'new_inference_calls':0,'frozen_labels_loaded':False,'benchmark_scores_loaded':False,
        'quality_metrics_claimed':False,'measurements':[],'contexts':{}}
    output = {}
    for scope,s,h,number in [('synthetic',*synthetic(args.work),1),('retained_bert',source,hybrid,6)]:
        begin=time.perf_counter(); index=SelectionIndex(h,s,expected_pdf_sha256=s['source_sha256']); initialization=time.perf_counter()-begin
        page=s['pages'][number-1]; chosen=page['characters'][:5]
        summary['contexts'][scope]={'validation_and_index_constructor_seconds':initialization,
            'source_document_pages':len(s['pages']),'query_page':number,'query_page_characters':len(page['characters']),
            'query_page_regions':sum(r['page_number']==number for e in h['hypotheses'] for r in e['regions']),
            'lookup':'Lazy per-page maps, linear geometry scans; no spatial tree; borrowed immutable input'}
        queries=[('explicit_units',{'kind':'character_ids','page_number':number,'character_ids':[c['id'] for c in chosen]}),
                 ('unit_rectangle',{'kind':'rectangle','page_number':number,'bbox':character_union_box(chosen),'coordinate_system':FRAME}),
                 ('point',{'kind':'point','page_number':number,'point':list(_center(chosen[0]['bbox'])),'coordinate_system':FRAME})]
        docling=next(e for e in h['hypotheses'] if e['prediction']['provider']=='docling')
        labels={i['native_id']:i for i in docling['items']}
        if scope=='synthetic':
            regions=docling['regions']
        else:
            first_multibox=next(r for r in docling['regions'] if r['native_item_id']=='#/texts/65')
            table=next(r for r in docling['regions'] if labels[r['native_item_id']]['label']=='table')
            paragraph=next(r for r in docling['regions'] if labels[r['native_item_id']]['label']=='text' and labels[r['native_item_id']]['parent_id']=='#/body')
            regions=[first_multibox,table,paragraph]
        for i,r in enumerate(regions):
            queries.append(('region_'+str(i),{'kind':'region','page_number':number,'evidence_id':docling['id'],'region_id':r['id'],'basis':'geometric'}))
        for name,query in queries:
            result, measurement=measure(index,scope+'_'+name,query,args.repeats)
            summary['measurements'].append(measurement)
            output[scope+'_'+name+'.json']=json_bytes(result)
        # Explicit native membership on the existing multi-box Docling item
        # must not fabricate a native crosswalk from its geometric associations.
        if scope=='retained_bert':
            r=index.by_region(number,docling['id'],regions[0]['id'],basis='native')
            assert not r['characters'] and not r['status']['textless_visual']
    output['measurements.json']=json_bytes(summary)
    PUBLISH(args.output,output)
    print(json.dumps({'contexts':summary['contexts'],'results':[{k:r[k] for k in ['name','response_bytes','warm_query_median_seconds','selected_source_units','structural_candidates']} for r in summary['measurements']]},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hybrid-root',type=Path,required=True)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=10)
    main(parser.parse_args())
