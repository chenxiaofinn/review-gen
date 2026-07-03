from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = REPO_ROOT / "backend" / "openalex-ajg-mcp" / "src" / "openalex_mcp" / "client.py"
BRIDGE_PATH = (
    REPO_ROOT
    / "skills"
    / "openalex-ajg-insights"
    / "scripts"
    / "openalex_ajg_bridge.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


client_module = load_module("openalex_client_under_test", CLIENT_PATH)
bridge_module = load_module("openalex_bridge_under_test", BRIDGE_PATH)


class FakeResponse:
    def json(self):
        return {"results": [], "meta": {"count": 0}}

    def raise_for_status(self):
        return None


class FakeAsyncClient:
    captured_params = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, params, timeout):
        FakeAsyncClient.captured_params = dict(params)
        return FakeResponse()


class OpenAlexClientApiKeyTests(unittest.TestCase):
    def test_search_works_sends_api_key_and_mailto(self) -> None:
        client = client_module.OpenAlexClient(email="user@example.com", api_key="openalex-key")

        with patch.object(client_module.httpx, "AsyncClient", FakeAsyncClient):
            asyncio.run(client.search_works("ai agents", ["1234-5678"], limit=1))

        self.assertEqual("openalex-key", FakeAsyncClient.captured_params["api_key"])
        self.assertEqual("user@example.com", FakeAsyncClient.captured_params["mailto"])


class OpenAlexBridgeEnvTests(unittest.TestCase):
    def test_make_openalex_client_reads_env_local(self) -> None:
        class CapturingClient:
            def __init__(self, email=None, api_key=None):
                self.email = email
                self.api_key = api_key

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "config" / ".env.local"
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(
                "OPENALEX_API_KEY=key-from-env-local\nOPENALEX_EMAIL=oa@example.com\n",
                encoding="utf-8",
            )

            previous = bridge_module.GLOBAL_ENV_PATH
            bridge_module.GLOBAL_ENV_PATH = env_path
            try:
                client = bridge_module.make_openalex_client(CapturingClient)
            finally:
                bridge_module.GLOBAL_ENV_PATH = previous

        self.assertEqual("key-from-env-local", client.api_key)
        self.assertEqual("oa@example.com", client.email)


class OpenAlexBridgeFrontierSourceTests(unittest.TestCase):
    def test_search_abs_parse_args_accepts_year_end(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "openalex_ajg_bridge.py",
                "search-abs",
                "--query",
                "generative AI",
                "--min-rank",
                "4*",
                "--year-start",
                "2025",
                "--year-end",
                "2026",
            ],
        ):
            args = bridge_module.parse_args()

        self.assertEqual(2025, args.year_start)
        self.assertEqual(2026, args.year_end)

    def test_filter_works_by_year_uses_inclusive_start_and_end(self) -> None:
        works = [
            {"title": "Old", "publication_year": 2024},
            {"title": "Start", "publication_year": 2025},
            {"title": "End", "publication_year": 2026},
            {"title": "Future", "publication_year": 2027},
            {"title": "Missing"},
        ]

        filtered = bridge_module.filter_works_by_year(works, year_start=2025, year_end=2026)

        self.assertEqual(["Start", "End"], [work["title"] for work in filtered])

    def test_abs_payload_has_frontier_source_provenance(self) -> None:
        payload = bridge_module.with_frontier_source_metadata({"search_type": "abs"})

        self.assertEqual("abs_ajg_4star", payload["source_id"])
        self.assertEqual("A", payload["source_tier"])
        self.assertEqual("openalex_ajg", payload["source_type"])


if __name__ == "__main__":
    unittest.main()
