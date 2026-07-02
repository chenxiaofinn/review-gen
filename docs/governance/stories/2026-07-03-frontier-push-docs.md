# Story: Frontier Push Documentation

## Intent Gate

- User goal: Make the optional frontier push workflow discoverable and reproducible.
- Success criteria: README, Chinese guide, env example, and tests explain setup and commands.
- Non-goals: No generated reports or private workspace data committed.
- Rollback path: Revert documentation and env-example changes.

## Boundary Gate

- Existing workflow stages touched: Documentation only.
- Existing workspace files touched: None.
- Manual user fields preserved: Yes.
- Optional behavior remains optional: Yes.

## Architecture Gate

- Files to create: None unless needed for examples.
- Files to modify: README files, user guide, env example.
- Data read: Implemented CLI behavior.
- Data written: Documentation only.
- Network or LLM dependencies: None.
- Failure fallback: Document prompt-only mode.

## Test Plan

- Unit tests: Existing suite.
- Offline fixtures: Not needed.
- Commands to run: `python -m unittest discover -s tests`.

## Review Gate

- Product drift checked: Yes.
- Compatibility checked: Yes.
- Overwrite risk checked: Yes.
- Diff size checked: Yes.
