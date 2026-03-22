from __future__ import annotations

import logging
import asyncio
import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
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
    RuntimeLLMConfig,
    RuntimeLLMConfigResponse,
    SessionSnapshot,
    UpdatePersonaRequest,
    UploadedDocument,
    UserInterjectionRequest,
)
from .repository import AppRepository
from .session_lock import session_lock
from .services.documents import build_document_context, ingest_upload, select_relevant_document_chunks
from .services.personas import expand_natural_language_persona, slugify
from .services.selection import select_panel
from .simulation.prompts import build_expand_persona_prompt
from .simulation.provider import SimulationProviderFactory, StructuredLLMClient
from .runtime_config import (
    build_effective_settings,
    clear_runtime_config as clear_session_runtime_config,
    get_runtime_config as get_session_runtime_config,
    get_session_id,
    set_runtime_config as set_session_runtime_config,
)

if TYPE_CHECKING:
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
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
_FRONTEND_INDEX = _FRONTEND_DIST / "index.html"
_FRONTEND_AVAILABLE = _FRONTEND_DIST.exists()

if _FRONTEND_AVAILABLE:
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="frontend-assets")
    
    @app.middleware("http")
    async def serve_frontend(request: Request, call_next):
        response = await call_next(request)
        if request.method != "GET":
            return response
        if response.status_code != 404:
            return response
        path = request.url.path
        if path.startswith("/api/") or path in {"/api", "/health", "/docs", "/redoc", "/openapi.json", "/assets"}:
            return response
        if path.startswith("/assets/"):
            return response
        if path != "/":
            candidate = _FRONTEND_DIST / path.lstrip("/")
            if candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
        if _FRONTEND_INDEX.exists():
            return FileResponse(_FRONTEND_INDEX)
        return response
else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "status": "ok",
            "message": "Perspective Engine API is running. Start frontend at http://127.0.0.1:5173",
        }


def get_repository(session: Session = Depends(get_db_session)) -> AppRepository:
    return AppRepository(session)


def get_runtime_settings(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> Settings:
    session_id = get_session_id(request, response)
    return build_effective_settings(settings, get_session_runtime_config(session_id))


def get_simulation_service(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_runtime_settings),
) -> "SimulationService":
    from .simulation.service import SimulationService

    return SimulationService(session, settings)


@app.get("/api/runtime/config", response_model=RuntimeLLMConfigResponse)
def runtime_config_status(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> RuntimeLLMConfigResponse:
    session_id = get_session_id(request, response)
    runtime_settings = get_session_runtime_config(session_id)
    resolved = build_effective_settings(settings, runtime_settings)
    return RuntimeLLMConfigResponse(
        provider=resolved.sim_provider,
        model=resolved.sim_model,
        selector_model=resolved.sim_selector_model,
        summary_model=resolved.sim_summary_model,
        base_url=resolved.sim_base_url,
        api_key_set=bool(resolved.sim_api_key),
        source="session" if runtime_settings else "default",
    )


@app.post("/api/runtime/config", response_model=RuntimeLLMConfigResponse)
def set_runtime_config(
    request: Request,
    response: Response,
    payload: RuntimeLLMConfig,
    settings: Settings = Depends(get_settings),
) -> RuntimeLLMConfigResponse:
    session_id = get_session_id(request, response)
    try:
        resolved = build_effective_settings(
            settings,
            RuntimeLLMConfig(
                provider=(payload.provider or "").strip() or "stub",
                model=(payload.model or "").strip() or "stub",
                selector_model=payload.selector_model,
                summary_model=payload.summary_model,
                base_url=payload.base_url,
                api_key=payload.api_key,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid runtime config: {exc}")

    set_session_runtime_config(
        session_id,
        RuntimeLLMConfig(
            provider=resolved.normalized_provider,
            model=resolved.sim_model,
            selector_model=resolved.sim_selector_model,
            summary_model=resolved.sim_summary_model,
            base_url=resolved.sim_base_url or "",
            api_key=resolved.sim_api_key,
        ),
    )

    return RuntimeLLMConfigResponse(
        provider=resolved.sim_provider,
        model=resolved.sim_model,
        selector_model=resolved.sim_selector_model,
        summary_model=resolved.sim_summary_model,
        base_url=resolved.sim_base_url,
        api_key_set=bool(resolved.sim_api_key),
        source="session",
    )


@app.delete("/api/runtime/config")
def clear_runtime_config(request: Request, response: Response) -> None:
    session_id = get_session_id(request, response)
    clear_session_runtime_config(session_id)
    return None


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


_RANDOM_SEEDS = [
    "A retired lighthouse keeper who spent 20 years talking only to seagulls and now has very strong opinions about solitude",
    "A competitive crossword puzzle champion who sees every problem as a grid waiting to be filled",
    "A former child prodigy who burned out at 16 and has spent the last decade unlearning everything",
    "A hospice nurse who has sat with hundreds of people in their final hours and is no longer afraid of any question",
    "A deep-sea diver who found something unexplainable 400 metres down and hasn't spoken about it until now",
    "A person who grew up in a travelling circus and believes everything in life is either a performance or an audience",
    "An insomniac philosopher who does their best thinking at 3am and mistrusts anyone who sleeps soundly",
    "A professional beekeeper who models all human behaviour on the logic of the hive",
    "A failed stand-up comedian who became a moral philosopher after a particularly brutal open-mic night",
    "A grandmother who survived three revolutions and still tends her garden every morning without fail",
    "A cartographer who maps things that don't exist yet and believes imagination is the most rigorous discipline",
    "A child psychologist who secretly thinks adults are far more confused than children",
    "A sommelier who applies the same precision to evaluating ideas as they do to wine",
    "A wilderness survival instructor who believes comfort is the enemy of clarity",
    "A translator who has worked in 11 languages and thinks meaning is always lost and that's beautiful",
    "A medieval historian who is convinced nothing about human nature has changed in 800 years",
    "A night-shift baker who thinks the world looks completely different at 4am and everyone else is missing it",
    "An astronomer who has spent 30 years staring at things too far away to touch and finds this comforting",
    "A reformed fraudster who now consults on trust and authenticity with an impeccable poker face",
    "A botanist who believes plants solve problems humans haven't even thought to ask yet",
]


@app.post("/api/personas/random")
async def random_persona(settings: Settings = Depends(get_runtime_settings)) -> dict:
    seed = random.choice(_RANDOM_SEEDS)
    if settings.normalized_provider != "stub":
        try:
            factory = SimulationProviderFactory(settings)
            client = StructuredLLMClient(factory.create_selector_backend())
            result = await client.generate_json(
                system_prompt="You create detailed, richly characterful debate personas for a philosophical deliberation council.",
                user_prompt=build_expand_persona_prompt(seed),
                schema=CreatePersonaRequest,
            )
            return {**result.model_dump(), "seed_description": seed}
        except Exception as exc:
            logger.warning("LLM random persona expansion failed (%s); falling back to heuristic.", exc)
    payload = expand_natural_language_persona(seed)
    return {**payload.model_dump(), "seed_description": seed}


@app.delete("/api/personas/{persona_id}")
def remove_persona(persona_id: str, repository: AppRepository = Depends(get_repository)) -> dict:
    persona = repository.delete_persona(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found.")
    repository.session.commit()
    return persona.model_dump()


@app.post("/api/personas/expand")
async def expand_persona(
    request: ExpandPersonaRequest,
    settings: Settings = Depends(get_runtime_settings),
) -> dict:
    # Use the real LLM when a provider is configured; otherwise use the fast heuristic fallback.
    if settings.normalized_provider != "stub":
        try:
            factory = SimulationProviderFactory(settings)
            client = StructuredLLMClient(factory.create_selector_backend())
            result = await client.generate_json(
                system_prompt="You create detailed, realistic debate personas for structured deliberation simulations.",
                user_prompt=build_expand_persona_prompt(request.description),
                schema=CreatePersonaRequest,
            )
            return result.model_dump()
        except Exception as exc:
            logger.warning("LLM persona expansion failed (%s); falling back to heuristic.", exc)
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


@app.patch("/api/personas/{persona_id}")
def update_persona(
    persona_id: str,
    request: UpdatePersonaRequest,
    repository: AppRepository = Depends(get_repository),
) -> dict:
    updated = repository.update_persona(persona_id, request.model_dump(exclude_none=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Persona not found.")
    repository.session.commit()
    return updated.model_dump()


@app.post("/api/panel/recommend", response_model=PanelRecommendationResponse)
async def panel_recommendation(
    request: RecommendPanelRequest,
    repository: AppRepository = Depends(get_repository),
    settings: Settings = Depends(get_runtime_settings),
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
        provider_factory=SimulationProviderFactory(settings),
    )
    repository.session.commit()
    return response


@app.post("/api/sessions", response_model=SessionSnapshot)
async def new_session(
    request: CreateSessionRequest,
    repository: AppRepository = Depends(get_repository),
    service: "SimulationService" = Depends(get_simulation_service),
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
def session_snapshot(session_id: str, service: "SimulationService" = Depends(get_simulation_service)) -> SessionSnapshot:
    try:
        return service.get_snapshot(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")


@app.post("/api/sessions/{session_id}/interjections", response_model=SessionSnapshot)
def interject(
    session_id: str,
    request: UserInterjectionRequest,
    service: "SimulationService" = Depends(get_simulation_service),
) -> SessionSnapshot:
    try:
        return service.add_interjection(session_id, request.content)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found.")


@app.post("/api/sessions/{session_id}/advance", response_model=SessionSnapshot)
async def advance(
    session_id: str,
    repository: AppRepository = Depends(get_repository),
    service: "SimulationService" = Depends(get_simulation_service),
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
    service: "SimulationService" = Depends(get_simulation_service),
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
                from .simulation.service import SimulationService

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
