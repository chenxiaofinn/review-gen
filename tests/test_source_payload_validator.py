"""Tests for the source-record payload validator (ADR-0004)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "openalex-ajg-insights" / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from frontier_push.source_collection import validate_source_payload  # noqa: E402
import review_workflow  # noqa: E402


class ValidateSourcePayloadTests(unittest.TestCase):
    def test_canonical_payload_has_no_warnings(self) -> None:
        payload = {
            "source_id": "abs_ajg_4star",
            "source_tier": "A",
            "source_type": "openalex_ajg",
            "profile_id": "demo",
            "year_start": 2023,
            "year_end": 2026,
            "records": [{"title": "x", "year": 2024}],
            "diagnostics": {},
        }
        warnings = validate_source_payload(payload)
        self.assertEqual(warnings, [])

    def test_legacy_payload_emits_warnings(self) -> None:
        legacy_payload = {
            "source_id": "utd24_ft50",
            "records": [
                {"title": "Generative AI at Work", "year": 2025, "venue": "QJE"},
            ],
        }
        warnings = validate_source_payload(legacy_payload, Path("legacy.json"))
        joined = " ".join(warnings)
        for missing in ("source_tier", "source_type", "profile_id", "year_start", "year_end"):
            self.assertIn(missing, joined)

    def test_top_level_non_object_emits_warning(self) -> None:
        warnings = validate_source_payload([1, 2, 3], Path("list.json"))
        self.assertTrue(any("top-level" in w for w in warnings))

    def test_integration_with_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "09_frontier_push" / "source_records").mkdir(parents=True)
            bad_file = workspace / "09_frontier_push" / "source_records" / "bad.json"
            bad_file.write_text(
                json.dumps({"source_id": "ssrn", "records": [{"title": "x"}]}),
                encoding="utf-8",
            )
            payload = review_workflow.init_frontier_push(workspace)
        self.assertTrue(any("bad.json" in w for w in payload["source_record_warnings"]))


if __name__ == "__main__":
    unittest.main()
