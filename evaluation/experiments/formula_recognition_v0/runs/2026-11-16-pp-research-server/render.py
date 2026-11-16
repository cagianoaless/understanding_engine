"""Local cached TeX rendering and compact inspection; never prediction correction."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def render(evidence, crops, destination, figure):
    import pypdfium2 as pdfium
    from PIL import Image, ImageChops, ImageDraw, ImageFont
    destination.mkdir(exist_ok=False)
    inputs = json.loads((evidence / 'inputs.json').read_text())
    names = inputs['execution_order']
    records = {}
    for identifier in names:
        path = evidence / 'outputs-decoder-complete' / identifier / 'prediction.json'
        if not path.exists():
            records[identifier] = {'status': 'NOT_EXECUTED', 'compiled': None}
            continue
        latex = json.loads(path.read_text())['raw_latex']
        if latex is None:
            records[identifier] = {'status': 'NO_PREDICTION', 'compiled': None}
            continue
        document = '\\documentclass{article}\n\\usepackage{amsmath,amssymb}\n\\pagestyle{empty}\n\\begin{document}\n\\begin{align*}\n' + latex + '\n\\end{align*}\n\\end{document}\n'
        source = destination / (identifier + '.tex')
        source.write_text(document)
        command = ['tectonic', '--only-cached', '--untrusted', '--outdir', str(destination), str(source)]
        with (destination / (identifier + '.log')).open('w') as stream:
            process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=30)
        records[identifier] = {'compiled': process.returncode == 0, 'exit_code': process.returncode,
                               'unchanged_body_sha256': hashlib.sha256(latex.encode()).hexdigest(),
                               'scope': 'Common align* display context; compilation is not mathematical correctness'}
    (destination / 'render-results.json').write_text(json.dumps(records, indent=2) + '\n')
    canvas = Image.new('RGB', (1600, 80 + 210 * len(names)), 'white')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=17)
    draw.text((20, 15), 'Original frozen PDF crop (display scaling only)', fill='black', font=font)
    draw.text((800, 15), 'Unmodified PP-FormulaNet-S LaTeX; common align* wrapper', fill='black', font=font)
    for index, identifier in enumerate(names):
        top = 65 + index * 210
        draw.line((10, top - 10, 1590, top - 10), fill='#aaa')
        draw.text((20, top), identifier, fill='black', font=font)
        source = Image.open(crops / (identifier + '.png')).convert('RGB')
        scale = min(2, 740 / source.width, 140 / source.height)
        canvas.paste(source.resize((round(source.width * scale), round(source.height * scale))), (20, top + 35))
        path = destination / (identifier + '.pdf')
        if path.exists() and records[identifier]['compiled']:
            doc = pdfium.PdfDocument(path)
            image = doc[0].render(scale=2).to_pil().convert('RGB')
            difference = ImageChops.difference(image, Image.new('RGB', image.size, 'white')).convert('L')
            box = difference.point(lambda v: 255 if v > 25 else 0).getbbox()
            if box:
                image = image.crop(box)
            scale = min(1, 770 / image.width, 145 / image.height)
            image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))))
            canvas.paste(image, (800, top + 35))
            doc.close()
        else:
            draw.text((800, top + 35), 'No successfully compiled unchanged prediction', fill='#a00', font=font)
    canvas.save(figure)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['evidence', 'crops', 'destination', 'figure']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    render(args.evidence, args.crops, args.destination, args.figure)
