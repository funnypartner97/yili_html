"""Pure, validated application of canonical edit commands to a document graph.

Commands are applied to a deep copy, and the *entire* graph is re-validated after
every single command, so a sequence can never leave a half-valid document. Only
the five canonical command kinds exist; the contract forbids additional
properties, and there is no HTML/JavaScript field anywhere in a block, so no
executable content can be introduced. Unknown block or section ids are rejected
rather than silently ignored.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.core.errors import DomainError
from src.db.validation import validate_persistence_text
from src.documents.contracts import DocumentGraphModel, EditCommandModel

COMMAND_KINDS = ("replaceText", "insertBlock", "removeBlock", "moveBlock", "setTheme")


def _not_found(target: str) -> DomainError:
    return DomainError("edit_target_not_found", f"The edit target {target} does not exist.", status_code=422)


def _find_block(graph: dict, block_id: str):
    for section in graph["sections"]:
        for index, block in enumerate(section["blocks"]):
            if block["id"] == block_id:
                return section, index, block
    return None, None, None


def _find_section(graph: dict, section_id: str):
    for section in graph["sections"]:
        if section["id"] == section_id:
            return section
    return None


def _renumber(section: dict) -> None:
    ordered = sorted(section["blocks"], key=lambda block: block["order"])
    for position, block in enumerate(ordered):
        block["order"] = position
    section["blocks"] = ordered


def _validate_graph(graph: dict) -> None:
    validate_persistence_text(graph)
    try:
        DocumentGraphModel.model_validate(graph)
    except DomainError:
        raise
    except Exception as exc:  # noqa: BLE001 - contract validation surfaces many types
        raise DomainError("edit_result_invalid", "The edited document failed validation.",
                          status_code=422, details={"reason": str(exc)}) from None


def _validate_command(command: Any) -> dict:
    try:
        model = EditCommandModel.model_validate(command)
    except Exception as exc:  # noqa: BLE001
        raise DomainError("edit_command_invalid", "The edit command is not canonical.",
                          status_code=422, details={"reason": str(exc)}) from None
    return model.model_dump(by_alias=True, mode="json")


def apply_commands(graph: dict, commands: list[Any]) -> tuple[dict, list[dict]]:
    """Apply commands to a copy of ``graph``; return the new graph and a diff summary."""
    work = deepcopy(graph)
    diffs: list[dict] = []
    for raw in commands:
        command = _validate_command(raw)
        kind = command["kind"]
        if kind == "replaceText":
            section, _, block = _find_block(work, command["blockId"])
            if block is None:
                raise _not_found(command["blockId"])
            if block["kind"] != "richText":
                raise DomainError("edit_target_incompatible",
                                  "Only rich-text blocks accept replacement text.", status_code=422)
            before = block["text"]
            block["text"] = command["text"]
            diffs.append({"kind": kind, "blockId": block["id"], "sectionId": section["id"],
                          "before": before, "after": command["text"]})
        elif kind == "insertBlock":
            section = _find_section(work, command["sectionId"])
            if section is None:
                raise _not_found(command["sectionId"])
            new_block = deepcopy(command["block"])
            max_order = max((block["order"] for block in section["blocks"]), default=-1)
            new_block["order"] = max_order + 1
            section["blocks"].append(new_block)
            diffs.append({"kind": kind, "blockId": new_block["id"], "sectionId": section["id"],
                          "after": new_block["kind"]})
        elif kind == "removeBlock":
            section, index, block = _find_block(work, command["blockId"])
            if block is None:
                raise _not_found(command["blockId"])
            section["blocks"].pop(index)
            diffs.append({"kind": kind, "blockId": block["id"], "sectionId": section["id"],
                          "before": block["kind"]})
        elif kind == "moveBlock":
            source_section, index, block = _find_block(work, command["blockId"])
            if block is None:
                raise _not_found(command["blockId"])
            target_section = _find_section(work, command["sectionId"])
            if target_section is None:
                raise _not_found(command["sectionId"])
            source_section["blocks"].pop(index)
            block["order"] = command["order"]
            target_section["blocks"].append(block)
            _renumber(target_section)
            if target_section is not source_section:
                _renumber(source_section)
            diffs.append({"kind": kind, "blockId": block["id"], "sectionId": target_section["id"],
                          "after": command["order"]})
        elif kind == "setTheme":
            work["theme"] = deepcopy(command["theme"])
            diffs.append({"kind": kind, "after": command["theme"]["id"]})
        else:  # pragma: no cover - contract validation rejects unknown kinds first
            raise DomainError("edit_command_invalid", "Unsupported edit command.", status_code=422)
        _validate_graph(work)
    return work, diffs


def affected_block_ids(diffs: list[dict]) -> list[str]:
    seen: list[str] = []
    for diff in diffs:
        block_id = diff.get("blockId")
        if block_id and block_id not in seen:
            seen.append(block_id)
    return seen
