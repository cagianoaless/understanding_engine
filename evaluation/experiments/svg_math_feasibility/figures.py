"""Small equation-only inspection figures, not accuracy measurements."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image,ImageDraw,ImageFont
import pypdfium2 as pdfium

from understanding_engine.viewer import _renderer_geometry
from understanding_engine.contracts import json_bytes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ['pdf','source','predictions','svg-render','out']:parser.add_argument('--'+k,type=Path,required=True)
    a=parser.parse_args();assert not a.out.exists();a.out.mkdir()
    source=json.loads(a.source.read_bytes());predictions=json.loads(a.predictions.read_bytes())['equations']
    assert hashlib.sha256(a.pdf.read_bytes()).hexdigest()==source['source_sha256']
    render=json.loads((a.svg_render/'render.json').read_bytes());assert render['complete'] and render['viewport']==[612,792] and render['device_scale']==3
    svg_image=Image.open(a.svg_render/'svg-page4.png').convert('RGB');assert svg_image.size==(1836,2376)
    actual_glyphs={g['id']:g for g in render['glyphs']};font=ImageFont.load_default(size=16)
    evidence=[]
    with pdfium.PdfDocument(str(a.pdf)) as pdf:
        page=pdf[3]
        try:
            _renderer_geometry(page,source['pages'][3]['geometry']);bitmap=page.render(scale=2.5,may_draw_forms=False,draw_annots=False)
            try:original=bitmap.to_pil().copy().convert('RGB')
            finally:bitmap.close()
        finally:page.close()
    original.save(a.out/'pdf-page4.png')
    for pred in predictions:
        box=pred['box'][:]
        # Replacement glyph extents can lie above the original formula. Retain
        # the complete intersecting context line, rather than clip/hide it.
        tops=[actual_glyphs[u['id']]['bbox'][1] for u in pred['units'] if u['id'] in actual_glyphs]
        box[1]=min([box[1]]+tops)
        selected={u['id'] for u in pred['source_units']}
        context=[c for c in source['pages'][3]['characters'] if c['id'] not in selected and c['bbox'][1]<=box[1]<=c['bbox'][3]]
        if context:box[0]=min([box[0]]+[c['bbox'][0] for c in context]);box[1]=min(c['bbox'][1] for c in context)-.5
        box=[box[0]-2,box[1],box[2]+2,box[3]];w,h=box[2]-box[0],box[3]-box[1]
        scale=min(2.1,775/w);cw=int(w*scale);ch=int(h*scale);cellw=800;rowh=ch+58
        canvas=Image.new('RGB',(1600,rowh*2+72),'#eef2f5');draw=ImageDraw.Draw(canvas)
        draw.text((16,10),pred['id'].upper()+' | original PDF vs supplied SVG; agent inspection, no independent ground truth',fill='#15334a',font=font)
        def panel(image,at,title,source_scale):
            x,y=at;crop=image.crop(tuple(round(v*source_scale) for v in box)).resize((cw,ch),Image.Resampling.LANCZOS)
            draw.rectangle((x-3,y-3,x+cw+3,y+ch+3),fill='white');canvas.paste(crop,(x,y));draw.text((x,y-24),title,fill='#15334a',font=font)
        top=62;bottom=top+rowh
        panel(original,(16,top),'A. Original PDF, exact source identity',2.5)
        panel(svg_image,(816,top),'B. SVG, existing local font fallback',3)
        panel(svg_image,(16,bottom),'C. Actual SVG-rendered glyph extents',3)
        panel(original,(816,bottom),'D. SVG groups linked to original font boxes',2.5)
        def mapped(b,x,y):return [x+(b[0]-box[0])*scale,y+(b[1]-box[1])*scale,x+(b[2]-box[0])*scale,y+(b[3]-box[1])*scale]
        for u in pred['units']:
            g=actual_glyphs.get(u['id'])
            if g:draw.rectangle(mapped(g['bbox'],16,bottom),outline='#cf3f3f' if u['text']=='\ufffd' else '#2e75b8',width=1)
        src={u['id']:u for u in pred['source_units']};bindings={b['svg_id']:b['source_ids'][0] for b in pred['bindings'] if len(b['source_ids'])==1}
        def union(ids):
            boxes=[src[bindings[i]]['box'] for i in ids if i in bindings]
            return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else None
        for u in pred['source_units']:draw.rectangle(mapped(u['box'],816,bottom),outline='#d3dce2',width=1)
        for f in pred['candidates']['svg_only']['relations']['fractions']:
            for role,color in [('numerator','#00875a'),('denominator','#b66b00')]:
                b=union(f[role])
                if b:draw.rectangle(mapped(b,816,bottom),outline=color,width=2)
            draw.line(mapped(f['bar_bbox'],816,bottom),fill='#8537a6',width=3)
        for rel in pred['candidates']['svg_only']['relations']['indices']:
            base,script=union(rel['base']),union(rel['script'])
            if base and script:
                b=mapped(base,816,bottom);s=mapped(script,816,bottom)
                draw.line(((b[0]+b[2])/2,(b[1]+b[3])/2,(s[0]+s[2])/2,(s[1]+s[3])/2),fill='#2970b0',width=1)
        draw.text((16,canvas.height-35),'Green: numerator | amber: denominator | purple: fraction bar | blue: script hypothesis (may be wrong) | red: U+FFFD',fill='#244454',font=font)
        dest=a.out/(pred['id']+'.png');canvas.save(dest)
        evidence.append(dict(equation=pred['id'],file=dest.name,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),bytes=dest.stat().st_size))
    (a.out/'figures.json').write_bytes(json_bytes(dict(figures=evidence,pdf_sha256=source['source_sha256'],svg_renderer=render['browser'],
         note='PDF font boxes are not ink extents; SVG boxes use actual local fallback-font metrics. Lines and glyphs are not corrected.')))


if __name__=='__main__':main()
