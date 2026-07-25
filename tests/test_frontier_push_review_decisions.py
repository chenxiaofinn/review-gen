import json
import tempfile
import unittest
from pathlib import Path

from frontier_push.candidates import FrontierCandidate, write_candidates_jsonl
from frontier_push.review_decisions import record_frontier_review


class FrontierReviewDecisionTests(unittest.TestCase):
    def test_records_decisions_against_run_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_id = "2026-07-14T000000"
            run_dir = workspace / "09_frontier_push" / "runs" / run_id
            candidate = FrontierCandidate(
                candidate_id="fp_keep", title="Paper", year=2026, venue="Journal",
                authors=[], doi="10.1/test", openalex_id="W1", url="", abstract="",
                source_id="ft50", source_tier="A", source_type="metadata",
                match_score=3, match_reasons=["exact phrase: AI"],
                push_bucket="main_push", strong_signal=False,
            )
            write_candidates_jsonl(run_dir / "candidates.jsonl", [candidate])
            decisions = workspace / "decisions.json"
            decisions.write_text(json.dumps([{
                "candidate_id": "fp_keep",
                "decision": "include",
                "reason": "Directly addresses the research question.",
            }]), encoding="utf-8")

            result = record_frontier_review(workspace, run_id, decisions, "reviewer")

            self.assertEqual(1, result["decision_count"])
            row = json.loads((run_dir / "review_decisions.jsonl").read_text(encoding="utf-8").strip())
            self.assertEqual("include", row["decision"])
            self.assertEqual("reviewer", row["reviewer"])


if __name__ == "__main__":
    unittest.main()
