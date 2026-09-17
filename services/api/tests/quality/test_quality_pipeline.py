from uuid import uuid7

from src.quality import capacity, semantic
from src.quality.pipeline import QualityPipeline

SOURCE_ID = str(uuid7())


def _rich(text, order=0):
    return {"id": str(uuid7()), "order": order, "kind": "richText", "text": text,
            "sourceRefs": [{"sourceId": SOURCE_ID, "locator": "page 1"}]}


def valid_graph():
    section_id = str(uuid7())
    title_block = _rich("执行摘要", 0)
    body_block = _rich("正文内容", 1)
    return {
        "schemaVersion": "1.0.0", "artifactId": str(uuid7()), "title": "季度报告",
        "outputModes": ["document", "presentation"], "theme": {"id": "core", "tokens": {}},
        "assets": [],
        "sections": [{"id": section_id, "order": 0, "title": "执行摘要",
                      "blocks": [title_block, body_block]}],
        "presentation": {"stage": {"width": 1920, "height": 1080}, "slides": [{
            "id": str(uuid7()), "order": 0, "sectionId": section_id, "kind": "content",
            "layoutId": "title-body",
            "slotAssignments": [
                {"id": str(uuid7()), "order": 0, "slotId": "title", "blockIds": [title_block["id"]], "assetIds": []},
                {"id": str(uuid7()), "order": 1, "slotId": "body", "blockIds": [body_block["id"]], "assetIds": []},
            ],
            "timing": {"plannedSeconds": 60, "rehearsalEvents": []}, "animationTimeline": [],
        }]},
    }


def overfull_graph():
    graph = valid_graph()
    section = graph["sections"][0]
    extra = [_rich(f"要点 {index}", order=2 + index) for index in range(6)]
    section["blocks"].extend(extra)
    body = next(a for a in graph["presentation"]["slides"][0]["slotAssignments"] if a["slotId"] == "body")
    body["blockIds"] = [section["blocks"][1]["id"], *[block["id"] for block in extra]]
    return graph


def test_valid_graph_passes_every_static_layer():
    report = QualityPipeline().run_static_layers(valid_graph(), document_version=3)
    assert report.passed_layers == ["schema", "semantic", "layout"]
    assert report.diagnostics == []
    assert report.document_version == 3 and report.profile == "standalone-html"
    assert not report.blocks_export()


def test_pipeline_stops_at_capacity_with_repair():
    graph = overfull_graph()
    report = QualityPipeline().run_static_layers(graph)
    issue = next(item for item in report.diagnostics if item.code == "slot_capacity_exceeded")
    assert report.passed_layers == ["schema", "semantic"]
    assert issue.node_id == graph["presentation"]["slides"][0]["id"]
    assert issue.repair == {"command": "splitSlide", "layoutId": "title-media"}
    assert issue.measurements == {"actual": 7, "allowed": 6}
    assert issue.constraint.endswith("title-body.body.maxItems")
    assert report.blocks_export()


def test_schema_failure_stops_before_later_layers():
    graph = valid_graph()
    graph["schemaVersion"] = "9.9.9"
    report = QualityPipeline().run_static_layers(graph)
    assert report.passed_layers == []
    assert any(item.code == "schema_invalid" and item.layer == "schema" for item in report.diagnostics)
    # Later layers never ran, so no capacity diagnostics are present.
    assert all(item.layer == "schema" for item in report.diagnostics)


def test_unresolved_slide_reference_is_a_schema_error():
    graph = valid_graph()
    graph["presentation"]["slides"][0]["slotAssignments"][0]["blockIds"] = [str(uuid7())]
    report = QualityPipeline().run_static_layers(graph)
    assert report.passed_layers == []
    assert any(item.code == "unresolved_reference" for item in report.diagnostics)


def test_semantic_layer_flags_missing_alt_text():
    graph = {"assets": [{"id": "asset-1", "kind": "image", "mediaIntent": {"alt": "   "}}], "sections": []}
    diagnostics = semantic.run(graph)
    assert any(item.code == "missing_alt_text" and item.repair["command"] == "addAltText"
               for item in diagnostics)


def test_semantic_layer_flags_missing_table_fallback():
    graph = {"assets": [], "sections": [{"id": "s", "blocks": [
        {"id": "b", "kind": "chart", "chart": {"mark": "bar"},
         "frame": {"title": "季度收入", "tableFallback": {"columns": ["a"], "rows": []}}}]}]}
    diagnostics = semantic.run(graph)
    assert any(item.code == "missing_table_fallback" and item.repair["command"] == "useTableFallback"
               for item in diagnostics)


def test_capacity_layer_flags_unknown_layout_and_text_overflow():
    graph = {"sections": [{"id": "s", "blocks": [{"id": "b", "kind": "richText", "text": "长" * 1200}]}],
             "presentation": {"slides": [
                 {"id": "slide-x", "kind": "content", "layoutId": "not-registered", "slotAssignments": []},
                 {"id": "slide-y", "kind": "content", "layoutId": "title-body", "slotAssignments": [
                     {"slotId": "title", "blockIds": ["b"], "assetIds": []}]},
             ]}}
    diagnostics = capacity.run(graph)
    codes = {item.code for item in diagnostics}
    assert "unknown_layout" in codes
    assert "text_capacity_exceeded" in codes
    overflow = next(item for item in diagnostics if item.code == "text_capacity_exceeded")
    assert overflow.repair["command"] == "truncateToCapacity"
