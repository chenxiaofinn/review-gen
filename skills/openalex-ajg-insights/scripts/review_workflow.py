from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import shutil
import sys
import time
import requests
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_RUNS_ROOT = Path("quality_reports") / "lit_review_runs"
DEFAULT_MINERU_BASE = "https://mineru.net"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
REVIEW_GEN_ROOT = Path(__file__).resolve().parents[3]
GLOBAL_ENV_PATH = REVIEW_GEN_ROOT / "config" / ".env.local"
PLAN_DIR_NAME = "07_plan"
LEGACY_PLAN_DIR_NAME = "07_notes"

WORKSPACE_DIRS = [
    "01_search/raw_json",
    "01_search/exports",
    "02_corpus",
    "03_screening",
    "04_fulltext/pdf_inbox",
    "04_fulltext/pdf_archive",
    "04_fulltext/download_batches",
    "05_mineru/raw_zip",
    "05_mineru/extracted",
    "05_mineru/batch_jobs",
    "06_chunks",
    PLAN_DIR_NAME,
    "08_outputs",
]

SCREENING_FIELDS = [
    "paper_key",
    "title",
    "year",
    "journal",
    "doi",
    "openalex_id",
    "matched_query",
    "search_type",
    "search_scope",
    "citations",
    "full_text_priority",
    "included_title_abstract",
    "exclusion_reason",
    "need_full_text",
    "screening_notes",
]

EVIDENCE_FIELDS = [
    "paper_key",
    "title",
    "citation",
    "research_question",
    "core_claim",
    "mechanism",
    "data_context",
    "method_design",
    "main_finding",
    "boundary_condition",
    "limitation",
    "source_level",
    "evidence_notes",
]

MANIFEST_FIELDS = [
    "paper_key",
    "title",
    "year",
    "journal",
    "doi",
    "citations",
    "full_text_priority",
    "need_full_text",
    "expected_pdf_name",
    "pdf_status",
    "pdf_path",
    "download_status",
    "download_source",
    "download_error",
    "download_batch",
    "md_status",
    "md_path",
    "mineru_batch_id",
    "mineru_error",
]


@dataclass
class Chunk:
    chunk_id: str
    paper_key: str
    title: str
    source_md: str
    heading_path: str
    section_type: str
    order: int
    word_count: int
    content: str


def slugify(text: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", text.strip())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return (cleaned or "review").lower()[:max_len].strip("-") or "review"


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_title(text: str) -> str:
    lowered = normalize_whitespace(text).lower()
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff ]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def copy_global_env_if_available(env_path: Path) -> bool:
    if env_path.exists() or not GLOBAL_ENV_PATH.exists():
        return False
    ensure_parent(env_path)
    shutil.copy2(GLOBAL_ENV_PATH, env_path)
    return True


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_workspace(topic: str | None, workspace: str | None) -> Path:
    if workspace:
        return Path(workspace).resolve()
    if not topic:
        raise ValueError("Provide either --workspace or --topic.")
    return (DEFAULT_RUNS_ROOT / slugify(topic)).resolve()


def ensure_plan_layout(workspace: Path) -> dict[str, Any]:
    canonical_dir = workspace / PLAN_DIR_NAME
    legacy_dir = workspace / LEGACY_PLAN_DIR_NAME
    canonical_dir.mkdir(parents=True, exist_ok=True)

    moved_plan = False
    moved_history = 0
    if legacy_dir.exists() and legacy_dir.is_dir():
        legacy_plan = legacy_dir / "review_plan.md"
        canonical_plan = canonical_dir / "review_plan.md"
        if legacy_plan.exists() and not canonical_plan.exists():
            ensure_parent(canonical_plan)
            shutil.move(str(legacy_plan), str(canonical_plan))
            moved_plan = True

        legacy_history = legacy_dir / "history"
        canonical_history = canonical_dir / "history"
        if legacy_history.exists() and legacy_history.is_dir():
            canonical_history.mkdir(parents=True, exist_ok=True)
            for item in sorted(legacy_history.iterdir()):
                target = canonical_history / item.name
                if target.exists():
                    continue
                shutil.move(str(item), str(target))
                moved_history += 1

    return {
        "canonical_plan_dir": str(canonical_dir),
        "legacy_plan_dir": str(legacy_dir),
        "moved_plan_file": moved_plan,
        "moved_history_entries": moved_history,
    }


def build_workspace(workspace: Path, topic: str) -> dict[str, str]:
    for rel in WORKSPACE_DIRS:
        (workspace / rel).mkdir(parents=True, exist_ok=True)
    layout_result = ensure_plan_layout(workspace)

    config_path = workspace / "review_config.json"
    if not config_path.exists():
        write_json(
            config_path,
            {
                "topic": topic,
                "created_for": "systematic literature review workflow",
                "search_queries": [
                    {
                        "label": "core concept",
                        "query": "",
                        "field": "",
                        "min_rank": "4",
                        "year_start": 2020,
                    }
                ],
                "notes": "Fill in search parameters before collecting papers.",
            },
        )

    screening_path = workspace / "03_screening" / "screening_table.csv"
    if not screening_path.exists():
        write_csv(screening_path, [], SCREENING_FIELDS)

    evidence_path = workspace / "03_screening" / "evidence_table.csv"
    if not evidence_path.exists():
        write_csv(evidence_path, [], EVIDENCE_FIELDS)

    manifest_path = workspace / "04_fulltext" / "fulltext_manifest.csv"
    if not manifest_path.exists():
        write_csv(manifest_path, [], MANIFEST_FIELDS)

    env_example = workspace / "04_fulltext" / "mineru.env.example"
    if not env_example.exists():
        write_text(
            env_example,
            "\n".join(
                [
                    "MINERU_API_KEY=",
                    f"MINERU_API_BASE_URL={DEFAULT_MINERU_BASE}",
                    "MINERU_MODEL_VERSION=vlm",
                    "MINERU_LANGUAGE=en",
                    "MINERU_ENABLE_FORMULA=true",
                    "MINERU_ENABLE_TABLE=true",
                    "MINERU_IS_OCR=false",
                    "",
                ]
            ),
        )
    env_path = workspace / "04_fulltext" / "mineru.env"
    env_created_from_global = copy_global_env_if_available(env_path)

    intake_path = workspace / "04_fulltext" / "pdf_intake_rules.txt"
    if not intake_path.exists():
        write_text(
            intake_path,
            "\n".join(
                [
                    "Place manually collected PDFs in 04_fulltext/pdf_inbox/.",
                    "Preferred naming rule: YEAR__FirstAuthor__ShortTitle.pdf",
                    "Example: 2021__Reypens__Beyond-Bricolage.pdf",
                    "Use DOI or OpenAlex metadata in fulltext_manifest.csv to map each file.",
                    "After MinerU conversion succeeds, keep the original PDF in pdf_archive/ and use the Markdown for AI reading.",
                    "",
                ]
            ),
        )

    return {
        "workspace": str(workspace),
        "topic": topic,
        "config_path": str(config_path),
        "screening_table": str(screening_path),
        "evidence_table": str(evidence_path),
        "fulltext_manifest": str(manifest_path),
        "mineru_env_example": str(env_example),
        "mineru_env": str(env_path),
        "mineru_env_created_from_global": env_created_from_global,
        "global_env_path": str(GLOBAL_ENV_PATH),
        "pdf_inbox": str(workspace / "04_fulltext" / "pdf_inbox"),
        "canonical_plan_dir": layout_result["canonical_plan_dir"],
        "legacy_plan_dir": layout_result["legacy_plan_dir"],
        "moved_legacy_plan_file": layout_result["moved_plan_file"],
        "moved_legacy_history_entries": layout_result["moved_history_entries"],
    }


def get_record_key(record: dict[str, Any]) -> str:
    doi = normalize_whitespace(record.get("doi", ""))
    if doi:
        return f"doi::{doi.lower()}"
    openalex_id = normalize_whitespace(record.get("openalex_id", ""))
    if openalex_id:
        return f"openalex::{openalex_id.lower()}"
    return f"title::{normalize_title(record.get('title', 'untitled'))}"


def cite_text(record: dict[str, Any]) -> str:
    authors = record.get("authors") or []
    lead = authors[0] if authors else "Unknown"
    year = record.get("year") or "n.d."
    title = record.get("title") or "Untitled"
    journal = record.get("journal") or "Unknown Journal"
    doi = record.get("doi") or ""
    base = f"{lead} ({year}). {title}. {journal}."
    return f"{base} DOI: {doi}" if doi else base


def flatten_payload(payload: dict[str, Any], source_file: Path) -> list[dict[str, Any]]:
    papers = payload.get("papers") or []
    search_scope_parts = []
    if payload.get("field"):
        search_scope_parts.append(payload["field"])
    if payload.get("min_rank"):
        search_scope_parts.append(payload["min_rank"])
    if payload.get("resolved_journal_name"):
        search_scope_parts.append(payload["resolved_journal_name"])
    search_scope = " | ".join(search_scope_parts)
    rows: list[dict[str, Any]] = []
    for paper in papers:
        row = {
            "paper_key": get_record_key(paper),
            "title": paper.get("title", ""),
            "year": paper.get("year", ""),
            "journal": paper.get("journal", ""),
            "authors": "; ".join(paper.get("authors") or []),
            "doi": paper.get("doi", ""),
            "openalex_id": paper.get("openalex_id", ""),
            "landing_page_url": paper.get("landing_page_url", ""),
            "citations": paper.get("citations", 0),
            "abstract": paper.get("abstract", ""),
            "abstract_word_count": paper.get("abstract_word_count", 0),
            "full_text_priority": (paper.get("full_text_priority") or {}).get("priority", ""),
            "full_text_reasons": " | ".join((paper.get("full_text_priority") or {}).get("reasons") or []),
            "matched_query": payload.get("query", ""),
            "search_type": payload.get("search_type", ""),
            "search_scope": search_scope,
            "source_json": str(source_file),
        }
        row["citation_text"] = cite_text(paper)
        rows.append(row)
    return rows


def discover_json_inputs(paths: list[str], workspace: Path) -> list[Path]:
    if paths:
        discovered: list[Path] = []
        for raw in paths:
            path = Path(raw)
            if path.is_dir():
                discovered.extend(sorted(path.rglob("*.json")))
            elif path.exists():
                discovered.append(path)
        return discovered
    return sorted((workspace / "01_search" / "raw_json").rglob("*.json"))


def merge_search_results(workspace: Path, inputs: list[str]) -> dict[str, Any]:
    files = discover_json_inputs(inputs, workspace)
    if not files:
        raise FileNotFoundError("No raw search JSON files found.")

    merged: dict[str, dict[str, Any]] = {}
    seen_sources: set[str] = set()
    for file_path in files:
        payload = read_json(file_path)
        for row in flatten_payload(payload, file_path):
            key = row["paper_key"]
            current = merged.get(key)
            if current is None:
                merged[key] = row
            else:
                current["citations"] = max(int(current.get("citations", 0)), int(row.get("citations", 0)))
                if len(row.get("abstract", "")) > len(current.get("abstract", "")):
                    current["abstract"] = row["abstract"]
                    current["abstract_word_count"] = row["abstract_word_count"]
                for field in ("doi", "openalex_id", "landing_page_url"):
                    if not current.get(field) and row.get(field):
                        current[field] = row[field]
                queries = set(filter(None, [current.get("matched_query", ""), row.get("matched_query", "")]))
                current["matched_query"] = " | ".join(sorted(queries))
                scopes = set(filter(None, [current.get("search_scope", ""), row.get("search_scope", "")]))
                current["search_scope"] = " | ".join(sorted(scopes))
                priorities = [current.get("full_text_priority", ""), row.get("full_text_priority", "")]
                current["full_text_priority"] = next((item for item in ("high", "medium", "low") if item in priorities), "")
                reasons = set(filter(None, [current.get("full_text_reasons", ""), row.get("full_text_reasons", "")]))
                current["full_text_reasons"] = " | ".join(sorted(reasons))
            seen_sources.add(str(file_path))

    rows = sorted(
        merged.values(),
        key=lambda item: (-int(item.get("citations", 0)), str(item.get("year", "")), item["title"]),
    )
    write_jsonl(workspace / "02_corpus" / "master_corpus.jsonl", rows)
    write_csv(
        workspace / "02_corpus" / "master_corpus.csv",
        rows,
        [
            "paper_key",
            "title",
            "year",
            "journal",
            "authors",
            "doi",
            "openalex_id",
            "citations",
            "matched_query",
            "search_type",
            "search_scope",
            "full_text_priority",
            "landing_page_url",
            "abstract",
            "full_text_reasons",
            "source_json",
        ],
    )

    screening_existing = {row["paper_key"]: row for row in read_csv_rows(workspace / "03_screening" / "screening_table.csv") if row.get("paper_key")}
    screening_rows: list[dict[str, Any]] = []
    for row in rows:
        existing = screening_existing.get(row["paper_key"], {})
        screening_rows.append(
            {
                "paper_key": row["paper_key"],
                "title": row["title"],
                "year": row["year"],
                "journal": row["journal"],
                "doi": row["doi"],
                "openalex_id": row["openalex_id"],
                "matched_query": row["matched_query"],
                "search_type": row["search_type"],
                "search_scope": row["search_scope"],
                "citations": row["citations"],
                "full_text_priority": row["full_text_priority"],
                "included_title_abstract": existing.get("included_title_abstract", ""),
                "exclusion_reason": existing.get("exclusion_reason", ""),
                "need_full_text": existing.get("need_full_text", ""),
                "screening_notes": existing.get("screening_notes", ""),
            }
        )
    write_csv(workspace / "03_screening" / "screening_table.csv", screening_rows, SCREENING_FIELDS)

    return {
        "workspace": str(workspace),
        "raw_files": len(files),
        "unique_papers": len(rows),
        "source_files": sorted(seen_sources),
        "master_corpus_jsonl": str(workspace / "02_corpus" / "master_corpus.jsonl"),
        "screening_table": str(workspace / "03_screening" / "screening_table.csv"),
    }


def expected_pdf_name(record: dict[str, Any]) -> str:
    author_field = record.get("authors", "")
    first_author = normalize_whitespace(author_field.split(";")[0] if author_field else "") or "Unknown"
    title_slug = slugify(record.get("title", ""), max_len=48).replace("-", "_")
    year = str(record.get("year") or "n.d.")
    author_slug = re.sub(r"[^A-Za-z0-9]+", "", first_author)[:24] or "Unknown"
    return f"{year}__{author_slug}__{title_slug}.pdf"


def prepare_fulltext_manifest(workspace: Path, min_priority: str, require_included: bool) -> dict[str, Any]:
    priority_order = {"low": 1, "medium": 2, "high": 3}
    threshold = priority_order[min_priority]
    corpus_rows = read_jsonl(workspace / "02_corpus" / "master_corpus.jsonl")
    if not corpus_rows:
        raise FileNotFoundError("master_corpus.jsonl is missing. Run merge-search-results first.")

    screening = {row["paper_key"]: row for row in read_csv_rows(workspace / "03_screening" / "screening_table.csv") if row.get("paper_key")}
    existing = {row["paper_key"]: row for row in read_csv_rows(workspace / "04_fulltext" / "fulltext_manifest.csv") if row.get("paper_key")}

    inbox = workspace / "04_fulltext" / "pdf_inbox"
    archive = workspace / "04_fulltext" / "pdf_archive"
    extracted = workspace / "05_mineru" / "extracted"

    manifest_rows: list[dict[str, Any]] = []
    for row in corpus_rows:
        screen = screening.get(row["paper_key"], {})
        priority = row.get("full_text_priority", "low")
        score = priority_order.get(priority, 0)
        if score < threshold:
            continue
        if require_included and screen.get("included_title_abstract", "").lower() not in {"yes", "y", "true", "1"}:
            continue

        need_full_text = screen.get("need_full_text", "")
        if not need_full_text:
            need_full_text = "yes" if score >= threshold else ""

        file_name = expected_pdf_name(row)
        inbox_path = inbox / file_name
        archive_path = archive / file_name
        existing_row = existing.get(row["paper_key"], {})
        pdf_path = inbox_path if inbox_path.exists() else archive_path if archive_path.exists() else Path(existing_row.get("pdf_path", "")) if existing_row.get("pdf_path") else None
        md_dir = extracted / Path(file_name).stem
        md_candidates = sorted(md_dir.rglob("*.md")) if md_dir.exists() else []

        manifest_rows.append(
            {
                "paper_key": row["paper_key"],
                "title": row["title"],
                "year": row["year"],
                "journal": row["journal"],
                "doi": row["doi"],
                "citations": row["citations"],
                "full_text_priority": priority,
                "need_full_text": need_full_text,
                "expected_pdf_name": file_name,
                "pdf_status": "ready" if pdf_path and pdf_path.exists() else "missing",
                "pdf_path": str(pdf_path) if pdf_path else "",
                "download_status": existing_row.get("download_status", ""),
                "download_source": existing_row.get("download_source", ""),
                "download_error": existing_row.get("download_error", ""),
                "download_batch": existing_row.get("download_batch", ""),
                "md_status": "ready" if md_candidates else existing_row.get("md_status", ""),
                "md_path": str(md_candidates[0]) if md_candidates else existing_row.get("md_path", ""),
                "mineru_batch_id": existing_row.get("mineru_batch_id", ""),
                "mineru_error": existing_row.get("mineru_error", ""),
            }
        )

    write_csv(workspace / "04_fulltext" / "fulltext_manifest.csv", manifest_rows, MANIFEST_FIELDS)
    return {
        "workspace": str(workspace),
        "manifest_path": str(workspace / "04_fulltext" / "fulltext_manifest.csv"),
        "papers_needing_full_text": len(manifest_rows),
        "missing_pdfs": sum(1 for row in manifest_rows if row["pdf_status"] == "missing"),
    }


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Env file not found: {path}")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def http_json(method: str, url: str, headers: dict[str, str], payload: Any | None = None) -> Any:
    response = requests.request(method, url, headers=dict(headers), json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def http_download(url: str, destination: Path) -> None:
    ensure_parent(destination)
    with requests.get(url, timeout=180) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            handle.write(response.content)


def http_put_file(url: str, source: Path) -> int:
    with source.open("rb") as handle:
        response = requests.put(url, data=handle, timeout=300)
    response.raise_for_status()
    return response.status_code


def save_batch_snapshot(path: Path, payload: Any) -> None:
    write_json(path, payload)


def resolve_mineru_token(env: dict[str, str]) -> str:
    token = env.get("MINERU_API_KEY", "").strip()
    if token:
        return token

    raise ValueError("Provide MINERU_API_KEY in the env file. Access-key/secret-key auth is no longer supported.")


def authorization_header_value(token: str) -> str:
    stripped = token.strip()
    return stripped if stripped.lower().startswith("bearer ") else f"Bearer {stripped}"


def convert_pdfs_with_mineru(
    workspace: Path,
    env_path: Path,
    batch_size: int,
    poll_seconds: int,
    max_wait_minutes: int,
    only_missing_md: bool,
) -> dict[str, Any]:
    env = load_env_file(env_path)
    token = resolve_mineru_token(env)

    base_url = env.get("MINERU_API_BASE_URL", DEFAULT_MINERU_BASE).rstrip("/")
    model_version = env.get("MINERU_MODEL_VERSION", "vlm")
    headers = {"Authorization": authorization_header_value(token)}
    manifest_path = workspace / "04_fulltext" / "fulltext_manifest.csv"
    manifest_rows = read_csv_rows(manifest_path)
    if not manifest_rows:
        raise FileNotFoundError("fulltext_manifest.csv is empty. Run prepare-fulltext-manifest first.")

    candidates: list[dict[str, str]] = []
    for row in manifest_rows:
        pdf_path = Path(row["pdf_path"]) if row.get("pdf_path") else workspace / "04_fulltext" / "pdf_inbox" / row["expected_pdf_name"]
        if not pdf_path.exists():
            continue
        if only_missing_md and row.get("md_status") == "ready" and row.get("md_path"):
            continue
        row["pdf_path"] = str(pdf_path)
        candidates.append(row)

    if not candidates:
        return {"workspace": str(workspace), "submitted": 0, "message": "No PDFs need conversion."}

    raw_zip_dir = workspace / "05_mineru" / "raw_zip"
    extract_root = workspace / "05_mineru" / "extracted"
    batch_root = workspace / "05_mineru" / "batch_jobs"
    submitted_batches: list[str] = []
    downloaded = 0
    failed = 0

    for offset in range(0, len(candidates), batch_size):
        batch_rows = candidates[offset : offset + batch_size]
        payload = {
            "files": [{"name": Path(row["pdf_path"]).name, "data_id": row["paper_key"]} for row in batch_rows],
            "model_version": model_version,
            "language": env.get("MINERU_LANGUAGE", "en"),
            "enable_formula": parse_bool(env.get("MINERU_ENABLE_FORMULA", "true"), True),
            "enable_table": parse_bool(env.get("MINERU_ENABLE_TABLE", "true"), True),
            "is_ocr": parse_bool(env.get("MINERU_IS_OCR", "false"), False),
        }
        response = http_json("POST", f"{base_url}/api/v4/file-urls/batch", headers, payload)
        if response.get("code") != 0:
            raise RuntimeError(f"MinerU upload-url request failed: {response}")

        batch_id = response["data"]["batch_id"]
        uploaded_urls = response["data"]["file_urls"]
        submitted_batches.append(batch_id)
        save_batch_snapshot(batch_root / f"{batch_id}_request.json", response)

        for row, upload_url in zip(batch_rows, uploaded_urls):
            status = http_put_file(upload_url, Path(row["pdf_path"]))
            if status not in {200, 201}:
                raise RuntimeError(f"Upload failed for {row['pdf_path']} with status {status}")
            row["mineru_batch_id"] = batch_id
            row["pdf_status"] = "uploaded"

        deadline = time.time() + max_wait_minutes * 60
        done_map: dict[str, dict[str, Any]] = {}
        while time.time() < deadline:
            result = http_json("GET", f"{base_url}/api/v4/extract-results/batch/{batch_id}", headers)
            save_batch_snapshot(batch_root / f"{batch_id}_status.json", result)
            extract_results = result.get("data", {}).get("extract_result", [])
            states = {item.get("state", "") for item in extract_results}
            for item in extract_results:
                done_map[item.get("file_name", "")] = item
            if states and states.issubset({"done", "failed"}):
                break
            time.sleep(poll_seconds)

        for row in batch_rows:
            file_name = Path(row["pdf_path"]).name
            item = done_map.get(file_name, {})
            state = item.get("state", "")
            row["mineru_batch_id"] = batch_id
            if state == "done" and item.get("full_zip_url"):
                zip_path = raw_zip_dir / f"{Path(file_name).stem}.zip"
                http_download(item["full_zip_url"], zip_path)
                extract_dir = extract_root / Path(file_name).stem
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zip_path, "r") as archive:
                    archive.extractall(extract_dir)
                md_files = sorted(extract_dir.rglob("*.md"))
                row["md_status"] = "ready" if md_files else "missing_md"
                row["md_path"] = str(md_files[0]) if md_files else ""
                row["mineru_error"] = ""
                archived_pdf = workspace / "04_fulltext" / "pdf_archive" / file_name
                ensure_parent(archived_pdf)
                if Path(row["pdf_path"]).resolve() != archived_pdf.resolve():
                    shutil.copy2(row["pdf_path"], archived_pdf)
                row["pdf_status"] = "archived"
                row["pdf_path"] = str(archived_pdf)
                downloaded += 1
            else:
                row["md_status"] = "failed"
                row["mineru_error"] = item.get("err_msg", "Timed out while waiting for MinerU.")
                failed += 1

    write_csv(manifest_path, manifest_rows, MANIFEST_FIELDS)
    return {
        "workspace": str(workspace),
        "submitted_batches": submitted_batches,
        "submitted": len(candidates),
        "downloaded": downloaded,
        "failed": failed,
        "manifest_path": str(manifest_path),
    }


def classify_section(heading_path: str) -> str:
    lowered = heading_path.lower()
    if any(word in lowered for word in ["abstract", "摘要"]):
        return "abstract"
    if any(word in lowered for word in ["introduction", "background", "引言"]):
        return "introduction"
    if any(word in lowered for word in ["theory", "concept", "hypoth", "framework", "literature"]):
        return "theory"
    if any(word in lowered for word in ["data", "sample", "method", "design", "measure", "empirical"]):
        return "methods"
    if any(word in lowered for word in ["result", "finding", "analysis", "estimate"]):
        return "results"
    if any(word in lowered for word in ["discussion", "implication", "conclusion", "limitation"]):
        return "discussion"
    if any(word in lowered for word in ["reference", "bibliography"]):
        return "references"
    if any(word in lowered for word in ["appendix", "supplement"]):
        return "appendix"
    return "body"


def parse_markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading_stack: list[str] = []
    current_lines: list[str] = []
    current_heading = "root"

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            level = len(match.group(1))
            heading = normalize_whitespace(match.group(2))
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading)
            current_heading = " > ".join(heading_stack)
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))
    return sections


def paragraph_chunks(text: str, target_words: int, overlap_words: int) -> list[str]:
    paragraphs = [normalize_whitespace(part) for part in re.split(r"\n\s*\n", text) if normalize_whitespace(part)]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for para in paragraphs:
        words = len(para.split())
        if current and current_words + words > target_words:
            chunk_text = "\n\n".join(current)
            chunks.append(chunk_text)
            if overlap_words > 0:
                overlap: list[str] = []
                overlap_count = 0
                for existing in reversed(current):
                    overlap.insert(0, existing)
                    overlap_count += len(existing.split())
                    if overlap_count >= overlap_words:
                        break
                current = overlap
                current_words = sum(len(item.split()) for item in current)
            else:
                current = []
                current_words = 0
        current.append(para)
        current_words += words
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def chunk_markdown(workspace: Path, target_words: int, overlap_words: int) -> dict[str, Any]:
    extract_root = workspace / "05_mineru" / "extracted"
    md_files = [path for path in extract_root.rglob("*.md") if "__MACOSX" not in str(path)]
    if not md_files:
        raise FileNotFoundError("No Markdown files found under 05_mineru/extracted.")

    corpus = read_jsonl(workspace / "02_corpus" / "master_corpus.jsonl")
    title_lookup = {expected_pdf_name(row).replace(".pdf", ""): row for row in corpus}

    chunks: list[dict[str, Any]] = []
    for md_file in sorted(md_files):
        paper_folder = md_file.parent.name
        row = title_lookup.get(paper_folder, {})
        paper_key = row.get("paper_key", paper_folder)
        title = row.get("title", paper_folder)
        text = md_file.read_text(encoding="utf-8", errors="ignore")
        sections = parse_markdown_sections(text)
        order = 0
        for heading_path, section_text in sections:
            if not section_text or classify_section(heading_path) in {"references"}:
                continue
            for content in paragraph_chunks(section_text, target_words, overlap_words):
                order += 1
                chunk = Chunk(
                    chunk_id=f"{paper_key}::{order}",
                    paper_key=paper_key,
                    title=title,
                    source_md=str(md_file),
                    heading_path=heading_path,
                    section_type=classify_section(heading_path),
                    order=order,
                    word_count=len(content.split()),
                    content=content,
                )
                chunks.append(chunk.__dict__)

    write_jsonl(workspace / "06_chunks" / "chunk_index.jsonl", chunks)
    return {
        "workspace": str(workspace),
        "markdown_files": len(md_files),
        "chunks": len(chunks),
        "chunk_index": str(workspace / "06_chunks" / "chunk_index.jsonl"),
    }
def tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", (text or "").lower()) if token not in {"the", "and", "for", "with", "that", "this"}]


def score_chunk(chunk: dict[str, Any], query_tokens: list[str], purpose: str) -> float:
    section_boosts = {
        "viewpoint": {"abstract": 4, "introduction": 3, "theory": 3, "discussion": 2},
        "definition": {"abstract": 3, "introduction": 3, "theory": 4},
        "method": {"methods": 5, "results": 2, "appendix": 3},
        "finding": {"results": 5, "discussion": 3, "abstract": 2},
    }
    weights = section_boosts.get(purpose, section_boosts["viewpoint"])
    content = f"{chunk.get('title', '')} {chunk.get('heading_path', '')} {chunk.get('content', '')}".lower()
    score = 0.0
    for token in query_tokens:
        occurrences = content.count(token)
        if occurrences:
            score += occurrences * 2
            if token in chunk.get("heading_path", "").lower():
                score += 2
    score += weights.get(chunk.get("section_type", ""), 0)
    if len(chunk.get("content", "").split()) < 120:
        score += 0.5
    return score


def retrieve_chunks(workspace: Path, query: str, purpose: str, top_k: int, include_neighbors: bool) -> dict[str, Any]:
    chunk_path = workspace / "06_chunks" / "chunk_index.jsonl"
    chunks = read_jsonl(chunk_path)
    if not chunks:
        raise FileNotFoundError("chunk_index.jsonl is missing. Run chunk-markdown first.")

    query_tokens = tokenize(query)
    scored = [(score_chunk(chunk, query_tokens, purpose), chunk) for chunk in chunks]
    scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: (-item[0], item[1]["paper_key"], item[1]["order"]))
    top = scored[:top_k]

    if include_neighbors:
        wanted = {(item[1]["paper_key"], item[1]["order"]) for item in top}
        extra: list[dict[str, Any]] = []
        chunk_lookup = {(chunk["paper_key"], chunk["order"]): chunk for chunk in chunks}
        for _, chunk in top:
            for neighbor_order in (chunk["order"] - 1, chunk["order"] + 1):
                neighbor = chunk_lookup.get((chunk["paper_key"], neighbor_order))
                if neighbor and (neighbor["paper_key"], neighbor["order"]) not in wanted:
                    extra.append(neighbor)
                    wanted.add((neighbor["paper_key"], neighbor["order"]))
        top_chunks = [item[1] for item in top] + extra
    else:
        top_chunks = [item[1] for item in top]

    return {
        "workspace": str(workspace),
        "query": query,
        "purpose": purpose,
        "returned": len(top_chunks),
        "chunks": top_chunks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    if "chunks" in payload:
        lines = [
            f"# Chunk Retrieval: {payload['query']}",
            "",
            f"- Purpose: {payload['purpose']}",
            f"- Returned: {payload['returned']}",
            "",
        ]
        for chunk in payload["chunks"]:
            lines.extend(
                [
                    f"## {chunk['title']}",
                    f"- Section: {chunk['heading_path']}",
                    f"- Type: {chunk['section_type']}",
                    f"- Source: {chunk['source_md']}",
                    "",
                    chunk["content"],
                    "",
                ]
            )
        return "\n".join(lines)
    return json.dumps(payload, indent=2, ensure_ascii=False)


def emit(payload: dict[str, Any], output_format: str) -> None:
    rendered = render_markdown(payload) if output_format == "markdown" else json.dumps(payload, indent=2, ensure_ascii=False)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")




def init_frontier_push(workspace: Path) -> dict[str, Any]:
    from frontier_push.sources import write_default_source_catalog
    from frontier_push.source_collection import validate_source_payload

    root = workspace / "09_frontier_push"
    for rel in ["profiles", "runs", "reports", "deep_reads", "source_records"]:
        (root / rel).mkdir(parents=True, exist_ok=True)

    sources_path = root / "sources.yml"
    if not sources_path.exists():
        write_default_source_catalog(sources_path)

    warnings: list[str] = []
    records_dir = root / "source_records"
    if records_dir.exists():
        for record_path in sorted(records_dir.glob("*.json")):
            try:
                payload = json.loads(record_path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError as exc:
                warnings.append(f"{record_path}: invalid JSON ({exc})")
                continue
            warnings.extend(validate_source_payload(payload, record_path))

    return {
        "workspace": str(workspace),
        "frontier_root": str(root),
        "sources_path": str(sources_path),
        "profiles_dir": str(root / "profiles"),
        "runs_dir": str(root / "runs"),
        "reports_dir": str(root / "reports"),
        "deep_reads_dir": str(root / "deep_reads"),
        "source_records_dir": str(records_dir),
        "source_record_warnings": warnings,
    }


def draft_interest_profile(workspace: Path, intent: str, llm_mode: str) -> dict[str, Any]:
    from frontier_push.llm import draft_interest_profile as draft_profile
    from frontier_push.profiles import InterestProfile, profile_path, write_interest_profile

    init_frontier_push(workspace)
    result = draft_profile(intent=intent, llm_mode=llm_mode, env=load_env_file(GLOBAL_ENV_PATH))
    profile_payload = result.get("profile")
    if profile_payload:
        profile = InterestProfile.from_dict(profile_payload)
        output_path = profile_path(workspace, profile.id)
        write_interest_profile(output_path, profile)
        result["profile_path"] = str(output_path)
    return result


def _frontier_source_id_from_payload(data: dict[str, Any], path: Path) -> str:
    from frontier_push.source_collection import canonical_source_id

    raw_source_id = data.get("source_id") or data.get("id")
    if not raw_source_id and data.get("search_type") == "abs":
        raw_source_id = "abs_ajg_4star"
    return canonical_source_id(str(raw_source_id or path.stem))


def _load_frontier_records(input_paths: list[str]) -> dict[str, list[dict[str, Any]]]:
    records_by_source: dict[str, list[dict[str, Any]]] = {}
    for raw_path in input_paths:
        path = Path(raw_path)
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            source_id = _frontier_source_id_from_payload(data, path)
            records = data.get("records") or data.get("papers") or []
            if not isinstance(records, list):
                raise ValueError(f"Frontier input records must be a list: {path}")
            records_by_source.setdefault(source_id, []).extend(records)
        elif isinstance(data, list):
            records_by_source.setdefault(path.stem, []).extend(data)
        else:
            raise ValueError(f"Unsupported frontier input JSON shape: {path}")
    return records_by_source


def run_frontier_push(
    workspace: Path,
    profile_id: str,
    source_tiers: list[str],
    input_paths: list[str],
    run_id: str | None = None,
    year_start: int | None = None,
    year_end: int | None = None,
) -> dict[str, Any]:
    from frontier_push.profiles import load_interest_profile, profile_path
    from frontier_push.runner import run_frontier_push_from_records

    init_frontier_push(workspace)
    if not input_paths:
        default_dir = workspace / "09_frontier_push" / "source_records"
        input_paths = [str(path) for path in sorted(default_dir.glob("*.json"))]
    if not input_paths:
        raise ValueError("Provide --input JSON files or place records in 09_frontier_push/source_records/.")

    profile = load_interest_profile(profile_path(workspace, profile_id))
    records_by_source = _load_frontier_records(input_paths)
    return run_frontier_push_from_records(
        workspace=workspace,
        profile=profile,
        records_by_source=records_by_source,
        source_tiers=source_tiers,
        run_id=run_id,
        year_start=year_start,
        year_end=year_end,
    )


def _parse_csv_arg(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


async def _collect_frontier_sources_async(
    workspace: Path,
    profile_id: str,
    source_ids: list[str],
    year_start: int,
    year_end: int,
    limit_per_query: int,
    max_queries: int,
) -> dict[str, Any]:
    from openalex_ajg_bridge import DEFAULT_REPO_ROOT, bootstrap_repo, make_openalex_client, tokenize_query, work_to_record
    from frontier_push.profiles import load_interest_profile, profile_path
    from frontier_push.source_collection import (
        build_profile_queries,
        build_source_payload,
        chunked,
        deduplicate_records,
        filter_records_by_year,
        resolve_tier_a_journals,
        write_source_payload,
    )

    init_frontier_push(workspace)
    profile = load_interest_profile(profile_path(workspace, profile_id))
    queries = build_profile_queries(profile, max_queries=max_queries)
    modules = bootstrap_repo(DEFAULT_REPO_ROOT)
    resolved_sources = resolve_tier_a_journals(modules["data_csv"], source_ids)
    client = make_openalex_client(modules["OpenAlexClient"])

    output_dir = workspace / "09_frontier_push" / "source_records"
    outputs = []
    for source_id, resolved in resolved_sources.items():
        issns = [journal.issn for journal in resolved.journals]
        collected_records: list[dict[str, Any]] = []
        api_calls = 0
        has_more = False

        for query in queries:
            query_tokens = tokenize_query(query)
            for issn_chunk in chunked(issns, 50):
                api_calls += 1
                works, chunk_has_more = await client.search_works(
                    query,
                    issn_chunk,
                    limit=limit_per_query,
                    sort="publication_date:desc",
                )
                has_more = has_more or bool(chunk_has_more)
                for work in works:
                    record = work_to_record(work, modules["reconstruct_abstract"], query_tokens)
                    record["source_query"] = query
                    collected_records.append(record)

        deduped = deduplicate_records(collected_records)
        filtered_records, year_stats = filter_records_by_year(deduped, year_start=year_start, year_end=year_end)
        diagnostics = {
            "query_count": len(queries),
            "api_calls": api_calls,
            "journal_count": len(resolved.journals),
            "issn_count": len(issns),
            "unresolved_journals": resolved.unresolved_journals,
            "raw_records": len(collected_records),
            "deduped_records": len(deduped),
            "has_more": has_more,
            "year_filter": year_stats,
        }
        payload = build_source_payload(
            source_id=source_id,
            source_tier=resolved.source_tier,
            source_type=resolved.source_type,
            profile_id=profile.id,
            year_start=year_start,
            year_end=year_end,
            records=filtered_records,
            diagnostics=diagnostics,
        )
        output_path = output_dir / f"{source_id}_{profile.id}_{year_start}_{year_end}.json"
        write_source_payload(output_path, payload)
        outputs.append({
            "source_id": source_id,
            "output_path": str(output_path),
            "record_count": len(filtered_records),
            "diagnostics": diagnostics,
        })

    return {
        "workspace": str(workspace),
        "profile_id": profile_id,
        "source_ids": list(resolved_sources.keys()),
        "year_start": year_start,
        "year_end": year_end,
        "outputs": outputs,
    }


def collect_frontier_sources(
    workspace: Path,
    profile_id: str,
    source_ids: list[str],
    year_start: int,
    year_end: int,
    limit_per_query: int = 200,
    max_queries: int = 12,
) -> dict[str, Any]:
    return asyncio.run(
        _collect_frontier_sources_async(
            workspace=workspace,
            profile_id=profile_id,
            source_ids=source_ids,
            year_start=year_start,
            year_end=year_end,
            limit_per_query=limit_per_query,
            max_queries=max_queries,
        )
    )


def promote_frontier_candidates(workspace: Path, run_id: str, candidate_ids: list[str]) -> dict[str, Any]:
    from frontier_push.promotion import promote_frontier_candidates as promote

    return promote(workspace, run_id, candidate_ids)


def _find_paper_for_decomposition(workspace: Path, paper_key: str) -> dict[str, Any]:
    for row in read_jsonl(workspace / "02_corpus" / "master_corpus.jsonl"):
        if row.get("paper_key") == paper_key:
            return {
                "title": row.get("title"),
                "authors": [],
                "year": row.get("year"),
                "venue": row.get("journal"),
                "abstract": row.get("abstract"),
                "doi": row.get("doi"),
                "openalex_id": row.get("openalex_id"),
            }
    frontier_runs = workspace / "09_frontier_push" / "runs"
    if frontier_runs.exists():
        from frontier_push.candidates import load_candidates_jsonl

        for candidates_path in sorted(frontier_runs.glob("*/candidates.jsonl")):
            for candidate in load_candidates_jsonl(candidates_path):
                if candidate.candidate_id == paper_key:
                    return candidate.to_dict()
    raise ValueError(f"Paper key not found in corpus or frontier candidates: {paper_key}")


def _load_excerpt_files(paths: list[str]) -> list[str]:
    return [Path(path).read_text(encoding="utf-8-sig") for path in paths]


def decompose_frontier_paper(
    workspace: Path,
    paper_key: str,
    llm_mode: str,
    excerpt_paths: list[str],
) -> dict[str, Any]:
    from frontier_push.decomposition import decompose_paper

    init_frontier_push(workspace)
    paper = _find_paper_for_decomposition(workspace, paper_key)
    excerpts = _load_excerpt_files(excerpt_paths)
    return decompose_paper(
        workspace=workspace,
        paper_key=paper_key,
        paper=paper,
        excerpts=excerpts,
        llm_mode=llm_mode,
        env=load_env_file(GLOBAL_ENV_PATH),
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Systematic literature review workflow helper.")
    parser.add_argument("--topic", help="Review topic. Used to derive the workspace if --workspace is omitted.")
    parser.add_argument("--workspace", help="Existing review workspace path.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser("init-workspace", help="Create a systematic review workspace.")
    init_cmd.add_argument("--topic", required=True, help="Topic label for the workspace.")

    merge_cmd = subparsers.add_parser("merge-search-results", help="Merge saved OpenAlex search JSON files.")
    merge_cmd.add_argument("--input", nargs="*", default=[], help="JSON files or folders. Defaults to 01_search/raw_json.")

    manifest_cmd = subparsers.add_parser("prepare-fulltext-manifest", help="Create a shortlist for full-text collection.")
    manifest_cmd.add_argument("--min-priority", choices=("low", "medium", "high"), default="medium")
    manifest_cmd.add_argument("--require-included", action="store_true", help="Only include title/abstract-screened papers marked as included.")

    convert_cmd = subparsers.add_parser("convert-pdfs-with-mineru", help="Upload PDFs to MinerU and extract Markdown.")
    convert_cmd.add_argument("--env-path", required=True, help="Path to the MinerU env file.")
    convert_cmd.add_argument("--batch-size", type=int, default=20)
    convert_cmd.add_argument("--poll-seconds", type=int, default=20)
    convert_cmd.add_argument("--max-wait-minutes", type=int, default=30)
    convert_cmd.add_argument("--all-pdfs", action="store_true", help="Convert PDFs even if Markdown already exists.")

    chunk_cmd = subparsers.add_parser("chunk-markdown", help="Chunk MinerU Markdown into retrieval units.")
    chunk_cmd.add_argument("--target-words", type=int, default=450)
    chunk_cmd.add_argument("--overlap-words", type=int, default=80)

    retrieve_cmd = subparsers.add_parser("retrieve-chunks", help="Retrieve the most relevant markdown chunks for a question.")
    retrieve_cmd.add_argument("--query", required=True)
    retrieve_cmd.add_argument("--purpose", choices=("viewpoint", "definition", "method", "finding"), default="viewpoint")
    retrieve_cmd.add_argument("--top-k", type=int, default=8)
    retrieve_cmd.add_argument("--include-neighbors", action="store_true")


    subparsers.add_parser("init-frontier-push", help="Create the optional frontier-push workspace layout.")

    draft_profile_cmd = subparsers.add_parser("draft-interest-profile", help="Draft a reviewable InterestProfile from Chinese intent.")
    draft_profile_cmd.add_argument("--intent", required=True)
    draft_profile_cmd.add_argument("--llm-mode", choices=("auto", "api", "prompt-only"), default="auto")

    run_frontier_cmd = subparsers.add_parser("run-frontier-push", help="Generate frontier candidates and a push report.")
    run_frontier_cmd.add_argument("--profile", required=True, help="InterestProfile id.")
    run_frontier_cmd.add_argument("--source-tiers", default="A,C", help="Comma-separated source tiers, for example A,C.")
    run_frontier_cmd.add_argument("--input", nargs="*", default=[], help="Frontier source JSON files. Defaults to 09_frontier_push/source_records/*.json.")
    run_frontier_cmd.add_argument("--run-id", help="Optional stable run id for repeatable output paths.")
    run_frontier_cmd.add_argument("--year-start", type=int, help="Optional inclusive start year for source records.")
    run_frontier_cmd.add_argument("--year-end", type=int, help="Optional inclusive end year for source records.")

    collect_frontier_cmd = subparsers.add_parser("collect-frontier-sources", help="Collect Tier A frontier source records into source_records.")
    collect_frontier_cmd.add_argument("--profile", required=True, help="InterestProfile id.")
    collect_frontier_cmd.add_argument("--source-ids", default="abs_ajg_4star,ft50,utd24", help="Comma-separated source ids. Supported: abs_ajg_4star,ft50,utd24.")
    collect_frontier_cmd.add_argument("--year-start", type=int, required=True)
    collect_frontier_cmd.add_argument("--year-end", type=int, required=True)
    collect_frontier_cmd.add_argument("--limit-per-query", type=int, default=200)
    collect_frontier_cmd.add_argument("--max-queries", type=int, default=12)

    promote_frontier_cmd = subparsers.add_parser("promote-frontier-candidates", help="Promote selected frontier candidates into raw search JSON.")
    promote_frontier_cmd.add_argument("--run-id", required=True)
    promote_frontier_cmd.add_argument("--candidate-ids", nargs="+", required=True)

    decompose_cmd = subparsers.add_parser("decompose-paper", help="Create a two-stage paper decomposition prompt or LLM draft.")
    decompose_cmd.add_argument("--paper-key", required=True)
    decompose_cmd.add_argument("--llm-mode", choices=("auto", "api", "prompt-only"), default="auto")
    decompose_cmd.add_argument("--excerpt-file", nargs="*", default=[], help="Optional text/Markdown excerpt files to ground the decomposition.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "init-workspace":
            workspace = find_workspace(args.topic, args.workspace)
            payload = build_workspace(workspace, args.topic)
        else:
            workspace = find_workspace(args.topic, args.workspace)
            layout_result = ensure_plan_layout(workspace)
            if args.command == "merge-search-results":
                payload = merge_search_results(workspace, args.input)
            elif args.command == "prepare-fulltext-manifest":
                payload = prepare_fulltext_manifest(workspace, args.min_priority, args.require_included)
            elif args.command == "convert-pdfs-with-mineru":
                payload = convert_pdfs_with_mineru(
                    workspace,
                    Path(args.env_path),
                    args.batch_size,
                    args.poll_seconds,
                    args.max_wait_minutes,
                    not args.all_pdfs,
                )
            elif args.command == "chunk-markdown":
                payload = chunk_markdown(workspace, args.target_words, args.overlap_words)
            elif args.command == "retrieve-chunks":
                payload = retrieve_chunks(workspace, args.query, args.purpose, args.top_k, args.include_neighbors)
            elif args.command == "init-frontier-push":
                payload = init_frontier_push(workspace)
            elif args.command == "draft-interest-profile":
                payload = draft_interest_profile(workspace, args.intent, args.llm_mode)
            elif args.command == "collect-frontier-sources":
                source_ids = [item.strip() for item in args.source_ids.split(",") if item.strip()]
                payload = collect_frontier_sources(
                    workspace,
                    args.profile,
                    source_ids,
                    args.year_start,
                    args.year_end,
                    limit_per_query=args.limit_per_query,
                    max_queries=args.max_queries,
                )
            elif args.command == "run-frontier-push":
                tiers = [tier.strip() for tier in args.source_tiers.split(",") if tier.strip()]
                payload = run_frontier_push(
                    workspace,
                    args.profile,
                    tiers,
                    args.input,
                    args.run_id,
                    year_start=args.year_start,
                    year_end=args.year_end,
                )
            elif args.command == "promote-frontier-candidates":
                payload = promote_frontier_candidates(workspace, args.run_id, args.candidate_ids)
            elif args.command == "decompose-paper":
                payload = decompose_frontier_paper(workspace, args.paper_key, args.llm_mode, args.excerpt_file)
            else:
                raise ValueError(f"Unsupported command: {args.command}")
            payload["canonical_plan_dir"] = layout_result["canonical_plan_dir"]
            payload["legacy_plan_dir"] = layout_result["legacy_plan_dir"]
            payload["moved_legacy_plan_file"] = layout_result["moved_plan_file"]
            payload["moved_legacy_history_entries"] = layout_result["moved_history_entries"]
    except Exception as exc:
        emit({"error": str(exc), "command": args.command}, args.format)
        return 1

    emit(payload, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




