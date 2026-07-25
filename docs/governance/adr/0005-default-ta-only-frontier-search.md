# ADR 0005: Default Frontier Search To TA-Only

## Status

Accepted

## Context

The documentation described Tier A journals as the normal frontier source
policy, while the CLI silently defaulted to source tiers A and C.

## Decision

`run-frontier-push` defaults to the TA-only contract: FT50, UTD24, and ABS/AJG
4-star source payloads, explicit input files, and an explicit year window.
Broader retrieval remains available through `--expanded-search`. The existing
`--ta-only` option remains accepted for scripts that state the policy explicitly.

## Consequences

Ordinary runs fail early if current TA payloads or the year window are missing.
Flexible retrieval remains possible but can no longer happen by accident.
