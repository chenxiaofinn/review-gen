import tempfile
import unittest
import sys
import json
from pathlib import Path
from unittest.mock import patch

SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "skills" / "openalex-ajg-insights" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from frontier_push.candidates import FrontierCandidate, write_candidates_jsonl
from frontier_push.pdf_download import download_frontier_pdfs
from frontier_push.promotion import promote_frontier_candidates


class FrontierPdfDownloadTests(unittest.TestCase):
    def test_include_drives_promotion_and_pdf_download_without_candidate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_dir = workspace / "09_frontier_push" / "runs" / "run-closed-loop"
            candidate = FrontierCandidate(
                candidate_id="fp_loop", title="Closed loop paper", year=2026, venue="Journal",
                authors=[], doi="10.1000/loop", openalex_id="W1", url="", abstract="",
                source_id="ft50", source_tier="A", source_type="metadata",
                match_score=3, match_reasons=[], push_bucket="main_push", strong_signal=False,
            )
            write_candidates_jsonl(run_dir / "candidates.jsonl", [candidate])
            (run_dir / "review_decisions.jsonl").write_text(
                '{"candidate_id":"fp_loop","decision":"include"}\n', encoding="utf-8"
            )

            promotion = promote_frontier_candidates(workspace, "run-closed-loop")

            def fake_download(_url: str, destination: Path, _timeout: int) -> None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.7\n" + b"x" * 1024)

            with patch("frontier_push.pdf_download._openalex_pdf", return_value="https://example.org/paper.pdf"), \
                 patch("frontier_push.pdf_download._download_pdf", side_effect=fake_download):
                download = download_frontier_pdfs(workspace, "run-closed-loop")

            promoted = json.loads(Path(promotion["output_path"]).read_text(encoding="utf-8"))
            self.assertEqual(["fp_loop"], [paper["frontier_candidate_id"] for paper in promoted["papers"]])
            self.assertEqual(1, download["downloaded"])
            self.assertTrue(list((workspace / "04_fulltext" / "pdf_inbox").glob("fp_loop_*.pdf")))

    def test_downloads_only_explicit_candidate_and_writes_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_dir = workspace / "09_frontier_push" / "runs" / "run-1"
            candidates = [
                FrontierCandidate(
                    candidate_id="fp_one", title="Open paper", year=2026, venue="Journal",
                    authors=[], doi="10.1000/one", openalex_id="W1", url="", abstract="",
                    source_id="ft50", source_tier="A", source_type="metadata",
                    match_score=3, match_reasons=[], push_bucket="main_push", strong_signal=False,
                ),
                FrontierCandidate(
                    candidate_id="fp_two", title="Unselected", year=2026, venue="Journal",
                    authors=[], doi="10.1000/two", openalex_id="W2", url="", abstract="",
                    source_id="ft50", source_tier="A", source_type="metadata",
                    match_score=3, match_reasons=[], push_bucket="main_push", strong_signal=False,
                ),
            ]
            write_candidates_jsonl(run_dir / "candidates.jsonl", candidates)
            (run_dir / "review_decisions.jsonl").write_text(
                '{"candidate_id":"fp_one","decision":"include"}\n', encoding="utf-8"
            )

            def fake_download(_url: str, destination: Path, _timeout: int) -> None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.7\n" + b"x" * 1024)

            with patch("frontier_push.pdf_download._openalex_pdf", return_value="https://example.org/paper.pdf"), \
                 patch("frontier_push.pdf_download._download_pdf", side_effect=fake_download):
                result = download_frontier_pdfs(workspace, "run-1", ["fp_one"])

            self.assertEqual(1, result["downloaded"])
            self.assertEqual(0, result["manual_required"])
            self.assertTrue(Path(result["pdf_downloads_path"]).exists())
            self.assertTrue(list((workspace / "04_fulltext" / "pdf_inbox").glob("fp_one_*.pdf")))
            self.assertFalse(list((workspace / "04_fulltext" / "pdf_inbox").glob("fp_two_*.pdf")))

    def test_missing_pdf_goes_to_manual_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_dir = workspace / "09_frontier_push" / "runs" / "run-1"
            candidate = FrontierCandidate(
                candidate_id="fp_missing", title="Closed paper", year=2026, venue="Journal",
                authors=[], doi="10.1000/missing", openalex_id="W1", url="", abstract="",
                source_id="ft50", source_tier="A", source_type="metadata",
                match_score=3, match_reasons=[], push_bucket="main_push", strong_signal=False,
            )
            write_candidates_jsonl(run_dir / "candidates.jsonl", [candidate])
            (run_dir / "review_decisions.jsonl").write_text(
                '{"candidate_id":"fp_missing","decision":"include"}\n', encoding="utf-8"
            )
            with patch("frontier_push.pdf_download._openalex_pdf", return_value=None):
                result = download_frontier_pdfs(workspace, "run-1", ["fp_missing"])
            self.assertEqual(0, result["downloaded"])
            self.assertEqual(1, result["manual_required"])
            self.assertIn("fp_missing", Path(result["manual_download_path"]).read_text(encoding="utf-8"))

    def test_openalex_download_failure_falls_back_to_unpaywall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_dir = workspace / "09_frontier_push" / "runs" / "run-1"
            candidate = FrontierCandidate(
                candidate_id="fp_fallback", title="Fallback paper", year=2026, venue="Journal",
                authors=[], doi="10.1000/fallback", openalex_id="W1", url="", abstract="",
                source_id="ft50", source_tier="A", source_type="metadata",
                match_score=3, match_reasons=[], push_bucket="main_push", strong_signal=False,
            )
            write_candidates_jsonl(run_dir / "candidates.jsonl", [candidate])
            (run_dir / "review_decisions.jsonl").write_text(
                '{"candidate_id":"fp_fallback","decision":"include"}\n', encoding="utf-8"
            )

            def fake_download(url: str, destination: Path, _timeout: int) -> None:
                if "openalex" in url:
                    raise ValueError("openalex response was HTML")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.7\n" + b"x" * 1024)

            with patch("frontier_push.pdf_download._openalex_pdf", return_value="https://openalex/paper"), \
                 patch("frontier_push.pdf_download._unpaywall_pdf", return_value="https://unpaywall/paper"), \
                 patch("frontier_push.pdf_download._download_pdf", side_effect=fake_download):
                result = download_frontier_pdfs(workspace, "run-1", ["fp_fallback"], email="test@example.org")

            self.assertEqual(1, result["downloaded"])
            row = json.loads((run_dir / "pdf_downloads.jsonl").read_text(encoding="utf-8").strip())
            self.assertEqual("unpaywall", row["source"])


if __name__ == "__main__":
    unittest.main()
