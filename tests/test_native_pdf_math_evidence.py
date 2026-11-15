"""Offline native provenance, bounded font diagnostics and frozen-solver checks."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import zlib

import pytest
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject,NumberObject,EncodedStreamObject
from reportlab.pdfgen import canvas

from understanding_engine.contracts import ExtractionError,json_bytes
from understanding_engine.pdf_parser import extract_pdf

ROOT=Path(__file__).parents[1]


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    return [importlib.import_module('evaluation.experiments.native_pdf_math_evidence_v0.'+name) for name in ['native','fonts','run']]


@pytest.fixture
def original(tmp_path):
    path=tmp_path/'authored.pdf';pdf=canvas.Canvas(str(path),pagesize=(200,200),invariant=1)
    pdf.setFont('Helvetica',10);pdf.drawString(20,140,'Original glyphs')
    pdf.line(40,150,100,150);pdf.rect(40,90,60,.4,stroke=0,fill=1)
    pdf.bezier(20,80,40,100,60,60,80,80);pdf.save()
    return path,extract_pdf(path)


def test_native_sidecar_conserves_ids_and_nonstraight_evidence(modules,original):
    native,_,_=modules;pdf,source=original;before=json_bytes(source)
    a=native.adapt(pdf,source,[1]);b=native.adapt(pdf,source,[1]);assert json_bytes(a)==json_bytes(b)
    assert before==json_bytes(source)
    page=a['pages'][0];assert page['source_character_ids']==[c['id'] for c in source['pages'][0]['characters']]
    assert {p['kind'] for p in page['primitives']}=={'line','rect','curve'}
    curve=next(p for p in page['primitives'] if p['kind']=='curve');assert curve['geometry_status']=='curved_path_retained_unresolved'
    assert not any(r['primitive_id']==curve['id'] for r in page['rule_proxies'])
    center=next(r for r in page['rule_proxies'] if r['basis'].startswith('thin filled'))
    assert center['bbox']==pytest.approx([40,109.8,100,109.8]);assert center['original_shape_bbox']==pytest.approx([40,109.6,100,110])
    assert len(native.rules_in_region(page,[35,100,105,115]))==1


@pytest.mark.parametrize('damage',['id','unicode','box','matrix','wrong_pdf'])
def test_corrupted_source_or_identity_fails(modules,original,tmp_path,damage):
    native,_,_=modules;pdf,source=original;s=deepcopy(source);char=s['pages'][0]['characters'][0]
    if damage=='id':char['id']='foreign'
    elif damage=='unicode':char['text']='Z'
    elif damage=='box':char['bbox'][0]+=.25
    elif damage=='matrix':char['matrix'][4]+=.25
    else:pdf=tmp_path/'wrong.pdf';pdf.write_bytes(b'Wrong immutable input')
    with pytest.raises((ValueError,ExtractionError)):native.adapt(pdf,s,[1])


@pytest.mark.parametrize('box',[[0,0,0,20],[-1,0,20,20],[0,0,201,20],[0,0,float('nan'),20]])
def test_invalid_regions_are_not_guessed(modules,original,box):
    native,_,_=modules;page=native.adapt(*original,[1])['pages'][0]
    with pytest.raises(ValueError):native.rules_in_region(page,box)


def test_rotated_native_frame_rejected(modules,tmp_path):
    native,_,_=modules;path=tmp_path/'rotated.pdf';pdf=canvas.Canvas(str(path),pagesize=(200,200),invariant=1)
    pdf.setPageRotation(90);pdf.drawString(30,30,'Rotated');pdf.save()
    with pytest.raises(ExtractionError):native.adapt(path,extract_pdf(path),[1])


def header(name='ABCDEF+CMEX10',statements='dup 88 /summationdisplay put'):
    return ('/FontName /'+name+' def\n/Encoding 256 array\n0 1 255 {1 index exch /.notdef put} for\n'+statements+'\nreadonly def\ncurrentdict end\ncurrentfile eexec\n').encode()


def fake_font(program=None,name='ABCDEF+CMEX10'):
    stream=DecodedStreamObject();data=program or header(name);stream.set_data(data);stream[NameObject('/Length1')]=NumberObject(len(data))
    descriptor=DictionaryObject({NameObject('/FontName'):NameObject('/'+name),NameObject('/FontFile'):stream})
    return DictionaryObject({NameObject('/BaseFont'):NameObject('/'+name),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/FontDescriptor'):descriptor})


def test_font_specific_resolution_preserves_original_cid(modules):
    _,fonts,_=modules;f=fake_font();page=DictionaryObject({NameObject('/Resources'):DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):f})})})
    source=dict(page_number=1,characters=[dict(id='original-id',text='(cid:88)',fontname='ABCDEF+CMEX10')]);before=deepcopy(source)
    result=fonts.resolve_page(page,source)['glyphs'][0]
    assert result['status']=='resolved_diagnostic' and result['diagnostic_unicode']=='∑'
    assert result['original_unicode']=='(cid:88)' and result['source_unicode_rewritten'] is False and source==before
    assert result['font_evidence'][0]['program_name']=='ABCDEF+CMEX10' and len(result['font_evidence'][0]['fontfile_sha256'])==64


def test_same_cid_is_not_a_global_unicode_mapping(modules):
    _,fonts,_=modules
    a=dict(base_font='ABCDEF+CMEX10',encoding={88:{'summationdisplay'}},unicode={})
    b=dict(base_font='OTHER',encoding={88:{'product'}},unicode={})
    assert fonts.diagnostic_identity(88,a)['diagnostic_unicode']=='∑'
    assert fonts.diagnostic_identity(88,b)['diagnostic_unicode']=='∏'
    b['encoding'][88]={'summationdisplay'};assert fonts.diagnostic_identity(88,b)['status']=='unrecoverable'


def test_duplicate_code_cmap_and_resource_ambiguity(modules):
    _,fonts,_=modules;name,bindings=fonts.static_encoding(header(statements='dup 88 /summationdisplay put dup 88 /product put'))
    assert fonts.diagnostic_identity(88,dict(base_font=name,encoding=bindings,unicode={}))['status']=='ambiguous'
    assert fonts.diagnostic_identity(88,dict(base_font=name,encoding={88:{'summationdisplay'}},unicode={88:'∑'}))['status']=='ambiguous'
    page=DictionaryObject({NameObject('/Resources'):DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):fake_font(),NameObject('/F2'):fake_font()})})})
    source=dict(page_number=1,characters=[dict(id='u',text='(cid:88)',fontname=name)])
    assert fonts.resolve_page(page,source)['glyphs'][0]['status']=='ambiguous'


@pytest.mark.parametrize('program',[header()+b'/Encoding 256 array def',header(statements='88 someDynamicProcedure'),b'x'*65537])
def test_noncanonical_font_headers_fail_closed(modules,program):
    _,fonts,_=modules
    with pytest.raises(ValueError):fonts.static_encoding(program)


def test_explicit_encoding_and_name_conflict_do_not_fallback(modules):
    _,fonts,_=modules;f=fake_font();f[NameObject('/Encoding')]=NameObject('/WinAnsiEncoding')
    page=DictionaryObject({NameObject('/Resources'):DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):f})})})
    source=dict(page_number=1,characters=[dict(id='u',text='(cid:88)',fontname='ABCDEF+CMEX10')])
    r=fonts.resolve_page(page,source)['glyphs'][0];assert r['status']=='unrecoverable' and 'override' in r['reason']
    del f['/Encoding'];program=header('DIFFERENT');f['/FontDescriptor']['/FontFile'].set_data(program)
    f['/FontDescriptor']['/FontFile'][NameObject('/Length1')]=NumberObject(len(program))
    r=fonts.resolve_page(page,source)['glyphs'][0];assert r['status']=='unrecoverable' and 'conflict' in r['reason']


def test_font_stream_decompression_and_filter_bounds(modules):
    _,fonts,_=modules;stream=EncodedStreamObject();stream._data=zlib.compress(b'0'*10000);stream[NameObject('/Filter')]=NameObject('/FlateDecode')
    with pytest.raises(ValueError):fonts.bounded_stream(stream,64)
    stream._data=zlib.compress(b'abc');assert fonts.bounded_stream(stream,64)==b'abc'
    stream[NameObject('/Filter')]=NameObject('/LZWDecode')
    with pytest.raises(ValueError):fonts.bounded_stream(stream,64)


def test_frozen_algorithm_and_unfixed_nested_fraction_limitation(modules):
    _,_,runner=modules;freeze=json.loads((runner.HERE/'freeze.json').read_bytes())
    assert runner.frozen.CONFIG==freeze['configuration']
    assert all(runner.sha(runner.ROOT/path)==digest for path,digest in freeze['frozen_parent_files'].items())
    def u(i,x,y):return dict(id=i,text=i,anchor=[x,y],font_size=10)
    units=[u('a',40,15),u('b',40,32),u('c',40,53)]
    prediction=runner.frozen.build(units,[dict(id='inner',bbox=[35,25,50,25]),dict(id='outer',bbox=[30,42,60,42])],200)
    assert sorted(prediction['conserved_unit_ids'])==['a','b','c']
    assert not any(set(f['numerator'])=={'a','b'} and f['denominator']==['c'] for f in prediction['relations']['fractions'])


def test_zero_denominators_remain_null(modules):
    _,_,runner=modules
    assert runner.aggregate([])=={}


def test_unvalidated_cmex_variant_remains_explicitly_unsupported(modules):
    _,fonts,_=modules
    font=dict(base_font='ABCDEF+CMEX9',encoding={80:{'summationtext'}},unicode={})
    result=fonts.diagnostic_identity(80,font)
    assert result['status']=='unrecoverable' and result['glyph_name']=='summationtext' and result['diagnostic_unicode'] is None


def test_runner_writes_predictions_before_loading_labels(modules,original,tmp_path,monkeypatch):
    _,_,runner=modules;pdf,source=original;here=tmp_path/'experiment';here.mkdir();out=tmp_path/'run'
    source_path=tmp_path/'source.json';source_path.write_bytes(json_bytes(source));retained=tmp_path/'retained.json';retained.write_text('{"equations":[]}')
    source_hash=runner.sha(source_path);pdf_hash=source['source_sha256'];svg_hash=runner.sha(retained)
    region=dict(id='authored',document='authored',page=1,bbox=[10,10,190,190],role='new_component_evaluation')
    (here/'regions.json').write_bytes(json_bytes(dict(regions=[region])))
    chars=source['pages'][0]['characters'];ids=[c['id'] for c in chars]
    ref=dict(id='authored',number='authored',fractions=[],indices=[],summations=[],delimiters=[],operators=[],expression_parts=[ids],equation_number_ids=[])
    (here/'reference.json').write_bytes(json_bytes(dict(equations=[ref])))
    freeze=json.loads((runner.HERE/'freeze.json').read_bytes());freeze['reference_sha256']=runner.sha(here/'reference.json')
    (here/'freeze.json').write_bytes(json_bytes(freeze))
    (here/'input-manifest.json').write_bytes(json_bytes(dict(documents=[dict(id='authored',pdf_sha256=pdf_hash,source_sha256=source_hash)],
        retained_svg_rules=dict(sha256=svg_hash),regions_sha256=runner.sha(here/'regions.json'))))
    local=tmp_path/'inputs.json';local.write_bytes(json_bytes(dict(documents=[dict(id='authored',pdf=str(pdf),source=str(source_path))],retained_svg_rules=dict(path=str(retained)))))
    original_read=Path.read_bytes;observed=[]
    def read(path):
        if path==here/'reference.json':
            assert (out/'predictions.json').exists();observed.append(True)
        return original_read(path)
    monkeypatch.setattr(runner,'HERE',here);monkeypatch.setattr(Path,'read_bytes',read)
    result=runner.execute(local,out)
    assert observed and len(result['regions'])==1
    predictions=json.loads((out/'predictions.json').read_bytes())['regions'][0]
    assert {c['text'] for c in predictions['units']}=={c['text'] for c in chars}
    assert set(predictions['candidates'])=={'characters','native_vectors'}
