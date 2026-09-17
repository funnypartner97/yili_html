import type { Block, TableData } from "@html-office/contracts";

import { DataTable } from "./TableBlock";

/** Marks the basic bundled renderer can draw offline from the table fallback. */
const BASIC_MARKS = new Set(["bar", "line", "area", "point"]);

interface Series {
  labels: string[];
  values: number[];
}

/** Derives a single numeric series from the contract table fallback. */
function seriesFrom(table: TableData): Series | null {
  if (table.columns.length < 2 || table.rows.length === 0) return null;
  const valueIndex = table.columns.length - 1;
  const labels: string[] = [];
  const values: number[] = [];
  for (const row of table.rows) {
    const raw = row[valueIndex];
    const numeric = typeof raw === "number" ? raw : Number(raw);
    if (!Number.isFinite(numeric)) continue;
    labels.push(String(row[0] ?? ""));
    values.push(numeric);
  }
  return values.length > 0 ? { labels, values } : null;
}

const VIEW_W = 640;
const VIEW_H = 320;
const PAD = { top: 16, right: 16, bottom: 40, left: 48 };

/**
 * A pinned, locally bundled SVG renderer for basic charts. It draws only from the
 * contract's table fallback — never from a CDN global and never via innerHTML —
 * and is purely decorative: the accessible frame and semantic table below remain
 * the source of truth for assistive technology.
 */
function BasicChart({ mark, series }: { mark: string; series: Series }) {
  const { values } = series;
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const innerW = VIEW_W - PAD.left - PAD.right;
  const innerH = VIEW_H - PAD.top - PAD.bottom;
  const stepX = values.length > 1 ? innerW / (values.length - 1) : innerW;
  const barW = Math.max(4, (innerW / values.length) * 0.6);

  const x = (index: number) => PAD.left + (values.length > 1 ? index * stepX : innerW / 2);
  const y = (value: number) => PAD.top + innerH - ((value - min) / span) * innerH;

  const points = values.map((value, index) => `${x(index)},${y(value)}`).join(" ");
  const baselineY = y(Math.max(min, 0));
  const bandW = innerW / values.length;

  return (
    <svg
      className="chart-svg"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      role="img"
      aria-hidden="true"
      focusable="false"
      preserveAspectRatio="xMidYMid meet"
    >
      <line x1={PAD.left} y1={baselineY} x2={VIEW_W - PAD.right} y2={baselineY} className="chart-axis" />
      {mark === "bar" && values.map((value, index) => (
        <rect
          key={index}
          x={PAD.left + bandW * index + (bandW - barW) / 2}
          y={Math.min(y(value), baselineY)}
          width={barW}
          height={Math.abs(baselineY - y(value))}
          className="chart-bar"
        />
      ))}
      {(mark === "line" || mark === "area") && (
        <polyline points={points} className="chart-line" fill="none" />
      )}
      {mark === "area" && (
        <polygon
          points={`${PAD.left},${baselineY} ${points} ${x(values.length - 1)},${baselineY}`}
          className="chart-area"
        />
      )}
      {(mark === "point" || mark === "line") && values.map((value, index) => (
        <circle key={index} cx={x(index)} cy={y(value)} r={4} className="chart-point" />
      ))}
    </svg>
  );
}

/**
 * Charts render through their accessible frame in the editor: an optional basic
 * bundled SVG, the claim, the semantic explanation, and the contract-mandated
 * table fallback.
 */
export default function ChartBlock({ block }: { block: Extract<Block, { kind: "chart" }> }) {
  const frame = block.frame;
  const mark = block.chart.mark;
  const series = BASIC_MARKS.has(mark) ? seriesFrom(frame.tableFallback) : null;
  return (
    <figure className="chart-block" aria-label={frame.title}>
      <header>
        <h4>{frame.title}</h4>
        <p>{block.chart.semanticExplanation}</p>
      </header>
      {series
        ? <BasicChart mark={mark} series={series} />
        : <p className="chart-unsupported">该图表类型将在数据可视化能力开放后渲染，当前以数据表呈现。</p>}
      <p className="chart-claim">{frame.claim}</p>
      <div className="chart-table"><DataTable table={frame.tableFallback} /></div>
    </figure>
  );
}
