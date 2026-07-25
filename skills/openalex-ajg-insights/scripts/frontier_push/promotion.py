from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .candidates import FrontierCandidate, load_candidates_jsonl
from .review_decisions import load_review_decisions


def _safe_stem(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "frontier_push"


def _candidate_to_raw_search_paper(
    candidate: FrontierCandidate,
    review_decision: dict[str, Any],
) -> dict[str, Any]:
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
        "frontier_review_decision": "include",
        "frontier_review_reason": str(review_decision.get("reason") or ""),
        "frontier_reviewer": str(review_decision.get("reviewer") or ""),
        "frontier_reviewed_at": str(review_decision.get("reviewed_at") or ""),
    }


def _author_to_ris(full_name: str) -> str:
    """Convert 'First Middle Last' -> 'Last, First Middle' for RIS AU field."""
    parts = str(full_name or "").strip().split()
    if len(parts) <= 1:
        return str(full_name or "")
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def _strip_doi_url(doi_url: str) -> str:
    text = str(doi_url or "")
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def _ris_collapse_whitespace(text: str) -> str:
    """RIS values must be single-line; collapse any whitespace to single spaces."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _derive_keywords(candidate: FrontierCandidate) -> list[str]:
    """Build a small keyword set from the candidate's match_reasons and source.

    We pull the matched phrase/term out of each match_reason (stripping the
    'exact phrase: ' / 'near phrase: ' / 'related term: ' prefixes) and add
    a couple of structural tags. This avoids hard-coding per-candidate_id
    keyword dictionaries and stays accurate to what the candidate actually
    matched on.
    """
    keywords: list[str] = []
    seen: set[str] = set()
    for reason in candidate.match_reasons:
        for prefix in ("exact phrase: ", "near phrase: ", "related term: "):
            if reason.startswith(prefix):
                phrase = reason[len(prefix):].strip()
                if phrase and phrase.lower() not in seen:
                    keywords.append(phrase)
                    seen.add(phrase.lower())
                break
    if candidate.source_id:
        keywords.append(candidate.source_id)
    if candidate.source_tier:
        keywords.append(f"tier {candidate.source_tier}")
    if candidate.push_bucket:
        keywords.append(candidate.push_bucket)
    return keywords


def _build_ris_record(candidate: FrontierCandidate) -> str:
    """Render one FrontierCandidate as a single RIS record (ends with ER -)."""
    title = _ris_collapse_whitespace(candidate.title)
    venue = _ris_collapse_whitespace(candidate.venue)
    year = candidate.year if candidate.year is not None else ""
    doi_url = candidate.doi or ""
    doi = _strip_doi_url(doi_url)
    landing = candidate.url or doi_url
    abstract = _ris_collapse_whitespace(candidate.abstract)
    authors = candidate.authors or []
    keywords = _derive_keywords(candidate)

    lines: list[str] = ["TY  - JOUR"]
    if title:
        lines.append(f"TI  - {title}")
    if venue:
        lines.append(f"T2  - {venue}")
    for author in authors:
        if author:
            lines.append(f"AU  - {_author_to_ris(author)}")
    if year:
        lines.append(f"PY  - {year}")
    if doi:
        lines.append(f"DO  - {doi}")
    if landing:
        lines.append(f"UR  - {_ris_collapse_whitespace(landing)}")
    if abstract:
        lines.append(f"AB  - {abstract}")
    for kw in keywords:
        lines.append(f"KW  - {_ris_collapse_whitespace(kw)}")
    note = (
        f"Candidate source: frontier push run, candidate_id={candidate.candidate_id}; "
        f"source_id={candidate.source_id}; source_tier={candidate.source_tier}; "
        f"match_score={candidate.match_score}; bucket={candidate.push_bucket}."
    )
    lines.append(f"N1  - {note}")
    lines.append("ER  -")
    return "\n".join(lines)


def write_consolidated_ris(workspace: Path, run_id: str, candidates: list[FrontierCandidate]) -> Path:
    """Write a single multi-record RIS file under 02_corpus/zotero_ris/.

    One record per promoted candidate; records are separated by a blank line
    per RIS convention. Overwrites any existing file at the same path so a
    re-promotion against the same run_id produces a fresh consolidated RIS.
    """
    target = workspace / "02_corpus" / "zotero_ris" / f"frontier_push_{_safe_stem(run_id)}.ris"
    target.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(_build_ris_record(c) for c in candidates) + "\n"
    target.write_text(body, encoding="utf-8")
    return target


def promote_frontier_candidates(
    workspace: Path,
    run_id: str,
    candidate_ids: list[str] | None = None,
    output_path: Path | None = None,
    write_ris: bool = True,
) -> dict[str, Any]:
    candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
    candidates = load_candidates_jsonl(candidates_path)
    by_id = {candidate.candidate_id: candidate for candidate in candidates}

    review_decisions = load_review_decisions(candidates_path.parent)
    included = {
        candidate_id
        for candidate_id, row in review_decisions.items()
        if row.get("decision") == "include"
    }
    selected_ids = candidate_ids or sorted(included)

    missing = [candidate_id for candidate_id in selected_ids if candidate_id not in by_id]
    if missing:
        raise ValueError(f"Candidate id(s) not found in run {run_id}: {', '.join(missing)}")

    not_included = [candidate_id for candidate_id in selected_ids if candidate_id not in included]
    if not_included:
        raise ValueError("Only candidates marked include can be promoted: " + ", ".join(not_included))
    selected = [by_id[candidate_id] for candidate_id in selected_ids]
    raw_output = output_path or workspace / "01_search" / "raw_json" / f"frontier_push_{_safe_stem(run_id)}.json"
    raw_output.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "search_type": "frontier_push",
        "query": "frontier push promoted candidates",
        "source_run_id": run_id,
        "count": len(selected),
        "papers": [
            _candidate_to_raw_search_paper(candidate, review_decisions[candidate.candidate_id])
            for candidate in selected
        ],
    }
    raw_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    ris_path: Path | None = None
    if write_ris:
        ris_path = write_consolidated_ris(workspace, run_id, selected)

    return {
        "workspace": str(workspace),
        "run_id": run_id,
        "selected_count": len(selected),
        "output_path": str(raw_output),
        "consolidated_ris_path": str(ris_path) if ris_path else None,
        "master_corpus_touched": False,
    }
