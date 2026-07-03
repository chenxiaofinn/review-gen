from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .source_collection import FT50_JOURNALS, UTD24_JOURNALS


def default_source_catalog() -> dict[str, Any]:
    return {
        "version": 2,
        "sources": [
            {
                "id": "abs_ajg_4star",
                "name": "ABS/AJG 4* journals",
                "tier": "A",
                "status": "active",
                "type": "openalex_ajg",
                "resolver": "ajg_csv_rank",
                "rank": "4*",
                "description": "Quality anchor resolved from the bundled AJG CSV; AJG 3+ is intentionally out of scope.",
            },
            {
                "id": "ft50",
                "name": "Financial Times 50 journals",
                "tier": "A",
                "status": "active",
                "type": "openalex_ajg",
                "resolver": "named_journal_pool_via_ajg_csv",
                "journal_names": FT50_JOURNALS,
                "description": "FT50 named pool resolved against the bundled AJG CSV for ISSNs.",
            },
            {
                "id": "utd24",
                "name": "UTD24 journals",
                "tier": "A",
                "status": "active",
                "type": "openalex_ajg",
                "resolver": "named_journal_pool_via_ajg_csv",
                "journal_names": UTD24_JOURNALS,
                "description": "UTD24 named pool resolved against the bundled AJG CSV for ISSNs.",
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
