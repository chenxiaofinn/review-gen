from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = REPO_ROOT / "skills" / "review-orchestrator" / "scripts" / "review_state_manager.py"
FRONTIER_SCRIPTS_ROOT = REPO_ROOT / "skills" / "openalex-ajg-insights" / "scripts"
if str(FRONTIER_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTIER_SCRIPTS_ROOT))

spec = importlib.util.spec_from_file_location("review_state_manager_under_test", STATUS_PATH)
review_state_manager = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(review_state_manager)

from frontier_push.candidates import FrontierCandidate, write_candidates_jsonl
from frontier_push.promotion import promote_frontier_candidates


TA_SOURCES = ("abs_ajg_4star", "ft50", "utd24")


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def write_source_payload(workspace: Path, source_id: str, profile_id: str, year_start: int, year_end: int) -> Path:
    path = workspace / "09_frontier_push" / "source_records" / f"{source_id}_{profile_id}_{year_start}_{year_end}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "source_id": source_id,
                "source_tier": "A",
                "profile_id": profile_id,
                "year_start": year_start,
                "year_end": year_end,
                "records": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def make_candidate(candidate_id: str = "fp_keep") -> FrontierCandidate:
    return FrontierCandidate(
        candidate_id=candidate_id,
        title="Technological Obsolescence",
        year=2026,
        venue="Review of Financial Studies",
        authors=["Song Ma"],
        doi="10.1093/rfs/hhaf059",
        openalex_id="",
        url="https://example.org/paper",
        abstract="This paper studies technological obsolescence.",
        source_id="abs_ajg_4star",
        source_tier="A",
        source_type="metadata",
        match_score=5,
        match_reasons=["exact phrase: technological obsolescence"],
        push_bucket="main_push",
        strong_signal=False,
    )


class ReviewOrchestratorStatusTests(unittest.TestCase):
    def test_empty_workspace_recommends_initialization_without_creating_plan_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            status = review_state_manager.compute_status(workspace)

            self.assertEqual("needs_init", status["current_stage"])
            self.assertEqual("init_workspace", status["recommended_next_action"]["action"])
            self.assertIn("workspace_layout", status["missing_inputs"])
            self.assertFalse((workspace / "07_plan").exists())

    def test_status_does_not_mutate_existing_workflow_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            files = [
                workspace / "07_plan" / "review_plan.md",
                workspace / "07_notes" / "review_plan.md",
                workspace / "03_screening" / "screening_table.csv",
                workspace / "04_fulltext" / "fulltext_manifest.csv",
                workspace / "02_corpus" / "master_corpus.jsonl",
                workspace / "09_frontier_push" / "source_records" / "abs_ajg_4star_profile_2025_2026.json",
                workspace / "09_frontier_push" / "runs" / "2026-07-03T000000" / "candidates.jsonl",
                workspace / "09_frontier_push" / "reports" / "profile" / "2026-07-03.md",
            ]
            for target in files:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.name == "master_corpus.jsonl":
                    target.write_text('{"paper_key":"doi::10.1/a","title":"A"}\n', encoding="utf-8")
                elif target.suffix == ".csv":
                    target.write_text("paper_key,included_title_abstract,need_full_text,expected_pdf_name,pdf_status,md_status\n", encoding="utf-8")
                elif target.name.endswith(".json"):
                    target.write_text('{"source_id":"abs_ajg_4star","profile_id":"profile","year_start":2025,"year_end":2026,"records":[]}\n', encoding="utf-8")
                elif target.name == "candidates.jsonl":
                    target.write_text("{}\n", encoding="utf-8")
                else:
                    target.write_text(f"sentinel::{target.name}\n", encoding="utf-8")
            before = {path: path.read_text(encoding="utf-8") for path in files}

            review_state_manager.compute_status(workspace)

            after = {path: path.read_text(encoding="utf-8") for path in files}
            self.assertEqual(before, after)

    def test_profile_without_source_records_recommends_collect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            profile_path = workspace / "09_frontier_push" / "profiles" / "tech_obsolescence.yml"
            profile_path.parent.mkdir(parents=True)
            profile_path.write_text("id: tech_obsolescence\n", encoding="utf-8")

            status = review_state_manager.compute_status(workspace)

            self.assertEqual("frontier_profile_ready", status["current_stage"])
            self.assertEqual("collect_frontier_sources", status["recommended_next_action"]["action"])
            self.assertEqual("tech_obsolescence", status["frontier_push"]["active_profile_id"])

    def test_current_ta_payloads_recommend_run_with_explicit_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            profile_id = "tech_obsolescence"
            profile_dir = workspace / "09_frontier_push" / "profiles"
            profile_dir.mkdir(parents=True)
            (profile_dir / f"{profile_id}.yml").write_text(f"id: {profile_id}\n", encoding="utf-8")
            expected_paths = [write_source_payload(workspace, source, profile_id, 2025, 2026) for source in TA_SOURCES]

            status = review_state_manager.compute_status(workspace)

            self.assertEqual("frontier_sources_ready", status["current_stage"])
            self.assertEqual("run_frontier_push", status["recommended_next_action"]["action"])
            self.assertEqual([str(path) for path in expected_paths], status["recommended_next_action"]["explicit_input_paths"])
            self.assertEqual([], status["frontier_push"]["warnings"])

    def test_mixed_source_record_windows_emit_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            profile_id = "tech_obsolescence"
            profile_dir = workspace / "09_frontier_push" / "profiles"
            profile_dir.mkdir(parents=True)
            (profile_dir / f"{profile_id}.yml").write_text(f"id: {profile_id}\n", encoding="utf-8")
            write_source_payload(workspace, "abs_ajg_4star", profile_id, 2025, 2026)
            write_source_payload(workspace, "ft50", profile_id, 2024, 2026)
            write_source_payload(workspace, "utd24", "other_profile", 2025, 2026)

            status = review_state_manager.compute_status(workspace)

            self.assertEqual("frontier_source_records_mixed", status["current_stage"])
            self.assertTrue(any("year windows" in warning for warning in status["frontier_push"]["warnings"]))
            self.assertTrue(any("profiles" in warning for warning in status["frontier_push"]["warnings"]))

    def test_candidates_block_on_human_triage_before_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-03T000000"
            candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
            write_candidates_jsonl(candidates_path, [make_candidate()])

            status = review_state_manager.compute_status(workspace)

            self.assertEqual("candidate_triage", status["current_stage"])
            self.assertEqual("candidate_triage", status["blocked_by_human"])
            self.assertEqual("promote_frontier_candidates", status["recommended_next_action"]["action"])

    def test_promoted_json_and_ris_recommend_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-03T000000"
            candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
            write_candidates_jsonl(candidates_path, [make_candidate()])
            promote_frontier_candidates(workspace, run_id, ["fp_keep"])

            status = review_state_manager.compute_status(workspace)

            self.assertEqual("promoted_ready_for_merge", status["current_stage"])
            self.assertEqual("merge_search_results", status["recommended_next_action"]["action"])
            self.assertTrue(status["frontier_push"]["promoted_raw_json"])
            self.assertTrue(status["frontier_push"]["consolidated_ris"])

    def test_merged_corpus_with_unfinished_screening_blocks_on_screening(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_jsonl(
                workspace / "02_corpus" / "master_corpus.jsonl",
                [{"paper_key": "doi::10.1/a", "title": "A", "full_text_priority": "medium"}],
            )
            write_csv(
                workspace / "03_screening" / "screening_table.csv",
                [{"paper_key": "doi::10.1/a", "included_title_abstract": "", "need_full_text": ""}],
                ["paper_key", "included_title_abstract", "need_full_text"],
            )

            status = review_state_manager.compute_status(workspace)

            self.assertEqual("screening_required", status["current_stage"])
            self.assertEqual("title_abstract_screening", status["blocked_by_human"])
            self.assertEqual("screen_manually", status["recommended_next_action"]["action"])

    def test_manifest_lists_missing_pdf_expected_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_jsonl(
                workspace / "02_corpus" / "master_corpus.jsonl",
                [{"paper_key": "doi::10.1/a", "title": "A", "full_text_priority": "medium"}],
            )
            write_csv(
                workspace / "03_screening" / "screening_table.csv",
                [{"paper_key": "doi::10.1/a", "included_title_abstract": "yes", "need_full_text": "yes"}],
                ["paper_key", "included_title_abstract", "need_full_text"],
            )
            write_csv(
                workspace / "04_fulltext" / "fulltext_manifest.csv",
                [{"paper_key": "doi::10.1/a", "expected_pdf_name": "2026__Author__a.pdf", "pdf_status": "missing", "md_status": ""}],
                ["paper_key", "expected_pdf_name", "pdf_status", "md_status"],
            )

            status = review_state_manager.compute_status(workspace)

            self.assertEqual("pdf_collection", status["current_stage"])
            self.assertEqual(["2026__Author__a.pdf"], status["pdf"]["missing_expected_pdf_names"])
            self.assertEqual("collect_pdfs", status["recommended_next_action"]["action"])

    def test_unapproved_plan_blocks_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_jsonl(
                workspace / "02_corpus" / "master_corpus.jsonl",
                [{"paper_key": "doi::10.1/a", "title": "A", "full_text_priority": "medium"}],
            )
            write_csv(
                workspace / "03_screening" / "screening_table.csv",
                [{"paper_key": "doi::10.1/a", "included_title_abstract": "yes", "need_full_text": "yes"}],
                ["paper_key", "included_title_abstract", "need_full_text"],
            )
            write_csv(
                workspace / "04_fulltext" / "fulltext_manifest.csv",
                [{"paper_key": "doi::10.1/a", "expected_pdf_name": "a.pdf", "pdf_status": "ready", "md_status": "ready"}],
                ["paper_key", "expected_pdf_name", "pdf_status", "md_status"],
            )
            (workspace / "06_chunks").mkdir(parents=True)
            (workspace / "06_chunks" / "chunk_index.jsonl").write_text("{}", encoding="utf-8")
            plan_path = workspace / "07_plan" / "review_plan.md"
            plan_path.parent.mkdir(parents=True)
            plan_path.write_text("Plan status: DRAFT - requires user confirmation before prose drafting.\n", encoding="utf-8")

            status = review_state_manager.compute_status(workspace)

            self.assertEqual("plan_approval_required", status["current_stage"])
            self.assertEqual("plan_approval", status["blocked_by_human"])
            self.assertEqual("approve_plan", status["recommended_next_action"]["action"])


if __name__ == "__main__":
    unittest.main()
