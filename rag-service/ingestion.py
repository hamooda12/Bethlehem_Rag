# ingestion.py

import hashlib
import math
import sys
from pathlib import Path

import chromadb
import pymupdf
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = "gemini-embedding-001"
DIMENSIONS = 768
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

gemini = genai.Client()
chroma = chromadb.PersistentClient(path="./chroma_db")

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
        return [(1, text)]

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


def ingest(file_path):
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(path)

    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    existing = collection.get(
        where={"file_hash": file_hash},
        limit=1
    )

    if existing["ids"]:
        print("Document already indexed. Skipping.")
        return

    pages = extract_pages(path)

    chunks = []
    metadata = []
    ids = []

    for page_number, text in pages:
        for index, chunk in enumerate(chunk_text(text)):
            chunks.append(chunk)

            metadata.append({
                "filename": path.name,
                "page": page_number,
                "file_hash": file_hash,
                "chunk_index": index
            })

            ids.append(
                f"{file_hash[:16]}-{page_number}-{index}"
            )

    if not chunks:
        raise ValueError(
            "No extractable text found. Scanned PDFs may require OCR."
        )

    print(f"Extracted {len(chunks)} chunks.")

    vectors = embed_documents(chunks)

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=vectors,
        metadatas=metadata
    )

    print("Document indexed successfully.")
    print(f"Total chunks in ChromaDB: {collection.count()}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python ingestion.py <file.pdf|file.txt>")
        sys.exit(1)

    ingest(sys.argv[1])