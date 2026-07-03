from __future__ import annotations

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

            result = promote_frontier_candidates(workspace, run_id, ["fp_keep"])

            output_path = Path(result["output_path"])
            payload = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertTrue(output_path.exists())
            self.assertEqual("frontier_push", payload["search_type"])
            self.assertEqual(1, len(payload["papers"]))
            self.assertEqual("10.1111/keep", payload["papers"][0]["doi"])
            self.assertEqual("Journal of Finance", payload["papers"][0]["journal"])
            self.assertFalse((workspace / "02_corpus" / "master_corpus.jsonl").exists())

    def test_promote_missing_candidate_id_raises_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-03T000000"
            candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
            write_candidates_jsonl(candidates_path, [make_candidate("fp_keep", "10.1111/keep", "Kept Paper")])

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

            result = promote_frontier_candidates(workspace, run_id, ["fp_only"], write_ris=False)

            # JSON is still written
            self.assertTrue(Path(result["output_path"]).exists())
            # RIS file is NOT written
            self.assertIsNone(result["consolidated_ris_path"])
            ris_dir = workspace / "02_corpus" / "zotero_ris"
            if ris_dir.exists():
                self.assertEqual(0, len(list(ris_dir.glob("*.ris"))))


if __name__ == "__main__":
    unittest.main()
