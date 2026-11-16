from contextlib import asynccontextmanager
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from agents.pipeline import generate_comparison, generate_review
from rag.chatbot import answer_question
from scraper.scraper import PHONES

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(OLLAMA_BASE_URL)
        if resp.status_code == 200:
            print(f"Ollama is reachable at {OLLAMA_BASE_URL}")
        else:
            print(f"Ollama returned status {resp.status_code}")
    except Exception as e:
        print(f"Could not reach Ollama at {OLLAMA_BASE_URL}: {e}")

    yield


app = FastAPI(
    title="Samsung Phone AI",
    description="RAG chatbot and agent pipeline for 12 Samsung phones.",
    version="1.0.0",
    lifespan=lifespan,
)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


class CompareRequest(BaseModel):
    phone1: str
    phone2: str


class CompareResponse(BaseModel):
    phone1: str
    phone2: str
    comparison: str


def resolve_phone(raw_name: str) -> str:
    cleaned = raw_name.strip()
    if cleaned in PHONES:
        return cleaned

    lower = cleaned.lower()
    for canonical in PHONES:
        if canonical.lower() == lower:
            return canonical

    valid = sorted(PHONES.keys())
    raise HTTPException(
        status_code=404,
        detail={
            "error": f"Phone '{raw_name}' not found.",
            "valid_phones": valid,
        },
    )


@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")
    answer = answer_question(body.question)
    return AskResponse(answer=answer)


@app.get("/review/{phone_model}")
async def review(phone_model: str):
    canonical = resolve_phone(phone_model)
    result = generate_review(canonical)
    return {"phone": canonical, "review": result}


@app.post("/compare", response_model=CompareResponse)
async def compare(body: CompareRequest):
    canonical1 = resolve_phone(body.phone1)
    canonical2 = resolve_phone(body.phone2)

    if canonical1 == canonical2:
        raise HTTPException(
            status_code=422,
            detail="phone1 and phone2 must be different phones.",
        )

    comparison = generate_comparison(canonical1, canonical2)
    return CompareResponse(phone1=canonical1, phone2=canonical2, comparison=comparison)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Samsung Phone AI is running. Visit /docs for the API.",
        "supported_phones": sorted(PHONES.keys()),
    }
