from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "openalex-ajg-insights" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from frontier_push.llm import audit_interest_profile, draft_interest_profile
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

    def test_descriptive_profile_requires_two_scored_concept_groups(self) -> None:
        payload = {
            "id": "work_repetition_satisfaction",
            "name": "重复劳动与满意度",
            "directionality": "descriptive",
            "target_construct": "employee satisfaction",
            "exact_phrases": ["work monotony", "job satisfaction"],
            "near_phrases": [],
            "related_terms": [],
            "exclude_keywords": [],
            "jel_codes": [],
            "natural_language": "Track the relationship between work repetition and satisfaction.",
        }

        with self.assertRaisesRegex(ValueError, "at least two"):
            validate_interest_profile_dict(payload)

        payload["required_concept_groups"] = {
            "work_repetition": ["work monotony"],
            "employee_outcomes": ["employee well-being"],
        }
        with self.assertRaisesRegex(ValueError, "exact_phrases or near_phrases"):
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
        self.assertIn("relationship/association/correlation", result["prompt"])
        self.assertIn("X与Y", result["prompt"])
        self.assertIn("descriptive", result["prompt"])
        self.assertIn("Preserve the user's research intent exactly", result["prompt"])
        self.assertIn("established construct names", result["prompt"])

    def test_relationship_intent_can_draft_descriptive_profile(self) -> None:
        yaml_response = """
id: repetitive_work_employee_wellbeing
name: 重复劳动与员工幸福度
directionality: descriptive
target_construct: employee well-being
required_concept_groups:
  work_repetition:
    - work monotony
    - repetitive work
  employee_outcomes:
    - job satisfaction
    - employee well-being
exact_phrases:
  - work monotony
  - job satisfaction
near_phrases:
  - repetitive work
  - employee well-being
related_terms:
  - job boredom
exclude_keywords: []
jel_codes:
  - J28
natural_language: >
  Track literature on the relationship between repetitive or monotonous work
  and employee well-being or job satisfaction.
"""
        with patch("frontier_push.llm._call_openai_compatible", return_value=yaml_response):
            result = draft_interest_profile(
                intent="检索重复劳动与员工幸福度/满意度的相关文献",
                llm_mode="api",
                env={"OPENAI_API_KEY": "test-key"},
                requested_directionality="descriptive",
            )

        self.assertEqual("drafted", result["status"])
        self.assertEqual("descriptive", result["profile"]["directionality"])
        self.assertIn("work monotony", result["profile"]["exact_phrases"])
        self.assertIn("job satisfaction", result["profile"]["exact_phrases"])
        self.assertEqual(2, len(result["profile"]["required_concept_groups"]))

    def test_human_directionality_mismatch_rejects_profile(self) -> None:
        yaml_response = """
id: work_monotony_effects
name: 重复劳动的影响
directionality: effects_of
target_construct: work monotony
required_concept_groups: {}
exact_phrases:
  - work monotony
near_phrases: []
related_terms: []
exclude_keywords: []
jel_codes: []
natural_language: Track outcomes of work monotony.
"""
        with patch("frontier_push.llm._call_openai_compatible", return_value=yaml_response):
            result = draft_interest_profile(
                intent="检索重复劳动与员工满意度的关系",
                llm_mode="api",
                env={"OPENAI_API_KEY": "test-key"},
                requested_directionality="descriptive",
            )

        self.assertEqual("prompt_fallback", result["status"])
        self.assertIn("directionality mismatch", result["error"])


    def test_profile_audit_without_key_is_non_blocking(self) -> None:
        profile = InterestProfile(
            id="work_monotony",
            name="Work monotony",
            directionality="effects_of",
            target_construct="employee well-being",
            exact_phrases=["work monotony"],
            near_phrases=[],
            related_terms=[],
            exclude_keywords=[],
            jel_codes=[],
            natural_language="Track effects of work monotony on employee well-being.",
        )
        result = audit_interest_profile("重复劳动与员工幸福度", profile, env={})

        self.assertEqual("unavailable", result["status"])
        self.assertEqual("missing_api_key", result["reason"])
        self.assertIn("missing_terms", result["prompt"])
        self.assertIn("Directionality audit rules", result["prompt"])
        self.assertIn("X与Y", result["prompt"])
        self.assertIn("title-style noun phrases", result["prompt"])

    def test_profile_audit_bad_yaml_is_non_blocking(self) -> None:
        profile = InterestProfile(
            id="work_monotony",
            name="Work monotony",
            directionality="descriptive",
            target_construct="employee well-being",
            exact_phrases=["work monotony"],
            near_phrases=["job satisfaction"],
            related_terms=[],
            exclude_keywords=[],
            jel_codes=[],
            natural_language="Track work monotony and employee well-being.",
        )
        with patch("frontier_push.llm._call_openai_compatible", return_value="status: pass\n- bad"):
            result = audit_interest_profile(
                "检索重复劳动与员工幸福度/满意度的相关文献",
                profile,
                llm_mode="api",
                env={"OPENAI_API_KEY": "test-key"},
            )

        self.assertEqual("unavailable", result["status"])
        self.assertEqual("llm_error", result["reason"])


if __name__ == "__main__":
    unittest.main()
