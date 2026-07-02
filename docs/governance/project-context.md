# Project Context

This file is the implementation guide for agents working on `review-gen`.
Treat it as the project constitution. If a future change conflicts with this
file, pause and update the governance decision before editing code.

## Product Role

`review-gen` is a literature review workflow toolkit for management,
strategy, entrepreneurship, innovation, organization studies, economics, and
finance-adjacent review projects. Its core job is to turn a reusable literature
workspace into a traceable review pipeline.

The current workflow is:

1. Search ABS/AJG and OpenAlex sources.
2. Save raw search results.
3. Merge into `02_corpus/master_corpus.jsonl`.
4. Maintain title/abstract screening tables.
5. Prepare `04_fulltext/fulltext_manifest.csv`.
6. Download and convert PDFs when needed.
7. Chunk full-text Markdown for retrieval.
8. Build and approve `07_plan/review_plan.md`.
9. Generate writing packets and citation allowlists.
10. Draft only after the plan is approved.

## Critical Implementation Rules

- Preserve the existing review workflow. Do not replace it with a daily radar,
  Obsidian memory system, weekly report system, or unrelated research assistant.
- Do not delete or bypass the existing skills:
  - `skills/openalex-ajg-insights`
  - `skills/management-review-planner`
  - `skills/management-review-writer`
  - `skills/review-orchestrator`
- Keep new features optional unless the user explicitly approves changing the
  default workflow.
- Keep generated project outputs inside review workspaces, not in the repository
  root.
- Keep secrets in ignored env files. Never commit API keys, tokens, local
  credentials, reports with private data, downloaded PDFs, or generated full-text
  corpora.
- Prefer small files with clear responsibility. Avoid large rewrites of
  `review_workflow.py` unless a story explicitly scopes the split.
- Preserve user-edited screening, manifest, plan, and evidence fields. Automated
  updates must not overwrite manual judgments unless a command explicitly says so.

## Testing Rules

- Run `python -m unittest discover -s tests` before claiming a repo change is
  complete.
- New behavior needs either unit tests or offline fixtures.
- Network-dependent behavior must have offline test coverage.
- If a live API call is optional, failure must produce diagnostics or a prompt
  fallback rather than silently corrupting outputs.

## Git Rules

- Start every implementation by checking `git status`.
- Commit small, coherent changes. Separate documentation, configuration, code,
  and generated artifacts.
- Do not push unless the user asks.
- Do not revert user changes unless the user explicitly requests it.

## BMAD-Inspired Phase Mapping

- Analysis: clarify intent and success criteria.
- Planning: write or update product boundary, ADR, and story files.
- Solutioning: decide data flow, public commands, configuration, and tests.
- Implementation: execute one story at a time.
- Review: run tests and adversarially inspect the diff.
