# HTML Office

HTML Office turns source material into editable business documents and presentations.

## Prerequisites

- Node.js 26
- pnpm 10.33.0
- Python 3.14 with [uv](https://docs.astral.sh/uv/)
- Docker Compose

## Start locally

1. Copy `.env.example` to `.env` and adjust any local port conflicts.
2. Start PostgreSQL, Redis, MinIO, and the `html-office` bucket:

   ```powershell
   docker compose up -d --wait
   ```

3. Install the web workspace dependencies:

   ```powershell
   pnpm install
   ```

4. Start the web application and API together:

   ```powershell
   pnpm dev
   ```

The web application runs on `http://localhost:3000`; the API health endpoint is `http://127.0.0.1:8000/healthz`.

## Verification

```powershell
pnpm test
pnpm lint
pnpm typecheck
pnpm e2e
```

The API test may also be run directly:

```powershell
uv run --project services/api pytest services/api/tests/test_health.py -v
```

## Local services

| Service | Address |
| --- | --- |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |
| MinIO API | `http://localhost:9000` |
| MinIO console | `http://localhost:9001` |

Use `docker compose down` to stop services while retaining local volumes, or `docker compose down -v` only when intentionally discarding local runtime data.

## Mandatory generation planning

Apply migrations before using persisted plans:

```powershell
uv run --project services/api alembic -c services/api/alembic.ini upgrade head
```

The API process needs `DASHSCOPE_API_KEY` in its environment. Server-only settings
are documented in `.env.example`; API callers cannot choose provider, model or URL.
The exact provider identifier is `qwen`, using the Beijing HTTPS endpoint only.
Planning, document generation and complex edit policies use the pinned Qwen Max
snapshot `qwen3.7-max-2026-05-20`; summary, classification, local rewrite and
validation repair policies use `qwen3.7-flash-2026-07-15`. These Qwen families
support [JSON Schema structured output](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output).
The OpenAI-compatible request format does not enable OpenAI or other overseas
providers. DeepSeek and Doubao remain disabled pending an explicit reviewed
endpoint/model allowlist; there is no automatic vendor or JSON Object fallback.

`POST /v1/artifacts/{artifactId}/plans` accepts `{instruction, parameters}` and
returns HTTP 201 with `{id, artifactId, revision, status, plan, createdAt, confirmedAt}`.
The instruction must be nonblank. Parameters are `outputModes`, `audience`,
`lengthPreset`, `density`, `outputSpec`, and `emphasis`. Both document and
presentation can be selected. Every parsed source participates; no source-range,
template-only or blank-generation path is exposed. Data/dashboard are disabled.
Omitting `templateId` is a deliberate correction to the original Task 5 wording:
template selection is disabled in this slice and Task 2's canonical plan contract
has no such field. Personal template authoring remains later scope.

`PUT /v1/artifacts/{artifactId}/plans/{planId}` accepts `{plan: <complete plan>}`
and creates a new ready revision. It never overwrites an existing revision.
Only the latest revision can be confirmed. Confirm with
`POST /v1/artifacts/{artifactId}/plans/{planId}/confirm` (no body): HTTP 202 returns
`{jobId, planId, status}`. The plan ID is the permanent idempotency key: concurrent
or repeated confirmations return the same job, including after that job finishes
or fails. A database unique constraint prevents a second job for the same plan.
Confirmation, its full job snapshot and the `generating` artifact transition
commit atomically. New plan edits may be saved during generation, but cannot be
confirmed until the active generation finishes. Existing confirmed snapshots stay
unchanged. Source changes invalidate unconfirmed plans and require a new plan.

Each successful inference stores provider/model, prompt/schema versions, schema
hash and source file/parsed-content hashes in the plan's invocation audit. Keys
and raw source text are not audit fields or logs. Transport enforces exact HTTPS
destinations, public unicast DNS addresses pinned for TLS, no redirects/proxies,
an 8 MiB request cap, a 2 MiB response cap and a 60-second request deadline.
Every task also sends an explicit thinking policy: plan/document/complex-edit
enable thinking with a 2,048-token thinking budget and an 8,192-token total
completion cap; summary/classification/local-rewrite/validation-repair disable
thinking and use a 4,096-token total completion cap. The request uses
`max_completion_tokens`, which bounds thinking plus the answer, instead of the
deprecated answer-only `max_tokens`. These server-owned bounds and policy version
are recorded in `invocationAudit.generationPolicy`; unsupported or invalid
configurations fail before transport. Alibaba documents a possible variance of
up to 10 tokens around the requested completion cap in its
[compatible API reference](https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions).
The existing byte/time limits still apply. Request/result dataclass repr strings
omit instructions, parameters, sources, plans, documents and output values.
Invalid/truncated output is rejected, without persistence or hidden retries.
Provider errors use the existing `{code, message, details}` envelope and leave
prior ready plans intact. No Redis dispatch or generation retry worker is included
yet; Task 6 consumes the committed `generate_document` job and its plan snapshot.

Tests inject `FakeProvider` through `get_provider`; no production environment
switch can accidentally select the fake. Its plans, document graphs and edit
commands are deterministic and validate against the same contracts. Run the
focused suites with:

```powershell
uv run --project services/api pytest services/api/tests/generation services/api/tests/api/test_plans.py services/api/tests/db/test_migrations.py -v
```

## Documents, editing, and versions

`GET /v1/artifacts/{artifactId}/document` returns the latest `DocumentGraph`, or
HTTP 409 `document_not_ready` until the first version exists.

`PUT /v1/artifacts/{artifactId}/document` saves a complete graph under optimistic
concurrency. Send the current version number in `If-Match`:

- Missing/invalid `If-Match` → HTTP 428 `version_precondition_required`.
- Stale `If-Match` → HTTP 409 `version_conflict` with `details.latestVersion`; the
  earlier version row is never overwritten.
- A graph whose citation does not resolve to an uploaded source → HTTP 502
  `citation_source_missing`. On success a new immutable `manual` version is
  appended and `{versionNumber, savedAt}` is returned.

The editor autosaves the complete validated graph 800 ms after the last edit. On a
conflict it pauses autosave, shows `文档已产生新版本`, and offers `加载最新版本`
or `保存为副本` (which re-reads the latest version as the new precondition). It
never silently merges two graphs.

Presentation rendering uses a fixed logical 1920×1080 stage scaled by exactly one
uniform factor `min(viewportWidth / 1920, viewportHeight / 1080)` applied at the
stage root (`data-logical-size="1920x1080"`, `data-scale`). There is no per-block
responsive reflow and no CSS `zoom`. A separate reflowed `阅读视图` (semantic
reading view) is its own accessible DOM tree — real headings, lists, figures and
captions, semantic tables with headers, and chart summaries with table fallbacks —
independent of the fixed-stage geometry. Motion consumes only declared animation
entries and shows a stable final state under `prefers-reduced-motion`.

### AI edits, undo, and history

- `POST /v1/artifacts/{artifactId}/edits/preview` `{instruction, blockIds?}` →
  HTTP 201 `{previewId, baseVersion, commands, summary, affectedBlockIds,
  expiresAt}`. Preview never mutates the artifact. Commands are the five canonical
  kinds (`replaceText`, `insertBlock`, `removeBlock`, `moveBlock`, `setTheme`),
  applied to a deep copy and re-validated as a whole graph after every command;
  unknown ids, non-canonical/executable commands, and edits that break slide
  references are rejected. A preview persists for 30 minutes with its base version.
- `POST /v1/artifacts/{artifactId}/edits/{previewId}/apply` → `{versionNumber,
  savedAt}`. Apply re-checks the base-version precondition (409 `version_conflict`
  when stale), refuses reuse (409 `preview_already_applied`) and expiry (409
  `preview_expired`), then writes an immutable `ai` version.
- `GET /v1/artifacts/{artifactId}/versions` → `{versions:[{versionNumber, origin,
  createdAt}]}` (newest first). Origins are `generation`, `manual`, `ai`, `restore`.
- `POST /v1/artifacts/{artifactId}/versions/{version}/restore` copies a historical
  graph into a new immutable `restore` version. The editor's `撤销本次修改` restores
  the version an AI edit was based on.

## Quality gates and diagnostic format

Export runs a fixed-order static pipeline before producing an archive: (1) `schema`
— canonical JSON Schema plus stable-identity/reference validation; (2) `semantic` —
alt text, chart table fallbacks, and source locators; (3) `layout` — registry slot
and capacity validation. The first layer that yields an `error`-severity diagnostic
stops the pipeline, so later layers never run on an invalid document
(`passedLayers` records the layers that passed). Every diagnostic is
`{code, severity, layer, nodeId, message, measurements, constraint, repair}` where
`severity` is `error | warning | review`, `nodeId` is a stable slide/block/asset id,
`measurements` carries actual-versus-allowed values, `constraint` cites the
registry/schema rule, and `repair` is one of a bounded set of commands:
`splitSlide`, `truncateToCapacity`, `replaceLayout`, `addAltText`,
`useTableFallback`. `error` diagnostics block export; `review` diagnostics require
explicit acknowledgement (`?acknowledgeReview=true`). Repairs create a new document
version and rerun the failed layer plus all later layers; they never mutate
exported HTML.

Browser geometry and accessibility gates (`apps/web/lib/quality/browser-validator.ts`)
measure clipping, overlap, safe-area intrusion, minimum font size, and WCAG contrast
at the canonical stage plus representative 16:9, 16:10, and narrow viewports using
the pinned Chromium. Ambiguous geometry becomes a `review` diagnostic instead of
silently passing. Its pure helpers are unit-tested in `apps/web/tests/quality-gate.test.ts`
and exercised in a real browser by `tests/e2e/quality-gate.spec.ts`.

## Standalone HTML export

`POST /v1/artifacts/{artifactId}/exports/html` returns
`{downloadUrl, expiresAt, contentHash, documentVersion, passedLayers, diagnostics}`.
The archive is a ZIP of `index.html`, `assets/*`, and `manifest.json` with no
external runtime dependency:

- Semantic HTML is built with text/attribute escaping — never `innerHTML` with
  user/model content — and product CSS is inlined. There are no `<script src="http…">`,
  no `<link href="http…">`, and no `javascript:` URLs.
- Basic charts (bar/line/area/point) are pre-rendered to static SVG by a bundled
  local renderer and always keep their accessible table fallback; chart data is
  embedded as a non-executable `<script type="application/json">` island with the
  closing-tag sequence escaped. Every chart carries title, description, source, and
  `asOf` metadata.
- Only manifest-declared managed assets are copied into `assets/`, each verified by
  SHA-256. The manifest records artifact id, document version, schema version,
  layout-registry and template-package versions, export profile, renderer/font
  versions, per-file content hashes, an archive hash, assets, dependencies,
  licenses, and explicit interaction/animation/network degradation.
- Fonts are declared as the self-hosted system stack (family, embedded flag, file
  hash, codepoint coverage, fallback, license id, notice path, redistribution
  permission). No external webfont is fetched, so the archive renders with all
  network requests blocked.
- The archive is byte-for-byte deterministic for the same document version and
  export profile: ZIP entries are sorted with fixed timestamps and no volatile time
  is written into any content-addressed file. The job/export timestamp is returned
  separately (`expiresAt`), never embedded in hashed content.

## Worker and generation execution

Generation is performed by `src.worker.jobs.generate_document_job`, which reports
the stages `loading_sources` (10%), `generating_structure` (30%),
`generating_content` (60%), `validating_document` (85%), and `saving_version`
(95%), then 100%. Provider timeouts and 429/5xx responses retry up to three times
with exponential backoff (`code in RETRYABLE_CODES`); schema errors and missing
citations do not retry. On final failure both the job and the artifact are marked
`failed` with `{code, message, stage}`, and the confirmed plan and parsed sources
are retained.

`POST …/plans/{planId}/confirm` returns HTTP 202 with `{jobId, planId, status}` and
records a `queued` `generate_document` job whose plan id is the permanent idempotency
key. The confirm route then hands the durable job to the ARQ queue
(`src/worker/enqueue.py`) using the job id as the ARQ `_job_id`, so re-confirmation
never double-enqueues. If Redis is unreachable the job row stays `queued` and the
route returns HTTP 503 `queue_unavailable`; confirming again retries the enqueue.

Run a worker (it consumes `generate_document_job` and reads `DATABASE_URL`,
`REDIS_URL`, and the provider allowlist from server-owned settings):

```powershell
uv run --project services/api arq src.worker.arq_settings.WorkerSettings
```

The worker entrypoint (`src/worker/arq_settings.WorkerSettings`) registers the
generation function, resolves `RedisSettings` from `REDIS_URL`, and caps attempts at
the configured budget (`max_tries=3`) with the in-job exponential backoff described
above. `scripts/e2e-seed.py` runs generation in process (no queue) to seed a
deterministic editable artifact for the end-to-end suite.

## End-to-end suite

The self-contained gate needs only Playwright browsers:

```powershell
pnpm --filter web exec playwright install chromium
pnpm --filter web exec playwright test quality-gate
```

The full-stack scenario additionally requires the services and servers:

```powershell
docker compose up -d --wait
uv run --project services/api alembic -c services/api/alembic.ini upgrade head
uv run --project services/api python scripts/e2e-seed.py   # optional deterministic artifact
uv run --project services/api uvicorn --app-dir services/api src.main:app --port 8000
uv run --project services/api arq src.worker.arq_settings.WorkerSettings   # generation worker
pnpm --filter web dev
pnpm --filter web exec playwright test core-vertical-slice
```

`scripts/e2e-seed.py` parses `tests/fixtures/quarterly-report.pdf`, stores it, and
runs planning plus generation with the deterministic `FakeProvider` in process,
writing `tests/e2e/.seed.json` so specs can open a known-editable artifact.

## Recovery procedures

- Failed parse: the source stays `failed` with a sanitized `{code, message}`;
  re-upload or re-parse. Parse leases expire and are reclaimed automatically.
- Failed generation: the job and artifact are `failed` while the confirmed plan and
  parsed sources are retained; confirm the same plan again (idempotent) or create a
  new plan after fixing sources.
- Failed validation/quality gate: export returns HTTP 422 `quality_gate_failed` with
  `details.diagnostics` and each `repair`; apply a repair (which creates a new
  version and reruns the failed and later layers) and export again.
- Failed export: nothing is stored until the archive is complete; re-run the export.
  Identical inputs produce an identical content hash, so retries are safe.

## Clean-room and license policy

The three supplied reference skills were used as clean-room product patterns, not
copied dependencies: one shared live-document core, a Presentation Pack, and a Data
Visualization Pack. Presentation and visualization contracts are reserved now;
dashboard/data UI stays disabled in this slice. The bundled chart renderer and
export runtime are original and offline; no CDN globals are loaded. Exported
archives declare their dependencies and licenses in `manifest.json`, and the
self-hosted font entry records redistribution permission. The Data Visualization
Pack (dataset profiling, auditable recommendation, chart spec/renderer core,
data/explore and dashboard experiences) is explicitly later scope in the
implementation plan and is not part of this slice.

