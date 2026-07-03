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


if __name__ == "__main__":
    unittest.main()
