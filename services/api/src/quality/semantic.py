"""Semantic layer: source/alt/table-fallback invariants on a structurally valid graph.

These checks assume the schema layer already passed, so they reason about meaning
rather than shape: does every image carry alt text, does every chart keep its
accessible table fallback, and does every citation carry a locator.
"""
from __future__ import annotations

from src.quality.models import Diagnostic


def run(graph: dict) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    assets = {asset["id"]: asset for asset in graph.get("assets", [])}

    for asset in graph.get("assets", []):
        intent = asset.get("mediaIntent", {})
        if asset.get("kind") == "image" and not str(intent.get("alt", "")).strip():
            diagnostics.append(Diagnostic(
                code="missing_alt_text", severity="error", layer="semantic", node_id=asset["id"],
                message="图片素材缺少替代文本。", constraint="presentation.schema.json#MediaIntent.alt",
                repair={"command": "addAltText", "nodeId": asset["id"]}))

    for section in graph.get("sections", []):
        for block in section.get("blocks", []):
            kind = block.get("kind")
            if kind == "chart":
                fallback = block.get("frame", {}).get("tableFallback", {})
                if not fallback.get("rows"):
                    diagnostics.append(Diagnostic(
                        code="missing_table_fallback", severity="error", layer="semantic",
                        node_id=block["id"], message="图表缺少可访问的数据表回退。",
                        constraint="document-graph.schema.json#ChartFrame.tableFallback",
                        repair={"command": "useTableFallback", "nodeId": block["id"]}))
                if not str(block.get("frame", {}).get("title", "")).strip():
                    diagnostics.append(Diagnostic(
                        code="missing_chart_title", severity="warning", layer="semantic",
                        node_id=block["id"], message="图表缺少标题。",
                        constraint="document-graph.schema.json#ChartFrame.title",
                        repair={"command": "useTableFallback", "nodeId": block["id"]}))
            if kind == "image" and block.get("assetId") not in assets:
                diagnostics.append(Diagnostic(
                    code="unresolved_asset", severity="error", layer="semantic",
                    node_id=block["id"], message="图片块引用了不存在的素材。",
                    constraint="document-graph.schema.json#Block.assetId",
                    repair={"command": "replaceLayout", "nodeId": block["id"]}))
            for reference in block.get("sourceRefs", []):
                if not str(reference.get("locator", "")).strip():
                    diagnostics.append(Diagnostic(
                        code="missing_source_locator", severity="warning", layer="semantic",
                        node_id=block["id"], message="引用缺少定位信息。",
                        constraint="common.schema.json#SourceRef.locator",
                        repair=None))
    return diagnostics
