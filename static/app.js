const textArea = document.querySelector('#rfpText');
const analyzeButton = document.querySelector('#analyzeButton');
const sampleButton = document.querySelector('#sampleButton');
const segmentButton = document.querySelector('#segmentButton');
const searchButton = document.querySelector('#searchButton');
const results = document.querySelector('#results');
const summary = document.querySelector('#summary');
const sectionsOutput = document.querySelector('#sectionsOutput');
const matchesOutput = document.querySelector('#matchesOutput');
const clauseQuery = document.querySelector('#clauseQuery');
const charCount = document.querySelector('#charCount');
const termCount = document.querySelector('#termCount');
const matchCount = document.querySelector('#matchCount');

const sample = `SECTION 1: SCOPE OF WORK
The COTR shall coordinate with the PWS-designated TPOC to ensure all deliverables comply with FAR Part 15 and applicable DFARS clauses prior to CPARS submission.

SECTION 2: SUBMISSION REQUIREMENTS
The vendor must provide weekly status reports, proof of general liability insurance of at least $1,000,000, and all required documentation before the end of the period of performance.

SECTION 3: EVALUATION CRITERIA
Proposals will be evaluated on technical approach, past performance, and price.`;

function updateCount() {
  charCount.textContent = `${textArea.value.length.toLocaleString()} characters`;
}

function showEmpty(message = 'No specialized jargon was found in this text.') {
  results.className = 'results empty-state';
  results.innerHTML = `<div class="empty-icon" aria-hidden="true">Aa</div><h3>Nothing to translate</h3><p>${message}</p>`;
  termCount.textContent = '0 terms';
}

function showEmptySummary(message = 'Add document text and build your summary.') {
  summary.className = 'summary empty-state';
  summary.innerHTML = `<div class="empty-icon" aria-hidden="true">✦</div><h3>No summary yet</h3><p>${message}</p>`;
}

function showSummary(text) {
  if (!text) return showEmptySummary('No summary was generated for this text.');
  summary.className = 'summary';
  summary.innerHTML = '';
  const card = document.createElement('article');
  card.className = 'summary-card';
  const heading = document.createElement('h3');
  heading.textContent = 'What this RFP is saying';
  const body = document.createElement('p');
  body.textContent = text;
  card.append(heading, body);
  summary.append(card);
}

function showTerms(terms) {
  if (!terms.length) return showEmpty();
  results.className = 'results';
  results.replaceChildren();
  terms.forEach(({term, definition}, index) => {
    const card = document.createElement('article');
    card.className = 'term-card';
    card.style.animationDelay = `${index * 45}ms`;
    const heading = document.createElement('h3');
    heading.textContent = term;
    const body = document.createElement('p');
    body.textContent = definition;
    card.append(heading, body);
    results.append(card);
  });
  termCount.textContent = `${terms.length} ${terms.length === 1 ? 'term' : 'terms'}`;
}

function showSections(sections) {
  if (!sections.length) {
    sectionsOutput.className = 'tool-output empty-state compact-empty';
    sectionsOutput.innerHTML = '<h3>No sections found</h3><p>The input is empty, so there is nothing to split yet.</p>';
    return;
  }
  sectionsOutput.className = 'tool-output';
  sectionsOutput.replaceChildren();
  sections.forEach(({heading, start_line, text}) => {
    const card = document.createElement('article');
    card.className = 'section-card';
    const title = document.createElement('h3');
    title.textContent = heading;
    const meta = document.createElement('span');
    meta.textContent = `Starts on line ${start_line}`;
    const body = document.createElement('p');
    body.textContent = text || 'No text appears under this heading.';
    card.append(title, meta, body);
    sectionsOutput.append(card);
  });
}

function showMatches(matches) {
  if (!matches.length) {
    matchesOutput.className = 'tool-output empty-state compact-empty';
    matchesOutput.innerHTML = '<h3>No matches yet</h3><p>Add RFP text and a search question first.</p>';
    matchCount.textContent = '0 matches';
    return;
  }
  matchesOutput.className = 'tool-output';
  matchesOutput.replaceChildren();
  matches.forEach(({text, score}) => {
    const card = document.createElement('article');
    card.className = 'match-card';
    const scoreBadge = document.createElement('span');
    scoreBadge.className = 'score-badge';
    scoreBadge.textContent = `Score ${Number(score).toFixed(2)}`;
    const body = document.createElement('p');
    body.textContent = text;
    card.append(scoreBadge, body);
    matchesOutput.append(card);
  });
  matchCount.textContent = `${matches.length} ${matches.length === 1 ? 'match' : 'matches'}`;
}

async function analyze() {
  const rfpText = textArea.value.trim();
  analyzeButton.disabled = true;
  analyzeButton.querySelector('span').textContent = 'Reading…';
  try {
    showEmptySummary('Reading the RFP and writing a plain-English overview…');
    const response = await fetch('/extract-glossary', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({rfp_text: rfpText})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not build the glossary.');
    showSummary(data.summary);
    showTerms(data.terms);
  } catch (error) {
    summary.className = 'summary';
    summary.innerHTML = `<p class="error">${error.message}</p>`;
    results.className = 'results';
    results.innerHTML = `<p class="error">${error.message}</p>`;
    termCount.textContent = 'Error';
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.querySelector('span').textContent = 'Build glossary';
  }
}

async function segmentRfp() {
  segmentButton.disabled = true;
  segmentButton.textContent = 'Splitting…';
  try {
    const response = await fetch('/segment-rfp', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({rfp_text: textArea.value})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not split sections.');
    showSections(data.sections);
  } catch (error) {
    sectionsOutput.className = 'tool-output';
    sectionsOutput.innerHTML = `<p class="error">${error.message}</p>`;
  } finally {
    segmentButton.disabled = false;
    segmentButton.textContent = 'Split sections';
  }
}

async function searchClauses() {
  const query = clauseQuery.value.trim();
  searchButton.disabled = true;
  searchButton.querySelector('span').textContent = 'Searching…';
  try {
    const response = await fetch('/search-clauses', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({rfp_text: textArea.value, query, top_k: 3})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not search clauses.');
    showMatches(data.matches);
  } catch (error) {
    matchesOutput.className = 'tool-output';
    matchesOutput.innerHTML = `<p class="error">${error.message}</p>`;
    matchCount.textContent = 'Error';
  } finally {
    searchButton.disabled = false;
    searchButton.querySelector('span').textContent = 'Search clauses';
  }
}

textArea.addEventListener('input', updateCount);
analyzeButton.addEventListener('click', analyze);
segmentButton.addEventListener('click', segmentRfp);
searchButton.addEventListener('click', searchClauses);
sampleButton.addEventListener('click', () => { textArea.value = sample; updateCount(); textArea.focus(); });
textArea.addEventListener('keydown', event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') analyze(); });
clauseQuery.addEventListener('keydown', event => { if (event.key === 'Enter') searchClauses(); });
