# main.py
import hashlib
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from google.genai import errors

from ingestion import ingest, collection
from generation import answer_question
from retrieval import UNIVERSITIES

app = FastAPI(title="IEEE Academic Advisor RAG", version="1.1.0")
MAX_FILE_SIZE = 10 * 1024 * 1024


class ChatRequest(BaseModel):
    university: str
    question: str = Field(min_length=1)
    top_k: int = Field(default=4, ge=1, le=10)


@app.get("/health")
def health():
    return {"status": "ok", "indexed_chunks": collection.count()}


@app.post("/documents", status_code=201)
def upload_document(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in (".pdf", ".txt"):
        raise HTTPException(415, "Only PDF and TXT are supported")
    data = file.file.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "File exceeds 10 MB")
    if not data:
        raise HTTPException(422, "Empty file")

    file_hash = hashlib.sha256(data).hexdigest()
    if collection.get(where={"file_hash": file_hash}, limit=1)["ids"]:
        return {"document_id": file_hash, "filename": filename, "status": "already_indexed"}
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / filename
            path.write_bytes(data)
            ingest(str(path))
        return {"document_id": file_hash, "filename": filename, "status": "indexed"}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except errors.APIError as exc:
        code = getattr(exc, "code", 503)
        raise HTTPException(code if code in (429, 503, 504) else 503,
                            "Gemini API is temporarily unavailable") from exc


@app.get("/documents")
def list_documents():
    docs = {}
    for m in collection.get(include=["metadatas"])["metadatas"]:
        hash_value = m.get("file_hash")
        if not hash_value:
            continue
        if hash_value not in docs:
            docs[hash_value] = {"document_id": hash_value, "filename": m["filename"], "chunks": 0}
        docs[hash_value]["chunks"] += 1
    return {"documents": list(docs.values())}


@app.post("/chat")
def chat(request: ChatRequest):
    if request.university not in UNIVERSITIES:
        raise HTTPException(422, "university must be 'birzeit' or 'aaup'")
    try:
        return answer_question(request.question, request.university, request.top_k)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except errors.APIError as exc:
        code = getattr(exc, "code", 503)
        raise HTTPException(code if code in (429, 503, 504) else 503,
                            "Gemini API is temporarily unavailable") from exc
