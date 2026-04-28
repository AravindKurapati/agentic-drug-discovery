"""FastAPI entrypoint. Run with:

    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

# Load .env first — run_pipeline reads NVIDIA_API_KEY from env.
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .runs import router as runs_router

app = FastAPI(title="Agentic Drug Discovery API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "service": "agentic-drug-discovery", "version": "0.1.0"}


app.include_router(runs_router)
