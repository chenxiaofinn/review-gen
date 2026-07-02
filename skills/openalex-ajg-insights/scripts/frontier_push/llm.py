from __future__ import annotations

import json
import os
import re
from typing import Any

import requests
import yaml

from .profiles import InterestProfile


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def build_interest_profile_prompt(intent: str) -> str:
    return "\n".join(
        [
            "You are helping maintain a reviewable InterestProfile for frontier literature tracking.",
            "",
            "User intent, in Chinese:",
            intent.strip(),
            "",
            "Return only YAML for one InterestProfile with these fields:",
            "id: lowercase_slug",
            "name: Chinese topic name",
            "directionality: factors_of | effects_of | bidirectional | descriptive",
            "target_construct: the outcome or focal construct in English",
            "exact_phrases:",
            "  - phrase that should match closely",
            "near_phrases:",
            "  - phrase with near meaning",
            "related_terms:",
            "  - broader or mechanism term",
            "exclude_keywords:",
            "  - keyword that should be filtered out",
            "jel_codes:",
            "  - JEL code",
            "natural_language: >",
            "  One English paragraph explaining what to track.",
            "",
            "Directionality rule:",
            "- If the intent asks for factors/determinants/antecedents of X, set directionality to factors_of.",
            "- If the intent asks for effects/consequences/impact of X, set directionality to effects_of.",
            "- Do not mix X-as-cause papers into factors_of unless the user clearly asks for both directions.",
            "",
            "Quality rules:",
            "- Prefer economics and finance terminology.",
            "- Include precise phrases, near phrases, broader related terms, exclusions, and JEL codes.",
            "- Keep the YAML reviewable by a human.",
            "- Do not include Markdown fences, comments, or explanatory text outside YAML.",
        ]
    )


def _fallback(prompt: str, reason: str, error: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "prompt_fallback",
        "reason": reason,
        "profile": None,
        "prompt": prompt,
    }
    if error:
        result["error"] = error
    return result


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _extract_yaml_mapping(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.search(r"```(?:yaml|yml)?\s*(.*?)```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()
    data = yaml.safe_load(stripped)
    if not isinstance(data, dict):
        raise ValueError("LLM response did not contain an InterestProfile YAML mapping.")
    return data


def _call_openai_compatible(prompt: str, env: dict[str, str], timeout: int) -> str:
    api_key = env["OPENAI_API_KEY"]
    base_url = env.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL
    model = env.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    response = requests.post(
        _chat_completions_url(base_url),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return reviewable YAML that follows the requested schema.",
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


def draft_interest_profile(
    intent: str,
    llm_mode: str = "auto",
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    if llm_mode not in {"auto", "api", "prompt-only"}:
        raise ValueError("llm_mode must be one of: auto, api, prompt-only.")

    resolved_env = dict(os.environ if env is None else env)
    prompt = build_interest_profile_prompt(intent)

    if llm_mode == "prompt-only":
        return _fallback(prompt, "prompt_only")
    if not resolved_env.get("OPENAI_API_KEY"):
        return _fallback(prompt, "missing_api_key")

    try:
        content = _call_openai_compatible(prompt, resolved_env, timeout)
        profile = InterestProfile.from_dict(_extract_yaml_mapping(content))
    except (KeyError, ValueError, requests.RequestException, json.JSONDecodeError) as exc:
        return _fallback(prompt, "llm_error", str(exc))

    return {
        "status": "drafted",
        "reason": "api",
        "profile": profile.to_dict(),
        "prompt": prompt,
    }
