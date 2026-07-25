from __future__ import annotations

import asyncio
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
import openalex_ajg_bridge


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


def write_frontier_source_settings(workspace: Path, source_ids: tuple[str, ...]) -> None:
    settings_path = workspace / "09_frontier_push" / "frontier_settings.yml"
    settings_path.write_text(
        "\n".join(
            [
                "source_ids:",
                *[f"- {source_id}" for source_id in source_ids],
                "year_start: 2025",
                "year_end: 2026",
                "limit_per_query: 100",
                "max_queries: 1",
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
    def test_draft_profile_marks_needs_revision_audit_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            drafted = {
                "status": "drafted",
                "profile": {
                    "id": "topic",
                    "name": "Topic",
                    "directionality": "factors_of",
                    "target_construct": "job satisfaction",
                    "exact_phrases": ["job satisfaction"],
                    "near_phrases": [],
                    "related_terms": [],
                    "exclude_keywords": [],
                    "jel_codes": [],
                    "natural_language": "Track factors of job satisfaction.",
                },
            }
            audit = {"status": "audited", "audit": {"status": "needs_revision"}}
            with patch("frontier_push.llm.draft_interest_profile", return_value=drafted), patch(
                "frontier_push.llm.audit_interest_profile", return_value=audit
            ):
                result = review_workflow.draft_interest_profile(
                    workspace,
                    "工作满意度的影响因素",
                    "api",
                    "factors_of",
                )

            self.assertEqual("pending", result["profile_audit"]["user_decision"]["status"])
            audit_text = Path(result["profile_audit_path"]).read_text(encoding="utf-8")
            self.assertIn("status: pending", audit_text)

    def test_descriptive_single_query_round_overrides_pass_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            drafted = {
                "status": "drafted",
                "profile": {
                    "id": "a_share_asset_pricing",
                    "name": "A-share asset pricing",
                    "directionality": "descriptive",
                    "target_construct": "A-share market and asset pricing",
                    "required_concept_groups": {
                        "market": ["A-share market"],
                        "pricing": ["asset pricing"],
                    },
                    "exact_phrases": ["A-share market", "asset pricing"],
                    "near_phrases": [],
                    "related_terms": [],
                    "exclude_keywords": [],
                    "jel_codes": ["G12"],
                    "natural_language": "Track A-share asset pricing.",
                },
            }
            audit = {
                "status": "audited",
                "audit": {
                    "status": "pass",
                    "suggested_changes": {},
                    "notes": [],
                },
            }
            with patch("frontier_push.llm.draft_interest_profile", return_value=drafted), patch(
                "frontier_push.llm.audit_interest_profile", return_value=audit
            ):
                result = review_workflow.draft_interest_profile(
                    workspace,
                    "A股市场与资产定价",
                    "api",
                    "descriptive",
                )

            profile_audit = result["profile_audit"]
            self.assertEqual("needs_revision", profile_audit["audit"]["status"])
            self.assertEqual("pending", profile_audit["user_decision"]["status"])
            self.assertIn(
                "only one query round",
                " ".join(profile_audit["audit"]["notes"]),
            )
            self.assertIn(
                "required_concept_groups",
                profile_audit["audit"]["suggested_changes"],
            )

    def test_descriptive_single_exact_alias_per_group_overrides_pass_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            drafted = {
                "status": "drafted",
                "profile": {
                    "id": "a_share_asset_pricing",
                    "name": "A-share asset pricing",
                    "directionality": "descriptive",
                    "target_construct": "A-share market and asset pricing",
                    "required_concept_groups": {
                        "market": ["A-share", "Chinese stock market"],
                        "pricing": ["asset pricing", "stock returns"],
                    },
                    "exact_phrases": ["A-share", "asset pricing"],
                    "near_phrases": ["Chinese stock market", "stock returns"],
                    "related_terms": [],
                    "exclude_keywords": [],
                    "jel_codes": ["G12"],
                    "natural_language": "Track A-share asset pricing.",
                },
            }
            audit = {
                "status": "audited",
                "audit": {
                    "status": "pass",
                    "suggested_changes": {},
                    "notes": [],
                },
            }
            with patch("frontier_push.llm.draft_interest_profile", return_value=drafted), patch(
                "frontier_push.llm.audit_interest_profile", return_value=audit
            ):
                result = review_workflow.draft_interest_profile(
                    workspace,
                    "A股市场与资产定价",
                    "api",
                    "descriptive",
                )

            profile_audit = result["profile_audit"]
            self.assertEqual("needs_revision", profile_audit["audit"]["status"])
            self.assertEqual("pending", profile_audit["user_decision"]["status"])
            notes = " ".join(profile_audit["audit"]["notes"])
            self.assertIn("fewer than two exact aliases", notes)
            self.assertIn("'market'", notes)
            self.assertIn("'pricing'", notes)

    def test_existing_pass_audit_is_stale_for_single_round_descriptive_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            profiles_dir = workspace / "09_frontier_push" / "profiles"
            profile_path = profiles_dir / "a_share_asset_pricing.yml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: a_share_asset_pricing",
                        "name: A-share asset pricing",
                        "directionality: descriptive",
                        "target_construct: A-share market and asset pricing",
                        "required_concept_groups:",
                        "  market:",
                        "    - A-share market",
                        "  pricing:",
                        "    - asset pricing",
                        "exact_phrases:",
                        "  - A-share market",
                        "  - asset pricing",
                        "near_phrases: []",
                        "related_terms: []",
                        "exclude_keywords: []",
                        "jel_codes: []",
                        "natural_language: Track A-share asset pricing.",
                    ]
                ),
                encoding="utf-8",
            )
            profile_path.with_suffix(".audit.yml").write_text(
                "audit:\n  status: pass\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "audit is stale"):
                review_workflow.validate_profile_audit_gate(
                    workspace,
                    "a_share_asset_pricing",
                )

            with patch(
                "openalex_ajg_bridge.bootstrap_repo",
                side_effect=AssertionError("preview must stop before backend bootstrap"),
            ):
                with self.assertRaisesRegex(ValueError, "audit is stale"):
                    review_workflow.preview_frontier_queries(
                        workspace,
                        "a_share_asset_pricing",
                    )

    def test_profile_audit_pending_blocks_frontier_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            audit_path = workspace / "09_frontier_push" / "profiles" / "topic.audit.yml"
            audit_path.write_text(
                "audit:\n  status: needs_revision\nuser_decision:\n  status: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "awaiting user confirmation"):
                review_workflow.run_frontier_push(workspace, "topic", ["A"], [])

    def test_profile_audit_pending_blocks_collection_before_backend_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            audit_path = (
                workspace
                / "09_frontier_push"
                / "profiles"
                / "firm_asset_pricing_determinants.audit.yml"
            )
            audit_path.write_text(
                "audit:\n  status: needs_revision\nuser_decision:\n  status: pending\n",
                encoding="utf-8",
            )

            with patch.object(openalex_ajg_bridge, "bootstrap_repo") as bootstrap:
                with self.assertRaisesRegex(ValueError, "awaiting user confirmation"):
                    asyncio.run(
                        review_workflow._collect_frontier_sources_async(
                            workspace=workspace,
                            profile_id="firm_asset_pricing_determinants",
                            source_ids=["abs3"],
                            year_start=2024,
                            year_end=2026,
                            limit_per_query=100,
                            max_queries=1,
                        )
                    )

            bootstrap.assert_not_called()

    def test_profile_audit_confirmed_decisions_pass_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            audit_path = workspace / "09_frontier_push" / "profiles" / "topic.audit.yml"
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            for decision in ("accepted", "partially_accepted", "rejected"):
                audit_path.write_text(
                    f"audit:\n  status: needs_revision\nuser_decision:\n  status: {decision}\n",
                    encoding="utf-8",
                )
                review_workflow.validate_profile_audit_gate(workspace, "topic")

    def test_profile_audit_pass_needs_no_user_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            audit_path = workspace / "09_frontier_push" / "profiles" / "topic.audit.yml"
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_text("audit:\n  status: pass\n", encoding="utf-8")

            review_workflow.validate_profile_audit_gate(workspace, "topic")

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
                "--directionality",
                "factors_of",
            ],
        ):
            args = review_workflow.parse_args()

        self.assertEqual("draft-interest-profile", args.command)
        self.assertEqual("检索企业资产定价影响因素", args.intent)
        self.assertEqual("factors_of", args.directionality)
        self.assertEqual("auto", args.llm_mode)

    def test_parse_args_accepts_bidirectional_directionality(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "review_workflow.py",
                "--workspace",
                "workspace",
                "draft-interest-profile",
                "--intent",
                "检索主题的影响因素和影响结果",
                "--directionality",
                "bidirectional",
            ],
        ):
            args = review_workflow.parse_args()

        self.assertEqual("bidirectional", args.directionality)

    def test_parse_args_requires_human_directionality(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "review_workflow.py",
                "--workspace",
                "workspace",
                "draft-interest-profile",
                "--intent",
                "检索一个主题",
            ],
        ):
            with self.assertRaises(SystemExit):
                review_workflow.parse_args()

    def test_init_frontier_push_writes_sources_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            payload = review_workflow.init_frontier_push(workspace)

            sources_path = workspace / "09_frontier_push" / "sources.yml"
            settings_path = workspace / "09_frontier_push" / "frontier_settings.yml"

            self.assertTrue(sources_path.exists())
            self.assertTrue(settings_path.exists())
            self.assertTrue((workspace / "09_frontier_push" / "profiles").exists())
            self.assertEqual(str(sources_path), payload["sources_path"])
            self.assertEqual(str(settings_path), payload["settings_path"])
            settings_text = settings_path.read_text(encoding="utf-8")
            self.assertIn("- abs3", settings_text)
            self.assertNotIn("- abs3_star", settings_text)
            self.assertNotIn("- ft50", settings_text)
            self.assertIn("limit_per_query: 100", settings_text)
            self.assertNotIn("max_queries:", settings_text)

    def test_partial_source_payload_is_rejected_before_candidate_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "abs3_profile_2024_2026.json"
            source_path.write_text(
                json.dumps(
                    {
                        "source_id": "abs3",
                        "source_tier": "A",
                        "source_type": "openalex_ajg",
                        "profile_id": "profile",
                        "year_start": 2024,
                        "year_end": 2026,
                        "records": [],
                        "diagnostics": {"collection_status": "partial", "has_more": True},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "incomplete"):
                review_workflow.validate_source_collection_completeness([str(source_path)])

    def test_collection_error_does_not_overwrite_existing_source_payload(self) -> None:
        class FailingClient:
            async def search_query_plan_for_issn_set(self, *args, **kwargs):
                raise RuntimeError("simulated API failure")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            output_path = (
                workspace
                / "09_frontier_push"
                / "source_records"
                / "abs_ajg_4star_firm_asset_pricing_determinants_2024_2026.json"
            )
            output_path.write_text('{"sentinel": true}\n', encoding="utf-8")

            with patch.object(openalex_ajg_bridge, "make_openalex_client", return_value=FailingClient()):
                with self.assertRaisesRegex(RuntimeError, "simulated API failure"):
                    asyncio.run(
                        review_workflow._collect_frontier_sources_async(
                            workspace=workspace,
                            profile_id="firm_asset_pricing_determinants",
                            source_ids=["abs_ajg_4star"],
                            year_start=2024,
                            year_end=2026,
                            limit_per_query=100,
                            max_queries=1,
                        )
                    )

            self.assertEqual('{"sentinel": true}\n', output_path.read_text(encoding="utf-8"))

    def test_collect_frontier_sources_uses_workspace_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            settings_path = workspace / "09_frontier_push" / "frontier_settings.yml"
            settings_path.write_text(
                "\n".join(
                    [
                        "source_ids:",
                        "  - ft50",
                        "year_start: 1990",
                        "year_end: 2000",
                        "limit_per_query: 30",
                        "max_queries: 4",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            captured = {}

            async def fake_collect(**kwargs):
                captured.update(kwargs)
                return {"ok": True}

            with patch.object(review_workflow, "_collect_frontier_sources_async", new=fake_collect):
                payload = review_workflow.collect_frontier_sources(
                    workspace,
                    "firm_asset_pricing_determinants",
                    source_ids=None,
                    year_start=None,
                    year_end=None,
                    limit_per_query=None,
                    max_queries=None,
                )

            self.assertEqual(
                {
                    "ok": True,
                    "max_queries": 4,
                    "max_queries_source": "frontier_settings.yml",
                },
                payload,
            )
            self.assertEqual(["ft50"], captured["source_ids"])
            self.assertEqual(1990, captured["year_start"])
            self.assertEqual(2000, captured["year_end"])
            self.assertEqual(30, captured["limit_per_query"])
            self.assertEqual(4, captured["max_queries"])
            self.assertEqual("frontier_settings.yml", captured["max_queries_source"])

    def test_collection_requires_persisted_max_queries_before_async_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            called = False

            async def fake_collect(**kwargs):
                nonlocal called
                called = True
                return {}

            with patch.object(review_workflow, "_collect_frontier_sources_async", new=fake_collect):
                with self.assertRaisesRegex(ValueError, "preview-frontier-queries"):
                    review_workflow.collect_frontier_sources(
                        workspace,
                        "firm_asset_pricing_determinants",
                        source_ids=None,
                        year_start=None,
                        year_end=None,
                        limit_per_query=None,
                        max_queries=None,
                    )

            self.assertFalse(called)

    def test_preview_frontier_queries_is_offline_and_estimates_both_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            profile_path = workspace / "09_frontier_push" / "profiles" / "a_share_asset_pricing.yml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: a_share_asset_pricing",
                        "name: A-share asset pricing",
                        "directionality: descriptive",
                        "target_construct: A-share market and asset pricing",
                        "exact_phrases:",
                        "  - A-share",
                        "  - asset pricing",
                        "near_phrases:",
                        "  - Chinese stock market",
                        "  - stock returns",
                        "related_terms:",
                        "  - expected returns",
                        "exclude_keywords: []",
                        "jel_codes:",
                        "  - G12",
                        "natural_language: Track A-share asset-pricing relationships.",
                        "required_concept_groups:",
                        "  market:",
                        "    - A-share",
                        "    - Chinese stock market",
                        "  pricing:",
                        "    - asset pricing",
                        "    - stock returns",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.object(openalex_ajg_bridge, "make_openalex_client") as make_client:
                payload = review_workflow.preview_frontier_queries(
                    workspace,
                    "a_share_asset_pricing",
                )

            make_client.assert_not_called()
            self.assertEqual(["exact", "exact+near"], [item["level"] for item in payload["rounds"]])
            self.assertEqual([1, 2], [item["max_queries"] for item in payload["max_queries_options"]])
            self.assertGreater(payload["issn_chunk_count"], 0)

    def test_collect_frontier_sources_cli_args_override_workspace_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)

            captured = {}

            async def fake_collect(**kwargs):
                captured.update(kwargs)
                return {"ok": True}

            with patch.object(review_workflow, "_collect_frontier_sources_async", new=fake_collect):
                review_workflow.collect_frontier_sources(
                    workspace,
                    "firm_asset_pricing_determinants",
                    source_ids=["utd24"],
                    year_start=2024,
                    year_end=2025,
                    limit_per_query=10,
                    max_queries=2,
                )

            self.assertEqual(["utd24"], captured["source_ids"])
            self.assertEqual(2024, captured["year_start"])
            self.assertEqual(2025, captured["year_end"])
            self.assertEqual(10, captured["limit_per_query"])
            self.assertEqual(2, captured["max_queries"])
            self.assertEqual("cli", captured["max_queries_source"])

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

    def test_run_frontier_push_uses_explicit_input_payload_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            stale_dir = workspace / "09_frontier_push" / "source_records"
            stale_dir.mkdir(parents=True, exist_ok=True)
            stale_payload = {
                "source_id": "ft50",
                "source_tier": "A",
                "profile_id": "firm_asset_pricing_determinants",
                "year_start": 2025,
                "year_end": 2026,
                "records": [],
            }
            (stale_dir / "ft50_stale_2025_2026.json").write_text(
                json.dumps(stale_payload, ensure_ascii=False),
                encoding="utf-8",
            )
            current_payload = {
                "source_id": "ft50",
                "source_tier": "A",
                "profile_id": "firm_asset_pricing_determinants",
                "year_start": 1990,
                "year_end": 2000,
                "records": [
                    {
                        "title": "Old Expected Stock Returns",
                        "year": 1995,
                        "journal": "Journal of Finance",
                        "abstract": "Expected stock returns and profitability.",
                        "doi": "10.1/old-current-input",
                        "authors": ["A Author"],
                    }
                ],
            }
            records_path = workspace / "ft50_current_1990_2000.json"
            records_path.write_text(json.dumps(current_payload, ensure_ascii=False), encoding="utf-8")

            payload = review_workflow.run_frontier_push(
                workspace,
                "firm_asset_pricing_determinants",
                ["A"],
                [str(records_path)],
                "explicit-input-bounds",
                year_start=1990,
                year_end=2000,
            )

            candidates = Path(payload["candidates_path"]).read_text(encoding="utf-8")
            self.assertEqual(1, payload["candidate_count"])
            self.assertIn("Old Expected Stock Returns", candidates)
            self.assertEqual(0, payload["year_filter"]["excluded_by_payload_bounds"])

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

    def test_parse_args_includes_preview_frontier_queries(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "review_workflow.py",
                "--workspace",
                "workspace",
                "preview-frontier-queries",
                "--profile",
                "a_share_asset_pricing",
            ],
        ):
            args = review_workflow.parse_args()

        self.assertEqual("preview-frontier-queries", args.command)
        self.assertEqual("a_share_asset_pricing", args.profile)


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

    def test_ta_only_is_default_and_expanded_search_is_explicit(self) -> None:
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
            ],
        ):
            default_args = review_workflow.parse_args()

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
                "--expanded-search",
            ],
        ):
            expanded_args = review_workflow.parse_args()

        self.assertTrue(default_args.ta_only)
        self.assertFalse(expanded_args.ta_only)

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
            write_frontier_source_settings(workspace, ("abs_ajg_4star", "ft50", "utd24"))
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
            write_frontier_source_settings(workspace, ("abs_ajg_4star", "ft50", "utd24"))
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
            write_frontier_source_settings(workspace, ("abs_ajg_4star", "ft50", "utd24"))
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
            write_frontier_source_settings(workspace, ("abs_ajg_4star", "ft50", "utd24"))
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
            write_frontier_source_settings(workspace, ("abs_ajg_4star", "ft50", "utd24"))
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
            write_frontier_source_settings(
                workspace,
                ("abs3", "abs3_star", "abs4", "abs_ajg_4star", "ft50", "utd24"),
            )
            inputs = [
                str(write_ta_payload(workspace, "abs3")),
                str(write_ta_payload(workspace, "abs3_star")),
                str(write_ta_payload(workspace, "abs4")),
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

    def test_ta_only_accepts_workspace_configured_abs3_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            review_workflow.init_frontier_push(workspace)
            write_profile(workspace)
            write_frontier_source_settings(workspace, ("abs3",))
            inputs = [str(write_ta_payload(workspace, "abs3", with_record=True))]

            payload = review_workflow.run_frontier_push(
                workspace,
                "firm_asset_pricing_determinants",
                ["A"],
                inputs,
                "ta-abs3-only",
                year_start=2025,
                year_end=2026,
                ta_only=True,
            )

            self.assertEqual(1, payload["candidate_count"])
            self.assertEqual(["A"], payload["source_tiers"])


if __name__ == "__main__":
    unittest.main()
