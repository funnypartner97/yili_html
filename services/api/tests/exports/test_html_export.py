from uuid import uuid7

from src.exports.assets import StaticAssetResolver
from src.exports.html import HtmlExporter

SOURCE = {"sourceId": str(uuid7()), "locator": "page 3"}


def text_graph(text="本季度收入稳步增长。"):
    return {
        "artifactId": str(uuid7()), "title": "季度经营分析", "schemaVersion": "1.0.0",
        "outputModes": ["document"], "theme": {"id": "core", "tokens": {}}, "assets": [],
        "sections": [{"id": str(uuid7()), "order": 0, "title": "执行摘要", "blocks": [
            {"id": str(uuid7()), "order": 0, "kind": "richText", "text": text, "sourceRefs": [SOURCE]}]}],
    }


def asset_graph():
    graph = text_graph()
    asset_id = str(uuid7())
    graph["assets"] = [{"id": asset_id, "kind": "image", "uri": "uploads/hero.png",
                        "mediaIntent": {"alt": "营收趋势图", "caption": "图 1：营收"}}]
    graph["sections"][0]["blocks"].append(
        {"id": str(uuid7()), "order": 1, "kind": "image", "assetId": asset_id, "sourceRefs": [SOURCE]})
    return graph, asset_id


def chart_graph():
    graph = text_graph()
    graph["sections"][0]["blocks"].append({
        "id": str(uuid7()), "order": 1, "kind": "chart",
        "chart": {"id": str(uuid7()), "mark": "bar", "semanticExplanation": "按季度汇总的营业收入。"},
        "frame": {"title": "季度收入", "description": "两个季度对比", "source": [SOURCE],
                  "asOf": "2026-06-30", "caveats": [], "claim": "收入环比增长。",
                  "tableFallback": {"columns": ["季度", "收入"], "rows": [["Q1", 120], ["Q2", 160]]}},
        "sourceRefs": [SOURCE]})
    return graph


RESOLVER = StaticAssetResolver({"uploads/hero.png": b"\x89PNG\r\n\x1a\n-fake-bytes"})


def test_html_export_is_self_contained():
    graph, asset_id = asset_graph()
    archive = HtmlExporter(RESOLVER).export(graph, document_version=2)
    html = archive.read_text("index.html")
    assert '<script src="http' not in html
    assert '<link href="http' not in html
    assert "javascript:" not in html
    assert archive.exists("manifest.json")
    manifest = archive.read_json("manifest.json")
    assert manifest["assets"][0]["sha256"]
    assert manifest["documentVersion"] == 2
    assert manifest["dependencies"] == []
    # The managed asset is copied locally and referenced by a relative path.
    assert archive.exists(f"assets/{asset_id}.png")
    assert f'src="assets/{asset_id}.png"' in html
    assert "http://" not in html and "https://" not in html


def test_export_escapes_user_text():
    graph = text_graph("<script>alert(1)</script>")
    html = HtmlExporter(RESOLVER).export(graph).read_text("index.html")
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html


def test_export_renders_chart_table_fallback_and_metadata():
    html = HtmlExporter(RESOLVER).export(chart_graph()).read_text("index.html")
    assert "季度收入" in html
    assert "数据截至 2026-06-30" in html
    assert "<th scope=\"col\">季度</th>" in html
    # A basic mark is pre-rendered to static SVG by the bundled renderer.
    assert 'class="svg-chart"' in html
    # Chart data is embedded as a non-executable JSON island.
    assert '<script type="application/json" id="chart-data">' in html


def test_export_is_byte_for_byte_deterministic():
    graph = chart_graph()
    first = HtmlExporter(RESOLVER).export(graph, document_version=1)
    second = HtmlExporter(RESOLVER).export(graph, document_version=1)
    assert first.to_bytes() == second.to_bytes()
    assert first.content_hash() == second.content_hash()


def test_export_hash_changes_with_document_version():
    graph = text_graph()
    v1 = HtmlExporter(RESOLVER).export(graph, document_version=1).content_hash()
    v2 = HtmlExporter(RESOLVER).export(graph, document_version=2).content_hash()
    assert v1 != v2


def test_manifest_records_hashes_fonts_and_licenses():
    graph, _ = asset_graph()
    manifest = HtmlExporter(RESOLVER).export(graph, document_version=4).read_json("manifest.json")
    assert manifest["contentHashes"]["index.html"]
    assert manifest["archiveHash"]
    assert manifest["fonts"][0]["family"] == "system-ui"
    assert manifest["fonts"][0]["redistributionPermission"] == "not-required"
    assert manifest["licenses"][0]["id"] == "html-office-export"
    assert manifest["degradation"]["network"] == "offline"
    assert manifest["layoutRegistryVersion"] == "1.0.0"
