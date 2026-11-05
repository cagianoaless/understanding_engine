"""Generate authored spacing samples; original content/generator CC0-1.0.

Each line has a known intended boundary pattern, not parser-generated truth.
The embedded Vera font retains FONT_LICENSE.txt. Run intentionally, offline;
regression tests use checked-in files. Existing fixtures are never regenerated.
"""

import hashlib
import io
import json
from pathlib import Path

import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).parent


def generate():
    output = io.BytesIO()
    canvas = Canvas(output, pagesize=(720, 400), invariant=1, pageCompression=0)
    samples = []
    page_number = 0

    def line(ident, font, size, y, gap, tracking=0, kern=0, explicit=False,
             expected="AVATAR, next. (x+y)=z"):
        x = 40
        canvas.setFont(font, size)
        if explicit:
            canvas.drawString(x, y, expected)
        else:
            previous = None
            for char in expected:
                if char == " ":
                    x += gap
                    previous = None
                    continue
                if previous is not None:
                    x += tracking + (kern if previous + char in {"AV", "VA"} else 0)
                canvas.drawString(x, y, char)
                x += pdfmetrics.stringWidth(char, font, size)
                previous = char
        samples.append({
            "id": ident, "document_id": "synthetic_spacing", "page_number": page_number,
            "bbox": [30, 400 - y - size * 1.3, 710, 400 - y + size * .5],
            "expected": expected, "verification": "synthetic_designed",
            "design": {"font": font, "font_size": size, "word_gap": gap,
                       "intra_word_tracking": tracking, "AV_VA_kerning": kern,
                       "explicit_space_glyphs": explicit},
        })

    for font in ("Helvetica", "Times-Roman"):
        for size in (6, 8, 10, 12, 18, 24):
            page_number += 1
            prefix = f"{font}-{size}"
            line(prefix + "-plain", font, size, 340, size * .25)
            line(prefix + "-tracked", font, size, 260, size * .28, tracking=size * .12,
                 kern=-size * .04)
            line(prefix + "-kerned", font, size, 180, size * .25, kern=-size * .08)
            line(prefix + "-explicit", font, size, 100, size * .25, explicit=True)
            canvas.showPage()
    page_number += 1
    line("attention-gap-2.49", "Times-Roman", 10, 340, 2.49)
    line("attention-gap-2.68", "Times-Roman", 10, 260, 2.68)
    line("tight-heading-24", "Helvetica", 24, 180, 3.2)
    line("tight-small-8", "Times-Roman", 8, 100, 1.8)
    canvas.showPage()
    page_number += 1
    font_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    font = TTFont("SpacingVera", str(font_path))
    assert all(ord(char) in font.face.charToGlyph for char in "Ω+Ω = Ω, Ω−Ω.caféﬁ")
    pdfmetrics.registerFont(font)
    line("unicode-math", "SpacingVera", 12, 300, 2.6, expected="Ω+Ω = Ω, Ω−Ω.")
    line("ligature-accent", "SpacingVera", 12, 200, 2.6, expected="café ﬁ = Ω.")
    canvas.showPage()
    canvas.save()
    pdf = output.getvalue()
    (ROOT / "spacing.pdf").write_bytes(pdf)
    record = {
        "schema_version": "1.0.0",
        "documents": [{"document_id": "synthetic_spacing", "sha256": hashlib.sha256(pdf).hexdigest()}],
        "samples": samples,
    }
    (ROOT / "spacing_samples.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sha256"]["spacing.pdf"] = hashlib.sha256(pdf).hexdigest()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate()
