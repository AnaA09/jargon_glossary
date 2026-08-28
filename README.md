# jargon_glossary

A FastAPI service and ClearTerms browser interface that summarizes RFP text, finds procurement acronyms, splits RFPs into sections, searches relevant clauses, answers RFP questions, extracts vendor requirement checklists, resolves amendments, reconstructs outlines, and builds proposal compliance matrices. Duplicate glossary terms are removed automatically.

## Run locally

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000). The API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

The included local demo can summarize text, recognize common procurement terms, segment sections, search clauses, answer questions, extract requirement checklists, resolve amendments, reconstruct outlines, and build compliance matrices without an API key. To get stronger AI summaries, better section segmentation, and better clause search, add an OpenRouter API key to `.env`:

```text
OPENROUTER_API_KEY=your-key-here
OPENROUTER_MODEL=openrouter/auto
```

Day 1 and Day 2 use the same OpenRouter key when it is configured. If no key is configured, Day 1 uses local heading rules and Day 2 uses local similarity search. For true local embeddings instead of the lightweight fallback, install `sentence-transformers` once:

```bash
pip install sentence-transformers
```

If `sentence-transformers` is not installed yet, the endpoint still works with a lightweight local similarity fallback.

## Example API request

```bash
curl -X POST http://localhost:8000/extract-glossary \
  -H "Content-Type: application/json" \
  -d '{"rfp_text":"The COTR shall coordinate with the PWS-designated TPOC to ensure deliverables comply with FAR Part 15 and applicable DFARS clauses prior to CPARS submission."}'
```

The response has one stable shape:

```json
{
  "summary": "The document asks the contractor to coordinate required deliverables, follow procurement rules, and submit performance information.",
  "terms": [
    {
      "term": "COTR",
      "definition": "Contracting Officer's Technical Representative. The government employee who monitors a contractor's day-to-day technical work."
    }
  ]
}
```

Simple text with no recognized jargon returns an empty `terms` list rather than an error.

## Day 1: segment an RFP into sections

```bash
curl -X POST http://localhost:8000/segment-rfp \
  -H "Content-Type: application/json" \
  -d '{"rfp_text":"SECTION 1: SCOPE OF WORK\nThe contractor shall provide support.\n\nSECTION 2: SUBMISSION REQUIREMENTS\nProposals must be submitted by email."}'
```

Example response:

```json
{
  "section_count": 2,
  "sections": [
    {
      "heading": "SCOPE OF WORK",
      "start_line": 1,
      "text": "The contractor shall provide support."
    }
  ]
}
```

## Day 2: search for relevant clauses

```bash
curl -X POST http://localhost:8000/search-clauses \
  -H "Content-Type: application/json" \
  -d '{"rfp_text":"The contractor shall provide help desk services.\n\nThe offeror must carry general liability insurance of at least $1,000,000.","query":"what insurance is required?","top_k":3}'
```

Example response:

```json
{
  "matches": [
    {
      "text": "The offeror must carry general liability insurance of at least $1,000,000.",
      "score": 0.81
    }
  ]
}
```

## Day 3: ask a precise RFP question

```bash
curl -X POST http://localhost:8000/ask-rfp \
  -H "Content-Type: application/json" \
  -d '{"rfp_text":"All proposals must be received no later than 4:00 PM local time on August 15, 2026.","question":"What is the submission deadline?"}'
```

Example response:

```json
{
  "answer": "August 15, 2026",
  "source_excerpt": "All proposals must be received no later than 4:00 PM local time on August 15, 2026.",
  "confidence": "high"
}
```

## Day 4: extract vendor requirements

```bash
curl -X POST http://localhost:8000/extract-requirements \
  -H "Content-Type: application/json" \
  -d '{"rfp_text":"The vendor must provide proof of general liability insurance of at least $1,000,000. A transition plan should be included when available."}'
```

Example response:

```json
{
  "requirements": [
    {
      "item": "Proof of general liability insurance of at least $1,000,000",
      "mandatory": true,
      "detail": "The vendor must provide proof of general liability insurance of at least $1,000,000."
    }
  ],
  "requirement_count": 1
}
```

## Amendment resolver

Applies dated amendments to the original RFP text. Later amendments win when they touch the same section.

```bash
curl -X POST http://localhost:8000/resolve-amendments \
  -H "Content-Type: application/json" \
  -d '{"original_text":"4.2 Insurance Requirements\nContractor shall maintain minimum $1,000,000 coverage.","amendments":[{"amendment_number":1,"date":"2026-06-02","text":"Amendment 1: Section 4.2 (Insurance Requirements) is revised to read: '\''Contractor shall maintain minimum $2,000,000 coverage.'\''"}]}'
```

## Outline reconstructor

Parses numbered headings into a nested tree. It supports dotted numeric headings like `1.`, `1.1`, `1.1.2`, plus simple `a.` and `i.` subheadings. It returns heading body text so each outline node is still traceable to the source document.

```bash
curl -X POST http://localhost:8000/reconstruct-outline \
  -H "Content-Type: application/json" \
  -d '{"document_text":"1. Introduction\n1.1 Purpose\n2. Scope\n2.1 Work\n2.1.3 Phase Three"}'
```

## Compliance matrix

Compares requirement text against vendor proposal text. The local scoring uses the same chunking/search helper as clause search, then applies simple rule checks for response times, years of experience, and negative language. Similarity alone can be fooled by topically related but contradictory text, so the matrix includes confidence and notes for human review.

```bash
curl -X POST http://localhost:8000/build-compliance-matrix \
  -H "Content-Type: application/json" \
  -d '{"requirements":[{"id":"req-1","text":"Vendor must provide 24/7 technical support with a maximum 1-hour response time.","mandatory":true}],"proposal_text":"Our support desk operates around the clock and responds within 45 minutes."}'
```

## Run tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Never commit `.env`; it is excluded by `.gitignore`.

## Deploy to Vercel

Vercel uses `app.py` as the serverless FastAPI entrypoint. Import the repository in
Vercel, leave the framework and build settings on their defaults, and add
`OPENROUTER_API_KEY` plus `OPENROUTER_MODEL` in the project's Environment Variables.
