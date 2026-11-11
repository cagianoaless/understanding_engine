"""Offline coordinate, renderer, session and integration regressions."""

from copy import deepcopy
import base64
import http.client
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import threading

from PIL import Image
import pytest

from understanding_engine.contracts import ExtractionError
from understanding_engine.viewer import DocumentContext, LocalServer, MAX_BODY
from understanding_engine.viewer_coordinates import browser_to_pdf
from understanding_engine.viewer_assets import COORDINATES_JS

SPEC=importlib.util.spec_from_file_location('viewer_fixtures',Path(__file__).parents[1]/'evaluation/local_pdf_viewer_v0/fixtures.py')
FIXTURES=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(FIXTURES)


@pytest.mark.parametrize('case',['exact','float32','rotation','crop'])
def test_renderer_frame_requires_explicit_numeric_representation(context,case):
    from understanding_engine.viewer import _renderer_geometry, _float32
    geometry=deepcopy(context.source['pages'][0]['geometry'])
    geometry.update(width=595.276,height=841.89)
    box=[0,0,geometry['width'],geometry['height']]
    for key in ['bbox','mediabox','cropbox','raw_mediabox','pdfminer_layout_bbox']:geometry[key]=box[:]
    geometry['raw_cropbox']=None
    actual=[_float32(v) for v in box] if case=='float32' else box
    class RendererPage:
        def get_rotation(self):return 90 if case=='rotation' else 0
        def get_size(self):return actual[2:]
        def get_mediabox(self):return actual
        def get_bbox(self):return actual
        def get_cropbox(self):return [1,0,*actual[2:]] if case=='crop' else actual
    if case in ['exact','float32']:_renderer_geometry(RendererPage(),geometry)
    else:
        with pytest.raises(ExtractionError):_renderer_geometry(RendererPage(),geometry)


@pytest.fixture
def inputs(tmp_path):
    return FIXTURES.create(tmp_path/'inputs')


@pytest.fixture
def context(inputs):
    paths,manifest,_,_=inputs
    ctx=DocumentContext(**paths,manifest=manifest,initial_page=1);ctx.start();ctx._thread.join(timeout=10)
    assert ctx.state=='ready',ctx.error
    yield ctx
    ctx.close()


@pytest.fixture
def server(context):
    instance=LocalServer(context)
    thread=threading.Thread(target=instance.serve_forever,daemon=True);thread.start()
    yield instance
    instance.shutdown();instance.server_close();thread.join()


def request(server,path,body=None,headers=None,method=None):
    c=http.client.HTTPConnection(*server.server_address,timeout=5)
    hs={'Authorization':'Bearer '+server.token,'Origin':server.origin}
    if headers is not None:
        hs.update(headers)
    payload=json.dumps(body).encode() if body is not None else None
    if payload is not None:hs['Content-Type']='application/json'
    c.request(method or ('POST' if body is not None else 'GET'),path,body=payload,headers=hs)
    response=c.getresponse();result=(response.status,dict(response.getheaders()),response.read());c.close();return result


def identity(ctx):
    return {'pdf_sha256':ctx.manifest['pdf']['sha256'],'source_canonical_sha256':ctx.hybrid['source_canonical_sha256']}


@pytest.mark.parametrize('scale',[.5,1,1.25,2])
def test_coordinate_mapping_round_trip_and_css_overlay(context,scale):
    g=context.source['pages'][0]['geometry'];box=context.source['pages'][0]['characters'][0]['bbox']
    point=[(box[0]+box[2])/2,(box[1]+box[3])/2];rect=[31.25,-42.5,300*scale,300*scale]
    client=[rect[0]+point[0]*rect[2]/g['width'],rect[1]+point[1]*rect[3]/g['height']]
    assert browser_to_pdf(g,[300,300],rect,client)==pytest.approx(point,abs=1e-12)
    node=shutil.which('node')
    if node is None:pytest.skip('No existing Node executable for JavaScript-only mapping check')
    url='data:text/javascript;base64,'+base64.b64encode(COORDINATES_JS.encode()).decode()
    script='const m=await import(process.argv[1]); const d=JSON.parse(process.argv[2]); console.log(JSON.stringify({p:m.pointerToPdf(...d.slice(0,4)),b:m.boxToCss(d[0],d[4],d[2])}));'
    data=[g,[300,300],rect,client,box]
    result=json.loads(subprocess.check_output([node,'--input-type=module','-e',script,url,json.dumps(data)],text=True))
    assert result['p']==pytest.approx(point,abs=1e-12)
    assert result['b']==pytest.approx([rect[0]+box[0]*rect[2]/g['width'],rect[1]+box[1]*rect[3]/g['height'],
        (box[2]-box[0])*rect[2]/g['width'],(box[3]-box[1])*rect[3]/g['height']],abs=1e-12)


@pytest.mark.parametrize('damage',['rotation','crop','unit','zero_display','outside','nan','bad_pixels'])
def test_mapping_rejects_unsupported_assumptions(context,damage):
    g=deepcopy(context.source['pages'][0]['geometry']);pixels=[300,300];rect=[0,0,300,300];point=[30,30]
    if damage=='rotation':g.update(rotation=90,raw_rotation=90)
    elif damage=='crop':g['cropbox']=[1,0,200,200]
    elif damage=='unit':g['user_unit']=2
    elif damage=='zero_display':rect[2]=0
    elif damage=='outside':point[0]=-1
    elif damage=='nan':point[0]=float('nan')
    else:pixels[0]=0
    with pytest.raises(ExtractionError):browser_to_pdf(g,pixels,rect,point)


def test_renderer_and_known_glyph_click(context,server):
    status,_,body=request(server,'/api/page/1');assert status==200
    meta=json.loads(body);assert [meta['render']['width'],meta['render']['height']]==[300,300]
    status,headers,png=request(server,'/api/page/1/image');assert status==200 and headers['Content-Type']=='image/png'
    assert Image.open(io.BytesIO(png)).size==(300,300)
    char=context.source['pages'][0]['characters'][0];box=char['bbox'];p=[(box[0]+box[2])/2,(box[1]+box[3])/2]
    body={**identity(context),'page_number':1,'render_sha256':meta['render']['sha256'],'image_pixels':[300,300],
          'display_rect':[10,20,150,150],'pointer':[10+p[0]*.75,20+p[1]*.75]}
    status,_,raw=request(server,'/api/click',body);assert status==200
    selected=json.loads(raw);assert char['id'] in [c['id'] for c in selected['characters']]
    assert selected['status']['ambiguous'] and selected['status']['overlapping_regions']
    candidates=[r for h in selected['hypotheses'] for r in h['regions']]
    assert {r['label'] for r in candidates}=={'table','formula'}
    assert selected['source_text']==char['text'] and selected['math_transcription']=='not_performed'
    assert request(server,'/api/click',body)[2]==raw


def test_textless_visual_and_source_only_page(context,server):
    q={'kind':'point','page_number':1,'point':[150,140],'coordinate_system':'pdfplumber-native-v1'}
    status,_,body=request(server,'/api/select',{**identity(context),'query':q})
    r=json.loads(body);assert status==200 and r['status']['textless_visual'] and r['characters']==[]
    q.update(page_number=2,point=[22,55])
    status,_,body=request(server,'/api/select',{**identity(context),'query':q})
    r=json.loads(body);assert status==200 and r['status']['source_only']
    assert not any(h['regions'] for h in r['hypotheses'])


@pytest.mark.parametrize('path',['/../manifest.json','/%2e%2e/%2e%2e/etc/passwd','/api/page/0','/api/page/999','/api/page/1/image?path=/etc/passwd','/files','/api/hybrid'])
def test_no_file_browser_or_invalid_pages(server,path):
    status,_,_=request(server,path);assert status in {400,404}


@pytest.mark.parametrize('headers',[{'Authorization':'Bearer wrong'},{'Authorization':'Bearer é'},
    {'Origin':'https://example.invalid'},{'Origin':'null'},{'Host':'attacker.invalid'}, {'Sec-Fetch-Site':'cross-site'}])
def test_origin_host_and_session_required(server,headers):
    status,response,_=request(server,'/api/status',headers=headers)
    assert status==403 and 'Access-Control-Allow-Origin' not in response


def test_loopback_only_read_only_bounded_server(server,context):
    assert server.server_address[0]=='127.0.0.1'
    for method in ['PUT','DELETE','PATCH','OPTIONS','TRACE','CONNECT']:
        assert request(server,'/api/status',method=method)[0]==405
    status,headers,html=request(server,'/')
    assert status==200 and b'Source inspection' in html
    assert "connect-src 'self'" in headers['Content-Security-Policy'] and "frame-ancestors 'none'" in headers['Content-Security-Policy']
    assert headers['Referrer-Policy']=='no-referrer' and headers['Cache-Control']=='no-store'
    c=http.client.HTTPConnection(*server.server_address,timeout=5)
    c.request('POST','/api/select',body=b'X'*(MAX_BODY+1),headers={'Authorization':'Bearer '+server.token,'Origin':server.origin,'Content-Type':'application/json'})
    response=c.getresponse();assert response.status==413;c.close()


def test_wrong_identity_and_stale_raster_fail(context,server):
    status,_,body=request(server,'/api/page/1');meta=json.loads(body)
    data={**identity(context),'page_number':1,'render_sha256':'0'*64,'image_pixels':[300,300],'display_rect':[0,0,300,300],'pointer':[20,20]}
    assert request(server,'/api/click',data)[0]==400
    data['render_sha256']=meta['render']['sha256'];data['image_pixels']=[301,300]
    assert request(server,'/api/click',data)[0]==400
    data={**identity(context),'query':{'kind':'character_ids','page_number':1,'character_ids':[]}}
    data['pdf_sha256']='0'*64;assert request(server,'/api/select',data)[0]==400


def test_context_initializes_once_and_image_cache_reuses_renderer(inputs,monkeypatch):
    import understanding_engine.viewer as viewer
    original=viewer.SelectionIndex;calls=[]
    def create(*a,**kw):calls.append(1);return original(*a,**kw)
    monkeypatch.setattr(viewer,'SelectionIndex',create)
    paths,m,_,_=inputs;ctx=DocumentContext(**paths,manifest=m,initial_page=1)
    assert ctx.status()['state']=='loading'
    ctx.start();ctx._thread.join(timeout=10);assert ctx.state=='ready'
    try:
        first=ctx.rendered(1);assert ctx.rendered(1) is first
        q={**identity(ctx),'query':{'kind':'point','page_number':1,'point':[22,55],'coordinate_system':'pdfplumber-native-v1'}}
        for _ in range(3):ctx.selection(q)
        assert calls==[1]
    finally:ctx.close()


@pytest.mark.parametrize('kind',['pdf','extraction','hybrid'])
def test_input_hashes_checked_before_use(inputs,kind):
    paths,m,_,_=inputs;m[kind]['sha256']='0'*64
    ctx=DocumentContext(**paths,manifest=m,initial_page=1);ctx.start();ctx._thread.join(timeout=10)
    try:assert ctx.state=='failed' and ctx.error
    finally:ctx.close()
