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

## Testing And Git

- Start implementation by checking `git status`.
- Run `python -m unittest discover -s tests` before claiming completion.
- Keep commits small and coherent.
- Separate documentation, configuration, code, and generated outputs.
- Never commit secrets, downloaded PDFs, generated full-text corpora, caches, or
  private reports.
- Do not push unless the user explicitly asks.
