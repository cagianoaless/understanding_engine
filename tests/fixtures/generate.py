"""Regenerate small synthetic PDFs offline using pinned development dependencies.

Original fixture content and this generator are dedicated to the public domain
under CC0-1.0. The embedded Vera font retains its accompanying license.
Tests use checked-in PDFs, never regenerate fixtures implicitly.
"""

import hashlib
import io
import json
from pathlib import Path

import reportlab
from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import (ArrayObject, ByteStringObject, DecodedStreamObject,
                           FloatObject, NameObject, NumberObject, RectangleObject)
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).parent


def document(pages) -> bytes:
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(300, 200), invariant=1, pageCompression=0)
    for draw in pages:
        draw(canvas)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def text(value, x=40, y=160):
    def draw(canvas):
        canvas.setFont("Helvetica", 12)
        canvas.drawString(x, y, value)
    return draw


def rewrite(content, modify=None, password=None):
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(content)).pages:
        if modify:
            modify(page)
        writer.add_page(page)
    # Fixed fixture-only file IDs make legacy encryption reproducible.
    writer._ID = ArrayObject([ByteStringObject(b"fixture-id-00001")] * 2)
    if password is not None:
        writer.encrypt(password, owner_password="owner-fixture-password", algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def main():
    single = document([text("Scientific PDF")])
    (ROOT / "single.pdf").write_bytes(single)
    (ROOT / "multi.pdf").write_bytes(document([text("First page"), text("Second page")]))

    font_dir = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("FixtureVera", str(font_dir / "Vera.ttf")))

    def unicode_page(canvas):
        canvas.setFont("FixtureVera", 12)
        canvas.drawString(40, 160, "café ﬁ Ω −")
    (ROOT / "unicode.pdf").write_bytes(document([unicode_page]))
    (ROOT / "FONT_LICENSE.txt").write_bytes((font_dir / "bitstream-vera-license.txt").read_bytes())

    def unicode_units(canvas):
        canvas.setFont("FixtureVera", 12)
        canvas.drawString(40, 160, "café ﬁ")
        canvas.drawString(40, 130, "Next line")

    def decompose_mapping(page):
        # One accent glyph intentionally maps to two Unicode code points.
        for font in page["/Resources"]["/Font"].values():
            font = font.get_object()
            if "/ToUnicode" in font:
                cmap = font["/ToUnicode"].get_data()
                assert b"<00E9>" in cmap
                replacement = DecodedStreamObject()
                replacement.set_data(cmap.replace(b"<00E9>", b"<00650301>"))
                font[NameObject("/ToUnicode")] = replacement
    (ROOT / "unicode_units.pdf").write_bytes(rewrite(document([unicode_units]), decompose_mapping))

    def verbatim(canvas):
        text("inter-", 40, 160)(canvas)
        text("pretation", 40, 130)(canvas)
        text("E", 200, 100)(canvas)
        text("E", 200, 100)(canvas)
    (ROOT / "verbatim.pdf").write_bytes(document([verbatim]))
    (ROOT / "whitespace.pdf").write_bytes(document([text("   ")]))

    def blank(canvas):
        pass

    def image(canvas):
        canvas.drawImage(ImageReader(Image.new("RGB", (2, 2), "navy")), 40, 80, 80, 80)
    (ROOT / "empty.pdf").write_bytes(document([blank]))
    (ROOT / "image.pdf").write_bytes(document([image]))
    (ROOT / "mixed.pdf").write_bytes(document([text("Text page"), blank, image]))

    def columns(canvas):
        text("Left one", 20, 160)(canvas)
        text("Left two", 20, 130)(canvas)
        text("Right one", 170, 160)(canvas)
        text("Right two", 170, 130)(canvas)
    (ROOT / "columns.pdf").write_bytes(document([columns]))

    rotations = PdfWriter()
    for degrees in (0, 90, 180, 270):
        page = PdfReader(io.BytesIO(single)).pages[0]
        page.rotate(degrees)
        rotations.add_page(page)
    rotations._ID = ArrayObject([ByteStringObject(b"fixture-id-00001")] * 2)
    with (ROOT / "rotations.pdf").open("wb") as stream:
        rotations.write(stream)

    def cropped_content(canvas):
        text("Visible", 40, 150)(canvas)
        text("Outside crop", 40, 20)(canvas)

    def crop(page):
        page.cropbox = RectangleObject((20, 60, 280, 180))
    cropped = document([cropped_content])
    (ROOT / "cropped.pdf").write_bytes(rewrite(cropped, crop))

    def shifted(page):
        page.add_transformation(Transformation().translate(10, 20))
        page.mediabox = RectangleObject((10, 20, 310, 220))
        page.cropbox = RectangleObject((30, 80, 290, 200))
        page[NameObject("/UserUnit")] = FloatObject(2)
    (ROOT / "shifted.pdf").write_bytes(rewrite(single, shifted))
    (ROOT / "encrypted.pdf").write_bytes(rewrite(single, password="fixture-password"))
    (ROOT / "encrypted_empty_password.pdf").write_bytes(rewrite(single, password=""))
    (ROOT / "invalid.pdf").write_bytes(b"This is not a PDF.\n")

    def broken_rotation(page):
        page[NameObject("/Rotate")] = NumberObject(45)
    (ROOT / "bad_rotation.pdf").write_bytes(rewrite(single, broken_rotation))
    manifest = {
        "provenance": "Synthetic, generated locally; original text/content CC0-1.0; embedded Vera font license in FONT_LICENSE.txt",
        "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob("*.pdf"))},
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
