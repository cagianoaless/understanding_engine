# Independent review of Experiment 006b, annotation revision 1

All six pages and every box, ordering pair and paragraph decision were selected
from original PDF renders by Codex before either candidate generated predictions.
They are **agent_visual_checked**, not human-verified ground truth. No human has
reviewed them. The form intentionally has no reviewer name and every decision
is pending. Visual review is an agent activity, not model inference in the parser.

The independent review ZIP is outside Git; its SHA-256, size and member hashes
are in `review-package.json`. It contains six raw pages, six labeled overlays,
window crops, original page geometry, frozen annotations, the scoring plan and
`human-review-form.json`. Copyrighted PDFs/renders are not committed. Local
access to the ZIP does not establish permission to redistribute the PDFs.

1. Verify the ZIP hash and member hashes. Use the registered original PDF hashes
   to establish document identity. Page numbers are physical, one-based PDF pages.
2. Inspect `raw/` first without candidate predictions. Form your own region,
   paragraph and order judgments; then inspect `overlays/`, crops and annotations.
   Green boxes are scored windows, red boxes are reference regions, blue strips
   identify source-linked paragraph probes. Labels refer to stable JSON IDs.
3. Check region extents, granularity (four separate Nature chart panels), types,
   order pairs and explicitly unresolved groups. A missing annotation is a
   reference defect, not automatically a candidate false positive. Partial-page
   scopes intentionally omit unannotated material and page furniture. Do not
   infer full-document or full-page accuracy from these windows.
4. A real independent human reviewer fills their actual name, accepts/rejects or
   marks each decision uncertain, and supplies corrections/comments. An agent
   must never fill in a human identity or change verification to human_verified.
   A teacher/model review is a separate hypothesis source, never a human review.
5. Save the completed form and corrections as a new, hashed revision. Do not edit
   this freeze or previously published experiments. Retain v1 agent-only metrics
   separately from any subsequently scored human-verified subset, including
   rejected and uncertain cases and their denominators.

Revision 1 contains no exact text transcriptions or Unicode-accuracy references.
It tests structural localization and selected relations. Source-character IDs
on paragraph strips were obtained from the existing authoritative extraction,
only to locate the original source evidence. They are not structure predictions.
Unmapped `(cid:...)` glyphs, mathematical reconstruction and reading order beyond
the explicitly annotated constraints remain outside the reference claims.
