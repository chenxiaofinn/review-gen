# Frontier Push TA-Only Runbook

## User-facing three-stage model

The detailed commands below implement three simple user stages:

1. Generate and confirm the search configuration.
2. Review and confirm candidates.
3. Connect confirmed candidates to the review workflow and process full text.

The workspace boundaries are: `09_frontier_push/` candidate area,
`01_search/` confirmed raw-search inputs, `02_corpus/` formal review corpus,
and `04_fulltext/` full-text processing area.

Use this runbook when a user asks for a frontier-push run limited to Tier A
sources. It preserves the workspace subflow: candidates go to a push report
first, and promotion requires an explicit human `include` decision.

When a new agent resumes the workspace, it should read this runbook, run the
read-only status command, report the current stage and next action, and pause
at any human confirmation gate. No hook or agent-specific chat state is
required; the workspace artifacts are the handoff record.

## Standard Flow

After drafting a profile, inspect its `.audit.yml`. If the audit status is
`needs_revision`, summarize the suggestions and wait for explicit user
confirmation. Record `accepted`, `partially_accepted`, or `rejected` under
`user_decision.status`; `pending` blocks every profile-driven OpenAlex call,
including collection. Apply only the profile edits the user confirmed.

1. Confirm the workspace and profile exist.
2. Run `init-frontier-push` idempotently.
3. Review or edit the workspace settings file:

```text
<review-workspace>/09_frontier_push/frontier_settings.yml
```

The default file created by `init-frontier-push` is:

```yaml
source_ids:
  - abs3
year_start: 2025
year_end: 2026
limit_per_query: 100
```

4. After the profile is reviewed, preview its queries without network access:

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  preview-frontier-queries \
  --profile <profile-id>
```

For descriptive profiles, round 1 uses exact phrases in every required concept
group. Round 2 uses exact plus near phrases in every group. Both use OR within
groups and AND between groups. Every exact or near query term must belong to a
required concept group; otherwise audit, preview, collection, bridge, and MCP
profile execution stop instead of silently ignoring the term. Add
`max_queries: 1` or `max_queries: 2` to
`frontier_settings.yml` after reviewing the expressions and estimated request
count. Collection does not use a hidden default and fails before network
access when this setting is missing or invalid.

5. Run `collect-frontier-sources` for TA sources only. If omitted, source ids,
   year window, and limits are read from `frontier_settings.yml`; command-line
   arguments override the settings file for one run:

   Collection compiles only the user-approved number of queries. It
   deduplicates the complete requested ISSN union, searches it in chunks of at
   most 50 ISSNs, and partitions the merged results locally into each source
   pool. Per-query `has_more` is retained; any partial query marks the source
   payloads partial and blocks candidate scoring.

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  collect-frontier-sources \
  --profile <profile-id>
```

6. Run `run-frontier-push` with explicit input files from the current collect
   step:

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  run-frontier-push \
  --profile <profile-id> \
  --year-start <start-year> \
  --year-end <end-year> \
  --input <abs_ajg_4star-current-window.json> \
          <ft50-current-window.json> \
          <utd24-current-window.json>
```

TA-only is the default path; `--ta-only` remains available when an explicit
declaration is useful. In this mode the command
rejects missing explicit inputs, missing year windows, non-TA payloads, missing
TA sources, profile mismatches, and payload year-window mismatches before writing
candidate or report artifacts. Use `--expanded-search` to opt into broader
source-tier choices and default source-record discovery.

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
- `run-frontier-push` used the default TA-only mode and explicit `--input` paths.
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
Status diagnostics group source records by profile and year window and use the
most recently updated group as the current collection; older complete windows
remain valid history and do not trigger a mixed-record warning.

## Promotion And Consolidated RIS

After the user records review decisions and marks candidates as `include`, run
promotion without listing candidate IDs:

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  promote-frontier-candidates \
  --run-id <run-id>
```

The command processes all `include` candidates. Use `--candidate-ids` only to
retry or process a smaller explicit subset.

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

## Recording Candidate Review Decisions

Before promotion, human decisions can be recorded in a UTF-8 JSON file. The
file must contain a list of objects with `candidate_id`, `decision`, and an
optional `reason`. Decisions are `include`, `exclude`, or `hold`.

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  record-frontier-review \
  --run-id <run-id> \
  --decisions-file <review-decisions.json> \
  --reviewer <name>
```

The command writes `09_frontier_push/runs/<run-id>/review_decisions.jsonl`.
Promotion now uses `include` decisions as its only human selection step;
recording a decision does not promote a paper automatically until the
promotion command is run.

## Stage 3: Full-text processing and required frontier brief

After candidate confirmation, record the candidate as `include` in
`review_decisions.jsonl`, then use the narrow PDF step if desired. The command
rejects candidates that are not marked `include`:

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  download-frontier-pdfs \
  --run-id <run-id>
```

The command processes all `include` candidates. Use `--candidate-ids` only for
a smaller retry subset.

This tries OpenAlex, and tries Unpaywall only when `--email` is provided.
Successful files go to `04_fulltext/pdf_inbox/`. Other candidates are listed
in `09_frontier_push/runs/<run-id>/manual_download.tsv`. This step does not
promote candidates, modify the corpus, or operate Zotero.

The frontier workflow does not end at candidate review or PDF collection. Its
complete closure is:

```text
record review -> promote -> merge -> prepare manifest -> download PDF
-> convert with MinerU -> generate frontier brief
```

Promotion carries the human `include` decision, reviewer, review time, and
reason into the raw search record. On the first merge, a new screening row
inherits `included_title_abstract=yes` and `need_full_text=yes`; existing
manual screening values are never overwritten.

After the included PDFs
are represented in `04_fulltext/fulltext_manifest.csv`, convert them with the
existing MinerU command:

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  convert-pdfs-with-mineru \
  --env-path <review-workspace>/04_fulltext/mineru.env
```

MinerU writes extracted Markdown under `05_mineru/extracted/` and records the
resolved Markdown path in `04_fulltext/fulltext_manifest.csv`. Then generate
one brief for the reviewed frontier run:

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  generate-frontier-brief \
  --run-id <run-id> \
  --profile <profile-id>
```

The output is `09_frontier_push/briefs/<run-id>.md`. Format version `1.0` has
fixed sections for batch metadata, executive summary, paper cards, synthesis,
research implications, evidence boundaries, and input provenance. The
renderer validates that the LLM returns exactly the included candidate ids and
records each Markdown input path and SHA-256 hash. The structure and source
inputs are reproducible; model wording is not guaranteed to be byte-identical.

The brief completes the frontier-push run. Formal review writing
still uses `02_corpus/master_corpus.jsonl` and the existing screening, full-text,
planning, and citation-allowlist gates. Promoted frontier records retain
`source_run_id` and candidate provenance in the corpus so a brief can be traced
back to its candidate run without creating a second writing evidence pipeline.
When a brief exists for the latest run, status reports the frontier subflow as
complete and presents chunking as an optional continuation into the main review.
