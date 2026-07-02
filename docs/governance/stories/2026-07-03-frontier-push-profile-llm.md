# Story: Frontier Push Profile And LLM Drafting

## Intent Gate

- User goal: Maintain long-running topic profiles and draft them from Chinese intent.
- Success criteria: YAML `InterestProfile` files can be created, loaded, validated, and drafted with an LLM prompt fallback.
- Non-goals: No automatic corpus merge, no final topic approval without user review.
- Rollback path: Remove profile module, CLI command, and tests.

## Boundary Gate

- Existing workflow stages touched: Workspace initialization and optional CLI only.
- Existing workspace files touched: `09_frontier_push/` only.
- Manual user fields preserved: Existing screening, manifest, corpus, and plan fields are untouched.
- Optional behavior remains optional: Yes.

## Architecture Gate

- Files to create: `frontier_push` profile and LLM modules, tests.
- Files to modify: `review_workflow.py`, `requirements.txt`, env example.
- Data read: User intent, profile YAML, env values.
- Data written: Profile YAML draft or prompt fallback output.
- Network or LLM dependencies: OpenAI-compatible API only when configured.
- Failure fallback: Emit a complete prompt and a machine-readable fallback status.

## Test Plan

- Unit tests: Profile validation, directionality fields, prompt fallback.
- Offline fixtures: Fake env without API key.
- Commands to run: `python -m unittest discover -s tests`.

## Review Gate

- Product drift checked: Yes.
- Compatibility checked: Yes.
- Overwrite risk checked: Yes.
- Diff size checked: Yes.
