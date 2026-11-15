"""Bounded native Type1 header/CMap diagnostics. No font execution or correction.

Glyph names are evidence, not a general glyph-name-to-Unicode decoder. This
diagnostic is not consumed by the reconstruction candidate or its scoring.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re

from pdfminer.cmapdb import CMapParser,FileUnicodeMap
from pypdf import PdfReader

from understanding_engine.contracts import json_bytes


def header_names(data):
    if len(data)>65536:raise ValueError('Header inspection bound exceeded')
    return {int(code):name.decode('ascii') for code,name in re.findall(br'\bdup\s+(\d{1,3})\s+/([A-Za-z0-9_.]+)\s+put\b',data)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ['pdf','source','out']:parser.add_argument('--'+k,type=Path,required=True)
    parser.add_argument('--page',type=int,default=4);a=parser.parse_args();assert not a.out.exists()
    source=json.loads(a.source.read_bytes());assert hashlib.sha256(a.pdf.read_bytes()).hexdigest()==source['source_sha256']
    page=source['pages'][a.page-1];reader=PdfReader(a.pdf);fonts={};records=[]
    for resource,ref in reader.pages[a.page-1]['/Resources']['/Font'].items():
        font=ref.get_object();name=str(font.get('/BaseFont','')).lstrip('/');descriptor=font.get('/FontDescriptor')
        if not descriptor:continue
        stream=descriptor.get_object().get('/FontFile')
        if not stream:continue
        # Bound the decoded font stream; never evaluate its PostScript program.
        stream=stream.get_object();data=stream.get_data();length=int(stream.get('/Length1',0))
        if not 0<length<=65536 or len(data)>1024**2:continue
        names=header_names(data[:length]);cmap=font.get('/ToUnicode');mapping=FileUnicodeMap();cmap_bytes=b''
        if cmap:
            cmap_bytes=cmap.get_object().get_data()
            if len(cmap_bytes)>65536:continue
            CMapParser(mapping,io.BytesIO(cmap_bytes)).run()
        fonts[name]=dict(resource=resource,names=names,unicode=mapping.cid2unichr,fontfile_sha256=hashlib.sha256(data).hexdigest(),cmap_sha256=hashlib.sha256(cmap_bytes).hexdigest())
    for c in page['characters']:
        match=re.fullmatch(r'\(cid:(\d+)\)',c['text']);font=fonts.get(c['fontname'])
        if match and font:
            code=int(match[1]);records.append(dict(source_id=c['id'],original_unicode=c['text'],font=c['fontname'],native_code=code,
               native_glyph_name=font['names'].get(code),declared_unicode=font['unicode'].get(code),resource=font['resource'],
               fontfile_sha256=font['fontfile_sha256'],cmap_sha256=font['cmap_sha256'],status='font_name_evidence_only; Unicode not rewritten'))
    a.out.write_bytes(json_bytes(dict(schema_version='svg-math-font-evidence.1',pdf_sha256=source['source_sha256'],page=a.page,glyphs=records,
        semantic_recovery_score=None,reason='No generic Unicode recovery implemented; header names inspected as diagnostic evidence only')))


if __name__=='__main__':main()
