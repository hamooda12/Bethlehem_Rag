"""Run with every RAG process using this index stopped."""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from shutil import copytree

from universities import INDEX_DIR, list_universities

# Verified filename and content-hash pairs from the existing index.
LEGACY_OWNERS = {
    ("أنظمة وتعليمات منح درجة البكالوريوس.txt",
     "2c21c827fa5739fbad7842b5a25dfb730af0b1eb1bc3b1c840aa5a6f80c444c4"): "birzeit",
    ("الأمريكية العربية الـ الجامعة.txt",
     "3ab391dddedd8cc604b950900241ed896220cbf5ab4aeb62cd50b75469ee9a84"): "aaup",
}


def backfill(collection, batch_size):
    rows = collection.get(include=["metadatas"])
    documents = defaultdict(list)
    unassigned = 0
    for key, metadata in zip(rows["ids"], rows["metadatas"], strict=True):
        if metadata and metadata.get("file_hash"):
            documents[metadata["file_hash"]].append((key, metadata))
        elif not metadata or not metadata.get("university_id"):
            unassigned += 1

    updates = []
    for file_hash, chunks in documents.items():
        owners = {LEGACY_OWNERS.get((metadata.get("filename"), file_hash)) for _, metadata in chunks}
        if len(owners) != 1 or None in owners:
            unassigned += sum(not m.get("university_id") for _, m in chunks)
            continue
        owner = next(iter(owners))
        if any(m.get("university_id") not in (None, owner) or
               (not m.get("university_id") and m.get("document_id") not in (None, file_hash))
               for _, m in chunks):
            unassigned += sum(not m.get("university_id") for _, m in chunks)
            continue
        updates.extend((key, {**metadata, "university_id": owner, "document_id": file_hash})
                       for key, metadata in chunks if not metadata.get("university_id"))

    for start in range(0, len(updates), batch_size):
        keys, metadata = zip(*updates[start:start + batch_size])
        collection.update(ids=list(keys), metadatas=list(metadata))

    after = collection.get(include=["metadatas"])
    if set(after["ids"]) != set(rows["ids"]):
        raise RuntimeError("Chunk IDs changed during migration")
    after_hashes = {m["file_hash"] for m in after["metadatas"] if m and m.get("file_hash")}
    if after_hashes != documents.keys():
        raise RuntimeError("Document hashes changed during migration")
    print(f"Documents {len(documents)} -> {len(after_hashes)}, chunks {len(rows['ids'])} -> {len(after['ids'])}")
    print(f"Updated chunks: {len(updates)}. Unassigned legacy chunks: {unassigned}.")
    return len(updates), unassigned


if __name__ == "__main__":
    if not (INDEX_DIR / "chroma.sqlite3").is_file():
        raise SystemExit("No existing index found in this working directory.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = Path("chroma-backup-" + stamp)
    copytree(INDEX_DIR, backup)
    print(f"Backup: {backup.resolve()}", flush=True)
    from ingestion import chroma, collection

    list_universities()
    backfill(collection, chroma.get_max_batch_size())
