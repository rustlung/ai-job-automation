# AI Job Automation Web UI

React + TypeScript frontend for the Orchestrator Web API. It is a LAN-first
working interface; it never calls Worker, Ollama, n8n or Google Sheets directly.

## Development

```powershell
cd web
Copy-Item .env.example .env.local
npm install
npm run dev
```

Vite opens at `http://localhost:5173`. Set `VITE_API_BASE_URL` to the
Orchestrator URL, for example `http://localhost:8000` locally or
`http://192.168.0.129:8000` on the LAN. `VITE_*` values are embedded into the
browser bundle and are not secrets.

```powershell
npm run typecheck
npm run lint
npm test
npm run build
```

## Structure

- `src/app` — React Query provider and routes.
- `src/pages` — Dashboard, run start, list and detail pages.
- `src/components` — small visual components such as `HealthCard`.
- `src/api` — typed Orchestrator HTTP client.
- `src/hooks` — thin TanStack Query hooks.
- `src/types` — shared API DTO types.
- `src/features/run-start` — local profile-selection state and helpers.

## Docker deployment

The production image is a static nginx server for the SPA only. It does not
proxy `/api`; the browser calls the configured Orchestrator origin directly.

```bash
cd web
VITE_API_BASE_URL=http://192.168.0.129:8000 docker compose up -d --build
```

The UI is served on port `3000`. The API URL is a Vite build-time value, so
rebuild the image after changing it. Nginx uses an SPA fallback, therefore a
direct refresh of `/runs/<run_id>` remains valid.

Configure the same browser origin in Orchestrator `WEB_UI_ALLOWED_ORIGINS`, for
example `http://192.168.0.129:3000`. Do not put webhook secrets, Worker URLs or
internal tokens in frontend environment files.
