import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai_extract import _openrouter_request
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
