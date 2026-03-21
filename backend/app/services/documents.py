from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from ..config import Settings
from ..models import StoredDocument
from ..repository import AppRepository

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


async def ingest_upload(repository: AppRepository, settings: Settings, file: UploadFile) -> StoredDocument:
    filename = Path(file.filename or "document").name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type for {filename}. Use .txt, .md, or .pdf.",
        )

    payload = await file.read()
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{filename} is larger than the 10 MB limit.",
        )

    extracted_text = _extract_text(filename, extension, payload)
    normalized_text = _normalize_whitespace(extracted_text)
    if not normalized_text:
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract readable text from {filename}.",
        )

    document_id = str(uuid4())
    storage_path = settings.uploads_dir / f"{document_id}{extension}"
    storage_path.write_bytes(payload)
    chunks = chunk_document_text(normalized_text)

    return repository.create_document(
        document_id=document_id,
        filename=filename,
        mime_type=file.content_type or _mime_type_for_extension(extension),
        size_bytes=len(payload),
        extraction_status="ready",
        extracted_text_preview=normalized_text[:260],
        extracted_char_count=len(normalized_text),
        extracted_text=normalized_text,
        storage_path=str(storage_path),
        chunks=chunks,
    )


def chunk_document_text(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return [chunk for chunk in chunks if chunk]


def build_document_context(documents: list[StoredDocument], limit: int = 4) -> str:
    if not documents:
        return ""

    snippets: list[str] = []
    for document in documents[:limit]:
        for chunk in document.chunks[:2]:
            snippets.append(f"[Document: {document.filename}]\n{chunk}")
    return "\n\n".join(snippets[:limit])


def select_relevant_document_chunks(documents: list[StoredDocument], query: str, limit: int = 4) -> list[str]:
    query_tokens = set(re.findall(r"[a-z0-9-]+", query.lower()))
    scored: list[tuple[int, str]] = []
    for document in documents:
        for chunk in document.chunks:
            tokens = set(re.findall(r"[a-z0-9-]+", chunk.lower()))
            overlap = len(tokens & query_tokens)
            scored.append((overlap, f"[Document: {document.filename}]\n{chunk}"))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [chunk for score, chunk in scored[:limit] if score > 0]
    if selected:
        return selected
    return [f"[Document: {document.filename}]\n{document.chunks[0]}" for document in documents[:limit] if document.chunks]


def _extract_text(filename: str, extension: str, payload: bytes) -> str:
    if extension in {".txt", ".md"}:
        return payload.decode("utf-8", errors="ignore")
    if extension == ".pdf":
        try:
            reader = PdfReader(BytesIO(payload))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as error:
            raise HTTPException(
                status_code=422,
                detail=f"Could not parse PDF {filename}: {error}",
            ) from error
    return ""


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _mime_type_for_extension(extension: str) -> str:
    if extension == ".pdf":
        return "application/pdf"
    if extension == ".md":
        return "text/markdown"
    return "text/plain"
