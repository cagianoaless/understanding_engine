"""Bounded diagnostic identities from unique embedded simple Type1 fonts.

No global CID table, equation context, PostScript execution, or source rewriting.
Only a canonical static Type1 Encoding subset and four standard math names / two
CMEX10 variants are supported. A name is declared font evidence, not proof that
an arbitrary adversarial outline depicts that symbol.
"""
import hashlib
import io
import re
import zlib

from pdfminer.cmapdb import CMapParser,FileUnicodeMap
from pdfminer.glyphlist import glyphname2unicode
from pypdf import PdfReader

from .native import require

STANDARD_NAMES={'summation','product','integral','radical'}
CMEX_ALIASES={'summationdisplay':'∑','summationtext':'∑'}


def bounded_stream(stream,limit):
    """No unbounded get_data(): fonts/CMaps only, unfiltered or one Flate."""
    data=stream._data
    require(isinstance(data,bytes) and len(data)<=limit,'Encoded stream bound')
    filters=stream.get('/Filter');params=stream.get('/DecodeParms')
    if params is not None:
        require(str(params)=='NullObject' or (isinstance(params,dict) and params.get('/Predictor',1)==1),'Unsupported stream parameters')
    if filters is None:return data
    if isinstance(filters,list):require(len(filters)==1,'Filter chain unsupported');filters=filters[0]
    require(str(filters)=='/FlateDecode','Unsupported stream filter')
    decoder=zlib.decompressobj();result=decoder.decompress(data,limit+1)
    require(len(result)<=limit and not decoder.unconsumed_tail and decoder.eof and not decoder.unused_data,'Decoded stream bound/trailing data')
    return result


def static_encoding(header):
    require(len(header)<=65536,'Font header bound')
    text=header.decode('ascii',errors='strict');text=re.sub(r'%[^\r\n]*','',text)
    names=re.findall(r'/FontName\s*/([A-Za-z0-9_.+-]+)\s+def',text)
    require(len(names)==1 and len(re.findall(r'/Encoding\b',text))==1,'Ambiguous font name/encoding')
    match=re.search(r'/Encoding\s+256\s+array\s+0\s+1\s+255\s*\{\s*1\s+index\s+exch\s*/\.notdef\s+put\s*\}\s*for\s*(.*?)\s*readonly\s+def',text,re.S)
    require(match is not None,'Noncanonical/dynamic encoding unsupported')
    pattern=r'dup\s+(\d{1,3})\s+/([A-Za-z0-9_.]+)\s+put\b';body=match[1]
    require(not re.sub(pattern,'',body).strip(),'Dynamic/unknown encoding statements')
    bindings={}
    for code,glyph in re.findall(pattern,body):
        code=int(code);require(0<=code<=255,'Simple-font byte out of range');bindings.setdefault(code,set()).add(glyph)
    return names[0],bindings


def diagnostic_identity(code,font):
    """Pure font-specific decision. Returns no authoritative replacement."""
    if font.get('error'):return dict(status='unrecoverable',reason=font['error'],diagnostic_unicode=None)
    glyphs=font['encoding'].get(code,set())
    if len(glyphs)>1:return dict(status='ambiguous',reason='Conflicting static encoding bindings',diagnostic_unicode=None)
    if len(glyphs)!=1:return dict(status='unrecoverable',reason='No explicit glyph name for code',diagnostic_unicode=None)
    glyph=next(iter(glyphs));family=re.sub(r'^[A-Z]{6}\+','',font['base_font'])
    value=CMEX_ALIASES.get(glyph) if family=='CMEX10' else None
    if glyph in STANDARD_NAMES:value=glyphname2unicode.get(glyph)
    if value is None:return dict(status='unrecoverable',reason='Glyph name/family outside bounded math identity set',glyph_name=glyph,diagnostic_unicode=None)
    declared=font['unicode'].get(code)
    if declared is not None:return dict(status='ambiguous',reason='Original unresolved decode conflicts with an existing CMap binding',glyph_name=glyph,diagnostic_unicode=None,declared_unicode=declared)
    return dict(status='resolved_diagnostic',glyph_name=glyph,diagnostic_unicode=value,
                basis='Unique embedded font + static byte-to-name encoding + bounded glyph-name identity',declared_unicode=None)


def catalog(page):
    entries={};visited_forms=set();font_count=0
    def walk(resources,path,depth):
        nonlocal font_count
        require(depth<=8,'Form resource depth bound')
        resources=resources.get_object() if hasattr(resources,'get_object') else resources
        if not resources:return
        font_dict=resources.get('/Font',{});font_dict=font_dict.get_object() if hasattr(font_dict,'get_object') else font_dict
        for key,ref in font_dict.items():
            font=ref.get_object();name=str(font.get('/BaseFont','')).lstrip('/')
            indirect=getattr(font,'indirect_reference',None);identity=(indirect.idnum,indirect.generation) if indirect else ('direct',path,str(key))
            if identity in entries:entries[identity]['resource_paths'].append(path+'/Font/'+str(key));continue
            font_count+=1;require(font_count<=256,'Font resource bound')
            entry=dict(base_font=name,resource_paths=[path+'/Font/'+str(key)],object_reference=list(identity) if indirect else None)
            entries[identity]=entry
            try:
                require(str(font.get('/Subtype'))=='/Type1','Only simple Type1 fonts supported')
                require(font.get('/Encoding') is None,'Explicit PDF Encoding override unsupported; no fallback')
                descriptor=font.get('/FontDescriptor');require(descriptor is not None,'Missing font descriptor');descriptor=descriptor.get_object()
                require(str(descriptor.get('/FontName','')).lstrip('/')==name,'Descriptor/font name conflict')
                stream=descriptor.get('/FontFile');require(stream is not None,'Missing embedded Type1 program');stream=stream.get_object()
                data=bounded_stream(stream,1024**2);length=int(stream.get('/Length1',0));require(0<length<=min(65536,len(data)),'Invalid header extent')
                program_name,encoding=static_encoding(data[:length]);require(program_name==name,'Embedded/program font name conflict')
                cmap=font.get('/ToUnicode');mapping=FileUnicodeMap();cmap_bytes=b''
                if cmap:
                    cmap_bytes=bounded_stream(cmap.get_object(),65536);CMapParser(mapping,io.BytesIO(cmap_bytes)).run()
                entry.update(encoding=encoding,unicode=mapping.cid2unichr,fontfile_sha256=hashlib.sha256(data).hexdigest(),
                             header_sha256=hashlib.sha256(data[:length]).hexdigest(),cmap_sha256=hashlib.sha256(cmap_bytes).hexdigest(),
                             program_name=program_name,font_subtype='Type1')
            except (ValueError,UnicodeError,KeyError,zlib.error) as error:entry['error']=str(error)
        xobjects=resources.get('/XObject',{});xobjects=xobjects.get_object() if hasattr(xobjects,'get_object') else xobjects
        for key,ref in xobjects.items():
            obj=ref.get_object()
            if str(obj.get('/Subtype'))!='/Form':continue
            indirect=getattr(obj,'indirect_reference',None);identity=(indirect.idnum,indirect.generation) if indirect else id(obj)
            if identity in visited_forms:continue
            visited_forms.add(identity);require(len(visited_forms)<=256,'Form resource count bound')
            walk(obj.get('/Resources'),path+'/XObject/'+str(key)+'/Resources',depth+1)
    walk(page.get('/Resources'),'page/Resources',0)
    return list(entries.values())


def resolve_page(page,source_page):
    fonts=catalog(page);records=[]
    for char in source_page['characters']:
        match=re.fullmatch(r'\(cid:(\d+)\)',char['text'])
        if not match and char['text']!='\ufffd':continue
        candidates=[f for f in fonts if f['base_font']==char['fontname']]
        record=dict(source_id=char['id'],original_unicode=char['text'],fontname=char['fontname'],
                    native_code=int(match[1]) if match else None,source_unicode_rewritten=False)
        if not match:decision=dict(status='unrecoverable',reason='Replacement has no original simple-font code',diagnostic_unicode=None)
        elif len(candidates)>1:decision=dict(status='ambiguous',reason='Source font name binds multiple distinct resource objects',diagnostic_unicode=None)
        elif not candidates:decision=dict(status='unrecoverable',reason='No matching native font resource',diagnostic_unicode=None)
        else:decision=diagnostic_identity(int(match[1]),candidates[0])
        record.update(decision)
        record['font_evidence']=[{k:v for k,v in f.items() if k not in {'encoding','unicode'}} for f in candidates]
        records.append(record)
    return dict(page_number=source_page['page_number'],scope='Unresolved CID or replacement units only; original Unicode never modified',glyphs=records,
                catalog=[{k:v for k,v in f.items() if k not in {'encoding','unicode'}} for f in fonts])


def resolve(pdf_path,source,page_numbers):
    with pdf_path.open('rb') as f:require(hashlib.file_digest(f,'sha256').hexdigest()==source['source_sha256'],'Wrong font/PDF identity')
    reader=PdfReader(pdf_path)
    return dict(schema_version='native-math-glyph-diagnostics.1',pdf_sha256=source['source_sha256'],
                unicode_role='diagnostic declared glyph identity only; authoritative extraction unchanged',
                pages=[resolve_page(reader.pages[n-1],source['pages'][n-1]) for n in sorted(page_numbers)])
