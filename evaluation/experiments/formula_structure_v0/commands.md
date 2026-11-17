# Offline reproduction

Use the existing Python3.11 environment and locked project dependencies. No model, runtime install, remote server, inference or renderer is involved. The retained inputs are tracked JSON records; all frozen crop/PDF identities are recorded inside them, and original PDF/crop bytes need not be reloaded to parse their transcription hypotheses.

```sh
# Run from the repository root. Choose a NEW output directory.
PYTHONPATH="$PWD/src" "$PYTHON" -B \
  evaluation/experiments/formula_structure_v0/evaluate.py \
  --output "$NEW_OUTPUT"
```

The command validates the frozen file hashes/settings/order, parses all eight CodeFormula records without reference inputs, then reads earlier provisional adjudications for comparison. Every example retains exact raw/cleaned strings and provenance. It refuses an existing output destination. `results.json` and `examples/*.json` are deterministic; run.json contains variable timings separately. PP outputs are hash-linked comparison evidence and are not supplied to parsing. Unknown/failed expressions stay in the eight-record denominator.

Observed run: base commit165ea6eb5118aa808cfe857de15860bafedbc3eb, parser latex-subset-v0.1.0, default settings in freeze.json. An initial synthetic safety audit after the first eight parses strengthened the root of a balanced-but-incomplete model string; the recorded safety amendment changes none of the eight deterministic outputs. Initial freeze SHA is preserved in freeze.json, with the original initial freeze and executions outside Git. No grammar/threshold adjustment used reference correctness labels.

On this Mac, the existing project `.venv` launcher is broken and remains untouched. The compatible retained CPython3.11.13 interpreter was used with the existing site-packages directory:

```sh
PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
  "$PYTHON" -B evaluation/experiments/formula_structure_v0/evaluate.py \
  --output "$NEW_OUTPUT"

PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$EXTERNAL_TEST_CACHE" \
  uv run --frozen --offline --no-project --python "$PYTHON" \
  "$PYTHON" -B -m pytest -q
```

`--frozen` has no synchronization effect with `--no-project`; no dependency installation is performed by this host command. GitHub CI uses the unchanged frozen repository workflow. `validate_formula_structure` uses existing jsonschema plus a deterministic rebuild. It validates internal consistency, not original-source correctness or provenance authenticity.

A minimal navigation example:

```python
import json
from pathlib import Path
from understanding_engine.formula_structure_contract import validate_formula_structure

result = json.loads(Path("evaluation/experiments/formula_structure_v0/examples/attn_fraction.json").read_text())
validate_formula_structure(result)
by_id = {n["id"]: n for n in result["nodes"]}
fraction = next(n for n in result["nodes"] if n["type"] == "fraction")
parts = {edge["role"]: by_id[edge["node_id"]]["source_text"]
         for edge in fraction["children"]}
# Numerator/denominator are exact LaTeX substrings, not original PDF text.
assert set(parts) == {"numerator", "denominator"}
assert result["evidence_status"]["mathematical_correctness"] == "unverified"
```

No human_verified/source_verified field is introduced. All source-review comparison labels remain the original agent_visual_checked records with zero independent human verification.

The evaluation runner publishes complete artifact directories using a sibling exclusive lock and staging directory followed by atomic rename, matching the existing output.py policy. Failed writes publish no successful-looking destination; existing directories and symlinks are refused.
