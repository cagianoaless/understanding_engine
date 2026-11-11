"""Authored test PDFs/hypotheses, not model predictions or paper ground truth."""

import hashlib
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from understanding_engine.contracts import json_bytes
from understanding_engine.hybrid import build_hybrid
from understanding_engine.pdf_parser import extract_pdf


def create(directory):
    directory = Path(directory); directory.mkdir()
    path = directory/'authored.pdf'
    pdf = canvas.Canvas(str(path), pagesize=(200,200), invariant=1)
    pdf.setFont('Helvetica',12)
    pdf.drawString(20,140,'x = y + 1'); pdf.drawString(20,120,'z = x / 2')
    tile = Image.new('RGB',(8,8),'#5086a1')
    pdf.drawImage(ImageReader(tile),120,30,width=60,height=60); tile.close()
    pdf.showPage(); pdf.drawString(20,140,'Source only'); pdf.save()
    source=extract_pdf(path)
    def item(ref,label,box,parent,children=None,text=None):
        return {'self_ref':ref,'label':label,'parent':{'$ref':parent},'children':[{'$ref':x} for x in children or []],
                'text':text,'prov':[{'page_no':1,'bbox':dict(zip(['l','t','r','b'],box),coord_origin='TOPLEFT'),'charspan':[0,0]}]}
    document={'body':{'self_ref':'#/body','label':'unspecified','children':[{'$ref':'#/tables/0'},{'$ref':'#/pictures/0'}]},
        'furniture':{'self_ref':'#/furniture','label':'unspecified','children':[]},
        'tables':[item('#/tables/0','table',[15,45,115,90],'#/body',['#/texts/0'])],
        'texts':[item('#/texts/0','formula',[18,48,110,86],'#/tables/0',text='')],
        'pictures':[item('#/pictures/0','picture',[120,110,180,170],'#/body')],
        'pages':{'1':{'page_no':1,'size':{'width':200,'height':200}}}}
    prediction={'provider':'docling','version':'2.148.0','source_pdf_sha256':source['source_sha256'],'status':'available',
        'native':{'document':document,'items':None},'provenance':{'basis':'Authored synthetic interface fixture, no model inference'},'error':None}
    hybrid=build_hybrid(source,[prediction])
    paths={'pdf':path,'extraction':directory/'extraction.json','hybrid':directory/'hybrid.json'}
    paths['extraction'].write_bytes(json_bytes(source)); paths['hybrid'].write_bytes(json_bytes(hybrid))
    manifest={'schema_version':'local-viewer-inputs.1'}
    for key,p in paths.items():
        payload=p.read_bytes(); manifest[key]={'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
    (directory/'manifest.json').write_bytes(json_bytes(manifest))
    return paths, manifest, source, hybrid
