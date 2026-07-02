# Story: Frontier Push Candidate Promotion

## Intent Gate

- User goal: Promote selected frontier candidates into the existing review search layer.
- Success criteria: Promotion writes compatible raw-search JSON and does not change `master_corpus.jsonl`.
- Non-goals: No automatic merge, screening, manifest, or full-text download.
- Rollback path: Delete generated raw-search JSON before running merge.

## Boundary Gate

- Existing workflow stages touched: `01_search/raw_json/` only.
- Existing workspace files touched: New promotion JSON file only.
- Manual user fields preserved: Yes.
- Optional behavior remains optional: Yes.

## Architecture Gate

- Files to create: Promotion helper and tests.
- Files to modify: `review_workflow.py`.
- Data read: `09_frontier_push/runs/<run-id>/candidates.jsonl`.
- Data written: `01_search/raw_json/frontier_push_<run-id>.json`.
- Network or LLM dependencies: None.
- Failure fallback: Refuse missing candidate IDs with a diagnostic payload.

## Test Plan

- Unit tests: Selected candidates only, raw-search compatibility, no corpus write.
- Offline fixtures: Candidate JSONL fixture.
- Commands to run: `python -m unittest discover -s tests`.

## Review Gate

- Product drift checked: Yes.
- Compatibility checked: Yes.
- Overwrite risk checked: Yes.
- Diff size checked: Yes.
