import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai_extract import _openrouter_request
from rfp_intelligence import _openrouter_search_clauses, _openrouter_segment_rfp
from main import app


client = TestClient(app)
SAMPLE = "The COTR coordinates with the PWS TPOC under FAR and DFARS before CPARS submission. COTR confirms it."


@pytest.fixture(autouse=True)
def force_local_mode(monkeypatch):
    """Unit tests must never call a paid external AI service."""
    monkeypatch.setenv("GLOSSARY_MODE", "local")


def test_sample_has_six_unique_terms():
    response = client.post("/extract-glossary", json={"rfp_text": SAMPLE})
    assert response.status_code == 200
    data = response.json()
    assert data["summary"].startswith("In plain English:")
    assert "COTR" not in data["summary"]
    assert "PWS" not in data["summary"]
    assert "FAR" not in data["summary"]
    assert "government technical representative" in data["summary"]
    assert "federal purchasing rules" in data["summary"]
    terms = [item["term"] for item in data["terms"]]
    assert terms == ["COTR", "PWS", "TPOC", "FAR", "DFARS", "CPARS"]
    assert len(terms) == len(set(terms))


def test_simple_text_returns_empty_list():
    response = client.post("/extract-glossary", json={"rfp_text": "Hello world"})
    assert response.status_code == 200
    assert response.json()["terms"] == []
    assert response.json()["summary"].startswith("In plain English:")


def test_unknown_acronyms_are_not_silently_dropped():
    response = client.post(
        "/extract-glossary",
        json={"rfp_text": "The XYZQ team shall coordinate with the ABCD office. XYZQ reports weekly."},
    )
    assert response.status_code == 200
    terms = response.json()["terms"]
    assert [item["term"] for item in terms] == ["XYZQ", "ABCD"]
    assert terms[0]["definition"].startswith("A team referenced in this document.")
    assert "In context:" in terms[0]["definition"]


def test_expansion_in_document_is_used_as_definition():
    response = client.post(
        "/extract-glossary",
        json={"rfp_text": "The Integrated Review Board (IRB) shall approve the plan."},
    )
    assert response.status_code == 200
    assert response.json()["terms"] == [
        {"term": "IRB", "definition": "The Integrated Review Board. This expansion is provided in the document."}
    ]


def test_known_mixed_case_acronym_gets_full_definition():
    response = client.post(
        "/extract-glossary",
        json={"rfp_text": "The cloud service must maintain FedRAMP authorization."},
    )
    assert response.status_code == 200
    assert response.json()["terms"][0]["term"] == "FEDRAMP"
    assert response.json()["terms"][0]["definition"].startswith("Federal Risk and Authorization Management Program.")


def test_openrouter_request_uses_bearer_key_and_parses_terms():
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            content = json.dumps({"terms": [{"term": "FAR", "definition": "Federal Acquisition Regulation."}]})
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
        assert request.get_header("Authorization") == "Bearer test-key"
        assert timeout == 45
        body = json.loads(request.data)
        assert body["model"] == "openrouter/auto"
        assert body["response_format"] == {"type": "json_object"}
        return FakeResponse()

    with patch("urllib.request.urlopen", fake_urlopen):
        assert _openrouter_request("FAR applies.", "test-key") == {
            "summary": "",
            "terms": [{"term": "FAR", "definition": "Federal Acquisition Regulation."}],
        }


def test_home_and_health():
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}


def test_segment_rfp_detects_and_normalizes_sections():
    response = client.post(
        "/segment-rfp",
        json={
            "rfp_text": (
                "SECTION 1: Scope of Work\n"
                "The contractor shall provide help desk services.\n\n"
                "SECTION 2: Submission Instructions\n"
                "Proposals must be submitted by email."
            )
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["section_count"] == 2
    assert data["sections"][0]["heading"] == "SCOPE OF WORK"
    assert data["sections"][1]["heading"] == "SUBMISSION REQUIREMENTS"


def test_segment_rfp_without_headings_returns_whole_document():
    response = client.post(
        "/segment-rfp",
        json={"rfp_text": "The contractor shall provide support. Proposals are due Friday."},
    )
    assert response.status_code == 200
    assert response.json() == {
        "section_count": 1,
        "sections": [
            {
                "heading": "DOCUMENT",
                "start_line": 1,
                "text": "The contractor shall provide support. Proposals are due Friday.",
            }
        ],
    }


def test_search_clauses_returns_relevant_matches():
    response = client.post(
        "/search-clauses",
        json={
            "rfp_text": (
                "The contractor shall provide help desk services.\n\n"
                "The offeror must carry general liability insurance of at least $1,000,000.\n\n"
                "Proposals will be evaluated on technical approach and price."
            ),
            "query": "what insurance is required?",
            "top_k": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["matches"]) == 2
    assert "insurance" in data["matches"][0]["text"].lower()


def test_openrouter_segment_rfp_parses_sections():
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            content = json.dumps(
                {
                    "sections": [
                        {"heading": "SCOPE OF WORK", "start_line": 1, "text": "The contractor shall provide support."}
                    ]
                }
            )
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    def fake_urlopen(request, timeout):
        assert request.get_header("Authorization") == "Bearer test-key"
        body = json.loads(request.data)
        assert "Split the supplied RFP text" in body["messages"][0]["content"]
        return FakeResponse()

    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}), patch("urllib.request.urlopen", fake_urlopen):
        assert _openrouter_segment_rfp("SECTION 1: SCOPE OF WORK\nThe contractor shall provide support.") == [
            {"heading": "SCOPE OF WORK", "start_line": 1, "text": "The contractor shall provide support."}
        ]


def test_openrouter_search_clauses_parses_matches():
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            content = json.dumps({"matches": [{"text": "Insurance is required.", "score": 0.91}]})
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    def fake_urlopen(request, timeout):
        assert request.get_header("Authorization") == "Bearer test-key"
        body = json.loads(request.data)
        assert "finding relevant clauses" in body["messages"][0]["content"]
        assert json.loads(body["messages"][1]["content"])["top_k"] == 3
        return FakeResponse()

    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}), patch("urllib.request.urlopen", fake_urlopen):
        assert _openrouter_search_clauses("Insurance is required.", "insurance?", 3) == [
            {"text": "Insurance is required.", "score": 0.91}
        ]


def test_ask_rfp_extracts_precise_deadline_answer():
    response = client.post(
        "/ask-rfp",
        json={
            "rfp_text": (
                "The contractor shall provide help desk services.\n\n"
                "All proposals must be received no later than 4:00 PM local time on August 15, 2026."
            ),
            "question": "What is the submission deadline?",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "August 15, 2026" in data["answer"]
    assert data["source_excerpt"]
    assert data["confidence"] == "high"


def test_ask_rfp_falls_back_to_source_excerpt_for_general_question():
    response = client.post(
        "/ask-rfp",
        json={
            "rfp_text": "Proposals will be evaluated on technical approach, past performance, and price.",
            "question": "What are the evaluation criteria?",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "technical approach" in data["answer"].lower()
    assert data["confidence"] == "low"


def test_extract_requirements_returns_structured_checklist():
    response = client.post(
        "/extract-requirements",
        json={
            "rfp_text": (
                "The vendor must provide proof of general liability insurance of at least $1,000,000. "
                "Offerors shall include three client references with the proposal. "
                "A transition plan should be included when available."
            )
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["requirement_count"] == 3
    assert data["requirements"][0]["mandatory"] is True
    assert data["requirements"][2]["mandatory"] is False


def test_extract_requirements_returns_empty_list_when_none_found():
    response = client.post("/extract-requirements", json={"rfp_text": "This document describes background only."})
    assert response.status_code == 200
    assert response.json() == {"requirements": [], "requirement_count": 0}


def test_resolve_amendments_applies_modified_and_struck_sections():
    response = client.post(
        "/resolve-amendments",
        json={
            "original_text": (
                "4.2 Insurance Requirements\n"
                "Contractor shall maintain minimum $1,000,000 general liability coverage.\n\n"
                "7.1 On-site Support\n"
                "Contractor shall provide on-site support."
            ),
            "amendments": [
                {
                    "amendment_number": 1,
                    "date": "2026-06-02",
                    "text": "Amendment 1: Section 4.2 (Insurance Requirements) is revised to read: 'Contractor shall maintain minimum $2,000,000 general liability coverage.'",
                },
                {
                    "amendment_number": 2,
                    "date": "2026-06-10",
                    "text": "Amendment 2: Section 7.1 (On-site Support) is struck in its entirety.",
                },
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    sections = {item["section"]: item for item in data["effective_sections"]}
    assert sections["4.2"]["status"] == "modified"
    assert "$2,000,000" in sections["4.2"]["text"]
    assert sections["7.1"]["status"] == "struck"
    assert sections["7.1"]["text"] is None
    assert len(data["changelog"]) == 2


def test_reconstruct_outline_builds_tree_and_warns_about_skipped_number():
    response = client.post(
        "/reconstruct-outline",
        json={
            "document_text": (
                "1. Introduction\n"
                "Some intro text.\n"
                "1.1 Purpose\n"
                "Text here.\n"
                "2. Scope of Work\n"
                "2.1 Deliverables\n"
                "2.1.1 Phase One\n"
                "Text.\n"
                "2.1.3 Phase Three\n"
                "Text."
            )
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["outline"][0]["children"][0]["number"] == "1.1"
    assert data["outline"][1]["children"][0]["children"][1]["number"] == "2.1.3"
    assert data["warnings"][0]["type"] == "skipped_number"


def test_reconstruct_outline_without_headings_returns_empty_outline():
    response = client.post("/reconstruct-outline", json={"document_text": "No numbered headings here."})
    assert response.status_code == 200
    assert response.json() == {"outline": [], "warnings": []}


def test_build_compliance_matrix_scores_mandatory_requirements():
    response = client.post(
        "/build-compliance-matrix",
        json={
            "requirements": [
                {
                    "id": "req-1",
                    "text": "Vendor must provide 24/7 technical support with a maximum 1-hour response time.",
                    "mandatory": True,
                },
                {
                    "id": "req-2",
                    "text": "Vendor should offer optional on-site training for staff.",
                    "mandatory": False,
                },
            ],
            "proposal_text": "Our support desk operates around the clock, every day of the year, and guarantees a response within 45 minutes.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matrix"][0]["status"] == "met"
    assert data["mandatory_requirements_met"] == 1
    assert data["mandatory_requirements_total"] == 1
    assert data["overall_flag"] == "passes_mandatory_requirements"


def test_build_compliance_matrix_handles_no_mandatory_requirements():
    response = client.post(
        "/build-compliance-matrix",
        json={
            "requirements": [{"id": "req-1", "text": "Vendor should offer optional training.", "mandatory": False}],
            "proposal_text": "",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mandatory_requirements_total"] == 0
    assert data["overall_flag"] == "no_mandatory_requirements"


def test_ocr_pdf_uses_mistral_key_and_returns_page_text(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"pages": [{"markdown": "Page one text."}, {"markdown": "Page two text."}]}).encode()

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://api.mistral.ai/v1/ocr"
        assert request.get_header("Authorization") == "Bearer test-mistral-key"
        assert timeout == 90
        body = json.loads(request.data)
        assert body["model"] == "mistral-ocr-latest"
        assert body["document"]["type"] == "document_url"
        assert body["document"]["document_url"].startswith("data:application/pdf;base64,")
        return FakeResponse()

    with patch("urllib.request.urlopen", fake_urlopen):
        response = client.post("/ocr-pdf", json={"filename": "rfp.pdf", "content_base64": "JVBERi0x"})

    assert response.status_code == 200
    assert response.json() == {"filename": "rfp.pdf", "text": "Page one text.\n\nPage two text.", "page_count": 2}


def test_ocr_pdf_reports_missing_mistral_key(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "")
    response = client.post("/ocr-pdf", json={"filename": "rfp.pdf", "content_base64": "JVBERi0x"})
    assert response.status_code == 502
    assert "Mistral API key is not configured" in response.json()["detail"]


def test_joint_summary_combines_documents_in_local_mode():
    response = client.post(
        "/joint-summary",
        json={
            "documents": [
                {
                    "name": "Original RFP",
                    "text": "The vendor must submit proposals by August 15, 2026. Insurance of $1,000,000 is required.",
                },
                {
                    "name": "Amendment 1",
                    "text": "Amendment 1 revised the due date to July 15, 2026 and requires insurance of $2,000,000.",
                },
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_count"] == 2
    assert "read together" in data["summary"]
    assert data["key_points"]
    assert any("July 15, 2026" in item for item in data["differences"])


def test_joint_summary_uses_openrouter_when_configured(monkeypatch):
    monkeypatch.delenv("GLOSSARY_MODE", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            content = json.dumps(
                {
                    "summary": "The original RFP and amendment should be read together.",
                    "key_points": ["The vendor must submit a proposal."],
                    "differences": ["The amendment changes the deadline."],
                }
            )
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
        assert request.get_header("Authorization") == "Bearer test-openrouter-key"
        body = json.loads(request.data)
        assert "Create a joint summary" in body["messages"][0]["content"]
        assert "Original RFP" in body["messages"][1]["content"]
        return FakeResponse()

    with patch("urllib.request.urlopen", fake_urlopen):
        response = client.post(
            "/joint-summary",
            json={
                "documents": [
                    {"name": "Original RFP", "text": "The vendor must submit by August 15, 2026."},
                    {"name": "Amendment", "text": "The due date is revised to July 15, 2026."},
                ]
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "The original RFP and amendment should be read together."
    assert data["document_count"] == 2
