# NOTES.md

This file provides guidance to AI agents when working with code in this
repository.

## Project Overview

**Agora Perspective Engine** — a multi-agent deliberation platform. Users submit
a decision/question, select a panel of AI personas, and the system simulates a
structured debate that produces a decision brief.

3-step product flow: **Frame decision → Select panel → Run simulation → Read
verdict**

## Repository Structure

```
agora/
├── backend/                         # FastAPI + SQLAlchemy + CAMEL-AI/OASIS
│   └── app/
│       ├── main.py                  # All API routes (entrypoint)
│       ├── models.py                # Pydantic request/response models
│       ├── entities.py              # SQLAlchemy ORM tables
│       ├── repository.py            # Data access layer
│       ├── services/                # Business logic (panel, personas, docs, debate)
│       └── simulation/              # OASIS/CAMEL runtime, provider abstraction
└── frontend/                        # React + Vite + Tailwind frontend
    └── src/app/
        ├── pages/                   # Home, SummonCouncil, Debate, Verdict
        ├── components/              # BrutalistButton, BrutalistCard, ui/ (Shadcn)
        └── data/                    # philosophers.ts (static definitions)
```

## Commands

### Backend

```bash
# Setup (run once)
uv venv --python python3.11 .venv
source .venv/bin/activate
uv pip install -r backend/requirements.txt

# Run dev server (port 8000)
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# Run tests
pytest backend/tests -q

# Run a single test file
pytest backend/tests/test_simulation_flow.py -q
```

### Frontend

```bash
cd frontend

npm install
npm run dev      # Dev server on port 5173
npm run build    # Production build
```

## Backend Architecture

**API endpoints** (all in `backend/app/main.py`):

| Endpoint                                | Purpose                                        |
| --------------------------------------- | ---------------------------------------------- |
| `GET /api/personas`                     | List all available personas                    |
| `POST /api/personas/expand`             | Expand natural language → full Persona         |
| `POST /api/personas`                    | Create custom persona                          |
| `POST /api/documents`                   | Upload document (multipart) → UploadedDocument |
| `DELETE /api/documents/{id}`            | Remove uploaded document                       |
| `POST /api/panel/recommend`             | Recommend panel for a decision                 |
| `POST /api/sessions`                    | Create debate session → SessionSnapshot        |
| `GET /api/sessions/{id}`                | Fetch current snapshot                         |
| `POST /api/sessions/{id}/advance`       | Run next round → SessionSnapshot               |
| `POST /api/sessions/{id}/interjections` | Add user message mid-debate                    |
| `POST /api/sessions/{id}/finish`        | End debate + generate DecisionBrief            |
| `GET /api/sessions/{id}/events`         | SSE stream (event_type, payload, round_index)  |

**Key data models** (`backend/app/models.py`):

- `SessionSnapshot` — full debate state: messages, roster stances, stance
  trajectories, network edges, brief
- `DecisionBrief` — headline, landscape_summary, strongest_arguments,
  key_uncertainties, blind_spots, suggested_next_steps
- `PersonaStance` — stance float (-1 to 1), confidence (0 to 1), label
  (for/against/undecided), rationale
- `TrajectorySeries` — per-persona stance history over rounds

**Provider configuration** (`.env` in repo root):

```bash
# Stub — no API key, deterministic responses
SIM_PROVIDER=stub

# Anthropic (Claude)
SIM_PROVIDER=anthropic
SIM_MODEL=claude-haiku-4-5-20251001
SIM_API_KEY=sk-ant-...

# Optional: stronger model for brief/panel selection
# SIM_SUMMARY_MODEL=claude-sonnet-4-6
# SIM_SELECTOR_MODEL=claude-haiku-4-5-20251001

# OpenAI-compatible (Ollama, Together, etc.)
SIM_PROVIDER=openai-compatible-model
SIM_MODEL=llama3
SIM_API_KEY=...
SIM_BASE_URL=http://localhost:11434/v1
```

Use `SIM_PROVIDER=stub` for development without real LLM calls.

**Two persistence layers:**

1. App SQLite (`backend/data/`) — durable sessions, personas, documents
2. Per-simulation OASIS SQLite — detailed agent interaction traces (stored in
   `oasis_db_path`)

**CORS:** Allows `localhost:5173` and `localhost:5174`.

## Frontend Architecture

**Routing** (`src/app/routes.tsx`):

- `/` → Home (question input + document upload)
- `/summon` → SummonCouncil (persona selection + debate parameters)
- `/debate/:debateId` → Debate (live simulation with SSE)
- `/verdict/:debateId` → Verdict (DecisionBrief display)

**State passing between routes:** `location.state` with `sessionStorage`
fallback.

**Design system** — Brutalist aesthetic:

- Thick black borders, `4px 4px 0 0 #0A0A0A` box shadows
- `BrutalistButton` (variants: primary/secondary/accent/green/terracotta/grey)
- `BrutalistCard` — bordered container with optional hover lift
- Tailwind 4 + Radix UI + Shadcn components in `components/ui/`
- Motion (Framer Motion fork) for animations

**Animation pattern:** `motion.div` with `animate={{ y: [0, -6, 0] }}` breathing
effects.

## Key Development Notes

- Backend and frontend run on separate ports; use the Vite dev proxy or direct
  `http://localhost:8000` for API calls.
- The stub provider returns deterministic responses — use it during UI
  development to avoid LLM costs.
- OASIS/CAMEL logs are noisy; redirect with `2>/dev/null` when running tests if
  needed.
- All timestamps should be UTC (`datetime.now(UTC)` in Python).
- Backend uses `from __future__ import annotations` — use string-style type
  hints in new Python files.
- Frontend uses `@/` alias mapped to `src/` (configured in `vite.config.ts`).
