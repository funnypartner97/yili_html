"""Quality-gate data model.

Every diagnostic is stable and actionable: it names the offending node by its
stable id, cites the constraint that was violated, carries the actual versus
allowed measurements, and proposes one of a bounded set of repair commands.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Severity = Literal["error", "warning", "review"]
Layer = Literal["schema", "semantic", "layout", "render", "accessibility"]

# The bounded repair vocabulary. Repairs create a new document version and rerun
# the failed layer plus every later layer; they never mutate exported HTML.
REPAIR_COMMANDS = (
    "splitSlide", "truncateToCapacity", "replaceLayout", "addAltText", "useTableFallback",
)

STATIC_LAYERS: tuple[Layer, ...] = ("schema", "semantic", "layout")


class Diagnostic(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    code: str
    severity: Severity
    layer: Layer
    node_id: str
    message: str
    measurements: dict[str, Any] = {}
    constraint: str = ""
    repair: dict[str, Any] | None = None


class QualityReport(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    document_version: int
    profile: str
    diagnostics: list[Diagnostic] = []
    passed_layers: list[str] = []

    @property
    def blocking(self) -> list[Diagnostic]:
        return [item for item in self.diagnostics if item.severity == "error"]

    @property
    def review(self) -> list[Diagnostic]:
        return [item for item in self.diagnostics if item.severity == "review"]

    def blocks_export(self) -> bool:
        return any(item.severity == "error" for item in self.diagnostics)
