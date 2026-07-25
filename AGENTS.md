# AGENTS.md

This file is the first-stop instruction sheet for AI agents working in
`review-gen`. Keep it short. Detailed governance lives under
`docs/governance/`.

## Required Context

Before any non-trivial change, read these files:

- `docs/governance/project-context.md`
- `docs/governance/product-boundary.md`
- `docs/governance/review-checklist.md`

For architecture or product-boundary changes, also read:

- `docs/governance/adr/README.md`
- `docs/governance/stories/README.md`

## Hard Boundaries

- Preserve `review-gen` as a structured literature review workflow toolkit.
- Do not refactor it into a standalone daily radar, Obsidian memory system,
  weekly newsletter generator, generic AI reading companion, or unrelated
  agent framework.
- Do not delete or bypass these core skills:
  - `skills/openalex-ajg-insights`
  - `skills/management-review-planner`
  - `skills/management-review-writer`
  - `skills/review-orchestrator`
- Keep new features optional unless the user explicitly approves a default
  workflow change.
- Do not overwrite user-edited screening, manifest, evidence, or plan fields
  unless a command explicitly asks for that behavior.

## Development Gates

Every substantial change must pass these gates:

1. Intent Gate: state the user goal, success criteria, non-goals, and rollback path.
2. Boundary Gate: state whether search, corpus, manifest, planner, writer, or
   orchestrator behavior changes.
3. Architecture Gate: state files, data flow, configuration, failure modes, and tests.
4. Story Gate: split large work into small, testable, revertible stories.
5. Review Gate: run tests and inspect for product drift, compatibility breakage,
   and over-refactoring.

## Literature Push Rules

Literature push work must remain a workspace subflow.

- Candidate papers go to a push report first.
- User confirmation is required before promotion into `master_corpus.jsonl`.
- LLM output is advisory and reviewable.
- Missing LLM credentials must produce a prompt fallback, not a failed workflow.
- Distinguish "factors of X" from "effects of X" unless the user requests both.
- Before drafting a frontier profile, obtain or infer the user's explicit search
  shape: `factors_of`, `effects_of`, or an A-and-B `descriptive` relationship.
- If a profile audit returns `needs_revision`, summarize its suggestions and
  wait for explicit user confirmation. Do not edit the profile or run frontier
  search while `user_decision.status` is `pending`.

## Agent Start Protocol

When resuming any review workspace, the agent must:

1. Read this file and the applicable governance runbook.
2. Run the read-only workflow status command.
3. Report what is complete, what is missing, and the recommended next action.
4. Ask the user only when `blocked_by_human` or another explicit confirmation
   gate requires a decision.

The workspace files and status output are the durable handoff contract. This
protocol does not depend on a browser hook, a particular agent, or a chat
session.

## Frontier Push Runbook

Use `docs/governance/runbooks/frontier-push-ta-only.md` for TA-only
frontier-push runs.

- TA-only source requirements come from the active workspace
  `09_frontier_push/frontier_settings.yml`; legacy workspaces without settings
  fall back to the supported Tier-A source set.
- Match the year window to frontier semantics: default to the most recent
  roughly 18 months, or to the user's explicit window.
- Pass explicit `--input` files to `run-frontier-push` from the current
  `collect-frontier-sources` call; do not rely on historical
  `source_records/*.json` auto-discovery.
- Do not run Tier B or Tier C sources unless the user explicitly asks.
- Do not promote candidates unless the user has marked them `include` in the
  run's review decisions. Candidate IDs are optional and only narrow retries.
- On Windows, prefer a UTF-8 Python subprocess runner for non-ASCII workspace
  paths.
- Never write API keys or tokens into logs.

## Testing And Git

- Start implementation by checking `git status`.
- Run `python -m unittest discover -s tests` before claiming completion.
- Keep commits small and coherent.
- Separate documentation, configuration, code, and generated outputs.
- Never commit secrets, downloaded PDFs, generated full-text corpora, caches, or
  private reports.
- Do not push unless the user explicitly asks.
