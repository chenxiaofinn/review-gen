from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path


APPROVED_PREFIX = "Plan status: APPROVED"
DRAFT_PREFIX = "Plan status: DRAFT"
PLAN_DIR_NAME = "07_plan"
LEGACY_PLAN_DIR_NAME = "07_notes"
TA_ONLY_SOURCE_IDS = ("abs_ajg_4star", "ft50", "utd24")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def ensure_plan_layout(workspace: Path) -> dict:
    canonical_dir = workspace / PLAN_DIR_NAME
    legacy_dir = workspace / LEGACY_PLAN_DIR_NAME
    canonical_dir.mkdir(parents=True, exist_ok=True)

    moved_plan = False
    moved_history = 0
    if legacy_dir.exists() and legacy_dir.is_dir():
        legacy_plan = legacy_dir / "review_plan.md"
        canonical_plan = canonical_dir / "review_plan.md"
        if legacy_plan.exists() and not canonical_plan.exists():
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


def inspect_plan_layout(workspace: Path) -> dict:
    canonical_dir = workspace / PLAN_DIR_NAME
    legacy_dir = workspace / LEGACY_PLAN_DIR_NAME
    return {
        "canonical_plan_dir": str(canonical_dir),
        "legacy_plan_dir": str(legacy_dir),
        "moved_plan_file": False,
        "moved_history_entries": 0,
        "canonical_plan_dir_exists": canonical_dir.exists(),
        "legacy_plan_dir_exists": legacy_dir.exists(),
    }


def plan_path(workspace: Path) -> Path:
    return workspace / PLAN_DIR_NAME / "review_plan.md"


def history_dir(workspace: Path) -> Path:
    return workspace / PLAN_DIR_NAME / "history"


def packet_path(workspace: Path) -> Path:
    return workspace / "08_outputs" / "review_packet.md"


def guardrails_path(workspace: Path) -> Path:
    return workspace / "08_outputs" / "review_guardrails.md"


def get_plan_status(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("plan status:"):
            if lowered.startswith("plan status: approved"):
                return "approved"
            if lowered.startswith("plan status: draft"):
                return "draft"
            return "other"
    return "missing-status"


def _yes(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"yes", "y", "true", "1"}


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _profile_id_from_file(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("id:"):
                return stripped.split(":", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    return path.stem


def _latest_mtime(paths: list[Path]) -> float:
    return max((path.stat().st_mtime for path in paths if path.exists()), default=0.0)


def _frontier_status(workspace: Path) -> dict:
    root = workspace / "09_frontier_push"
    profiles_dir = root / "profiles"
    records_dir = root / "source_records"
    runs_dir = root / "runs"
    raw_dir = workspace / "01_search" / "raw_json"
    ris_dir = workspace / "02_corpus" / "zotero_ris"

    profile_paths = []
    if profiles_dir.exists():
        profile_paths = sorted(profiles_dir.glob("*.yml")) + sorted(profiles_dir.glob("*.yaml"))
    profile_ids = [_profile_id_from_file(path) for path in profile_paths]
    active_profile_id = profile_ids[0] if len(profile_ids) == 1 else ""

    source_payloads: list[dict] = []
    source_paths = sorted(records_dir.glob("*.json")) if records_dir.exists() else []
    for path in source_paths:
        payload = _read_json(path)
        source_payloads.append(
            {
                "path": str(path),
                "source_id": str(payload.get("source_id") or payload.get("id") or path.stem),
                "profile_id": str(payload.get("profile_id") or ""),
                "year_start": payload.get("year_start"),
                "year_end": payload.get("year_end"),
                "source_tier": str(payload.get("source_tier") or ""),
            }
        )

    payload_profile_ids = {item["profile_id"] for item in source_payloads if item["profile_id"]}
    year_windows = {
        (item["year_start"], item["year_end"])
        for item in source_payloads
        if item["year_start"] is not None or item["year_end"] is not None
    }
    source_ids = {item["source_id"] for item in source_payloads}
    warnings: list[str] = []
    if len(payload_profile_ids) > 1:
        warnings.append(f"Mixed source_records profiles detected: {sorted(payload_profile_ids)}.")
    if len(year_windows) > 1:
        warnings.append(f"Mixed source_records year windows detected: {sorted(year_windows)}.")
    unexpected_sources = sorted(source_ids - set(TA_ONLY_SOURCE_IDS))
    if unexpected_sources:
        warnings.append(f"Non-TA source_records detected for TA-only workflow: {unexpected_sources}.")

    explicit_input_paths: list[str] = []
    missing_ta_sources: list[str] = []
    if source_payloads and not warnings:
        by_source = {item["source_id"]: item for item in source_payloads}
        missing_ta_sources = [source_id for source_id in TA_ONLY_SOURCE_IDS if source_id not in by_source]
        if not missing_ta_sources:
            explicit_input_paths = [by_source[source_id]["path"] for source_id in TA_ONLY_SOURCE_IDS]

    candidate_paths = sorted(runs_dir.glob("*/candidates.jsonl")) if runs_dir.exists() else []
    raw_paths = sorted(raw_dir.glob("frontier_push_*.json")) if raw_dir.exists() else []
    ris_paths = sorted(ris_dir.glob("frontier_push_*.ris")) if ris_dir.exists() else []
    latest_run_id = candidate_paths[-1].parent.name if candidate_paths else ""

    if not active_profile_id and len(payload_profile_ids) == 1:
        active_profile_id = next(iter(payload_profile_ids))

    return {
        "root_exists": root.exists(),
        "profile_paths": [str(path) for path in profile_paths],
        "active_profile_id": active_profile_id,
        "source_record_paths": [str(path) for path in source_paths],
        "explicit_input_paths": explicit_input_paths,
        "missing_ta_sources": missing_ta_sources,
        "warnings": warnings,
        "candidate_paths": [str(path) for path in candidate_paths],
        "latest_run_id": latest_run_id,
        "promoted_raw_json": [str(path) for path in raw_paths],
        "consolidated_ris": [str(path) for path in ris_paths],
        "latest_candidate_mtime": _latest_mtime(candidate_paths),
        "latest_promotion_mtime": _latest_mtime(raw_paths),
    }


def _screening_status(corpus_rows: list[dict], screening_rows: list[dict[str, str]]) -> dict:
    by_key = {row.get("paper_key", ""): row for row in screening_rows if row.get("paper_key")}
    missing = []
    undecided = []
    included = 0
    need_full_text = 0
    for row in corpus_rows:
        key = str(row.get("paper_key") or "")
        screen = by_key.get(key)
        if not screen:
            missing.append(key)
            continue
        included_value = str(screen.get("included_title_abstract") or "").strip()
        if not included_value:
            undecided.append(key)
        if _yes(included_value):
            included += 1
        if _yes(screen.get("need_full_text")):
            need_full_text += 1
    return {
        "rows": len(screening_rows),
        "included_title_abstract_yes": included,
        "need_full_text_yes": need_full_text,
        "missing_paper_keys": missing,
        "undecided_paper_keys": undecided,
        "complete": bool(corpus_rows) and not missing and not undecided,
    }


def _manifest_status(fulltext_rows: list[dict[str, str]]) -> dict:
    missing_pdf_names = [
        row.get("expected_pdf_name", "")
        for row in fulltext_rows
        if row.get("expected_pdf_name") and str(row.get("pdf_status") or "").strip().lower() not in {"ready", "uploaded", "archived"}
    ]
    ready_pdf = sum(1 for row in fulltext_rows if str(row.get("pdf_status") or "").strip().lower() in {"ready", "uploaded", "archived"})
    ready_md = sum(1 for row in fulltext_rows if str(row.get("md_status") or "").strip().lower() == "ready")
    return {
        "manifest_rows": len(fulltext_rows),
        "ready_pdf_count": ready_pdf,
        "ready_markdown_count": ready_md,
        "missing_expected_pdf_names": missing_pdf_names,
    }


def _workspace_has_layout(workspace: Path) -> bool:
    return any((workspace / rel).exists() for rel in ("01_search", "02_corpus", "03_screening", "04_fulltext", "09_frontier_push"))


def _action(action: str, message: str, **extra: object) -> dict:
    payload = {"action": action, "message": message}
    payload.update(extra)
    return payload


def _derive_stage(
    workspace: Path,
    corpus_rows: list[dict],
    screening: dict,
    manifest: dict,
    frontier: dict,
    plan_status: str,
    plan_exists: bool,
    packet_exists: bool,
) -> tuple[str, str, dict, list[str], list[str], str, str]:
    completed: list[str] = []
    missing: list[str] = []
    next_skill = "openalex-ajg-insights"

    if _workspace_has_layout(workspace):
        completed.append("workspace_layout")
    else:
        missing.append("workspace_layout")
        return ("needs_init", "", _action("init_workspace", "Create or select a review workspace before running frontier-push diagnostics."), completed, missing, next_skill, "search")

    if frontier["profile_paths"]:
        completed.append("frontier_profile")
    if frontier["source_record_paths"]:
        completed.append("frontier_source_records")
    if frontier["candidate_paths"]:
        completed.append("frontier_candidate_report")
    if frontier["promoted_raw_json"]:
        completed.append("frontier_promotion")
    if corpus_rows:
        completed.append("master_corpus")
    if screening["rows"]:
        completed.append("screening_table")
    if manifest["manifest_rows"]:
        completed.append("fulltext_manifest")
    if manifest["ready_markdown_count"]:
        completed.append("mineru_markdown")
    if (workspace / "06_chunks" / "chunk_index.jsonl").exists():
        completed.append("chunks")
    if plan_exists:
        completed.append("review_plan")
    if plan_status == "approved":
        completed.append("approved_plan")
    if packet_exists:
        completed.append("writing_packet")

    if not corpus_rows:
        if frontier["promoted_raw_json"]:
            return ("promoted_ready_for_merge", "", _action("merge_search_results", "Merge promoted frontier JSON into the durable corpus."), completed, missing, next_skill, "search")
        if frontier["candidate_paths"]:
            return (
                "candidate_triage",
                "candidate_triage",
                _action("promote_frontier_candidates", "Review candidates first; promote only explicit user-selected candidate_ids.", run_id=frontier["latest_run_id"]),
                completed,
                missing,
                next_skill,
                "search",
            )
        if frontier["source_record_paths"]:
            if frontier["warnings"]:
                return ("frontier_source_records_mixed", "", _action("inspect_source_records", "Resolve mixed profile/year/source records before run-frontier-push."), completed, missing, next_skill, "search")
            if frontier["missing_ta_sources"]:
                missing.append("complete_ta_source_records")
                return (
                    "frontier_source_records_incomplete",
                    "",
                    _action("collect_frontier_sources", "Collect missing TA-only source payloads.", missing_ta_sources=frontier["missing_ta_sources"]),
                    completed,
                    missing,
                    next_skill,
                    "search",
                )
            return (
                "frontier_sources_ready",
                "",
                _action("run_frontier_push", "Run frontier scoring with explicit --input paths from the current collection.", explicit_input_paths=frontier["explicit_input_paths"]),
                completed,
                missing,
                next_skill,
                "search",
            )
        if frontier["profile_paths"]:
            return ("frontier_profile_ready", "", _action("collect_frontier_sources", "Collect TA-only OpenAlex source records for the reviewed profile."), completed, missing, next_skill, "search")
        missing.append("frontier_profile")
        return ("needs_frontier_profile", "", _action("draft_interest_profile", "Draft or select a reviewable frontier-push InterestProfile."), completed, missing, next_skill, "search")

    if not screening["complete"]:
        return ("screening_required", "title_abstract_screening", _action("screen_manually", "Complete title/abstract screening before preparing the full-text manifest."), completed, missing, next_skill, "screening")

    if not manifest["manifest_rows"]:
        missing.append("fulltext_manifest")
        return ("manifest_required", "", _action("prepare_fulltext_manifest", "Prepare the full-text manifest with --require-included.", require_included=True), completed, missing, next_skill, "manifest")

    if manifest["missing_expected_pdf_names"]:
        return ("pdf_collection", "", _action("collect_pdfs", "Collect or download missing PDFs, then place Zotero PDFs in 04_fulltext/pdf_inbox/ with expected names."), completed, missing, next_skill, "fulltext")

    if manifest["ready_markdown_count"] < manifest["manifest_rows"]:
        return ("conversion_required", "", _action("convert_pdfs_with_mineru", "Convert ready PDFs with MinerU before chunking."), completed, missing, next_skill, "fulltext")

    if not (workspace / "06_chunks" / "chunk_index.jsonl").exists():
        return ("chunking_required", "", _action("chunk_markdown", "Chunk converted Markdown before planning or writing."), completed, missing, next_skill, "fulltext")

    if not plan_exists:
        return ("planning_required", "", _action("build_review_plan", "Build a review plan and wait for explicit user approval."), completed, missing, "management-review-planner", "planning")

    if plan_status != "approved":
        return ("plan_approval_required", "plan_approval", _action("approve_plan", "Record explicit plan approval before writing."), completed, missing, "review-orchestrator", "planning")

    return ("writing_ready", "", _action("build_review_packet", "Generate or refresh the writing packet and draft inside the approved framework."), completed, missing, "management-review-writer", "writing")


def compute_status(workspace: Path) -> dict:
    layout = inspect_plan_layout(workspace)
    corpus_rows = read_jsonl(workspace / "02_corpus" / "master_corpus.jsonl")
    screening_rows = read_csv(workspace / "03_screening" / "screening_table.csv")
    fulltext_rows = read_csv(workspace / "04_fulltext" / "fulltext_manifest.csv")
    screening = _screening_status(corpus_rows, screening_rows)
    manifest = _manifest_status(fulltext_rows)
    frontier = _frontier_status(workspace)
    ready_md = manifest["ready_markdown_count"]
    plan_file = plan_path(workspace)
    packet_file = packet_path(workspace)
    guardrails_file = guardrails_path(workspace)

    plan_exists = plan_file.exists()
    if plan_exists:
        plan_text = plan_file.read_text(encoding="utf-8", errors="ignore")
        current_plan_status = get_plan_status(plan_text)
    else:
        current_plan_status = "missing"

    current_stage, blocked_by_human, recommended_next_action, completed, missing_inputs, next_skill, phase = _derive_stage(
        workspace=workspace,
        corpus_rows=corpus_rows,
        screening=screening,
        manifest=manifest,
        frontier=frontier,
        plan_status=current_plan_status,
        plan_exists=plan_exists,
        packet_exists=packet_file.exists(),
    )
    next_action = recommended_next_action["message"]

    return {
        "workspace": str(workspace),
        "phase": phase,
        "current_stage": current_stage,
        "completed": completed,
        "blocked_by_human": blocked_by_human,
        "missing_inputs": missing_inputs,
        "recommended_next_action": recommended_next_action,
        "frontier_push": frontier,
        "screening": screening,
        "pdf": manifest,
        "master_corpus_count": len(corpus_rows),
        "fulltext_markdown_ready": ready_md,
        "review_plan_exists": plan_exists,
        "review_plan_status": current_plan_status,
        "review_plan_path": str(plan_file),
        "review_packet_exists": packet_file.exists(),
        "review_guardrails_exists": guardrails_file.exists(),
        "next_skill": next_skill,
        "next_action": next_action,
        "canonical_plan_dir": layout["canonical_plan_dir"],
        "legacy_plan_dir": layout["legacy_plan_dir"],
        "moved_legacy_plan_file": layout["moved_plan_file"],
        "moved_legacy_history_entries": layout["moved_history_entries"],
    }


def replace_status_line(lines: list[str], new_line: str) -> list[str]:
    replaced = False
    output: list[str] = []
    for line in lines:
        if line.strip().lower().startswith("plan status:") and not replaced:
            output.append(new_line)
            replaced = True
        else:
            output.append(line)
    if not replaced:
        if output and output[0].startswith("# Review Plan:"):
            output.insert(2, new_line)
        else:
            output.insert(0, new_line)
    return output


def remove_section(lines: list[str], heading: str) -> list[str]:
    output: list[str] = []
    skip = False
    for line in lines:
        if line.strip() == heading:
            skip = True
            continue
        if skip and line.startswith("## "):
            skip = False
        if not skip:
            output.append(line)
    return output


def append_approval_metadata(lines: list[str], actor: str, note: str, now: str) -> list[str]:
    lines = remove_section(lines, "## Approval Metadata")
    metadata = [
        "## Approval Metadata",
        f"- Recorded at: {now}",
        f"- Recorded by: {actor}",
        f"- Note: {note}",
        "",
    ]
    if lines and lines[-1].strip() != "":
        lines.append("")
    lines.extend(metadata)
    return lines


def archive_snapshot(workspace: Path, plan_text: str, label: str) -> Path:
    target_dir = history_dir(workspace)
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = target_dir / f"review_plan__{stamp}__{label}.md"
    archive_path.write_text(plan_text, encoding="utf-8")
    return archive_path


def approve_plan(workspace: Path, approved_by: str, note: str) -> dict:
    ensure_plan_layout(workspace)
    path = plan_path(workspace)
    if not path.exists():
        raise FileNotFoundError(f"review_plan.md not found at {path}")
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    now = datetime.now().isoformat(timespec="seconds")
    lines = replace_status_line(lines, f"{APPROVED_PREFIX} - framework frozen unless author revises it.")
    lines = remove_section(lines, "## Approval Note")
    lines = append_approval_metadata(lines, approved_by, note, now)
    plan_text = "\n".join(lines) + "\n"
    path.write_text(plan_text, encoding="utf-8")
    archive_path = archive_snapshot(workspace, plan_text, "approved")
    payload = compute_status(workspace)
    payload.update({
        "updated": "approved",
        "approved_by": approved_by,
        "approval_note": note,
        "approved_at": now,
        "archive_path": str(archive_path),
    })
    return payload


def reopen_plan(workspace: Path, reopened_by: str, note: str) -> dict:
    ensure_plan_layout(workspace)
    path = plan_path(workspace)
    if not path.exists():
        raise FileNotFoundError(f"review_plan.md not found at {path}")
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    now = datetime.now().isoformat(timespec="seconds")
    lines = replace_status_line(lines, f"{DRAFT_PREFIX} - reopened for revision before prose drafting.")
    lines = remove_section(lines, "## Approval Note")
    lines = append_approval_metadata(lines, reopened_by, f"REOPENED: {note}", now)
    plan_text = "\n".join(lines) + "\n"
    path.write_text(plan_text, encoding="utf-8")
    archive_path = archive_snapshot(workspace, plan_text, "reopened")
    payload = compute_status(workspace)
    payload.update({
        "updated": "reopened",
        "reopened_by": reopened_by,
        "reopen_note": note,
        "reopened_at": now,
        "archive_path": str(archive_path),
    })
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage orchestration state for literature review workspaces.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_cmd = subparsers.add_parser("status", help="Inspect the current review workflow state.")
    status_cmd.add_argument("--workspace", required=True, help="Path to the review workspace.")

    approve_cmd = subparsers.add_parser("approve-plan", help="Approve the review plan after the user confirms it in chat.")
    approve_cmd.add_argument("--workspace", required=True, help="Path to the review workspace.")
    approve_cmd.add_argument("--approved-by", default="user-confirmed-in-chat")
    approve_cmd.add_argument("--note", default="User explicitly approved the framework in conversation.")

    reopen_cmd = subparsers.add_parser("reopen-plan", help="Reopen the review plan for revision.")
    reopen_cmd.add_argument("--workspace", required=True, help="Path to the review workspace.")
    reopen_cmd.add_argument("--reopened-by", default="user-requested-revision")
    reopen_cmd.add_argument("--note", default="User requested framework revision.")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace)
    if args.command == "status":
        payload = compute_status(workspace)
    elif args.command == "approve-plan":
        payload = approve_plan(workspace, args.approved_by, args.note)
    elif args.command == "reopen-plan":
        payload = reopen_plan(workspace, args.reopened_by, args.note)
    else:
        raise ValueError(f"Unsupported command: {args.command}")

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
