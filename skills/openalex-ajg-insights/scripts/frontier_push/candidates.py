from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .profiles import InterestProfile


TIER_PRIORITY = {"A": 3, "B": 2, "C": 1}


@dataclass
class FrontierCandidate:
    candidate_id: str
    title: str
    year: int | None
    venue: str
    authors: list[str]
    doi: str
    openalex_id: str
    url: str
    abstract: str
    source_id: str
    source_tier: str
    source_type: str
    match_score: int
    match_reasons: list[str]
    push_bucket: str
    strong_signal: bool

    @property
    def topic_match_score(self) -> int:
        """Mechanical topic-match score; not a paper-quality judgment."""
        return self.match_score

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FrontierCandidate":
        return cls(
            candidate_id=str(payload.get("candidate_id", "")),
            title=str(payload.get("title", "")),
            year=payload.get("year"),
            venue=str(payload.get("venue", "")),
            authors=list(payload.get("authors") or []),
            doi=str(payload.get("doi", "")),
            openalex_id=str(payload.get("openalex_id", "")),
            url=str(payload.get("url", "")),
            abstract=str(payload.get("abstract", "")),
            source_id=str(payload.get("source_id", "")),
            source_tier=str(payload.get("source_tier", "")),
            source_type=str(payload.get("source_type", "")),
            match_score=int(payload.get("topic_match_score", payload.get("match_score")) or 0),
            match_reasons=list(payload.get("match_reasons") or []),
            push_bucket=str(payload.get("push_bucket", "")),
            strong_signal=bool(payload.get("strong_signal")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["topic_match_score"] = payload["match_score"]
        payload["score_interpretation"] = "mechanical topic-match signal; not paper quality or inclusion decision"
        return payload


def normalize_text(text: str) -> str:
    normalized = re.sub(r"[\u2010-\u2015\u2212]", "-", text or "")
    return re.sub(r"\s+", " ", normalized).strip().lower()


def normalize_doi(value: str) -> str:
    doi = normalize_text(value)
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    doi = re.sub(r"^(10\.\d{4,9})/+", r"\1/", doi)
    return doi.rstrip(".")


def _is_correction_notice(record: dict[str, Any]) -> bool:
    title = normalize_text(str(record.get("title") or ""))
    title = title.strip('"')
    return bool(re.search(r":\s*correction\.?$", title))


def candidate_key(record: dict[str, Any]) -> str:
    doi = normalize_doi(str(record.get("doi") or ""))
    if doi:
        return f"doi::{doi}"
    openalex_id = normalize_text(str(record.get("openalex_id") or record.get("id") or ""))
    if openalex_id:
        return f"openalex::{openalex_id}"
    return f"title::{normalize_text(str(record.get('title') or 'untitled'))}"


def candidate_id_for(record: dict[str, Any]) -> str:
    digest = hashlib.sha1(candidate_key(record).encode("utf-8")).hexdigest()[:12]
    return f"fp_{digest}"


def _combined_text(record: dict[str, Any]) -> str:
    return normalize_text(f"{record.get('title', '')} {record.get('abstract', '')}")


def _contains_phrase(text: str, phrase: str) -> bool:
    return normalize_text(phrase) in text


def _violates_exclusion(record: dict[str, Any], profile: InterestProfile) -> bool:
    text = _combined_text(record)
    return any(_contains_phrase(text, keyword) for keyword in profile.exclude_keywords)


def _violates_directionality(record: dict[str, Any], profile: InterestProfile) -> bool:
    text = _combined_text(record)
    target = normalize_text(profile.target_construct)
    if not target:
        return False

    if profile.directionality == "factors_of":
        wrong_way_patterns = [
            f"effect of {target} on",
            f"effects of {target} on",
            f"impact of {target} on",
            f"impacts of {target} on",
            f"{target} affect",
            f"{target} affects",
            f"{target} influence",
            f"{target} influences",
        ]
        return any(pattern in text for pattern in wrong_way_patterns)

    if profile.directionality == "effects_of":
        wrong_way_patterns = [
            f"determinants of {target}",
            f"drivers of {target}",
            f"factors of {target}",
            f"antecedents of {target}",
        ]
        return any(pattern in text for pattern in wrong_way_patterns)

    return False


def score_record(record: dict[str, Any], profile: InterestProfile) -> tuple[int, list[str]]:
    text = _combined_text(record)
    score = 0
    reasons: list[str] = []

    for phrase in profile.exact_phrases:
        if _contains_phrase(text, phrase):
            score += 3
            reasons.append(f"exact phrase: {phrase}")
    for phrase in profile.near_phrases:
        if _contains_phrase(text, phrase):
            score += 2
            reasons.append(f"near phrase: {phrase}")
    for term in profile.related_terms:
        if _contains_phrase(text, term):
            score += 1
            reasons.append(f"related term: {term}")

    return score, reasons


def _required_concept_reasons(record: dict[str, Any], profile: InterestProfile) -> list[str] | None:
    groups = profile.required_concept_groups
    if profile.directionality == "descriptive" and len(groups) < 2:
        raise ValueError("descriptive profiles require at least two non-empty required_concept_groups.")
    if not groups:
        return []

    text = _combined_text(record)
    # OpenAlex search covers title, abstract, and indexed full text, while the
    # persisted source record only carries title and abstract.  Require at
    # least one concept group to be visible in that persisted metadata, then
    # allow the approved retrieval query to substantiate remaining groups.
    # This preserves recall without treating retrieval alone as paper-level
    # topic evidence.
    query_text = normalize_text(str(record.get("source_query") or ""))
    reasons: list[str] = []
    missing_groups: list[tuple[str, list[str]]] = []
    for group_name, terms in groups.items():
        matched = next((term for term in terms if _contains_phrase(text, term)), None)
        if matched is not None:
            reasons.append(f"required concept: {group_name} = {matched}")
            continue
        missing_groups.append((group_name, terms))

    if not reasons:
        return None

    for group_name, terms in missing_groups:
        query_match = next((term for term in terms if _contains_phrase(query_text, term)), None)
        if query_match is None:
            return None
        reasons.append(f"retrieval query concept: {group_name} = {query_match}")
    return reasons


def choose_push_bucket(source_tier: str, score: int, strong_signal: bool) -> str:
    if source_tier == "A" and score > 0:
        return "main_push"
    if source_tier == "C" and strong_signal and score >= 5:
        return "main_push"
    return "early_signal"


def build_frontier_candidates(
    records: list[dict[str, Any]],
    profile: InterestProfile,
    source_id: str,
    source_tier: str,
    source_type: str = "metadata",
) -> list[FrontierCandidate]:
    if profile.directionality == "descriptive" and len(profile.required_concept_groups) < 2:
        raise ValueError("descriptive profiles require at least two non-empty required_concept_groups.")
    candidates: list[FrontierCandidate] = []
    for record in records:
        if _is_correction_notice(record) or _violates_exclusion(record, profile) or _violates_directionality(record, profile):
            continue
        concept_reasons = _required_concept_reasons(record, profile)
        if concept_reasons is None:
            continue
        score, reasons = score_record(record, profile)
        if score <= 0:
            continue
        strong_signal = bool(record.get("strong_signal"))
        candidates.append(
            FrontierCandidate(
                candidate_id=candidate_id_for(record),
                title=str(record.get("title") or "Untitled"),
                year=record.get("year") or record.get("publication_year"),
                venue=str(record.get("venue") or record.get("journal") or "Unknown Venue"),
                authors=list(record.get("authors") or []),
                doi=normalize_doi(str(record.get("doi") or "")),
                openalex_id=str(record.get("openalex_id") or record.get("id") or ""),
                url=str(record.get("url") or record.get("landing_page_url") or ""),
                abstract=str(record.get("abstract") or ""),
                source_id=source_id,
                source_tier=source_tier,
                source_type=source_type,
                match_score=score,
                match_reasons=[*concept_reasons, *reasons],
                push_bucket=choose_push_bucket(source_tier, score, strong_signal),
                strong_signal=strong_signal,
            )
        )
    return candidates


def deduplicate_candidates(candidates: list[FrontierCandidate]) -> list[FrontierCandidate]:
    best_by_key: dict[str, FrontierCandidate] = {}
    for candidate in candidates:
        key = normalize_doi(candidate.doi) if candidate.doi else candidate.title.lower()
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = candidate
            continue
        current_rank = (TIER_PRIORITY.get(current.source_tier, 0), current.match_score)
        new_rank = (TIER_PRIORITY.get(candidate.source_tier, 0), candidate.match_score)
        if new_rank > current_rank:
            best_by_key[key] = candidate
    return sorted(best_by_key.values(), key=lambda item: (-TIER_PRIORITY.get(item.source_tier, 0), -item.match_score, item.title))


def write_candidates_jsonl(path: Path, candidates: list[FrontierCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate.to_dict(), ensure_ascii=False) + "\n")


def load_candidates_jsonl(path: Path) -> list[FrontierCandidate]:
    if not path.exists():
        return []
    candidates: list[FrontierCandidate] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            candidates.append(FrontierCandidate.from_dict(json.loads(line)))
    return candidates
