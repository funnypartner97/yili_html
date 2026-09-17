"""Deterministic, self-contained standalone HTML export.

The exporter renders semantic HTML from the document graph using text/attribute
escaping (never `innerHTML` with user content), inlines a versioned product CSS,
copies only manifest-declared managed assets into `assets/`, pre-renders basic
charts to static SVG with a bundled renderer, and embeds chart data as
non-executable JSON. There are no external runtime dependencies, no CDN
references, and no `javascript:` URLs. For the same document version and export
profile the archive is byte-for-byte stable: the ZIP uses fixed entry ordering and
timestamps, and no volatile timestamp is written into any content-addressed file.
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import zipfile

from src.documents.contracts import CORE_LAYOUTS
from src.exports.assets import AssetResolver, PreparedAsset, collect_assets

EXPORTER_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
FONT_STACK = ('system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", '
              '"Helvetica Neue", Arial, sans-serif')
# Fixed 1980-01-01 ZIP timestamps keep the archive byte-stable across runs.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

PRODUCT_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; font-family: __FONT_STACK__; line-height: 1.7; color: #1d1d1f; background: #fff; }
main { max-width: 860px; margin: 0 auto; padding: 48px 24px 96px; }
h1 { font-size: 34px; line-height: 1.25; margin: 0 0 8px; }
h2 { font-size: 24px; margin: 36px 0 10px; }
h3 { font-size: 19px; margin: 20px 0 8px; }
p { margin: 10px 0; }
.subtitle { color: #6e6e73; margin: 0 0 24px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 15px; }
th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid rgba(0,0,0,0.1); }
th { background: #f5f5f7; font-weight: 600; }
figure { margin: 16px 0; padding: 16px; border: 1px solid rgba(0,0,0,0.1); border-radius: 12px; }
figcaption { font-weight: 600; margin-bottom: 8px; }
.chart-summary { color: #6e6e73; }
.chart-asof { font-size: 13px; color: #86868b; }
.metric { font-size: 18px; }
img { max-width: 100%; height: auto; display: block; }
.svg-chart { width: 100%; height: auto; }
.svg-chart .axis { stroke: rgba(0,0,0,0.2); stroke-width: 2; }
.svg-chart .bar { fill: #0071e3; }
.svg-chart .line { stroke: #0071e3; stroke-width: 3; fill: none; }
.svg-chart .area { fill: rgba(0,113,227,0.16); }
.svg-chart .point { fill: #0071e3; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
""".replace("__FONT_STACK__", FONT_STACK)


class ExportArchive:
    """An in-memory, deterministic file archive."""

    def __init__(self, files: dict[str, bytes]):
        self._files = files

    def names(self) -> list[str]:
        return sorted(self._files)

    def exists(self, name: str) -> bool:
        return name in self._files

    def read_bytes(self, name: str) -> bytes:
        return self._files[name]

    def read_text(self, name: str) -> str:
        return self._files[name].decode("utf-8")

    def read_json(self, name: str) -> dict:
        return json.loads(self.read_text(name))

    def to_bytes(self) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(self._files):
                info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, self._files[name])
        return buffer.getvalue()

    def content_hash(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_island(value: object) -> str:
    """JSON for embedding inside a <script type="application/json"> block.

    Escaping the closing-tag sequence prevents any user/model text from breaking
    out of the script context; the payload stays non-executable data.
    """
    return _json(value).replace("</", "<\\/")


# --- bundled basic chart renderer (static SVG) -------------------------------
_VIEW_W, _VIEW_H = 640, 320
_PAD = {"top": 16, "right": 16, "bottom": 40, "left": 48}
_BASIC_MARKS = {"bar", "line", "area", "point"}


def _series(table: dict) -> tuple[list[str], list[float]] | None:
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    if len(columns) < 2 or not rows:
        return None
    value_index = len(columns) - 1
    labels: list[str] = []
    values: list[float] = []
    for row in rows:
        try:
            numeric = float(row[value_index])
        except (TypeError, ValueError, IndexError):
            continue
        labels.append(str(row[0]) if row else "")
        values.append(numeric)
    return (labels, values) if values else None


def _render_chart_svg(mark: str, table: dict) -> str:
    series = _series(table)
    if not series or mark not in _BASIC_MARKS:
        return ""
    _, values = series
    vmax, vmin = max(*values, 0.0), min(*values, 0.0)
    span = (vmax - vmin) or 1.0
    inner_w = _VIEW_W - _PAD["left"] - _PAD["right"]
    inner_h = _VIEW_H - _PAD["top"] - _PAD["bottom"]
    step_x = inner_w / (len(values) - 1) if len(values) > 1 else inner_w
    band_w = inner_w / len(values)
    bar_w = max(4.0, band_w * 0.6)

    def x(index: int) -> float:
        return _PAD["left"] + (index * step_x if len(values) > 1 else inner_w / 2)

    def y(value: float) -> float:
        return _PAD["top"] + inner_h - ((value - vmin) / span) * inner_h

    baseline = y(max(vmin, 0.0))
    parts = [f'<svg class="svg-chart" viewBox="0 0 {_VIEW_W} {_VIEW_H}" role="img" '
             f'aria-hidden="true" preserveAspectRatio="xMidYMid meet">',
             f'<line class="axis" x1="{_PAD["left"]}" y1="{baseline:.2f}" '
             f'x2="{_VIEW_W - _PAD["right"]}" y2="{baseline:.2f}" />']
    if mark == "bar":
        for index, value in enumerate(values):
            bx = _PAD["left"] + band_w * index + (band_w - bar_w) / 2
            by = min(y(value), baseline)
            parts.append(f'<rect class="bar" x="{bx:.2f}" y="{by:.2f}" '
                         f'width="{bar_w:.2f}" height="{abs(baseline - y(value)):.2f}" />')
    points = " ".join(f"{x(i):.2f},{y(v):.2f}" for i, v in enumerate(values))
    if mark in ("line", "area"):
        parts.append(f'<polyline class="line" points="{points}" />')
    if mark == "area":
        parts.append(f'<polygon class="area" points="{_PAD["left"]:.2f},{baseline:.2f} '
                     f'{points} {x(len(values) - 1):.2f},{baseline:.2f}" />')
    if mark in ("point", "line"):
        for index, value in enumerate(values):
            parts.append(f'<circle class="point" cx="{x(index):.2f}" cy="{y(value):.2f}" r="4" />')
    parts.append("</svg>")
    return "".join(parts)


# --- block rendering ---------------------------------------------------------
def _render_table(table: dict, name: str) -> str:
    columns = table.get("columns", [])
    head = "".join(f"<th scope=\"col\">{_e(column)}</th>" for column in columns)
    body_rows = []
    for row in table.get("rows", []):
        cells = "".join(f"<td>{_e(cell)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    return (f'<table aria-label="{_e(name)}"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table>')


def _render_block(block: dict, assets: dict[str, PreparedAsset], section_title: str) -> str:
    kind = block.get("kind")
    if kind == "richText":
        paragraphs = [line.strip() for line in str(block.get("text", "")).split("\n") if line.strip()]
        return "".join(f"<p>{_e(line)}</p>" for line in paragraphs) or "<p></p>"
    if kind == "table":
        return _render_table(block.get("table", {}), f"{section_title} 数据表")
    if kind == "metric":
        return (f'<p class="metric"><strong>{_e(block.get("label"))}</strong>：'
                f'{_e(block.get("value"))}{_e(block.get("unit"))}</p>')
    if kind == "chart":
        frame = block.get("frame", {})
        title = frame.get("title", "")
        svg = _render_chart_svg(block.get("chart", {}).get("mark", ""), frame.get("tableFallback", {}))
        sources = "；".join(reference.get("locator", "") for reference in frame.get("source", []))
        return (f'<figure><figcaption>{_e(title)}</figcaption>'
                f'<p class="chart-summary">{_e(block.get("chart", {}).get("semanticExplanation"))}</p>'
                f'{svg}'
                f'<p class="chart-claim">{_e(frame.get("claim"))}</p>'
                f'{_render_table(frame.get("tableFallback", {}), title)}'
                f'<p class="chart-asof">数据截至 {_e(frame.get("asOf"))}｜来源：{_e(sources)}</p>'
                f'</figure>')
    if kind == "image":
        prepared = assets.get(block.get("assetId"))
        if not prepared:
            return ""
        caption = f"<figcaption>{_e(prepared.caption)}</figcaption>" if prepared.caption else ""
        return (f'<figure><img src="{_e(prepared.path)}" alt="{_e(prepared.alt)}" '
                f'width="1280" height="720" loading="lazy" decoding="async" />{caption}</figure>')
    return ""


class HtmlExporter:
    def __init__(self, resolver: AssetResolver, *, profile: str = "standalone-html"):
        self.resolver = resolver
        self.profile = profile

    def export(self, graph: dict, *, document_version: int = 0) -> ExportArchive:
        prepared = collect_assets(graph, self.resolver)
        assets = {item.asset_id: item for item in prepared}

        sections = sorted(graph.get("sections", []), key=lambda section: section.get("order", 0))
        body: list[str] = []
        chart_data: list[dict] = []
        for section in sections:
            title = section.get("title") or "章节"
            blocks = sorted(section.get("blocks", []), key=lambda block: block.get("order", 0))
            rendered = "".join(_render_block(block, assets, title) for block in blocks)
            body.append(f'<section aria-label="{_e(title)}"><h2>{_e(title)}</h2>{rendered}</section>')
            for block in blocks:
                if block.get("kind") == "chart":
                    frame = block.get("frame", {})
                    chart_data.append({
                        "id": block.get("chart", {}).get("id"),
                        "mark": block.get("chart", {}).get("mark"),
                        "title": frame.get("title"),
                        "asOf": frame.get("asOf"),
                        "source": frame.get("source"),
                        "tableFallback": frame.get("tableFallback"),
                    })

        title = graph.get("title", "文档")
        head_scripts = ""
        if chart_data:
            # Non-executable JSON island; no inline executable chart code is required
            # because charts are pre-rendered to static SVG above.
            head_scripts = (f'<script type="application/json" id="chart-data">{_json_island(chart_data)}</script>')

        index_html = (
            "<!DOCTYPE html>\n"
            '<html lang="zh-CN">\n<head>\n'
            '<meta charset="utf-8" />\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
            f"<title>{_e(title)}</title>\n"
            f"<style>{PRODUCT_CSS}</style>\n"
            "</head>\n<body>\n<main>\n"
            f'<article class="document" aria-label="{_e(title)}">\n'
            f"<header><h1>{_e(title)}</h1>"
            f'<p class="subtitle">独立 HTML 导出 · 版本 {document_version}</p></header>\n'
            f"{''.join(body)}\n"
            "</article>\n</main>\n"
            f"{head_scripts}\n"
            "</body>\n</html>\n"
        )

        files: dict[str, bytes] = {"index.html": index_html.encode("utf-8")}
        for item in prepared:
            files[item.path] = item.data

        # Hash the content files (excluding the manifest) so the manifest can record
        # a stable archive digest without self-reference.
        content_hashes = {name: hashlib.sha256(files[name]).hexdigest() for name in sorted(files)}
        archive_hash = hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest()
        manifest = {
            "artifactId": graph.get("artifactId"),
            "documentVersion": document_version,
            "schemaVersion": SCHEMA_VERSION,
            "layoutRegistryVersion": CORE_LAYOUTS.get("version"),
            "templatePackageVersion": EXPORTER_VERSION,
            "exportProfile": self.profile,
            "renderer": {"name": "html-office-export", "version": EXPORTER_VERSION},
            "fonts": [{
                "family": "system-ui",
                "stack": FONT_STACK,
                "embedded": False,
                "fileHash": None,
                "codepointCoverage": "system",
                "fallback": ["sans-serif"],
                "licenseId": "system-ui",
                "noticePath": None,
                "redistributionPermission": "not-required",
            }],
            "contentHashes": content_hashes,
            "archiveHash": archive_hash,
            "assets": [item.manifest_entry() for item in prepared],
            "dependencies": [],
            "licenses": [{
                "id": "html-office-export", "name": "HTML Office export renderer",
                "version": EXPORTER_VERSION, "license": "proprietary", "noticePath": None,
            }],
            "degradation": {"interaction": "static", "animation": "final-state",
                            "reducedMotion": "honored", "network": "offline"},
        }
        files["manifest.json"] = _json(manifest).encode("utf-8")
        return ExportArchive(files)
