# Story: Frontier Push Paper Decomposition

## Intent Gate

- User goal: Produce a detailed, accurate, readable Simplified Chinese paper decomposition.
- Success criteria: The CLI can create a two-stage prompt fallback and, when configured, an LLM output file.
- Non-goals: No full-paper translation, no citation fabrication, no external skill migration.
- Rollback path: Remove decomposition helper, CLI command, and tests.

## Boundary Gate

- Existing workflow stages touched: Optional full-text reading only.
- Existing workspace files touched: `09_frontier_push/deep_reads/` only.
- Manual user fields preserved: Existing evidence table and plan are untouched.
- Optional behavior remains optional: Yes.

## Architecture Gate

- Files to create: Decomposition prompt builder and tests.
- Files to modify: `review_workflow.py`.
- Data read: Candidate metadata, corpus metadata, optional Markdown chunks or full text.
- Data written: `deep_reads/<paper-key>.md`.
- Network or LLM dependencies: OpenAI-compatible API only when configured.
- Failure fallback: Write the complete two-stage prompt instead of failing.

## Test Plan

- Unit tests: Prompt constraints, two-stage structure, missing-key fallback.
- Offline fixtures: Sample paper metadata and excerpt text.
- Commands to run: `python -m unittest discover -s tests`.

## Review Gate

- Product drift checked: Yes.
- Compatibility checked: Yes.
- Overwrite risk checked: Yes.
- Diff size checked: Yes.
