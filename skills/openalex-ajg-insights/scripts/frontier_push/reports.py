from __future__ import annotations

from datetime import date

from .candidates import FrontierCandidate
from .profiles import InterestProfile


def _candidate_line(candidate: FrontierCandidate) -> str:
    authors = ", ".join(candidate.authors[:3]) if candidate.authors else "Unknown authors"
    year = candidate.year or "n.d."
    reasons = "; ".join(candidate.match_reasons[:4])
    return (
        f"- **{candidate.title}** ({year}). {authors}. "
        f"*{candidate.venue}*. Tier {candidate.source_tier}, score {candidate.match_score}. "
        f"{reasons}"
    ).strip()


def render_frontier_report(
    profile: InterestProfile,
    candidates: list[FrontierCandidate],
    run_id: str,
    generated_on: date | None = None,
) -> str:
    generated = generated_on or date.today()
    main_push = [candidate for candidate in candidates if candidate.push_bucket == "main_push"]
    early_signals = [candidate for candidate in candidates if candidate.push_bucket != "main_push"]

    lines = [
        f"# Frontier Push Report: {profile.name}",
        "",
        f"- Profile: `{profile.id}`",
        f"- Run ID: `{run_id}`",
        f"- Generated: {generated.isoformat()}",
        f"- Directionality: `{profile.directionality}`",
        f"- Target construct: {profile.target_construct}",
        "",
        "## Main Push",
        "",
    ]
    lines.extend([_candidate_line(candidate) for candidate in main_push] or ["No main-push candidates."])
    lines.extend(["", "## Early Signals", ""])
    lines.extend([_candidate_line(candidate) for candidate in early_signals] or ["No early signals."])
    lines.extend(
        [
            "",
            "## Review Notes",
            "",
            "Candidates in this report are not added to `master_corpus.jsonl` until the user promotes them.",
            "",
        ]
    )
    return "\n".join(lines)

