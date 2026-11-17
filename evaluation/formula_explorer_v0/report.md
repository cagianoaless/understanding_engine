# Formula Explorer Demo v0

**The end-to-end local interaction passed on the verified original Attention PDF.** An actual browser selected the frozen equation crop, expanded Fraction, selected Numerator and Denominator, observed different exact LaTeX highlights and returned to the same PDF crop. The optional rejected LoG example also passed with explicit unresolved/partial rejection labels.

This is an interface demonstration over retained evidence, not a recognition-quality experiment, mathematical validation, new model run or source-symbol alignment result.

## Input identities and preparation

Base PR29 / `60d4e7921e5e24d79aa57a3aa6f1ae3cdd6debb8`. Registered originals/extractions were present; their lengths and SHA-256 values were checked before use. Both original crop PNG hashes, original CodeFormula prediction artifact/canonical-record hashes, raw/cleaned strings and frozen graph identities were also verified. `input-readiness.json` records these checks without private paths.

| Example | Original PDF SHA-256 | Page | Preserved graph SHA-256 |
|---|---|---:|---|
| attn_fraction | bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697 | 4 | 4c25eea1216f9f02111c8071cf44b3a55f1a3f3c1a6ffdff7a2c0a73c4460d4c |
| log_eq2 | ad6d6d00a432f2f7e2e3b1c77a5e4ef80ecf2080300713d1c680de1f3fd79060 | 4 | 5cfc66578506cdbfad1be71748576aa94e897da801a511ac1b007d389630e266 |

No matching retained Attention/LoG hybrid was found. Rather than substitute another document or fabricate layout evidence, the explicit preparation helper used the unchanged `build_hybrid(source, [])` on each verified extraction. These new **source-only** hybrids contain no layout predictions and preserve all original characters. They remain external:31,673,524 B Attention and90,888,919 B LoG. No real PDF extraction, recognition, graph regeneration/output repair, source-reference edit or model/runtime change occurred. The graph's existing replay validator runs for consistency, without changing its stored bytes.

## Observed browser interactions

Tests used the already installed Brave executable, Chromium protocol product Chrome146.0.7680.164, and existing Node24.2.0 for a test-only CDP harness. No Browser-plugin JavaScript execution tool was exposed after discovery, so that plugin was not used; no dependency or alternative browser was installed. Each run created its own temporary profile and loopback server, disabled background integrations and kept browser security sandboxing enabled. Personal profiles, sessions and unrelated processes were untouched.

Automated **Attention** checks:

- Original page4 rendered, with identity-bound graph and the session fragment removed from the address bar.
- A real pointer event inside the visible original crop activated the formula panel.
- Fraction disclosure expanded; actual pointer clicks selected its existing Numerator/Denominator child nodes.
- Numerator Unicode span `[58,73)`, token span `[50,65)` marked exactly `{ Q K ^ { T } }`.
- Denominator Unicode span `[74,97)`, token span `[66,85)` marked exactly `{ \sqrt { d _ { k } } }`.
- The complete displayed LaTeX stayed character-for-character identical to the original graph input; child roles and node diagnostics matched the graph.
- PDF overlay stayed exactly at bbox `[189.3976867756,460.0679132,420.38849780439995,495.7921212]`, with **one rectangle**, for both node selections. No denominator/symbol box appeared.
- Return-to-crop and reset worked. The interface exposed unverified-transcription and crop-only provenance labels.
- The actual browser also exercised a synthetic non-BMP helper check: selecting code-point span `[0,1)` from `𝛼+x` returns the complete `𝛼`. This is a Unicode implementation check, not evidence about the real formula's symbol correctness.

Automated **LoG** checks:

- The exact original PDF/page4 and original rejected graph loaded in a separate context.
- Root selection exposed its full model substring and parsed-fragment children.
- Global text included **REJECTED AS A COMPLETE FORMULA**, with partial parsing and unverified mathematical correctness; selected-node text retained the rejected-formula context.
- PDF overlay stayed at the frozen **whole** LoG crop. Return/reset and the browser non-BMP helper check passed.

Both final runs reported zero browser exceptions and zero external **page** requests. This measures the tested page's requests, not every operating-system/browser background packet. Owned browser/server processes exited with code0. Native symbol/subexpression geometry and source-glyph alignment remain unavailable. No automatic semantic assertions, formula corrections or explanations were introduced.

## Actual visual evidence

[Attention denominator screenshot](attention-denominator.png) and [rejected LoG screenshot](log-rejected.png) are unmodified captures from completed browser runs. The agent inspected both rendered screenshots: original PDF crop, LaTeX mark, tree selection and uncertainty/rejection labels were visible. These are **agent visual checks**, not independent human review.

`browser-attention.json` and `browser-log2026.json` preserve normalized interaction assertions, exact spans/overlay boxes, browser versions, startup observations and cleanup status. Full logs and additional screenshots stay outside Git with byte/hash manifests. Original PDFs, bulk extractions/hybrids, browser profiles, private launch paths and session tokens are not committed.

## Regression/security verification and limitations

Offline regressions cover graph/PDF/hash/page/frame mismatch, corrupted spans, invalid/missing node IDs, exact Unicode slicing, deterministic node navigation, retained diagnostics, partial graphs, source-only preparation without PDF extraction, default viewer behavior, one-time validation, authorization/Host/origin/CSP/path boundaries and absence of node-level PDF boxes. No model libraries or network services are needed by the implementation. Full test/CI results are recorded in validation.json and on the PR.

The first CI run (43998646436) stopped during collection: the new test imported the experimental `evaluation` directory as a package, relying on a repository-root PYTHONPATH present in the initial Mac run. New test/preparation helpers now load the existing experimental files by explicit path with standard-library `runpy`, matching existing test conventions. No old files or runtime behavior were changed by this correction. The full Mac suite was rerun without the repository-root PYTHONPATH: **758 passed in30.61s**. Final exact-head Linux CI is reported on the PR; the original failed run is preserved.

The default viewer's source selection remains available without demo activation. Only viewer.py/viewer_assets.py change among prior tracked files; frozen experiments/predictions, parser contracts/grammar, character IDs and source geometry remain byte-identical.

Manual human clicking, cross-browser testing, accessibility audit, arbitrary Unicode formula datasets and larger-document performance testing are **not executed**. API invalid-request boundaries are covered offline; an injected technical API-error alert was not separately exercised in the real browser. Inputs with unsupported page frames fail rather than guessing transformations. One graph is loaded per document context; this is not automatic formula detection or a document browser. New preparation outputs use the existing atomic staging/lock publication policy; temporary local bundles may need recreation if the OS removes them.

## Reproduce and stop boundary

See [launch documentation](../../docs/formula-explorer-demo-v0.md) and commands.md. The provided Mac-local launchers reference verified original inputs and the new external source-only bundles. No missing files blocked either tested example.

The success criterion is satisfied for this controlled demonstration: users can move from an original PDF crop into a frozen syntactic hypothesis, inspect exact model-LaTeX substrings and return to the whole original region. **Model text remains distinct from authoritative PDF text, and no source-symbol correspondence is invented.** No viewer explanation system, new inference, production semantic AST, additional benchmark or integration beyond this opt-in demonstration was implemented.
