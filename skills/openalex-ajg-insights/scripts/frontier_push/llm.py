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


def build_interest_profile_prompt(intent: str, requested_directionality: str | None = None) -> str:
    lines = [
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
            "required_concept_groups:  # required for descriptive; otherwise {}",
            "  concept_a:",
            "    - academically common term also listed in exact_phrases or near_phrases",
            "  concept_b:",
            "    - academically common term also listed in exact_phrases or near_phrases",
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
            "- If the intent asks for the relationship/association/correlation between two or more concepts, set directionality to descriptive.",
            "- Do not infer a causal direction from neutral wording such as 'X and Y', 'X with Y', or Chinese 'X与Y'.",
            "- Use bidirectional only when the user explicitly asks for mutual, reciprocal, or two-way causality.",
            "- Do not mix X-as-cause papers into factors_of unless the user clearly asks for both directions.",
            "",
            "Quality rules:",
            "- Preserve the user's research intent exactly; do not substitute a different topic.",
            "- Prefer economics and finance terminology.",
            "- Prefer established construct names, scale names, and noun-phrase terms used in article titles over literal translations.",
            "- For relationship topics, cover both concept groups with academically common terms in exact_phrases or near_phrases.",
            "- For descriptive relationship topics, provide at least two required_concept_groups; every group term must also appear in exact_phrases or near_phrases.",
            "- In descriptive required_concept_groups, use concise, discriminative concept anchors rather than repeating the whole research question as long phrases.",
            "- Usually provide 2-5 established aliases per descriptive concept group across exact_phrases and near_phrases.",
            "- Provide at least one precise exact anchor per group for round 1; when multiple equally precise established aliases exist, include all of them in that group and in exact_phrases.",
            "- Add genuine near aliases so exact+near produces a broader round 2.",
            "- Prefer a lexical core such as 'A-share' over redundant variants such as 'A-share market' and 'A-share returns' when the shorter anchor preserves the concept.",
            "- For descriptive profiles, every exact_phrases and near_phrases query term must be assigned to one required_concept_groups group; put scoring-only context in related_terms.",
            "- For factors_of and effects_of topics, return required_concept_groups: {}.",
            "- Include precise phrases, near phrases, broader related terms, exclusions, and JEL codes.",
            "- Keep the YAML reviewable by a human.",
            "- Do not include Markdown fences, comments, or explanatory text outside YAML.",
        ]
    if requested_directionality:
        lines.extend(
            [
                "",
                f"The user explicitly selected directionality: {requested_directionality}",
                "Return exactly that directionality value. Do not infer or substitute another one.",
            ]
        )
    return "\n".join(lines)


def build_profile_audit_prompt(intent: str, profile: InterestProfile) -> str:
    from .source_collection import build_profile_queries

    profile_yaml = yaml.safe_dump(profile.to_dict(), allow_unicode=True, sort_keys=False)
    query_plan_error = ""
    try:
        query_plan = build_profile_queries(profile)
    except ValueError as exc:
        query_plan = []
        query_plan_error = str(exc)
    query_plan_yaml = yaml.safe_dump(query_plan, allow_unicode=True, sort_keys=False)
    return "\n".join(
        [
            "Audit this literature-search InterestProfile against the user's original research intent.",
            "",
            "User intent:",
            intent.strip(),
            "",
            "Current InterestProfile YAML:",
            profile_yaml.strip(),
            "",
            "Compiled OpenAlex query plan:",
            query_plan_yaml.strip(),
            f"Compiled query rounds: {len(query_plan)}",
            f"Compiled query error: {query_plan_error or 'none'}",
            "",
            "Return only YAML with these fields:",
            "status: pass | needs_revision",
            "missing_terms:",
            "  - academically common term missing from the profile",
            "overbroad_terms:",
            "  - term likely to create weakly related results",
            "coverage_assessment:",
            "  core_concept: complete | partial | missing",
            "  outcome_concept: complete | partial | missing",
            "  directionality: acceptable | review",
            "suggested_changes:",
            "  required_concept_groups: {}",
            "  exact_phrases: []",
            "  near_phrases: []",
            "  related_terms: []",
            "  exclude_keywords: []",
            "notes:",
            "  - concise reason for the main findings",
            "",
            "Directionality audit rules:",
            "- For relationship/association/correlation topics between two or more concepts, directionality should normally be descriptive.",
            "- Flag directionality as review if neutral wording such as 'X and Y' or Chinese 'X与Y' was turned into factors_of or effects_of without explicit causal wording.",
            "- Use bidirectional only when the intent explicitly asks for mutual, reciprocal, or two-way causality.",
            "- For descriptive relationship topics, check whether both concept groups are covered by academically common terms.",
            "- For descriptive profiles, verify that required_concept_groups separates the concepts and that each group has precise terms.",
            "- Flag a descriptive group that relies on one over-specific long phrase when a concise lexical anchor or established aliases are available.",
            "- Flag missing core stems and common academic aliases; usually each descriptive group should have 2-5 useful forms.",
            "- Check that every descriptive exact_phrases and near_phrases term is assigned to a required_concept_groups group; ungrouped query terms make the profile inconsistent.",
            "- When several equally precise aliases exist, keep them in exact_phrases and the same concept group so round 1 compiles them with OR.",
            "- A descriptive profile with only one compiled query round needs revision unless the user's intent explicitly requires exact-only retrieval.",
            "- suggested_changes.required_concept_groups must contain directly usable replacement groups when concept-group coverage needs revision.",
            "- Flag missing_terms when the profile uses only literal translations or adjective paraphrases but omits established construct names, scale names, or title-style noun phrases.",
            "",
            "Do not rewrite the whole profile. Do not silently assume that a broad mechanism term is a core topic term.",
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


def audit_interest_profile(
    intent: str,
    profile: InterestProfile,
    llm_mode: str = "auto",
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    if llm_mode not in {"auto", "api", "prompt-only"}:
        raise ValueError("llm_mode must be one of: auto, api, prompt-only.")

    resolved_env = dict(os.environ if env is None else env)
    prompt = build_profile_audit_prompt(intent, profile)
    if llm_mode == "prompt-only":
        return {"status": "unavailable", "reason": "prompt_only", "prompt": prompt}
    if not resolved_env.get("OPENAI_API_KEY"):
        return {"status": "unavailable", "reason": "missing_api_key", "prompt": prompt}

    try:
        content = _call_openai_compatible(prompt, resolved_env, timeout)
        audit = _extract_yaml_mapping(content)
    except (KeyError, ValueError, yaml.YAMLError, requests.RequestException, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": "llm_error", "error": str(exc), "prompt": prompt}

    return {"status": "audited", "reason": "api", "audit": audit, "prompt": prompt}


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
    requested_directionality: str | None = None,
) -> dict[str, Any]:
    if llm_mode not in {"auto", "api", "prompt-only"}:
        raise ValueError("llm_mode must be one of: auto, api, prompt-only.")

    resolved_env = dict(os.environ if env is None else env)
    prompt = build_interest_profile_prompt(intent, requested_directionality=requested_directionality)

    if llm_mode == "prompt-only":
        return _fallback(prompt, "prompt_only")
    if not resolved_env.get("OPENAI_API_KEY"):
        return _fallback(prompt, "missing_api_key")

    try:
        content = _call_openai_compatible(prompt, resolved_env, timeout)
        profile = InterestProfile.from_dict(_extract_yaml_mapping(content))
        if requested_directionality and profile.directionality != requested_directionality:
            raise ValueError(
                "LLM directionality mismatch: "
                f"user selected {requested_directionality}, model returned {profile.directionality}."
            )
    except (KeyError, ValueError, yaml.YAMLError, requests.RequestException, json.JSONDecodeError) as exc:
        return _fallback(prompt, "llm_error", str(exc))

    return {
        "status": "drafted",
        "reason": "api",
        "profile": profile.to_dict(),
        "prompt": prompt,
    }
