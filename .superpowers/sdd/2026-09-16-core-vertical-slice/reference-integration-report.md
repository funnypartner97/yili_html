# Reference Pattern Integration Report

Date: 2026-09-16

## Status

Completed as a documentation-and-requirements amendment only. No application code, dependency, template, asset, prompt, or runtime implementation was added.

## Files amended

- `docs/superpowers/specs/2026-09-16-ai-native-html-office-platform-design.md`
- `docs/superpowers/plans/2026-09-16-core-vertical-slice.md`
- `.superpowers/sdd/2026-09-16-core-vertical-slice/reference-integration-report.md`

## Integrated decisions

- Reframed the platform as a shared live-document core plus Presentation Pack and Data Visualization Pack.
- Added stable slide IDs, a machine-readable layout registry with slot/capacity constraints, `MediaIntent`, notes/timing reservations, a fixed 1920×1080 uniformly scaled presentation stage, an independent semantic reflow view, and semantic/reduced-motion animation rules.
- Reserved `DatasetProfile`, `AnalyticIntent`, auditable `ChartPlan`, `ChartSpec`/`EncodingSpec`, chart capacity/invariants, and `ChartFrame` provenance fields while keeping data/dashboard UI disabled in this slice.
- Distinguished Data/Explore, Dashboard/Glance, and Report/Story and moved their implementation into seven follow-on subprojects.
- Expanded `TemplatePackage` metadata and required future previews to use real artifact content.
- Defined the quality-gate order as schema, semantic/data invariants, layout capacity, browser geometry/safe areas, accessibility/contrast/reduced motion, then screenshot/export/offline checks, all with stable-ID repairable diagnostics.
- Required managed asset IDs/content hashes, local pinned runtime dependencies, self-hosted fonts with license records, strict message origins, no data-driven `innerHTML`, deterministic offline export, and accessible chart-table fallbacks.
- Recorded the clean-room/license boundary: Guizang AGPL-3.0; Frontend Slides root MIT with separate template/font/upstream verification; Lieflat Charts PolyForm Noncommercial. Copying reference templates, assets, prompts, or runtime code requires prior written approval.
- Amended Task 2, Task 8, and Task 10 without renumbering Tasks 1–10.
- Preserved the confirmed constraints: source/template required, no external data sources, single-user slice, mandatory plan confirmation, multi-select `outputModes`, all uploaded files included with no material-range control, and data/dashboard disabled in the current slice.

## Verification performed

- Checked the Git diff for whitespace errors.
- Confirmed the implementation plan still contains exactly Tasks 1 through 10 in order.
- Scanned both documents for placeholder markers and undefined follow-up language.
- Scanned for the preserved product constraints and the required presentation, visualization, asset, security, quality, and license terms.
- Reviewed the scope boundary so reserved visualization contracts do not introduce data/dashboard routes, screens, or runtime work into the core vertical slice.

## Concerns and follow-ups

- Legal review is still required before any future proposal to reuse reference code or assets; this amendment authorizes only clean-room implementation of abstract patterns.
- The Data Visualization Pack remains intentionally unimplemented. Its seven follow-on subprojects require separate approved specs and plans.
- Presenter/audience/rehearsal UI, template authoring/previews, HTML import, and PDF/image export remain outside this vertical slice even though their compatible contract or security boundaries are documented.
