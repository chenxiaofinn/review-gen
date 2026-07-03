from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from .llm import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL


def _paper_metadata_block(paper: dict[str, Any]) -> str:
    authors = paper.get("authors") or []
    author_text = ", ".join(str(author) for author in authors) if authors else "Unknown authors"
    return "\n".join(
        [
            f"Title: {paper.get('title') or 'Untitled'}",
            f"Authors: {author_text}",
            f"Year: {paper.get('year') or 'n.d.'}",
            f"Venue: {paper.get('venue') or paper.get('journal') or 'Unknown venue'}",
            f"Abstract: {paper.get('abstract') or ''}",
        ]
    )


def build_decomposition_prompt(paper: dict[str, Any], excerpts: list[str]) -> str:
    excerpt_block = "\n\n".join(
        f"[Excerpt {index + 1}]\n{excerpt.strip()}" for index, excerpt in enumerate(excerpts) if excerpt.strip()
    )
    if not excerpt_block:
        excerpt_block = "[No full-text excerpts provided. Work only from the metadata and mark uncertainty clearly.]"

    return "\n".join(
        [
            "You are an academic paper decomposition assistant for economics and finance literature.",
            "",
            "Paper metadata:",
            _paper_metadata_block(paper),
            "",
            "Available paper excerpts:",
            excerpt_block,
            "",
            "Stage 1: Structured understanding",
            "Extract the paper's research question, motivation, theory, data, method, identification logic, main findings, limitations, and marginal contribution.",
            "Keep claims faithful to the metadata and excerpts. Mark unsupported inferences as uncertain.",
            "",
            "Stage 2: 简体中文深度解读",
            "现在我需要你详细地理解这篇论文，并将该英文文章重写成通俗流畅、引人入胜的简体中文；不是翻译全文。",
            "",
            "核心要求：",
            "- 准确第一：核心事实、数据和逻辑必须与原文完全一致。",
            "- 过程完整：完整解读，不遗漏重要内容。",
            "- 展示亮点：侧重展示文章的亮点，尤其是原文中提到的边际贡献。",
            "- 行文流畅：使用地道中文表达，将英文长句拆解为自然的中文短句，语言连贯，不要机械分点。",
            "- 保留格式：保持原文的标题、粗体、斜体等 Markdown 格式。",
            "- 术语标准：专业术语使用标准翻译，首次出现时括号标注英文原文，例如 R&D -> 研发。",
            "- 读者导向：清晰易懂，适合研究者快速判断这篇论文是否值得精读。",
            "",
            "Output format:",
            "# <Chinese title>",
            "",
            "## 论文基本信息",
            "## 这篇论文在问什么",
            "## 作者为什么这样研究",
            "## 研究设计和证据链",
            "## 主要发现",
            "## 边际贡献",
            "## 局限与阅读提示",
            "",
            "Do not fabricate citations, data, results, or author claims.",
        ]
    )


def _deep_read_path(workspace: Path, paper_key: str) -> Path:
    return workspace / "09_frontier_push" / "deep_reads" / f"{paper_key}.md"


def _call_openai_compatible(prompt: str, env: dict[str, str], timeout: int) -> str:
    base_url = env.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL
    model = env.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {env['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Produce accurate paper decomposition. Do not invent unsupported details.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return str(payload["choices"][0]["message"]["content"])


def decompose_paper(
    workspace: Path,
    paper_key: str,
    paper: dict[str, Any],
    excerpts: list[str],
    llm_mode: str = "auto",
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    if llm_mode not in {"auto", "api", "prompt-only"}:
        raise ValueError("llm_mode must be one of: auto, api, prompt-only.")

    resolved_env = dict(os.environ if env is None else env)
    prompt = build_decomposition_prompt(paper, excerpts)
    output_path = _deep_read_path(workspace, paper_key)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if llm_mode == "prompt-only" or not resolved_env.get("OPENAI_API_KEY"):
        reason = "prompt_only" if llm_mode == "prompt-only" else "missing_api_key"
        output_path.write_text(
            "\n".join(
                [
                    f"# Paper Decomposition Prompt: {paper_key}",
                    "",
                    "LLM credentials were not available. Copy the prompt below into your chosen model.",
                    "",
                    prompt,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return {
            "status": "prompt_fallback",
            "reason": reason,
            "paper_key": paper_key,
            "output_path": str(output_path),
        }

    try:
        content = _call_openai_compatible(prompt, resolved_env, timeout)
    except requests.RequestException as exc:
        output_path.write_text(
            f"# Paper Decomposition Prompt: {paper_key}\n\nLLM call failed: {exc}\n\n{prompt}\n",
            encoding="utf-8",
        )
        return {
            "status": "prompt_fallback",
            "reason": "llm_error",
            "error": str(exc),
            "paper_key": paper_key,
            "output_path": str(output_path),
        }

    output_path.write_text(content, encoding="utf-8")
    return {
        "status": "drafted",
        "reason": "api",
        "paper_key": paper_key,
        "output_path": str(output_path),
    }

