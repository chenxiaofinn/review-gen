# ADR 0006: Use Budgeted ISSN-Chunked OpenAlex Search

## Status

Accepted

## Context

The shared OpenAlex client truncated journal filters to the first 50 ISSNs.
Frontier collection also repeated each query across overlapping ABS/AJG, FT50,
and UTD24 pools. This caused silent coverage gaps, duplicate paid searches, and
timeouts. API failures, including budget exhaustion, were converted to empty
results and could be mistaken for a genuine zero-result search.

A one-page global-search prototype removed the ISSN cutoff, but its top-100
relevance window missed the known 2025 ABS3 regression paper even though the
same query found it when constrained to its journal. Raising the global window
to 200 still missed it. Pure global search is therefore retained as an explicit
client capability, not used as the default source-collection path.

## Decision

The complete union of requested journal ISSNs is deduplicated, split into
chunks of at most 50 ISSNs, and searched with at most five concurrent requests
per query. Each chunk returns at most 100 works by default. Results are
deduplicated and then matched locally against every requested source pool.

Descriptive profiles compile deterministically into at most two ordered
queries without adding profile fields. Query 1 uses the exact phrases present
in every required concept group. Query 2 uses the exact and near phrases
present in every group. Terms are joined with `OR` within a group and required
groups with `AND`; no synonym Cartesian product is generated. Non-descriptive
profiles retain one exact-plus-near `OR` query. Related terms, exclusions,
directionality, and JEL codes remain candidate-layer or metadata concerns.

Before collection, `preview-frontier-queries` shows the compiled queries and
estimated ISSN-chunk request count without network access. New workspaces do
not receive a hidden `max_queries` default. The user records `max_queries` in
`frontier_settings.yml` after reviewing the preview; collection rejects a
missing or out-of-range value before calling OpenAlex. Existing workspace
values remain valid. The shared client executes the selected queries in order,
deduplicates works, preserves matched query expressions, and reports
per-query completeness.

The shared client raises classified errors for budget exhaustion, timeout, and
other API failures. Failed collection does not replace existing source records.
If any ISSN chunk reports more results than were retrieved, the collection is
marked partial and cannot be used for candidate scoring.

Single-journal searches continue to use the journal ISSN filter directly.

## Consequences

- Paid volume is bounded by `max_queries * ceil(unique ISSNs / 50)` requests
  before pagination; the preview reports this estimate.
- Every requested ISSN is searched; there is no first-50 cutoff.
- Overlapping source pools reuse the same union search and do not multiply
  requests.
- TA-only completeness is evaluated against the active workspace settings,
  rather than a hard-coded global source list.
- Existing source-record schemas, candidate reports, and promotion gates remain
  unchanged.
- Rollback restores the earlier per-source loop; the rejected global-default
  prototype remains documented here to prevent recurrence.
