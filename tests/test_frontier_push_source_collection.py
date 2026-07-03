from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "openalex-ajg-insights" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from frontier_push.source_collection import (
    SUPPORTED_TIER_A_SOURCE_IDS,
    build_profile_queries,
    build_source_payload,
    chunked,
    deduplicate_records,
    filter_records_by_year,
    resolve_tier_a_journals,
)
from frontier_push.profiles import InterestProfile
from frontier_push.sources import default_source_catalog


def write_ajg_fixture(path: Path) -> None:
    rows = [
        {"Journal Title": "Four Star Journal", "ISSN": "0001-0001", "Rank": "4*", "Field": "GEN"},
        {"Journal Title": "Rank Three Journal", "ISSN": "0003-0003", "Rank": "3", "Field": "GEN"},
        {"Journal Title": "Academy of Management Journal", "ISSN": "0001-4273", "Rank": "4*", "Field": "MAN"},
        {"Journal Title": "Management Science", "ISSN": "0025-1909", "Rank": "4", "Field": "OPS"},
        {"Journal Title": "MIS Quarterly: Management Information Systems", "ISSN": "0276-7783", "Rank": "4*", "Field": "INFO MAN"},
        {"Journal Title": "Human Resource Management (USA)", "ISSN": "0090-4848", "Rank": "4", "Field": "HRM&EMP"},
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Journal Title", "ISSN", "Rank", "Field"])
        writer.writeheader()
        writer.writerows(rows)


class FrontierSourceCollectionTests(unittest.TestCase):
    def test_default_catalog_uses_only_requested_tier_a_sources(self) -> None:
        catalog = default_source_catalog()
        tier_a_ids = [source["id"] for source in catalog["sources"] if source["tier"] == "A"]

        self.assertEqual(["abs_ajg_4star", "ft50", "utd24"], tier_a_ids)
        self.assertNotIn("abs_ajg_3plus", tier_a_ids)
        self.assertNotIn("utd24_ft50", tier_a_ids)
        self.assertEqual(set(tier_a_ids), set(SUPPORTED_TIER_A_SOURCE_IDS))

    def test_resolves_ajg_4star_ft50_and_utd24_against_ajg_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "ajg.csv"
            write_ajg_fixture(csv_path)

            resolved = resolve_tier_a_journals(csv_path, ["abs_ajg_4star", "ft50", "utd24"])

        self.assertEqual(["0001-0001", "0001-4273", "0276-7783"], [journal.issn for journal in resolved["abs_ajg_4star"].journals])
        self.assertEqual(["0001-4273", "0090-4848", "0025-1909", "0276-7783"], [journal.issn for journal in resolved["ft50"].journals])
        self.assertEqual(["0276-7783", "0001-4273", "0025-1909"], [journal.issn for journal in resolved["utd24"].journals])
        self.assertNotIn("0003-0003", [journal.issn for journal in resolved["abs_ajg_4star"].journals])

    def test_chunks_cover_more_than_fifty_issns(self) -> None:
        chunks = list(chunked([f"issn-{index}" for index in range(121)], 50))

        self.assertEqual([50, 50, 21], [len(chunk) for chunk in chunks])
        self.assertEqual("issn-120", chunks[-1][-1])

    def test_filter_records_by_year_is_strict_and_reports_exclusions(self) -> None:
        records = [
            {"title": "Old", "year": 2024},
            {"title": "Start", "year": 2025},
            {"title": "End", "publication_year": 2026},
            {"title": "Future", "year": 2027},
            {"title": "Missing"},
        ]

        kept, stats = filter_records_by_year(records, year_start=2025, year_end=2026)

        self.assertEqual(["Start", "End"], [record["title"] for record in kept])
        self.assertEqual(5, stats["input_records"])
        self.assertEqual(2, stats["kept_records"])
        self.assertEqual(2, stats["excluded_out_of_range"])
        self.assertEqual(1, stats["excluded_missing_year"])

    def test_payload_preserves_source_provenance_and_deduplicates(self) -> None:
        records = [
            {"title": "Generative AI at Work", "year": 2025, "doi": "10.1/a"},
            {"title": "Generative AI at Work", "year": 2025, "doi": "10.1/a"},
            {"title": "Another Paper", "year": 2026, "openalex_id": "W1"},
        ]

        deduped = deduplicate_records(records)
        payload = build_source_payload(
            source_id="ft50",
            source_tier="A",
            source_type="openalex_ajg",
            profile_id="generative_ai_economic_consequences",
            year_start=2025,
            year_end=2026,
            records=deduped,
            diagnostics={"query_count": 2},
        )

        self.assertEqual(2, len(deduped))
        self.assertEqual("ft50", payload["source_id"])
        self.assertEqual("A", payload["source_tier"])
        self.assertEqual("openalex_ajg", payload["source_type"])
        self.assertEqual(2025, payload["year_start"])
        self.assertEqual(2026, payload["year_end"])
        self.assertEqual(2, payload["count"])

    def test_profile_queries_use_reviewable_terms_without_exclusions(self) -> None:
        profile = InterestProfile(
            id="generative_ai_economic_consequences",
            name="Generative AI economic consequences",
            directionality="effects_of",
            target_construct="generative AI",
            exact_phrases=["generative AI", "ChatGPT"],
            near_phrases=["AI adoption and productivity"],
            related_terms=["productivity"],
            exclude_keywords=["determinants of generative AI"],
            jel_codes=["O33"],
            natural_language="Track economic effects of generative AI.",
        )

        queries = build_profile_queries(profile)

        self.assertEqual(["generative AI", "ChatGPT", "AI adoption and productivity"], queries)
        self.assertNotIn("determinants of generative AI", queries)


if __name__ == "__main__":
    unittest.main()
