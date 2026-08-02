const textArea = document.querySelector('#rfpText');
const analyzeButton = document.querySelector('#analyzeButton');
const sampleButton = document.querySelector('#sampleButton');
const segmentButton = document.querySelector('#segmentButton');
const questionButton = document.querySelector('#questionButton');
const requirementsButton = document.querySelector('#requirementsButton');
const results = document.querySelector('#results');
const summary = document.querySelector('#summary');
const sectionsOutput = document.querySelector('#sectionsOutput');
const questionOutput = document.querySelector('#questionOutput');
const requirementsOutput = document.querySelector('#requirementsOutput');
const rfpQuestion = document.querySelector('#rfpQuestion');
const charCount = document.querySelector('#charCount');
const termCount = document.querySelector('#termCount');
const answerConfidence = document.querySelector('#answerConfidence');
const requirementCount = document.querySelector('#requirementCount');

const sample = `SECTION 1: SCOPE OF WORK
The COTR shall coordinate with the PWS-designated TPOC to ensure all deliverables comply with FAR Part 15 and applicable DFARS clauses prior to CPARS submission.

SECTION 2: SUBMISSION REQUIREMENTS
The vendor must provide weekly status reports, proof of general liability insurance of at least $1,000,000, three client references, and all required documentation before the end of the period of performance. All proposals must be received no later than 4:00 PM local time on August 15, 2026. A transition plan should be included when available.

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

function createMatchesFragment(matches) {
  const fragment = document.createDocumentFragment();
  if (!matches.length) {
    const empty = document.createElement('p');
    empty.className = 'muted-note';
    empty.textContent = 'No related passages were found.';
    fragment.append(empty);
    return fragment;
  }
  matches.forEach(({text, score}) => {
    const card = document.createElement('article');
    card.className = 'match-card';
    const scoreBadge = document.createElement('span');
    scoreBadge.className = 'score-badge';
    scoreBadge.textContent = `Score ${Number(score).toFixed(2)}`;
    const body = document.createElement('p');
    body.textContent = text;
    card.append(scoreBadge, body);
    fragment.append(card);
  });
  return fragment;
}

function showQuestionResults(answerData, matches) {
  questionOutput.className = 'tool-output';
  questionOutput.replaceChildren();

  if (!answerData.answer) {
    questionOutput.className = 'tool-output empty-state compact-empty';
    questionOutput.innerHTML = '<h3>No answer found</h3><p>Try asking a more specific question about the RFP.</p>';
    answerConfidence.textContent = 'Low confidence';
    return;
  }

  const card = document.createElement('article');
  card.className = 'answer-card';
  const heading = document.createElement('h3');
  heading.textContent = 'Direct answer';
  const answer = document.createElement('p');
  answer.textContent = answerData.answer;
  const sourceHeading = document.createElement('span');
  sourceHeading.className = 'source-label';
  sourceHeading.textContent = 'Best source excerpt';
  const source = document.createElement('p');
  source.className = 'source-excerpt';
  source.textContent = answerData.source_excerpt || 'No source excerpt available.';
  card.append(heading, answer, sourceHeading, source);

  const matchesHeading = document.createElement('h3');
  matchesHeading.className = 'matches-heading';
  matchesHeading.textContent = 'Related passages';

  questionOutput.append(card, matchesHeading, createMatchesFragment(matches));
  answerConfidence.textContent = `${answerData.confidence || 'low'} confidence`;
}

function showRequirements(requirements) {
  if (!requirements.length) {
    requirementsOutput.className = 'tool-output empty-state compact-empty';
    requirementsOutput.innerHTML = '<h3>No requirements found</h3><p>No explicit vendor submission requirements were detected.</p>';
    requirementCount.textContent = '0 items';
    return;
  }
  requirementsOutput.className = 'tool-output';
  requirementsOutput.replaceChildren();
  requirements.forEach(({item, mandatory, detail}) => {
    const card = document.createElement('article');
    card.className = 'requirement-card';
    const badge = document.createElement('span');
    badge.className = mandatory ? 'status-badge required' : 'status-badge optional';
    badge.textContent = mandatory ? 'Required' : 'Optional';
    const heading = document.createElement('h3');
    heading.textContent = item;
    const body = document.createElement('p');
    body.textContent = detail;
    card.append(badge, heading, body);
    requirementsOutput.append(card);
  });
  requirementCount.textContent = `${requirements.length} ${requirements.length === 1 ? 'item' : 'items'}`;
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

async function searchRfpQuestion() {
  const question = rfpQuestion.value.trim();
  questionButton.disabled = true;
  questionButton.querySelector('span').textContent = 'Searching…';
  try {
    const [answerResponse, matchesResponse] = await Promise.all([
      fetch('/ask-rfp', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rfp_text: textArea.value, question})
      }),
      fetch('/search-clauses', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rfp_text: textArea.value, query: question, top_k: 3})
      })
    ]);
    const answerData = await answerResponse.json();
    const matchesData = await matchesResponse.json();
    if (!answerResponse.ok) throw new Error(answerData.detail || 'Could not answer the question.');
    if (!matchesResponse.ok) throw new Error(matchesData.detail || 'Could not search related passages.');
    showQuestionResults(answerData, matchesData.matches || []);
  } catch (error) {
    questionOutput.className = 'tool-output';
    questionOutput.innerHTML = `<p class="error">${error.message}</p>`;
    answerConfidence.textContent = 'Error';
  } finally {
    questionButton.disabled = false;
    questionButton.querySelector('span').textContent = 'Search RFP';
  }
}

async function extractRequirements() {
  requirementsButton.disabled = true;
  requirementsButton.querySelector('span').textContent = 'Extracting…';
  try {
    const response = await fetch('/extract-requirements', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({rfp_text: textArea.value})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not extract requirements.');
    showRequirements(data.requirements);
  } catch (error) {
    requirementsOutput.className = 'tool-output';
    requirementsOutput.innerHTML = `<p class="error">${error.message}</p>`;
    requirementCount.textContent = 'Error';
  } finally {
    requirementsButton.disabled = false;
    requirementsButton.querySelector('span').textContent = 'Extract checklist';
  }
}

textArea.addEventListener('input', updateCount);
analyzeButton.addEventListener('click', analyze);
segmentButton.addEventListener('click', segmentRfp);
questionButton.addEventListener('click', searchRfpQuestion);
requirementsButton.addEventListener('click', extractRequirements);
sampleButton.addEventListener('click', () => { textArea.value = sample; updateCount(); textArea.focus(); });
textArea.addEventListener('keydown', event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') analyze(); });
rfpQuestion.addEventListener('keydown', event => { if (event.key === 'Enter') searchRfpQuestion(); });
