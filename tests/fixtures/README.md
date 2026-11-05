# Synthetic regression fixtures

All PDFs are small, generated locally by `generate.py`; no papers or downloaded
datasets are included. Original fixture text, content, and generator are dedicated
to the public domain under [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/).
The embedded Bitstream Vera font retains the complete notice in `FONT_LICENSE.txt`.
ReportLab supplies that font; no system font discovery is used.

Regenerate intentionally with the pinned development environment:

```sh
uv run --frozen --offline python tests/fixtures/generate.py
```

Tests never regenerate fixtures. `manifest.json` records their byte hashes.
ReportLab's invariant mode and fixed fixture-only IDs make regeneration
reproducible. The RC4 encryption is only for input rejection tests.

| Fixture | Purpose |
| --- | --- |
| single, multi | Known text, dimensions, positions, and page offsets |
| unicode | Accented Latin, a ligature, Greek, and a mathematical minus |
| unicode_units | One accent glyph maps to decomposed `e` + U+0301; two lines test references |
| verbatim | Hyphenated lines and duplicate overprinted glyphs |
| empty, image, whitespace | Valid PDFs with no non-whitespace text |
| mixed | Text, blank, and image-only pages in one document |
| columns | Both columns retained; reading order is not an acceptance claim |
| rotations | 0, 90, 180, 270 degree pages |
| cropped | CropBox recorded while text outside the crop is retained |
| shifted | Nonzero MediaBox origin, translated text, CropBox, UserUnit=2 |
| invalid, encrypted, encrypted_empty_password, bad_rotation | Explicit input rejection |

Expected text and analytic Helvetica coordinates are maintained independently in
the tests. Backend parity tests additionally check faithful copying; parity alone
is not evidence that the PDF was interpreted correctly. The decomposed mapping
renders the same accented glyph while intentionally testing a multi-codepoint
Unicode mapping.
