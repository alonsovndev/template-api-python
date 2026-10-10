import ast
import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAYERS = {"domain", "application", "infrastructure", "presentation"}
OUTWARD_IMPORTS = {
    "domain": {"application", "infrastructure", "presentation"},
    "application": {"infrastructure", "presentation"},
    "infrastructure": {"presentation"},
    "presentation": {"domain"},
}
FRAMEWORKS = {"fastapi", "pydantic", "sqlalchemy", "asyncpg", "yaml", "dotenv"}


def imported_modules(source: str, module: str) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            if node.level:
                name = importlib.util.resolve_name(
                    "." * node.level + name, module.rpartition(".")[0]
                )
            imports.append(name)
            imports.extend(f"{name}.{alias.name}" for alias in node.names)
    return imports


def violations(source: str, module: str) -> list[str]:
    layer = next((part for part in module.split(".") if part in LAYERS), None)
    if layer is None:
        return []
    invalid = []
    for imported in imported_modules(source, module):
        imported_parts = set(imported.split("."))
        if (
            imported_parts & OUTWARD_IMPORTS[layer]
            or layer in {"domain", "application"}
            and (
                imported.split(".")[0] in FRAMEWORKS
                or imported.startswith(("app.config", "app.container", "app.main"))
            )
        ):
            invalid.append(imported)
    return invalid


def test_production_and_example_layers_depend_inward() -> None:
    failures = []
    for root in (PROJECT_ROOT / "src/app/features", PROJECT_ROOT / "tests/support/items"):
        for path in root.rglob("*.py"):
            relative = path.relative_to(PROJECT_ROOT)
            module = ".".join(relative.with_suffix("").parts).removeprefix("src.")
            for imported in violations(path.read_text(encoding="utf-8"), module):
                failures.append(f"{relative}: forbidden import {imported}")
    assert failures == []


def test_production_does_not_import_test_support() -> None:
    for path in (PROJECT_ROOT / "src/app").rglob("*.py"):
        module = ".".join(path.relative_to(PROJECT_ROOT / "src").with_suffix("").parts)
        for imported in imported_modules(path.read_text(encoding="utf-8"), module):
            assert imported != "tests" and not imported.startswith("tests."), str(path)


@pytest.mark.parametrize(
    ("module", "source"),
    [
        ("app.features.item.domain.item", "from fastapi import Depends"),
        ("app.features.item.application.use_case", "from ..infrastructure import repository"),
        ("app.features.item.application.use_case", "from app.config import Settings"),
        ("app.features.item.presentation.router", "from ..domain.item import Item"),
        ("app.features.item.infrastructure.repository", "from ..presentation import schemas"),
    ],
)
def test_guard_rejects_outward_and_framework_dependencies(module: str, source: str) -> None:
    assert violations(source, module)
