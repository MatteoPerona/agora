# Perspective Engine

A first local MVP of the proposal in `/Users/matteoperona/Downloads/perspective_engine_proposal.md`.

## Stack

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + SQLite
- Data: Seeded persona library and seeded reasoning profile

## Run locally

1. Create a Python environment and install backend dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

2. Optional but recommended for real LLM-backed persona preselection:

```bash
export ANTHROPIC_API_KEY=your_key_here
# Optional override; defaults to claude-3-5-sonnet-latest
export ANTHROPIC_MODEL=claude-3-5-sonnet-latest
```

If `ANTHROPIC_API_KEY` is not set, the app still runs and transparently falls back to the local persona recommender.

3. Start the backend:

```bash
.venv/bin/uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Start the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

5. Open the Vite URL, usually `http://127.0.0.1:5173`.

## What this MVP includes

- Route-based 3-screen flow for compose, persona selection, and simulation
- Real document upload for `.txt`, `.md`, and `.pdf`
- Anthropic-backed persona preselection with a local fallback
- Dedicated simulation workspace with interaction graph, opinion chart, and transcript
- Expandable and downloadable decision brief
- Separate utility routes for library management and reasoning profile
