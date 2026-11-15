"""Offline stages: inspect/map -> freeze candidates to disk -> load/score reference.

Only small summaries are intended for Git. Full source/units/predictions and
machine-specific execution logs belong in a new external --out directory.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import re
import time

import pdfplumber
import pypdfium2 as pdfium

from understanding_engine.contracts import json_bytes,validate_extraction
from understanding_engine.pdf_parser import extract_pdf,configuration
from .svg_inspector import read_archive,inspect,point,need,LIMITS
from .reconstruct import build,CONFIG

ANCHOR_TOLERANCE=0.05 # PDF points; explicit coordinate quantization tolerance, not IoU.


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save(path,value):path.write_bytes(json_bytes(value))


def frame(geometry,svg):
    w,h=geometry['width'],geometry['height'];expected=[0,0,w,h]
    need(geometry['rotation']==geometry['raw_rotation']==0 and geometry['user_unit']==1,'Unsupported PDF rotation/UserUnit')
    need(all(geometry[k]==expected for k in ['bbox','mediabox','cropbox','raw_mediabox','pdfminer_layout_bbox']),'Unsupported crop/media frame')
    need(geometry['raw_cropbox'] in [None,expected],'Unsupported raw crop')
    vx,vy,vw,vh=svg['viewBox'];sw,sh=svg['dimensions']
    need(sw==w and sh==h and vw/vh==w/h,'Unverified viewport/aspect transform')
    return [w/vw,0,0,h/vh,-vx*w/vw,-vy*h/vh]


def source_units(page):
    h=page['geometry']['height']
    return [dict(id=c['id'],text=c['text'],anchor=[c['matrix'][4],h-c['matrix'][5]],
                 font_size=c['size'],font_family=c['fontname'],box=c['bbox'],width_hint=c['bbox'][2]-c['bbox'][0]) for c in page['characters']]


def ground(svg_units,pdf_units):
    """Position-only association. Do not use labels/Unicode or force a match."""
    grid=defaultdict(list);step=ANCHOR_TOLERANCE
    for c in pdf_units:grid[tuple(math.floor(v/step) for v in c['anchor'])].append(c)
    result=[]
    for u in svg_units:
        p=u['anchor'];candidates=[]
        if p is not None:
            gx,gy=[math.floor(v/step) for v in p]
            for dx in [-1,0,1]:
                for dy in [-1,0,1]:
                    candidates += [c for c in grid[(gx+dx,gy+dy)] if math.dist(p,c['anchor'])<=step]
        ids=[c['id'] for c in candidates];unique=candidates[0] if len(candidates)==1 else None
        equality=('exact' if unique['text']==u['text'] else 'unresolved_encoding' if u['text']=='\ufffd' or unique['text'].startswith('(cid:') else 'contradictory') if unique else None
        result.append(dict(svg_id=u['id'],source_ids=ids,status='geometric_unique' if unique else 'ambiguous' if ids else 'unmatched',
                           unicode=equality,distance=math.dist(p,unique['anchor']) if unique else None,
                           evidence='Anchor coincidence only; no native source membership'))
    return result


def fingerprint(text):
    # Identity retrieval only; not Unicode normalization or an accuracy metric.
    letters=''.join(c for c in text if c.isascii() and c.isalnum())
    return {letters[i:i+7] for i in range(max(0,len(letters)-6))}


def page_mapping(source,svgs):
    pdf=[fingerprint(''.join(c['text'] for c in p['characters'])) for p in source['pages']];rows=[]
    for number,svg in enumerate(svgs,1):
        text=fingerprint(''.join(c['text'] for c in svg['text']))
        scores=sorted([(len(text&p)/len(text|p) if text|p else 0,i+1) for i,p in enumerate(pdf)],reverse=True)
        score,p=scores[0];second=scores[1][0] if len(scores)>1 else 0
        confident=score>=.6 and score-second>=.2
        rows.append(dict(svg_page=number,pdf_page=p if confident else None,identity_ascii_7gram_jaccard=score,
                         next_best=second,margin=score-second,status='page_correspondence_only' if confident else 'unresolved',
                         not_an_accuracy_score=True))
    need(len({r['pdf_page'] for r in rows if r['pdf_page'] is not None})==sum(r['pdf_page'] is not None for r in rows),'Nonunique page mapping')
    return rows


def crop_units(units,box):
    return [u for u in units if u['anchor'] is not None and box[0]<=u['anchor'][0]<=box[2] and box[1]<=u['anchor'][1]<=box[3]]


def counts(statuses):
    c=Counter(statuses);return dict(denominator=len(statuses),**{k:c[k] for k in ['correct','incorrect','missing','ambiguous','unscoreable']})


def unscoreable_result(ref):
    scores={}
    for mode in ['svg_only','source_only','combined']:
        scores[mode]={k:dict(reference=counts(['unscoreable']*len(ref[k])),predictions=0,incorrect_predictions=0,
                            reason='Document/region version comparability not established')
                      for k in ['fractions','indices','summations','delimiters','operators','expression_parts']}
        scores[mode]['equation_number']=dict(reference=counts(['unscoreable']),reason='Region not comparable')
    return dict(number=ref['number'],status='unscoreable',reason='Document/page correspondence unresolved or version mismatch',
                glyph_fidelity=counts(['unscoreable']*len(ref['symbols'])),geometry=None,source_traceability=None,scores=scores,
                visual_pixel_accuracy=None)


def evaluate(reference,prediction,bindings):
    """Exact relation-set checks against a separate, already frozen PDF reference."""
    mapping={b['svg_id']:b['source_ids'][0] for b in bindings if len(b['source_ids'])==1}
    def ids(seq):return frozenset(mapping.get(x,x) for x in seq)
    expected=reference;got=prediction['relations'];details={}
    for kind in ['fractions','indices','summations','delimiters','operators','expression_parts']:
        def signature(obj):
            if kind=='fractions':return (ids(obj['numerator']),ids(obj['denominator']))
            if kind=='indices':return (obj['kind'],ids(obj['base']),ids(obj['script']))
            if kind=='summations':return (ids(obj['operator']),ids(obj['index']),ids(obj['summand']))
            if kind in {'delimiters','expression_parts'}:return ids(obj)
            return ids([obj])
        def truth_signature(obj):
            # Reference IDs are already native. mapping cannot change them.
            return signature(obj)
        gold=[truth_signature(x) for x in expected[kind]];actual=[signature(x) for x in got[kind]]
        items=[]
        for i,signature_value in enumerate(gold):
            status='correct' if signature_value in actual else 'missing'
            if status=='missing' and kind=='indices':
                wanted=expected[kind][i]
                # Same base or same script with wrong linked counterpart is an
                # incorrect attachment; do not hide it as a mere missing link.
                if any(a['kind']==wanted['kind'] and (ids(a['base'])==ids(wanted['base']) or ids(a['script'])==ids(wanted['script'])) for a in got[kind]):status='incorrect'
            if status=='missing' and kind=='fractions' and any(a['bar_bbox']==expected[kind][i]['bar_bbox'] for a in got[kind]):status='incorrect'
            # Preserve explicit script ambiguity rather than count it as a hidden miss.
            if status=='missing' and kind=='indices':
                if any(isinstance(a,dict) and ids(a.get('script',[]))==ids(expected[kind][i]['script']) for a in prediction['ambiguities']):status='ambiguous'
            items.append(dict(reference_index=i,status=status,expected=expected[kind][i]))
        extras=sum(x not in gold for x in actual)
        details[kind]=dict(reference=counts([x['status'] for x in items]),predictions=len(actual),correct_predictions=sum(x in gold for x in actual),
                           incorrect_predictions=extras,items=items,comparison='Exact original-ID sets; no partial-credit matching')
    details['equation_number']=dict(reference=counts(['correct' if ids(prediction['equation_number_units'])==frozenset(reference['equation_number_ids']) else 'incorrect']))
    return details


def execute(pdf,archive,source_path,regions_path,reference_path,out,expected_pdf,expected_zip):
    need(not out.exists(),'Refuse to overwrite a run');need(digest(pdf)==expected_pdf and digest(archive)==expected_zip,'Input identity differs')
    started=time.perf_counter();out.mkdir()
    source=json.loads(source_path.read_bytes()) if source_path else extract_pdf(pdf)
    validate_extraction(source);need(source['source_sha256']==expected_pdf,'Extraction source differs')
    need(source['parser']['settings']==configuration(),'Extraction settings differ')
    if not source_path:save(out/'extraction.json',source)
    members=read_archive(archive);need([p['page'] for p in members]==list(range(1,len(members)+1)),'Noncontiguous archive page inventory')
    svgs=[inspect(p['root']) for p in members];mapping=page_mapping(source,svgs)
    statistics=[];allbindings={}
    for member,svg,row in zip(members,svgs,mapping):
        if row['pdf_page'] is not None:
            page=source['pages'][row['pdf_page']-1];matrix=frame(page['geometry'],svg)
            for u in svg['text']:
                if u['anchor']:u['anchor']=point(matrix,*u['anchor'])
            bindings=ground(svg['text'],source_units(page));allbindings[member['page']]=bindings
            row.update(svg_to_pdf=matrix,anchor_status_counts=dict(Counter(b['status'] for b in bindings)),unicode_status_counts=dict(Counter(b['unicode'] or 'unmatched_or_ambiguous' for b in bindings)))
            save(out/f"page-{member['page']}-grounding.json",{'bindings':bindings})
        stats=dict(page=member['page'],**svg['statistics'],shapes=dict(Counter(s['geometry_status'] for s in svg['shapes'])),warnings=svg['warnings'],
                   replacements=[dict(id=u['id'],font=u['font_family'],anchor=u['anchor']) for u in svg['text'] if u['text']=='\ufffd'])
        statistics.append(stats);save(out/f"page-{member['page']}-inspection.json",svg)
    save(out/'svg-inspection.json',dict(schema_version='svg-inspection.1',pages=statistics,limits=LIMITS))
    regions=json.loads(regions_path.read_bytes());predictions=[];pdf_lines=[]
    need(regions['identity_guard']==dict(pdf_sha256=expected_pdf,zip_sha256=expected_zip),'Region approval belongs to different inputs')
    # This phase does not open the reference. Regions carry boxes only.
    with pdfplumber.open(pdf) as backend:
        for region in regions['regions']:
            page_number=region['pdf_page'];svg_number=region['svg_page'];box=region['bbox'];row=mapping[svg_number-1]
            need(region['comparison_status'] in {'agent_visual_checked_comparable','unscoreable_version_mismatch'},'Region comparability has not been checked')
            if row['pdf_page']!=page_number or region['comparison_status']=='unscoreable_version_mismatch':
                predictions.append(dict(id=region['id'],status='unscoreable_version_mapping'));continue
            svg=svgs[svg_number-1];page=source['pages'][page_number-1];matrix=frame(page['geometry'],svg)
            s_units=crop_units(svg['text'],box);p_units=crop_units(source_units(page),box)
            bars=[]
            for shape in svg['shapes']:
                if shape['bbox'] is None or shape['in_definition']:continue
                x0,y0,x1,y1=shape['bbox'];corners=[point(matrix,x0,y0),point(matrix,x1,y1)]
                b=[min(v[0] for v in corners),min(v[1] for v in corners),max(v[0] for v in corners),max(v[1] for v in corners)]
                if box[0]<=b[0]<=b[2]<=box[2] and box[1]<=b[1]<=b[3]<=box[3]:bars.append(dict(shape,bbox=b))
            bindings=ground(s_units,p_units)
            pred={name:build(units,lines,page['geometry']['width']) for name,units,lines in [('svg_only',s_units,bars),('source_only',p_units,[]),('combined',p_units,bars)]}
            for name,units in [('svg_only',s_units),('source_only',p_units),('combined',p_units)]:
                need(sorted(pred[name]['conserved_unit_ids'])==sorted(u['id'] for u in units),'Prototype lost/duplicated units')
            backend_page=backend.pages[page_number-1]
            verified=0
            for char in page['characters']:
                if char['id'] not in {u['id'] for u in p_units}:continue
                native=backend_page.chars[char['backend_index']]
                need(native['text']==char['text'] and [native['x0'],native['top'],native['x1'],native['bottom']]==char['bbox'] and list(native['matrix'])==char['matrix'],'Native character contract differs')
                verified+=1
            lines=[dict(id='pdf-line-'+str(i),bbox=[l['x0'],l['top'],l['x1'],l['bottom']],linewidth=l['linewidth']) for i,l in enumerate(backend_page.lines)
                   if box[0]<=l['x0']<=l['x1']<=box[2] and box[1]<=l['top']<=l['bottom']<=box[3]]
            pdf_lines.append(dict(id=region['id'],lines=lines,native_character_exact_matches=verified,native_character_denominator=len(p_units)))
            predictions.append(dict(id=region['id'],status='candidate_predictions_frozen',pdf_page=page_number,svg_page=svg_number,box=box,
                                    units=s_units,source_units=p_units,shapes=bars,bindings=bindings,candidates=pred))
    save(out/'predictions.json',{'equations':predictions,'configuration':CONFIG})
    save(out/'pdf-native-lines.json',{'regions':pdf_lines,'not_in_existing_extraction_contract':True})
    prediction_hash=digest(out/'predictions.json')
    # Load labels only after immutable prediction bytes have been saved.
    reference=json.loads(reference_path.read_bytes());need(reference['pdf_sha256']==expected_pdf,'Reference identity differs')
    results=[]
    for region,pred,ref in zip(regions['regions'],predictions,reference['equations']):
        need(region['id']=='eq'+str(ref['number']),'Reference/region order differs')
        if pred['status']!='candidate_predictions_frozen':
            results.append(unscoreable_result(ref));continue
        by_source={}
        for b in pred['bindings']:
            if len(b['source_ids'])==1:by_source.setdefault(b['source_ids'][0],[]).append(b)
        glyphs=[];us={u['id']:u for u in pred['units']}
        for symbol in ref['symbols']:
            found=by_source.get(symbol['source_id'],[])
            if len(found)!=1:status='missing' if not found else 'ambiguous';svg_text=None
            else:svg_text=us[found[0]['svg_id']]['text'];status='correct' if svg_text==symbol['printed'] else 'incorrect'
            glyphs.append(dict(source_id=symbol['source_id'],printed=symbol['printed'],svg_text=svg_text,source_unicode=symbol['source_unicode'],
                              svg_status=status,source_status='correct' if symbol['source_unicode']==symbol['printed'] else 'ambiguous' if symbol['source_unicode'].startswith('(cid:') else 'incorrect',
                              presentation_equivalence='exact_unicode' if svg_text==symbol['printed'] else 'replacement_not_equivalent',
                              association='geometric_unique' if len(found)==1 else 'unmatched_or_ambiguous'))
        scores={name:evaluate(ref,candidate,pred['bindings'] if name=='svg_only' else []) for name,candidate in pred['candidates'].items()}
        distances=[b['distance'] for b in pred['bindings'] if len(b['source_ids'])==1]
        formula_ids={s['source_id'] for s in ref['symbols']};number_ids=set(ref['equation_number_ids'])
        unmatched=[u['id'] for u in pred['units'] if not any(b['svg_id']==u['id'] and len(b['source_ids'])==1 for b in pred['bindings'])]
        results.append(dict(number=ref['number'],status='comparable_region',glyphs=glyphs,
                            glyph_fidelity=counts([x['svg_status'] for x in glyphs]),source_unicode_fidelity=counts([x['source_status'] for x in glyphs]),
                            extra_unmatched_svg_units=unmatched,geometry=dict(unique_matches=len(distances),denominator=len(pred['units']),max_anchor_distance=max(distances,default=None),tolerance=ANCHOR_TOLERANCE,frame='TOPLEFT PDF points'),
                            source_traceability=dict(native_membership=0,geometric_unique=len(distances),denominator=len(pred['units']),original_ids_recoverable_by_geometry=True),
                            scores=scores,visual_pixel_accuracy=None,visual_pixel_accuracy_reason='Fonts absent from SVG; no registered cross-renderer pixel scoring protocol'))
    save(out/'equation-results.json',dict(schema_version='svg-math-results.1',reference_status=reference['status'],independent_human_verifications=0,
         predictions_sha256=prediction_hash,reference_sha256=digest(reference_path),configuration=CONFIG,equations=results))
    manifest=dict(schema_version='svg-math-inputs.1',development_only=True,pdf=dict(name=pdf.name,bytes=pdf.stat().st_size,sha256=expected_pdf,page_count=source['page_count']),
         pdf_filename_decision='User explicitly confirmed discovered final_preview.pdf in place of absent source_clean_preview.pdf; not a silent substitute',
         zip=dict(name=archive.name,bytes=archive.stat().st_size,sha256=expected_zip),svgs=[{k:v for k,v in p.items() if k not in ['root','payload']}|dict(dimensions=v['dimensions'],viewBox=v['viewBox']) for p,v in zip(members,svgs)],
         page_mapping=mapping,comparable_regions=regions['regions'],source_extraction=dict(sha256=digest(source_path or out/'extraction.json'),parser=source['parser'],coordinate_system=source['coordinate_system']),
         versions={p:importlib.metadata.version(p) for p in ['pdfplumber','pdfminer.six','pypdfium2','Pillow','pytest']},python=platform.python_version(),
         note='ASCII retrieval and anchor checks establish page/region correspondence, not whole-page Unicode or visual accuracy. No declared earlier PDF-version mismatch was assumed.')
    save(out/'input-manifest.json',manifest)
    save(out/'run.local.json',dict(seconds=time.perf_counter()-started,paths=dict(pdf=str(pdf),archive=str(archive),source=str(source_path)),prediction_hash=prediction_hash))
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ['pdf','zip','regions','reference','out']:parser.add_argument('--'+k,type=Path,required=True)
    parser.add_argument('--source',type=Path);parser.add_argument('--pdf-sha256',required=True);parser.add_argument('--zip-sha256',required=True)
    a=parser.parse_args();execute(a.pdf,a.zip,a.source,a.regions,a.reference,a.out,a.pdf_sha256,a.zip_sha256)


if __name__=='__main__':main()
