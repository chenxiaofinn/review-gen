# Product Boundary

This file freezes the product boundary for `review-gen` so future agent work
does not drift into a different application.

## What review-gen Is

`review-gen` is a structured literature review workflow toolkit. It is built
around project workspaces, durable corpora, full-text preparation, review
planning, and citation-safe writing.

Its durable truth is the review workspace, especially:

- `01_search/`
- `02_corpus/master_corpus.jsonl`
- `03_screening/screening_table.csv`
- `04_fulltext/fulltext_manifest.csv`
- `05_mineru/`
- `06_chunks/`
- `07_plan/review_plan.md`
- `08_outputs/`

## What review-gen Is Not

`review-gen` must not be refactored into:

- a standalone daily news radar,
- an Obsidian or private-memory product,
- a weekly newsletter generator,
- a general AI reading companion,
- a generic agent orchestration framework,
- a replacement for Zotero, CNKI, or reference managers,
- a product whose main output is only a feed instead of a review workspace.

## Allowed Extensions

Extensions are allowed when they strengthen the review workflow and remain
optional:

- topic profiles for long-running literature tracking,
- frontier-push reports that produce candidates for user review,
- prompt-assisted topic drafting,
- prompt-assisted paper decomposition,
- source configuration improvements,
- better provenance, diagnostics, and citation checks.

## Rules For Literature Push

The literature-push feature must obey these boundaries:

- It is a workspace subflow, not a new top-level product.
- It may create a candidate report before corpus updates.
- It must not automatically pollute `master_corpus.jsonl`.
- User confirmation is required before candidates are promoted into the corpus.
- LLM output is advisory and reviewable. Missing model credentials must produce
  a prompt fallback.
- It must distinguish "factors of X" from "effects of X" unless the user asks
  for bidirectional tracking.

## Boundary Change Rule

If a future change needs to move these boundaries, create or update an ADR first.
Do not let implementation code make the product decision implicitly.
