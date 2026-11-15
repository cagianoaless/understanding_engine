"""Small original-PDF/reference review sheet; never generates or converts SVG."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image,ImageDraw,ImageFont
import pypdfium2 as pdfium

from understanding_engine.viewer import _renderer_geometry


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['inputs','predictions','out']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();assert not a.out.exists();a.out.mkdir()
    local=json.loads(a.inputs.read_bytes());docs={d['id']:d for d in local['documents']}
    rows=[r for r in json.loads(a.predictions.read_bytes())['regions'] if r['role']=='new_component_evaluation']
    font=ImageFont.load_default(size=16);sheet=Image.new('RGB',(1240,1450),'#eef2f5');draw=ImageDraw.Draw(sheet);y=12
    draw.text((15,y),'Six frozen source regions | original PDF (left) and native rule hypotheses (right)',font=font,fill='#17394e');y+=32
    for row in rows:
        doc=docs[row['document']];path=Path(doc['pdf']);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['pdf_sha256']
        with pdfium.PdfDocument(str(path)) as pdf:
            page=pdf[row['page']-1]
            try:
                _renderer_geometry(page,row['geometry']);bitmap=page.render(scale=2.5,may_draw_forms=False,draw_annots=False)
                try:image=bitmap.to_pil().copy().convert('RGB')
                finally:bitmap.close()
            finally:page.close()
        box=row['bbox'];w,h=box[2]-box[0],box[3]-box[1];scale=min(2.5,585/w)
        pixels=[image.width/row['geometry']['width'],image.height/row['geometry']['height']]
        crop=image.crop((round(box[0]*pixels[0]),round(box[1]*pixels[1]),round(box[2]*pixels[0]),round(box[3]*pixels[1]))).resize((round(w*scale),round(h*scale)),Image.Resampling.LANCZOS)
        draw.text((15,y),row['id']+' | page '+str(row['page'])+' | native proxies: '+str(len(row['native_rules'])),font=font,fill='#17394e');y+=27
        sheet.paste(crop,(15,y));sheet.paste(crop,(635,y))
        for rule in row['native_rules']:
            b=rule['bbox'];draw.line([635+(b[0]-box[0])*scale,y+(b[1]-box[1])*scale,635+(b[2]-box[0])*scale,y+(b[3]-box[1])*scale],fill='#d23f43',width=2)
        y+=crop.height+35
    draw.text((15,y),'Red: native straight segment / thin-fill centerline evidence. Not every rule is a fraction. Agent references; no human verification.',font=font,fill='#17394e');y+=28
    sheet.crop((0,0,1240,y)).save(a.out/'six-expression-review.png')


if __name__=='__main__':main()
