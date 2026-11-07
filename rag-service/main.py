# main.py
import hashlib
import os
import secrets
import tempfile
from pathlib import Path, PureWindowsPath

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from google.genai import errors

from ingestion import ingest, collection, find_document
from generation import answer_question
from universities import list_universities, create_university, university_name

app = FastAPI(title="IEEE Academic Advisor RAG", version="1.1.0")
MAX_FILE_SIZE = 10 * 1024 * 1024
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
ADMIN_TOKEN = os.getenv("RAG_ADMIN_TOKEN", "").strip()
bearer = HTTPBearer(auto_error=False)


def require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not ADMIN_TOKEN:
        raise HTTPException(503, "Document upload is disabled")
    if not credentials or not secrets.compare_digest(
        credentials.credentials.encode("utf-8"), ADMIN_TOKEN.encode("utf-8")
    ):
        raise HTTPException(
            401, "Administrator token required", headers={"WWW-Authenticate": "Bearer"}
        )


class UniversityRequest(BaseModel):
    id: str
    name: str


@app.get("/universities")
def universities():
    return {"universities": list_universities()}


@app.post("/universities", status_code=201, dependencies=[Depends(require_admin)])
def add_university(request: UniversityRequest):
    try:
        university = create_university(request.id, request.name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if university is None:
        raise HTTPException(409, "University ID already exists")
    return university


class ChatRequest(BaseModel):
    university: str
    question: str = Field(min_length=1)
    top_k: int = Field(default=4, ge=1, le=10)


@app.get("/health")
def health():
    return {"status": "ok", "indexed_chunks": collection.count()}


@app.post("/documents", status_code=201, dependencies=[Depends(require_admin)])
def upload_document(file: UploadFile = File(...), university_id: str | None = Form(None)):
    path = PureWindowsPath(file.filename or "")
    filename = path.name
    if path.is_reserved() or any(ord(char) < 32 or char in ':<>|?*"' for char in filename):
        raise HTTPException(422, "Invalid filename")
    if university_id is not None and not university_name(university_id):
        raise HTTPException(422, "Unsupported university")
    if Path(filename).suffix.lower() not in (".pdf", ".txt"):
        raise HTTPException(415, "Only PDF and TXT are supported")
    data = file.file.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "File exceeds 10 MB")
    if not data:
        raise HTTPException(422, "Empty file")

    if university_id is None:
        # Legacy callers may check a known duplicate, but new ownership must be explicit.
        existing = find_document(hashlib.sha256(data).hexdigest())
        if existing:
            return {"document_id": existing[1], "filename": filename, "status": "already_indexed",
                    "university_id": existing[0]}
        raise HTTPException(422, "University is required for new documents")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / filename
            path.write_bytes(data)
            document_id, status = ingest(path, university_id)
        return {"document_id": document_id, "filename": filename, "status": status,
                "university_id": university_id}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except errors.APIError as exc:
        code = getattr(exc, "code", 503)
        raise HTTPException(code if code in (429, 503, 504) else 503,
                            "Gemini API is temporarily unavailable") from exc


@app.get("/documents")
def list_documents(university_id: str | None = None):
    if university_id is not None and not university_name(university_id):
        raise HTTPException(422, "Unsupported university")
    where = {"university_id": university_id} if university_id else None
    docs = {}
    for m in collection.get(where=where, include=["metadatas"])["metadatas"]:
        if not m or not m.get("file_hash"):
            continue
        document_id = m.get("document_id", m["file_hash"])
        if document_id not in docs:
            docs[document_id] = {"document_id": document_id, "filename": m["filename"],
                                 "chunks": 0, "university_id": m.get("university_id")}
        docs[document_id]["chunks"] += 1
    return {"documents": list(docs.values())}


@app.post("/chat")
def chat(request: ChatRequest):
    try:
        return answer_question(request.question, request.university, request.top_k)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except errors.APIError as exc:
        code = getattr(exc, "code", 503)
        raise HTTPException(code if code in (429, 503, 504) else 503,
                            "Gemini API is temporarily unavailable") from exc
