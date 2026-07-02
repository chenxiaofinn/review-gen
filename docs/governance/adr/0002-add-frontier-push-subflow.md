# ADR 0002: Add Optional Frontier Push Subflow

## Status

Accepted

## Context

`review-gen` is a structured literature review workflow toolkit. The existing
workflow is centered on reusable workspaces, search results, corpus merging,
full-text preparation, planning, and citation-safe writing.

Users also need a long-running way to track research-frontier papers by topic.
This must not turn the project into a standalone daily radar product or bypass
the existing review workflow.

## Decision

Add `frontier_push` as an optional workspace subflow under
`09_frontier_push/`.

The subflow may:

- maintain durable topic profiles,
- draft reviewable `InterestProfile` YAML files with LLM help,
- collect Tier A and Tier C frontier candidates,
- write candidate reports,
- generate paper-decomposition prompts or outputs,
- promote user-confirmed candidates into the existing raw-search layer.

The subflow must not:

- replace `01_search/` through `08_outputs/`,
- write directly to `02_corpus/master_corpus.jsonl`,
- delete or bypass planner, writer, or orchestrator skills,
- make LLM access mandatory,
- add Tier B conference crawling in the first implementation.

## Data Layout

The workspace subflow uses these paths:

- `09_frontier_push/sources.yml`
- `09_frontier_push/profiles/<profile-id>.yml`
- `09_frontier_push/runs/<run-id>/candidates.jsonl`
- `09_frontier_push/reports/<profile-id>/<date>.md`
- `09_frontier_push/deep_reads/<paper-key>.md`

## CLI Surface

The review workflow CLI may add these optional commands:

- `init-frontier-push`
- `draft-interest-profile --intent "..."`
- `run-frontier-push --profile <id> --source-tiers A,C`
- `promote-frontier-candidates --run-id <id> --candidate-ids ...`
- `decompose-paper --paper-key <key>`

## Consequences

- Existing review workflows remain unchanged by default.
- Frontier candidates enter a report before they enter corpus tooling.
- User confirmation is required before promotion.
- LLM failures degrade to prompt fallback.
- Tier B is documented as a future source class, not crawled in v1.

## Rollback

Remove the optional `frontier_push` module, the CLI subcommands, and the
`09_frontier_push/` workspace files. Existing review workspaces and core
corpus/planner/writer behavior do not need migration.
