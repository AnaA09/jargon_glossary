"""Glossary extraction through OpenRouter, with a useful local fallback."""

from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from dotenv import load_dotenv


SYSTEM_PROMPT = """You are an expert in United States government procurement documents.
Read the document and create two outputs:
1. A short, plain-English summary of what the RFP text is asking for.
2. A glossary of every acronym, abbreviation, and specialized technical or procurement
   term a general reader may not understand. For each term, write a concise,
   plain-English definition that is accurate in this context.

Return ONLY a JSON object in this exact shape:
{"summary": "Plain-English summary.", "terms": [{"term": "ACRONYM", "definition": "Plain-English explanation."}]}

Rules:
- Keep the summary easy to understand, direct, and under 120 words.
- In the summary, explain the purpose, work requested, important requirements, and deadlines only if the document says them.
- Include terms only when they actually appear in the document.
- Do not include duplicate terms, even with different capitalization.
- Do not include ordinary words such as "contract", "document", "the", or "and".
- Keep each definition to one or two short sentences.
- If the text contains no jargon, return an empty terms list.
- Do not add markdown or any text outside the JSON object.
"""


# Keeps the project usable before an API key is configured and makes the sample deterministic.
LOCAL_GLOSSARY = {
    "COTR": "Contracting Officer's Technical Representative. The government employee who monitors a contractor's day-to-day technical work.",
    "PWS": "Performance Work Statement. A document that describes the work outcomes and standards a contractor must meet.",
    "TPOC": "Technical Point of Contact. The person designated to answer technical questions and coordinate technical work.",
    "FAR": "Federal Acquisition Regulation. The primary set of rules governing how U.S. federal agencies buy goods and services.",
    "DFARS": "Defense Federal Acquisition Regulation Supplement. Extra acquisition rules used by the U.S. Department of Defense.",
    "CPARS": "Contractor Performance Assessment Reporting System. The federal system used to record and review a contractor's performance.",
    "RFP": "Request for Proposals. A formal government invitation asking vendors to submit solutions and prices for a requirement.",
    "RFQ": "Request for Quotation. A request asking vendors to provide pricing for clearly defined goods or services.",
    "SOW": "Statement of Work. A description of the tasks, deliverables, and responsibilities required under a contract.",
    "IDIQ": "Indefinite Delivery, Indefinite Quantity. A contract with flexible timing and quantities, fulfilled through later orders.",
    "NAICS": "North American Industry Classification System. Codes agencies use to classify a procurement by industry.",
    "CLIN": "Contract Line Item Number. A numbered contract entry identifying a specific product, service, quantity, or price.",
    "CO": "Contracting Officer. The government official authorized to enter into, administer, or terminate a contract.",
    "COR": "Contracting Officer's Representative. A person appointed to monitor technical performance on the contracting officer's behalf.",
    "SBA": "Small Business Administration. The U.S. agency that supports small businesses and administers contracting programs.",
    "RFI": "Request for Information. A notice used to gather market information before an agency decides how to buy something.",
    "SAM": "System for Award Management. The federal website where organizations register to do business with the U.S. government.",
    "UEI": "Unique Entity Identifier. The official identifier assigned to an organization registered in SAM.gov.",
    "DUNS": "Data Universal Numbering System. A former business identifier that the federal government replaced with the UEI.",
    "GSA": "General Services Administration. The federal agency that manages shared government purchasing, property, and services.",
    "GAO": "Government Accountability Office. An independent congressional agency that audits federal spending and decides many bid protests.",
    "FTE": "Full-Time Equivalent. A unit representing the workload of one full-time worker.",
    "LOE": "Level of Effort. The amount of labor or time expected for a task or contract.",
    "QASP": "Quality Assurance Surveillance Plan. The government's plan for monitoring whether a contractor meets performance standards.",
    "OCI": "Organizational Conflict of Interest. A situation where other business relationships could impair a contractor's objectivity or create an unfair advantage.",
    "NDAA": "National Defense Authorization Act. An annual law that authorizes U.S. defense programs and often includes acquisition requirements.",
    "NIST": "National Institute of Standards and Technology. The federal agency that publishes widely used technical and cybersecurity standards.",
    "CMMC": "Cybersecurity Maturity Model Certification. A Department of Defense program for assessing contractors' protection of sensitive information.",
    "CUI": "Controlled Unclassified Information. Government information that is not classified but still requires safeguarding.",
    "ITAR": "International Traffic in Arms Regulations. U.S. rules controlling the export of defense-related articles, services, and technical data.",
    "FOCI": "Foreign Ownership, Control, or Influence. A condition evaluated when a company with foreign ties needs access to classified information.",
    "BPA": "Blanket Purchase Agreement. A simplified arrangement used for repeated purchases from approved suppliers.",
    "GWAC": "Governmentwide Acquisition Contract. A contract multiple federal agencies can use to buy information technology services or products.",
    "FFP": "Firm-Fixed-Price. A contract type in which the agreed price generally does not change based on the contractor's actual costs.",
    "CPFF": "Cost-Plus-Fixed-Fee. A contract type that reimburses allowable costs and pays an agreed fixed fee.",
    "LPTA": "Lowest Price Technically Acceptable. A selection method that chooses the lowest-priced offer meeting all minimum technical requirements.",
    "PII": "Personally Identifiable Information. Information that can identify a specific person and must be appropriately protected.",
    "FOIA": "Freedom of Information Act. A law allowing the public to request records from federal agencies, subject to exemptions.",
    "SLA": "Service-Level Agreement. A documented commitment defining expected service performance, such as uptime or response time.",
    "KPI": "Key Performance Indicator. A measurable value used to track whether a program or contractor is meeting an important objective.",
    "SOP": "Standard Operating Procedure. Written step-by-step instructions for performing a routine activity consistently.",
    "POP": "Period of Performance. The date range during which contract work must be completed.",
    "BOE": "Basis of Estimate. The assumptions, methods, and supporting information used to develop a cost or staffing estimate.",
    "WBS": "Work Breakdown Structure. A hierarchy that divides a project into smaller, manageable pieces of work.",
    "CDRL": "Contract Data Requirements List. A form identifying the data items a defense contractor must deliver and when they are due.",
    "DD": "Department of Defense form designation. In a form number such as DD 254, it identifies an official Defense Department form.",
    "ACO": "Administrative Contracting Officer. The government official responsible for administering a contract after it is awarded.",
    "BAA": "Broad Agency Announcement. A notice inviting proposals for research and development in broadly defined areas of interest.",
    "CAGE": "Commercial and Government Entity code. A five-character identifier assigned to organizations that do business with the federal government.",
    "CAS": "Cost Accounting Standards. Rules designed to make certain government contractors' cost accounting practices consistent and transparent.",
    "CFR": "Code of Federal Regulations. The organized collection of permanent rules issued by U.S. federal agencies.",
    "CONUS": "Continental United States. The 48 adjoining states and Washington, D.C., excluding Alaska, Hawaii, and U.S. territories.",
    "OCONUS": "Outside the Continental United States. Locations outside the 48 adjoining states and Washington, D.C.",
    "DCAA": "Defense Contract Audit Agency. The Department of Defense agency that audits contractor costs and financial systems.",
    "DCMA": "Defense Contract Management Agency. The Department of Defense agency that administers many defense contracts and monitors contractor performance.",
    "DHS": "Department of Homeland Security. The federal department responsible for public security, including cybersecurity, border security, and disaster response.",
    "DOC": "Department of Commerce. The federal department that supports economic growth, trade, technology, and business data.",
    "DOE": "Department of Energy. The federal department responsible for energy policy, nuclear security, and related research.",
    "DOJ": "Department of Justice. The federal department responsible for enforcing federal law and administering justice.",
    "DOL": "Department of Labor. The federal department responsible for worker protections, employment programs, and labor statistics.",
    "EPA": "Environmental Protection Agency. The federal agency that develops and enforces environmental regulations.",
    "FAA": "Federal Aviation Administration. The federal agency that regulates civil aviation in the United States.",
    "FEMA": "Federal Emergency Management Agency. The federal agency that coordinates disaster preparedness, response, and recovery.",
    "FSS": "Federal Supply Schedule. A GSA contracting program offering government buyers pre-negotiated products and services.",
    "HUBZONE": "Historically Underutilized Business Zone. An SBA program that helps eligible businesses in designated areas compete for federal contracts.",
    "MOU": "Memorandum of Understanding. A document recording an agreement or shared understanding between organizations.",
    "MOA": "Memorandum of Agreement. A document describing agreed responsibilities and terms between organizations.",
    "OMB": "Office of Management and Budget. The White House office that oversees federal budgets, management, and agency policy implementation.",
    "OSHA": "Occupational Safety and Health Administration. The federal agency that sets and enforces workplace safety standards.",
    "OTA": "Other Transaction Authority. Legal authority allowing certain agencies to use flexible agreements outside standard procurement contracts or grants.",
    "PBA": "Performance-Based Acquisition. A purchasing approach that describes required results and performance standards rather than prescribing how work must be done.",
    "POC": "Point of Contact. The person designated to answer questions or coordinate communication about a specific matter.",
    "PSC": "Product and Service Code. A federal code that categorizes the product or service being purchased.",
    "QPL": "Qualified Products List. A list of products that have been examined and found to meet specified requirements.",
    "SDVOSB": "Service-Disabled Veteran-Owned Small Business. A small business owned and controlled by one or more service-disabled veterans.",
    "TAA": "Trade Agreements Act. A law that can limit federal purchases to products made in the United States or designated countries.",
    "TIN": "Taxpayer Identification Number. An identifier used by the Internal Revenue Service to administer tax laws.",
    "T&M": "Time and Materials. A contract type that pays for labor at fixed hourly rates plus the actual cost of approved materials.",
    "VA": "Department of Veterans Affairs. The federal department that provides benefits and services to veterans.",
    "VOSB": "Veteran-Owned Small Business. A small business owned and controlled by one or more veterans.",
    "WOSB": "Women-Owned Small Business. An SBA contracting-program designation for qualifying businesses owned and controlled by women.",
    "WAWF": "Wide Area Workflow. A Department of Defense system used to submit and process invoices and receiving reports, now part of Procurement Integrated Enterprise Environment.",
    "API": "Application Programming Interface. A defined way for software systems to exchange data or request functions from one another.",
    "ATO": "Authorization to Operate. Formal approval allowing an information system to operate after its security risks have been assessed and accepted.",
    "CAC": "Common Access Card. The standard identification card used by active-duty military personnel, many civilian employees, and eligible contractors.",
    "FISMA": "Federal Information Security Modernization Act. The law establishing federal requirements for information-security programs and oversight.",
    "FEDRAMP": "Federal Risk and Authorization Management Program. A governmentwide program that standardizes security assessment and authorization for cloud services.",
    "IAAS": "Infrastructure as a Service. Cloud computing that provides virtualized servers, storage, and networking on demand.",
    "MFA": "Multi-Factor Authentication. A security method requiring two or more different forms of verification to sign in.",
    "PAAS": "Platform as a Service. Cloud computing that provides a managed platform for developing and running applications.",
    "PIV": "Personal Identity Verification. A federal standard and credential for securely verifying the identity of employees and contractors.",
    "PKI": "Public Key Infrastructure. Technology and policies that use digital certificates and cryptographic keys to secure identities and communications.",
    "RMF": "Risk Management Framework. NIST's structured process for managing security and privacy risk throughout a system's life cycle.",
    "SAAS": "Software as a Service. Software hosted by a provider and accessed over a network, usually through a subscription.",
    "SIEM": "Security Information and Event Management. Technology that collects and analyzes security logs to detect and investigate threats.",
    "SOC": "Security Operations Center. A team or facility that continuously monitors and responds to cybersecurity threats.",
    "SSO": "Single Sign-On. An authentication method that lets a user access multiple systems after signing in once.",
}


# Uppercase words that are normally formatting, locations, file types, or ordinary
# shorthand rather than procurement jargon. Everything else acronym-shaped is kept.
ACRONYM_EXCLUSIONS = {
    "AM", "PM", "US", "USA", "PDF", "DOC", "DOCX", "HTML", "HTTP", "HTTPS",
    "WWW", "EMAIL", "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN",
    "JAN", "FEB", "MAR", "APR", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
}


def _dedupe(terms: list[dict[str, Any]]) -> list[dict[str, str]]:
    clean: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in terms:
        term = str(item.get("term", "")).strip()
        definition = str(item.get("definition", "")).strip()
        key = term.casefold()
        if term and definition and key not in seen:
            seen.add(key)
            clean.append({"term": term, "definition": definition})
    return clean


def _clean_summary(summary: Any) -> str:
    clean = re.sub(r"\s+", " ", str(summary or "")).strip()
    return clean


def _local_summary(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return ""

    sentences = re.findall(r"[^.!?]+[.!?]?", clean)
    sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
    if not sentences:
        sentences = [clean]

    priority_words = (
        "shall",
        "must",
        "require",
        "requires",
        "seeking",
        "request",
        "proposal",
        "deliverable",
        "deadline",
        "performance",
        "submit",
        "provide",
    )
    chosen: list[str] = []
    for sentence in sentences:
        lower = sentence.lower()
        if any(word in lower for word in priority_words):
            chosen.append(sentence)
        if len(chosen) == 3:
            break
    if not chosen:
        chosen = sentences[:3]

    summary = " ".join(chosen)
    if len(summary) > 650:
        summary = summary[:647].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    return (
        "In plain English: this document describes a procurement request and the main "
        f"requirements the vendor needs to follow. Key text: {summary}"
    )


def _document_expansion(text: str, acronym: str) -> str | None:
    """Find definitions written as 'Full Term (ABC)' or 'ABC (Full Term)'."""
    escaped = re.escape(acronym)
    before = re.search(
        rf"([A-Z][A-Za-z0-9'/-]*(?:\s+(?:of|and|for|the|to|in|on|or|[A-Z][A-Za-z0-9'/-]*)){{1,9}})\s*\(\s*{escaped}\s*\)",
        text,
    )
    if before:
        expansion = before.group(1).strip()
        return f"{expansion}. This expansion is provided in the document."

    after = re.search(rf"(?<![A-Za-z0-9]){escaped}\s*\(\s*([^()\n]{{3,100}})\s*\)", text)
    if after:
        expansion = after.group(1).strip().rstrip(".")
        if any(character.islower() for character in expansion):
            return f"{expansion}. This expansion is provided in the document."
    return None


def _contextual_definition(text: str, acronym: str) -> str:
    """Explain an undefined acronym's role using its sentence without inventing a name."""
    match = re.search(rf"[^.!?\n]*\b{re.escape(acronym)}\b[^.!?\n]*[.!?]?", text)
    sentence = re.sub(r"\s+", " ", match.group(0)).strip() if match else ""
    role_match = re.search(
        rf"\b{re.escape(acronym)}\b(?:[- ](?:designated|approved))?\s+"
        r"(team|office|system|program|plan|agency|department|board|committee|unit|platform|portal|report|document|requirement)s?\b",
        sentence,
        re.IGNORECASE,
    )
    if role_match:
        role = role_match.group(1).lower()
        opening = f"A {role} referenced in this document."
    else:
        opening = "An acronym or abbreviation used in this document."
    context = f' In context: "{sentence[:240]}"' if sentence else ""
    return (
        f"{opening}{context} The supplied text does not spell out its full name, so the exact "
        "expansion cannot be stated reliably without an AI definition service."
    )


def _extract_local(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    # Match known terms case-insensitively (including forms such as FedRAMP), add
    # unfamiliar all-caps acronyms, and preserve document order.
    candidates: list[tuple[int, str]] = []
    for known_term in LOCAL_GLOSSARY:
        match = re.search(
            rf"(?<![A-Za-z0-9]){re.escape(known_term)}(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        )
        if match:
            candidates.append((match.start(), known_term))
    for match in re.finditer(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9]*(?:[&/-][A-Z0-9]+)*)\b", text):
        raw_term = match.group(1).strip("-/")
        candidates.append((match.start(), raw_term.upper()))

    for _position, term in sorted(candidates, key=lambda item: item[0]):
        if len(term) < 2 or len(term) > 15 or term in ACRONYM_EXCLUSIONS or term.isdigit():
            continue
        if not any(character.isalpha() for character in term) or term in seen:
            continue
        seen.add(term)
        definition = LOCAL_GLOSSARY.get(term) or _document_expansion(text, term)
        if definition is None:
            definition = _contextual_definition(text, term)
        found.append({"term": term, "definition": definition})
    return found


def _openrouter_request(text: str, api_key: str) -> dict[str, Any]:
    """Ask OpenRouter for a schema-shaped summary and glossary response."""
    model = os.getenv("OPENROUTER_MODEL", "openrouter/auto").strip() or "openrouter/auto"
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 4000,
    }
    request = urllib.request.Request(
        url,
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
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        if isinstance(exc, urllib.error.HTTPError) and exc.code == 401:
            raise RuntimeError("OpenRouter rejected the API key. Check OPENROUTER_API_KEY in .env.") from exc
        if isinstance(exc, urllib.error.HTTPError) and exc.code == 402:
            raise RuntimeError("The OpenRouter account has insufficient credits for this request.") from exc
        if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
            raise RuntimeError("OpenRouter is rate-limiting requests. Please try again shortly.") from exc
        raise RuntimeError("OpenRouter could not be reached. Please try again.") from exc

    try:
        raw = body["choices"][0]["message"]["content"]
        parsed = json.loads(raw)
        return {
            "summary": _clean_summary(parsed.get("summary", "")),
            "terms": _dedupe(parsed.get("terms", [])),
        }
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("OpenRouter returned a response in an unexpected format.") from exc


async def analyze_rfp(text: str) -> tuple[dict[str, Any], str]:
    """Return a plain-English summary, deduplicated terms, and the mode used."""
    if not text.strip():
        return {"summary": "", "terms": []}, "local"
    # Reload the private configuration so a newly added key works without a restart.
    load_dotenv(override=True)
    if os.getenv("GLOSSARY_MODE", "").strip().lower() == "local":
        return {"summary": _local_summary(text), "terms": _dedupe(_extract_local(text))}, "local"
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if api_key:
        result = await asyncio.to_thread(_openrouter_request, text, api_key)
        if not result["summary"]:
            result["summary"] = _local_summary(text)
        return result, "openrouter"
    return {"summary": _local_summary(text), "terms": _dedupe(_extract_local(text))}, "local"


async def extract_glossary(text: str) -> tuple[list[dict[str, str]], str]:
    """Return deduplicated terms and the extraction mode used."""
    result, mode = await analyze_rfp(text)
    return result["terms"], mode
