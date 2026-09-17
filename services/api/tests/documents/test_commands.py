from uuid import uuid7

import pytest

from src.core.errors import DomainError
from src.documents.commands import affected_block_ids, apply_commands


def _ref():
    return {"sourceId": str(uuid7()), "locator": "page 1"}


def _rich(text, order=0):
    return {"id": str(uuid7()), "order": order, "kind": "richText", "text": text, "sourceRefs": [_ref()]}


def _table(order=0):
    return {"id": str(uuid7()), "order": order, "kind": "table",
            "table": {"columns": ["季度", "收入"], "rows": [["Q1", 100]]}, "sourceRefs": [_ref()]}


def graph():
    return {
        "schemaVersion": "1.0.0",
        "artifactId": str(uuid7()),
        "title": "季度经营分析",
        "outputModes": ["document"],
        "theme": {"id": "core", "tokens": {}},
        "assets": [],
        "sections": [
            {"id": str(uuid7()), "order": 0, "title": "执行摘要", "blocks": [_rich("A0", 0), _rich("A1", 1)]},
            {"id": str(uuid7()), "order": 1, "title": "收入", "blocks": [_rich("B0", 0)]},
        ],
    }


def deck_graph():
    doc = graph()
    doc["outputModes"] = ["document", "presentation"]
    title_block = doc["sections"][0]["blocks"][0]
    doc["presentation"] = {
        "stage": {"width": 1920, "height": 1080},
        "slides": [{
            "id": str(uuid7()), "order": 0, "sectionId": doc["sections"][0]["id"], "kind": "content",
            "layoutId": "title-body", "animationTimeline": [],
            "timing": {"plannedSeconds": 60, "rehearsalEvents": []},
            "slotAssignments": [{"id": str(uuid7()), "order": 0, "slotId": "title",
                                 "blockIds": [title_block["id"]], "assetIds": []}],
        }],
    }
    return doc


def block_by_id(doc, block_id):
    for section in doc["sections"]:
        for block in section["blocks"]:
            if block["id"] == block_id:
                return block
    return None


def test_replace_text_only_changes_target_block():
    doc = graph()
    target = doc["sections"][0]["blocks"][0]
    other = doc["sections"][0]["blocks"][1]
    updated, diffs = apply_commands(doc, [{"kind": "replaceText", "blockId": target["id"], "text": "改写后的摘要"}])
    assert block_by_id(updated, target["id"])["text"] == "改写后的摘要"
    assert block_by_id(updated, other["id"])["text"] == other["text"]
    # The original graph is never mutated in place.
    assert target["text"] == "A0"
    assert affected_block_ids(diffs) == [target["id"]]


def test_unknown_block_is_rejected():
    with pytest.raises(DomainError) as error:
        apply_commands(graph(), [{"kind": "removeBlock", "blockId": str(uuid7())}])
    assert error.value.code == "edit_target_not_found"


def test_unknown_section_is_rejected_on_insert():
    with pytest.raises(DomainError) as error:
        apply_commands(graph(), [{"kind": "insertBlock", "sectionId": str(uuid7()), "block": _rich("新段落")}])
    assert error.value.code == "edit_target_not_found"


def test_insert_block_assigns_a_unique_order():
    doc = graph()
    section_id = doc["sections"][0]["id"]
    new_block = _rich("新增内容", order=0)
    updated, diffs = apply_commands(doc, [{"kind": "insertBlock", "sectionId": section_id, "block": new_block}])
    section = next(s for s in updated["sections"] if s["id"] == section_id)
    orders = [block["order"] for block in section["blocks"]]
    assert orders == sorted(set(orders)) == [0, 1, 2]
    assert block_by_id(updated, new_block["id"])["text"] == "新增内容"
    assert diffs[0]["kind"] == "insertBlock"


def test_remove_block_deletes_only_the_target():
    doc = graph()
    target = doc["sections"][1]["blocks"][0]
    updated, _ = apply_commands(doc, [{"kind": "removeBlock", "blockId": target["id"]}])
    assert block_by_id(updated, target["id"]) is None
    assert len(updated["sections"][0]["blocks"]) == 2


def test_move_block_between_sections():
    doc = graph()
    moved = doc["sections"][0]["blocks"][1]
    source_section = doc["sections"][0]["id"]
    target_section = doc["sections"][1]["id"]
    updated, _ = apply_commands(doc, [
        {"kind": "moveBlock", "blockId": moved["id"], "sectionId": target_section, "order": 0},
    ])
    destination = next(s for s in updated["sections"] if s["id"] == target_section)
    source = next(s for s in updated["sections"] if s["id"] == source_section)
    assert moved["id"] in [block["id"] for block in destination["blocks"]]
    assert moved["id"] not in [block["id"] for block in source["blocks"]]
    orders = [block["order"] for block in destination["blocks"]]
    assert orders == sorted(set(orders))


def test_set_theme_replaces_the_theme():
    updated, diffs = apply_commands(graph(), [{"kind": "setTheme", "theme": {"id": "dark", "tokens": {"bg": "#000"}}}])
    assert updated["theme"] == {"id": "dark", "tokens": {"bg": "#000"}}
    assert diffs[0]["kind"] == "setTheme"


def test_replace_text_rejects_non_rich_text_block():
    doc = graph()
    doc["sections"][1]["blocks"] = [_table(0)]
    table_id = doc["sections"][1]["blocks"][0]["id"]
    with pytest.raises(DomainError) as error:
        apply_commands(doc, [{"kind": "replaceText", "blockId": table_id, "text": "x"}])
    assert error.value.code == "edit_target_incompatible"


def test_non_canonical_command_is_rejected():
    doc = graph()
    target = doc["sections"][0]["blocks"][0]["id"]
    with pytest.raises(DomainError) as error:
        apply_commands(doc, [{"kind": "replaceText", "blockId": target, "text": "x", "script": "alert(1)"}])
    assert error.value.code == "edit_command_invalid"


def test_command_that_breaks_a_slide_reference_is_rejected():
    doc = deck_graph()
    title_block = doc["presentation"]["slides"][0]["slotAssignments"][0]["blockIds"][0]
    with pytest.raises(DomainError) as error:
        apply_commands(doc, [{"kind": "removeBlock", "blockId": title_block}])
    assert error.value.code == "edit_result_invalid"


def test_sequence_validates_after_every_command():
    doc = graph()
    section_id = doc["sections"][0]["id"]
    new_block = _rich("先插入", order=0)
    updated, diffs = apply_commands(doc, [
        {"kind": "insertBlock", "sectionId": section_id, "block": new_block},
        {"kind": "replaceText", "blockId": new_block["id"], "text": "再改写"},
    ])
    assert block_by_id(updated, new_block["id"])["text"] == "再改写"
    assert [diff["kind"] for diff in diffs] == ["insertBlock", "replaceText"]
