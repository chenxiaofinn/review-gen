from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REVIEW_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "openalex-ajg-insights"
    / "scripts"
    / "review_workflow.py"
)

spec = importlib.util.spec_from_file_location("review_workflow", REVIEW_WORKFLOW_PATH)
review_workflow = importlib.util.module_from_spec(spec)
sys.modules["review_workflow"] = review_workflow
assert spec.loader is not None
spec.loader.exec_module(review_workflow)


class BuildWorkspaceEnvTests(unittest.TestCase):
    def test_build_workspace_copies_global_env_local_when_mineru_env_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            env_local = root / ".env.local"
            env_local.write_text(
                "MINERU_API_KEY=test-token\nPAPER_DOWNLOAD_EMAIL=user@example.com\n",
                encoding="utf-8",
            )

            previous = review_workflow.GLOBAL_ENV_PATH
            review_workflow.GLOBAL_ENV_PATH = env_local
            try:
                payload = review_workflow.build_workspace(workspace, "Test Topic")
            finally:
                review_workflow.GLOBAL_ENV_PATH = previous

            mineru_env = workspace / "04_fulltext" / "mineru.env"
            self.assertTrue(mineru_env.exists())
            self.assertEqual(env_local.read_text(encoding="utf-8"), mineru_env.read_text(encoding="utf-8"))
            self.assertEqual(str(mineru_env), payload["mineru_env"])
            self.assertTrue(payload["mineru_env_created_from_global"])

    def test_build_workspace_does_not_overwrite_existing_mineru_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            env_local = root / ".env.local"
            env_local.write_text("MINERU_API_KEY=global-token\n", encoding="utf-8")
            existing_env = workspace / "04_fulltext" / "mineru.env"
            existing_env.parent.mkdir(parents=True)
            existing_env.write_text("MINERU_API_KEY=workspace-token\n", encoding="utf-8")

            previous = review_workflow.GLOBAL_ENV_PATH
            review_workflow.GLOBAL_ENV_PATH = env_local
            try:
                payload = review_workflow.build_workspace(workspace, "Test Topic")
            finally:
                review_workflow.GLOBAL_ENV_PATH = previous

            self.assertEqual("MINERU_API_KEY=workspace-token\n", existing_env.read_text(encoding="utf-8"))
            self.assertEqual(str(existing_env), payload["mineru_env"])
            self.assertFalse(payload["mineru_env_created_from_global"])


if __name__ == "__main__":
    unittest.main()
