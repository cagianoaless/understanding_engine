"""Offline safety, provenance and abstention regressions for an isolated experiment."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import stat
import xml.etree.ElementTree as ET
import zipfile
import importlib
import hashlib

import pytest

ROOT=Path(__file__).parents[1]
DIRECTORY=ROOT/'evaluation/experiments/svg_math_feasibility'
def load(name):
    spec=importlib.util.spec_from_file_location('experimental_'+name,DIRECTORY/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
SVG=load('svg_inspector');MATH=load('reconstruct')


def svg(body,attrs=''):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200" '+attrs+'>'+body+'</svg>').encode()


def archive(tmp_path,payload=None,name='LOG2026_arxiv_final_preview-1.svg',mode=None,compression=zipfile.ZIP_STORED):
    path=tmp_path/'input.zip'
    with zipfile.ZipFile(path,'w',compression=compression) as z:
        if mode is None:z.writestr(name,payload or svg(''))
        else:
            i=zipfile.ZipInfo(name);i.external_attr=mode<<16;z.writestr(i,payload or svg(''))
    return path


@pytest.mark.parametrize('name',['../escape.svg','/absolute.svg','a/../../escape.svg','C:\\evil.svg','safe.svg','nested/LOG2026_arxiv_final_preview-1.svg'])
def test_archive_name_allowlist_and_no_extraction(tmp_path,name):
    p=archive(tmp_path,name=name)
    with pytest.raises(ValueError):SVG.read_archive(p)
    assert sorted(x.name for x in tmp_path.iterdir())==['input.zip']


@pytest.mark.parametrize('mode',[stat.S_IFLNK|0o777,stat.S_IFDIR|0o755,stat.S_IFIFO|0o600])
def test_nonregular_members_rejected(tmp_path,mode):
    with pytest.raises(ValueError):SVG.read_archive(archive(tmp_path,mode=mode))


def test_decompression_bound_and_duplicate_member(tmp_path):
    with pytest.raises(ValueError):SVG.read_archive(archive(tmp_path,b'0'*100000,compression=zipfile.ZIP_DEFLATED))
    p=tmp_path/'duplicate.zip'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('LOG2026_arxiv_final_preview-1.svg',svg(''))
        with pytest.warns(UserWarning):z.writestr('LOG2026_arxiv_final_preview-1.svg',svg(''))
    with pytest.raises(ValueError):SVG.read_archive(p)


@pytest.mark.parametrize('payload',[
    b'<!DOCTYPE svg [<!ENTITY e SYSTEM "file:///etc/passwd">]>'+svg('<text>&e;</text>'),
    b'<?xml-stylesheet href="https://example.invalid/a"?>'+svg(''),
    svg('<script>alert(1)</script>'),svg('<foreignObject/>'),svg('<g onclick="alert(1)"/>'),
    svg('<image href="https://example.invalid/a.png"/>'),svg('<use href="file:///etc/passwd"/>'),
    svg('<style>@import "https://example.invalid/x";</style>'),svg('<text style="fill:url(https://example.invalid/a)">x</text>'),
    svg('<style>body{background:im\\61ge-set("https://example.invalid/x")}</style>'),
    svg('<iframe xmlns="http://www.w3.org/1999/xhtml" src="https://example.invalid/"/>'),
    svg('<g>'),b'\xff\xfe\0<\0s\0v\0g',svg('','xml:base="https://example.invalid/"')])
def test_xml_active_external_and_malformed_content_rejected(payload):
    with pytest.raises((ValueError,ET.ParseError)):SVG.xml_root(payload)


def test_transforms_inheritance_unicode_and_unresolved_advances():
    b=svg('<g transform="translate(10,20) scale(2)" font-size="7" font-family="Math"><text x="3 8" y="4"><tspan>ϕ�</tspan></text></g>')
    result=SVG.inspect(SVG.xml_root(b));a,c=result['text']
    assert a['anchor']==[16,28] and c['anchor']==[26,28]
    assert a['font_size']==14 and a['font_family']=='Math' and c['text']=='\ufffd'
    assert result['statistics']['replacement_characters']==1
    assert result['text'][0]['box'] is None
    root=SVG.xml_root(svg('<text x="1" y="10">AB</text>'));assert all(x['anchor'] is None for x in SVG.inspect(root)['text'])
    root=SVG.xml_root(svg('<text x="1 2" y="10" text-anchor="end">AB</text>'));assert all(x['anchor'] is None for x in SVG.inspect(root)['text'])


def test_path_geometry_is_not_glyph_identity():
    r=SVG.inspect(SVG.xml_root(svg('<path transform="matrix(1,0,0,-1,20,40)" d="M0 0H10"/><path d="M0 0C1 2 3 4 5 6"/>')))
    assert r['shapes'][0]['bbox']==[20,40,30,40] and r['shapes'][0]['glyph_identity'] is None
    assert r['shapes'][1]['bbox'] is None and r['shapes'][1]['geometry_status']=='unresolved_curve'
    assert SVG.transform('rotate(90,2,2)')==pytest.approx([0,1,-1,0,4,0],abs=1e-12)


def unit(id,text,x,y,size=10):return dict(id=id,text=text,anchor=[x,y],font_size=size)


def test_fraction_grouping_number_and_character_conservation():
    units=[unit('a','a',20,40),unit('eq','=',30,40),unit('n','b',45,30),unit('d','c',45,49),unit('lp','(',170,40),unit('digit','9',176,40),unit('rp',')',182,40)]
    shapes=[dict(id='bar',bbox=[42,38,57,38])]
    original=deepcopy(units);a=MATH.build(units,shapes,200)
    assert a==MATH.build(units,shapes,200) and original==units
    assert sorted(a['conserved_unit_ids'])==sorted(u['id'] for u in units)
    assert a['equation_number_units']==['lp','digit','rp']
    f=a['relations']['fractions'][0];assert f['numerator']==['n'] and f['denominator']==['d'] and f['bar_id']=='bar'
    assert not MATH.build([unit('u','u',45,20)],shapes,200)['relations']['fractions']


def test_scripts_without_known_formula_and_unknown_glyph_abstention():
    units=[unit('base','Q',20,50),unit('up','3',26,46,7),unit('down','i',26,52,7)]
    r=MATH.build(units,[],200)
    assert {(x['kind'],tuple(x['base']),tuple(x['script'])) for x in r['relations']['indices']}=={
      ('superscript',('base',),('up',)),('subscript',('base',),('down',))}
    unknown=MATH.build([unit('bad','�',20,50),unit('i','i',26,55,7),unit('x','x',40,50)],[],200)
    assert unknown['unresolved_symbol_ids']==['bad'] and unknown['relations']['summations']==[]
    known=MATH.build([unit('sum','∑',20,50),unit('i','i',26,55,7),unit('x','x',40,50)],[],200)
    assert known['relations']['summations']==[dict(operator=['sum'],index=['i'],summand=['x'])]


def test_ambiguous_scripts_are_not_forced():
    r=MATH.build([unit('a','a',20,50),unit('b','b',21,50),unit('i','i',26,54,7)],[],200)
    assert not r['relations']['indices'] and any(x['kind']=='script_candidates' for x in r['ambiguities'])


def test_frozen_reference_and_configuration_are_not_candidate_input():
    frozen=json.loads((DIRECTORY/'freeze.json').read_text())
    assert frozen['configuration']==MATH.CONFIG
    source=(DIRECTORY/'reconstruct.py').read_text()
    assert 'reference.json' not in source and 'regions.json' not in source and 'json.load' not in source
    assert MATH.build([],[],200)['conserved_unit_ids']==[]


def test_typed_tree_preserves_unknown_operations_and_all_units():
    units=[unit('a','a',10,50),unit('eq','=',20,50),unit('lp','(',35,50),unit('b','b',45,50),unit('minus','−',55,50),unit('c','c',65,50),unit('rp',')',75,50)]
    r=MATH.build(units,[],200)
    assert r['expression_tree']['kind']=='equality'
    assert sorted(MATH.descendants(r['expression_tree']))==sorted(u['id'] for u in units)
    assert 'arithmetic' in json.dumps(r['expression_tree']) and 'group' in json.dumps(r['expression_tree'])


@pytest.fixture
def experiment(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    return importlib.import_module('evaluation.experiments.svg_math_feasibility.experiment')


@pytest.mark.parametrize('damage',['rotation','crop','user_unit','aspect'])
def test_coordinate_frames_fail_closed(experiment,damage):
    box=[0,0,200,200];g={k:box[:] for k in ['bbox','mediabox','cropbox','raw_mediabox','pdfminer_layout_bbox']}
    g.update(width=200,height=200,rotation=0,raw_rotation=0,user_unit=1,raw_cropbox=None)
    v=dict(viewBox=[10,20,400,400],dimensions=[200,200])
    assert experiment.frame(g,v)==[.5,0,0,.5,-5,-10]
    if damage=='rotation':g['rotation']=90
    elif damage=='crop':g['cropbox']=[1,0,200,200]
    elif damage=='user_unit':g['user_unit']=2
    else:v['viewBox'][2]=300
    with pytest.raises(ValueError):experiment.frame(g,v)


def test_geometric_grounding_does_not_invent_one_to_one_membership(experiment):
    pdf=[unit('p1','fi',20,40),unit('p2','x',50,40),unit('p3','x',50,40)]
    svg_units=[unit('s1','f',20,40),unit('s2','i',23,40),unit('s3','x',50,40),unit('s4','�',70,40)]
    b=experiment.ground(svg_units,pdf)
    assert [x['status'] for x in b]==['geometric_unique','unmatched','ambiguous','unmatched']
    assert b[0]['unicode']=='contradictory' and b[2]['source_ids']==['p2','p3']
    assert all('no native source membership' in x['evidence'] for x in b)


def test_isolated_pipeline_freezes_predictions_before_reference(tmp_path,experiment,monkeypatch):
    from reportlab.pdfgen import canvas
    from understanding_engine.pdf_parser import extract_pdf
    from understanding_engine.contracts import json_bytes
    pdf=tmp_path/'authored.pdf';c=canvas.Canvas(str(pdf),pagesize=(200,200),invariant=1);c.setFont('Helvetica',10);c.drawString(20,140,'ABCDEFGH = 9');c.save()
    source=extract_pdf(pdf);chars=[c for c in source['pages'][0]['characters'] if c['text']!=' ']
    xs=' '.join(str(c['matrix'][4]) for c in chars);text=''.join(c['text'] for c in chars)
    zip_path=archive(tmp_path,svg(f'<text font-size="10"><tspan x="{xs}" y="60">{text}</tspan></text>'))
    src=tmp_path/'source.json';src.write_bytes(json_bytes(source))
    regions=tmp_path/'regions.json';regions.write_text(json.dumps({'identity_guard':dict(pdf_sha256=source['source_sha256'],zip_sha256=hashlib.sha256(zip_path.read_bytes()).hexdigest()),'regions':[dict(id='eq9',pdf_page=1,svg_page=1,bbox=[15,45,150,70],comparison_status='agent_visual_checked_comparable')]}))
    ref=tmp_path/'reference.json';ref.write_text(json.dumps(dict(pdf_sha256=source['source_sha256'],status='authored_synthetic',equations=[dict(number=9,
       symbols=[dict(source_id=c['id'],printed=c['text'],source_unicode=c['text']) for c in chars],equation_number_ids=[],fractions=[],indices=[],summations=[],delimiters=[],operators=[c['id'] for c in chars if c['text']=='='],expression_parts=[[c['id'] for c in chars]])])))
    out=tmp_path/'results';original=Path.read_bytes;reads=[]
    def read(path):
        if path==ref:
            assert (out/'predictions.json').is_file();reads.append(True)
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',read)
    scores=experiment.execute(pdf,zip_path,src,regions,ref,out,source['source_sha256'],hashlib.sha256(zip_path.read_bytes()).hexdigest())
    assert reads and scores[0]['glyph_fidelity']['correct']==len(chars)
    assert all(x['association']=='geometric_unique' for x in scores[0]['glyphs'])
    assert (out/'input-manifest.json').exists()
    with pytest.raises(ValueError):experiment.execute(pdf,zip_path,src,regions,ref,out,source['source_sha256'],'0'*64)
    rejected=tmp_path/'rejected'
    with pytest.raises(ValueError):experiment.execute(pdf,zip_path,src,regions,ref,rejected,'0'*64,hashlib.sha256(zip_path.read_bytes()).hexdigest())
    assert not rejected.exists()


def test_native_font_names_are_diagnostics_not_source_rewrites():
    m=load('font_evidence');header=b'/Encoding 256 array dup 88 /summationdisplay put dup 80 /summationtext put'
    assert m.header_names(header)=={88:'summationdisplay',80:'summationtext'}
    with pytest.raises(ValueError):m.header_names(b' '*65537)
    assert 'font_evidence' not in (DIRECTORY/'reconstruct.py').read_text()


def test_page_mapping_detects_shifts_and_abstains_on_other_content(experiment):
    source=dict(pages=[dict(characters=[dict(text='ABCDEFGH')]),dict(characters=[dict(text='KLMNOPQR')])])
    rows=experiment.page_mapping(source,[dict(text=[dict(text='KLMNOPQR')]),dict(text=[dict(text='ABCDEFGH')])])
    assert [r['pdf_page'] for r in rows]==[2,1]
    row=experiment.page_mapping(source,[dict(text=[dict(text='STUVWXYZ')])])[0]
    assert row['pdf_page'] is None and row['status']=='unresolved'


def test_version_mismatch_keeps_complete_unscoreable_denominators(experiment):
    ref=dict(number=2,symbols=['a','b'],fractions=[{}],indices=[{}],summations=[{}],delimiters=[{}],operators=['='],expression_parts=[{}])
    result=experiment.unscoreable_result(ref)
    assert result['glyph_fidelity']['denominator']==result['glyph_fidelity']['unscoreable']==2
    assert result['geometry'] is None and result['source_traceability'] is None
    for mode in ['svg_only','source_only','combined']:
        assert all(v['reference']['unscoreable']==v['reference']['denominator'] for v in result['scores'][mode].values())
