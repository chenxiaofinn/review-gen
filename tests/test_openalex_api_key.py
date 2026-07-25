from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


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
    status_code = 200
    text = ""

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


class ResultResponse(FakeResponse):
    def json(self):
        return {
            "results": [{"id": "W1"}],
            "meta": {"count": 2},
        }


class ResultAsyncClient(FakeAsyncClient):
    async def get(self, url, params, timeout):
        ResultAsyncClient.captured_params = dict(params)
        return ResultResponse()


class TimeoutAsyncClient(FakeAsyncClient):
    async def get(self, url, params, timeout):
        raise client_module.httpx.ReadTimeout("timed out")


class BudgetResponse(FakeResponse):
    status_code = 429
    text = "Insufficient budget"

    def json(self):
        return {"error": "Rate limit exceeded", "message": "Insufficient budget", "retryAfter": 60}

    def raise_for_status(self):
        request = client_module.httpx.Request("GET", "https://api.openalex.org/works")
        response = client_module.httpx.Response(429, request=request, json=self.json())
        raise client_module.httpx.HTTPStatusError("429", request=request, response=response)


class BudgetAsyncClient(FakeAsyncClient):
    async def get(self, url, params, timeout):
        return BudgetResponse()


class ApiErrorResponse(BudgetResponse):
    status_code = 500
    text = "Server error"

    def json(self):
        return {"error": "Server error"}

    def raise_for_status(self):
        request = client_module.httpx.Request("GET", "https://api.openalex.org/works")
        response = client_module.httpx.Response(500, request=request, json=self.json())
        raise client_module.httpx.HTTPStatusError("500", request=request, response=response)


class ApiErrorAsyncClient(FakeAsyncClient):
    async def get(self, url, params, timeout):
        return ApiErrorResponse()


class GatewayTimeoutResponse(ApiErrorResponse):
    status_code = 504
    text = "Query took too long"

    def json(self):
        return {"error": "Query took too long"}

    def raise_for_status(self):
        request = client_module.httpx.Request("GET", "https://api.openalex.org/works")
        response = client_module.httpx.Response(504, request=request, json=self.json())
        raise client_module.httpx.HTTPStatusError("504", request=request, response=response)


class GatewayTimeoutAsyncClient(FakeAsyncClient):
    async def get(self, url, params, timeout):
        return GatewayTimeoutResponse()


class ChunkedResultAsyncClient(FakeAsyncClient):
    captured_filters = []

    async def get(self, url, params, timeout):
        self.__class__.captured_filters.append(params["filter"])
        issn_filter = params["filter"].split(",", 1)[0]
        results = [{"id": "W-target"}] if "0000-0465" in issn_filter else [{"id": "W-head"}]

        class ChunkResponse(FakeResponse):
            def json(self):
                return {"meta": {"count": len(results)}, "results": results}

        return ChunkResponse()


class OpenAlexClientApiKeyTests(unittest.TestCase):
    def test_local_issn_filter_checks_the_complete_allowed_set(self) -> None:
        works = [
            {
                "id": "W1",
                "primary_location": {
                    "source": {"issn_l": "0000-0101", "issn": ["0000-0101"]}
                },
            }
        ]
        allowed = [f"0000-{index:04d}" for index in range(1, 102)]

        filtered = client_module.filter_works_by_issns(works, allowed)

        self.assertEqual(["W1"], [work["id"] for work in filtered])

    def test_search_works_sends_api_key_and_mailto(self) -> None:
        client = client_module.OpenAlexClient(email="user@example.com", api_key="openalex-key")

        with patch.object(client_module.httpx, "AsyncClient", FakeAsyncClient):
            asyncio.run(client.search_works("ai agents", ["1234-5678"], limit=1))

        self.assertEqual("openalex-key", FakeAsyncClient.captured_params["api_key"])
        self.assertEqual("user@example.com", FakeAsyncClient.captured_params["mailto"])

    def test_search_works_sends_publication_date_filter(self) -> None:
        client = client_module.OpenAlexClient()

        with patch.object(client_module.httpx, "AsyncClient", FakeAsyncClient):
            asyncio.run(
                client.search_works(
                    "work monotony",
                    ["0021-9010"],
                    limit=1,
                    year_start=1990,
                    year_end=2000,
                )
            )

        filter_value = FakeAsyncClient.captured_params["filter"]
        self.assertIn("primary_location.source.issn:0021-9010", filter_value)
        self.assertIn("from_publication_date:1990-01-01", filter_value)
        self.assertIn("to_publication_date:2000-12-31", filter_value)

    def test_global_search_omits_issn_filter_and_reports_partial_results(self) -> None:
        client = client_module.OpenAlexClient()

        with patch.object(client_module.httpx, "AsyncClient", ResultAsyncClient):
            results, has_more = asyncio.run(
                client.search_works_global(
                    "asset pricing",
                    limit=1,
                    year_start=2024,
                    year_end=2026,
                )
            )

        self.assertEqual([{"id": "W1"}], results)
        self.assertTrue(has_more)
        self.assertNotIn("primary_location.source.issn", ResultAsyncClient.captured_params["filter"])
        self.assertEqual(1, ResultAsyncClient.captured_params["per_page"])

    def test_search_works_rejects_more_than_fifty_issns(self) -> None:
        client = client_module.OpenAlexClient()

        with self.assertRaisesRegex(ValueError, "at most 50"):
            asyncio.run(client.search_works("asset pricing", [f"{index:04d}-0000" for index in range(51)]))

    def test_complete_issn_set_is_searched_in_bounded_chunks(self) -> None:
        client = client_module.OpenAlexClient()
        ChunkedResultAsyncClient.captured_filters = []
        issns = [f"0000-{index:04d}" for index in range(466)]

        with patch.object(client_module.httpx, "AsyncClient", ChunkedResultAsyncClient):
            results, has_more = asyncio.run(
                client.search_works_for_issn_set("A-share asset pricing", issns, limit_per_chunk=100)
            )

        self.assertEqual(["W-head", "W-target"], [work["id"] for work in results])
        self.assertFalse(has_more)
        self.assertEqual(10, client.last_request_count)
        self.assertEqual(10, len(ChunkedResultAsyncClient.captured_filters))
        self.assertIn("0000-0000", ChunkedResultAsyncClient.captured_filters[0])
        self.assertIn("0000-0465", ChunkedResultAsyncClient.captured_filters[9])

    def test_query_plan_executes_in_order_and_preserves_query_provenance(self) -> None:
        client = client_module.OpenAlexClient()
        client.search_works_for_issn_set = AsyncMock(
            side_effect=[
                ([{"id": "W-shared"}, {"id": "W-exact"}], False),
                ([{"id": "W-shared"}, {"id": "W-near"}], True),
            ]
        )

        works, work_queries, rounds = asyncio.run(
            client.search_query_plan_for_issn_set(
                ['"A-share" AND "asset pricing"', '"Chinese stock market" AND "stock returns"'],
                ["1057-5219"],
            )
        )

        self.assertEqual(["W-shared", "W-exact", "W-near"], [work["id"] for work in works])
        self.assertEqual(
            ['"A-share" AND "asset pricing"', '"Chinese stock market" AND "stock returns"'],
            work_queries["W-shared"],
        )
        self.assertEqual([False, True], [round_item["has_more"] for round_item in rounds])
        self.assertEqual(2, client.search_works_for_issn_set.await_count)

    def test_budget_error_is_not_converted_to_empty_results(self) -> None:
        client = client_module.OpenAlexClient()

        with patch.object(client_module.httpx, "AsyncClient", BudgetAsyncClient):
            with self.assertRaises(client_module.OpenAlexRequestError) as caught:
                asyncio.run(client.search_works_global("asset pricing", limit=1))

        self.assertEqual("budget_exhausted", caught.exception.error_type)
        self.assertEqual(60, caught.exception.retry_after)

    def test_timeout_is_not_converted_to_empty_results(self) -> None:
        client = client_module.OpenAlexClient()

        with patch.object(client_module.httpx, "AsyncClient", TimeoutAsyncClient):
            with self.assertRaises(client_module.OpenAlexRequestError) as caught:
                asyncio.run(client.search_works_global("asset pricing", limit=1))

        self.assertEqual("timed_out", caught.exception.error_type)

    def test_server_error_is_not_converted_to_empty_results(self) -> None:
        client = client_module.OpenAlexClient()

        with patch.object(client_module.httpx, "AsyncClient", ApiErrorAsyncClient):
            with self.assertRaises(client_module.OpenAlexRequestError) as caught:
                asyncio.run(client.search_works_global("asset pricing", limit=1))

        self.assertEqual("api_error", caught.exception.error_type)

    def test_gateway_timeout_is_not_converted_to_empty_results(self) -> None:
        client = client_module.OpenAlexClient()

        with patch.object(client_module.httpx, "AsyncClient", GatewayTimeoutAsyncClient):
            with self.assertRaises(client_module.OpenAlexRequestError) as caught:
                asyncio.run(
                    client.search_works_for_issn_set(
                        "A-share AND asset pricing",
                        ["1057-5219"],
                        limit_per_chunk=100,
                    )
                )

        self.assertEqual("api_error", caught.exception.error_type)
        self.assertEqual(504, caught.exception.status_code)


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

    def test_search_abs_parse_args_accepts_profile_and_max_queries(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "openalex_ajg_bridge.py",
                "search-abs",
                "--profile",
                "profile.yml",
                "--max-queries",
                "2",
            ],
        ):
            args = bridge_module.parse_args()

        self.assertEqual("profile.yml", args.profile)
        self.assertEqual(2, args.max_queries)
        self.assertIsNone(args.query)

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
