from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .candidates import build_frontier_candidates, deduplicate_candidates, write_candidates_jsonl
from .profiles import InterestProfile
from .reports import render_frontier_report
from .source_collection import canonical_source_id, filter_records_by_year
from .sources import default_source_catalog


def frontier_root(workspace: Path) -> Path:
    return workspace / "09_frontier_push"


def source_tier_map(catalog: dict[str, Any] | None = None) -> dict[str, str]:
    resolved = catalog or default_source_catalog()
    tiers = {str(source["id"]): str(source["tier"]) for source in resolved.get("sources", [])}
    tiers["abs4_star"] = tiers.get("abs_ajg_4star", "A")
    tiers["utd24_ft50"] = tiers.get("ft50", "A")
    return tiers


def _resolve_input_year_bounds(
    workspace: Path,
    records_by_source: dict[str, list[dict[str, Any]]],
) -> dict[str, tuple[int | None, int | None]]:
    """Map each canonical source_id to its payload year bounds if available.

    Files written by ``collect-frontier-sources`` carry ``year_start`` /
    ``year_end`` at the payload level. Files written before ADR-0004 do not;
    the loader returns ``(None, None)`` for them so the CLI filter still
    applies downstream.
    """
    sources_root = workspace / "09_frontier_push" / "source_records"
    bounds: dict[str, tuple[int | None, int | None]] = {}
    if not sources_root.exists():
        return bounds
    for payload_path in sorted(sources_root.glob("*.json")):
        try:
            data = json.loads(payload_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        raw_id = data.get("source_id") or payload_path.stem
        canonical = canonical_source_id(str(raw_id))
        bounds[canonical] = (
            data.get("year_start") if isinstance(data.get("year_start"), int) else None,
            data.get("year_end") if isinstance(data.get("year_end"), int) else None,
        )
    return bounds


def run_frontier_push_from_records(
    workspace: Path,
    profile: InterestProfile,
    records_by_source: dict[str, list[dict[str, Any]]],
    source_tiers: list[str],
    run_id: str | None = None,
    catalog: dict[str, Any] | None = None,
    year_start: int | None = None,
    year_end: int | None = None,
) -> dict[str, Any]:
    resolved_run_id = run_id or datetime.now().strftime("%Y-%m-%dT%H%M%S")
    tiers_by_source = source_tier_map(catalog)
    allowed_tiers = set(source_tiers)

    payload_bounds = _resolve_input_year_bounds(workspace, records_by_source)

    candidates = []
    year_filter = {
        "input_records": 0,
        "kept_records": 0,
        "excluded_out_of_range": 0,
        "excluded_missing_year": 0,
        "excluded_by_payload_bounds": 0,
    }
    for raw_source_id, records in records_by_source.items():
        source_id = canonical_source_id(raw_source_id)
        tier = tiers_by_source.get(source_id, tiers_by_source.get(raw_source_id, "C"))
        if tier not in allowed_tiers:
            continue
        payload_start, payload_end = payload_bounds.get(source_id, (None, None))
        if payload_start is not None or payload_end is not None:
            within_payload, payload_stats = filter_records_by_year(
                records, year_start=payload_start, year_end=payload_end
            )
            year_filter["excluded_by_payload_bounds"] += payload_stats[
                "excluded_out_of_range"
            ] + payload_stats["excluded_missing_year"]
            records = within_payload
        filtered_records, stats = filter_records_by_year(records, year_start=year_start, year_end=year_end)
        for key in year_filter:
            if key == "excluded_by_payload_bounds":
                continue
            year_filter[key] += stats[key]
        candidates.extend(
            build_frontier_candidates(
                filtered_records,
                profile,
                source_id=source_id,
                source_tier=tier,
            )
        )

    deduped = deduplicate_candidates(candidates)
    root = frontier_root(workspace)
    candidates_path = root / "runs" / resolved_run_id / "candidates.jsonl"
    report_path = root / "reports" / profile.id / f"{resolved_run_id[:10]}.md"

    write_candidates_jsonl(candidates_path, deduped)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_frontier_report(profile, deduped, run_id=resolved_run_id),
        encoding="utf-8",
    )

    return {
        "workspace": str(workspace),
        "profile_id": profile.id,
        "run_id": resolved_run_id,
        "candidate_count": len(deduped),
        "candidates_path": str(candidates_path),
        "report_path": str(report_path),
        "source_tiers": sorted(allowed_tiers),
        "year_filter": year_filter,
    }

