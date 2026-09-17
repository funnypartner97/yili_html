"""Fixed-order static quality pipeline.

Layers run in a fixed order — schema, semantic, layout — and the first layer that
produces an error-severity diagnostic stops the pipeline, so later render/export
layers never run on an invalid document. Each diagnostic is stable and carries a
bounded repair command.
"""
from __future__ import annotations

import re
from typing import Callable

from src.documents.contracts import validate_schema
from src.quality import capacity, semantic
from src.quality.models import Diagnostic, QualityReport

_ID_PATTERN = re.compile(r"^[0-9a-f]{8}-")


def _collect_identities(value, found: list[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_identities(item, found)
    elif isinstance(value, dict):
        artifact_id = value.get("artifactId")
        if isinstance(artifact_id, str):
            found.append(artifact_id)
        node_id = value.get("id")
        if isinstance(node_id, str) and _ID_PATTERN.match(node_id):
            found.append(node_id)
        for child in value.values():
            _collect_identities(child, found)


def _schema_layer(graph: dict) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    try:
        validate_schema("DocumentGraph", graph)
    except ValueError as exc:
        diagnostics.append(Diagnostic(
            code="schema_invalid", severity="error", layer="schema",
            node_id=str(graph.get("artifactId", "")), message="文档结构不符合契约。",
            constraint="document-graph.schema.json", measurements={"detail": str(exc)[:200]}, repair=None))
        return diagnostics

    identities: list[str] = []
    _collect_identities(graph, identities)
    for duplicate in sorted({item for item in identities if identities.count(item) > 1}):
        diagnostics.append(Diagnostic(
            code="duplicate_identity", severity="error", layer="schema", node_id=duplicate,
            message="存在重复的稳定标识。", constraint="document-graph.schema.json#StableId",
            repair=None))

    section_ids = {section["id"] for section in graph.get("sections", [])}
    block_ids = {block["id"] for section in graph.get("sections", []) for block in section.get("blocks", [])}
    asset_ids = {asset["id"] for asset in graph.get("assets", [])}

    for section in graph.get("sections", []):
        for block in section.get("blocks", []):
            if block.get("kind") == "image" and block.get("assetId") not in asset_ids:
                diagnostics.append(Diagnostic(
                    code="unresolved_reference", severity="error", layer="schema", node_id=block["id"],
                    message="图片块引用了不存在的素材。", constraint="document-graph.schema.json#Block.assetId",
                    repair=None))

    presentation = graph.get("presentation")
    if presentation:
        for slide in presentation["slides"]:
            if slide.get("sectionId") not in section_ids:
                diagnostics.append(Diagnostic(
                    code="unresolved_reference", severity="error", layer="schema", node_id=slide["id"],
                    message="幻灯片引用了不存在的章节。", constraint="presentation.schema.json#Slide.sectionId",
                    repair=None))
            known_targets = {slide["id"]}
            for assignment in slide.get("slotAssignments", []):
                known_targets.add(assignment["id"])
                for block_id in assignment.get("blockIds", []):
                    known_targets.add(block_id)
                    if block_id not in block_ids:
                        diagnostics.append(Diagnostic(
                            code="unresolved_reference", severity="error", layer="schema",
                            node_id=slide["id"], message="槽位引用了不存在的内容块。",
                            constraint="presentation.schema.json#SlotAssignment.blockIds", repair=None))
                for asset_id in assignment.get("assetIds", []):
                    known_targets.add(asset_id)
                    if asset_id not in asset_ids:
                        diagnostics.append(Diagnostic(
                            code="unresolved_reference", severity="error", layer="schema",
                            node_id=slide["id"], message="槽位引用了不存在的素材。",
                            constraint="presentation.schema.json#SlotAssignment.assetIds", repair=None))
            for animation in slide.get("animationTimeline", []):
                for target in animation.get("targetIds", []):
                    if target not in known_targets:
                        diagnostics.append(Diagnostic(
                            code="unresolved_reference", severity="error", layer="schema",
                            node_id=slide["id"], message="动画目标不存在。",
                            constraint="presentation.schema.json#AnimationEntry.targetIds", repair=None))
    return diagnostics


LayerRunner = Callable[[dict], list[Diagnostic]]
_STATIC_RUNNERS: tuple[tuple[str, LayerRunner], ...] = (
    ("schema", _schema_layer),
    ("semantic", semantic.run),
    ("layout", capacity.run),
)


class QualityPipeline:
    def __init__(self, *, profile: str = "standalone-html"):
        self.profile = profile

    def run_static_layers(self, graph: dict, *, document_version: int = 0) -> QualityReport:
        passed: list[str] = []
        diagnostics: list[Diagnostic] = []
        for layer, runner in _STATIC_RUNNERS:
            layer_diagnostics = runner(graph)
            diagnostics.extend(layer_diagnostics)
            if any(item.severity == "error" for item in layer_diagnostics):
                break
            passed.append(layer)
        return QualityReport(document_version=document_version, profile=self.profile,
                             diagnostics=diagnostics, passed_layers=passed)
