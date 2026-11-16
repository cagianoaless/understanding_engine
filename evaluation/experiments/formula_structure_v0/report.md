# Formula Structure v0 — offline research evaluation

**Yes, noisy transcriptions can yield useful navigable syntax while remaining explicitly fallible.** Six of eight retained CodeFormulaV2 outputs were consumed by the v0 grammar. Both LoG outputs retain partial fragments but are rejected as complete formulas. Crucially, both Nature transcriptions parse despite the earlier provisional review identifying lost vector boldness. Parsing does not establish mathematical correctness, source truth or glyph alignment.

## Inputs and separation

Base PR28 / `165ea6eb5118aa808cfe857de15860bafedbc3eb`. All eight original PR26 records were reused without alteration, including raw_model_output, cleaned_latex, native generation observations and crop/PDF identities. The parser consumes the original cleaned_latex exactly and separately preserves the raw string. Formula provenance includes original artifact byte hash and canonical-record hash, model/checkpoint, page/region and crop SHA-256. Original source characters/Unicode/fonts/geometry remain external original-PDF evidence; no token-level PDF association is inferred.

The experiment did not invoke a recognizer, GPU, OCR, renderer, API or network service for parsing. No model/package was acquired. PP outputs from PR28 are retained only as hash-linked comparison evidence; no second-model parsing/ensemble was introduced. No original references, production contracts, historical experiments or held-out data were changed.

The candidate grammar/settings were frozen after synthetic tests before the first eight parses. A later synthetic safety audit strengthened the root status for otherwise balanced strings whose model generation is explicitly incomplete; that amendment is recorded in freeze.json. The real incomplete LoG output was already unresolved: **all eight deterministic examples and results remained byte-identical**, including diagnostics. The API also rejects malformed settings objects instead of silently taking defaults. These were input-safety fixes, not accuracy tuning or repair using references. The initial freeze is retained externally with its recorded SHA-256.

`parse_inputs` has no reference/score arguments. All eight results are constructed and validated before earlier adjudications are read for comparison. The Nature Greek-alpha versus Latin-a discrepancy stays unchanged; the parser neither corrects nor scores that glyph. Every quality comparison remains **agent_visual_checked**, with **zero independent human verifications**. This small development-exposed set is not independent validation.

## Eight-image accounting

| Prediction | Grammar result | Complete-formula disposition | Identifier/grouping diagnostics | Unresolved nodes | Prior provisional source review |
|---|---|---|---:|---:|---|
| attn_fraction | parsed | inspect with ambiguities | 3 | 0 | correct |
| attn_heads | parsed | inspect with ambiguities | 4 | 0 | correct |
| attn_ffn | parsed | inspect with ambiguities | 2 | 0 | correct |
| attn_positional | parsed | inspect with ambiguities | 14 | 0 | correct |
| nature_weights | parsed | inspect with ambiguities | 1 | 0 | incorrect: vector bold lost; alpha conflict separate |
| nature_softmax | parsed | inspect syntax only | 0 | 0 | incorrect: vector bold lost |
| log_eq2 | partial | reject | 1 | 1 | incomplete/unknown |
| log_eq4 | partial | reject | 2 | 2 | incorrect: extraneous/malformed prose |

Denominator remains **8**: **6 parsed**, **2 partial**, **0 fully rejected without useful fragments**. Both partial results are nevertheless **rejected as complete formulas**. There are **3 unresolved nodes**, **27 identifier/grouping diagnostics**, and one additional explicit cross-line relation-scope diagnostic. These are diagnostic events, not 27 independently verified identifier errors.

All **8 mathematical-correctness states remain unverified** and **0 have token-to-PDF glyph alignment**. Six results are inspectable, never automatically source_verified. `nature_softmax` is a concrete counterexample: balanced/supported syntax with no grouping diagnostic still transcribes the source notation incorrectly under the existing review. Four of six fully consumed outputs were previously provisionally source-faithful; two were not. Those labels do not enter the parser or imply calibrated acceptance precision.

## Recovered syntax, with limits

| Node kind | Fully parsed six | Partial LoG fragments | Total |
|---|---:|---:|---:|
| Fractions | 2 | 2 | 4 |
| Radicals | 1 | 0 | 1 |
| Summations | 2 | 3 | 5 |
| Subscript attachments | 17 | 10 | 27 |
| Superscript attachments | 5 | 4 | 9 |
| Delimited groups | 13 | 9 | 22 |

These counts describe **generated-syntax nodes**, not reference-component correctness. In particular the old reference inventory excludes some max-index scripts; its denominators cannot be substituted for these node counts. Nodes inside a rejected formula remain explicitly partial evidence.

Fractions expose numerator/denominator links; radicals expose radicands/optional degree; scripts link a literal syntactic base; sums expose operator and explicit limits without inventing summand scope or variable binding. Seven explicit relation nodes exist across complete/partial subtrees, but positional-encoding line breaks prevent an invented cross-row relation chain. Layout markers remain navigable tokens.

`Attention` is a run of individual letters; `head_1` is not silently manufactured from `h e a d _1`. The latter script attaches to literal `d`, faithfully reflecting the LaTeX spelling while failing to establish the likely intended human identifier. Spaced numeric digits in positional encoding are not joined into a confidently recognized numeral. Explicit operatorname grouping in synthetic cases is kept distinct from bare letters and from verified semantic functions. `\text{softmax}` stays a textual-name hypothesis; `\mathbf{x}` remains distinguishable from plain x. No function application, implicit multiplication, arithmetic precedence or equivalence is inferred.

For LoG(2), fraction/sum fragments remain visible before unsupported intertext; native non-EOS termination is explicitly incomplete. For LoG(4), the initial multiword text is unresolved and later intertext prevents full consumption. No surrounding prose is discarded, no missing closure guessed and no expected equation substituted. The parser may expose useful fragments from a mathematically wrong output, which is why the whole-expression rejection and evidence-role fields must travel with every subtree.

## Synthetic validation and performance

Synthetic unit tests cover known fraction/radical/script/limit structures, exact Unicode/code-point spans, deterministic IDs/serialization, glyph typography, ambiguous names, unknown/incomplete termination, malformed/prose/macro inputs, cross-line scope, resource guards and graph/provenance tampering. Seeded adversarial cases verify bounded, non-executing failure behavior. These tests measure authored syntax behavior, **not recognition accuracy on scientific PDFs**.

The first local API call took9.395ms, including cold provenance-schema setup; subsequent calls took0.202–1.695ms in this one run. Measurements exclude file loading and post-build graph revalidation; run.json's “validation” exclusion refers to that post-build check, not the API's provenance validation. Serialized examples range29,681–101,305 B. No full-document scalability or performance distribution is established. Machine-specific execution evidence is outside Git; deterministic examples/results reproduced byte-for-byte in repeated runs and after the safety amendment.

Defaults bound depth32, tokens4,096, ordinary nodes8,192 plus one reserved wrapper, input65,536 characters and32 diagnostics. Repetition rejection is a conservative exact-pattern guard, not proof that repeated mathematics is invalid. Original strings remain intact when parsing is refused; lexical mapping completeness is explicit.

## Limitations and next milestone

This is a small LaTeX-body subset, not a full TeX parser, CAS or mathematical understanding system. Environments, matrices, macro expansion, unbraced multi-token command arguments and general prose are unsupported. Parenthesis adjacency does not prove function application; summand extent and variable binding remain unknown. Typography is represented but not interpreted as vector semantics. Parsed graph validity proves internal consistency only; caller-supplied PDF/model hashes are recorded rather than independently authenticated by this API. There are no symbol-level source boxes or character IDs.

The smallest justified follow-up is an **independently human-reviewed, small unseen-formula set** evaluating syntactic coverage, identifier ambiguity, rejection behavior and source notation separately. Review whether the exposed graphs help manual navigation before adding new grammar or production/viewer integration. A later source-alignment experiment must validate glyph links independently. No automatic mathematical explanations, production parser or viewer change is justified by these eight examples.

Implementation/API: [docs/formula-structure-v0.md](../../../docs/formula-structure-v0.md). Structured outcomes: results.json; complete graphs/raw strings: examples/*.json; scientific comparison retains original provisional labels and PP hashes. Validation and exact-head CI are reported on the PR. **Neither successful parsing nor successful rendering upgrades a model prediction into an authoritative mathematical fact.**
