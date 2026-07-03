from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REVIEW_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "openalex-ajg-insights"
    / "scripts"
    / "review_workflow.py"
)

spec = importlib.util.spec_from_file_location("review_workflow_frontier_cli", REVIEW_WORKFLOW_PATH)
review_workflow = importlib.util.module_from_spec(spec)
sys.modules["review_workflow_frontier_cli"] = review_workflow
assert spec.loader is not None
spec.loader.exec_module(review_workflow)


class FrontierPushCliTests(unittest.TestCase):
    def test_parse_args_includes_frontier_push_commands(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "review_workflow.py",
                "--workspace",
                "workspace",
                "draft-interest-profile",
                "--intent",
                "检索企业资产定价影响因素",
            ],
        ):
            args = review_workflow.parse_args()

        self.assertEqual("draft-interest-profile", args.command)
        self.assertEqual("检索企业资产定价影响因素", args.intent)
        self.assertEqual("auto", args.llm_mode)

    def test_init_frontier_push_writes_sources_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            payload = review_workflow.init_frontier_push(workspace)

            sources_path = workspace / "09_frontier_push" / "sources.yml"

            self.assertTrue(sources_path.exists())
            self.assertTrue((workspace / "09_frontier_push" / "profiles").exists())
            self.assertEqual(str(sources_path), payload["sources_path"])

    def test_run_frontier_push_reads_records_json_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            profile_path = workspace / "09_frontier_push" / "profiles" / "firm_asset_pricing_determinants.yml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: firm_asset_pricing_determinants",
                        "name: 企业资产定价影响因素",
                        "directionality: factors_of",
                        "target_construct: expected stock returns",
                        "exact_phrases:",
                        "  - expected stock returns",
                        "near_phrases:",
                        "  - return predictability",
                        "related_terms:",
                        "  - profitability",
                        "exclude_keywords:",
                        "  - option pricing",
                        "jel_codes:",
                        "  - G12",
                        "natural_language: Track determinants of expected stock returns.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            records_path = workspace / "records.json"
            records_path.write_text(
                json.dumps(
                    {
                        "source_id": "abs4_star",
                        "records": [
                            {
                                "title": "Firm Characteristics and Expected Stock Returns",
                                "year": 2026,
                                "journal": "Journal of Finance",
                                "abstract": "Profitability explains expected stock returns.",
                                "doi": "10.1111/main",
                                "authors": ["A Author"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = review_workflow.run_frontier_push(workspace, "firm_asset_pricing_determinants", ["A", "C"], [str(records_path)], "2026-07-03T000000")

            self.assertEqual(1, payload["candidate_count"])
            self.assertTrue(Path(payload["report_path"]).exists())

    def test_run_frontier_push_filters_records_by_year_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            profile_path = workspace / "09_frontier_push" / "profiles" / "firm_asset_pricing_determinants.yml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: firm_asset_pricing_determinants",
                        "name: Firm asset pricing determinants",
                        "directionality: factors_of",
                        "target_construct: expected stock returns",
                        "exact_phrases:",
                        "  - expected stock returns",
                        "near_phrases:",
                        "  - return predictability",
                        "related_terms:",
                        "  - profitability",
                        "exclude_keywords:",
                        "  - option pricing",
                        "jel_codes:",
                        "  - G12",
                        "natural_language: Track determinants of expected stock returns.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            records_path = workspace / "records.json"
            records_path.write_text(
                json.dumps(
                    {
                        "source_id": "abs_ajg_4star",
                        "records": [
                            {"title": "Old Expected Stock Returns", "year": 2024, "journal": "Journal of Finance", "abstract": "Expected stock returns and profitability.", "doi": "10.1/old"},
                            {"title": "Current Expected Stock Returns", "year": 2025, "journal": "Journal of Finance", "abstract": "Expected stock returns and profitability.", "doi": "10.1/current"},
                            {"title": "Future Expected Stock Returns", "year": 2027, "journal": "Journal of Finance", "abstract": "Expected stock returns and profitability.", "doi": "10.1/future"},
                            {"title": "Missing Expected Stock Returns", "journal": "Journal of Finance", "abstract": "Expected stock returns and profitability.", "doi": "10.1/missing"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = review_workflow.run_frontier_push(
                workspace,
                "firm_asset_pricing_determinants",
                ["A"],
                [str(records_path)],
                "2026-07-03Tyear-filter",
                year_start=2025,
                year_end=2026,
            )

            candidates = Path(payload["candidates_path"]).read_text(encoding="utf-8")
            self.assertEqual(1, payload["candidate_count"])
            self.assertIn("Current Expected Stock Returns", candidates)
            self.assertNotIn("Old Expected Stock Returns", candidates)
            self.assertNotIn("Future Expected Stock Returns", candidates)
            self.assertEqual(1, payload["year_filter"]["kept_records"])
            self.assertEqual(2, payload["year_filter"]["excluded_out_of_range"])
            self.assertEqual(1, payload["year_filter"]["excluded_missing_year"])

    def test_parse_args_includes_collect_frontier_sources(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "review_workflow.py",
                "--workspace",
                "workspace",
                "collect-frontier-sources",
                "--profile",
                "generative_ai_economic_consequences",
                "--source-ids",
                "abs_ajg_4star,ft50,utd24",
                "--year-start",
                "2025",
                "--year-end",
                "2026",
            ],
        ):
            args = review_workflow.parse_args()

        self.assertEqual("collect-frontier-sources", args.command)
        self.assertEqual("generative_ai_economic_consequences", args.profile)
        self.assertEqual("abs_ajg_4star,ft50,utd24", args.source_ids)
        self.assertEqual(2025, args.year_start)
        self.assertEqual(2026, args.year_end)


if __name__ == "__main__":
    unittest.main()
