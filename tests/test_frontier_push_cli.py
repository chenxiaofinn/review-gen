from __future__ import annotations

import importlib.util
import io
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


def write_profile(workspace: Path, profile_id: str = "firm_asset_pricing_determinants") -> None:
    profile_path = workspace / "09_frontier_push" / "profiles" / f"{profile_id}.yml"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        "\n".join(
            [
                f"id: {profile_id}",
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


def write_ta_payload(
    workspace: Path,
    source_id: str,
    profile_id: str = "firm_asset_pricing_determinants",
    year_start: int = 2025,
    year_end: int = 2026,
    with_record: bool = False,
) -> Path:
    payload = {
        "source_id": source_id,
        "source_tier": "A",
        "profile_id": profile_id,
        "year_start": year_start,
        "year_end": year_end,
        "records": [],
    }
    if with_record:
        payload["records"].append(
            {
                "title": "Current Expected Stock Returns",
                "year": 2025,
                "journal": "Journal of Finance",
                "abstract": "Expected stock returns and profitability.",
                "doi": "10.1/current",
                "authors": ["A Author"],
            }
        )
    path = workspace / f"{source_id}_{profile_id}_{year_start}_{year_end}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


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


    def test_parse_args_includes_ta_only_run_mode(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "review_workflow.py",
                "--workspace",
                "workspace",
                "run-frontier-push",
                "--profile",
                "firm_asset_pricing_determinants",
                "--ta-only",
                "--year-start",
                "2025",
                "--year-end",
                "2026",
                "--input",
                "abs.json",
                "ft50.json",
                "utd24.json",
            ],
        ):
            args = review_workflow.parse_args()

        self.assertEqual("run-frontier-push", args.command)
        self.assertTrue(args.ta_only)

    def test_ta_only_main_defaults_source_tiers_to_a(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "review_workflow.py",
                "--workspace",
                "workspace",
                "run-frontier-push",
                "--profile",
                "firm_asset_pricing_determinants",
                "--ta-only",
                "--year-start",
                "2025",
                "--year-end",
                "2026",
                "--input",
                "abs.json",
                "ft50.json",
                "utd24.json",
            ],
        ), patch.object(review_workflow, "find_workspace", return_value=Path("workspace")), patch.object(
            review_workflow,
            "ensure_plan_layout",
            return_value={"canonical_plan_dir": "", "legacy_plan_dir": "", "moved_plan_file": False, "moved_history_entries": 0},
        ), patch.object(review_workflow, "run_frontier_push") as run_mock, patch("sys.stdout", new_callable=io.StringIO):
            run_mock.return_value = {"ok": True}

            self.assertEqual(0, review_workflow.main())

        self.assertEqual(["A"], run_mock.call_args.args[2])
        self.assertTrue(run_mock.call_args.kwargs["ta_only"])

    def test_ta_only_requires_explicit_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)

            with self.assertRaisesRegex(ValueError, "--input"):
                review_workflow.run_frontier_push(
                    workspace,
                    "firm_asset_pricing_determinants",
                    ["A"],
                    [],
                    "ta-no-input",
                    year_start=2025,
                    year_end=2026,
                    ta_only=True,
                )

    def test_ta_only_requires_year_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            inputs = [str(write_ta_payload(workspace, source_id)) for source_id in ("abs_ajg_4star", "ft50", "utd24")]

            with self.assertRaisesRegex(ValueError, "year-start"):
                review_workflow.run_frontier_push(
                    workspace,
                    "firm_asset_pricing_determinants",
                    ["A"],
                    inputs,
                    "ta-no-year",
                    ta_only=True,
                )

    def test_ta_only_rejects_non_a_source_tiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            inputs = [str(write_ta_payload(workspace, source_id)) for source_id in ("abs_ajg_4star", "ft50", "utd24")]

            with self.assertRaisesRegex(ValueError, "source-tiers A"):
                review_workflow.run_frontier_push(
                    workspace,
                    "firm_asset_pricing_determinants",
                    ["A", "C"],
                    inputs,
                    "ta-tier-c",
                    year_start=2025,
                    year_end=2026,
                    ta_only=True,
                )

    def test_ta_only_requires_all_three_ta_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            inputs = [str(write_ta_payload(workspace, source_id)) for source_id in ("abs_ajg_4star", "ft50")]

            with self.assertRaisesRegex(ValueError, "Missing TA source"):
                review_workflow.run_frontier_push(
                    workspace,
                    "firm_asset_pricing_determinants",
                    ["A"],
                    inputs,
                    "ta-missing-source",
                    year_start=2025,
                    year_end=2026,
                    ta_only=True,
                )

    def test_ta_only_rejects_unexpected_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            inputs = [str(write_ta_payload(workspace, source_id)) for source_id in ("abs_ajg_4star", "ft50", "utd24")]
            inputs.append(str(write_ta_payload(workspace, "nber_wp")))

            with self.assertRaisesRegex(ValueError, "Unexpected TA-only source"):
                review_workflow.run_frontier_push(
                    workspace,
                    "firm_asset_pricing_determinants",
                    ["A"],
                    inputs,
                    "ta-unexpected-source",
                    year_start=2025,
                    year_end=2026,
                    ta_only=True,
                )

    def test_ta_only_rejects_duplicate_source_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            duplicate_ft50 = write_ta_payload(workspace, "ft50", year_start=2025, year_end=2026)
            duplicate_ft50_copy = workspace / "ft50_duplicate.json"
            duplicate_ft50_copy.write_text(duplicate_ft50.read_text(encoding="utf-8"), encoding="utf-8")
            inputs = [
                str(write_ta_payload(workspace, "abs_ajg_4star")),
                str(duplicate_ft50),
                str(duplicate_ft50_copy),
                str(write_ta_payload(workspace, "utd24")),
            ]

            with self.assertRaisesRegex(ValueError, "Duplicate TA source"):
                review_workflow.run_frontier_push(
                    workspace,
                    "firm_asset_pricing_determinants",
                    ["A"],
                    inputs,
                    "ta-duplicate-source",
                    year_start=2025,
                    year_end=2026,
                    ta_only=True,
                )

    def test_ta_only_rejects_profile_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            inputs = [str(write_ta_payload(workspace, source_id)) for source_id in ("abs_ajg_4star", "ft50", "utd24")]
            inputs[1] = str(write_ta_payload(workspace, "ft50", profile_id="other_profile"))

            with self.assertRaisesRegex(ValueError, "profile"):
                review_workflow.run_frontier_push(
                    workspace,
                    "firm_asset_pricing_determinants",
                    ["A"],
                    inputs,
                    "ta-profile-mismatch",
                    year_start=2025,
                    year_end=2026,
                    ta_only=True,
                )

    def test_ta_only_rejects_year_window_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            inputs = [str(write_ta_payload(workspace, source_id)) for source_id in ("abs_ajg_4star", "ft50", "utd24")]
            inputs[2] = str(write_ta_payload(workspace, "utd24", year_start=2024, year_end=2026))

            with self.assertRaisesRegex(ValueError, "year window"):
                review_workflow.run_frontier_push(
                    workspace,
                    "firm_asset_pricing_determinants",
                    ["A"],
                    inputs,
                    "ta-year-mismatch",
                    year_start=2025,
                    year_end=2026,
                    ta_only=True,
                )

    def test_ta_only_happy_path_writes_candidates_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            inputs = [
                str(write_ta_payload(workspace, "abs_ajg_4star", with_record=True)),
                str(write_ta_payload(workspace, "ft50")),
                str(write_ta_payload(workspace, "utd24")),
            ]

            payload = review_workflow.run_frontier_push(
                workspace,
                "firm_asset_pricing_determinants",
                ["A"],
                inputs,
                "ta-happy-path",
                year_start=2025,
                year_end=2026,
                ta_only=True,
            )

            self.assertEqual(1, payload["candidate_count"])
            self.assertEqual(["A"], payload["source_tiers"])
            self.assertTrue(Path(payload["candidates_path"]).exists())
            self.assertTrue(Path(payload["report_path"]).exists())


if __name__ == "__main__":
    unittest.main()
