# Architecture Decision Records

Use ADRs for decisions that affect multiple files, long-term maintenance, or
future agent behavior.

## When To Write An ADR

Write an ADR when a change:

- changes product boundaries,
- adds or removes a persistent workspace directory,
- changes public CLI commands,
- changes data formats used across workflow stages,
- adds a new external service, model, or network dependency,
- changes how user-edited fields are preserved,
- changes testing or release expectations.

## ADR Format

Each ADR should use this shape:

```markdown
# ADR NNNN: Title

## Status

Accepted | Superseded | Proposed

## Context

Why the decision matters.

## Decision

What we chose.

## Consequences

Trade-offs and follow-up requirements.
```
