"""FastAPI application for the RFP jargon glossary."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_extract import analyze_rfp
from rfp_intelligence import analyze_clause_search, analyze_rfp_sections


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


class SegmentRequest(BaseModel):
    rfp_text: str = Field(default="", max_length=100_000)


class Section(BaseModel):
    heading: str
    start_line: int
    text: str


class SegmentResponse(BaseModel):
    section_count: int
    sections: list[Section]


class ClauseSearchRequest(BaseModel):
    rfp_text: str = Field(default="", max_length=100_000)
    query: str = Field(default="", max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)


class ClauseMatch(BaseModel):
    text: str
    score: float


class ClauseSearchResponse(BaseModel):
    matches: list[ClauseMatch]


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


@app.post("/segment-rfp", response_model=SegmentResponse)
async def segment_rfp(request: SegmentRequest) -> SegmentResponse:
    try:
        sections, _mode = await analyze_rfp_sections(request.rfp_text)
        return SegmentResponse(section_count=len(sections), sections=sections)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/search-clauses", response_model=ClauseSearchResponse)
async def search_clauses(request: ClauseSearchRequest) -> ClauseSearchResponse:
    try:
        matches, _mode = await analyze_clause_search(request.rfp_text, request.query, request.top_k)
        return ClauseSearchResponse(matches=matches)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
