"""Small source/prediction contact sheet; never alters inference crops or LaTeX."""
import argparse
import json
from pathlib import Path
import textwrap


def create(evidence, crops, renders, output):
    import pypdfium2 as pdfium
    from PIL import Image, ImageChops, ImageDraw, ImageFont
    inputs = json.loads((evidence / 'inference-inputs.json').read_text())
    names = inputs['execution_order']
    canvas = Image.new('RGB', (1600, 80 + 210 * len(names)), 'white')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=17)
    small = ImageFont.load_default(size=14)
    draw.text((20, 15), 'Frozen original PDF crop (display scaled only)', fill='black', font=font)
    draw.text((800, 15), 'Unmodified model LaTeX in common align* wrapper', fill='black', font=font)
    for index, name in enumerate(names):
        top = 65 + index * 210
        draw.line((10, top - 10, 1590, top - 10), fill='#aaa')
        draw.text((20, top), name, fill='black', font=font)
        source = Image.open(crops / (name + '.png')).convert('RGB')
        scale = min(2, 740 / source.width, 140 / source.height)
        source = source.resize((round(source.width * scale), round(source.height * scale)))
        canvas.paste(source, (20, top + 35))
        path = renders / (name + '.pdf')
        if path.exists():
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
            draw.text((800, top + 30), 'TeX compilation FAILED; no repaired rendering substituted', fill='#a00', font=small)
            prediction = json.loads((evidence / 'outputs/primary' / name / 'prediction.json').read_text())['cleaned_latex']
            excerpt = prediction[:430] + (' ... [excerpt; full text in predictions.json]' if len(prediction) > 430 else '')
            for line_index, line in enumerate(textwrap.wrap(excerpt, width=90)[:7]):
                draw.text((800, top + 55 + 17 * line_index), line, fill='#444', font=small)
    canvas.save(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['evidence', 'crops', 'renders', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    create(args.evidence, args.crops, args.renders, args.output)
