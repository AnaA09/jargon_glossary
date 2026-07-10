# jargon_glossary

A FastAPI service and ClearTerms browser interface that summarizes RFP text, finds procurement acronyms, and explains them in plain English. Duplicate terms are removed automatically.

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

The included local demo can summarize text and recognize common procurement terms without an API key. To get stronger AI summaries and analyze arbitrary RFP jargon, add an OpenRouter API key to `.env`:

```text
OPENROUTER_API_KEY=your-key-here
OPENROUTER_MODEL=openrouter/auto
```

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
