# Story: TA-Only Run Hardening

## Intent Gate

- User goal: make canonical TA-only `run-frontier-push` runs reject the
  highest-risk inputs that can contaminate candidate reports: historical
  payload auto-discovery, Tier C inclusion, missing year windows, and mixed
  source/profile/year payloads.
- Success criteria:
  - `run-frontier-push --ta-only` requires explicit `--input` paths.
  - `--ta-only` requires `--year-start` and `--year-end`.
  - `--ta-only` accepts only source tier `A` and exactly the three TA source
    payloads: `abs_ajg_4star`, `ft50`, and `utd24`.
  - Payload profile and year metadata, when present, must match the CLI
    profile and year window.
  - Existing flexible/legacy `run-frontier-push` behavior remains available
    when `--ta-only` is omitted.
- Non-goals:
  - No promotion confirmation gate.
  - No changes to screening, manifest, planner, writer, or Zotero intake.
  - No one-click workflow runner.
- Rollback path: revert this story, the runbook update, the CLI tests, and the
  `--ta-only` validation changes in `review_workflow.py`.

## Boundary Gate

- Literature push remains a workspace subflow. This hardening only affects the
  canonical TA-only run mode.
- Flexible frontier runs are preserved for legacy or explicitly non-standard
  use by omitting `--ta-only`.
- No user-edited screening, manifest, evidence, plan, or corpus fields are
  overwritten by this change.

## Architecture Gate

- Files changed:
  - `skills/openalex-ajg-insights/scripts/review_workflow.py`
  - `docs/governance/runbooks/frontier-push-ta-only.md`
  - `tests/test_frontier_push_cli.py`
  - this story file
- Data read: explicit frontier source payload JSON files passed to
  `run-frontier-push --ta-only`.
- Data written: unchanged from existing `run-frontier-push`; validated runs
  still write candidates under `09_frontier_push/runs/<run-id>/` and reports
  under `09_frontier_push/reports/<profile>/`.
- Failure behavior: invalid TA-only inputs fail before loading the profile or
  writing run/report artifacts.
- Tests: offline unit tests cover parser support, required inputs, source tier,
  source coverage, profile/year mismatch, unexpected sources, and happy path.

## Review Gate

- Product drift checked: no generic orchestration framework and no end-to-end
  runner added.
- Compatibility checked: non-`--ta-only` `run-frontier-push` keeps existing
  flexible defaults.
- Overwrite risk checked: validation happens before `run_frontier_push_from_records`
  writes candidates or reports.
- Generated-output risk checked: tests use temporary workspaces only.
