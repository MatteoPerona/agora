from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from ..db import UPLOADS_DIR, create_document
from ..models import StoredDocument

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


async def ingest_upload(file: UploadFile) -> StoredDocument:
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
    storage_path = UPLOADS_DIR / f"{document_id}{extension}"
    storage_path.write_bytes(payload)

    return create_document(
        document_id=document_id,
        filename=filename,
        mime_type=file.content_type or _mime_type_for_extension(extension),
        size_bytes=len(payload),
        extraction_status="ready",
        extracted_text_preview=normalized_text[:260],
        extracted_char_count=len(normalized_text),
        extracted_text=normalized_text,
        storage_path=str(storage_path),
    )


def build_document_context(documents: list[StoredDocument]) -> str:
    if not documents:
        return ""

    snippets: list[str] = []
    for document in documents:
        excerpt = document.extracted_text[:1800].strip()
        snippets.append(f"[Document: {document.filename}]\n{excerpt}")
    return "\n\n".join(snippets)


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

