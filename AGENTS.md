# Project rules

- Implement only the approved milestone, on a feature branch; never merge automatically.
- Baseline: Python 3.11. Keep dependencies minimal and exactly pinned; update uv.lock together.
- Extraction and tests run offline. No LLM, OCR, GPU, UI, database, or external service dependencies.
- Preserve backend Unicode, geometry, extraction indices, and PDF provenance. Never silently normalize, dehyphenate, deduplicate, or correct text.
- Keep authoritative characters separate from derived text. Neither extraction order nor geometric sorting is proven reading order.
- Keep paths, wall-clock timestamps, and timings in run.json, outside deterministic extraction output.
- Validate contracts and geometry. Publish complete output directories atomically; do not overwrite existing destinations.
- Add meaningful offline regressions for changes. Run `uv run --frozen --offline pytest` before proposing a merge.
- Keep development and held-out documents separate. Teacher/model suggestions are hypotheses until manually checked against the PDF; never apply model corrections automatically.
- Document limitations and report only behavior actually tested as verified.
