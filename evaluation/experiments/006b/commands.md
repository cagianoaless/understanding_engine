# Execution and reproduction

Run from the repository root. The existing Python 3.11.13 environment and uv
0.7.13 were used; versions are in `environment.json`. No install/sync command
was executed. Offline tests use a writable temporary uv cache because the host's
default uv cache is outside the sandbox's accessible roots.

The actual freeze builder command, executed before runtime discovery, was:

```sh
.venv/bin/python evaluation/experiments/006b/review_pack.py --pdf-map /private/tmp/understanding-engine-e006b/pdf-map.json --output /private/tmp/understanding-engine-e006b/human-review-v1-final > /private/tmp/understanding-engine-e006b/review-package.json
```

The same command with output `human-review-v1-reproduce` and redirected JSON
`reproduced-package.json` produced the same ZIP bytes. Raw source pages were
rendered at scale 1.5 with the existing pypdfium2; original cached extraction
geometry was read to anchor paragraph strips, never structure predictions.
Annotations are deliberate frozen judgments, not regenerated from a candidate.

For a new **atomic** rebuild, create a JSON map containing the paths to the
three registered original PDFs (`source-inputs.json` records this run's paths):

```json
{
  "attention": "/absolute/path/to/1706.03762v7.pdf",
  "bert": "/absolute/path/to/1810.04805v2.pdf",
  "tabpfn_nature_2025": "/absolute/path/to/s41586-024-08328-6.pdf"
}
```

Then run, choosing a nonexistent destination **outside Git**:

```sh
.venv/bin/python evaluation/experiments/006b/reproduce_review.py --pdf-map /absolute/path/to/pdf-map.json --output /private/tmp/006b-independent-review
```

The wrapper preserves the frozen builder/input bytes and stages the entire pack
and ZIP before publishing the directory. It rejects existing destinations and
paths inside this repository. The original builder remains frozen; failed early
pre-freeze builds were not successful artifacts. The atomic rebuild was also
executed locally with `/private/tmp/understanding-engine-e006b/pdf-map.json` and
output `/private/tmp/understanding-engine-e006b/atomic-review-rebuild`; its ZIP
matched the frozen SHA-256. Compare ZIP and per-member hashes against
`review-package.json`. Do not commit PDFs or renders.

Focused Stage A validation and local freeze:

```sh
UV_CACHE_DIR=/private/tmp/understanding-engine-uv-cache uv run --frozen --offline pytest tests/test_experiment006b.py -q
git add evaluation/experiments/006b tests/test_experiment006b.py
git commit -m 'Freeze Experiment 006b development references and human-review package'
```

After that freeze, read-only runtime discovery (exclusive-create output):

```sh
.venv/bin/python evaluation/experiments/006b/discover_runtime.py --output evaluation/experiments/006b/runtime-discovery-expanded.json
```

To reproduce discovery, choose a different, nonexistent output filename; retain
the original evidence. It prints no credentials or runtime context configuration,
does not start daemons and makes no network calls. Host CPU/disk values and
permissions are measurements, so a rerun need not match those bytes.

The official documentation URLs and conclusions are in `preflight.json/md`.
The first discovery was a read-only inline Python PATH/location/disk/platform
check, saved as `runtime-discovery.json`; the committed script broadened that
same check to user CLI locations and the unprivileged host-RAM probe. No Linux
container probe, pull, pip install, dependency resolution, weight fetch, baseline
prediction or Docling conversion command was executed in this experiment.

Full offline suite (also the unchanged GitHub CI test command):

```sh
UV_CACHE_DIR=/private/tmp/understanding-engine-uv-cache uv run --frozen --offline pytest
```

Exact command arguments, stdout/stderr, exit code and duration of the final local
test execution are preserved in `validation-final.json` and `logs/pytest-final.*.log`.
The 255-test execution and its CI result are retained separately in `validation.json`,
`logs/pytest.*.log` and `publication.json`. The final 256-test suite adds an explicit
guard against neural imports in all five experiment helpers. A prior full run
passed 252 tests before additional atomic-publish and summary checks were added.
`publication.json` links the public commits, dedicated PR and CI evidence. Git
credential-helper access from the shell was unavailable, so Git objects/refs and
the PR were published with the GitHub connector; no merge or force-push was used.
