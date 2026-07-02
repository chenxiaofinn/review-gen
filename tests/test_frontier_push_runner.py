from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "openalex-ajg-insights" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from frontier_push.profiles import InterestProfile
from frontier_push.runner import run_frontier_push_from_records


class FrontierRunnerTests(unittest.TestCase):
    def test_runner_writes_candidates_and_report_to_workspace(self) -> None:
        profile = InterestProfile(
            id="firm_asset_pricing_determinants",
            name="企业资产定价影响因素",
            directionality="factors_of",
            target_construct="expected stock returns",
            exact_phrases=["expected stock returns"],
            near_phrases=["return predictability"],
            related_terms=["profitability"],
            exclude_keywords=["option pricing"],
            jel_codes=["G12"],
            natural_language="Track firm-level determinants of expected stock returns.",
        )
        records_by_source = {
            "abs4_star": [
                {
                    "title": "Firm Characteristics and Expected Stock Returns",
                    "year": 2026,
                    "journal": "Journal of Finance",
                    "abstract": "Profitability explains expected stock returns.",
                    "doi": "10.1111/main",
                    "authors": ["A Author"],
                }
            ],
            "nber_wp": [
                {
                    "title": "Profitability and Return Predictability",
                    "year": 2026,
                    "journal": "NBER Working Paper",
                    "abstract": "Profitability predicts returns.",
                    "doi": "10.3386/early",
                    "authors": ["D Author"],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = run_frontier_push_from_records(
                workspace,
                profile,
                records_by_source,
                source_tiers=["A", "C"],
                run_id="2026-07-03T000000",
            )

            candidates_path = Path(result["candidates_path"])
            report_path = Path(result["report_path"])

            self.assertTrue(candidates_path.exists())
            self.assertTrue(report_path.exists())
            self.assertEqual(2, result["candidate_count"])
            self.assertIn("Firm Characteristics", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
