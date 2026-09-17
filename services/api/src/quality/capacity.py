"""Layout layer: registry slot and capacity validation.

Capacity failures become diagnostics with a bounded repair command rather than
silently shrinking text below the registry minimum or dropping content. The node
id is always the stable slide id so a repair can be targeted deterministically.
"""
from __future__ import annotations

from src.documents.contracts import CORE_LAYOUTS
from src.quality.models import Diagnostic

LAYOUTS = {layout["id"]: layout for layout in CORE_LAYOUTS["layouts"]}
# The registry's media layout is the canonical target when a body slot overflows.
SPLIT_LAYOUT = "title-media"
FALLBACK_LAYOUT = "title-body"


def _constraint(layout_id: str, slot_id: str, field: str) -> str:
    return f"core-presentation-layouts.json#{layout_id}.{slot_id}.{field}"


def run(graph: dict) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    presentation = graph.get("presentation")
    if not presentation:
        return diagnostics

    blocks = {block["id"]: block
              for section in graph.get("sections", []) for block in section.get("blocks", [])}

    for slide in presentation["slides"]:
        layout = LAYOUTS.get(slide["layoutId"])
        if layout is None:
            diagnostics.append(Diagnostic(
                code="unknown_layout", severity="error", layer="layout", node_id=slide["id"],
                message=f"未登记的版式 “{slide['layoutId']}”。",
                constraint="core-presentation-layouts.json#layouts",
                repair={"command": "replaceLayout", "layoutId": FALLBACK_LAYOUT}))
            continue
        if slide["kind"] not in layout["slideKinds"]:
            diagnostics.append(Diagnostic(
                code="incompatible_layout_kind", severity="error", layer="layout", node_id=slide["id"],
                message=f"版式 “{layout['id']}” 不支持类型 “{slide['kind']}”。",
                constraint=_constraint(layout["id"], "*", "slideKinds"),
                repair={"command": "replaceLayout", "layoutId": FALLBACK_LAYOUT}))

        slots = {slot["id"]: slot for slot in layout["slots"]}
        assigned = {assignment["slotId"] for assignment in slide["slotAssignments"]}
        for slot in layout["slots"]:
            if slot["required"] and slot["id"] not in assigned:
                diagnostics.append(Diagnostic(
                    code="missing_required_slot", severity="error", layer="layout", node_id=slide["id"],
                    message=f"缺少必填槽位 “{slot['id']}”。",
                    constraint=_constraint(layout["id"], slot["id"], "required"),
                    repair={"command": "replaceLayout", "layoutId": FALLBACK_LAYOUT}))

        for assignment in slide["slotAssignments"]:
            slot = slots.get(assignment["slotId"])
            if slot is None:
                diagnostics.append(Diagnostic(
                    code="unknown_slot", severity="error", layer="layout", node_id=slide["id"],
                    message=f"版式 “{layout['id']}” 未定义槽位 “{assignment['slotId']}”。",
                    constraint=_constraint(layout["id"], assignment["slotId"], "slots"),
                    repair={"command": "replaceLayout", "layoutId": FALLBACK_LAYOUT}))
                continue

            count = len(assignment["blockIds"]) + len(assignment["assetIds"])
            min_items = slot.get("minItems", 1 if slot["required"] else 0)
            if count > slot["maxItems"]:
                diagnostics.append(Diagnostic(
                    code="slot_capacity_exceeded", severity="error", layer="layout", node_id=slide["id"],
                    message=f"槽位 “{slot['id']}” 内容数 {count} 超过上限 {slot['maxItems']}。",
                    measurements={"actual": count, "allowed": slot["maxItems"]},
                    constraint=_constraint(layout["id"], slot["id"], "maxItems"),
                    repair={"command": "splitSlide", "layoutId": SPLIT_LAYOUT}))
            elif count < min_items:
                diagnostics.append(Diagnostic(
                    code="slot_capacity_unmet", severity="error", layer="layout", node_id=slide["id"],
                    message=f"槽位 “{slot['id']}” 内容数 {count} 低于下限 {min_items}。",
                    measurements={"actual": count, "allowed": min_items},
                    constraint=_constraint(layout["id"], slot["id"], "minItems"),
                    repair={"command": "splitSlide", "layoutId": SPLIT_LAYOUT}))

            chars = lines = 0
            for block_id in assignment["blockIds"]:
                block = blocks.get(block_id)
                if block and block["kind"] == "richText":
                    chars += len(block["text"])
                    lines += len(block["text"].split("\n"))
            if slot.get("maxChars") and chars > slot["maxChars"]:
                diagnostics.append(Diagnostic(
                    code="text_capacity_exceeded", severity="error", layer="layout", node_id=slide["id"],
                    message=f"槽位 “{slot['id']}” 文本 {chars} 字超过上限 {slot['maxChars']} 字。",
                    measurements={"actual": chars, "allowed": slot["maxChars"]},
                    constraint=_constraint(layout["id"], slot["id"], "maxChars"),
                    repair={"command": "truncateToCapacity", "slotId": slot["id"], "maxChars": slot["maxChars"]}))
            if slot.get("maxLines") and lines > slot["maxLines"]:
                diagnostics.append(Diagnostic(
                    code="line_capacity_exceeded", severity="error", layer="layout", node_id=slide["id"],
                    message=f"槽位 “{slot['id']}” 文本 {lines} 行超过上限 {slot['maxLines']} 行。",
                    measurements={"actual": lines, "allowed": slot["maxLines"]},
                    constraint=_constraint(layout["id"], slot["id"], "maxLines"),
                    repair={"command": "truncateToCapacity", "slotId": slot["id"], "maxLines": slot["maxLines"]}))
    return diagnostics
