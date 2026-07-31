# jargon_glossary

A FastAPI service and ClearTerms browser interface that summarizes RFP text, finds procurement acronyms, splits RFPs into sections, and searches for relevant clauses. Duplicate glossary terms are removed automatically.

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

The included local demo can summarize text, recognize common procurement terms, segment sections, and search clauses without an API key. To get stronger AI summaries, better section segmentation, and better clause search, add an OpenRouter API key to `.env`:

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
