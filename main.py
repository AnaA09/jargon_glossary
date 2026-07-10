"""FastAPI application for the RFP jargon glossary."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_extract import analyze_rfp


load_dotenv()
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="jargon_glossary",
    description="Turn government procurement jargon into plain English.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class GlossaryRequest(BaseModel):
    rfp_text: str = Field(default="", max_length=100_000)


class Term(BaseModel):
    term: str
    definition: str


class GlossaryResponse(BaseModel):
    summary: str
    terms: list[Term]


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/extract-glossary", response_model=GlossaryResponse)
async def glossary(request: GlossaryRequest) -> GlossaryResponse:
    try:
        result, _mode = await analyze_rfp(request.rfp_text)
        return GlossaryResponse(summary=result["summary"], terms=result["terms"])
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
