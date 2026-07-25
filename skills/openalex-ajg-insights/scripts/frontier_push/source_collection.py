from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .profiles import InterestProfile, descriptive_profile_unassigned_query_terms


SUPPORTED_TIER_A_SOURCE_IDS = ("abs3", "abs3_star", "abs4", "abs_ajg_4star", "ft50", "utd24")
LEGACY_SOURCE_ALIASES = {"abs4_star": "abs_ajg_4star", "utd24_ft50": "ft50"}

FT50_JOURNALS = [
    "Academy of Management Annals",
    "Academy of Management Journal",
    "Academy of Management Review",
    "Accounting Review",
    "Accounting, Organizations and Society",
    "Administrative Science Quarterly",
    "American Economic Review",
    "American Sociological Review",
    "Contemporary Accounting Research",
    "Econometrica",
    "Entrepreneurship Theory and Practice",
    "Harvard Business Review",
    "Human Resource Management",
    "Information Systems Research",
    "Journal of Accounting and Economics",
    "Journal of Accounting Research",
    "Journal of Applied Psychology",
    "Journal of Business Venturing",
    "Journal of Consumer Psychology",
    "Journal of Consumer Research",
    "Journal of Finance",
    "Journal of Financial and Quantitative Analysis",
    "Journal of Financial Economics",
    "Journal of International Business Studies",
    "Journal of Management",
    "Journal of Management Information Systems",
    "Journal of Management Studies",
    "Journal of Marketing",
    "Journal of Marketing Research",
    "Journal of Operations Management",
    "Journal of Political Economy",
    "Journal of the Academy of Marketing Science",
    "Management Science",
    "Manufacturing & Service Operations Management",
    "Marketing Science",
    "MIS Quarterly",
    "MIT Sloan Management Review",
    "Operations Research",
    "Organization Science",
    "Organizational Behavior and Human Decision Processes",
    "Production and Operations Management",
    "Psychological Science",
    "Quarterly Journal of Economics",
    "Research Policy",
    "Review of Accounting Studies",
    "Review of Economic Studies",
    "Review of Finance",
    "Review of Financial Studies",
    "Strategic Entrepreneurship Journal",
    "Strategic Management Journal",
]

UTD24_JOURNALS = [
    "Accounting Review",
    "Contemporary Accounting Research",
    "Journal of Accounting and Economics",
    "Journal of Accounting Research",
    "Journal of Finance",
    "Journal of Financial Economics",
    "Review of Finance",
    "Review of Financial Studies",
    "Information Systems Research",
    "MIS Quarterly",
    "Academy of Management Journal",
    "Academy of Management Review",
    "Administrative Science Quarterly",
    "Organization Science",
    "Strategic Management Journal",
    "Journal of Consumer Research",
    "Journal of Marketing",
    "Journal of Marketing Research",
    "Marketing Science",
    "Journal of Operations Management",
    "Management Science",
    "Manufacturing & Service Operations Management",
    "Operations Research",
    "Production and Operations Management",
]

JOURNAL_TITLE_ALIASES = {
    "human resource management": ["Human Resource Management (USA)"],
    "mis quarterly": ["MIS Quarterly: Management Information Systems"],
}


@dataclass(frozen=True)
class ResolvedJournal:
    title: str
    issn: str
    rank: str
    field: str


@dataclass(frozen=True)
class ResolvedSource:
    source_id: str
    source_tier: str
    source_type: str
    journals: list[ResolvedJournal]
    unresolved_journals: list[str]


def canonical_source_id(source_id: str) -> str:
    cleaned = str(source_id or "").strip()
    return LEGACY_SOURCE_ALIASES.get(cleaned, cleaned)


def normalize_journal_title(title: str) -> str:
    text = str(title or "").lower().replace("&", "and")
    text = re.sub(r"^the\s+", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _split_issns(raw_issn: str) -> list[str]:
    parts = re.split(r"[,;]", str(raw_issn or ""))
    return [part.strip() for part in parts if part.strip()]


def load_ajg_journals(csv_path: Path) -> list[ResolvedJournal]:
    journals: list[ResolvedJournal] = []
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            for issn in _split_issns(row.get("ISSN", "")):
                journals.append(
                    ResolvedJournal(
                        title=str(row.get("Journal Title") or "").strip(),
                        issn=issn,
                        rank=str(row.get("Rank") or "").strip(),
                        field=str(row.get("Field") or "").strip(),
                    )
                )
    return journals


def _dedupe_journals(journals: Iterable[ResolvedJournal]) -> list[ResolvedJournal]:
    seen: set[str] = set()
    deduped: list[ResolvedJournal] = []
    for journal in journals:
        if journal.issn in seen:
            continue
        seen.add(journal.issn)
        deduped.append(journal)
    return deduped


def _resolve_named_pool(source_id: str, ajg_journals: list[ResolvedJournal], names: list[str]) -> ResolvedSource:
    by_title: dict[str, list[ResolvedJournal]] = {}
    for journal in ajg_journals:
        by_title.setdefault(normalize_journal_title(journal.title), []).append(journal)

    resolved: list[ResolvedJournal] = []
    unresolved: list[str] = []
    for name in names:
        lookup_keys = [normalize_journal_title(name)]
        lookup_keys.extend(normalize_journal_title(alias) for alias in JOURNAL_TITLE_ALIASES.get(lookup_keys[0], []))
        matches: list[ResolvedJournal] = []
        for key in lookup_keys:
            matches.extend(by_title.get(key, []))
        if not matches:
            unresolved.append(name)
            continue
        resolved.extend(matches)

    return ResolvedSource(
        source_id=source_id,
        source_tier="A",
        source_type="openalex_ajg",
        journals=_dedupe_journals(resolved),
        unresolved_journals=unresolved,
    )


def resolve_tier_a_journals(csv_path: Path, source_ids: Iterable[str]) -> dict[str, ResolvedSource]:
    ajg_journals = load_ajg_journals(Path(csv_path))
    resolved: dict[str, ResolvedSource] = {}
    for raw_source_id in source_ids:
        source_id = canonical_source_id(raw_source_id)
        if source_id not in SUPPORTED_TIER_A_SOURCE_IDS:
            raise ValueError(f"Unsupported Tier A frontier source id: {raw_source_id}")
        if source_id == "abs3":
            journals = _dedupe_journals(journal for journal in ajg_journals if journal.rank in {"3", "3*", "4", "4*"})
            resolved[source_id] = ResolvedSource(source_id, "A", "openalex_ajg", journals, [])
        elif source_id == "abs3_star":
            journals = _dedupe_journals(journal for journal in ajg_journals if journal.rank in {"3*", "4", "4*"})
            resolved[source_id] = ResolvedSource(source_id, "A", "openalex_ajg", journals, [])
        elif source_id == "abs4":
            journals = _dedupe_journals(journal for journal in ajg_journals if journal.rank in {"4", "4*"})
            resolved[source_id] = ResolvedSource(source_id, "A", "openalex_ajg", journals, [])
        elif source_id == "abs_ajg_4star":
            journals = _dedupe_journals(journal for journal in ajg_journals if journal.rank == "4*")
            resolved[source_id] = ResolvedSource(source_id, "A", "openalex_ajg", journals, [])
        elif source_id == "ft50":
            resolved[source_id] = _resolve_named_pool(source_id, ajg_journals, FT50_JOURNALS)
        elif source_id == "utd24":
            resolved[source_id] = _resolve_named_pool(source_id, ajg_journals, UTD24_JOURNALS)
    return resolved


def chunked(items: list[str], size: int) -> Iterable[list[str]]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for index in range(0, len(items), size):
        yield items[index : index + size]


def work_source_issns(work: dict[str, Any]) -> set[str]:
    source = ((work.get("primary_location") or {}).get("source") or {})
    values = source.get("issn") or []
    if isinstance(values, str):
        values = [values]
    issns = {str(value).strip() for value in values if str(value).strip()}
    issn_l = str(source.get("issn_l") or "").strip()
    if issn_l:
        issns.add(issn_l)
    return issns


def partition_works_by_source(
    works: Iterable[dict[str, Any]],
    resolved_sources: dict[str, ResolvedSource],
) -> dict[str, list[dict[str, Any]]]:
    allowed_by_source = {
        source_id: {journal.issn for journal in resolved.journals}
        for source_id, resolved in resolved_sources.items()
    }
    partitioned = {source_id: [] for source_id in resolved_sources}
    for work in works:
        issns = work_source_issns(work)
        for source_id, allowed in allowed_by_source.items():
            if issns & allowed:
                partitioned[source_id].append(work)
    return partitioned


def record_year(record: dict[str, Any]) -> int | None:
    raw_year = record.get("year") or record.get("publication_year")
    try:
        return int(raw_year)
    except (TypeError, ValueError):
        return None


def filter_records_by_year(
    records: list[dict[str, Any]],
    year_start: int | None = None,
    year_end: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stats = {
        "input_records": len(records),
        "kept_records": 0,
        "excluded_out_of_range": 0,
        "excluded_missing_year": 0,
    }
    if year_start is None and year_end is None:
        stats["kept_records"] = len(records)
        return list(records), stats

    kept: list[dict[str, Any]] = []
    for record in records:
        year = record_year(record)
        if year is None:
            stats["excluded_missing_year"] += 1
            continue
        if year_start is not None and year < year_start:
            stats["excluded_out_of_range"] += 1
            continue
        if year_end is not None and year > year_end:
            stats["excluded_out_of_range"] += 1
            continue
        kept.append(record)
    stats["kept_records"] = len(kept)
    return kept, stats


def _record_key(record: dict[str, Any]) -> str:
    doi = str(record.get("doi") or "").strip().lower()
    if doi:
        return f"doi::{doi}"
    openalex_id = str(record.get("openalex_id") or record.get("id") or "").strip().lower()
    if openalex_id:
        return f"openalex::{openalex_id}"
    return f"title::{str(record.get('title') or '').strip().lower()}"


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for record in records:
        key = _record_key(record)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


REQUIRED_SOURCE_PAYLOAD_FIELDS = (
    "source_id",
    "source_tier",
    "source_type",
    "profile_id",
    "year_start",
    "year_end",
    "records",
)


def validate_source_payload(payload: Any, path: Path | None = None) -> list[str]:
    """Return a list of human-readable warnings for a source-record payload.

    The validator never raises. It is designed to flag legacy or
    hand-edited files that lack the metadata fields required by ADR-0004.
    """
    warnings: list[str] = []
    label = str(path) if path is not None else "<payload>"
    if not isinstance(payload, dict):
        return [f"{label}: top-level value must be a JSON object"]
    for field in REQUIRED_SOURCE_PAYLOAD_FIELDS:
        if field not in payload:
            warnings.append(f"{label}: missing required field '{field}'")
    if isinstance(payload.get("records"), list) and len(payload["records"]) > 0:
        sample = payload["records"][0]
        if not isinstance(sample, dict):
            warnings.append(f"{label}: first record must be a JSON object")
    return warnings


def build_profile_queries(profile: InterestProfile, max_queries: int | None = None) -> list[str]:
    def quoted_or_group(terms: Iterable[str]) -> str:
        cleaned: list[str] = []
        seen: set[str] = set()
        for term in terms:
            value = str(term or "").strip()
            key = value.lower()
            if not value or key in seen:
                continue
            seen.add(key)
            cleaned.append(f'"{value}"')
        if not cleaned:
            return ""
        return cleaned[0] if len(cleaned) == 1 else f"({' OR '.join(cleaned)})"

    if profile.directionality == "descriptive":
        unassigned_terms = descriptive_profile_unassigned_query_terms(profile)
        if unassigned_terms:
            raise ValueError(
                "Descriptive exact_phrases/near_phrases query terms are not assigned "
                "to any required concept group: "
                + ", ".join(unassigned_terms)
            )
        exact_terms = {str(term).strip().lower() for term in profile.exact_phrases if str(term).strip()}
        searchable_terms = {
            str(term).strip().lower()
            for term in [*profile.exact_phrases, *profile.near_phrases]
            if str(term).strip()
        }

        def compile_required_groups(allowed_terms: set[str], label: str) -> str:
            groups: list[str] = []
            for group_name, terms in profile.required_concept_groups.items():
                selected = [term for term in terms if str(term).strip().lower() in allowed_terms]
                group = quoted_or_group(selected)
                if not group:
                    raise ValueError(
                        f"Descriptive query level {label!r} cannot cover required concept group "
                        f"{group_name!r}. Add at least one exact phrase for every required group."
                    )
                groups.append(group)
            return " AND ".join(groups)

        exact_query = compile_required_groups(exact_terms, "exact")
        expanded_query = compile_required_groups(searchable_terms, "exact+near")
        queries = [exact_query]
        if expanded_query != exact_query:
            queries.append(expanded_query)
    else:
        # Preserve the existing single-query behavior for non-descriptive
        # profiles. Related terms, exclusions, directionality, and JEL remain
        # downstream concerns rather than standalone OpenAlex queries.
        query = quoted_or_group([*profile.exact_phrases, *profile.near_phrases])
        if not query:
            raise ValueError("Profile must define at least one exact_phrases or near_phrases search anchor.")
        queries = [query]

    if max_queries is None:
        return queries
    if not isinstance(max_queries, int) or isinstance(max_queries, bool):
        raise ValueError("max_queries must be an integer.")
    if max_queries < 1 or max_queries > len(queries):
        raise ValueError(f"max_queries must be between 1 and {len(queries)} for profile {profile.id!r}.")
    return queries[:max_queries]


def build_source_payload(
    source_id: str,
    source_tier: str,
    source_type: str,
    profile_id: str,
    year_start: int | None,
    year_end: int | None,
    records: list[dict[str, Any]],
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched_records = []
    for record in records:
        enriched = dict(record)
        enriched.setdefault("source_id", source_id)
        enriched.setdefault("source_tier", source_tier)
        enriched.setdefault("source_type", source_type)
        enriched_records.append(enriched)
    return {
        "source_id": source_id,
        "source_tier": source_tier,
        "source_type": source_type,
        "profile_id": profile_id,
        "year_start": year_start,
        "year_end": year_end,
        "count": len(enriched_records),
        "records": enriched_records,
        "diagnostics": diagnostics or {},
    }


def write_source_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
