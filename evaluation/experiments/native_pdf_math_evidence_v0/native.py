"""Read-only native drawing sidecar; original extraction remains authoritative.

pdfplumber 0.11.8 converts .pts/.path to page TOPLEFT coordinates in
Page.process_object. Raw bottom-origin boxes are retained independently.
Drawing presence is not a guarantee of unclipped/visible ink or a math role.
"""
from copy import deepcopy
import hashlib
import math

import pdfplumber
from understanding_engine.contracts import validate_extraction
from understanding_engine.pdf_parser import _page_geometry,configuration
from understanding_engine.hybrid import _docling_geometry

RULE_POLICY={'thin_fill_max_thickness_points':1,'thin_fill_min_aspect_ratio':20,'thin_fill_min_length_points':2}


def require(ok,message):
    if not ok:raise ValueError(message)


def finite(values):return all(type(v) in (int,float) and math.isfinite(v) for v in values)


def straight_segments(path):
    """No chords, curve flattening, font outline interpretation or inferred paths."""
    if any(op[0] not in {'m','l','h'} for op in path):return None
    current=start=None;result=[]
    for op in path:
        if op[0] in {'m','l'}:
            require(len(op)==2 and len(op[1])==2 and finite(op[1]),'Malformed path point')
            target=list(op[1])
            if op[0]=='m':current=start=target;continue
            require(current is not None,'Path without start');result.append([current,target]);current=target
        else:
            require(current is not None and start is not None,'Unstarted closepath')
            result.append([current,start]);current=start
    return result


def proxies(primitive):
    """Only geometric rule hypotheses; never label a primitive a fraction."""
    b=primitive['bbox'];x0,y0,x1,y1=b;w,h=x1-x0,y1-y0
    if (primitive['kind']=='rect' and primitive['fill'] and 0<h<=RULE_POLICY['thin_fill_max_thickness_points']
        and w>=RULE_POLICY['thin_fill_min_length_points'] and w/h>=RULE_POLICY['thin_fill_min_aspect_ratio']):
        return [dict(id=primitive['id']+':centerline',primitive_id=primitive['id'],bbox=[x0,(y0+y1)/2,x1,(y0+y1)/2],
                     basis='thin filled rectangle centerline hypothesis',original_shape_bbox=b)]
    if not primitive['stroke']:return []
    segments=straight_segments(primitive['path'])
    if segments is None:return []
    return [dict(id=primitive['id']+':segment'+str(i),primitive_id=primitive['id'],
                 bbox=[min(p[0] for p in segment),min(p[1] for p in segment),max(p[0] for p in segment),max(p[1] for p in segment)],
                 basis='explicit native straight segment',endpoints=segment) for i,segment in enumerate(segments)]


def adapt_page(page,source_page,pdf_sha256):
    require(_page_geometry(page)==source_page['geometry'],'Native/source geometry differs')
    geometry=source_page['geometry'];_docling_geometry(geometry,{k:geometry[k] for k in ['width','height']})
    chars=source_page['characters'];require(len(chars)==len(page.chars),'Character count differs')
    for i,(source,native) in enumerate(zip(chars,page.chars)):
        require(source['id']==f"{pdf_sha256}:p{page.page_number}:c{i}" and source['backend_index']==i,'Foreign/corrupted source ID')
        require(source['text']==native['text'] and source['fontname']==native['fontname'] and source['size']==native['size']
                and source['bbox']==[native['x0'],native['top'],native['x1'],native['bottom']] and source['matrix']==list(native['matrix']),
                'Native character provenance differs')
    primitives=[];rules=[]
    for kind,objects in [('line',page.lines),('rect',page.rects),('curve',page.curves)]:
        require(len(objects)<=10000,'Primitive count bound')
        for index,obj in enumerate(objects):
            box=[obj['x0'],obj['top'],obj['x1'],obj['bottom']]
            require(finite(box) and box[0]<=box[2] and box[1]<=box[3],'Malformed primitive geometry')
            path=deepcopy(obj.get('path',[]));require(len(path)<=100000,'Path operation bound')
            for op in path:
                for p in op[1:]:require(len(p)==2 and finite(p),'Nonfinite path control point')
            record=dict(id=f'{pdf_sha256}:p{page.page_number}:{kind}{index}',kind=kind,backend_index=index,
              bbox=box,bottom_origin_bbox=[obj['x0'],obj['y0'],obj['x1'],obj['y1']],path=path,points=deepcopy(obj.get('pts',[])),
              stroke=bool(obj.get('stroke')),fill=bool(obj.get('fill')),linewidth=obj.get('linewidth'),
              mcid=obj.get('mcid'),tag=obj.get('tag'),
              geometry_status='explicit_straight_path' if straight_segments(path) is not None else 'curved_path_retained_unresolved',
              bounds_status='inside_page' if 0<=box[0]<=box[2]<=geometry['width'] and 0<=box[1]<=box[3]<=geometry['height'] else 'outside_page_retained',
              visibility='not_verified; clipping/occlusion not applied',content_stream_offset=None)
            primitives.append(record);rules+=proxies(record)
    return dict(page_number=page.page_number,geometry=deepcopy(geometry),
                source_character_ids=[c['id'] for c in chars],verified_original_characters=len(chars),
                primitives=primitives,rule_proxies=rules)


def adapt(pdf_path,source,page_numbers):
    validate_extraction(source);require(source['parser']['settings']==configuration(),'Nonbaseline extraction settings')
    require(page_numbers and len(page_numbers)==len(set(page_numbers)) and all(type(n)is int and 1<=n<=source['page_count'] for n in page_numbers),'Invalid pages')
    with pdf_path.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest();stream.seek(0)
        require(digest==source['source_sha256'],'Wrong PDF source identity')
        with pdfplumber.open(stream,unicode_norm=None,laparams=None) as pdf:
            require(len(pdf.pages)==source['page_count'],'Wrong PDF page count')
            pages=[adapt_page(pdf.pages[n-1],source['pages'][n-1],digest) for n in sorted(page_numbers)]
    return dict(schema_version='native-math-evidence.1',pdf_sha256=digest,coordinate_system='pdfplumber-native-v1',
      provenance=dict(provider='pdfplumber',version=source['parser']['dependencies']['pdfplumber'],source_parser=source['parser'],
                      object_ids='PDF hash + page + backend object kind/index; stable only with pinned backend',
                      association='Rule-to-character roles are separate reconstruction hypotheses, not native text membership'),
      rule_policy=RULE_POLICY,pages=pages)


def rules_in_region(page,box):
    g=page['geometry']
    require(isinstance(box,(list,tuple)) and len(box)==4 and finite(box) and
            0<=box[0]<box[2]<=g['width'] and 0<=box[1]<box[3]<=g['height'],'Invalid region geometry')
    return [deepcopy(r) for r in page['rule_proxies'] if box[0]<=r['bbox'][0]<=r['bbox'][2]<=box[2] and box[1]<=r['bbox'][1]<=r['bbox'][3]<=box[3]]
