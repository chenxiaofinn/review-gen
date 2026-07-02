from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "openalex-ajg-insights" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from frontier_push.llm import draft_interest_profile
from frontier_push.profiles import (
    InterestProfile,
    load_interest_profile,
    validate_interest_profile_dict,
    write_interest_profile,
)


class InterestProfileTests(unittest.TestCase):
    def test_interest_profile_round_trips_as_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "firm_asset_pricing_determinants.yml"
            profile = InterestProfile(
                id="firm_asset_pricing_determinants",
                name="企业资产定价影响因素",
                directionality="factors_of",
                target_construct="expected stock returns",
                exact_phrases=["cross-section of stock returns", "expected stock returns"],
                near_phrases=["asset pricing anomalies"],
                related_terms=["profitability", "investment", "momentum"],
                exclude_keywords=["option pricing", "cryptocurrency pricing"],
                jel_codes=["G12", "G14", "G30"],
                natural_language=(
                    "Track papers on how firm characteristics and corporate policies "
                    "explain expected stock returns."
                ),
            )

            write_interest_profile(path, profile)
            loaded = load_interest_profile(path)

            self.assertEqual(profile.id, loaded.id)
            self.assertEqual("factors_of", loaded.directionality)
            self.assertEqual("expected stock returns", loaded.target_construct)
            self.assertIn("momentum", loaded.related_terms)
            self.assertIn("G12", loaded.jel_codes)

    def test_profile_validation_requires_directionality_and_target(self) -> None:
        payload = {
            "id": "firm_asset_pricing_determinants",
            "name": "企业资产定价影响因素",
            "exact_phrases": ["expected stock returns"],
            "near_phrases": [],
            "related_terms": [],
            "exclude_keywords": [],
            "jel_codes": [],
            "natural_language": "Track determinants of expected stock returns.",
        }

        with self.assertRaisesRegex(ValueError, "directionality"):
            validate_interest_profile_dict(payload)

        payload["directionality"] = "factors_of"
        with self.assertRaisesRegex(ValueError, "target_construct"):
            validate_interest_profile_dict(payload)

    def test_profile_validation_rejects_unknown_directionality(self) -> None:
        payload = {
            "id": "effects_topic",
            "name": "Effects topic",
            "directionality": "causal_everything",
            "target_construct": "stock returns",
            "exact_phrases": ["stock returns"],
            "near_phrases": [],
            "related_terms": [],
            "exclude_keywords": [],
            "jel_codes": [],
            "natural_language": "Track stock return papers.",
        }

        with self.assertRaisesRegex(ValueError, "directionality"):
            validate_interest_profile_dict(payload)


class InterestProfileLlmTests(unittest.TestCase):
    def test_draft_interest_profile_without_key_returns_prompt_fallback(self) -> None:
        result = draft_interest_profile(
            intent="检索企业资产定价影响因素的相关文献",
            llm_mode="auto",
            env={},
        )

        self.assertEqual("prompt_fallback", result["status"])
        self.assertEqual("missing_api_key", result["reason"])
        self.assertIsNone(result["profile"])
        self.assertIn("InterestProfile", result["prompt"])
        self.assertIn("directionality", result["prompt"])
        self.assertIn("factors_of", result["prompt"])
        self.assertIn("检索企业资产定价影响因素的相关文献", result["prompt"])


if __name__ == "__main__":
    unittest.main()
