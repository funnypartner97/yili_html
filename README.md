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
