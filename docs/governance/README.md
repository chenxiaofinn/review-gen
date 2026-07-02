# review-gen Governance

This folder defines the lightweight BMAD-style development guardrails for
`review-gen`. It adopts BMAD's staged context discipline without installing the
BMAD toolchain or changing the product into a different system.

## Required Development Gates

Every non-trivial change must pass these gates before implementation:

1. **Intent Gate**: State the user goal, success criteria, non-goals, and rollback path.
2. **Boundary Gate**: State whether the change affects the existing search, corpus,
   manifest, planner, or writer workflow.
3. **Architecture Gate**: State the files, data flow, configuration, failure modes,
   and fallback behavior.
4. **Story Gate**: Split the change into small stories that can be tested, committed,
   and reverted independently.
5. **Review Gate**: Run tests and perform an adversarial review for product drift,
   compatibility breakage, and over-refactoring.

## Canonical Governance Files

- `project-context.md`: implementation rules and current system context.
- `product-boundary.md`: what this product is and is not allowed to become.
- `review-checklist.md`: pre-implementation, pre-commit, and pre-push checks.
- `adr/`: architectural decisions that affect long-term maintenance.
- `stories/`: implementation story template and future story files.

## BMAD References

- https://github.com/bmad-code-org/BMAD-METHOD
- https://docs.bmad-method.org/reference/workflow-map/
- https://docs.bmad-method.org/explanation/project-context/
- https://docs.bmad-method.org/explanation/preventing-agent-conflicts/
- https://docs.bmad-method.org/how-to/established-projects/
