from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .candidates import load_candidates_jsonl


ALLOWED_DECISIONS = {"include", "exclude", "hold"}


def load_review_decisions(run_dir: Path) -> dict[str, dict[str, Any]]:
    decisions_path = run_dir / "review_decisions.jsonl"
    if not decisions_path.exists():
        raise ValueError(
            "review_decisions.jsonl is missing; record human decisions first and mark candidates as include."
        )
    decisions: dict[str, dict[str, Any]] = {}
    for line in decisions_path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        candidate_id = str(row.get("candidate_id") or "").strip()
        if candidate_id:
            decisions[candidate_id] = row
    return decisions


def load_included_candidate_ids(run_dir: Path) -> set[str]:
    return {
        candidate_id
        for candidate_id, row in load_review_decisions(run_dir).items()
        if row.get("decision") == "include"
    }


def record_frontier_review(
    workspace: Path,
    run_id: str,
    decisions_path: Path,
    reviewer: str,
) -> dict[str, Any]:
    candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
    candidates = {candidate.candidate_id for candidate in load_candidates_jsonl(candidates_path)}
    if not candidates_path.exists():
        raise FileNotFoundError(f"Candidate report not found: {candidates_path}")

    rows = json.loads(decisions_path.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list):
        raise ValueError("Review decisions JSON must be a list of objects.")

    now = datetime.now(timezone.utc).isoformat()
    output_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each review decision must be an object.")
        candidate_id = str(row.get("candidate_id") or "").strip()
        decision = str(row.get("decision") or "").strip().lower()
        if candidate_id not in candidates:
            raise ValueError(f"Unknown candidate_id: {candidate_id}")
        if candidate_id in seen:
            raise ValueError(f"Duplicate candidate_id: {candidate_id}")
        if decision not in ALLOWED_DECISIONS:
            raise ValueError(f"decision must be one of: {', '.join(sorted(ALLOWED_DECISIONS))}")
        seen.add(candidate_id)
        output_rows.append({
            "candidate_id": candidate_id,
            "decision": decision,
            "reason": str(row.get("reason") or "").strip(),
            "reviewer": reviewer,
            "reviewed_at": str(row.get("reviewed_at") or now),
        })

    output_path = workspace / "09_frontier_push" / "runs" / run_id / "review_decisions.jsonl"
    output_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    return {"run_id": run_id, "decision_count": len(output_rows), "output_path": str(output_path)}
