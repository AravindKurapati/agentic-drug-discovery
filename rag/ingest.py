"""
rag/ingest.py — Fetch PubMed abstracts for a protein target, embed them with
sentence-transformers, and store them in a local Chroma vector DB at .chroma/.

Usage:
    python rag/ingest.py --target EGFR --max-papers 100
"""

import argparse
import time
from pathlib import Path

import chromadb
from Bio import Entrez
from sentence_transformers import SentenceTransformer

# Entrez requires a contact email — no API key needed.
Entrez.email = "arvind.kurapati@gmail.com"

CHROMA_PATH = Path(__file__).resolve().parents[1] / ".chroma"


def fetch_pubmed_abstracts(target: str, max_papers: int) -> list[dict]:
    """Search PubMed and return a list of {pmid, title, abstract} dicts."""
    print(f"Fetching {max_papers} abstracts for {target}...")

    # Step 1: search for PMIDs
    search_handle = Entrez.esearch(
        db="pubmed",
        term=f"{target}[Title/Abstract]",
        retmax=max_papers,
        usehistory="y",
    )
    search_results = Entrez.read(search_handle)
    search_handle.close()

    pmids: list[str] = search_results["IdList"]
    if not pmids:
        return []

    # Step 2: fetch records in one batch (XML)
    fetch_handle = Entrez.efetch(
        db="pubmed",
        id=",".join(pmids),
        rettype="xml",
        retmode="xml",
    )
    records = Entrez.read(fetch_handle)
    fetch_handle.close()

    articles = []
    for record in records["PubmedArticle"]:
        medline = record["MedlineCitation"]
        pmid = str(medline["PMID"])

        article = medline["Article"]
        title = str(article.get("ArticleTitle", ""))

        # Abstract may be absent or structured (list of sections)
        abstract_obj = article.get("Abstract", {})
        abstract_texts = abstract_obj.get("AbstractText", [])
        if isinstance(abstract_texts, list):
            abstract = " ".join(str(t) for t in abstract_texts)
        else:
            abstract = str(abstract_texts)

        if abstract.strip():
            articles.append({"pmid": pmid, "title": title, "abstract": abstract})

    return articles


def ingest(target: str, max_papers: int) -> None:
    articles = fetch_pubmed_abstracts(target, max_papers)
    if not articles:
        print(f"No abstracts found for {target}.")
        return

    # Chroma persistent client
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection_name = f"{target.lower()}_abstracts"
    collection = client.get_or_create_collection(collection_name)

    # Load embedding model (local, no API key)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    new_docs: list[str] = []
    new_ids: list[str] = []
    new_meta: list[dict] = []
    skipped = 0

    for art in articles:
        pmid = art["pmid"]
        # Idempotency check: skip PMIDs already in the collection
        existing = collection.get(ids=[pmid])
        if existing["ids"]:
            skipped += 1
            continue
        new_docs.append(art["abstract"])
        new_ids.append(pmid)
        new_meta.append({"pmid": pmid, "title": art["title"], "target": target})

    if new_docs:
        embeddings = model.encode(new_docs, show_progress_bar=False).tolist()
        collection.add(
            ids=new_ids,
            embeddings=embeddings,
            documents=new_docs,
            metadatas=new_meta,
        )

    print(
        f"Ingested {len(new_docs)} new abstracts "
        f"({skipped} already present)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest PubMed abstracts into a local Chroma vector DB."
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Protein target name to search on PubMed (e.g. EGFR)",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=100,
        help="Maximum number of PubMed abstracts to fetch (default: 100)",
    )
    args = parser.parse_args()

    ingest(target=args.target, max_papers=args.max_papers)


if __name__ == "__main__":
    main()
