"""
rag/query.py — Query the Chroma vector DB built by rag/ingest.py.
"""

from pathlib import Path

import chromadb

CHROMA_PATH = Path(__file__).resolve().parents[1] / ".chroma"


def query_abstracts(target: str, query_text: str, n_results: int = 5) -> list[dict]:
    """
    Search the Chroma collection for `target` with `query_text`.

    Returns [{pmid, title, abstract, distance}] ordered by relevance.
    Returns [] if the collection has not been ingested yet.
    """
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection_name = f"{target.lower()}_abstracts"
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        return []

    results = collection.query(query_texts=[query_text], n_results=n_results)
    docs      = results.get("documents", [[]])[0]
    metas     = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    return [
        {
            "pmid": m.get("pmid", ""),
            "title": m.get("title", ""),
            "abstract": d,
            "distance": dist,
        }
        for d, m, dist in zip(docs, metas, distances)
    ]
