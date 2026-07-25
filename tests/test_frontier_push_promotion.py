from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "openalex-ajg-insights" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from frontier_push.candidates import FrontierCandidate, write_candidates_jsonl
from frontier_push.promotion import promote_frontier_candidates
from review_workflow import merge_search_results


def mark_included(candidates_path: Path, *candidate_ids: str) -> None:
    candidates_path.parent.mkdir(parents=True, exist_ok=True)
    candidates_path.parent.joinpath("review_decisions.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "candidate_id": item,
                    "decision": "include",
                    "reason": "Relevant to the reviewed topic.",
                    "reviewer": "human-reviewer",
                    "reviewed_at": "2026-07-25T00:00:00+00:00",
                }
            )
            + "\n"
            for item in candidate_ids
        ),
        encoding="utf-8",
    )


def make_candidate(candidate_id: str, doi: str, title: str) -> FrontierCandidate:
    return FrontierCandidate(
        candidate_id=candidate_id,
        title=title,
        year=2026,
        venue="Journal of Finance",
        authors=["A Author"],
        doi=doi,
        openalex_id="",
        url="https://example.org/paper",
        abstract="Profitability explains expected stock returns.",
        source_id="abs4_star",
        source_tier="A",
        source_type="metadata",
        match_score=5,
        match_reasons=["exact phrase: expected stock returns"],
        push_bucket="main_push",
        strong_signal=False,
    )


class FrontierPromotionTests(unittest.TestCase):
    def test_promote_selected_candidates_writes_raw_json_without_master_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-03T000000"
            candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
            write_candidates_jsonl(
                candidates_path,
                [
                    make_candidate("fp_keep", "10.1111/keep", "Expected Stock Returns and Firm Characteristics"),
                    make_candidate("fp_skip", "10.1111/skip", "A Different Paper"),
                ],
            )
            mark_included(candidates_path, "fp_keep")

            result = promote_frontier_candidates(workspace, run_id, ["fp_keep"])

            output_path = Path(result["output_path"])
            payload = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertTrue(output_path.exists())
            self.assertEqual("frontier_push", payload["search_type"])
            self.assertEqual(1, len(payload["papers"]))
            self.assertEqual("10.1111/keep", payload["papers"][0]["doi"])
            self.assertEqual("Journal of Finance", payload["papers"][0]["journal"])
            self.assertEqual("include", payload["papers"][0]["frontier_review_decision"])
            self.assertEqual("human-reviewer", payload["papers"][0]["frontier_reviewer"])
            self.assertEqual(
                "2026-07-25T00:00:00+00:00",
                payload["papers"][0]["frontier_reviewed_at"],
            )
            self.assertFalse((workspace / "02_corpus" / "master_corpus.jsonl").exists())

    def test_promote_missing_candidate_id_raises_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-03T000000"
            candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
            write_candidates_jsonl(candidates_path, [make_candidate("fp_keep", "10.1111/keep", "Kept Paper")])
            mark_included(candidates_path, "fp_keep")

            with self.assertRaisesRegex(ValueError, "fp_missing"):
                promote_frontier_candidates(workspace, run_id, ["fp_missing"])

    def test_promote_writes_consolidated_ris(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-03T180322"
            candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
            write_candidates_jsonl(
                candidates_path,
                [
                    make_candidate("fp_first", "10.1111/first", "First Paper Title"),
                    make_candidate("fp_second", "10.1111/second", "Second Paper Title"),
                ],
            )
            mark_included(candidates_path, "fp_first", "fp_second")

            result = promote_frontier_candidates(workspace, run_id, ["fp_first", "fp_second"])

            ris_path = Path(result["consolidated_ris_path"])
            self.assertTrue(ris_path.exists())
            # Path uses the run-id stem, parallel to the raw JSON path
            self.assertEqual(
                workspace / "02_corpus" / "zotero_ris" / "frontier_push_2026-07-03T180322.ris",
                ris_path,
            )
            # Only one RIS file for the whole promotion, not one per candidate
            ris_dir = workspace / "02_corpus" / "zotero_ris"
            self.assertEqual(1, len(list(ris_dir.glob("*.ris"))))
            ris_text = ris_path.read_text(encoding="utf-8")
            # Two records, each with TY - JOUR and ER -
            self.assertEqual(2, ris_text.count("TY  - JOUR"))
            self.assertEqual(2, ris_text.count("ER  -"))
            # Both papers are present, in the order they were promoted
            self.assertIn("First Paper Title", ris_text)
            self.assertIn("Second Paper Title", ris_text)
            # DOI / authors / keywords are emitted for each record
            self.assertIn("DO  - 10.1111/first", ris_text)
            self.assertIn("DO  - 10.1111/second", ris_text)
            self.assertIn("AU  - Author, A", ris_text)
            # match_reason keywords are derived, not hard-coded
            self.assertIn("KW  - expected stock returns", ris_text)

    def test_promote_consolidated_ris_overwrites_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-03T180322"
            candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
            write_candidates_jsonl(
                candidates_path,
                [
                    make_candidate("fp_a", "10.1111/a", "Paper A"),
                    make_candidate("fp_b", "10.1111/b", "Paper B"),
                ],
            )
            mark_included(candidates_path, "fp_a", "fp_b")
            # First promotion: 2 candidates
            promote_frontier_candidates(workspace, run_id, ["fp_a", "fp_b"])
            # Second promotion with same run_id but fewer candidates
            result = promote_frontier_candidates(workspace, run_id, ["fp_a"])
            ris_path = Path(result["consolidated_ris_path"])
            ris_text = ris_path.read_text(encoding="utf-8")
            self.assertEqual(1, ris_text.count("TY  - JOUR"))
            self.assertIn("Paper A", ris_text)
            self.assertNotIn("Paper B", ris_text)

    def test_promote_skips_ris_when_write_ris_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-03T180322"
            candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
            write_candidates_jsonl(
                candidates_path,
                [make_candidate("fp_only", "10.1111/only", "Only Paper")],
            )
            mark_included(candidates_path, "fp_only")

            result = promote_frontier_candidates(workspace, run_id, ["fp_only"], write_ris=False)

            # JSON is still written
            self.assertTrue(Path(result["output_path"]).exists())
            # RIS file is NOT written
            self.assertIsNone(result["consolidated_ris_path"])
            ris_dir = workspace / "02_corpus" / "zotero_ris"
            if ris_dir.exists():
                self.assertEqual(0, len(list(ris_dir.glob("*.ris"))))

    def test_promoted_json_merges_into_corpus_with_frontier_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-17T120000"
            candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
            write_candidates_jsonl(
                candidates_path,
                [make_candidate("fp_trace", "10.1111/trace", "Traceable Frontier Paper")],
            )
            mark_included(candidates_path, "fp_trace")

            result = promote_frontier_candidates(workspace, run_id, ["fp_trace"])
            merge_result = merge_search_results(workspace, [result["output_path"]])

            corpus_rows = json.loads(
                "[" + ",".join(
                    line
                    for line in (workspace / "02_corpus" / "master_corpus.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ) + "]"
            )
            self.assertEqual(1, merge_result["unique_papers"])
            self.assertEqual(1, len(corpus_rows))
            self.assertEqual("fp_trace", corpus_rows[0]["frontier_candidate_id"])
            self.assertEqual(run_id, corpus_rows[0]["source_run_id"])
            self.assertEqual("doi::10.1111/trace", corpus_rows[0]["paper_key"])
            with (workspace / "03_screening" / "screening_table.csv").open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as handle:
                screening_rows = list(csv.DictReader(handle))
            self.assertEqual("yes", screening_rows[0]["included_title_abstract"])
            self.assertEqual("yes", screening_rows[0]["need_full_text"])
            self.assertIn("human-reviewer", screening_rows[0]["screening_notes"])
            self.assertIn(run_id, screening_rows[0]["screening_notes"])

    def test_merge_does_not_overwrite_existing_manual_screening_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-17T130000"
            candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
            write_candidates_jsonl(
                candidates_path,
                [make_candidate("fp_manual", "10.1111/manual", "Manually Screened Paper")],
            )
            mark_included(candidates_path, "fp_manual")
            screening_path = workspace / "03_screening" / "screening_table.csv"
            screening_path.parent.mkdir(parents=True, exist_ok=True)
            screening_path.write_text(
                "paper_key,title,year,journal,doi,openalex_id,matched_query,search_type,"
                "search_scope,citations,full_text_priority,included_title_abstract,"
                "exclusion_reason,need_full_text,screening_notes\n"
                "doi::10.1111/manual,Old title,2026,Journal of Finance,10.1111/manual,,,"
                ",,0,,no,manual exclusion,no,Keep this manual decision.\n",
                encoding="utf-8",
            )

            result = promote_frontier_candidates(workspace, run_id, ["fp_manual"])
            merge_search_results(workspace, [result["output_path"]])

            with screening_path.open("r", encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual("no", row["included_title_abstract"])
            self.assertEqual("no", row["need_full_text"])
            self.assertEqual("manual exclusion", row["exclusion_reason"])
            self.assertEqual("Keep this manual decision.", row["screening_notes"])


if __name__ == "__main__":
    unittest.main()
