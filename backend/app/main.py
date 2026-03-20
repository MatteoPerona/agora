from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .db import (
    create_persona,
    delete_document,
    get_document,
    get_documents,
    get_persona,
    get_profile,
    increment_persona_usage,
    init_db,
    list_personas,
)
from .models import (
    CreatePersonaRequest,
    CreateSessionRequest,
    ExpandPersonaRequest,
    PanelRecommendationResponse,
    RecommendPanelRequest,
    SessionSnapshot,
    UploadedDocument,
    UserInterjectionRequest,
)
from .services.debate import SESSIONS, add_interjection, advance_session, create_session, finish_session, get_session_snapshot
from .services.documents import build_document_context, ingest_upload
from .services.personas import expand_natural_language_persona, slugify
from .services.selection import select_panel


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Perspective Engine API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/personas")
def personas() -> list[dict]:
    return [persona.model_dump() for persona in list_personas()]


@app.get("/api/profile")
def profile() -> dict:
    return get_profile().model_dump()


@app.post("/api/documents", response_model=UploadedDocument)
async def upload_document(file: UploadFile = File(...)) -> UploadedDocument:
    document = await ingest_upload(file)
    return UploadedDocument(**document.model_dump())


@app.delete("/api/documents/{document_id}", response_model=UploadedDocument)
def remove_document(document_id: str) -> UploadedDocument:
    document = delete_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@app.post("/api/personas/expand")
def expand_persona(request: ExpandPersonaRequest) -> dict:
    payload = expand_natural_language_persona(request.description)
    return payload.model_dump()


@app.post("/api/personas")
def new_persona(request: CreatePersonaRequest) -> dict:
    persona_id = slugify(request.name)
    existing = get_persona(persona_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="A persona with that name already exists.")
    persona = create_persona(request, persona_id)
    return persona.model_dump()


@app.post("/api/panel/recommend", response_model=PanelRecommendationResponse)
async def panel_recommendation(request: RecommendPanelRequest) -> PanelRecommendationResponse:
    documents = get_documents(request.document_ids)
    if len(documents) != len(request.document_ids):
        raise HTTPException(status_code=404, detail="One or more documents could not be found.")
    return await select_panel(
        decision=request.decision,
        documents=documents,
        personas=list_personas(),
        profile=get_profile(),
        panel_size=request.panel_size,
        manual_ids=request.manual_ids,
    )


@app.post("/api/sessions", response_model=SessionSnapshot)
def new_session(request: CreateSessionRequest) -> SessionSnapshot:
    personas = [get_persona(persona_id) for persona_id in request.persona_ids]
    if any(persona is None for persona in personas):
        raise HTTPException(status_code=404, detail="One or more personas could not be found.")
    documents = get_documents(request.document_ids)
    if len(documents) != len(request.document_ids):
        raise HTTPException(status_code=404, detail="One or more documents could not be found.")
    increment_persona_usage(request.persona_ids)
    return create_session(
        decision=request.decision,
        personas=[persona for persona in personas if persona is not None],
        profile=get_profile(),
        round_goal=request.round_goal,
        document_context=build_document_context(documents),
        document_names=[document.filename for document in documents],
    )


@app.get("/api/sessions/{session_id}", response_model=SessionSnapshot)
def session_snapshot(session_id: str) -> SessionSnapshot:
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found.")
    return get_session_snapshot(session_id)


@app.post("/api/sessions/{session_id}/interjections", response_model=SessionSnapshot)
def interject(session_id: str, request: UserInterjectionRequest) -> SessionSnapshot:
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found.")
    return add_interjection(session_id, request.content)


@app.post("/api/sessions/{session_id}/advance", response_model=SessionSnapshot)
def advance(session_id: str) -> SessionSnapshot:
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found.")
    return advance_session(session_id)


@app.post("/api/sessions/{session_id}/finish", response_model=SessionSnapshot)
def finish(session_id: str) -> SessionSnapshot:
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found.")
    return finish_session(session_id)
