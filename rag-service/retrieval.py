# retrieval.py
import math
import re
import unicodedata

from dotenv import load_dotenv
from google import genai
from google.genai import types

from ingestion import collection, MODEL, DIMENSIONS
from universities import university_name

load_dotenv()
client = genai.Client()

def normalize_ar(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub("[إأآٱ]", "ا", value)
    return value.replace("ة", "ه").replace("ى", "ي").lower()


def embed_query(question: str):
    response = client.models.embed_content(
        model=MODEL,
        contents=question,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY", output_dimensionality=DIMENSIONS
        ),
    )
    values = response.embeddings[0].values
    norm = math.sqrt(sum(value * value for value in values))
    if not norm:
        raise ValueError("Zero-length query embedding")
    return [value / norm for value in values]


def keyword_score(question: str, passage: str) -> float:
    ignored = {"ما", "من", "في", "هل", "على", "عن", "الى", "كم", "هو", "هي", "جامعه", "الطالب", "طلبه"}

    def words(text):
        return {word for word in re.findall(r"[\u0621-\u064A]+|\d+", normalize_ar(text)) if len(word) > 2 and word not in ignored}

    q_words = words(question)
    return len(q_words & words(passage)) / len(q_words) if q_words else 0.0


def retrieve(question: str, university: str, top_k: int = 4):
    if not university_name(university):
        raise ValueError("Unsupported university")
    if not question.strip() or not 1 <= top_k <= 10:
        raise ValueError("Invalid question or top_k")

    where = {"university_id": university}
    eligible_count = len(collection.get(where=where, include=[])["ids"])
    if not eligible_count:
        return []

    results = collection.query(
        query_embeddings=[embed_query(question)],
        where=where,
        n_results=min(max(15, top_k), eligible_count),
        include=["documents", "metadatas", "distances"],
    )

    matches = []
    for text, metadata, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        semantic_score = max(0.0, 1.0 - distance)
        lexical_score = keyword_score(question, text)
        matches.append({
            "text": text,
            "source": metadata["filename"],
            "page": metadata.get("page"),
            "distance": distance,
            "rerank_score": 0.65 * semantic_score + 0.35 * lexical_score,
        })

    matches.sort(key=lambda x: x["rerank_score"], reverse=True)
    return matches[:top_k]
