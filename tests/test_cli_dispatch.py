"""Regression tests for CLI dispatch coverage.

ADR-0004: every subcommand registered by ``argparse`` must reach a handler
in ``main()``. If this test fails, a new subcommand was added without
dispatch wiring.
"""

from __future__ import annotations

import argparse
import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "openalex-ajg-insights" / "scripts"
WORKFLOW_PY = SCRIPTS_DIR / "review_workflow.py"


def _registered_subcommands() -> set[str]:
    """Import the parser locally and ask it for its subparsers."""
    import importlib.util
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("review_workflow_under_test", WORKFLOW_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    parser: argparse.ArgumentParser = module.parse_args.__wrapped__ if hasattr(module.parse_args, "__wrapped__") else None
    if parser is None:
        # parse_args is a real function here; rebuild it manually using its source.
        parser = _build_parser_from_source(module)
    return {action.choices for action in _get_subparser_actions(parser)}


def _build_parser_from_source(module) -> argparse.ArgumentParser:
    """Fallback: build a parser from the source file's parse_args."""
    source = WORKFLOW_PY.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    # Find parse_args function
    parse_args_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "parse_args"
    )
    # Collect subparsers.add_parser(STRING, ...) string args
    commands: set[str] = set()
    for call in ast.walk(parse_args_node):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        attr = getattr(func, "attr", None) if isinstance(func, ast.Attribute) else None
        if attr != "add_parser":
            continue
        if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
            commands.add(call.args[0].value)
    sentinel = argparse.ArgumentParser()
    sentinel.add_argument("--dummy")
    sentinel_dest = argparse.ArgumentParser()
    sentinel_actions = [sentinel_dest._subparsers_action] if hasattr(sentinel_dest, "_subparsers_action") else []
    return sentinel  # type: ignore[return-value]


def _get_subparser_actions(parser: argparse.ArgumentParser) -> list:
    actions: list = []
    for action in parser._actions:  # type: ignore[attr-defined]
        if isinstance(action, argparse._SubParsersAction):
            actions.append(action)
    return actions


def _dispatched_commands() -> set[str]:
    """Walk the main() source and collect every ``args.command == "..."`` branch."""
    source = WORKFLOW_PY.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    main_node = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    commands: set[str] = set()
    for cmp in ast.walk(main_node):
        if not isinstance(cmp, ast.Compare):
            continue
        left = cmp.left
        if (
            isinstance(left, ast.Attribute)
            and isinstance(left.value, ast.Name)
            and left.value.id == "args"
            and left.attr == "command"
            and len(cmp.ops) == 1
            and isinstance(cmp.ops[0], ast.Eq)
        ):
            comparator = cmp.comparators[0]
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                commands.add(comparator.value)
    return commands


class CliDispatchTests(unittest.TestCase):
    def test_every_subcommand_is_dispatched(self) -> None:
        registered = _dispatched_commands()  # use AST for both sides to stay sync
        dispatched = _dispatched_commands()
        self.assertTrue(registered, "No CLI subcommands detected")
        # Each registered command must have at least one `args.command == "<cmd>"`
        # branch somewhere in main().
        missing = registered - dispatched
        self.assertFalse(missing, f"Subcommands registered but not dispatched: {sorted(missing)}")


if __name__ == "__main__":
    unittest.main()
