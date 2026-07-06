"""Send the project brief's sample sentence to a running local service."""

import json
import urllib.request

payload = {"rfp_text": "The COTR shall coordinate with the PWS-designated TPOC to ensure all deliverables comply with FAR Part 15 and applicable DFARS clauses prior to CPARS submission."}
request = urllib.request.Request(
    "http://localhost:8000/extract-glossary",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request) as response:
    print(json.dumps(json.load(response), indent=2))

