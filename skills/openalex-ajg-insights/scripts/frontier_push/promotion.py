from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .candidates import FrontierCandidate, load_candidates_jsonl


def _safe_stem(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "frontier_push"


def _candidate_to_raw_search_paper(candidate: FrontierCandidate) -> dict[str, Any]:
    abstract = candidate.abstract or ""
    return {
        "title": candidate.title,
        "year": candidate.year,
        "journal": candidate.venue,
        "authors": candidate.authors,
        "citations": 0,
        "doi": candidate.doi,
        "openalex_id": candidate.openalex_id,
        "landing_page_url": candidate.url,
        "abstract": abstract,
        "abstract_word_count": len(abstract.split()) if abstract else 0,
        "full_text_priority": {
            "priority": "medium" if candidate.push_bucket == "main_push" else "low",
            "reasons": [
                "Promoted from frontier push candidate report.",
                *candidate.match_reasons[:3],
            ],
            "heuristic_only": True,
        },
        "frontier_candidate_id": candidate.candidate_id,
        "frontier_source_id": candidate.source_id,
        "frontier_source_tier": candidate.source_tier,
        "frontier_push_bucket": candidate.push_bucket,
        "frontier_match_score": candidate.match_score,
    }


def promote_frontier_candidates(
    workspace: Path,
    run_id: str,
    candidate_ids: list[str],
    output_path: Path | None = None,
) -> dict[str, Any]:
    candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
    candidates = load_candidates_jsonl(candidates_path)
    by_id = {candidate.candidate_id: candidate for candidate in candidates}

    missing = [candidate_id for candidate_id in candidate_ids if candidate_id not in by_id]
    if missing:
        raise ValueError(f"Candidate id(s) not found in run {run_id}: {', '.join(missing)}")

    selected = [by_id[candidate_id] for candidate_id in candidate_ids]
    raw_output = output_path or workspace / "01_search" / "raw_json" / f"frontier_push_{_safe_stem(run_id)}.json"
    raw_output.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "search_type": "frontier_push",
        "query": "frontier push promoted candidates",
        "source_run_id": run_id,
        "count": len(selected),
        "papers": [_candidate_to_raw_search_paper(candidate) for candidate in selected],
    }
    raw_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "workspace": str(workspace),
        "run_id": run_id,
        "selected_count": len(selected),
        "output_path": str(raw_output),
        "master_corpus_touched": False,
    }

