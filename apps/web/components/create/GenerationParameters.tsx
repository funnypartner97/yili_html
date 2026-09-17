"use client";

import type { GenerationParametersValue } from "../../lib/api/types";
import { DEFAULT_GENERATION_PARAMETERS } from "../../lib/api/types";

export { DEFAULT_GENERATION_PARAMETERS };

const OUTPUT_MODES = [
  { id: "document", label: "文档", enabled: true },
  { id: "presentation", label: "演示", enabled: true },
  { id: "data", label: "数据", enabled: false },
  { id: "dashboard", label: "看板", enabled: false },
] as const;

const LENGTH_PRESETS = [
  { id: "short", label: "精简" },
  { id: "standard", label: "标准" },
  { id: "long", label: "详尽" },
] as const;

const DENSITIES = [
  { id: "sparse", label: "疏朗" },
  { id: "balanced", label: "均衡" },
  { id: "dense", label: "紧凑" },
] as const;

const OUTPUT_SPECS = [
  { id: "responsive", label: "自适应" },
  { id: "fixed", label: "固定" },
] as const;

interface Props {
  value: GenerationParametersValue;
  onChange: (value: GenerationParametersValue) => void;
  disabled?: boolean;
}

export default function GenerationParameters({ value, onChange, disabled = false }: Props) {
  function patch(patchValue: Partial<GenerationParametersValue>) {
    onChange({ ...value, ...patchValue });
  }

  function toggleMode(mode: "document" | "presentation") {
    const next = value.outputModes.includes(mode)
      ? value.outputModes.filter((item) => item !== mode)
      : [...value.outputModes, mode];
    if (next.length === 0) return;
    patch({ outputModes: next });
  }

  return (
    <fieldset className="generation-parameters" disabled={disabled}>
      <legend>生成参数</legend>

      <div className="parameter-group">
        <span className="parameter-label">产物形式</span>
        <div className="mode-chips">
          {OUTPUT_MODES.map((mode) => (
            <span key={mode.id} className="mode-chip">
              <label className={mode.enabled ? undefined : "mode-locked"}>
                <input
                  type="checkbox"
                  checked={value.outputModes.includes(mode.id as "document" | "presentation")}
                  onChange={() => mode.enabled && toggleMode(mode.id as "document" | "presentation")}
                  disabled={disabled || !mode.enabled}
                />
                {mode.label}
              </label>
              {!mode.enabled && <small>后续开放</small>}
            </span>
          ))}
        </div>
      </div>

      <div className="parameter-group">
        <label className="parameter-label" htmlFor="audience">受众</label>
        <input
          id="audience"
          type="text"
          value={value.audience}
          placeholder="为谁创作这份成果"
          onChange={(event) => patch({ audience: event.target.value })}
        />
      </div>

      <div className="parameter-group">
        <span className="parameter-label">篇幅</span>
        {LENGTH_PRESETS.map((preset) => (
          <label key={preset.id}>
            <input
              type="radio"
              name="length-preset"
              checked={value.lengthPreset === preset.id}
              onChange={() => patch({ lengthPreset: preset.id })}
            />
            {preset.label}
          </label>
        ))}
      </div>

      <div className="parameter-group">
        <span className="parameter-label">信息密度</span>
        {DENSITIES.map((density) => (
          <label key={density.id}>
            <input
              type="radio"
              name="density"
              checked={value.density === density.id}
              onChange={() => patch({ density: density.id })}
            />
            {density.label}
          </label>
        ))}
      </div>

      <div className="parameter-group">
        <span className="parameter-label">输出规格</span>
        {OUTPUT_SPECS.map((spec) => (
          <label key={spec.id}>
            <input
              type="radio"
              name="output-spec"
              checked={value.outputSpec === spec.id}
              onChange={() => patch({ outputSpec: spec.id })}
            />
            {spec.label}
          </label>
        ))}
      </div>

      <div className="parameter-group">
        <label className="parameter-label" htmlFor="emphasis">侧重点（每行一条）</label>
        <textarea
          id="emphasis"
          rows={3}
          value={value.emphasis.join("\n")}
          onChange={(event) => patch({
            emphasis: event.target.value.split("\n").map((line) => line.trim()).filter(Boolean),
          })}
        />
      </div>
    </fieldset>
  );
}
