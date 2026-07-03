from __future__ import annotations

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
    }
    for raw_source_id, records in records_by_source.items():
        source_id = canonical_source_id(raw_source_id)
        tier = tiers_by_source.get(source_id, tiers_by_source.get(raw_source_id, "C"))
        if tier not in allowed_tiers:
            continue
        filtered_records, stats = filter_records_by_year(records, year_start=year_start, year_end=year_end)
        for key in year_filter:
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

