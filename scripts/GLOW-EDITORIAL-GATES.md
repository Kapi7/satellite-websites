# Glow Coded publication gates

The 20 September 2026 Jev audit is a triage tool, not verification of facts or photographs. Its confidence values must not automatically approve content.

For a new cosmetics article, the daily publisher now requires all nine translations to match the current English fingerprint, no copied English prose paragraphs of 25+ words, and an image approval that matches the current image bytes. A missing approval stops publication before undrafting. Existing unreviewed pages remain in the audit backlog; they are not silently certified by this change.

For the five repaired guides in `cosmetics/src/data/reviewed-articles.json`, the same checks run before every production build. English meaning, product paths, title or image changes invalidate translations. Date and draft-only changes do not. `translationSourceHash` records source synchronization, not native-speaker approval. A paragraph-only repair deliberately does not stamp the whole translation.

Image review is recorded in `cosmetics/src/data/image-approvals.json`: exact product reference URL, reference image, SHA-256 of the reviewed image, reviewer and date. Use one real source photograph in the Gemini enhancement workflow; inspect the source and output, including labels, size, color, formula and cropping. Record approval only after visual review. Never let an LLM write its own approval.

## Evidence-driven next work

Prioritize improvements to existing pages before more generic shopping-checklist articles. The first batch was selected from Search Console impressions, product-click signals, and confirmed quality defects. Traffic volumes are too small to infer reliable purchase conversion effects.

1. TIRTIR shade guide: preserve formula identity and improve the depth/undertone decision.
2. Lip-care guide: compare real formats, remove invented tests, retain relevant product links.
3. Oily-skin SPF guide: distinguish Aqua-Fresh from Original and avoid universal white-cast promises.
4. Galactomyces and mugwort: repair fabricated heroes and source/formula claims.
5. Next review: dark-spot and sensitive-skin moisturizer pages; verify sizes and formulas before replacing their images.

Before adding a brief, record actual query/page evidence, the reader's unresolved question, overlap with existing pages, an exact relevant product and the proposed purchase path. No-query data means unknown demand, not zero. HTTP 429 means unknown availability, not a dead or out-of-stock product.

Measure complete comparable 28-day periods after indexing: page/query impressions and clicks, production-host product-click events, Mirai attributed sessions, and purchases. Keep click events distinct from people and exclude internal tests when identifiable. Improvements in rankings or sales are hypotheses, not promised results.

## Verification

Run `python3 scripts/test_content_quality.py`, `python3 scripts/test_translation_quality.py`, `python3 scripts/test_markdown_quality.py`, and `npm --prefix cosmetics run build`. The one-off `repair_glow_batch.py` outputs review artifacts only; it never publishes or approves an image. The `repair_batch` workflow input keeps the publisher job disabled.
