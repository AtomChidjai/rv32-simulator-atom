"""Enforce the public callable naming convention."""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
PYTHON_ROOTS = ("rv32i", "gui", "tests", "programs")


def test_python_callables_do_not_have_single_leading_underscores() -> None:
    violations: list[str] = []

    for root_name in PYTHON_ROOTS:
        for path in (PROJECT_ROOT / root_name).rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name.startswith("_")
                    and not node.name.startswith("__")
                ):
                    relative_path = path.relative_to(PROJECT_ROOT)
                    violations.append(f"{relative_path}:{node.lineno}: {node.name}")

    assert not violations, "single-leading-underscore callables:\n" + "\n".join(
        violations
    )
