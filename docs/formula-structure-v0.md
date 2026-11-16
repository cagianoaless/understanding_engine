# Formula Structure v0 — experimental API

This separate offline module interprets a **model transcription hypothesis**. It does not change PDF extraction, Hybrid, Source Selection or the viewer. No model, renderer, GPU, network or new dependency is used. Original PDF evidence, generated LaTeX, parsed syntax and mathematical understanding remain four distinct objects.

## API

```python
from understanding_engine.contracts import json_bytes
from understanding_engine.formula_structure import parse_formula, ParseSettings
from understanding_engine.formula_structure_contract import validate_formula_structure

result = parse_formula(
    latex, provenance,
    raw_model_output=raw_output,  # exact optional diagnostic string, never rewritten
    termination="complete",    # observed caller fact: complete/incomplete/unknown
    settings=ParseSettings(),
)
validate_formula_structure(result)
payload = json_bytes(result)
by_id = {node["id"]: node for node in result["nodes"]}
root = by_id[result["root_id"]]
children = [(edge["role"], by_id[edge["node_id"]]) for edge in root["children"]]
```

`provenance` requires original PDF SHA-256, one-based page_number, positive-area original bbox, coordinate_system=`pdfplumber-native-v1`, crop_sha256, model_name, model_revision, prediction_id, prediction_record_sha256 and prediction_artifact_sha256. No viewport conversion or coordinate inference occurs. The evaluation uses a SHA-256 of canonical `json_bytes(record)` for record identity and the exact original JSON-file byte hash for artifact identity. These are different identities.

The API records supplied identity; it does not open or authenticate the PDF/crop/model/artifact. The caller must independently verify those files. `validate_formula_structure` checks schema and deterministic rebuild, **not the truth of caller-supplied provenance**. Invalid identity/geometry raises ExtractionError; malformed or unsupported LaTeX returns a diagnostic result. Caller-supplied termination is not guessed from balanced braces.

## Versioned representation

The contract is `FormulaStructure` / schema `formula-structure-0.1`, version0.1.0. Parser identity is `latex-subset-v0.1.0` plus all settings. Formula IDs hash parser identity, exact input and provenance; node IDs append deterministic postorder indices. Identical inputs/settings produce identical JSON bytes. Different raw evidence, crop, model, termination or parser settings changes identity.

Every node has type, stable ID, half-open token_span, half-open character_span, exact **LaTeX** source_text substring, ordered role-labelled child links, status, attributes and diagnostic codes. Node `source_text` is a substring of `input.latex`: **it is not authoritative PDF text**, unlike Source Selection's original-character text. Character offsets count Python Unicode code points, not UTF-8 bytes, PDF glyphs or pixels. Whitespace is retained as tokens; no Unicode/spacing normalization occurs. Ancestor spans naturally overlap child spans. Children precede parents; the graph is acyclic and all retained fragments remain reachable.

`input.latex` is the exact chosen transcription; the eight-record experiment uses its already frozen `cleaned_latex`, with no new cleanup. `input.raw_model_output` retains the original raw string separately. Both hashes are stored. No LaTeX token is given a PDF character ID or bounding box. Crop-level provenance is not glyph-level membership.

All results, including perfectly parsed `1=2`, retain:

- `text_role=model_transcription_hypothesis`
- `source_alignment=formula_crop_only`
- `mathematical_correctness=unverified`
- `source_validation=provenance_recorded_not_verified`

There is no numerical confidence or automatically obtainable source_verified state.

## Explicit grammar and deliberate boundaries

Supported syntax includes individual letter/Greek-command symbols; contiguous decimal digit strings; explicit operators/relations; braced fractions and radicals with optional root degree; scripts; sum operators with optional lower/upper limits; balanced braces/parentheses/brackets/escaped braces/angle delimiters; sized matching `left/right`; explicit operatorname/named-command groups; selected typography commands; single-word text groups; layout markers and sequences.

- Fraction arguments and radical/style/operatorname bodies require braces. Valid TeX such as `\frac12` is deliberately unsupported. Unbraced scripts accept one supported symbol or one digit; `_12` is rejected rather than assigning both digits to the script. Braces are required for multi-token script arguments.
- Arithmetic is a sequence of explicit tokens, with local malformed-operator checks. No precedence, implicit multiplication, algebraic equivalence, variable binding or function application is inferred. Summations have explicit operator/limit links but **no inferred summand scope or bound variable**.
- `A t t e n t i o n` remains individual symbols. Bare contiguous `sin` also remains individual symbols. A script on `h e a d _1` attaches to literal `d`, not an invented `head` identifier.
- `\operatorname{A t t e n t i o n}` retains explicit operator grouping and its exact body, but no verified semantic function. `\sin` is an explicitly written operator command, not an assertion that its model/source identity is correct. Ordinary following parentheses remain separate delimited groups.
- `\mathbf{x}` retains its typography command; plain `x` is distinct. Boldness does not automatically classify a symbol as a vector. Text groups such as `\text{softmax}` are ambiguous textual name hypotheses; multiword prose is unresolved.
- Bare letter/numeric runs flag grouping ambiguity rather than joining digits or names. This may conservatively flag legitimate mathematical adjacency.
- Top-level line-break/alignment markers are retained. Relation scope across line breaks is explicitly unresolved; no cross-row equation chain is manufactured. General environments, matrices, macros, intertext, escaped document commands, TeX expansion and a full TeX grammar are outside v0.

A relation node records only explicit operands/operators in the syntax. It is not a proof of equality. A limited-grammar success is not a successful TeX compilation or mathematical validation. Unmarked prose may look like ambiguous letter sequences; this parser is not a reliable prose detector. Explicit multiword text/intertext is refused, but inspection remains necessary.

## Failure and acceptance policy

Independent result fields record parsing, syntax, structural_support, acceptance, diagnostic completeness and observed model termination:

| Outcome | Meaning | Acceptance |
|---|---|---|
| parsed | Entire body consumed by the supported subset; no unresolved subtree | inspect_syntax_only, or inspect_with_ambiguities |
| partial | Useful syntax fragments exist, but unsupported/malformed content or incomplete generation prevents full structure | reject as a complete formula |
| rejected | No useful supported structure, or a resource guard prevents parsing | reject |

An incomplete-generation observation rejects the whole expression even if its current braces balance; the root is unresolved. Unknown termination stays unknown and requires inspection. Partial parses have an unresolved whole-input wrapper with explicit parsed_fragment children. No missing delimiter, command argument, operator or symbol is inserted. Prose, unsupported commands, duplicate scripts, unbalanced groups and excessive repetition never become full successes. A prefix does not validate the unparsed tail.

Defaults:65,536 input characters,4,096 lexical tokens,8,192 ordinary nodes plus one reserved final wrapper, depth32,32 global diagnostics and8 repetitions of an exact token block of width1–8. Hard configuration ceilings prevent disabling bounds with arbitrarily large settings. Guards are deterministic engineering limits, not calibrated correctness or maliciousness scores. Repetition checks may reject legitimate repeated notation. Diagnostics are bounded and that bounding is explicit.

When lexical guards fire, the full original input/raw evidence remains stored but the token stream may be absent; token_span_complete=false explains that no full token mapping is available. Resource guards bound parsing, not the storage required to retain an arbitrarily large supplied original string. No untrusted LaTeX is executed.

## Research use

See `evaluation/experiments/formula_structure_v0/` for the eight-record evaluation, examples, frozen hashes, safety amendment, reproducible command, timing and limitations. Reference labels are read only after candidate parsing; they never repair its results. The retained PP data remains comparison evidence, not an ensemble input. Six supported parses do not imply six correct transcriptions. No production integration or independent recognition validation is claimed.
