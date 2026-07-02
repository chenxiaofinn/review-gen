# ADR 0001: Adopt Lightweight BMAD Governance

## Status

Accepted

## Context

`review-gen` is an existing literature review workflow toolkit. Future work will
add targeted literature-push and LLM-assisted paper decomposition features. A
previous related project drifted after large uncommitted rewrites and conflicting
architecture rules. The project needs explicit guardrails before new feature
work starts.

BMAD-METHOD offers a staged approach: analysis, planning, solutioning,
implementation, and review. Its useful lesson for this repository is structured
context, not wholesale framework installation.

## Decision

Adopt a lightweight BMAD-inspired governance layer under `docs/governance/`.

Do not install the BMAD toolchain in this repository for now. Instead, use local
documents to define:

- project context,
- product boundary,
- development gates,
- ADR expectations,
- story expectations,
- review checklist.

## Consequences

- Feature work must be split into reviewable stories.
- Product-boundary changes must be explicit ADRs.
- Literature push must remain an optional workspace subflow unless a later ADR
  changes that decision.
- Agents must read these governance files before major edits.
- The repository gains process documentation but no new runtime dependency.
