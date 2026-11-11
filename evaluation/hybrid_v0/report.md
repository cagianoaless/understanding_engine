# Hybrid Interface v0 — offline implementation record, 2026-11-11

Implemented on `feat/hybrid-interface-v0`, stacked on PR17 commit
`efdac22d4567c40eb162910ecdf55ae8a258963a`. This is an interface/grounding
prototype, **not a new model evaluation**. No inference, candidate installation,
model/package acquisition, runtime changes, annotation edits or benchmark scoring
occurred. Structure 0.2, the production parser, dependencies and historical
experiments remain unchanged.

The [architecture](../../docs/hybrid-interface-v0.md) defines schema **0.1.0**,
Python TypedDict contracts, source-aware validation and exact failure semantics.
The implementation reuses existing extraction/schema/serialization contracts,
Structure 0.2 validation and DAG reachability. The few inclusive-center/origin
operations follow PR17 but live in the package so it does not import an experiment
or scorer. No frozen experiment code was moved or edited.

Available functionality:

- `build_hybrid(source_document, layout_predictions=None)`: complete immutable-
  input source copy, provider-qualified hypotheses, original boxes/origins,
  native hierarchy/order, explicit native versus geometric links and fallback.
- `validate_hybrid(document, original_source)`: schema plus conservation,
  provenance and derived-association validation against the original extraction.
- `source_text`: only original Unicode, in backend extraction order; no model
  text, normalization, inserted whitespace or reading-order claim.
- `order_hypothesis`: native provider evidence with unresolved within-item order,
  never certified reading order.

Missing/failed/rejected layout output leaves original source pages/characters
available. Input corruption fails closed. Native table children and group nodes,
overlapping owners and all provenance boxes remain explicit. Empty formula
diagnostic text does not erase source glyphs. Raster objects can have zero source
glyphs without inventing OCR. Unsupported Docling native-character claims are
contradictory, never legitimized by coincident ID strings. Confidence stays null
unless supported by a native numeric value/pointer; no cluster-to-item confidence
alignment was invented.

**Retained-evidence demonstration.** The six native Docling documents, existing
comparison adapter and five published failure cases were inspected. The live
demonstration consumes only already-retained **BERT page 6** native Structure and
Docling outputs plus its complete original extraction. Every consumed file is
verified against PR17's content-hash manifest; PDF identity is bound through the
hash-verified successful execution ledger, not Docling's non-SHA256 binary hash.
The builder/demo does not load frozen labels or scoring functions.

| Observed contract check | Result |
| --- | --- |
| Original BERT source retained | **16 pages / 54,003 characters**, unchanged |
| Source page 6 retained | **3,690 characters**, original IDs/Unicode/boxes |
| Remaining original pages | 15 explicitly source-only; no new predictions |
| Structure evidence | available, 90 original native regions with native membership |
| Docling evidence | available, 76 hierarchy/item nodes, 74 provenance boxes |
| Native table/group/text hierarchy | retained; parent/child ambiguity not suppressed |
| `#/texts/65` multi-box continuation | two boxes, common native item, order **unresolved** |
| Repeated offline construction | byte-identical full JSON |
| Current-code source-aware validation | PASS against original extraction |
| New inference / rescored benchmark | **0 / no** |

Full JSON is **58,496,673 bytes**, SHA256
`448464901ab56611dcbde6e8a2621ad17118508d0936415f06acc4408a2a7649`.
It and test logs are preserved in a fresh private mode-0700 external directory
under `/Users/Shared`; exact locations are in local `evidence-location.local.json`.
[evidence-manifest.json](evidence-manifest.json) lists portable relative paths,
lengths and hashes. The temporary original and preliminary successful construction
are retained, not overwritten or cleaned. Both actual full JSON constructions
agree; no inference was repeated. Source-aware validation was rerun after the
final geometry-free contradictory-claim guard was added and passed unchanged.

[example.json](example.json) is a small **inspection excerpt**, explicitly tagged
`is_complete_hybrid_document=false`, with original source-character records,
native hierarchy, two boxes and the provider-qualified unresolved order. It must
not be mistaken for the complete HybridDocument or proof that omitted source
characters were dropped. [demonstration.json](demonstration.json) records the
input hashes and conservation checks. Association-state counts are interface
diagnostics, **not precision/recall, accuracy or comparative quality metrics**.

**Testing.** Complete offline suite: **415 passed**, no failures/skips, **8.52 s**,
including **48** new hybrid regressions. Tests cover paragraphs/headings, native
membership, table/group/child overlap, caption outside parent geometry, multi-box
continuation, merged equations, empty formula text, raster objects, textless
overlap, unsupported claims, absent/failed output, bad geometry/identities,
hierarchy/traversal corruption, Unicode, key-order determinism, output mutation,
existing synthetic PDF fixtures, and atomic new-directory publication. No test
requires private PDFs, network, Docling or a neural model.

The existing project launcher remains broken and unrepaired. Tests use the
already-installed compatible CPython **3.11.13** and unchanged project packages
read-only. As in PR17, `uv --no-project` makes `--frozen` ineffective; no dependency
resolution/sync/install occurred. Existing CI uses its normal locked environment.
See [commands.md](commands.md) and [validation.json](validation.json).

**Known limitations.** Geometry association is not native provenance or model-text
alignment. It does not choose between parent/child owners, resolve conflicting
providers, split merged equations or reconstruct mathematical content. Only
verified origin-zero/unrotated/UserUnit-1 Docling frames are accepted; invalid
transforms reject the supplied artifact with source preserved. Confidence is not
inferred or calibrated. The complete inline source/native evidence increases
JSON size; center matching and actual overlap reporting are quadratic in the
relevant input sizes in worst cases. No full-document scalability claim is made.

The existing review form, protocol and archive manifest were inspected; the ZIP
is unavailable at its registered path. No archive was recreated and no human
review performed. The [checklist](../../docs/hybrid-v0-human-review.md) references
all **48 regions / 24 known order pairs / 18 paragraph decisions**, preserves
`agent_visual_checked` status and records zero independent human verifications.
This does not block the deterministic prototype.

The first independently validated evaluation should freeze v0 and new unexposed
development pages, then obtain independent source-first human associations/order
constraints before inspecting hybrid outputs. Test conservation, valid links,
ambiguity/contradiction/unmatched handling and abstention coverage separately.
Do not call PR17 pages independent validation, pool agent/human labels, modify
held-out data, or claim a detection advantage from this interface alone. No such
evaluation or final hybrid architecture is implemented here. **Stop at v0.**
