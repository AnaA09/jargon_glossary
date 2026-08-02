"""RFP text-intelligence helpers for sectioning, search, answers, and requirements."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv


SEGMENT_SYSTEM_PROMPT = """You are an expert at reading United States government procurement documents.
Split the supplied RFP text into logical labeled sections.

Return ONLY a JSON object in this exact shape:
{"sections":[{"heading":"CANONICAL SECTION NAME","start_line":1,"text":"Section body text."}]}

Rules:
- Detect real section headings such as "SECTION 4: EVALUATION CRITERIA", "4. Submission Requirements", "Scope of Work", or "Article IV — Timeline".
- Everything after a heading belongs to that section until the next heading.
- Normalize common variants: "Statement of Work" and "Project Description" should become "SCOPE OF WORK"; "Submission Instructions" should become "SUBMISSION REQUIREMENTS".
- If there are no headings, return one section with heading "DOCUMENT", start_line 1, and the full text.
- Do not invent content. Section text must come from the document.
- Do not add markdown or text outside the JSON object.
"""


SEARCH_SYSTEM_PROMPT = """You are an expert at finding relevant clauses in United States government procurement documents.
Given RFP text and a user's plain-English question, return the passages that best answer or relate to the question.

Return ONLY a JSON object in this exact shape:
{"matches":[{"text":"Relevant passage copied from the RFP.","score":0.87}]}

Rules:
- Return the top matching passages, sorted from most relevant to least relevant.
- Copy passage text from the RFP. Do not invent facts, rewrite clauses, or answer from outside knowledge.
- Scores must be numbers from 0 to 1, where higher means more relevant.
- If nothing is a strong match, still return the best available low-score passages.
- Keep each match concise, ideally one paragraph or a few closely related sentences.
- Do not add markdown or text outside the JSON object.
"""


SECTION_VARIANTS = {
    "SCOPE OF WORK": {
        "scope",
        "scope of work",
        "statement of work",
        "project description",
        "work statement",
        "services required",
    },
    "EVALUATION CRITERIA": {
        "evaluation",
        "evaluation criteria",
        "basis for award",
        "proposal evaluation",
        "selection criteria",
        "award criteria",
    },
    "SUBMISSION REQUIREMENTS": {
        "submission",
        "submission requirements",
        "proposal submission",
        "submission instructions",
        "instructions to offerors",
        "proposal requirements",
    },
    "TIMELINE": {
        "timeline",
        "schedule",
        "period of performance",
        "important dates",
        "key dates",
    },
    "BACKGROUND": {
        "background",
        "overview",
        "introduction",
        "purpose",
    },
    "TERMS AND CONDITIONS": {
        "terms and conditions",
        "contract terms",
        "general terms",
        "special conditions",
    },
}


def _strip_heading_prefix(line: str) -> str:
    cleaned = line.strip().strip(":-–—")
    cleaned = re.sub(
        r"^(?:section|part|article|attachment|appendix)\s+[A-Z0-9IVXLC]+(?:\s*[-:–—.]\s*)?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^\d+(?:\.\d+)*[\).:-]?\s*", "", cleaned)
    cleaned = re.sub(r"^[IVXLC]+[\).:-]\s+", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" :-–—")


def _normalize_heading(line: str) -> str:
    cleaned = _strip_heading_prefix(line)
    key = cleaned.casefold()
    for canonical, variants in SECTION_VARIANTS.items():
        if key in variants:
            return canonical
    return cleaned.upper() if cleaned.isupper() else cleaned


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) > 90:
        return False
    if stripped.endswith((".", "?", "!")):
        return False

    cleaned = _strip_heading_prefix(stripped)
    if not cleaned or len(cleaned) > 70:
        return False

    words = re.findall(r"[A-Za-z0-9&/-]+", cleaned)
    if not words or len(words) > 9:
        return False

    has_section_prefix = bool(
        re.match(
            r"^(?:section|part|article|attachment|appendix)\s+[A-Z0-9IVXLC]+|\d+(?:\.\d+)*[\).:-]",
            stripped,
            flags=re.IGNORECASE,
        )
    )
    is_all_caps = cleaned.upper() == cleaned and any(char.isalpha() for char in cleaned)
    is_title_case = sum(word[:1].isupper() for word in words if word[:1].isalpha()) >= max(1, len(words) - 1)
    is_known_variant = cleaned.casefold() in {variant for variants in SECTION_VARIANTS.values() for variant in variants}

    # A heading usually has a section prefix, a known RFP heading phrase, or compact heading-style casing.
    return has_section_prefix or is_known_variant or is_all_caps or (is_title_case and len(words) <= 6)


def segment_rfp_text(text: str) -> list[dict[str, Any]]:
    """Split an RFP into sections using heading-like line patterns."""
    if not text.strip():
        return []

    lines = text.splitlines()
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines, start=1):
        if _looks_like_heading(line):
            headings.append((index, _normalize_heading(line)))

    if not headings:
        return [{"heading": "DOCUMENT", "start_line": 1, "text": text.strip()}]

    sections: list[dict[str, Any]] = []
    for position, (line_number, heading) in enumerate(headings):
        next_line = headings[position + 1][0] if position + 1 < len(headings) else len(lines) + 1
        body_lines = lines[line_number: next_line - 1]
        body = "\n".join(body_lines).strip()
        sections.append({"heading": heading, "start_line": line_number, "text": body})
    return sections


def _dedupe_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    for item in sections:
        heading = re.sub(r"\s+", " ", str(item.get("heading", "")).strip()) or "DOCUMENT"
        try:
            start_line = int(item.get("start_line", 1))
        except (TypeError, ValueError):
            start_line = 1
        body = str(item.get("text", "")).strip()
        clean.append({"heading": heading, "start_line": max(1, start_line), "text": body})
    return clean


def chunk_rfp_text(text: str) -> list[str]:
    """Split text into paragraph-sized chunks, with sentence fallback for long paragraphs."""
    clean = re.sub(r"\r\n?", "\n", text).strip()
    if not clean:
        return []

    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n+", clean)]
    chunks: list[str] = []
    for paragraph in paragraphs:
        if not paragraph:
            continue
        if len(paragraph) <= 700:
            chunks.append(paragraph)
            continue
        sentences = re.findall(r"[^.!?]+[.!?]?", paragraph)
        buffer = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if buffer and len(buffer) + len(sentence) > 700:
                chunks.append(buffer.strip())
                buffer = sentence
            else:
                buffer = f"{buffer} {sentence}".strip()
        if buffer:
            chunks.append(buffer.strip())
    return chunks


@lru_cache(maxsize=1)
def _embedding_model() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2]


def _lexical_similarity(query: str, chunks: list[str]) -> list[float]:
    query_counts = Counter(_tokenize(query))
    scores: list[float] = []
    for chunk in chunks:
        chunk_counts = Counter(_tokenize(chunk))
        vocabulary = sorted(set(query_counts) | set(chunk_counts))
        scores.append(
            _cosine(
                [float(query_counts.get(token, 0)) for token in vocabulary],
                [float(chunk_counts.get(token, 0)) for token in vocabulary],
            )
        )
    return scores


def search_rfp_clauses(text: str, query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Return the most relevant chunks for a query, using embeddings when available."""
    chunks = chunk_rfp_text(text)
    clean_query = query.strip()
    if not chunks or not clean_query:
        return []

    requested = max(1, min(top_k, 10))
    try:
        model = _embedding_model()
        embeddings = model.encode([clean_query, *chunks], normalize_embeddings=True)
        query_embedding = embeddings[0]
        scores = [float(query_embedding @ chunk_embedding) for chunk_embedding in embeddings[1:]]
    except Exception:
        scores = _lexical_similarity(clean_query, chunks)

    ranked = sorted(zip(chunks, scores), key=lambda item: item[1], reverse=True)
    return [{"text": chunk, "score": round(score, 4)} for chunk, score in ranked[:requested]]


def _clean_matches(matches: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    for item in matches:
        text = re.sub(r"\s+", " ", str(item.get("text", "")).strip())
        if not text:
            continue
        try:
            score = float(item.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        clean.append({"text": text, "score": round(max(0.0, min(1.0, score)), 4)})
    return clean[: max(1, min(top_k, 10))]


def _openrouter_json(system_prompt: str, user_content: str, max_tokens: int = 3000) -> dict[str, Any]:
    model = os.getenv("OPENROUTER_MODEL", "openrouter/auto").strip() or "openrouter/auto"
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OpenRouter API key is not configured.")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.05,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:8000"),
            "X-OpenRouter-Title": "jargon_glossary",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
        raw = body["choices"][0]["message"]["content"]
        return json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        if isinstance(exc, urllib.error.HTTPError) and exc.code == 401:
            raise RuntimeError("OpenRouter rejected the API key. Check OPENROUTER_API_KEY in .env.") from exc
        if isinstance(exc, urllib.error.HTTPError) and exc.code == 402:
            raise RuntimeError("The OpenRouter account has insufficient credits for this request.") from exc
        if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
            raise RuntimeError("OpenRouter is rate-limiting requests. Please try again shortly.") from exc
        raise RuntimeError("OpenRouter could not be reached. Please try again.") from exc
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("OpenRouter returned a response in an unexpected format.") from exc


def _openrouter_segment_rfp(text: str) -> list[dict[str, Any]]:
    parsed = _openrouter_json(SEGMENT_SYSTEM_PROMPT, text, max_tokens=3500)
    return _dedupe_sections(parsed.get("sections", []))


def _openrouter_search_clauses(text: str, query: str, top_k: int) -> list[dict[str, Any]]:
    requested = max(1, min(top_k, 10))
    user_content = json.dumps({"rfp_text": text, "query": query, "top_k": requested})
    parsed = _openrouter_json(SEARCH_SYSTEM_PROMPT, user_content, max_tokens=2500)
    return _clean_matches(parsed.get("matches", []), requested)


async def analyze_rfp_sections(text: str) -> tuple[list[dict[str, Any]], str]:
    """Return RFP sections using OpenRouter when configured, otherwise local rules."""
    if not text.strip():
        return [], "local"
    load_dotenv(override=True)
    if os.getenv("GLOSSARY_MODE", "").strip().lower() == "local":
        return segment_rfp_text(text), "local"
    if os.getenv("OPENROUTER_API_KEY", "").strip():
        sections = await asyncio.to_thread(_openrouter_segment_rfp, text)
        return sections or segment_rfp_text(text), "openrouter"
    return segment_rfp_text(text), "local"


async def analyze_clause_search(text: str, query: str, top_k: int = 3) -> tuple[list[dict[str, Any]], str]:
    """Return relevant RFP clauses using OpenRouter when configured, otherwise local similarity."""
    if not text.strip() or not query.strip():
        return [], "local"
    load_dotenv(override=True)
    if os.getenv("GLOSSARY_MODE", "").strip().lower() == "local":
        return search_rfp_clauses(text, query, top_k), "local"
    if os.getenv("OPENROUTER_API_KEY", "").strip():
        matches = await asyncio.to_thread(_openrouter_search_clauses, text, query, top_k)
        return matches or search_rfp_clauses(text, query, top_k), "openrouter"
    return search_rfp_clauses(text, query, top_k), "local"


def _classify_question(question: str) -> str:
    clean = question.lower()
    if any(word in clean for word in ("when", "deadline", "due", "date", "time")):
        return "date"
    if any(word in clean for word in ("how much", "cost", "price", "dollar", "amount", "fee", "budget")):
        return "money"
    if clean.startswith(("is ", "are ", "does ", "do ", "can ", "will ", "must ", "should ")):
        return "yes_no"
    return "general"


def _extract_precise_answer(chunk: str, question_type: str) -> tuple[str, str]:
    clean_chunk = re.sub(r"\s+", " ", chunk).strip()
    if not clean_chunk:
        return "", "low"

    if question_type == "date":
        date_patterns = [
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}(?:,?\s+(?:at|by|no later than)?\s*\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?(?:\s+local time)?)?",
            r"\b\d{1,2}/\d{1,2}/\d{2,4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)?",
            r"\b\d{4}-\d{2}-\d{2}(?:\s+\d{1,2}:\d{2})?",
            r"\b(?:no later than|by|before)\s+\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)(?:\s+local time)?",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, clean_chunk, flags=re.IGNORECASE)
            if match:
                return match.group(0).strip(" ,."), "high"

    if question_type == "money":
        money_match = re.search(
            r"\$\s?\d[\d,]*(?:\.\d{2})?|\b\d+(?:\.\d+)?\s*(?:percent|%)\b",
            clean_chunk,
            flags=re.IGNORECASE,
        )
        if money_match:
            return money_match.group(0).strip(), "high"

    if question_type == "yes_no":
        lower = clean_chunk.lower()
        if any(word in lower for word in ("must", "shall", "required", "will", "is required", "are required")):
            return f"Yes. {clean_chunk}", "medium"
        if any(word in lower for word in ("not required", "optional", "may", "should", "preferred")):
            return f"Not strictly required. {clean_chunk}", "medium"

    sentence_match = re.search(r"[^.!?]+[.!?]?", clean_chunk)
    return (sentence_match.group(0).strip() if sentence_match else clean_chunk, "low")


async def answer_rfp_question(text: str, question: str) -> dict[str, str]:
    """Use clause search plus rules to extract a precise answer to an RFP question."""
    if not text.strip() or not question.strip():
        return {"answer": "", "source_excerpt": "", "confidence": "low"}

    matches, _mode = await analyze_clause_search(text, question, top_k=1)
    source_excerpt = matches[0]["text"] if matches else ""
    question_type = _classify_question(question)
    answer, confidence = _extract_precise_answer(source_excerpt, question_type)
    if confidence == "low" and question_type in {"date", "money"}:
        for chunk in chunk_rfp_text(text):
            fallback_answer, fallback_confidence = _extract_precise_answer(chunk, question_type)
            if fallback_confidence == "high":
                answer = fallback_answer
                source_excerpt = chunk
                confidence = fallback_confidence
                break
    return {
        "answer": answer or source_excerpt,
        "source_excerpt": source_excerpt,
        "confidence": confidence if answer else "low",
    }


REQUIREMENT_NOUNS = (
    "bond",
    "certificate",
    "insurance",
    "reference",
    "references",
    "license",
    "licenses",
    "plan",
    "resume",
    "resumes",
    "report",
    "reports",
    "documentation",
    "document",
    "documents",
    "proposal",
    "pricing",
    "quote",
    "form",
    "forms",
    "certification",
    "certifications",
    "past performance",
)

OBLIGATION_VERBS = (
    "submit",
    "provide",
    "include",
    "attach",
    "deliver",
    "furnish",
    "carry",
    "maintain",
    "certify",
)

MANDATORY_WORDS = ("shall", "must", "required", "requires", "requirement", "mandatory", "will")
OPTIONAL_WORDS = ("may", "should", "encouraged", "preferred", "optional", "recommended")


def _split_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.findall(r"[^.!?]+[.!?]?", re.sub(r"\s+", " ", text)) if sentence.strip()]


def _is_requirement_sentence(sentence: str) -> bool:
    lower = sentence.lower()
    has_noun = any(noun in lower for noun in REQUIREMENT_NOUNS)
    has_obligation = any(verb in lower for verb in OBLIGATION_VERBS) or any(word in lower for word in MANDATORY_WORDS + OPTIONAL_WORDS)
    return has_noun and has_obligation


def _is_mandatory(sentence: str) -> bool:
    lower = sentence.lower()
    mandatory_positions = [lower.find(word) for word in MANDATORY_WORDS if word in lower]
    optional_positions = [lower.find(word) for word in OPTIONAL_WORDS if word in lower]
    if mandatory_positions and optional_positions:
        # Mixed signals are treated by the first signal in the sentence.
        return min(position for position in mandatory_positions if position >= 0) < min(
            position for position in optional_positions if position >= 0
        )
    if mandatory_positions:
        return True
    return False


def _requirement_item(sentence: str) -> str:
    lower = sentence.lower()
    if "proposal" in lower and any(word in lower for word in ("received", "submitted", "submit")):
        return "Proposal submission"
    patterns = [
        r"(?:submit|provide|include|attach|deliver|furnish|carry|maintain)\s+(?:all\s+required\s+|a\s+|an\s+|the\s+)?([^.;:]+)",
        r"((?:bid\s+)?bond|certificate of insurance|insurance certificate|general liability insurance|client references?|licenses?|plans?|reports?|documentation|forms?|certifications?|past performance)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lower, flags=re.IGNORECASE)
        if match:
            item = match.group(1).strip()
            item = re.split(r"\s+(?:by|before|with|and all|and the|, and)\b", item, maxsplit=1)[0].strip(" ,.")
            return item[:1].upper() + item[1:]
    return sentence[:70].rstrip(" .,")


def extract_requirement_checklist(text: str) -> list[dict[str, Any]]:
    """Extract vendor submission requirements as a validated checklist-shaped list."""
    requirements: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sentence in _split_sentences(text):
        if not _is_requirement_sentence(sentence):
            continue
        item = _requirement_item(sentence)
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        requirements.append(
            {
                "item": item,
                "mandatory": _is_mandatory(sentence),
                "detail": sentence.strip(),
            }
        )
    return requirements
