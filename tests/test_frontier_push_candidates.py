from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "openalex-ajg-insights" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from frontier_push.candidates import (
    build_frontier_candidates,
    deduplicate_candidates,
    load_candidates_jsonl,
    write_candidates_jsonl,
)
from frontier_push.profiles import InterestProfile
from frontier_push.reports import render_frontier_report
from frontier_push.sources import default_source_catalog


def firm_asset_pricing_profile() -> InterestProfile:
    return InterestProfile(
        id="firm_asset_pricing_determinants",
        name="企业资产定价影响因素",
        directionality="factors_of",
        target_construct="expected stock returns",
        exact_phrases=["cross-section of stock returns", "expected stock returns"],
        near_phrases=["asset pricing anomalies", "return predictability"],
        related_terms=["profitability", "investment", "momentum"],
        exclude_keywords=["option pricing", "cryptocurrency pricing"],
        jel_codes=["G12", "G14"],
        natural_language="Track firm-level determinants of expected stock returns.",
    )


class FrontierCandidateTests(unittest.TestCase):
    def test_build_candidates_filters_exclusions_and_wrong_direction(self) -> None:
        profile = firm_asset_pricing_profile()
        records = [
            {
                "title": "Firm Characteristics and Expected Stock Returns",
                "year": 2026,
                "journal": "Journal of Finance",
                "abstract": "Profitability, investment, and momentum explain expected stock returns.",
                "doi": "10.1111/main",
                "authors": ["A Author"],
            },
            {
                "title": "Option Pricing and Expected Stock Returns",
                "year": 2026,
                "journal": "Journal of Finance",
                "abstract": "This paper studies option pricing.",
                "doi": "10.1111/excluded",
                "authors": ["B Author"],
            },
            {
                "title": "The Effect of Expected Stock Returns on Corporate Investment",
                "year": 2026,
                "journal": "Journal of Corporate Finance",
                "abstract": "Expected stock returns affect corporate investment.",
                "doi": "10.1111/wrong-way",
                "authors": ["C Author"],
            },
        ]

        candidates = build_frontier_candidates(records, profile, source_id="abs4_star", source_tier="A")

        self.assertEqual(["10.1111/main"], [candidate.doi for candidate in candidates])
        self.assertEqual("main_push", candidates[0].push_bucket)
        self.assertIn("exact phrase: expected stock returns", candidates[0].match_reasons)

    def test_tier_c_defaults_to_early_signal_unless_strong_signal(self) -> None:
        profile = firm_asset_pricing_profile()
        records = [
            {
                "title": "Profitability and Return Predictability",
                "year": 2026,
                "journal": "NBER Working Paper",
                "abstract": "Profitability and investment predict returns.",
                "doi": "10.3386/early",
                "authors": ["D Author"],
            },
            {
                "title": "Expected Stock Returns and the Cross-Section of Stock Returns",
                "year": 2026,
                "journal": "NBER Working Paper",
                "abstract": "Profitability, investment, and momentum explain expected stock returns.",
                "doi": "10.3386/strong",
                "authors": ["E Author"],
                "strong_signal": True,
            },
        ]

        candidates = build_frontier_candidates(records, profile, source_id="nber_wp", source_tier="C")
        buckets = {candidate.doi: candidate.push_bucket for candidate in candidates}

        self.assertEqual("early_signal", buckets["10.3386/early"])
        self.assertEqual("main_push", buckets["10.3386/strong"])

    def test_deduplicate_candidates_prefers_tier_a_then_score(self) -> None:
        profile = firm_asset_pricing_profile()
        tier_c = build_frontier_candidates(
            [
                {
                    "title": "Expected Stock Returns and Firm Characteristics",
                    "year": 2026,
                    "journal": "SSRN",
                    "abstract": "Expected stock returns and profitability.",
                    "doi": "10.1234/same",
                    "authors": ["A Author"],
                    "strong_signal": True,
                }
            ],
            profile,
            source_id="ssrn",
            source_tier="C",
        )
        tier_a = build_frontier_candidates(
            [
                {
                    "title": "Expected Stock Returns and Firm Characteristics",
                    "year": 2026,
                    "journal": "Review of Financial Studies",
                    "abstract": "Expected stock returns and profitability.",
                    "doi": "10.1234/same",
                    "authors": ["A Author"],
                }
            ],
            profile,
            source_id="abs4_star",
            source_tier="A",
        )

        deduped = deduplicate_candidates(tier_c + tier_a)

        self.assertEqual(1, len(deduped))
        self.assertEqual("A", deduped[0].source_tier)
        self.assertEqual("abs4_star", deduped[0].source_id)

    def test_candidates_jsonl_round_trip(self) -> None:
        profile = firm_asset_pricing_profile()
        candidates = build_frontier_candidates(
            [
                {
                    "title": "Firm Characteristics and Expected Stock Returns",
                    "year": 2026,
                    "journal": "Journal of Finance",
                    "abstract": "Profitability explains expected stock returns.",
                    "doi": "10.1111/main",
                    "authors": ["A Author"],
                }
            ],
            profile,
            source_id="abs4_star",
            source_tier="A",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates.jsonl"
            write_candidates_jsonl(path, candidates)
            loaded = load_candidates_jsonl(path)

        self.assertEqual(candidates[0].candidate_id, loaded[0].candidate_id)
        self.assertEqual("main_push", loaded[0].push_bucket)


class FrontierReportTests(unittest.TestCase):
    def test_report_has_main_push_and_early_signal_sections(self) -> None:
        profile = firm_asset_pricing_profile()
        candidates = build_frontier_candidates(
            [
                {
                    "title": "Firm Characteristics and Expected Stock Returns",
                    "year": 2026,
                    "journal": "Journal of Finance",
                    "abstract": "Profitability explains expected stock returns.",
                    "doi": "10.1111/main",
                    "authors": ["A Author"],
                },
                {
                    "title": "Profitability and Return Predictability",
                    "year": 2026,
                    "journal": "NBER Working Paper",
                    "abstract": "Profitability predicts returns.",
                    "doi": "10.3386/early",
                    "authors": ["D Author"],
                },
            ],
            profile,
            source_id="mixed_fixture",
            source_tier="C",
        )
        candidates[0].source_tier = "A"
        candidates[0].push_bucket = "main_push"

        report = render_frontier_report(profile, candidates, run_id="2026-07-03T000000")

        self.assertIn("# Frontier Push Report: 企业资产定价影响因素", report)
        self.assertIn("## Main Push", report)
        self.assertIn("## Early Signals", report)
        self.assertIn("Firm Characteristics and Expected Stock Returns", report)
        self.assertIn("Profitability and Return Predictability", report)


class FrontierSourceCatalogTests(unittest.TestCase):
    def test_default_source_catalog_marks_tier_b_as_config_only(self) -> None:
        catalog = default_source_catalog()
        tiers = {source["tier"] for source in catalog["sources"]}
        tier_b = [source for source in catalog["sources"] if source["tier"] == "B"]

        self.assertEqual({"A", "B", "C"}, tiers)
        self.assertTrue(tier_b)
        self.assertTrue(all(source["status"] == "config_only" for source in tier_b))


if __name__ == "__main__":
    unittest.main()
