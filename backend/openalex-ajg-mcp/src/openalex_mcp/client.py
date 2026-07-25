from __future__ import annotations

import asyncio
import math
from typing import Any, Dict, List, Optional

import httpx


class OpenAlexRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_type: str,
        status_code: int | None = None,
        retry_after: int | None = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        self.retry_after = retry_after


def work_source_issns(work: dict[str, Any]) -> set[str]:
    source = ((work.get("primary_location") or {}).get("source") or {})
    values = source.get("issn") or []
    if isinstance(values, str):
        values = [values]
    issns = {str(value).strip() for value in values if str(value).strip()}
    issn_l = str(source.get("issn_l") or "").strip()
    if issn_l:
        issns.add(issn_l)
    return issns


def filter_works_by_issns(works: List[Dict[str, Any]], issn_list: List[str]) -> List[Dict[str, Any]]:
    allowed = {str(value).strip() for value in issn_list if str(value).strip()}
    if not allowed:
        return []
    return [work for work in works if work_source_issns(work) & allowed]


class OpenAlexClient:
    BASE_URL = "https://api.openalex.org/works"
    MAX_RESULTS = 2000
    MAX_PAGE_SIZE = 100
    MAX_FILTER_ISSNS = 50

    def __init__(self, email: Optional[str] = None, api_key: Optional[str] = None):
        self.email = email
        self.api_key = api_key
        self.last_request_count = 0

    async def _search(
        self,
        query: str,
        *,
        filters: List[str],
        limit: int,
        sort: str,
    ) -> tuple[List[Dict[str, Any]], bool]:
        effective_limit = limit if limit > 0 else self.MAX_RESULTS
        effective_limit = min(effective_limit, self.MAX_RESULTS)
        params: dict[str, Any] = {"sort": sort}
        if filters:
            params["filter"] = ",".join(filters)
        if query and query.strip() != "*":
            params["search"] = query
        if self.email:
            params["mailto"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key

        all_results: List[Dict[str, Any]] = []
        total_count = 0
        max_pages = math.ceil(effective_limit / self.MAX_PAGE_SIZE)
        self.last_request_count = 0

        try:
            async with httpx.AsyncClient() as client:
                for page in range(1, max_pages + 1):
                    remaining = effective_limit - len(all_results)
                    params["per_page"] = min(self.MAX_PAGE_SIZE, remaining)
                    params["page"] = page
                    self.last_request_count += 1
                    response = await client.get(self.BASE_URL, params=params, timeout=30.0)
                    response.raise_for_status()
                    data = response.json()
                    results = data.get("results", [])
                    total_count = int((data.get("meta") or {}).get("count") or 0)
                    if not results:
                        break
                    all_results.extend(results)
                    if len(all_results) >= effective_limit:
                        break
        except httpx.TimeoutException as exc:
            raise OpenAlexRequestError(
                "OpenAlex request timed out.",
                error_type="timed_out",
            ) from exc
        except httpx.HTTPStatusError as exc:
            response = exc.response
            status_code = response.status_code
            body = response.text
            retry_after = None
            try:
                payload = response.json()
                body = str(payload.get("message") or payload.get("error") or body)
                retry_after = payload.get("retryAfter")
            except (TypeError, ValueError):
                pass
            error_type = (
                "budget_exhausted"
                if status_code == 429 and any(token in body.lower() for token in ("budget", "credit", "fund"))
                else "api_error"
            )
            raise OpenAlexRequestError(
                f"OpenAlex API returned HTTP {status_code}: {body}",
                error_type=error_type,
                status_code=status_code,
                retry_after=retry_after,
            ) from exc
        except httpx.HTTPError as exc:
            raise OpenAlexRequestError(
                f"OpenAlex API request failed: {exc}",
                error_type="api_error",
            ) from exc

        results = all_results[:effective_limit]
        return results, total_count > len(results)

    async def search_works_global(
        self,
        query: str,
        limit: int = 100,
        sort: str = "relevance_score:desc",
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> tuple[List[Dict[str, Any]], bool]:
        filters: List[str] = []
        if year_start is not None:
            filters.append(f"from_publication_date:{int(year_start)}-01-01")
        if year_end is not None:
            filters.append(f"to_publication_date:{int(year_end)}-12-31")
        return await self._search(query, filters=filters, limit=limit, sort=sort)

    async def search_works(
        self,
        query: str,
        issn_list: List[str],
        limit: int = 0,
        sort: str = "cited_by_count:desc",
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> tuple[List[Dict[str, Any]], bool]:
        issns = list(dict.fromkeys(str(value).strip() for value in issn_list if str(value).strip()))
        if not issns:
            return [], False
        if len(issns) > self.MAX_FILTER_ISSNS:
            raise ValueError(
                f"OpenAlex ISSN filters support at most {self.MAX_FILTER_ISSNS} values; "
                "use search_works_for_issn_set for larger journal pools."
            )
        filters = [f"primary_location.source.issn:{'|'.join(issns)}"]
        if year_start is not None:
            filters.append(f"from_publication_date:{int(year_start)}-01-01")
        if year_end is not None:
            filters.append(f"to_publication_date:{int(year_end)}-12-31")
        return await self._search(query, filters=filters, limit=limit, sort=sort)

    async def search_works_for_issn_set(
        self,
        query: str,
        issn_list: List[str],
        limit_per_chunk: int = 100,
        sort: str = "relevance_score:desc",
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> tuple[List[Dict[str, Any]], bool]:
        issns = list(dict.fromkeys(str(value).strip() for value in issn_list if str(value).strip()))
        if not issns:
            self.last_request_count = 0
            return [], False

        chunks = [
            issns[start : start + self.MAX_FILTER_ISSNS]
            for start in range(0, len(issns), self.MAX_FILTER_ISSNS)
        ]
        semaphore = asyncio.Semaphore(5)
        chunk_clients = [OpenAlexClient(email=self.email, api_key=self.api_key) for _ in chunks]

        async def run_chunk(
            chunk_client: OpenAlexClient,
            chunk: List[str],
        ) -> tuple[List[Dict[str, Any]], bool]:
            async with semaphore:
                return await chunk_client.search_works(
                    query,
                    chunk,
                    limit=limit_per_chunk,
                    sort=sort,
                    year_start=year_start,
                    year_end=year_end,
                )

        outcomes = await asyncio.gather(
            *(run_chunk(chunk_client, chunk) for chunk_client, chunk in zip(chunk_clients, chunks)),
            return_exceptions=True,
        )
        self.last_request_count = sum(chunk_client.last_request_count for chunk_client in chunk_clients)
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                raise outcome

        all_results: List[Dict[str, Any]] = []
        seen: set[str] = set()
        has_more = False
        for results, chunk_has_more in outcomes:
            has_more = has_more or chunk_has_more
            for work in results:
                key = str(work.get("id") or work.get("doi") or work.get("title") or "").strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                all_results.append(work)

        return all_results, has_more

    async def search_query_plan_for_issn_set(
        self,
        queries: List[str],
        issn_list: List[str],
        limit_per_chunk: int = 100,
        sort: str = "relevance_score:desc",
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> tuple[List[Dict[str, Any]], Dict[str, List[str]], List[Dict[str, Any]]]:
        """Execute an already-approved query plan in order and merge its works."""
        if not queries:
            raise ValueError("queries must contain at least one compiled query.")

        unique_works: Dict[str, Dict[str, Any]] = {}
        work_queries: Dict[str, List[str]] = {}
        round_diagnostics: List[Dict[str, Any]] = []
        total_request_count = 0
        for index, query in enumerate(queries, start=1):
            works, has_more = await self.search_works_for_issn_set(
                query,
                issn_list,
                limit_per_chunk=limit_per_chunk,
                sort=sort,
                year_start=year_start,
                year_end=year_end,
            )
            request_count = self.last_request_count
            total_request_count += request_count
            round_diagnostics.append(
                {
                    "round": index,
                    "query": query,
                    "result_count": len(works),
                    "has_more": bool(has_more),
                    "api_calls": request_count,
                }
            )
            for work in works:
                key = str(work.get("id") or work.get("doi") or work.get("title") or "").strip()
                if not key:
                    continue
                unique_works.setdefault(key, work)
                work_queries.setdefault(key, [])
                if query not in work_queries[key]:
                    work_queries[key].append(query)

        self.last_request_count = total_request_count
        return list(unique_works.values()), work_queries, round_diagnostics
