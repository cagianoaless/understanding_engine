"""Offline authored UI/API fixtures, not formula recognition accuracy."""
from copy import deepcopy
import base64
import hashlib
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import threading

import pytest

from understanding_engine.contracts import ExtractionError, json_bytes
from understanding_engine.formula_structure import parse_formula
from understanding_engine.viewer import DocumentContext, LocalServer
from understanding_engine.viewer_formula import FormulaDemo
from understanding_engine.viewer_formula_assets import JS
from evaluation.local_pdf_viewer_v0.fixtures import create


@pytest.fixture
def inputs(tmp_path):
    paths,manifest,source,hybrid=create(tmp_path/'inputs')
    provenance=dict(pdf_sha256=source['source_sha256'],page_number=1,bbox=[18,48,110,86],
                    coordinate_system='pdfplumber-native-v1',crop_sha256='b'*64,model_name='authored-fixture',
                    model_revision='fixture',prediction_id='authored',prediction_record_sha256='c'*64,
                    prediction_artifact_sha256='d'*64)
    graph=parse_formula(r'𝛼=\frac{x_{i}}{\sqrt{y}}',provenance,termination='complete')
    path=tmp_path/'graph.json';path.write_bytes(json_bytes(graph))
    fm={'schema_version':'local-formula-demo-inputs.1','graph':{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
    return paths,manifest,source,hybrid,path,fm,graph


@pytest.fixture
def context(inputs):
    paths,m,_,_,graph,fm,_=inputs
    ctx=DocumentContext(**paths,manifest=m,initial_page=None,formula_graph=graph,formula_manifest=fm)
    ctx.start();ctx._thread.join(timeout=10)
    assert ctx.state=='ready',ctx.error
    yield ctx
    ctx.close()


@pytest.fixture
def server(context):
    s=LocalServer(context);thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
    yield s
    s.shutdown();s.server_close();thread.join()


def request(server,path,body=None,headers=None):
    connection=http.client.HTTPConnection(*server.server_address,timeout=5)
    hs={'Authorization':'Bearer '+server.token,'Origin':server.origin}
    hs.update(headers or {})
    payload=None if body is None else json_bytes(body)
    if payload is not None:hs['Content-Type']='application/json'
    connection.request('GET' if body is None else 'POST',path,body=payload,headers=hs)
    response=connection.getresponse();r=response.status,dict(response.getheaders()),response.read();connection.close();return r


def node_query(context,node_id):
    return dict(pdf_sha256=context.manifest['pdf']['sha256'],source_canonical_sha256=context.hybrid['source_canonical_sha256'],
                formula_id=context.formula.graph['id'],node_id=node_id)


def test_identity_bound_graph_and_exact_node_navigation(context,server):
    status,_,data=request(server,'/api/formula');assert status==200
    payload=json.loads(data);g=payload['graph']
    assert context.status()['formula_demo'] and context.initial_page==1
    assert g['provenance']['pdf_sha256']==context.manifest['pdf']['sha256']
    fraction=next(n for n in g['nodes'] if n['type']=='fraction')
    nodes={n['id']:n for n in g['nodes']}
    for edge in fraction['children']:
        status,_,data=request(server,'/api/formula/node',node_query(context,edge['node_id']))
        selected=json.loads(data);assert status==200
        assert selected['node']==nodes[edge['node_id']]
        a,b=selected['node']['character_span']
        assert selected['latex_substring']==g['input']['latex'][a:b]
        assert selected['pdf_overlay']=='whole_formula_crop_only'
        assert 'bbox' not in selected['node'] and 'pdf_bbox' not in selected
        assert request(server,'/api/formula/node',node_query(context,edge['node_id']))[2]==data


@pytest.mark.parametrize('damage',['pdf','page','bbox','tokens'])
def test_mismatched_or_corrupt_graph_rejected(inputs,damage):
    _,_,source,_,_,_,original=inputs
    p=deepcopy(original['provenance'])
    if damage=='pdf':p['pdf_sha256']='0'*64
    elif damage=='page':p['page_number']=3
    elif damage=='bbox':p['bbox']=[0,0,201,200]
    g=parse_formula(original['input']['latex'],p,termination='complete')
    if damage=='tokens':g['nodes'][0]['source_text']='invented'
    with pytest.raises(ExtractionError):FormulaDemo(g,source)


def test_manifest_hash_and_graph_symlink_rejected(inputs,tmp_path):
    paths,m,_,_,path,fm,_=inputs
    for candidate,identity in [(path,{**fm,'graph':{**fm['graph'],'sha256':'0'*64}}),(tmp_path/'link',fm)]:
        if candidate!=path:candidate.symlink_to(path)
        ctx=DocumentContext(**paths,manifest=m,initial_page=1,formula_graph=candidate,formula_manifest=identity)
        ctx.start();ctx._thread.join(timeout=10)
        try:assert ctx.state=='failed'
        finally:ctx.close()


@pytest.mark.parametrize('field,value',[('node_id','missing'),('node_id',None),('formula_id','wrong'),('pdf_sha256','0'*64),('source_canonical_sha256','0'*64),('path','/etc/passwd')])
def test_invalid_node_and_identity_are_not_silently_substituted(context,server,field,value):
    query=node_query(context,context.formula.graph['root_id']);query[field]=value
    assert request(server,'/api/formula/node',query)[0]==400


@pytest.mark.parametrize('path',['/api/formula','/api/formula/node'])
@pytest.mark.parametrize('headers',[{'Authorization':'Bearer wrong'},{'Origin':'https://example.invalid'},{'Host':'attacker.invalid'},{'Sec-Fetch-Site':'cross-site'}])
def test_formula_routes_keep_authorization_origin_and_host_boundaries(context,server,path,headers):
    body=node_query(context,context.formula.graph['root_id']) if path.endswith('node') else None
    status,hs,_=request(server,path,body,headers)
    assert status==403 and 'Access-Control-Allow-Origin' not in hs


def test_formula_graph_validated_once_outside_queries(inputs,monkeypatch):
    import understanding_engine.viewer_formula as formula
    original=formula.validate_formula_structure;calls=[]
    def validate(g):calls.append(1);return original(g)
    monkeypatch.setattr(formula,'validate_formula_structure',validate)
    paths,m,_,_,graph,fm,_=inputs
    ctx=DocumentContext(**paths,manifest=m,initial_page=1,formula_graph=graph,formula_manifest=fm)
    ctx.start();ctx._thread.join(timeout=10)
    try:
        assert ctx.state=='ready'
        for _ in range(3):
            ctx.formula_payload();ctx.formula_node(node_query(ctx,ctx.formula.graph['root_id']))
        assert calls==[1]
    finally:ctx.close()


def test_partial_rejected_graph_and_diagnostics_preserved(inputs):
    _,_,source,_,_,_,g=inputs
    rejected=parse_formula(r'x=\frac{y}{',g['provenance'],termination='incomplete')
    demo=FormulaDemo(rejected,source)
    payload=demo.payload();assert payload['graph']['status']['acceptance']=='reject'
    root=demo.node(rejected['root_id'])
    assert root['node']['status']=='unresolved'
    assert root['whole_expression_status']['parsing']=='partial'
    assert payload['graph']['diagnostics'] and root['node']['children']
    payload['graph']['input']['latex']='changed'
    assert demo.payload()['graph']['input']['latex']==rejected['input']['latex']


def test_original_viewer_mode_remains_source_selection_only(inputs):
    paths,m,_,_,_,_,_=inputs
    ctx=DocumentContext(**paths,manifest=m,initial_page=1);ctx.start();ctx._thread.join(timeout=10)
    s=LocalServer(ctx);thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
    try:
        assert ctx.state=='ready' and 'formula_demo' not in ctx.status()
        assert request(s,'/api/formula')[0]==404
        assert request(s,'/api/formula/node',{'node_id':'anything'})[0]==404
        assert request(s,'/api/page/1')[0]==200
    finally:s.shutdown();s.server_close();thread.join();ctx.close()


def test_code_point_substrings_use_complete_non_bmp_characters():
    node=shutil.which('node')
    if node is None:pytest.skip('No existing Node for JavaScript-only span test')
    url='data:text/javascript;base64,'+base64.b64encode(JS.encode()).decode()
    script='const {latexSlices}=await import(process.argv[1]); const s="𝛼+x";console.log(JSON.stringify([latexSlices(s,[0,1]),latexSlices(s,[2,3])]));'
    result=json.loads(subprocess.check_output([node,'--input-type=module','-e',script,url],text=True))
    assert result==[dict(before='',selected='𝛼',after='+x'),dict(before='𝛼+',selected='x',after='')]
    for span in [[-1,1],[0,4],[2,1],[0.5,1]]:
        fail='const {latexSlices}=await import(process.argv[1]);latexSlices("𝛼+x",JSON.parse(process.argv[2]));'
        assert subprocess.run([node,'--input-type=module','-e',fail,url,json.dumps(span)],capture_output=True).returncode!=0


def test_fixed_assets_keep_csp_and_no_untrusted_html(server):
    status,headers,body=request(server,'/formula-explorer.js')
    assert status==200 and b'latexSlices' in body
    assert 'innerHTML' not in JS and 'insertAdjacentHTML' not in JS and 'eval(' not in JS
    assert "script-src 'self'" in headers['Content-Security-Policy']
    assert "connect-src 'self'" in headers['Content-Security-Policy']
    for path in ['/api/formula?path=/etc/passwd','/api/formula/../../etc/passwd','/api/formula/node/file']:
        assert request(server,path)[0]==404


def test_source_only_preparation_reuses_extraction_without_parsing(inputs,tmp_path,monkeypatch):
    import sys
    import understanding_engine.pdf_parser as parser
    from evaluation.formula_explorer_v0.prepare import prepare
    paths,m,source,_,g,fm,_=inputs
    def forbidden(*a,**k):raise AssertionError('No real PDF re-extraction permitted')
    monkeypatch.setattr(parser,'extract_pdf',forbidden)
    identity={'schema_version':'formula-explorer-source-inputs.1','pdf':m['pdf'],'extraction':m['extraction'],'graph':fm['graph']}
    output=tmp_path/'prepared'
    result=prepare(paths['pdf'],paths['extraction'],g,identity,output)
    assert result['pdf_extraction_calls']==0 and result['neural_calls']==0
    hybrid=json.loads((output/'source-only-hybrid.json').read_text())
    assert hybrid['source']==source and hybrid['hypotheses']==[]
    assert hybrid['source_only_pages']==[1,2]
    assert not {'torch','paddle','transformers'} & set(sys.modules)
    with pytest.raises(FileExistsError):prepare(paths['pdf'],paths['extraction'],g,identity,output)
    assert json.loads((output/'source-only-hybrid.json').read_text())==hybrid
