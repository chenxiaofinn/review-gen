from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "openalex-ajg-insights" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from frontier_push.decomposition import build_decomposition_prompt, decompose_paper


class FrontierPaperDecompositionTests(unittest.TestCase):
    def test_build_decomposition_prompt_contains_two_stage_chinese_constraints(self) -> None:
        prompt = build_decomposition_prompt(
            paper={
                "title": "Firm Characteristics and Expected Stock Returns",
                "authors": ["A Author"],
                "year": 2026,
                "venue": "Journal of Finance",
                "abstract": "Profitability explains expected stock returns.",
            },
            excerpts=[
                "The paper contributes by linking firm characteristics to the cross-section of returns.",
                "R&D intensity is one of the firm-level variables.",
            ],
        )

        self.assertIn("Stage 1", prompt)
        self.assertIn("Stage 2", prompt)
        self.assertIn("简体中文", prompt)
        self.assertIn("不是翻译全文", prompt)
        self.assertIn("准确第一", prompt)
        self.assertIn("过程完整", prompt)
        self.assertIn("边际贡献", prompt)
        self.assertIn("R&D -> 研发", prompt)
        self.assertIn("Firm Characteristics and Expected Stock Returns", prompt)

    def test_decompose_paper_without_key_writes_prompt_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = decompose_paper(
                workspace=workspace,
                paper_key="paper_001",
                paper={
                    "title": "Firm Characteristics and Expected Stock Returns",
                    "authors": ["A Author"],
                    "year": 2026,
                    "venue": "Journal of Finance",
                    "abstract": "Profitability explains expected stock returns.",
                },
                excerpts=["This paper studies the determinants of expected stock returns."],
                llm_mode="auto",
                env={},
            )

            output_path = Path(result["output_path"])
            content = output_path.read_text(encoding="utf-8")

            self.assertEqual("prompt_fallback", result["status"])
            self.assertEqual("missing_api_key", result["reason"])
            self.assertTrue(output_path.exists())
            self.assertIn("Stage 1", content)
            self.assertIn("paper_001", content)


if __name__ == "__main__":
    unittest.main()
