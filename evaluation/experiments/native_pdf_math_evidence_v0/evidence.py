"""Small selected-region export; full page sidecars/predictions remain external."""
import argparse
from collections import Counter
import json
from pathlib import Path

from understanding_engine.contracts import json_bytes


def export(run,out):
    if out.exists():raise ValueError('Refuse to overwrite evidence')
    out.mkdir();read=lambda p:json.loads(p.read_bytes())
    results=read(run/'results.compact.json');predictions=read(run/'predictions.json')['regions']
    (out/'results.json').write_bytes(json_bytes(results))
    catalog={p.stem.removesuffix('-glyphs'):read(p) for p in run.glob('*-glyphs.json')}
    glyph_summary={doc:dict(counts=dict(Counter(g['status'] for p in data['pages'] for g in p['glyphs'])),
                           glyphs=[g for p in data['pages'] for g in p['glyphs']]) for doc,data in catalog.items()}
    selected=[]
    for row in predictions:
        selected.append({k:row[k] for k in ['id','document','page','role','pdf_sha256','geometry','units','native_rules','retained_svg_rules']})
    (out/'selected-evidence.json').write_bytes(json_bytes(dict(schema_version='native-math-selected-evidence.1',regions=selected,
      note='Only selected original units and native/SVG rule evidence; no authoritative Unicode changes, no whole-document text')))
    (out/'glyph-results.json').write_bytes(json_bytes(dict(schema_version='native-math-glyph-results.1',documents=glyph_summary,
      scope='CID/replacement units on selected source pages; counts outside selected formulas are separate diagnostics, not extra benchmark samples',
      known_limit='CMEX9 TeX aliases not enabled; unresolved means not resolved by this bounded implementation, not intrinsically absent from the PDF')))
    examples=[]
    for doc in ['log2026','tabpfn_nature_2025']:
        page_data=read(run/(doc+'-native.json'));byid={p['id']:p for page in page_data['pages'] for p in page['primitives']}
        for row in predictions:
            if row['document']!=doc or not row['native_rules']:continue
            examples.append(dict(region=row['id'],pdf_sha256=row['pdf_sha256'],page=row['page'],geometry=row['geometry'],
                 primitives=[byid[r['primitive_id']] for r in row['native_rules']],rule_proxies=row['native_rules']))
    (out/'native-examples.json').write_bytes(json_bytes(dict(schema_version='native-math-examples.1',examples=examples)))
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();export(a.run,a.out)


if __name__=='__main__':main()
