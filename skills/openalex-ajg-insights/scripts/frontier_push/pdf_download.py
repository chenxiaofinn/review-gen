from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from .candidates import load_candidates_jsonl
from .review_decisions import load_included_candidate_ids


def _safe_name(candidate_id: str, title: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_")[:80]
    return f"{candidate_id}_{text or 'paper'}.pdf"


def _openalex_pdf(doi: str, timeout: int) -> str | None:
    response = requests.get(
        "https://api.openalex.org/works/https://doi.org/" + quote(doi, safe=""),
        timeout=timeout,
        headers={"Accept": "application/json", "User-Agent": "review-gen/1.0"},
    )
    response.raise_for_status()
    work = response.json()
    locations = []
    if work.get("best_oa_location"):
        locations.append(work["best_oa_location"])
    locations.extend(work.get("locations", []))
    for location in locations:
        if not isinstance(location, dict):
            continue
        pdf_url = location.get("pdf_url")
        if pdf_url:
            return str(pdf_url)
    return None


def _unpaywall_pdf(doi: str, email: str, timeout: int) -> str | None:
    response = requests.get(
        "https://api.unpaywall.org/v2/" + quote(doi, safe=""),
        params={"email": email},
        timeout=timeout,
        headers={"Accept": "application/json", "User-Agent": "review-gen/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    locations = []
    if payload.get("best_oa_location"):
        locations.append(payload["best_oa_location"])
    locations.extend(payload.get("oa_locations", []))
    for location in locations:
        if not isinstance(location, dict):
            continue
        pdf_url = location.get("url_for_pdf") or location.get("pdf_url")
        if pdf_url:
            return str(pdf_url)
    return None


def _download_pdf(url: str, destination: Path, timeout: int) -> None:
    response = requests.get(
        url,
        timeout=timeout,
        headers={"Accept": "application/pdf,*/*", "User-Agent": "review-gen/1.0"},
        stream=True,
    )
    response.raise_for_status()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                handle.write(chunk)
    if destination.stat().st_size < 1024 or destination.read_bytes()[:5] != b"%PDF-":
        destination.unlink(missing_ok=True)
        raise ValueError("downloaded file is not a valid PDF")


def download_frontier_pdfs(
    workspace: Path,
    run_id: str,
    candidate_ids: list[str] | None = None,
    *,
    email: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    candidates_path = workspace / "09_frontier_push" / "runs" / run_id / "candidates.jsonl"
    run_dir = workspace / "09_frontier_push" / "runs" / run_id
    candidates = {item.candidate_id: item for item in load_candidates_jsonl(candidates_path)}
    included = load_included_candidate_ids(run_dir)
    selected_ids = candidate_ids or sorted(included)
    missing = [item for item in selected_ids if item not in candidates]
    if missing:
        raise ValueError(f"Unknown candidate_id(s): {', '.join(missing)}")
    output_dir = workspace / "04_fulltext" / "pdf_inbox"
    not_included = [item for item in selected_ids if item not in included]
    if not_included:
        raise ValueError(
            "Only candidates marked include can be downloaded: " + ", ".join(not_included)
        )
    records: list[dict[str, Any]] = []
    for candidate_id in selected_ids:
        candidate = candidates[candidate_id]
        record: dict[str, Any] = {
            "candidate_id": candidate_id,
            "title": candidate.title,
            "doi": candidate.doi,
            "pdf_url": "",
            "source": "",
            "status": "manual_required",
            "local_pdf_path": "",
            "reason": "",
        }
        try:
            if not candidate.doi:
                raise ValueError("missing DOI")
            sources = [("openalex", _openalex_pdf)]
            if email:
                sources.append(("unpaywall", lambda doi, t: _unpaywall_pdf(doi, email, t)))
            last_error = "no PDF URL returned"
            for source, resolver in sources:
                try:
                    url = resolver(candidate.doi, timeout)
                except Exception as exc:
                    last_error = f"{source}: {exc}"
                    continue
                if not url:
                    continue
                record.update({"pdf_url": url, "source": source})
                destination = output_dir / _safe_name(candidate_id, candidate.title)
                try:
                    _download_pdf(url, destination, timeout)
                except Exception as exc:
                    last_error = f"{source}: {exc}"
                    continue
                record.update({"status": "downloaded", "local_pdf_path": str(destination)})
                break
            else:
                record["reason"] = last_error
        except Exception as exc:
            record["reason"] = str(exc)
        records.append(record)

    jsonl_path = run_dir / "pdf_downloads.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    manual_path = run_dir / "manual_download.tsv"
    with manual_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "title", "doi", "reason"], delimiter="\t")
        writer.writeheader()
        for row in records:
            if row["status"] != "downloaded":
                writer.writerow({field: row.get(field, "") for field in writer.fieldnames})
    return {
        "run_id": run_id,
        "requested": len(records),
        "downloaded": sum(row["status"] == "downloaded" for row in records),
        "manual_required": sum(row["status"] != "downloaded" for row in records),
        "pdf_downloads_path": str(jsonl_path),
        "manual_download_path": str(manual_path),
        "corpus_touched": False,
    }
