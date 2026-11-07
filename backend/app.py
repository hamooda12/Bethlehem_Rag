import os
import secrets
from pathlib import Path, PureWindowsPath

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MAX_FILE_SIZE = 10 * 1024 * 1024
RAG_URL = os.getenv("RAG_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
ADMIN_TOKEN = os.getenv("RAG_ADMIN_TOKEN", "").strip()
DEFAULT_ORIGINS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:5175,http://127.0.0.1:5175"
)
origins = [
    origin.strip()
    for origin in os.getenv("RAG_CORS_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]
if "*" in origins:
    raise ValueError("RAG_CORS_ORIGINS must list explicit frontend origins")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE + 64 * 1024  # Multipart overhead.
CORS(app, origins=origins, methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"])


def error(status, detail):
    return jsonify(detail=detail), status


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(_error):
    return error(413, "File exceeds 10 MB")


def call_rag(method, path, *, read_timeout=10, **kwargs):
    try:
        upstream = requests.request(
            method, RAG_URL + path, timeout=(3, read_timeout),
            allow_redirects=False, **kwargs,
        )
    except requests.Timeout:
        return error(504, "RAG service timed out")
    except requests.RequestException:
        app.logger.warning("RAG request failed for %s", path)
        return error(503, "RAG service is unavailable")

    if 200 <= upstream.status_code < 300:
        try:
            return jsonify(upstream.json()), upstream.status_code
        except ValueError:
            return error(502, "Invalid RAG response")

    messages = {
        401: "Administrator token required",
        409: "University ID already exists",
        413: "File exceeds 10 MB",
        415: "Only PDF and TXT are supported",
        422: "RAG could not process the request",
        429: "RAG request limit reached",
        503: "RAG service is unavailable",
        504: "RAG service timed out",
    }
    if upstream.status_code in messages:
        return error(upstream.status_code, messages[upstream.status_code])
    app.logger.warning("RAG returned HTTP %s for %s", upstream.status_code, path)
    return error(502, "RAG request failed")


@app.get("/health")
def health():
    return call_rag("GET", "/health")


@app.get("/documents")
def documents():
    university_id = request.args.get("university_id")
    params = {"university_id": university_id} if university_id is not None else None
    return call_rag("GET", "/documents", params=params)


@app.get("/universities")
def universities():
    return call_rag("GET", "/universities")


@app.post("/universities")
def add_university():
    denied = require_admin()
    if denied is not None:
        return denied
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error(422, "Expected a JSON object")
    return call_rag("POST", "/universities", json=data,
                    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})


@app.post("/chat")
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error(422, "Expected a JSON object")
    question = data.get("question")
    university = data.get("university")
    top_k = data.get("top_k", 4)
    if not isinstance(question, str) or not question.strip():
        return error(422, "Question cannot be empty")
    if not isinstance(university, str) or not university:
        return error(422, "Unsupported university")
    if type(top_k) is not int or not 1 <= top_k <= 10:
        return error(422, "Invalid top_k")
    return call_rag("POST", "/chat", read_timeout=75, json={
        "university": university,
        "question": question.strip(),
        "top_k": top_k,
    })


def require_admin():
    if not ADMIN_TOKEN:
        return error(503, "Document upload is disabled")
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(
        token.encode("utf-8"), ADMIN_TOKEN.encode("utf-8")
    ):
        response, status = error(401, "Administrator token required")
        response.headers["WWW-Authenticate"] = "Bearer"
        return response, status
    return None


@app.post("/documents")
def upload():
    denied = require_admin()
    if denied is not None:
        return denied
    file = request.files.get("file")
    if file is None:
        return error(422, "Missing file")
    path = PureWindowsPath(file.filename or "")
    filename = path.name
    if Path(filename).suffix.lower() not in (".pdf", ".txt"):
        return error(415, "Only PDF and TXT are supported")
    if path.is_reserved() or any(ord(char) < 32 or char in ':<>|?*"' for char in filename):
        return error(422, "Invalid filename")
    data = file.stream.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        return file_too_large(None)
    if not data:
        return error(422, "Empty file")

    university_id = request.form.get("university_id")
    fields = {"university_id": university_id} if university_id is not None else None
    return call_rag(
        "POST", "/documents", read_timeout=150, data=fields,
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        files={"file": (filename, data, file.mimetype)},
    )
