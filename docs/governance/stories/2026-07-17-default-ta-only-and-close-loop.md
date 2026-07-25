# Default TA-Only And Close The Confirmed-Candidate Loop

## Intent

Make the documented TA source policy the CLI default and verify that one human
`include` decision drives promotion and PDF download without repeated IDs.

## Product Boundary Impact

Only the frontier-search CLI default changes. Frontier push remains optional,
and promotion still requires a human decision.

## Files And Data

The CLI, documentation, and offline tests change. No workspace or corpus format,
network provider, or generated project output changes.

## Tests

Verify default TA-only parsing, explicit expanded search, and the offline flow
from `review_decisions.jsonl` to promoted JSON and a validated PDF.

## Rollback

Restore the prior parser default and remove `--expanded-search`; the underlying
strict and flexible runners remain unchanged.

## Review Checklist

- Default behavior matches documentation.
- Expanded search remains explicit.
- One `include` decision is the only human selection step.
- The full unit test suite passes.
