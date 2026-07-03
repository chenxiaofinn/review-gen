# ADR 0003: Unify Frontier Source Catalog With AJG Journal Resolution

## Status

Accepted

## Context

The existing review workflow searches ABS/AJG journals through the bundled
OpenAlex/AJG bridge and its AJG CSV. The optional `09_frontier_push` workflow
introduced a YAML source catalog, but the YAML initially described source tiers
without resolving them into concrete journal ISSNs. That created confusing
results: `sources.yml` looked broad, while `run-frontier-push` only consumed the
small JSON files already present in `source_records/`.

The user clarified that Tier A journal collection should use only AJG 4*, FT50,
and UTD24. AJG 3+ should not be added as a fallback.

## Decision

Frontier push source collection will remain an optional workspace subflow, but
its Tier A journal sources must resolve through the same AJG CSV-backed OpenAlex
capability used by the main workflow.

The active Tier A journal source ids are:

- `abs_ajg_4star`
- `ft50`
- `utd24`

`ft50` and `utd24` are named journal pools resolved against the AJG CSV for
ISSNs. Unresolved journal names must be reported in collection diagnostics.
`abs_ajg_3plus` is intentionally out of scope.

## Consequences

- `sources.yml` remains a workspace-local strategy snapshot, not a second source
  of truth for ISSNs.
- Candidate promotion still requires user confirmation and does not directly
  touch `02_corpus/master_corpus.jsonl`.
- Multi-round fetching is allowed for coverage, but it must write metadata into
  `09_frontier_push/source_records/` before `run-frontier-push` creates a report.
- FT50/UTD24 list maintenance is explicit and reviewable; future list revisions
  require a small source-list update rather than hidden code behavior.

## Rollback

Remove the collection command and restore the prior `sources.yml` defaults. The
existing main review workflow and already promoted corpus files remain unaffected.
