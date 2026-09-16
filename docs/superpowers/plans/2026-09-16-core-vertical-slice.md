# Core Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable single-user flow on the shared live-document core that turns uploaded business files into a user-approved generation plan, then into an editable document and Presentation Pack view that can be exported as standalone HTML.

**Architecture:** Use a pnpm monorepo with a Next.js web application, a FastAPI application/worker service, shared JSON Schema contracts, PostgreSQL persistence, Redis-backed jobs, and S3-compatible object storage. The shared live-document core owns stable content, asset, template, command, and version contracts; the Presentation Pack renders a fixed 1920×1080 logical stage plus a separate semantic reading view. AI providers emit structured plans, document graphs, and edit commands; layered validators run before storage, rendering, and deterministic export. Data Visualization Pack contracts are reserved, while data/dashboard UI and runtime remain out of scope.

**Tech Stack:** Node.js 26, pnpm 10.33, Next.js 16.3.5, React 19.3, TypeScript 7.0.2, Tiptap 3.31.3, TanStack Query 5.103, Zod 4.6.5, Vitest 5.0.1, Playwright 1.63; Python 3.14, FastAPI 0.141.1, Pydantic 2.13.5, SQLAlchemy 2.0.54, Alembic 1.20, ARQ 0.28, PostgreSQL, Redis, MinIO, PyMuPDF 1.28.2, python-docx 1.2.0, python-pptx 1.0.2, openpyxl 3.1.5, OpenAI-compatible Python SDK 3.14.1, pytest 9.1.1.

**Spec:** `docs/superpowers/specs/2026-09-16-ai-native-html-office-platform-design.md`

## Global Constraints

- The repository is currently empty and unversioned; Task 1 initializes Git and the monorepo.
- The core slice is single-user and has no workspace, member, permission, comment, approval, billing, or commercialization features.
- A generation request is invalid unless it contains at least one successfully parsed source file or a template reference.
- Every generation requires a persisted plan and an explicit confirmation request before a generation job can be queued.
- `outputModes` is a non-empty multi-select array. This slice enables `document` and `presentation`; `data` and `dashboard` remain reserved enum values and are disabled in the UI.
- All files uploaded to an artifact participate in planning. There is no material-range parameter.
- The system does not connect to databases, APIs, or SaaS data sources.
- HTML import, PDF/image export, personal template authoring, and enterprise collaboration belong to later plans.
- AI output never writes arbitrary executable HTML or JavaScript. It must validate against shared JSON Schema before persistence.
- Reference repositories are untrusted inspiration only. Implement all schemas, visuals, validators, and runtime behavior independently; do not copy Guizang (AGPL-3.0), Lieflat Charts (PolyForm Noncommercial), or Frontend Slides templates/assets/prompts/runtime code without written approval. Frontend Slides root MIT does not establish the licenses of its template pack, fonts, or upstream assets.
- All render assets use managed IDs and SHA-256 content hashes. Runtime/export packages use pinned local dependencies and self-hosted fonts with license records; no CDN globals are allowed.
- Template previews, when introduced in a later slice, must render the requesting artifact's real content rather than palette swatches or generic examples.
- Upload limits for the slice are 10 files per artifact and 50 MiB per file. Accepted types are PDF, DOCX, PPTX, XLSX, CSV, PNG, and JPEG; images are stored and indexed by metadata but OCR is not part of this slice.
- API timestamps are UTC ISO 8601 strings; identifiers are UUIDv7 strings; API JSON uses camelCase.

## Repository Map

```text
.
├── apps/
│   └── web/
│       ├── app/                       # Next.js routes and layouts
│       ├── components/create/         # Composer, upload, parameters, plan confirmation
│       ├── components/editor/         # Document tree, canvas, inspector, AI panel
│       ├── components/presentation/   # Fixed PresentationStage and semantic reading view
│       ├── lib/api/                   # Typed HTTP client and query hooks
│       └── tests/                     # Vitest and Playwright tests
├── packages/
│   └── contracts/
│       ├── schemas/                   # Canonical JSON Schemas
│       ├── registries/                # Versioned layout/template capability fixtures
│       ├── src/                       # Generated TS types and Zod wrappers
│       └── tests/                     # Contract fixtures and schema tests
├── services/
│   └── api/
│       ├── src/api/                   # FastAPI routers and request/response models
│       ├── src/core/                  # Settings, errors, logging, identifiers
│       ├── src/db/                    # SQLAlchemy models, sessions, repositories
│       ├── src/files/                 # Object storage and file parsers
│       ├── src/generation/            # Provider interfaces, prompts, orchestration
│       ├── src/documents/             # Validation, command application, versions
│       ├── src/exports/               # Standalone HTML renderer
│       ├── src/quality/               # Layered semantic, geometry, a11y, offline/export gates
│       ├── src/worker/                 # ARQ job entry points
│       ├── migrations/                # Alembic revisions
│       └── tests/                     # Unit, integration, and API tests
├── tests/e2e/                          # Full-stack Playwright scenarios
├── docker-compose.yml                  # PostgreSQL, Redis, MinIO
├── pnpm-workspace.yaml
├── package.json
└── .env.example
```

---

### Task 1: Bootstrap the Monorepo and Local Runtime

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `docker-compose.yml`
- Create: `apps/web/package.json`
- Create: `apps/web/app/page.tsx`
- Create: `apps/web/vitest.config.ts`
- Create: `services/api/pyproject.toml`
- Create: `services/api/src/main.py`
- Create: `services/api/tests/test_health.py`
- Create: `README.md`

**Interfaces:**
- Produces: `GET /healthz -> {"status":"ok"}`.
- Produces: root scripts `dev`, `test`, `lint`, `typecheck`, and `e2e`.
- Produces: local services on PostgreSQL `5432`, Redis `6379`, MinIO API `9000`, and MinIO console `9001`.

- [ ] **Step 1: Initialize Git and workspace metadata**

```powershell
git init -b main
pnpm init
```

Use `apply_patch` to create `pnpm-workspace.yaml` with `apps/*` and `packages/*`, then replace the generated root `package.json` with scripts that run `pnpm --filter web` and `uv run --project services/api`; set `packageManager` to `pnpm@10.33.0`.

- [ ] **Step 2: Create the failing API health test**

```python
# services/api/tests/test_health.py
from fastapi.testclient import TestClient
from src.main import app

def test_healthz() -> None:
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: Run the health test and verify failure**

Run: `uv run --project services/api pytest services/api/tests/test_health.py -v`  
Expected: FAIL because `src.main` or `app` does not exist.

- [ ] **Step 4: Implement the minimal FastAPI application**

```python
# services/api/src/main.py
from fastapi import FastAPI

app = FastAPI(title="HTML Office API", version="0.1.0")

@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

Create `services/api/pyproject.toml` with Python `>=3.14,<3.15`, the pinned runtime dependencies from the header, and pytest configuration containing `pythonpath = ["."]`.

- [ ] **Step 5: Scaffold the Next.js application and smoke test**

Run:

```powershell
pnpm create next-app@16.3.5 apps/web --ts --eslint --app --src-dir=false --use-pnpm --import-alias "@/*"
pnpm --filter web add @tanstack/react-query@5.103.0 zod@4.6.5
pnpm --filter web add -D vitest@5.0.1 @testing-library/react @testing-library/jest-dom jsdom
```

Create `apps/web/app/page.tsx` that renders the heading `把材料变成可编辑成果` and two disabled actions, `添加材料` and `选择模板`.

- [ ] **Step 6: Define local infrastructure**

Create `docker-compose.yml` with named volumes and health checks for `postgres:17-alpine`, `redis:8-alpine`, and `minio/minio:RELEASE.2025-09-07T16-13-09Z`. Create a one-shot `minio-init` service that creates the private bucket `html-office`.

- [ ] **Step 7: Verify the bootstrap**

Run:

```powershell
docker compose up -d --wait
pnpm install
pnpm test
pnpm typecheck
```

Expected: health test passes, web smoke test passes, TypeScript check exits 0, and all three infrastructure services report healthy.

- [ ] **Step 8: Commit the bootstrap**

```powershell
git add .
git commit -m "chore: bootstrap html office monorepo"
```

---

### Task 2: Define the Shared Document and Plan Contracts

**Files:**
- Create: `packages/contracts/package.json`
- Create: `packages/contracts/schemas/document-graph.schema.json`
- Create: `packages/contracts/schemas/generation-plan.schema.json`
- Create: `packages/contracts/schemas/edit-command.schema.json`
- Create: `packages/contracts/schemas/presentation.schema.json`
- Create: `packages/contracts/schemas/layout-registry.schema.json`
- Create: `packages/contracts/schemas/template-package.schema.json`
- Create: `packages/contracts/schemas/data-visualization.schema.json`
- Create: `packages/contracts/registries/core-presentation-layouts.json`
- Create: `packages/contracts/src/index.ts`
- Create: `packages/contracts/tests/fixtures.ts`
- Create: `packages/contracts/tests/contracts.test.ts`
- Create: `services/api/src/documents/contracts.py`
- Create: `services/api/tests/documents/test_contracts.py`

**Interfaces:**
- Produces: `OutputMode = "document" | "presentation" | "data" | "dashboard"`.
- Produces: `DocumentGraph`, `GenerationPlan`, `EditCommand`, `PresentationDocument`, `LayoutRegistry`, `MediaIntent`, `TemplatePackage`, `DatasetProfile`, `AnalyticIntent`, `ChartPlan`, `ChartSpec`, `EncodingSpec`, and `ChartFrame` TypeScript types.
- Produces: matching Pydantic models for every shared TypeScript type, including the reserved presentation, template, and data-visualization contracts, with camelCase JSON aliases.
- Reserves Data Visualization Pack types for future plans; no endpoint or UI in this slice may enable `data` or `dashboard`.

- [ ] **Step 1: Write failing TypeScript contract tests**

```ts
import { describe, expect, it } from "vitest";
import {
  DocumentGraphSchema,
  GenerationPlanSchema,
  LayoutRegistrySchema,
} from "../src";
import { presentationGraphFixture } from "./fixtures";

describe("GenerationPlanSchema", () => {
  it("accepts multiple enabled output modes", () => {
    const result = GenerationPlanSchema.parse({
      artifactId: "01993f2f-2b79-7000-8000-000000000001",
      outputModes: ["document", "presentation"],
      audience: "管理层",
      lengthPreset: "standard",
      density: "balanced",
      outputSpec: "responsive",
      emphasis: ["利润变化"],
      outline: [{ id: "summary", title: "执行摘要" }],
      sourceSummary: { parsed: 2, failed: 0, conflicts: [] },
    });
    expect(result.outputModes).toHaveLength(2);
  });

  it("binds stable slide ids to registered layouts, media, notes, and timing", () => {
    const registry = LayoutRegistrySchema.parse({
      version: "1.0.0",
      layouts: [{
        id: "title-media",
        slideKinds: ["content"],
        slots: [
          { id: "title", kind: "text", required: true, maxItems: 1, maxChars: 90 },
          { id: "hero", kind: "media", required: true, maxItems: 1, aspectRatios: ["16:9"] },
        ],
        safeArea: { top: 48, right: 48, bottom: 72, left: 48 },
        exportSupport: ["html"],
      }],
    });
    const graph = DocumentGraphSchema.parse(presentationGraphFixture);
    expect(registry.layouts[0].id).toBe(graph.presentation?.slides[0].layoutId);
    expect(graph.presentation?.slides[0].speakerNotes?.slideId)
      .toBe(graph.presentation?.slides[0].id);
    expect(graph.presentation?.stage).toEqual({ width: 1920, height: 1080 });
  });
});
```

- [ ] **Step 2: Run the contract test and verify failure**

Run: `pnpm --filter @html-office/contracts test`  
Expected: FAIL because schemas and exports do not exist.

- [ ] **Step 3: Implement canonical JSON Schemas and generated wrappers**

Define `DocumentGraph` with `schemaVersion`, `artifactId`, `title`, `outputModes`, `theme`, `assets`, `sections`, and optional `presentation`. Every section, slide, block, asset, slot assignment, note, animation target, and chart has a stable UUIDv7 identity; ordering is explicit and never inferred from an ID or page number. Define blocks as a discriminated union of `richText`, `table`, `metric`, `chart`, and `image`. Define edit commands as `replaceText`, `insertBlock`, `removeBlock`, `moveBlock`, and `setTheme`.

Define `PresentationDocument` as `{stage:{width:1920,height:1080}, slides}`. Each slide contains `{id,sectionId,kind,layoutId,slotAssignments,speakerNotes,timing,animationTimeline}`. `speakerNotes` reserves separate `talk`, `transition`, `interaction`, and `stageDirections` fields and binds by `slideId`; `timing` reserves `plannedSeconds`, `autoAdvanceSeconds`, and later rehearsal events. Animation entries contain a semantic intent, target stable IDs, tokenized duration/easing, and an export state; arbitrary JavaScript is invalid.

Define `LayoutRegistry` entries with `id`, supported slide kinds and languages, ordered slots, min/max items, text/line capacity, accepted media aspect ratios, reading order, safe areas, minimum font size, accessibility requirements, and export support. Define `MediaIntent` with `role`, `fidelity`, `slotId`, `targetAspectRatio`, `cropPolicy`, `subjectSafeArea`, `language`, `brandTokens`, `provenance`, `rights`, `alt`, and optional `caption`. Reject unknown `layoutId`, unknown `slotId`, duplicate IDs, note/slide mismatches, slot over-capacity, and non-1920×1080 stages in this pack version.

Define `TemplatePackage` metadata with `modes`, `formality`, `density`, `readingSpeed`, `languageCoverage`, `layoutCapabilities`, `chartCapabilities`, semantic `tokens`, `validators`, `exportSupport`, pinned `dependencies`, and per-asset/font `licenseMetadata`. The schema is reserved in this slice; personal template authoring and preview UI remain later work, and any future preview must use real artifact content.

Define reserved Data Visualization Pack contracts: `DatasetProfile` (field types, cardinality, null/invalid counts, timezone, units, aggregation provenance, sensitivity, sampling), `AnalyticIntent` (question, audience, reading speed, surface, interaction, accessibility, offline), auditable `ChartPlan` (selected candidate, alternatives, scores, reasons, expected marks, fallback, invariant results), `ChartSpec`/`EncodingSpec` (mark, channel bindings, aggregation, scale/domain/baseline, sorting, filters, calculations, semantic explanation), and `ChartFrame` (`title`, `description`, `source`, `asOf`, optional `methodology`, `caveats`, `claim`, accessible table fallback). Include discriminated invariants/capacity for composition, proportional bars, OHLC, hierarchy, network, and map, but do not implement a chart recommender or data/dashboard screens in this slice.

Use `json-schema-to-typescript` during `pnpm --filter @html-office/contracts generate`, then wrap the generated types with Zod validators whose refinements enforce non-empty unique `outputModes` and stable unique block IDs.

- [ ] **Step 4: Mirror and test the contracts in Python**

```python
def test_plan_accepts_multiple_modes() -> None:
    plan = GenerationPlanModel.model_validate({
        "artifactId": "01993f2f-2b79-7000-8000-000000000001",
        "outputModes": ["document", "presentation"],
        "audience": "管理层",
        "lengthPreset": "standard",
        "density": "balanced",
        "outputSpec": "responsive",
        "emphasis": ["利润变化"],
        "outline": [{"id": "summary", "title": "执行摘要"}],
        "sourceSummary": {"parsed": 2, "failed": 0, "conflicts": []},
    })
    assert plan.output_modes == ["document", "presentation"]
```

Load the same JSON Schema files through `jsonschema` in Python tests so schema drift fails CI.

Add fixtures proving that a slide reorder preserves note bindings, an unregistered layout and over-capacity slot fail, a media item without provenance/rights/alt fails, a chart plan without rejected alternatives/reasons fails, and a `TemplatePackage` without dependency/license metadata fails. Add round-trip fixtures for every reserved data-visualization type while asserting the service's enabled modes remain only `document` and `presentation`.

- [ ] **Step 5: Verify both contract suites**

Run:

```powershell
pnpm --filter @html-office/contracts test
uv run --project services/api pytest services/api/tests/documents/test_contracts.py -v
```

Expected: all valid contract and cross-language round-trip fixtures pass; empty `outputModes`, duplicate stable IDs, layout/slot violations, incomplete media metadata, incomplete chart audit metadata, and incomplete template license metadata fail validation.

- [ ] **Step 6: Commit the contracts**

```powershell
git add packages/contracts services/api/src/documents services/api/tests/documents
git commit -m "feat: define document generation contracts"
```

---

### Task 3: Persist Artifacts, Plans, Jobs, Documents, and Versions

**Files:**
- Create: `services/api/src/core/settings.py`
- Create: `services/api/src/core/ids.py`
- Create: `services/api/src/db/session.py`
- Create: `services/api/src/db/models.py`
- Create: `services/api/src/db/repositories.py`
- Create: `services/api/src/api/artifacts.py`
- Create: `services/api/src/api/schemas.py`
- Create: `services/api/migrations/env.py`
- Create: `services/api/migrations/versions/0001_initial.py`
- Modify: `services/api/src/main.py`
- Create: `services/api/tests/api/test_artifacts.py`

**Interfaces:**
- Produces: `POST /v1/artifacts -> ArtifactResponse`.
- Produces: `GET /v1/artifacts/{artifactId} -> ArtifactResponse`.
- Produces: repository methods `create_artifact(title)`, `save_plan(plan)`, `save_document(graph, origin)`, and `get_versions(artifact_id)`.

- [ ] **Step 1: Write the failing artifact API test**

```python
def test_create_artifact(client) -> None:
    response = client.post("/v1/artifacts", json={"title": "季度经营分析"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "季度经营分析"
    assert body["status"] == "draft"
    assert body["sourceCount"] == 0
```

- [ ] **Step 2: Run the API test and verify failure**

Run: `uv run --project services/api pytest services/api/tests/api/test_artifacts.py -v`  
Expected: FAIL with HTTP 404 for `/v1/artifacts`.

- [ ] **Step 3: Implement database models and migration**

Create SQLAlchemy models for `artifacts`, `source_files`, `generation_plans`, `jobs`, and `artifact_versions`. Store plan and document payloads in PostgreSQL JSONB. Add unique constraints on `(artifact_id, version_number)` and indexes on artifact status, source parse status, and job status.

Use Python 3.14 `uuid.uuid7()` and expose IDs as strings. Artifact statuses are `draft`, `planning`, `plan_ready`, `generating`, `editable`, and `failed`.

- [ ] **Step 4: Implement repositories and API routes**

```python
@router.post("", response_model=ArtifactResponse, status_code=201)
def create_artifact(payload: ArtifactCreate, session: SessionDep) -> ArtifactResponse:
    artifact = Artifact(title=payload.title, status="draft")
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return ArtifactResponse.from_model(artifact, source_count=0)
```

Map database constraint violations to stable API errors shaped as `{code, message, details}`.

- [ ] **Step 5: Verify persistence and migration**

Run:

```powershell
uv run --project services/api alembic upgrade head
uv run --project services/api pytest services/api/tests/api/test_artifacts.py -v
```

Expected: migration succeeds against the test database and artifact tests pass.

- [ ] **Step 6: Commit persistence**

```powershell
git add services/api
git commit -m "feat: persist artifacts and document versions"
```

---

### Task 4: Upload, Store, and Parse Source Files

**Files:**
- Create: `services/api/src/files/storage.py`
- Create: `services/api/src/files/types.py`
- Create: `services/api/src/files/parsers/base.py`
- Create: `services/api/src/files/parsers/pdf.py`
- Create: `services/api/src/files/parsers/docx.py`
- Create: `services/api/src/files/parsers/pptx.py`
- Create: `services/api/src/files/parsers/spreadsheet.py`
- Create: `services/api/src/files/parsers/image.py`
- Create: `services/api/src/files/service.py`
- Create: `services/api/src/api/files.py`
- Create: `services/api/tests/files/test_parsers.py`
- Create: `services/api/tests/api/test_file_upload.py`

**Interfaces:**
- Produces: `POST /v1/artifacts/{artifactId}/files` multipart upload.
- Produces: `GET /v1/artifacts/{artifactId}/files` with parse status.
- Produces: `ParsedSource {kind, title, segments, tables, images, metadata}` stored as JSONB.
- Consumes: artifact repository and S3-compatible object store settings.

- [ ] **Step 1: Write parser contract tests with generated fixtures**

```python
def test_xlsx_parser_extracts_sheet_and_cells(tmp_path) -> None:
    path = tmp_path / "sales.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sales"
    sheet.append(["Month", "Revenue"])
    sheet.append(["Jan", 120])
    workbook.save(path)

    parsed = SpreadsheetParser().parse(path)
    assert parsed.tables[0].name == "Sales"
    assert parsed.tables[0].rows[1] == ["Jan", 120]
```

Add equivalent generated fixtures for PDF text, DOCX headings, PPTX slide text, CSV cells, and PNG dimensions.

- [ ] **Step 2: Run parser tests and verify failure**

Run: `uv run --project services/api pytest services/api/tests/files/test_parsers.py -v`  
Expected: FAIL because parser classes do not exist.

- [ ] **Step 3: Implement parser adapters**

Each parser returns the same `ParsedSource` model. Preserve source locators as `{page}`, `{slide}`, `{paragraph}`, or `{sheet,row,column}` so generated content can cite its origin. Spreadsheet formulas are stored as formula text plus cached value when available; the service does not execute macros.

- [ ] **Step 4: Implement upload validation and storage**

Stream uploads to a temporary file while computing SHA-256, reject files above 50 MiB and artifacts already containing 10 files, validate content signatures rather than filename only, then upload to `artifacts/{artifactId}/sources/{sourceId}/{safeFilename}`. Never interpolate user filenames into filesystem paths.

- [ ] **Step 5: Implement and test the upload API**

```python
def test_upload_requires_supported_signature(client, artifact_id) -> None:
    response = client.post(
        f"/v1/artifacts/{artifact_id}/files",
        files={"file": ("report.pdf", b"not-a-pdf", "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_file_signature"
```

The successful response returns HTTP 202 and `{sourceId, parseStatus:"queued"}`; the worker updates status to `parsed` or `failed` with a user-facing reason.

- [ ] **Step 6: Verify all file tests**

Run: `uv run --project services/api pytest services/api/tests/files services/api/tests/api/test_file_upload.py -v`  
Expected: all parser, signature, size, count, storage-key, and failure-state tests pass.

- [ ] **Step 7: Commit file ingestion**

```powershell
git add services/api/src/files services/api/src/api/files.py services/api/tests
git commit -m "feat: ingest and parse source files"
```

---

### Task 5: Generate and Update the Mandatory Production Plan

**Files:**
- Create: `services/api/src/generation/provider.py`
- Create: `services/api/src/generation/fake_provider.py`
- Create: `services/api/src/generation/openai_compatible.py`
- Create: `services/api/src/generation/prompts/plan.py`
- Create: `services/api/src/generation/planner.py`
- Create: `services/api/src/api/plans.py`
- Create: `services/api/tests/generation/test_planner.py`
- Create: `services/api/tests/api/test_plans.py`

**Interfaces:**
- Produces: `POST /v1/artifacts/{artifactId}/plans` from `{instruction, parameters}`.
- Produces: `PUT /v1/artifacts/{artifactId}/plans/{planId}` for user edits.
- Produces: `POST /v1/artifacts/{artifactId}/plans/{planId}/confirm` only after validation.
- Consumes: all successfully parsed files belonging to the artifact.

- [ ] **Step 1: Write failing planner rules tests**

```python
def test_planner_rejects_artifact_without_parsed_sources(planner, artifact) -> None:
    with pytest.raises(DomainError) as error:
        planner.create_plan(artifact.id, instruction="生成管理层汇报", parameters={})
    assert error.value.code == "source_required"

def test_planner_passes_every_parsed_source_to_provider(planner, provider, artifact_with_two_sources) -> None:
    planner.create_plan(artifact_with_two_sources.id, "生成报告", {"outputModes": ["document"]})
    assert provider.last_source_ids == artifact_with_two_sources.source_ids
```

- [ ] **Step 2: Run planner tests and verify failure**

Run: `uv run --project services/api pytest services/api/tests/generation/test_planner.py -v`  
Expected: FAIL because the planner does not exist.

- [ ] **Step 3: Implement the provider boundary and deterministic fake**

```python
class GenerationProvider(Protocol):
    async def create_plan(self, request: PlanProviderRequest) -> GenerationPlanModel: ...
    async def create_document(self, request: DocumentProviderRequest) -> DocumentGraphModel: ...
    async def create_edit_commands(self, request: EditProviderRequest) -> list[EditCommandModel]: ...
```

The fake provider returns fixture plans and document graphs for tests. The OpenAI-compatible adapter submits JSON Schema response formats and rejects non-conforming responses without attempting best-effort persistence.

- [ ] **Step 4: Implement planning rules**

Require one or more parsed sources, reject `data` or `dashboard` in this slice with `output_mode_not_enabled`, allow `document` and `presentation` together, and include source summaries, conflicts, inferred audience, outline, template ID, density, output specification, and emphasis in the stored plan.

- [ ] **Step 5: Implement editable plan API and confirmation guard**

```python
def confirm_plan(plan: GenerationPlan, session: Session) -> Job:
    if plan.status != "ready":
        raise DomainError("plan_not_ready", "生成计划尚不可确认")
    plan.status = "confirmed"
    job = Job(kind="generate_document", artifact_id=plan.artifact_id, status="queued")
    session.add(job)
    session.commit()
    return job
```

Store a full snapshot of the confirmed plan; later edits create a new plan revision rather than mutating the confirmed snapshot.

- [ ] **Step 6: Verify planning APIs**

Run: `uv run --project services/api pytest services/api/tests/generation/test_planner.py services/api/tests/api/test_plans.py -v`  
Expected: source-required, multi-select, disabled-mode, update, revision, and explicit-confirmation tests all pass.

- [ ] **Step 7: Commit planning**

```powershell
git add services/api/src/generation services/api/src/api/plans.py services/api/tests
git commit -m "feat: add mandatory generation planning"
```

---

### Task 6: Generate a Validated Document Graph in a Durable Job

**Files:**
- Create: `services/api/src/generation/generator.py`
- Create: `services/api/src/worker/settings.py`
- Create: `services/api/src/worker/jobs.py`
- Create: `services/api/src/api/jobs.py`
- Create: `services/api/src/api/documents.py`
- Create: `services/api/tests/generation/test_generator.py`
- Create: `services/api/tests/worker/test_generation_job.py`
- Create: `services/api/tests/api/test_jobs.py`

**Interfaces:**
- Produces: ARQ job `generate_document_job(ctx, job_id: str) -> None`.
- Produces: `GET /v1/jobs/{jobId} -> {status, progress, stage, error}`.
- Produces: `GET /v1/artifacts/{artifactId}/document -> DocumentGraph`.
- Consumes: confirmed immutable plan, parsed sources, and `GenerationProvider`.

- [ ] **Step 1: Write the failing confirmation invariant test**

```python
async def test_generation_requires_confirmed_plan(generator, ready_plan) -> None:
    with pytest.raises(DomainError) as error:
        await generator.generate(ready_plan.id)
    assert error.value.code == "plan_confirmation_required"
```

- [ ] **Step 2: Run the generator tests and verify failure**

Run: `uv run --project services/api pytest services/api/tests/generation/test_generator.py -v`  
Expected: FAIL because the generator does not exist.

- [ ] **Step 3: Implement staged generation**

The worker reports stages `loading_sources` at 10%, `generating_structure` at 30%, `generating_content` at 60%, `validating_document` at 85%, and `saving_version` at 95%. Validate the provider response, verify every citation refers to an uploaded source locator, save artifact version 1 with origin `generation`, set artifact status to `editable`, then report 100%.

- [ ] **Step 4: Implement retry and failure semantics**

Retry provider timeouts and 429/5xx responses up to three times with ARQ exponential backoff. Do not retry schema errors or missing citations. On final failure, set both job and artifact to `failed`, store `{code,message,stage}`, and retain the confirmed plan and parsed sources.

- [ ] **Step 5: Implement job and document APIs**

Return HTTP 202 with `jobId` when confirming the plan. Job polling uses a two-second interval while queued or running and stops on completed or failed. `GET /document` returns 409 `document_not_ready` until the first version exists.

- [ ] **Step 6: Verify worker and API behavior**

Run: `uv run --project services/api pytest services/api/tests/generation services/api/tests/worker services/api/tests/api/test_jobs.py -v`  
Expected: success, retry, non-retryable validation failure, progress, and document-not-ready tests pass.

- [ ] **Step 7: Commit generation jobs**

```powershell
git add services/api
git commit -m "feat: generate validated document graphs"
```

---

### Task 7: Build the Conversation-First Creation and Plan Confirmation UI

**Files:**
- Create: `apps/web/lib/api/client.ts`
- Create: `apps/web/lib/api/types.ts`
- Create: `apps/web/lib/api/hooks.ts`
- Create: `apps/web/components/create/CreateComposer.tsx`
- Create: `apps/web/components/create/FileQueue.tsx`
- Create: `apps/web/components/create/GenerationParameters.tsx`
- Create: `apps/web/components/create/PlanReview.tsx`
- Create: `apps/web/components/create/GenerationProgress.tsx`
- Create: `apps/web/app/create/page.tsx`
- Create: `apps/web/app/artifacts/[artifactId]/plan/page.tsx`
- Create: `apps/web/tests/create-flow.test.tsx`
- Modify: `apps/web/app/page.tsx`

**Interfaces:**
- Consumes: artifact, file, plan, confirm, and job endpoints from Tasks 3–6.
- Produces: browser route `/create` and `/artifacts/{artifactId}/plan`.
- Produces: `GenerationParametersValue` with multi-select `outputModes` and no source-range field.

- [ ] **Step 1: Write failing creation-flow tests**

```tsx
it("keeps generation disabled until a source is parsed", async () => {
  render(<CreateComposer api={fakeApi({ sources: [] })} />);
  await userEvent.type(screen.getByRole("textbox"), "生成季度汇报");
  expect(screen.getByRole("button", { name: "生成计划" })).toBeDisabled();
});

it("allows document and presentation to be selected together", async () => {
  render(<GenerationParameters value={defaults} onChange={onChange} />);
  await userEvent.click(screen.getByLabelText("文档"));
  await userEvent.click(screen.getByLabelText("演示"));
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
    outputModes: ["document", "presentation"],
  }));
});
```

- [ ] **Step 2: Run UI tests and verify failure**

Run: `pnpm --filter web test -- create-flow.test.tsx`  
Expected: FAIL because creation components do not exist.

- [ ] **Step 3: Implement the homepage composer and upload queue**

Place a large instruction textbox in the center, with `添加材料` and disabled `选择模板` actions. Display per-file states `uploading`, `parsing`, `parsed`, or `failed`. Enable `生成计划` only when instruction is non-empty and at least one source is parsed.

- [ ] **Step 4: Implement generation parameters**

Show output modes as multi-select chips; enable document and presentation, render data and dashboard as disabled with the label `后续开放`. Show audience, length, density, visual preset, output specification, and emphasis controls. Do not render a material-range control.

- [ ] **Step 5: Implement mandatory plan review**

Render output modes, outline, source summary, conflicts, inferred settings, and editable parameters. The primary action is `确认并生成`; there is no bypass action. After confirmation, show the five worker stages and link to the editor when the job completes.

- [ ] **Step 6: Verify the complete UI state machine**

Run: `pnpm --filter web test -- create-flow.test.tsx`  
Expected: composer gating, upload failures, multi-select parameters, plan editing, mandatory confirmation, progress, failure recovery, and completed navigation tests pass.

- [ ] **Step 7: Commit the creation flow**

```powershell
git add apps/web
git commit -m "feat: add conversation-first creation flow"
```

---

### Task 8: Render and Directly Edit Document and Presentation Views

**Files:**
- Create: `apps/web/components/editor/ArtifactEditor.tsx`
- Create: `apps/web/components/editor/SectionNavigator.tsx`
- Create: `apps/web/components/editor/DocumentRenderer.tsx`
- Create: `apps/web/components/presentation/PresentationStage.tsx`
- Create: `apps/web/components/presentation/SemanticReadingView.tsx`
- Create: `apps/web/components/presentation/presentationScale.ts`
- Create: `apps/web/components/editor/blocks/RichTextBlock.tsx`
- Create: `apps/web/components/editor/blocks/TableBlock.tsx`
- Create: `apps/web/components/editor/blocks/MetricBlock.tsx`
- Create: `apps/web/components/editor/blocks/ChartBlock.tsx`
- Create: `apps/web/components/editor/blocks/ImageBlock.tsx`
- Create: `apps/web/components/editor/useDocumentDraft.ts`
- Create: `apps/web/app/artifacts/[artifactId]/edit/page.tsx`
- Create: `services/api/src/documents/service.py`
- Modify: `services/api/src/api/documents.py`
- Create: `apps/web/tests/artifact-editor.test.tsx`
- Create: `services/api/tests/api/test_document_save.py`

**Interfaces:**
- Produces: `PUT /v1/artifacts/{artifactId}/document` with `If-Match: <version>`.
- Produces: `DocumentSaveResponse {versionNumber, savedAt}`.
- Produces: `PresentationStage({graph, activeSlideId, viewport})`, a 1920×1080 logical renderer transformed by one uniform scale and never used as the semantic reading surface.
- Produces: `SemanticReadingView({graph})`, a separate reflowed semantic HTML view using the registry reading order.
- Consumes: shared `DocumentGraph` and block types.

- [ ] **Step 1: Write failing optimistic-concurrency API tests**

```python
def test_save_rejects_stale_version(client, editable_artifact) -> None:
    response = client.put(
        f"/v1/artifacts/{editable_artifact.id}/document",
        headers={"If-Match": "0"},
        json=editable_artifact.document,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "version_conflict"
```

- [ ] **Step 2: Write failing editor rendering tests**

```tsx
it("renders the same graph as a document and presentation", () => {
  const { rerender } = render(<ArtifactEditor graph={graph} activeMode="document" />);
  expect(screen.getByRole("heading", { name: "执行摘要" })).toBeVisible();
  rerender(<ArtifactEditor graph={graph} activeMode="presentation" />);
  expect(screen.getByLabelText("幻灯片 1")).toBeVisible();
  expect(screen.getByTestId("presentation-stage"))
    .toHaveAttribute("data-logical-size", "1920x1080");
});

it("offers a semantic reflow view independent of fixed-stage geometry", () => {
  render(<SemanticReadingView graph={graph} />);
  expect(screen.getByRole("article", { name: graph.title })).toBeVisible();
  expect(screen.getByRole("heading", { name: "执行摘要" })).toBeVisible();
  expect(screen.getByRole("table", { name: "季度收入" })).toBeVisible();
});
```

- [ ] **Step 3: Run API and UI tests and verify failure**

Run:

```powershell
uv run --project services/api pytest services/api/tests/api/test_document_save.py -v
pnpm --filter web test -- artifact-editor.test.tsx
```

Expected: both suites fail because save/version behavior and editor components do not exist.

- [ ] **Step 4: Implement versioned saves**

Validate the complete graph, compare `If-Match` to the latest version, save a new version with origin `manual`, and return 409 with the latest version number when stale. Never overwrite an earlier version row.

- [ ] **Step 5: Implement document rendering, the fixed stage, and semantic reading**

Document mode uses normal flow. `PresentationStage` renders each active slide from its registered layout and slot assignments on an absolutely positioned 1920×1080 logical canvas. `presentationScale.ts` returns `Math.min(viewportWidth / 1920, viewportHeight / 1080)`; apply that single scale at the stage root and center it, without per-block responsive reflow or CSS `zoom`. Use stable slide IDs for navigation, deep links, notes, and animation targets; page numbers are display-only. Reject unknown layouts/slots and expose capacity failures as diagnostics rather than shrinking text below the registry minimum.

`SemanticReadingView` is a separate DOM tree, not a visually hidden copy of the fixed canvas. Render sections, headings, paragraphs, lists, figures/captions, semantic tables with headers, chart summaries and table fallbacks in registry reading order. It must support browser zoom, keyboard traversal, accessible names, and `lang`; it ignores presentation coordinates. A visible `阅读视图` control lets users switch to it from presentation mode.

Use Tiptap for `richText`, semantic HTML for `table`, a pinned locally bundled chart renderer for the basic `chart` block, and plain components for metrics and images. Never load CDN globals and never inject user/model/data content through `innerHTML`; use DOM/text/component APIs. Images resolve managed asset IDs, verify content hashes, and surface alt/caption. Motion consumes only declared semantic animation entries, shows a stable final state when disabled, and honors `prefers-reduced-motion`. This slice does not add presenter/audience windows; any later cross-window implementation must use explicit `targetOrigin` plus origin/source/schema/session validation. Autosave the complete validated graph 800 ms after the last edit.

- [ ] **Step 6: Implement conflict recovery**

On 409, pause autosave and show `文档已产生新版本`. Offer `加载最新版本` and `保存为副本`; do not silently merge document graphs in this slice.

- [ ] **Step 7: Verify editor and save behavior**

Run:

```powershell
uv run --project services/api pytest services/api/tests/api/test_document_save.py -v
pnpm --filter web test -- artifact-editor.test.tsx
```

Expected: renderer switching, exact uniform scaling at representative 16:9/16:10/mobile viewports, stable-ID navigation, separate reflow reading order, reduced-motion final state, text editing, debounced save, new versions, and conflict recovery tests pass. Data and dashboard routes remain absent/disabled.

- [ ] **Step 8: Commit the editor**

```powershell
git add apps/web services/api
git commit -m "feat: add editable document and presentation views"
```

---

### Task 9: Add AI Edit Preview, Apply, Undo, and Version History

**Files:**
- Create: `services/api/src/documents/commands.py`
- Create: `services/api/src/generation/editor.py`
- Create: `services/api/src/api/commands.py`
- Create: `services/api/tests/documents/test_commands.py`
- Create: `services/api/tests/api/test_ai_edits.py`
- Create: `apps/web/components/editor/AIAssistantPanel.tsx`
- Create: `apps/web/components/editor/EditPreview.tsx`
- Create: `apps/web/components/editor/VersionHistory.tsx`
- Create: `apps/web/tests/ai-edit-flow.test.tsx`

**Interfaces:**
- Produces: `POST /v1/artifacts/{artifactId}/edits/preview -> {previewId, commands, summary, affectedBlockIds}`.
- Produces: `POST /v1/artifacts/{artifactId}/edits/{previewId}/apply -> DocumentSaveResponse`.
- Produces: `GET /v1/artifacts/{artifactId}/versions` and `POST /v1/artifacts/{artifactId}/versions/{version}/restore`.
- Consumes: provider edit commands and document command validator.

- [ ] **Step 1: Write failing command safety tests**

```python
def test_replace_text_only_changes_target_block(graph) -> None:
    updated = apply_commands(graph, [
        ReplaceTextCommand(blockId="summary", content={"type": "doc", "content": []})
    ])
    assert updated.block("summary").content != graph.block("summary").content
    assert updated.block("revenue") == graph.block("revenue")

def test_unknown_block_is_rejected(graph) -> None:
    with pytest.raises(DomainError, match="edit_target_not_found"):
        apply_commands(graph, [RemoveBlockCommand(blockId="missing")])
```

- [ ] **Step 2: Run command tests and verify failure**

Run: `uv run --project services/api pytest services/api/tests/documents/test_commands.py -v`  
Expected: FAIL because command application does not exist.

- [ ] **Step 3: Implement pure command application and diff summaries**

Apply commands to a deep copy, validate after every command, reject executable content and unknown IDs, and return both the updated graph and a diff summary. Persist previews with a 30-minute expiry and the base version number.

- [ ] **Step 4: Implement preview and apply endpoints**

Preview calls the provider but does not change the artifact. Apply rejects a stale base version, persists an `ai` version, and records the instruction and command summary. Restore creates a new `restore` version copied from the selected historical graph.

- [ ] **Step 5: Implement the right-side AI panel**

The panel accepts an instruction and optional selected block IDs. Always show the proposed summary and affected blocks before enabling `应用修改`. Provide `取消`, `应用修改`, and after apply `撤销本次修改`, which restores the prior version.

- [ ] **Step 6: Verify AI edit and history behavior**

Run:

```powershell
uv run --project services/api pytest services/api/tests/documents/test_commands.py services/api/tests/api/test_ai_edits.py -v
pnpm --filter web test -- ai-edit-flow.test.tsx
```

Expected: targeted edits, rejected unsafe commands, stale preview, apply, undo, restore, and version list tests pass.

- [ ] **Step 7: Commit AI editing**

```powershell
git add apps/web services/api
git commit -m "feat: preview and apply safe ai edits"
```

---

### Task 10: Export Standalone HTML and Prove the Full Slice

**Files:**
- Create: `services/api/src/quality/models.py`
- Create: `services/api/src/quality/pipeline.py`
- Create: `services/api/src/quality/semantic.py`
- Create: `services/api/src/quality/capacity.py`
- Create: `services/api/src/exports/html.py`
- Create: `services/api/src/exports/assets.py`
- Create: `services/api/src/api/exports.py`
- Create: `services/api/tests/quality/test_quality_pipeline.py`
- Create: `services/api/tests/exports/test_html_export.py`
- Create: `apps/web/lib/quality/browser-validator.ts`
- Create: `apps/web/tests/quality-gate.test.ts`
- Create: `apps/web/components/editor/ExportMenu.tsx`
- Create: `tests/e2e/core-vertical-slice.spec.ts`
- Create: `tests/e2e/quality-gate.spec.ts`
- Create: `playwright.config.ts`
- Create: `scripts/e2e-seed.py`
- Modify: `README.md`
- Modify: `.env.example`

**Interfaces:**
- Produces: `POST /v1/artifacts/{artifactId}/exports/html -> {downloadUrl, expiresAt}`.
- Produces: a ZIP containing `index.html`, `assets/*`, and `manifest.json` with no external runtime dependency.
- Produces: `QualityReport {documentVersion, profile, diagnostics, passedLayers}` where every diagnostic has `{code,severity,layer,nodeId,message,measurements,constraint,repair}`.
- Consumes: latest validated document graph and stored source assets.

- [ ] **Step 1: Write failing export safety tests**

```python
def test_html_export_is_self_contained(exporter, graph) -> None:
    archive = exporter.export(graph)
    html = archive.read_text("index.html")
    assert "<script src=\"http" not in html
    assert "<link href=\"http" not in html
    assert "javascript:" not in html
    assert archive.exists("manifest.json")
    assert archive.read_json("manifest.json")["assets"][0]["sha256"]

def test_export_escapes_user_text(exporter, graph_with_script_text) -> None:
    html = exporter.export(graph_with_script_text).read_text("index.html")
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html

def test_quality_pipeline_stops_at_capacity_with_repair(quality, overfull_graph) -> None:
    report = quality.run_static_layers(overfull_graph)
    issue = next(item for item in report.diagnostics if item.code == "slot_capacity_exceeded")
    assert report.passed_layers == ["schema", "semantic"]
    assert issue.node_id == overfull_graph.presentation.slides[0].id
    assert issue.repair == {"command": "splitSlide", "layoutId": "title-media"}
```

- [ ] **Step 2: Run quality and export tests and verify failure**

Run: `uv run --project services/api pytest services/api/tests/quality/test_quality_pipeline.py services/api/tests/exports/test_html_export.py -v`
Expected: FAIL because the quality pipeline and HTML exporter do not exist.

- [ ] **Step 3: Implement the static quality layers**

Implement a fixed-order pipeline: (1) JSON Schema and stable-reference validation; (2) semantic/source and reserved data invariants; (3) layout registry slot/capacity validation. A failed layer prevents later render/export layers from running. Diagnostics use stable slide/block/chart/asset IDs, include actual versus allowed measurements, cite the registry/schema rule, and provide one of a bounded set of repair commands such as `splitSlide`, `truncateToCapacity`, `replaceLayout`, `addAltText`, or `useTableFallback`. Repairs create a new document version and rerun the failed layer plus all later layers; they never mutate exported HTML.

- [ ] **Step 4: Implement browser geometry and accessibility gates**

Use Playwright with the pinned Chromium from the workspace lockfile to render every presentation slide at canonical 1920×1080 plus representative 16:9, 16:10, and narrow viewports. Measure text/content clipping, unintended bounding-box overlap, layout safe-area intrusion, minimum font size, image crop bounds, and final animation state. Then check semantic reading order, headings, labels/alt/captions, table headers/fallbacks, keyboard focus, contrast, non-color meaning, and `prefers-reduced-motion`. Add screenshot baselines for both the fixed stage and reading view. Ambiguous geometry becomes a `review` diagnostic instead of silently passing.

- [ ] **Step 5: Implement deterministic standalone rendering**

Render semantic HTML from the document graph with DOM/text/component escaping rather than `innerHTML`, inline versioned product CSS, copy only manifest-declared managed assets into `assets/`, verify each SHA-256, serialize chart data into non-executable JSON, and bootstrap basic charts from a pinned bundled local renderer. Every chart includes title/description/source/`asOf` metadata and a semantic table fallback. Self-host font files and record family, file hash, codepoint coverage, fallback, license ID, notice path, and redistribution permission.

Add a manifest with artifact ID, document version, schema version, layout/template package versions, export profile, fixed renderer/browser/font versions, deterministic content hashes, assets, dependencies, licenses, and explicit interaction/animation degradation. The exported content for the same document version and export profile must be byte-for-byte stable except for a separately stored job timestamp; do not include volatile timestamps in content-addressed files. The archive must render with all network requests blocked. There is no cross-window messaging in this slice; future messaging must use strict origins, never `postMessage('*')`.

- [ ] **Step 6: Implement export API and UI**

Run the complete quality pipeline before queuing export. Block `error` diagnostics and show their repair actions in the editor; permit explicitly acknowledged `review` diagnostics. Store the deterministic ZIP in object storage and return a 15-minute signed download URL. The editor export menu shows only `独立 HTML` as enabled; PDF and image appear disabled with `后续开放`.

- [ ] **Step 7: Write the full-stack Playwright scenarios**

```ts
test("source to confirmed plan to edited HTML export", async ({ page }) => {
  await page.goto("/create");
  await page.getByRole("textbox").fill("生成管理层季度经营汇报");
  await page.getByLabel("添加材料").setInputFiles("tests/fixtures/quarterly-report.pdf");
  await expect(page.getByText("解析完成")).toBeVisible();
  await page.getByLabel("文档").check();
  await page.getByLabel("演示").check();
  await page.getByRole("button", { name: "生成计划" }).click();
  await expect(page.getByRole("heading", { name: "确认生成计划" })).toBeVisible();
  await page.getByRole("button", { name: "确认并生成" }).click();
  await expect(page.getByText("生成完成")).toBeVisible();
  await page.getByRole("link", { name: "进入编辑器" }).click();
  await page.getByRole("textbox", { name: "执行摘要" }).fill("更新后的执行摘要");
  await expect(page.getByText("已保存")).toBeVisible();
  await page.getByRole("button", { name: "导出" }).click();
  await page.getByRole("menuitem", { name: "独立 HTML" }).click();
  await expect(page.getByText("导出完成")).toBeVisible();
});
```

Add `quality-gate.spec.ts` fixtures that deliberately cause overflow, overlap, safe-area intrusion, insufficient contrast, missing alt text/table fallback, forbidden motion under reduced-motion, an external URL, hash mismatch, an `innerHTML`-style script payload, and wildcard `postMessage`. Assert each yields the expected stable diagnostic and repair. Export the valid fixture twice, compare hashes, open it with browser networking denied, and verify fixed-stage screenshots, semantic reading content, chart tables, source/as-of metadata, fonts/assets, and manifest licenses.

- [ ] **Step 8: Run the complete verification suite**

Run:

```powershell
docker compose up -d --wait
pnpm lint
pnpm typecheck
pnpm test
uv run --project services/api pytest services/api/tests -v
pnpm exec playwright test tests/e2e/core-vertical-slice.spec.ts tests/e2e/quality-gate.spec.ts
```

Expected: all linters, type checks, unit tests, API/integration tests, the full browser scenario, layered quality fixtures, deterministic double-export hash comparison, and offline export checks pass with zero failures.

- [ ] **Step 9: Document operation and failure recovery**

Update `README.md` with exact startup commands, environment variables, database migration command, worker command, MinIO bucket initialization, fake-provider mode, OpenAI-compatible provider mode, test commands, the quality-layer order and diagnostic format, clean-room/license policy, asset/font registration, offline/deterministic export checks, and recovery procedures for failed parse, generation, validation, and export jobs.

- [ ] **Step 10: Commit the completed vertical slice**

```powershell
git add .
git commit -m "feat: complete source-to-html vertical slice"
```

## Scope Coverage Review

This plan implements the first independently testable slice of the approved product spec: conversation-first creation, source parsing, mandatory parameterized plan confirmation, validated document generation, direct editing, AI edit preview, immutable versions, a fixed-stage Presentation Pack renderer with a separate semantic reading view, layered quality gates, and deterministic standalone HTML export.

The following approved product areas are intentionally assigned to separate implementation plans and are not gaps inside this slice: Data Visualization Pack UI/runtime, HTML import and sandbox conversion, personal template authoring and real-content candidate previews, presenter/audience/rehearsal runtime, PDF/image export, material replacement and selective update, and enterprise collaboration/governance.

## Follow-on Data Visualization Pack Subprojects

Do not add these to Tasks 1–10. Each item requires a separate spec and implementation plan while preserving the single-user, upload-only data boundary until the product spec changes:

1. **Dataset profiling and quality:** implement `DatasetProfile`, type/unit/timezone inference, null/invalid/cardinality reports, sampling disclosure, sensitivity labels, and upload-version lineage.
2. **Auditable recommendation service:** implement `AnalyticIntent → ChartPlan`, deterministic candidate scoring, selected/alternative reasons, capacity/invariant evaluation, fallbacks, and user override audit.
3. **Chart specification and renderer core:** implement versioned `ChartSpec`/`EncodingSpec`, shared scale/layout/format/accessibility primitives, an original SVG-first renderer, and one governed advanced-renderer adapter without CDN globals.
4. **Data/Explore experience:** implement record/field inspection, encoding editor, filters, progressive disclosure, keyboard interaction, accessible table/CSV fallback, and provenance display.
5. **Dashboard/Glance experience:** implement KPI/rank/trend/anomaly composition, dashboard layout registry, filter state, performance budgets, explicit source/`asOf`, and uploaded-file replacement semantics.
6. **Report/Story experience:** implement narrative report schemas, claim/evidence/source links, section/page capacity, reading-speed intent, and embedding contracts with document and presentation views.
7. **Visualization delivery and quality:** implement semantic/data property tests, mark/label geometry, contrast/non-color cues, screenshot parity, offline behavior, deterministic SVG/PNG/PDF exports, and data/provenance sidecars.

## Final Acceptance Checklist

- [ ] A user cannot request generation without at least one parsed source.
- [ ] The plan page appears for every generation and cannot be bypassed.
- [ ] Document and presentation can be selected together.
- [ ] No material-range control exists; every parsed source is included.
- [ ] Data and dashboard modes are visible but disabled for this slice.
- [ ] The generated graph passes shared schema validation in TypeScript and Python.
- [ ] Stable slide IDs preserve layout, media, notes, timing, and animation bindings across reorder and version round-trips.
- [ ] Presentation mode renders a 1920×1080 logical stage with one uniform scale, while the separate semantic reading view reflows and remains keyboard/screen-reader accessible.
- [ ] Direct edits produce immutable versions and stale saves are rejected.
- [ ] AI edits show affected blocks before application and can be undone.
- [ ] The layered gate runs schema → semantic/data invariants → layout capacity → browser geometry/safe areas → accessibility/contrast/reduced motion → screenshot/export/offline checks and returns repairable stable-ID diagnostics.
- [ ] The HTML export is deterministic, self-contained, offline-capable, contains no user-supplied executable script, CDN global, `innerHTML` data sink, or wildcard `postMessage`, and includes accessible chart-table fallbacks.
- [ ] Every exported asset/font has a managed ID, SHA-256, provenance/license record, and required notice.
- [ ] Parse, generation, and export failures have stable codes and recoverable UI states.
- [ ] The complete Playwright scenario passes against the real local stack.
