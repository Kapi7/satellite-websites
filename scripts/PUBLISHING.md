# Reviewed article releases

The publisher releases explicit entries from `reviewed-releases.json`. It does not generate articles, translate copy, send notifications, or treat raw draft count as approval.

Prepare and review copy, primary sources, exact photos and mobile presentation first. Record the source URL and visual review for each image, and the content/image hashes after that review. Each locale needs its own explicit approval. English-only releases are supported; excluded translations must be absent or still marked as drafts. Existing full-translation checks remain in place for the protected Glow guides.

Run `python3 scripts/reviewed_publisher.py` for a read-only validation. `--prepare` is only for an isolated local preview: it transitions approved files without pushing or deploying. The workflow runs `--run` from a clean checkout, builds affected sites, commits only approved article files, pushes without force, directly deploys the affected Cloudflare Pages projects and verifies live content markers and exact image hashes. A failed deployment leaves the manifest pending so the next run can retry; publication dates remain stable. Verified entries are retained as release evidence.

Add reviewed entries deliberately. Do not refresh hashes to silence a failed check without repeating the relevant editorial or photo review. Missing images, changed copy, stale included translations and public excluded translations block a release. Do not add a second pending entry for the same site/slug.

An empty reviewed queue is a visible editorial warning and a no-op, not a publishing outage or a claim of fresh content. The raw backlog is reported separately. Replenishment belongs to the twice-weekly editorial work, not an unattended generation loop. No-op success must never be used as evidence that new articles went live.

Tracking, consent, affiliate IDs and existing attribution parameters are outside this release change.

Production deployment ownership: as of 20 October 2026, native Cloudflare production Git builds for Glow and Rooted are disabled (preview settings preserved). Build's separate deployment workflow is manual-only and shares the publisher lock. This prevents older parallel builds from replacing reviewed releases. Use the publisher for approved article releases; code-only site changes require an explicit validated direct deployment. Do not re-enable a competing automatic production path without serialization and stale-revision protection.

If source files are already published after an interrupted run, the publisher first checks live copy and exact image hashes. It acknowledges a matching deployment without rebuilding, otherwise it runs validation/build/deployment again. Image and HTML requests both identify the verifier explicitly.
