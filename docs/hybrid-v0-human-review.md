# Independent review preparation — unchanged Experiment 006b revision 1

The existing [protocol](../evaluation/experiments/006b/review_protocol.md),
[pending form](../evaluation/experiments/006b/human-review-form.json) and
[archive manifest](../evaluation/experiments/006b/review-package.json) were
inspected. The ZIP was **unavailable at its registered local path** during this
milestone; bounded checks of the known original artifact roots found no copy.
Only the manifest/form/protocol are confirmed inspected, not the missing raster
members. Nothing was regenerated, edited or submitted as human review. The
manifest registers 4,744,612 bytes, SHA256
`b1ed02b722fb73e8c0dce480403c95a74a4b414e207663e2d645fba7c6552ab6`.
An independent reviewer must first locate/verify that package, or separately
authorize reproduction with the existing tooling and original source identities.
This does not block the deterministic interface prototype.

| Existing page ID | Regions | Known order pairs | Paragraph decisions |
| --- | ---: | ---: | ---: |
| attention-p06 | 10 | 6 | 3 |
| attention-p09 | 8 | 5 | 4 |
| bert-p06 | 12 | 5 | 4 |
| bert-p10 | 9 | 7 | 4 |
| tabpfn_nature_2025-p15 | 6 | 1 | 2 |
| tabpfn_nature_2025-p19 | 3 | 0 | 1 |
| Total | **48** | **24** | **18** |

For the actual independent human reviewer:

1. Verify package/member/PDF hashes and physical page numbers. Inspect raw pages
   before overlays or candidate predictions. Use actual reviewer identity; an
   agent must not fill it in or declare human verification.
2. Review each `:rN` region's extent/type/granularity, including four separate
   Nature chart panels. Record missing/uncertain reference regions explicitly.
   Nature 19's `:r3` note has ambiguous type; localization/paragraph still count.
3. Review each `:oN` known pair and unresolved group separately. Inspect the BERT
   cross-column continuation; native multi-box item order is not automatically
   a justified within-item sequence. Do not infer orders for all unlisted pairs.
4. Review every `:pN` join/break using its original source-ID strips. Separate a
   real paragraph decision from an unsupported model text-region assignment;
   correctly labelled captions need not satisfy a text-only assignment rule.
5. For a later interface-specific review, distinguish native ID membership from
   geometric coverage. Preserve table groups/children, overlapping owners,
   textless raster objects and formula glyphs whose model diagnostic text is
   empty. Do not correct source Unicode, recover `(cid:...)` or invent alignments.
6. Save any real human decisions/corrections as a **new hashed revision**, with
   rejected/uncertain decisions and denominators. Preserve v1 unchanged. Do not
   pool its agent-only metrics with a human-verified subset or describe these
   already exposed pages as independent generalization evidence.

Current status remains **agent_visual_checked**, **zero independent human
verifications**. No form entries, annotations, source identities or historical
reports changed. Human review is a subsequent activity, not completed by this
checklist.
