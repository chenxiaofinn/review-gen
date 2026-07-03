# Story: Consolidated RIS Export As Side-Effect Of Promote

## Intent Gate

- User goal: when an agent promotes frontier candidates into the main
  search layer, also produce a single consolidated RIS file so the user
  can import the promoted set into Zotero with one File → Import action
  (replacing the previous ad-hoc per-paper `.ris` workflow).
- Success criteria:
  - `promote-frontier-candidates` writes both the promoted JSON and one
    multi-record RIS file atomically.
  - The RIS is at `02_corpus/zotero_ris/frontier_push_<run-id>.ris`,
    naming symmetric with the promoted JSON path.
  - Per-paper `.ris` files are no longer generated.
  - RIS writing can be disabled with `--no-write-ris` to preserve the
    "promote is single-purpose" boundary for users who do not want RIS.
  - Two new unit tests cover the happy path and the overwrite path;
    all existing tests still pass.
- Non-goals:
  - No new CLI subcommand; RIS writing is a side-effect of the existing
    `promote-frontier-candidates`, opt-out via `--no-write-ris`.
  - No per-paper RIS export helper.
  - No changes to `merge-search-results`, screening, manifest, planner,
    or writer modules.
  - No slug / diacritic normalisation change in this story (tracked
    separately as a known limitation).
- Rollback path: revert this single commit; the previous per-paper RIS
  workflow was a temp script in `C:/Users/14543/AppData/Local/Temp/opencode/`,
  not in the repo, so no repo file needs deletion on rollback.

## Boundary Gate

- Existing workflow stages touched: optional `09_frontier_push/` subflow
  only. The promoted JSON is the existing boundary crossing into
  `01_search/raw_json/`; the consolidated RIS is a **new** file under
  `02_corpus/zotero_ris/`, parallel to `02_corpus/cnki_ris/` (which is
  already documented in `README_zh.md`).
- Existing workspace files touched: only the consolidated RIS file is
  new; nothing is overwritten or moved. Per-paper `.ris` files at
  `02_corpus/zotero_ris/<year>__<author>__*.ris` are user-side artifacts
  and can be deleted manually when convenient.
- Manual user fields preserved: unchanged. The promotion step does not
  touch screening, manifest, evidence, or plan fields.
- Optional behaviour remains optional: `--no-write-ris` flag keeps the
  previous single-purpose semantics available.

## Architecture Gate

- Files to modify:
  - `skills/openalex-ajg-insights/scripts/frontier_push/promotion.py`
    (add RIS helpers + `write_consolidated_ris`, wire into
    `promote_frontier_candidates`, add `--write-ris` / `--no-write-ris`
    flag passed through by `review_workflow.py`).
  - `skills/openalex-ajg-insights/scripts/review_workflow.py`
    (forward `--write-ris` / `--no-write-ris` to `promote-frontier-candidates`,
    default `True`).
  - `tests/test_frontier_push_promotion.py` (two new tests:
    `test_promote_writes_consolidated_ris`,
    `test_promote_consolidated_ris_overwrites_existing`).
  - `docs/governance/runbooks/frontier-push-ta-only.md`
    (add "Promotion And Consolidated RIS" section describing the new
    side-effect and the `--no-write-ris` opt-out).
- Data read: candidate records from
  `09_frontier_push/runs/<run-id>/candidates.jsonl` (unchanged).
- Data written: `01_search/raw_json/frontier_push_<run-id>.json`
  (unchanged) **and** `02_corpus/zotero_ris/frontier_push_<run-id>.ris`
  (new).
- Network or LLM dependencies: none.
- Failure fallback: RIS write is a local file write after the JSON write.
  If the RIS write fails (permission, disk full), the JSON is still on
  disk and the exception propagates; user can re-run with `--no-write-ris`
  to skip the failing step. The promotion result payload includes the
  resolved `consolidated_ris_path` (or `None` when `--no-write-ris`).

## Test Plan

- Unit tests:
  - `test_promote_writes_consolidated_ris`: two-candidate fixture, asserts
    the RIS file exists at the canonical path, contains exactly two
    `TY  - JOUR` and two `ER  -` markers, includes both titles, DOIs, and
    derived keywords, and that the directory contains only one `.ris`
    file (not five).
  - `test_promote_consolidated_ris_overwrites_existing`: re-promote with
    fewer candidates against the same `run_id`, asserts the file shrinks
    to the new candidate set.
- Offline fixtures: only the existing `tmp` workspace + JSONL fixtures;
  no new fixtures needed.
- Commands to run: `python -m unittest discover -s tests`.

## Review Gate

- Product drift checked: yes. The change is additive (new side-effect
  file under `02_corpus/zotero_ris/`). `merge-search-results`,
  screening, manifest, planner, writer, and orchestrator are untouched.
- Compatibility checked: existing `promote-frontier-candidates` callers
  get the new side-effect with default `--write-ris=True`; tests pass.
- Overwrite risk checked: the consolidated RIS overwrites itself on
  re-promote (intentional, see `test_promote_consolidated_ris_overwrites_existing`).
  Per-paper RIS files are not touched.
- Diff size checked: promotion.py grows by ~80 lines (helpers + writer);
  test file grows by ~55 lines; runbook doc grows by ~25 lines. All
  within "small reviewable change" rule.

## Cross-References

- Operational procedure: `docs/governance/runbooks/frontier-push-ta-only.md`
  (the "Promotion And Consolidated RIS" section added in this change).
- Sibling precedent: `generative-ai-economic-consequences` workspace uses
  `download_status=manually_imported_via_zotero` + `download_source=zotero_storage`
  for Zotero-imported PDFs; this story covers the complementary path
  (Zotero import via RIS rather than PDF).
- Pre-existing story: `2026-07-03-frontier-push-promotion.md` documents
  the original `promote-frontier-candidates` CLI; this story is the
  delta for the RIS side-effect.