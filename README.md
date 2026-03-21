# Perspective Engine

A first local MVP of the proposal in `/Users/matteoperona/Downloads/perspective_engine_proposal.md`.

## Stack

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy + Alembic
- Simulation runtime: CAMEL-AI OASIS
- Data: SQLite app DB, per-simulation OASIS trace DBs, seeded persona library, seeded reasoning profile

## Run locally

1. Create a Python 3.11 environment and install backend dependencies:

```bash
uv venv --python python3.11 .venv
source .venv/bin/activate
uv pip install -r backend/requirements.txt
```

2. Configure the simulation provider.

For a local smoke test with deterministic stub responses:

```bash
export SIM_PROVIDER=stub
export SIM_MODEL=stub
```

For a real OASIS-backed run against an OpenAI-compatible endpoint:

```bash
export SIM_PROVIDER=openai-compatible-model
export SIM_MODEL=your_model_name
export SIM_API_KEY=your_key_here
export SIM_BASE_URL=https://your-endpoint.example/v1
```

For Anthropic-backed runs:

```bash
export SIM_PROVIDER=anthropic
export SIM_MODEL=claude-3-5-sonnet-latest
export SIM_API_KEY=your_key_here
```

Optional overrides for separate planner/brief models:

```bash
export SIM_SELECTOR_MODEL=your_selector_model
export SIM_SUMMARY_MODEL=your_summary_model
export SIM_MAX_CONCURRENCY=8
```

3. Start the backend:

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Start the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

5. Open the Vite URL, usually `http://127.0.0.1:5173`.

## What this backend now includes

- Route-based 3-screen flow for compose, persona selection, and simulation
- Real document upload for `.txt`, `.md`, and `.pdf`
- Provider-backed panel recommendation with deterministic fallback
- OASIS-backed panel simulation with persisted rounds, events, and per-run trace databases
- Structured stance interviews and trajectory tracking per round
- Expandable and downloadable decision brief
- Additive SSE event endpoint at `/api/sessions/{id}/events`

## Backend Docs

For a detailed architecture walkthrough of the backend, including data flow, OASIS integration, persistence, API contracts, frontend coupling, and Mermaid diagrams, see [backend/README.md](/Users/matteoperona/Projects/agora/backend/README.md).
