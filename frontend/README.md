# Frontend — DevAutoPilot v2 Dashboard

A premium **dark SRE control center** (Next.js App Router, TypeScript, Tailwind, Recharts, Framer Motion).

> **Note:** these files are **placeholders**. To bootstrap the real app, run:
>
> ```bash
> npx create-next-app@latest frontend --ts --tailwind --app --src-dir
> ```
>
> Then re-introduce the page/component stubs under `src/`. The configs here are minimal starting points so the structure is visible in Phase 0.

## Pages

1. **Dashboard** (`/`) — live incident feed, stats, agent activity, model-health & drift widget.
2. **Incidents** (`/incidents`) — list + detail with the full agent timeline and trace view.
3. **Agents** (`/agents`) — status of all five agents, workload, token/cost per run.
4. **Models** (`/models`) — model versions, eval metrics, drift charts, retrain button.
5. **Postmortems** (`/postmortems`) — searchable archive.
6. **Simulate** (`/simulate`) — trigger anomalies/incidents on demand for live demos.

## Develop

```bash
cd frontend
npm install
npm run dev
```

API base URL is read from `NEXT_PUBLIC_API_BASE_URL` (see `src/lib/api.ts`).
