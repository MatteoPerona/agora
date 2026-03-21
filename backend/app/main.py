from __future__ import annotations

import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .bootstrap import initialize_app
from .config import Settings, get_settings
from .database import SessionLocal, get_db_session
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
from .repository import AppRepository
from .session_lock import session_lock
from .services.documents import build_document_context, ingest_upload, select_relevant_document_chunks
from .services.personas import expand_natural_language_persona, slugify
from .services.selection import select_panel
from .simulation.service import SimulationService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    initialize_app(settings)
    logger.info(
        "Perspective Engine starting with provider=%s model=%s selector_model=%s summary_model=%s",
        settings.normalized_provider,
        settings.sim_model,
        settings.selector_model,
        settings.summary_model,
    )
    yield


app = FastAPI(title="Perspective Engine API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_repository(session: Session = Depends(get_db_session)) -> AppRepository:
    return AppRepository(session)


def get_simulation_service(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> SimulationService:
    return SimulationService(session, settings)


@app.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "provider": settings.normalized_provider}


@app.get("/api/personas")
def personas(repository: AppRepository = Depends(get_repository)) -> list[dict]:
    return [persona.model_dump() for persona in repository.list_personas()]


@app.get("/api/profile")
def profile(repository: AppRepository = Depends(get_repository)) -> dict:
    return repository.get_profile().model_dump()


@app.post("/api/documents", response_model=UploadedDocument)
async def upload_document(
    file: UploadFile = File(...),
    repository: AppRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> UploadedDocument:
    document = await ingest_upload(repository, settings, file)
    repository.session.commit()
    return UploadedDocument(**document.model_dump(exclude={"storage_path", "extracted_text", "chunks"}))


@app.delete("/api/documents/{document_id}", response_model=UploadedDocument)
def remove_document(document_id: str, repository: AppRepository = Depends(get_repository)) -> UploadedDocument:
    existing = repository.get_document(document_id)
    document = repository.delete_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    repository.session.commit()
    if existing is not None:
        path = Path(existing.storage_path)
        if path.exists():
            path.unlink()
    return document


@app.post("/api/personas/expand")
def expand_persona(request: ExpandPersonaRequest) -> dict:
    payload = expand_natural_language_persona(request.description)
    return payload.model_dump()


@app.post("/api/personas")
def new_persona(request: CreatePersonaRequest, repository: AppRepository = Depends(get_repository)) -> dict:
    persona_id = slugify(request.name)
    existing = repository.get_persona(persona_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="A persona with that name already exists.")
    persona = repository.create_persona(request, persona_id)
    repository.session.commit()
    return persona.model_dump()


@app.post("/api/panel/recommend", response_model=PanelRecommendationResponse)
async def panel_recommendation(
    request: RecommendPanelRequest,
    repository: AppRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> PanelRecommendationResponse:
    documents = repository.get_documents(request.document_ids)
    if len(documents) != len(request.document_ids):
        raise HTTPException(status_code=404, detail="One or more documents could not be found.")
    response = await select_panel(
        decision=request.decision,
        documents=documents,
        personas=repository.list_personas(),
        profile=repository.get_profile(),
        panel_size=request.panel_size,
        manual_ids=request.manual_ids,
        provider_factory=SimulationService(repository.session, settings).provider_factory,
    )
    repository.session.commit()
    return response


@app.post("/api/sessions", response_model=SessionSnapshot)
async def new_session(
    request: CreateSessionRequest,
    repository: AppRepository = Depends(get_repository),
    service: SimulationService = Depends(get_simulation_service),
) -> SessionSnapshot:
    personas = [repository.get_persona(persona_id) for persona_id in request.persona_ids]
    if any(persona is None for persona in personas):
        raise HTTPException(status_code=404, detail="One or more personas could not be found.")
    documents = repository.get_documents(request.document_ids)
    if len(documents) != len(request.document_ids):
        raise HTTPException(status_code=404, detail="One or more documents could not be found.")
    return await service.create_session(
        request=request,
        personas=[persona for persona in personas if persona is not None],
        profile=repository.get_profile(),
        document_context=build_document_context(documents),
        document_names=[document.filename for document in documents],
    )


@app.get("/api/sessions/{session_id}", response_model=SessionSnapshot)
def session_snapshot(session_id: str, service: SimulationService = Depends(get_simulation_service)) -> SessionSnapshot:
    try:
        return service.get_snapshot(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")


@app.post("/api/sessions/{session_id}/interjections", response_model=SessionSnapshot)
def interject(
    session_id: str,
    request: UserInterjectionRequest,
    service: SimulationService = Depends(get_simulation_service),
) -> SessionSnapshot:
    try:
        return service.add_interjection(session_id, request.content)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")


@app.post("/api/sessions/{session_id}/advance", response_model=SessionSnapshot)
async def advance(
    session_id: str,
    repository: AppRepository = Depends(get_repository),
    service: SimulationService = Depends(get_simulation_service),
) -> SessionSnapshot:
    try:
        simulation = repository.get_simulation(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")

    documents = repository.get_documents(simulation.document_ids)
    relevant_chunks = select_relevant_document_chunks(
        documents,
        query=f"{simulation.decision} round {simulation.current_round + 1}",
        limit=4,
    )
    try:
        async with session_lock(session_id):
            return await service.advance_session(simulation_id=session_id, documents=relevant_chunks)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")


@app.post("/api/sessions/{session_id}/finish", response_model=SessionSnapshot)
async def finish(
    session_id: str,
    repository: AppRepository = Depends(get_repository),
    service: SimulationService = Depends(get_simulation_service),
) -> SessionSnapshot:
    try:
        simulation = repository.get_simulation(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")

    relevant_chunks = select_relevant_document_chunks(
        repository.get_documents(simulation.document_ids),
        query=f"{simulation.decision} final brief",
        limit=6,
    )
    async with session_lock(session_id):
        return await service.finish_session(
            simulation_id=session_id,
            documents=relevant_chunks,
            profile=repository.get_profile(),
        )


@app.get("/api/sessions/{session_id}/events")
async def session_events(
    session_id: str,
    last_event_id: int | None = Query(default=None),
    settings: Settings = Depends(get_settings),
):
    async def event_stream():
        current_last = last_event_id
        idle_cycles = 0
        while idle_cycles < 30:
            with SessionLocal(settings)() as session:
                service = SimulationService(session, settings)
                try:
                    events = service.list_events(session_id, current_last)
                except ValueError:
                    yield "event: error\ndata: {\"detail\":\"Session not found.\"}\n\n"
                    return

            if events:
                idle_cycles = 0
                for event in events:
                    current_last = event.id
                    yield f"id: {event.id}\nevent: {event.event_type}\ndata: {event.model_dump_json()}\n\n"
            else:
                idle_cycles += 1
                yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
