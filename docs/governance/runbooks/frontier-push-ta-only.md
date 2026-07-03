# Frontier Push TA-Only Runbook

Use this runbook when a user asks for a frontier-push run limited to Tier A
sources. It preserves the workspace subflow: candidates go to a push report
first, and promotion into the corpus requires explicit user-selected
`candidate_ids`.

## Standard Flow

1. Confirm the workspace and profile exist.
2. Run `init-frontier-push` idempotently.
3. Run `collect-frontier-sources` for TA sources only:

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  collect-frontier-sources \
  --profile <profile-id> \
  --source-ids abs_ajg_4star,ft50,utd24 \
  --year-start <start-year> \
  --year-end <end-year> \
  --limit-per-query <n> \
  --max-queries <n>
```

4. Run `run-frontier-push` with explicit input files from the current collect
   step:

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  run-frontier-push \
  --profile <profile-id> \
  --source-tiers A \
  --year-start <start-year> \
  --year-end <end-year> \
  --input <abs_ajg_4star-current-window.json> \
          <ft50-current-window.json> \
          <utd24-current-window.json>
```

Do not rely on default `source_records/*.json` discovery when historical
payloads exist. Mixed year windows can silently contaminate a frontier report.

## Defaults And Boundaries

- TA-only sources are `abs_ajg_4star`, `ft50`, and `utd24`.
- Tier B is configuration-only in the current catalog. Tier C is out of scope
  unless the user explicitly asks for early signals.
- For frontier semantics, default to the most recent roughly 18 months, or use
  the exact window the user specifies. Do not default to broad windows such as
  2023-2026 unless requested.
- Do not run `promote-frontier-candidates` until the user provides explicit
  `candidate_ids`.
- Do not modify `master_corpus.jsonl`, screening tables, full-text manifests,
  evidence tables, or review plans during a TA-only push run.

## Windows Path Note

For non-ASCII workspace paths on Windows, prefer a small Python wrapper that
calls `subprocess.run` with `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`.
Passing Chinese workspace paths directly through PowerShell can corrupt argv
encoding in some shells.

The wrapper should pass arguments as a list, not as a shell string.

## Verification

After the run, check:

- `09_frontier_push/source_records/` contains exactly the current TA payloads
  for the intended year window.
- `run-frontier-push` used `--source-tiers A` and explicit `--input` paths.
- `runs/<run-id>/candidates.jsonl` exists and contains only Tier A candidates.
- The report says candidates are advisory and not yet added to the corpus.
- `master_corpus.jsonl`, screening tables, manifests, evidence tables, and
  review plans are unchanged.

## Rollback

Delete only the generated artifacts from the current run:

- current-window TA JSON files under `09_frontier_push/source_records/`
- `09_frontier_push/runs/<run-id>/`
- the corresponding report under `09_frontier_push/reports/<profile-id>/`
- the consolidated RIS at `02_corpus/zotero_ris/frontier_push_<run-id>.ris`

Keep historical payloads unless the user explicitly asks to remove them.

## Promotion And Consolidated RIS

After the user picks `candidate_ids` to promote, run:

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  promote-frontier-candidates \
  --run-id <run-id> \
  --candidate-ids <fp_xxx1> <fp_xxx2> ...
```

This writes two files atomically:

- `01_search/raw_json/frontier_push_<run-id>.json` — the promoted JSON
  payload (input to `merge-search-results`).
- `02_corpus/zotero_ris/frontier_push_<run-id>.ris` — a single multi-record
  RIS file containing every promoted candidate, separated by blank lines.
  Open it in Zotero via File → Import to add all candidates in one action.

Do not produce per-paper `.ris` files; one consolidated file per run is the
canonical import format. Re-promoting the same `run-id` overwrites the
RIS with the latest candidate list.

The consolidated RIS is generated as a side-effect of `promote-frontier-candidates`;
there is no separate CLI command. Authors are written in `Last, First` form,
keywords are derived from each candidate's `match_reasons`, and an `N1` note
records the `candidate_id`, `source_id`, `source_tier`, `match_score`, and
`push_bucket` for audit.

Pass `--no-write-ris` to skip the RIS file and keep `promote-frontier-candidates`
as a single-purpose "promote only" command. The promoted JSON is always
written regardless of the flag.

## Known Limitation

Reports are currently named by date under `reports/<profile-id>/`. Multiple
runs for the same profile on the same day can overwrite the human-readable
report. Treat `runs/<run-id>/candidates.jsonl` as the durable candidate record,
or pass a stable `--run-id` and capture the report immediately.
