"""Bounded read-only SVG evidence inspector. No font decoding or text repair.

Supported positioning: explicit per-character coordinates (including inherited
text/tspan x/y), numeric affine transforms and basic inline presentation styles.
Unpositioned advances, CSS selectors, curves and font metrics remain unresolved.
"""
from collections import Counter
import hashlib
import math
from pathlib import PurePosixPath
import re
import stat
import xml.etree.ElementTree as ET
import zipfile

LIMITS = dict(entries=64, member=8*1024**2, total=32*1024**2, ratio=100,
              elements=100000, depth=64, text=200000, archive=16*1024**2)
IDENTITY = [1,0,0,1,0,0]
NUMBER = r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
INHERITED = {'font-family','font-size','font-style','font-weight','text-anchor','fill','stroke','stroke-width','visibility','display','clip-path','opacity'}


def need(ok, message):
    if not ok: raise ValueError(message)


def numbers(value):
    need(isinstance(value,str), 'Non-string coordinate')
    need(not re.sub(NUMBER,'',value).strip(' ,\t\r\n'), 'Unsupported coordinate unit/syntax')
    result=[float(x) for x in re.findall(NUMBER,value)]
    need(all(math.isfinite(x) and abs(x)<=1e8 for x in result),'Nonfinite/excessive coordinate')
    return result


def multiply(a,b):
    return [a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]]


def point(m,x,y):return [m[0]*x+m[2]*y+m[4],m[1]*x+m[3]*y+m[5]]


def transform(value=''):
    result=IDENTITY[:];cursor=0
    for match in re.finditer(r'([A-Za-z]+)\s*\(([^)]*)\)',value):
        need(not value[cursor:match.start()].strip(' ,\t\n'),'Malformed transform')
        name=match[1];v=numbers(match[2]);m=IDENTITY[:]
        if name=='matrix' and len(v)==6:m=v
        elif name=='translate' and len(v) in {1,2}:m[4:]=[v[0],v[1] if len(v)==2 else 0]
        elif name=='scale' and len(v) in {1,2}:m[0]=v[0];m[3]=v[-1]
        elif name=='rotate' and len(v) in {1,3}:
            t=math.radians(v[0]);m=[math.cos(t),math.sin(t),-math.sin(t),math.cos(t),0,0]
            if len(v)==3:m=multiply(multiply([1,0,0,1,v[1],v[2]],m),[1,0,0,1,-v[1],-v[2]])
        elif name in {'skewX','skewY'} and len(v)==1:m[2 if name=='skewX' else 1]=math.tan(math.radians(v[0]))
        else:raise ValueError('Unsupported transform')
        need(all(math.isfinite(x) and abs(x)<=1e8 for x in m),'Excessive transform')
        result=multiply(result,m);cursor=match.end()
    need(not value[cursor:].strip(' ,\t\n'),'Malformed transform tail')
    return result


def xml_root(payload):
    need(len(payload)<=LIMITS['member'] and b'\0' not in payload,'XML size/encoding limit')
    upper=payload.upper();need(b'<!DOCTYPE' not in upper and b'<!ENTITY' not in upper,'DTD/entity declarations prohibited')
    need(not re.search(br'<\?(?!xml\s)',payload,re.I),'Processing instruction prohibited')
    root=ET.fromstring(payload);need(root.tag=='{http://www.w3.org/2000/svg}svg','Not SVG XML')
    count=0
    def check(e,depth):
        nonlocal count
        count+=1;need(count<=LIMITS['elements'] and depth<=LIMITS['depth'],'XML complexity limit')
        tag=e.tag.split('}')[-1]
        allowed={'svg','g','defs','clipPath','symbol','text','tspan','textPath','path','line','rect','polyline','polygon','circle','ellipse',
                 'use','image','font','font-face','glyph','missing-glyph','hkern','vkern','style','title','desc','metadata',
                 'linearGradient','radialGradient','stop','pattern','mask'}
        need(e.tag.startswith('{http://www.w3.org/2000/svg}') and tag in allowed,'Active/unsupported SVG element prohibited')
        for key,value in e.attrib.items():
            local=key.split('}')[-1]
            need(not local.lower().startswith('on') and local!='base','Active attribute/base URI prohibited')
            if local=='style':need('\\' not in value and '@' not in value,'Escaped/at-rule inline CSS prohibited')
            if local=='href':
                # Embedded raster bytes are retained, never decoded by this inspector.
                need(value.startswith('#') or re.fullmatch(r'data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=\s]+',value),'External/unsupported resource prohibited')
            need('@import' not in value.lower() and not re.search(r'url\(\s*[\'"]?(?!#)[^)]',value,re.I),'External CSS resource prohibited')
        if tag=='style':
            text=''.join(e.itertext());need('\\' not in text and '@' not in text and not re.search(r'url\(\s*[\'"]?(?!#)[^)]',text,re.I),'External/escaped stylesheet prohibited')
        for child in e:check(child,depth+1)
    check(root,0);return root


def read_archive(path):
    need(path.stat().st_size<=LIMITS['archive'],'Archive size limit')
    result=[]
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist();need(0<len(infos)<=LIMITS['entries'],'Archive entry limit')
        seen=set();total=0
        for info in infos:
            name=info.filename;p=PurePosixPath(name);mode=info.external_attr>>16
            need(name not in seen and not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name and '\0' not in name,'Unsafe/duplicate member name')
            need(not info.is_dir() and stat.S_IFMT(mode) in {0,stat.S_IFREG} and not stat.S_ISLNK(mode),'Nonregular archive entry')
            need(not info.flag_bits&1 and info.compress_type in {zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED},'Unsupported archive encoding')
            need(0<info.file_size<=LIMITS['member'] and info.file_size/max(1,info.compress_size)<=LIMITS['ratio'],'Decompression bound')
            total+=info.file_size;need(total<=LIMITS['total'],'Total decompression bound');seen.add(name)
            match=re.fullmatch(r'LOG2026_arxiv_final_preview-(\d+)\.svg',name)
            need(match is not None,'Unexpected member (no extraction performed)')
            with archive.open(info) as stream:payload=stream.read(LIMITS['member']+1)
            need(len(payload)==info.file_size,'Member length mismatch') # CRC also checked by zipfile.
            root=xml_root(payload)
            result.append(dict(name=name,page=int(match[1]),bytes=len(payload),compressed_bytes=info.compress_size,
                               sha256=hashlib.sha256(payload).hexdigest(),root=root,payload=payload))
    need(len({p['page'] for p in result})==len(result),'Duplicate page identity')
    return sorted(result,key=lambda p:p['page'])


def straight_path(value,matrix):
    """Only explicit straight-line paths. Curves/arcs are unknown, not glyphs."""
    if re.search(r'[CcSsQqTtAa]',value):return None
    tokens=re.findall(r'[A-Za-z]|'+NUMBER,value)
    need(not re.sub(r'[A-Za-z]|'+NUMBER,'',value).strip(' ,\r\n\t'),'Malformed path')
    out=[];i=0;cmd=None;x=y=0;start=None
    while i<len(tokens):
        if tokens[i].isalpha():cmd=tokens[i];i+=1
        need(cmd is not None and cmd.upper() in {'M','L','H','V','Z'},'Unsupported line path')
        if cmd.upper()=='Z':
            need(start is not None,'Unstarted closed path');out.append(point(matrix,*start));x,y=start;cmd=None;continue
        count=2 if cmd.upper() in {'M','L'} else 1
        need(i+count<=len(tokens) and all(not s.isalpha() for s in tokens[i:i+count]),'Incomplete path')
        v=[float(z) for z in tokens[i:i+count]];i+=count
        need(all(math.isfinite(z) and abs(z)<=1e8 for z in v),'Invalid path coordinate')
        if cmd.upper() in {'M','L'}:x,y=(x+v[0],y+v[1]) if cmd.islower() else v
        elif cmd.upper()=='H':x=x+v[0] if cmd.islower() else v[0]
        else:y=y+v[0] if cmd.islower() else v[0]
        out.append(point(matrix,x,y))
        if cmd.upper()=='M':start=(x,y);cmd='l' if cmd.islower() else 'L'
    return out


def inspect(root):
    width=numbers(root.get('width',''));height=numbers(root.get('height',''));view=numbers(root.get('viewBox',''))
    need(len(width)==len(height)==1 and len(view)==4 and min(width+height+view[2:])>0,'Unsupported viewport')
    text=[];shapes=[];warnings=[];tags=Counter();families=Counter();sizes=Counter();char_total=0
    def visit(e,parent_matrix,style,inherited_position,identity,depth):
        nonlocal char_total
        tag=e.tag.split('}')[-1];tags[tag]+=1
        matrix=multiply(parent_matrix,transform(e.get('transform','')))
        need(all(math.isfinite(v) and abs(v)<=1e8 for v in matrix),'Excessive nested transform')
        local=style.copy();local.update({k:v for k,v in e.attrib.items() if k in INHERITED})
        if tag in {'defs','clipPath','symbol','font','glyph'}:local['_definition']=True
        if 'style' in e.attrib:
            for part in e.attrib['style'].split(';'):
                if ':' in part:
                    k,v=part.split(':',1);local[k.strip()]=v.strip()
        pos=inherited_position.copy()
        for k in ['x','y','dx','dy','rotate']:
            if k in e.attrib:pos[k]=numbers(e.attrib[k])
        if tag in {'text','tspan'} and e.text:
            content=e.text;char_total+=len(content);need(char_total<=LIMITS['text'],'Text complexity limit')
            size=numbers(local.get('font-size','16'));need(len(size)==1 and size[0]>0,'Unsupported font size')
            family=local.get('font-family','unspecified');families[family]+=len(content);sizes[str(size[0])]+=len(content)
            xs=pos.get('x',[]);ys=pos.get('y',[]);dx=pos.get('dx',[0]);dy=pos.get('dy',[0]);rotation=pos.get('rotate',[0])
            supported=(len(xs)==len(content) and len(ys) in {1,len(content)} and len(dx)==len(dy)==1 and not any(rotation)
                       and local.get('text-anchor','start')=='start' and not e.get('textLength') and not e.get('lengthAdjust'))
            for i,c in enumerate(content):
                p=point(matrix,xs[i]+dx[0],ys[min(i,len(ys)-1)]+dy[0]) if supported else None
                text.append(dict(id=f'{identity}:u{i}',element=identity,xml_id=e.get('id'),offset=i,text=c,
                                 anchor=p,font_family=family,font_size=size[0]*math.hypot(matrix[2],matrix[3]),
                                 font_style=local.get('font-style','normal'),matrix=matrix[:],
                                 raw_position={'x':xs[i] if supported else None,'y':ys[min(i,len(ys)-1)] if supported else None,
                                               'dx':dx[0] if supported else None,'dy':dy[0] if supported else None},
                                 text_anchor=local.get('text-anchor','start'),position_status='explicit' if p else 'unresolved',
                                 box=None,box_status='font metrics unavailable; anchor is not glyph extent'))
            if not supported:warnings.append(dict(element=identity,reason='Unresolved advances, anchors or positioning'))
        if tag in {'path','line','rect','polyline','polygon'}:
            pts=None
            if tag=='path':pts=straight_path(e.get('d',''),matrix)
            elif tag=='line':
                v=[numbers(e.get(k,'0')) for k in ['x1','y1','x2','y2']];need(all(len(q)==1 for q in v),'Line coordinate')
                pts=[point(matrix,v[0][0],v[1][0]),point(matrix,v[2][0],v[3][0])]
            elif tag=='rect':
                v=[numbers(e.get(k,'0')) for k in ['x','y','width','height']];need(all(len(q)==1 for q in v),'Rect coordinate')
                x,y,w,h=[q[0] for q in v];pts=[point(matrix,a,b) for a,b in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]]
            else:
                v=numbers(e.get('points',''));need(len(v)%2==0,'Polygon coordinate');pts=[point(matrix,*v[i:i+2]) for i in range(0,len(v),2)]
            bbox=[min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)] if pts else None
            shapes.append(dict(id=identity,kind=tag,points=pts,bbox=bbox,matrix=matrix,style=local,
                               in_definition=local.get('_definition',False),clipping_applied=False,
                               geometry_status='straight_primitive' if pts else 'unresolved_curve',glyph_identity=None))
        if tag in {'style','use','textPath','font','glyph','font-face'}:warnings.append(dict(element=identity,reason='CSS/reference/font program not interpreted: '+tag))
        for i,c in enumerate(e):visit(c,matrix,local,pos,identity+'/'+str(i),depth+1)
        if e.tail and e.tail.strip():warnings.append(dict(element=identity,reason='Tail text is not assigned guessed advances'))
    visit(root,IDENTITY,{}, {},'svg',0)
    return dict(dimensions=[width[0],height[0]],viewBox=view,text=text,shapes=shapes,
                statistics=dict(tags=dict(tags),unicode_units=len(text),replacement_characters=sum(x['text']=='\ufffd' for x in text),
                                literal_whitespace=sum(x['text'].isspace() for x in text),fonts=dict(families),font_sizes=dict(sizes),
                                explicit_position_units=sum(x['anchor'] is not None for x in text)),warnings=warnings)
