# Story: Frontier Source Collection And Strict Year Filters

## Intent Gate

- User goal: make frontier push return enough 2025-2026 papers from the intended
  Tier A journal anchors: AJG 4*, FT50, and UTD24.
- Success criteria: collection covers all resolved journals via multi-round
  OpenAlex calls, preserves source provenance, filters by `--year-start` and
  `--year-end`, and reports diagnostics.
- Non-goals: no AJG 3+ fallback, no Tier B conference crawler, no automatic
  promotion into corpus, no rewrite of planner/writer/orchestrator.
- Rollback: remove the new collection command and year-filter arguments; existing
  review workspaces and corpus files are untouched.

## Boundary Gate

- The change only extends `09_frontier_push` and OpenAlex/AJG metadata collection.
- `run-frontier-push` still writes candidates and reports only.
- `promote-frontier-candidates` remains the only bridge into `01_search/raw_json`.
- `master_corpus.jsonl` is not changed by collection or push report commands.

## Architecture Gate

- Source strategy: workspace `sources.yml` lists Tier A strategy ids; concrete
  ISSNs resolve through the bundled AJG CSV used by the existing OpenAlex/AJG
  bridge.
- Collection: a new CLI command writes source-record JSON files under
  `09_frontier_push/source_records/`.
- Filtering: `run-frontier-push --year-start --year-end` applies strict record
  filtering before scoring.
- Failure modes: unresolved FT50/UTD24 names and empty query results are returned
  as diagnostics, not silent success.
- Tests: offline unit tests cover source resolution, chunking, year filtering,
  provenance, and CLI behavior.

## Review Gate

- Run `D:\ProgramData\anaconda3\python.exe -m unittest discover -s tests`.
- Verify generated `quality_reports/` is ignored and not staged.
- Commit docs, config, code, and user-guide updates separately.
