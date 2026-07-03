# Story: Frontier Push Status Diagnostics In Review Orchestrator

## Intent Gate

- User goal: make the frontier-push and downstream review workflow easier to
  inspect without adding a one-click workflow runner or bypassing human review
  gates.
- Success criteria:
  - `review_state_manager.py status` reports the current stage, completed
    milestones, missing inputs, human blockers, and recommended next action.
  - Frontier-push diagnostics surface TA-only source coverage, mixed profile or
    year-window source records, explicit `--input` paths, candidate-triage
    blockers, and promotion/RIS readiness as routing recommendations rather
    than hard CLI blocks.
  - Downstream diagnostics identify screening, manifest, PDF, MinerU, chunk,
    plan approval, and writing-packet readiness without modifying workspace
    files.
- Non-goals:
  - No new workflow runner.
  - No automatic promotion, screening edits, manifest edits, plan approval, PDF
    import, or drafting.
  - No change to default search, corpus, planner, writer, or promotion behavior.
- Rollback path: revert the status helper changes, the tests, and this story
  file. Existing approve/reopen commands remain unchanged.

## Boundary Gate

- Product boundary preserved: the change strengthens the review workspace as
  the durable source of truth.
- Literature-push remains a workspace subflow. Candidates still go to reports
  first and require explicit user-selected `candidate_ids` before promotion.
- Manual fields are preserved. The status command is read-only and does not
  overwrite screening, manifest, evidence, plan, corpus, frontier runs,
  reports, or source-record files.
- Existing orchestrator is extended instead of introducing a generic agent
  framework.

## Architecture Gate

- Files changed:
  - `skills/review-orchestrator/scripts/review_state_manager.py`
  - `tests/test_review_orchestrator_status.py`
  - `skills/review-orchestrator/SKILL.md`
  - this story file
- Data read:
  - workspace layout, frontier profiles/source records/runs/promoted JSON/RIS,
    corpus, screening table, full-text manifest, chunks, plan, writing packet.
- Data written:
  - `status` writes nothing. `approve-plan` and `reopen-plan` keep their
    pre-existing write behavior.
- Failure modes:
  - Invalid source-record JSON is ignored for status purposes rather than
    causing a write or workflow mutation.
  - Mixed source windows or profiles produce warnings and stop short of
    recommending `run-frontier-push`.
- Tests:
  - Offline unit tests cover each major stage and warning path.

## Review Gate

- Product drift checked: no new runner, no generic orchestration framework.
- Compatibility checked: existing status keys remain present.
- Overwrite risk checked: `compute_status` now uses read-only plan layout
  inspection instead of migrating legacy plan files, with tests snapshotting
  key workflow files before and after status.
- Generated-output risk checked: tests use temporary workspaces only.
