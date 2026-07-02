# Story: Frontier Push Candidates And Report

## Intent Gate

- User goal: Generate a topic-specific frontier report from Tier A and Tier C sources.
- Success criteria: A run writes candidates JSONL and a Markdown report with main-push and early-signal sections.
- Non-goals: No Tier B conference crawling in v1.
- Rollback path: Remove run/report module, CLI command, and tests.

## Boundary Gate

- Existing workflow stages touched: Optional search helper only.
- Existing workspace files touched: `09_frontier_push/` only.
- Manual user fields preserved: Existing corpus and screening files are untouched.
- Optional behavior remains optional: Yes.

## Architecture Gate

- Files to create: Source catalog, candidate scoring, report generation, tests.
- Files to modify: `review_workflow.py`.
- Data read: Profile YAML, source catalog, optional metadata responses.
- Data written: Run candidates JSONL and report Markdown.
- Network or LLM dependencies: Metadata fetches may use configured source adapters; tests use fixtures.
- Failure fallback: Write diagnostics and keep partial candidates separated by source.

## Test Plan

- Unit tests: Deduplication, tier labels, exclude keywords, directionality filtering, report sections.
- Offline fixtures: Fake Tier A and Tier C candidate records.
- Commands to run: `python -m unittest discover -s tests`.

## Review Gate

- Product drift checked: Yes.
- Compatibility checked: Yes.
- Overwrite risk checked: Yes.
- Diff size checked: Yes.
