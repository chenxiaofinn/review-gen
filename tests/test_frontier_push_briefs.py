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

from frontier_push.briefs import (
    BRIEF_FORMAT_VERSION,
    build_frontier_brief_prompt,
    collect_brief_inputs,
    render_frontier_brief,
    validate_brief_payload,
)


class FrontierBriefTests(unittest.TestCase):
    def _workspace(self, root: Path) -> tuple[Path, str]:
        workspace = root / "workspace"
        run_id = "frontier_test"
        run_dir = workspace / "09_frontier_push" / "runs" / run_id
        run_dir.mkdir(parents=True)
        candidate = {
            "candidate_id": "fp_test",
            "title": "Repetitive Work and Job Satisfaction",
            "year": 2025,
            "venue": "Test Journal",
            "authors": ["A Author"],
            "doi": "10.1000/test",
            "abstract": "A test abstract.",
            "source_id": "ft50",
            "source_tier": "A",
            "source_type": "metadata",
            "match_score": 6,
            "match_reasons": [],
            "push_bucket": "main_push",
            "strong_signal": False,
            "openalex_id": "",
            "url": "",
        }
        (run_dir / "candidates.jsonl").write_text(json.dumps(candidate) + "\n", encoding="utf-8")
        (run_dir / "review_decisions.jsonl").write_text(
            json.dumps({"candidate_id": "fp_test", "decision": "include"}) + "\n",
            encoding="utf-8",
        )
        md_path = workspace / "05_mineru" / "extracted" / "paper" / "paper.md"
        md_path.parent.mkdir(parents=True)
        md_path.write_text("# Paper\n\nThis paper reports a test finding.", encoding="utf-8")
        manifest_path = workspace / "04_fulltext" / "fulltext_manifest.csv"
        manifest_path.parent.mkdir(parents=True)
        with manifest_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["doi", "md_status", "md_path"])
            writer.writeheader()
            writer.writerow({"doi": "10.1000/test", "md_status": "ready", "md_path": str(md_path)})
        return workspace, run_id

    def test_collect_and_render_use_fixed_traceable_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, run_id = self._workspace(Path(tmp))
            inputs = collect_brief_inputs(workspace, run_id)
            payload = {
                "executive_summary": "摘要。",
                "papers": [{
                    "candidate_id": "fp_test",
                    "why_it_matters": "相关。",
                    "research_question": "问题。",
                    "data_and_method": "方法。",
                    "main_findings": "发现。",
                    "contribution": "贡献。",
                    "limitations": "局限。",
                }],
                "cross_paper_synthesis": "单篇证据。",
                "research_implications": "启示。",
                "evidence_boundaries": "边界。",
            }
            validate_brief_payload(payload, ["fp_test"])
            rendered = render_frontier_brief("profile_test", run_id, "model_test", inputs, payload)

            self.assertIn(f"格式版本：`{BRIEF_FORMAT_VERSION}`", rendered)
            self.assertIn("## 3. 文献速览", rendered)
            self.assertIn("## 7. 输入追溯", rendered)
            self.assertIn("fp_test", rendered)
            self.assertIn("SHA-256", rendered)

    def test_prompt_requires_structured_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, run_id = self._workspace(Path(tmp))
            prompt = build_frontier_brief_prompt("profile_test", run_id, collect_brief_inputs(workspace, run_id))
            self.assertIn("只返回一个 JSON 对象", prompt)
            self.assertIn('"candidate_id"', prompt)
            self.assertIn("full_text_markdown", prompt)


if __name__ == "__main__":
    unittest.main()
