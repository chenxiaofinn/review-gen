from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .candidates import build_frontier_candidates, deduplicate_candidates, write_candidates_jsonl
from .profiles import InterestProfile
from .reports import render_frontier_report
from .source_collection import canonical_source_id, filter_records_by_year, record_year
from .sources import default_source_catalog


def frontier_root(workspace: Path) -> Path:
    return workspace / "09_frontier_push"


def source_tier_map(catalog: dict[str, Any] | None = None) -> dict[str, str]:
    resolved = catalog or default_source_catalog()
    tiers = {str(source["id"]): str(source["tier"]) for source in resolved.get("sources", [])}
    tiers["abs4_star"] = tiers.get("abs_ajg_4star", "A")
    tiers["utd24_ft50"] = tiers.get("ft50", "A")
    return tiers


def _filter_records_by_payload_bounds(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    excluded = 0
    for record in records:
        payload_start = record.get("_frontier_payload_year_start")
        payload_end = record.get("_frontier_payload_year_end")
        if not isinstance(payload_start, int) and not isinstance(payload_end, int):
            kept.append(record)
            continue
        year = record_year(record)
        if year is None:
            excluded += 1
            continue
        if isinstance(payload_start, int) and year < payload_start:
            excluded += 1
            continue
        if isinstance(payload_end, int) and year > payload_end:
            excluded += 1
            continue
        kept.append(record)
    return kept, excluded


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
        records, payload_excluded = _filter_records_by_payload_bounds(records)
        year_filter["excluded_by_payload_bounds"] += payload_excluded
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

