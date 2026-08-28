"""FastAPI application for the RFP jargon glossary."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_extract import analyze_rfp
from rfp_intelligence import (
    analyze_clause_search,
    analyze_rfp_sections,
    answer_rfp_question,
    build_compliance_matrix,
    extract_requirement_checklist,
    reconstruct_outline,
    resolve_amendments,
)


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


class AskRfpRequest(BaseModel):
    rfp_text: str = Field(default="", max_length=100_000)
    question: str = Field(default="", max_length=500)


class AskRfpResponse(BaseModel):
    answer: str
    source_excerpt: str
    confidence: str


class RequirementRequest(BaseModel):
    rfp_text: str = Field(default="", max_length=100_000)


class Requirement(BaseModel):
    item: str
    mandatory: bool
    detail: str


class RequirementResponse(BaseModel):
    requirements: list[Requirement]
    requirement_count: int


class Amendment(BaseModel):
    amendment_number: int
    date: str
    text: str


class ResolveAmendmentsRequest(BaseModel):
    original_text: str = Field(default="", max_length=100_000)
    amendments: list[Amendment] = Field(default_factory=list)


class EffectiveSection(BaseModel):
    section: str
    heading: str
    text: str | None
    status: str
    modified_by_amendment: int | None


class ChangelogEntry(BaseModel):
    amendment_number: int
    date: str
    section: str
    action: str


class ResolveAmendmentsResponse(BaseModel):
    effective_sections: list[EffectiveSection]
    changelog: list[ChangelogEntry]
    unmatched_amendment_text: list[str]


class OutlineRequest(BaseModel):
    document_text: str = Field(default="", max_length=100_000)


class OutlineNode(BaseModel):
    number: str
    heading: str
    depth: int
    text: str
    children: list["OutlineNode"] = Field(default_factory=list)


class OutlineWarning(BaseModel):
    type: str
    location: str
    detail: str


class OutlineResponse(BaseModel):
    outline: list[OutlineNode]
    warnings: list[OutlineWarning]


class ComplianceRequirement(BaseModel):
    id: str
    text: str
    mandatory: bool


class ComplianceMatrixRequest(BaseModel):
    requirements: list[ComplianceRequirement] = Field(default_factory=list)
    proposal_text: str = Field(default="", max_length=100_000)


class ComplianceRow(BaseModel):
    requirement_id: str
    status: str
    confidence: str
    matched_passage: str | None
    similarity_score: float
    note: str | None = None


class ComplianceMatrixResponse(BaseModel):
    matrix: list[ComplianceRow]
    mandatory_requirements_met: int
    mandatory_requirements_total: int
    overall_flag: str


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


@app.post("/ask-rfp", response_model=AskRfpResponse)
async def ask_rfp(request: AskRfpRequest) -> AskRfpResponse:
    try:
        result = await answer_rfp_question(request.rfp_text, request.question)
        return AskRfpResponse(**result)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/extract-requirements", response_model=RequirementResponse)
async def extract_requirements(request: RequirementRequest) -> RequirementResponse:
    requirements = extract_requirement_checklist(request.rfp_text)
    return RequirementResponse(requirements=requirements, requirement_count=len(requirements))


@app.post("/resolve-amendments", response_model=ResolveAmendmentsResponse)
async def resolve_rfp_amendments(request: ResolveAmendmentsRequest) -> ResolveAmendmentsResponse:
    result = resolve_amendments(
        request.original_text,
        [amendment.model_dump() for amendment in request.amendments],
    )
    return ResolveAmendmentsResponse(**result)


@app.post("/reconstruct-outline", response_model=OutlineResponse)
async def reconstruct_document_outline(request: OutlineRequest) -> OutlineResponse:
    return OutlineResponse(**reconstruct_outline(request.document_text))


@app.post("/build-compliance-matrix", response_model=ComplianceMatrixResponse)
async def build_requirement_compliance_matrix(request: ComplianceMatrixRequest) -> ComplianceMatrixResponse:
    result = build_compliance_matrix(
        [requirement.model_dump() for requirement in request.requirements],
        request.proposal_text,
    )
    return ComplianceMatrixResponse(**result)
