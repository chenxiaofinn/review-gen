# Budgeted ISSN-Chunked OpenAlex Search

## Intent

Prevent silent journal truncation, duplicate paid searches, global relevance
window misses, and false zero-result reports while keeping OpenAlex usage
bounded and reviewable.

## Product Boundary Impact

This changes the search and frontier-source collection stages only. It does not
change corpus promotion, screening, full text, planning, or writing gates.

## Expected Changes

- Shared OpenAlex client: complete ISSN-set chunking and classified errors.
- OpenAlex bridge and frontier collector: one non-descriptive query or at most
  two deterministic descriptive queries over the deduplicated ISSN union,
  followed by local per-source partitioning.
- Orchestrator diagnostics and tests: distinguish complete, partial, and failed
  collection and honor workspace-configured Tier-A sources.

## Data Behavior

Read the existing AJG CSV, profile, and frontier settings. Preview the exact
and exact-plus-near descriptive queries offline, require the user to persist
`max_queries`, then query OpenAlex once per selected query and 50-ISSN chunk.
Merge and deduplicate works, preserve matched queries, and atomically replace
current-window source payloads only after every chunk succeeds.

## Tests

- More than 50 ISSNs remain eligible, including the final chunk.
- Descriptive synonyms are ORed within groups and required groups are ANDed.
- `max_queries=1` executes the exact descriptive query only.
- `max_queries=2` executes exact followed by exact-plus-near.
- Missing or invalid `max_queries` fails before network access.
- Related terms are not sent as standalone OpenAlex queries.
- Overlapping source pools reuse the same ISSN-union results.
- The default profile contributes one semantic query.
- ABS3-only workspace settings satisfy runner and orchestrator source checks.
- Budget, timeout, and API errors write no source payloads.
- Genuine zero results and per-chunk result caps are explicit.
- The 2025 A-share asset-price-bubbles ABS3 regression reaches candidates even
  without an OpenAlex abstract.

## Rollback

Revert ADR 0006 implementation changes; existing workspaces and historical
reports remain readable.

## Review Checklist

- Preserve existing CLI names and source payload fields.
- Do not auto-page or auto-promote.
- Run targeted OpenAlex/frontier tests and the full unit test suite.
