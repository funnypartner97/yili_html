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
