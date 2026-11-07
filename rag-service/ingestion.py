# ingestion.py

import hashlib
import math
import sys
from threading import Lock
from pathlib import Path

import chromadb
import pymupdf
from dotenv import load_dotenv
from google import genai
from google.genai import types

from universities import INDEX_DIR, university_name

load_dotenv()

MODEL = "gemini-embedding-001"
DIMENSIONS = 768
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

gemini = genai.Client()
chroma = chromadb.PersistentClient(path=str(INDEX_DIR))
write_lock = Lock()

collection = chroma.get_or_create_collection(
    name="rag_documents",
    metadata={"hnsw:space": "cosine"}
)


def extract_pages(path: Path):
    if path.suffix.lower() == ".pdf":
        with pymupdf.open(path) as pdf:
            return [
                (i + 1, page.get_text("text"))
                for i, page in enumerate(pdf)
            ]

    if path.suffix.lower() == ".txt":
        text = path.read_text(encoding="utf-8-sig")
        return [(None, text)]

    raise ValueError("Only PDF and TXT files are supported")


def chunk_text(text):
    text = " ".join(text.split())
    if not text:
        return []

    chunks = []
    step = CHUNK_SIZE - CHUNK_OVERLAP

    for start in range(0, len(text), step):
        chunk = text[start:start + CHUNK_SIZE]
        if chunk:
            chunks.append(chunk)

        if start + CHUNK_SIZE >= len(text):
            break

    return chunks


def embed_documents(texts):
    vectors = []

    # Small batches to keep requests manageable
    for start in range(0, len(texts), 10):
        batch = texts[start:start + 10]

        result = gemini.models.embed_content(
            model=MODEL,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=DIMENSIONS
            )
        )

        if len(result.embeddings) != len(batch):
            raise RuntimeError("Embedding count mismatch")

        for embedding in result.embeddings:
            values = embedding.values
            norm = math.sqrt(sum(v * v for v in values))

            if norm == 0:
                raise RuntimeError("Zero-length embedding")

            vectors.append([v / norm for v in values])

    return vectors


def find_document(file_hash, university_id=None):
    where = {"file_hash": file_hash}
    if university_id is not None:
        where = {"$and": [where, {"university_id": university_id}]}
    records = collection.get(where=where, include=["metadatas"])["metadatas"]
    documents = {
        (row.get("university_id"), row.get("document_id", file_hash)) for row in records
    }
    return next(iter(documents)) if len(documents) == 1 else None


def ingest(file_path, university_id):
    if not university_name(university_id):
        raise ValueError("Unsupported university")
    path = Path(file_path)
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with write_lock:
        return index_document(path, file_hash, university_id)


def index_document(path, file_hash, university_id):
    existing = find_document(file_hash, university_id)
    if existing:
        return existing[1], "already_indexed"
    document_id = hashlib.sha256(f"{university_id}:{file_hash}".encode()).hexdigest()

    pages = extract_pages(path)

    chunks = []
    metadata = []
    ids = []

    for page_number, text in pages:
        for index, chunk in enumerate(chunk_text(text)):
            chunks.append(chunk)

            metadata.append({
                "filename": path.name,
                **({"page": page_number} if page_number is not None else {}),
                "university_id": university_id,
                "document_id": document_id,
                "file_hash": file_hash,
                "chunk_index": index
            })

            ids.append(
                f"{document_id}-{page_number}-{index}"
            )

    if not chunks:
        raise ValueError(
            "No extractable text found. Scanned PDFs may require OCR."
        )

    print(f"Extracted {len(chunks)} chunks.")

    if len(chunks) > chroma.get_max_batch_size():
        raise ValueError("Document contains too many chunks for one atomic write")
    vectors = embed_documents(chunks)

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=vectors,
        metadatas=metadata
    )

    return document_id, "indexed"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python ingestion.py <file.pdf|file.txt> <university_id>")
        sys.exit(1)

    print(ingest(sys.argv[1], sys.argv[2]))
