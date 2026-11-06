"""Rebuild the frozen, source-only review pack. No parser/model predictions.

Run with the existing locked Python 3.11 environment. Copyrighted renders stay
outside Git. Deliberately supports only the six audited page transformations.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def transform(box, geometry, pixels, inverse=False):
    """Native pdfplumber top-origin points <-> raster pixel edges.

    Refuse transformations not verified for this review pack, rather than
    guessing about rotated pages, UserUnit, or crop offsets.
    """
    w, h = geometry["width"], geometry["height"]
    if (geometry["rotation"] != 0 or geometry["raw_rotation"] != 0
            or geometry["user_unit"] != 1
            or geometry["bbox"] != [0, 0, w, h]
            or geometry["mediabox"] != [0, 0, w, h]
            or geometry["cropbox"] != [0, 0, w, h]):
        raise ValueError("Unaudited page transformation")
    if (len(box) != 4 or len(pixels) != 2
            or not all(math.isfinite(v) for v in (*box, *pixels, w, h))
            or min(w, h, *pixels) <= 0
            or box[0] >= box[2] or box[1] >= box[3]):
        raise ValueError("Malformed geometry")
    factors = (pixels[0] / w, pixels[1] / h) * 2
    return [v / f if inverse else v * f for v, f in zip(box, factors)]


def build(pdf_paths, destination):
    # Late imports: ordinary test collection never imports a neural stack.
    import pypdfium2 as pdfium
    from PIL import ImageDraw

    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    # Verify all originals before writing anything.
    annotations = json.loads((HERE / "annotations.json").read_text())
    geometry = json.loads((HERE / "page_geometry.json").read_text())
    for doc in annotations["documents"]:
        if sha256(pdf_paths[doc["document_id"]]) != doc["source_sha256"]:
            raise ValueError("Original PDF hash mismatch: " + doc["document_id"])
    destination.mkdir(parents=True)
    try:
        for page in annotations["pages"]:
            name = page["id"]
            with pdfium.PdfDocument(pdf_paths[page["document_id"]]) as pdf:
                source = pdf[page["page_number"] - 1]
                try:
                    g = geometry[name]
                    if (source.get_rotation() != 0
                            or abs(source.get_width() - g["width"]) > 0.001
                            or abs(source.get_height() - g["height"]) > 0.001):
                        raise ValueError("Render geometry disagrees with frozen metadata")
                    bitmap = source.render(scale=1.5)
                    try:
                        raw = bitmap.to_pil().convert("RGB")
                    finally:
                        bitmap.close()
                finally:
                    source.close()
            overlay = raw.copy()
            draw = ImageDraw.Draw(overlay)
            def mark(box, color, label):
                coords = transform(box, g, raw.size)
                draw.rectangle(coords, outline=color, width=2)
                draw.text((coords[0] + 2, coords[1] + 1), label,
                          fill=color, stroke_width=1, stroke_fill="white")
            for i, window in enumerate(page["windows"]):
                mark(window, "green", "window " + str(i + 1))
                crop = raw.crop(tuple(round(v) for v in transform(window, g, raw.size)))
                path = destination / "crops" / f"{name}-w{i+1}.png"
                path.parent.mkdir(exist_ok=True)
                crop.save(path)
            for region in page["regions"]:
                mark(region["bbox"], "red", region["id"].split(":")[-1])
            for decision in page["paragraph_decisions"]:
                for strip in decision["line_strips"]:
                    mark(strip, "blue", decision["id"].split(":")[-1])
            for folder, img in (("raw", raw), ("overlays", overlay)):
                path = destination / folder / (name + ".png")
                path.parent.mkdir(exist_ok=True)
                img.save(path)
        for filename in ("annotations.json", "page_geometry.json", "plan.json",
                         "review_protocol.md", "human-review-form.json"):
            (destination / filename).write_bytes((HERE / filename).read_bytes())
        manifest = [{"path": str(p.relative_to(destination)), "bytes": p.stat().st_size,
                     "sha256": sha256(p)} for p in sorted(destination.rglob("*")) if p.is_file()]
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        archive = destination.with_suffix(".zip")
        if archive.exists():
            raise FileExistsError(archive)
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(destination.rglob("*")):
                if p.is_file():
                    info = zipfile.ZipInfo(str(p.relative_to(destination)), (1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    z.writestr(info, p.read_bytes())
        return {"archive": str(archive), "bytes": archive.stat().st_size,
                "sha256": sha256(archive), "files": manifest,
                "verification": "agent_visual_checked", "human_review": "pending"}
    except BaseException:
        # Partial output deliberately remains identifiable; no manifest means
        # an incomplete pack. Never print a successful archive record on error.
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-map", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(json.loads(args.pdf_map.read_text()), args.output), indent=2))
