from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .candidates import FrontierCandidate, load_candidates_jsonl, normalize_doi
from .llm import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL
from .review_decisions import load_included_candidate_ids


BRIEF_FORMAT_VERSION = "1.0"
MAX_MARKDOWN_CHARS_PER_PAPER = 100000
REQUIRED_PAPER_FIELDS = (
    "why_it_matters",
    "research_question",
    "data_and_method",
    "main_findings",
    "contribution",
    "limitations",
)


def _safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned or "frontier_brief"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_manifest_by_doi(workspace: Path) -> dict[str, dict[str, str]]:
    import csv

    path = workspace / "04_fulltext" / "fulltext_manifest.csv"
    if not path.exists():
        raise FileNotFoundError("fulltext_manifest.csv is missing. Convert the included PDFs first.")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {normalize_doi(row.get("doi", "")): row for row in rows if normalize_doi(row.get("doi", ""))}


def collect_brief_inputs(workspace: Path, run_id: str) -> list[dict[str, Any]]:
    run_dir = workspace / "09_frontier_push" / "runs" / run_id
    included_ids = load_included_candidate_ids(run_dir)
    candidates = {
        candidate.candidate_id: candidate
        for candidate in load_candidates_jsonl(run_dir / "candidates.jsonl")
    }
    manifest_by_doi = _load_manifest_by_doi(workspace)
    inputs: list[dict[str, Any]] = []
    missing: list[str] = []

    for candidate_id in sorted(included_ids):
        candidate = candidates.get(candidate_id)
        if candidate is None:
            missing.append(f"{candidate_id}: candidate metadata missing")
            continue
        manifest_row = manifest_by_doi.get(normalize_doi(candidate.doi), {})
        md_path = Path(manifest_row.get("md_path", "")) if manifest_row.get("md_path") else None
        if not md_path or not md_path.exists():
            missing.append(f"{candidate_id}: converted Markdown missing")
            continue
        full_text = md_path.read_text(encoding="utf-8", errors="ignore")
        prompt_text = full_text[:MAX_MARKDOWN_CHARS_PER_PAPER]
        inputs.append(
            {
                "candidate": candidate,
                "md_path": md_path,
                "sha256": _sha256(md_path),
                "markdown": prompt_text,
                "input_chars": len(prompt_text),
                "truncated": len(full_text) > len(prompt_text),
            }
        )

    if missing:
        raise ValueError("Frontier brief inputs are incomplete: " + "; ".join(missing))
    if not inputs:
        raise ValueError("No included candidates with converted Markdown were found.")
    return inputs


def build_frontier_brief_prompt(profile_id: str, run_id: str, inputs: list[dict[str, Any]]) -> str:
    papers: list[str] = []
    for item in inputs:
        candidate: FrontierCandidate = item["candidate"]
        papers.append(
            "\n".join(
                [
                    f"candidate_id: {candidate.candidate_id}",
                    f"title: {candidate.title}",
                    f"year: {candidate.year or 'n.d.'}",
                    f"venue: {candidate.venue}",
                    f"doi: {candidate.doi}",
                    "full_text_markdown:",
                    item["markdown"],
                ]
            )
        )

    return "\n".join(
        [
            "你是一名严谨的学术文献编辑。请根据提供的全文 Markdown 生成中文前沿文献快报。",
            "只能使用输入材料中的信息，不得补写无法验证的事实、数据或因果结论。",
            "即使输入只有一篇文献，也不要虚构跨文献共识。",
            "",
            f"profile_id: {profile_id}",
            f"run_id: {run_id}",
            "",
            "只返回一个 JSON 对象，不要使用 Markdown 代码围栏。固定结构如下：",
            "{",
            '  "executive_summary": "2至4句话",',
            '  "papers": [',
            "    {",
            '      "candidate_id": "必须与输入一致",',
            '      "why_it_matters": "与本次主题的关系",',
            '      "research_question": "研究问题",',
            '      "data_and_method": "数据、样本与方法",',
            '      "main_findings": "主要发现",',
            '      "contribution": "边际贡献",',
            '      "limitations": "局限及阅读提醒"',
            "    }",
            "  ],",
            '  "cross_paper_synthesis": "共同点、差异或单篇证据说明",',
            '  "research_implications": "对后续研究的启示",',
            '  "evidence_boundaries": "证据边界和不能推出的结论"',
            "}",
            "",
            "输入文献：",
            "\n\n--- PAPER ---\n\n".join(papers),
        ]
    )


def _parse_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("LLM brief response must be a JSON object.")
    return payload


def validate_brief_payload(payload: dict[str, Any], candidate_ids: list[str]) -> None:
    for field in ("executive_summary", "cross_paper_synthesis", "research_implications", "evidence_boundaries"):
        if not str(payload.get(field) or "").strip():
            raise ValueError(f"LLM brief response is missing: {field}")
    papers = payload.get("papers")
    if not isinstance(papers, list):
        raise ValueError("LLM brief response papers must be a list.")
    returned_ids = [str(item.get("candidate_id") or "") for item in papers if isinstance(item, dict)]
    if returned_ids != candidate_ids:
        raise ValueError("LLM brief response candidate_ids do not match the included candidates.")
    for paper in papers:
        for field in REQUIRED_PAPER_FIELDS:
            if not str(paper.get(field) or "").strip():
                raise ValueError(f"LLM brief paper entry is missing: {field}")


def render_frontier_brief(
    profile_id: str,
    run_id: str,
    model: str,
    inputs: list[dict[str, Any]],
    payload: dict[str, Any],
) -> str:
    candidate_lookup = {item["candidate"].candidate_id: item["candidate"] for item in inputs}
    lines = [
        "# 前沿文献快报",
        "",
        "## 1. 批次信息",
        "",
        f"- 格式版本：`{BRIEF_FORMAT_VERSION}`",
        f"- Run ID：`{run_id}`",
        f"- Profile：`{profile_id}`",
        f"- 纳入文献数：{len(inputs)}",
        f"- 生成模型：`{model}`",
        f"- 生成时间（UTC）：{datetime.now(timezone.utc).isoformat()}",
        "",
        "## 2. 本期摘要",
        "",
        str(payload["executive_summary"]).strip(),
        "",
        "## 3. 文献速览",
    ]
    for index, paper in enumerate(payload["papers"], start=1):
        candidate = candidate_lookup[paper["candidate_id"]]
        citation = f"{'; '.join(candidate.authors)} ({candidate.year or 'n.d.'}). {candidate.title}. {candidate.venue}."
        lines.extend(
            [
                "",
                f"### 3.{index} {candidate.title}",
                "",
                f"- Candidate ID：`{candidate.candidate_id}`",
                f"- DOI：`{candidate.doi or '无'}`",
                f"- 引用信息：{citation}",
                f"- 推荐理由：{paper['why_it_matters']}",
                f"- 研究问题：{paper['research_question']}",
                f"- 数据与方法：{paper['data_and_method']}",
                f"- 主要发现：{paper['main_findings']}",
                f"- 边际贡献：{paper['contribution']}",
                f"- 局限与阅读提醒：{paper['limitations']}",
            ]
        )
    lines.extend(
        [
            "",
            "## 4. 综合判断",
            "",
            str(payload["cross_paper_synthesis"]).strip(),
            "",
            "## 5. 后续研究启示",
            "",
            str(payload["research_implications"]).strip(),
            "",
            "## 6. 证据边界",
            "",
            str(payload["evidence_boundaries"]).strip(),
            "",
            "## 7. 输入追溯",
            "",
            "| Candidate ID | DOI | Markdown | SHA-256 | 截断 | 输入字符数 |",
            "|---|---|---|---|---|---:|",
        ]
    )
    for item in inputs:
        candidate = item["candidate"]
        lines.append(
            f"| `{candidate.candidate_id}` | `{candidate.doi or ''}` | `{item['md_path']}` | `{item['sha256']}` | "
            f"{'是' if item['truncated'] else '否'} | {item['input_chars']} |"
        )
    lines.append("")
    return "\n".join(lines)


def generate_frontier_brief(
    workspace: Path,
    run_id: str,
    profile_id: str,
    llm_mode: str = "auto",
    env: dict[str, str] | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    if llm_mode not in {"auto", "api", "prompt-only"}:
        raise ValueError("llm_mode must be one of: auto, api, prompt-only.")
    resolved_env = dict(os.environ if env is None else env)
    inputs = collect_brief_inputs(workspace, run_id)
    prompt = build_frontier_brief_prompt(profile_id, run_id, inputs)
    output_dir = workspace / "09_frontier_push" / "briefs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{_safe_stem(run_id)}.md"

    if llm_mode == "prompt-only" or not resolved_env.get("OPENAI_API_KEY"):
        prompt_path = output_dir / f"{_safe_stem(run_id)}.prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        return {
            "status": "prompt_fallback",
            "reason": "prompt_only" if llm_mode == "prompt-only" else "missing_api_key",
            "run_id": run_id,
            "input_count": len(inputs),
            "output_path": str(prompt_path),
        }

    base_url = resolved_env.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL
    model = resolved_env.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {resolved_env['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "Return faithful structured JSON for a reproducible literature brief."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    content = str(response.json()["choices"][0]["message"]["content"])
    payload = _parse_json_object(content)
    candidate_ids = [item["candidate"].candidate_id for item in inputs]
    validate_brief_payload(payload, candidate_ids)
    output_path.write_text(
        render_frontier_brief(profile_id, run_id, model, inputs, payload),
        encoding="utf-8",
    )
    return {
        "status": "generated",
        "run_id": run_id,
        "profile_id": profile_id,
        "format_version": BRIEF_FORMAT_VERSION,
        "input_count": len(inputs),
        "model": model,
        "output_path": str(output_path),
    }
