# Story: Enforce Frontier Record Schema and CLI Dispatch

## Intent Gate

- User goal: prevent the 2026-07-03 frontier-push under-sampling bug from
  recurring and make legacy source-record files honest about their provenance.
- Success criteria: every CLI subcommand dispatches in `main()`; CLI
  `--year-start`/`--year-end` reach the runner; legacy files emit warnings
  instead of silently polluting reports.
- Non-goals: no rewrite of `candidates.py`, no LLM-driven filtering, no
  promotion logic changes, no override of the existing Tier A/C catalog.
- Rollback: revert the validator function and the extra dispatch branch.

## Boundary Gate

- Existing workflow stages touched: optional CLI dispatch only.
- Existing workspace files touched: `09_frontier_push/source_records/*` is
  read; nothing is rewritten.
- Manual user fields preserved: candidate `match_reasons`, `match_score`,
  `push_bucket`, and `strong_signal` are untouched.
- Optional behavior remains optional: warnings are non-blocking by design.

## Architecture Gate

- Files to create: `tests/test_cli_dispatch.py`,
  `tests/test_source_payload_validator.py`.
- Files to modify: `review_workflow.py` (new dispatch branch + arg
  pass-through + init diagnostic), `frontier_push/source_collection.py`
  (new validator), `frontier_push/runner.py` (per-source year bounds).
- Data read: existing source-record JSON files under `source_records/`.
- Data written: warnings emitted via `emit()`; no files overwritten.
- Network or LLM dependencies: none.
- Failure fallback: warnings degrade to logs, never to exceptions.

## Test Plan

- Unit tests: CLI dispatch enumeration, validator diagnostics, runner
  per-source year filter.
- Offline fixtures: a tiny workspace with a legacy and a canonical
  source-record file under `source_records/`.
- Commands to run: `python -m unittest discover -s tests`.

## Review Gate

- Product drift checked: yes.
- Compatibility checked: legacy files still load.
- Overwrite risk checked: validator writes nothing into the workspace.
- Diff size checked: small, separated docs / code / tests.
