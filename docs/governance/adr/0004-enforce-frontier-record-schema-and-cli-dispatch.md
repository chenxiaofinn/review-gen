# ADR 0004: Enforce Frontier Source-Record Schema and CLI Dispatch

## Status

Accepted

## Context

The optional `09_frontier_push/` subflow ran into a real bug on 2026-07-03:

- `collect-frontier-sources` was registered in the CLI subparsers but never
  dispatched in `main()`, returning `Unsupported command: collect-frontier-sources`.
- The CLI arguments `--year-start` and `--year-end` for `run-frontier-push`
  were registered but never forwarded to the underlying function. As a result,
  `filter_records_by_year` was called with `year_start=None, year_end=None`,
  allowing out-of-range records (a 2023 Science paper) to slip into the
  candidate report.
- Manual replacement source records had inconsistent schemas: top-level
  `records` vs `papers`, single-record JSONs without provenance metadata,
  non-canonical `source_id` values such as `utd24_ft50`.

Combined, these three gaps caused the push run to return only two Tier A
candidates instead of an expected double-digit count.

## Decision

1. **CLI dispatch coverage.** `main()` must dispatch every command registered
   by `argparse`. Tests must enforce this so regressions cannot reintroduce
   the silent `Unsupported command` failure.

2. **Argument pass-through.** `run-frontier-push` and
   `collect-frontier-sources` must receive every CLI argument that their
   function signatures accept. Filters applied via CLI must reach the runner.

3. **Required source-record fields.** Files written under
   `09_frontier_push/source_records/` by the canonical collection path must
   carry these top-level keys:

   - `source_id`
   - `source_tier`
   - `source_type`
   - `profile_id`
   - `year_start`
   - `year_end`
   - `records`
   - `diagnostics` (optional but recommended)

   Validation must warn on missing fields but never silently overwrite an
   existing file. Loader must tolerate legacy files that predate this ADR by
   falling back to a derived `source_id` from the filename and default
   `year_start`/`year_end` to the CLI filter.

4. **Per-source year bounds.** The runner must apply each source payload's
   embedded `year_start`/`year_end` before scoring. Legacy files without those
   fields fall back to the CLI filter as today.

## Consequences

- A new validator function in `frontier_push/source_collection.py` reports
  per-file diagnostics.
- `init_frontier-push` returns a `source_record_warnings` list.
- A new regression test enumerates every CLI subcommand and asserts that
  `main()` branches cover all of them.
- Existing tests continue to pass; legacy files still load with warnings.

## Rollback

Revert the dispatch branch, the year-bounds pass-through, and the validator
function. Tests will fail loudly if any other code depends on the validator
output.
