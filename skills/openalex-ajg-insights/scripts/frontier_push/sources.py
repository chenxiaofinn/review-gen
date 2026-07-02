from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def default_source_catalog() -> dict[str, Any]:
    return {
        "version": 1,
        "sources": [
            {
                "id": "abs4_star",
                "name": "ABS/AJG 4* journals",
                "tier": "A",
                "status": "active",
                "type": "openalex_ajg",
                "description": "Quality anchor for elite ABS/AJG 4* journals.",
            },
            {
                "id": "utd24_ft50",
                "name": "UTD24 and FT50 journals",
                "tier": "A",
                "status": "config_only",
                "type": "journal_list",
                "description": "Quality anchor list for later ISSN-backed expansion.",
            },
            {
                "id": "top_conferences",
                "name": "ASSA/AEA, Econometric Society, NBER SI, CEPR, AFA, WFA, EFA, SFS Cavalcade, FIRS",
                "tier": "B",
                "status": "config_only",
                "type": "conference_program",
                "description": "Conference programs are documented in v1 but not crawled.",
            },
            {
                "id": "nber_wp",
                "name": "NBER Working Papers",
                "tier": "C",
                "status": "active",
                "type": "metadata",
                "description": "Early signal source; main-push requires strong signal.",
            },
            {
                "id": "cepr_dp",
                "name": "CEPR Discussion Papers",
                "tier": "C",
                "status": "active",
                "type": "metadata",
                "description": "Early signal source; main-push requires strong signal.",
            },
            {
                "id": "ssrn",
                "name": "SSRN",
                "tier": "C",
                "status": "active",
                "type": "metadata",
                "description": "Early signal source; main-push requires strong signal.",
            },
            {
                "id": "arxiv_qfin_econ",
                "name": "arXiv q-fin/econ",
                "tier": "C",
                "status": "active",
                "type": "metadata",
                "description": "Early signal source; main-push requires strong signal.",
            },
            {
                "id": "iza_wp",
                "name": "IZA Discussion Papers",
                "tier": "C",
                "status": "active",
                "type": "metadata",
                "description": "Early signal source; main-push requires strong signal.",
            },
        ],
    }


def write_default_source_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(default_source_catalog(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def load_source_catalog(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        raise ValueError(f"Source catalog must contain a sources list: {path}")
    return data

