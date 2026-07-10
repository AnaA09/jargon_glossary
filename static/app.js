const textArea = document.querySelector('#rfpText');
const analyzeButton = document.querySelector('#analyzeButton');
const sampleButton = document.querySelector('#sampleButton');
const results = document.querySelector('#results');
const summary = document.querySelector('#summary');
const charCount = document.querySelector('#charCount');
const termCount = document.querySelector('#termCount');

const sample = 'The COTR shall coordinate with the PWS-designated TPOC to ensure all deliverables comply with FAR Part 15 and applicable DFARS clauses prior to CPARS submission. The vendor must provide weekly status reports, maintain quality controls, and submit all required documentation before the end of the period of performance.';

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

textArea.addEventListener('input', updateCount);
analyzeButton.addEventListener('click', analyze);
sampleButton.addEventListener('click', () => { textArea.value = sample; updateCount(); textArea.focus(); });
textArea.addEventListener('keydown', event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') analyze(); });
