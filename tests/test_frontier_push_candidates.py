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
    normalize_doi,
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


def relationship_profile() -> InterestProfile:
    return InterestProfile.from_dict(
        {
            "id": "work_repetition_satisfaction",
            "name": "重复劳动与员工满意度",
            "directionality": "descriptive",
            "target_construct": "employee satisfaction",
            "required_concept_groups": {
                "work_repetition": ["work monotony", "repetitive work"],
                "employee_outcomes": ["job satisfaction", "employee well-being"],
            },
            "exact_phrases": ["work monotony", "job satisfaction"],
            "near_phrases": ["repetitive work", "employee well-being"],
            "related_terms": ["autonomy", "work design"],
            "exclude_keywords": [],
            "jel_codes": ["J28"],
            "natural_language": "Track the relationship between repetitive work and employee satisfaction.",
        }
    )


class FrontierCandidateTests(unittest.TestCase):
    def test_descriptive_candidates_require_every_concept_group(self) -> None:
        records = [
            {
                "title": "Work Monotony in Modern Organizations",
                "abstract": "This study examines repetitive work and autonomy.",
                "doi": "10.1/only-work",
            },
            {
                "title": "Job Satisfaction and Employee Well-Being",
                "abstract": "This study examines work design and autonomy.",
                "doi": "10.1/only-outcome",
            },
            {
                "title": "Repetitive Work and Employee Well-Being",
                "abstract": "We examine how repetitive work relates to employee well-being.",
                "doi": "10.1/both",
            },
            {
                "title": "Autonomy and Work Design",
                "abstract": "Autonomy shapes work design.",
                "doi": "10.1/related-only",
            },
        ]

        candidates = build_frontier_candidates(
            records,
            relationship_profile(),
            source_id="ft50",
            source_tier="A",
        )

        self.assertEqual(["10.1/both"], [candidate.doi for candidate in candidates])
        self.assertIn("required concept: work_repetition = repetitive work", candidates[0].match_reasons)
        self.assertIn("required concept: employee_outcomes = employee well-being", candidates[0].match_reasons)

    def test_descriptive_candidate_uses_query_evidence_when_abstract_is_missing(self) -> None:
        profile = InterestProfile.from_dict(
            {
                "id": "a_share_asset_pricing",
                "name": "A-share asset pricing",
                "directionality": "descriptive",
                "target_construct": "A-share market and asset pricing",
                "required_concept_groups": {
                    "a_share_market": ["A-share", "Chinese stock market"],
                    "asset_pricing": ["asset pricing", "asset price"],
                },
                "exact_phrases": ["A-share", "Chinese stock market", "asset pricing", "asset price"],
                "near_phrases": [],
                "related_terms": ["bubbles"],
                "exclude_keywords": [],
                "jel_codes": ["G12"],
                "natural_language": "Track A-share asset pricing relationships.",
            }
        )
        records = [
            {
                "title": "Digital finance empowerment, social media sentiment, and asset price bubbles",
                "abstract": "",
                "source_query": '("A-share" OR "Chinese stock market") AND '
                '("asset pricing" OR "asset price")',
                "doi": "10.1016/j.irfa.2025.104806",
            }
        ]

        candidates = build_frontier_candidates(records, profile, source_id="abs3", source_tier="A")

        self.assertEqual(["10.1016/j.irfa.2025.104806"], [candidate.doi for candidate in candidates])
        self.assertTrue(any("abstract unavailable" in reason for reason in candidates[0].match_reasons))

    def test_descriptive_profile_without_groups_fails_before_scoring(self) -> None:
        profile = InterestProfile(
            id="legacy_relationship",
            name="Legacy relationship",
            directionality="descriptive",
            target_construct="employee satisfaction",
            exact_phrases=["work monotony", "job satisfaction"],
            near_phrases=[],
            related_terms=[],
            exclude_keywords=[],
            jel_codes=[],
            natural_language="Track a relationship.",
        )

        with self.assertRaisesRegex(ValueError, "at least two"):
            build_frontier_candidates([], profile, source_id="ft50", source_tier="A")

    def test_normalize_doi_collapses_url_prefix_and_extra_slash(self) -> None:
        self.assertEqual(
            "10.1037/0021-9010.80.1.29",
            normalize_doi("https://doi.org/10.1037//0021-9010.80.1.29"),
        )
        self.assertEqual("10.1037/0021-9010.80.1.29", normalize_doi("doi:10.1037/0021-9010.80.1.29."))

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

    def test_deduplicate_candidates_uses_normalized_doi(self) -> None:
        profile = firm_asset_pricing_profile()
        first = build_frontier_candidates(
            [
                {
                    "title": "Expected Stock Returns and Firm Characteristics",
                    "year": 2026,
                    "journal": "Journal of Finance",
                    "abstract": "Expected stock returns and profitability.",
                    "doi": "https://doi.org/10.1037/0021-9010.80.1.29",
                    "authors": ["A Author"],
                }
            ],
            profile,
            source_id="ft50",
            source_tier="A",
        )
        duplicate = build_frontier_candidates(
            [
                {
                    "title": "Expected Stock Returns and Firm Characteristics",
                    "year": 2026,
                    "journal": "Journal of Finance",
                    "abstract": "Expected stock returns and profitability.",
                    "doi": "https://doi.org/10.1037//0021-9010.80.1.29",
                    "authors": ["A Author"],
                }
            ],
            profile,
            source_id="ft50",
            source_tier="A",
        )

        self.assertEqual(1, len(deduplicate_candidates(first + duplicate)))

    def test_build_candidates_skips_correction_notices(self) -> None:
        profile = firm_asset_pricing_profile()
        candidates = build_frontier_candidates(
            [
                {
                    "title": '"Expected Stock Returns and Firm Characteristics": Correction.',
                    "year": 2026,
                    "journal": "Journal of Finance",
                    "abstract": "Expected stock returns and profitability.",
                    "doi": "10.1037/correction",
                    "authors": ["A Author"],
                },
                {
                    "title": "Expected Stock Returns and Firm Characteristics",
                    "year": 2026,
                    "journal": "Journal of Finance",
                    "abstract": "Expected stock returns and profitability.",
                    "doi": "10.1037/main",
                    "authors": ["A Author"],
                },
            ],
            profile,
            source_id="ft50",
            source_tier="A",
        )

        self.assertEqual(["10.1037/main"], [candidate.doi for candidate in candidates])

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
