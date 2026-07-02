from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


ALLOWED_DIRECTIONALITY = {"factors_of", "effects_of", "bidirectional", "descriptive"}
LIST_FIELDS = [
    "exact_phrases",
    "near_phrases",
    "related_terms",
    "exclude_keywords",
    "jel_codes",
]
REQUIRED_FIELDS = [
    "id",
    "name",
    "directionality",
    "target_construct",
    *LIST_FIELDS,
    "natural_language",
]


@dataclass(frozen=True)
class InterestProfile:
    id: str
    name: str
    directionality: str
    target_construct: str
    exact_phrases: list[str]
    near_phrases: list[str]
    related_terms: list[str]
    exclude_keywords: list[str]
    jel_codes: list[str]
    natural_language: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InterestProfile":
        validated = validate_interest_profile_dict(payload)
        return cls(**validated)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_string(value: Any) -> str:
    return str(value or "").strip()


def _clean_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list.")
    cleaned = [_clean_string(item) for item in value]
    return [item for item in cleaned if item]


def validate_interest_profile_dict(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"InterestProfile missing required field(s): {', '.join(missing)}")

    profile_id = _clean_string(payload["id"])
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,79}", profile_id):
        raise ValueError("id must be a lowercase slug using letters, numbers, underscore, or hyphen.")

    directionality = _clean_string(payload["directionality"])
    if directionality not in ALLOWED_DIRECTIONALITY:
        allowed = ", ".join(sorted(ALLOWED_DIRECTIONALITY))
        raise ValueError(f"directionality must be one of: {allowed}.")

    target_construct = _clean_string(payload["target_construct"])
    if not target_construct:
        raise ValueError("target_construct is required.")

    validated: dict[str, Any] = {
        "id": profile_id,
        "name": _clean_string(payload["name"]),
        "directionality": directionality,
        "target_construct": target_construct,
        "natural_language": _clean_string(payload["natural_language"]),
    }
    if not validated["name"]:
        raise ValueError("name is required.")
    if not validated["natural_language"]:
        raise ValueError("natural_language is required.")

    for field in LIST_FIELDS:
        validated[field] = _clean_string_list(payload[field], field)

    return validated


def load_interest_profile(path: Path) -> InterestProfile:
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"InterestProfile YAML must contain a mapping: {path}")
    return InterestProfile.from_dict(data)


def write_interest_profile(path: Path, profile: InterestProfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(profile.to_dict(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def profile_path(workspace: Path, profile_id: str) -> Path:
    return workspace / "09_frontier_push" / "profiles" / f"{profile_id}.yml"

