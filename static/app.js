const textArea = document.querySelector('#rfpText');
const analyzeButton = document.querySelector('#analyzeButton');
const sampleButton = document.querySelector('#sampleButton');
const pdfFiles = document.querySelector('#pdfFiles');
const ocrButton = document.querySelector('#ocrButton');
const individualSummaryButton = document.querySelector('#individualSummaryButton');
const segmentButton = document.querySelector('#segmentButton');
const questionButton = document.querySelector('#questionButton');
const requirementsButton = document.querySelector('#requirementsButton');
const amendmentButton = document.querySelector('#amendmentButton');
const outlineButton = document.querySelector('#outlineButton');
const complianceButton = document.querySelector('#complianceButton');
const results = document.querySelector('#results');
const summary = document.querySelector('#summary');
const sectionsOutput = document.querySelector('#sectionsOutput');
const questionOutput = document.querySelector('#questionOutput');
const requirementsOutput = document.querySelector('#requirementsOutput');
const amendmentOutput = document.querySelector('#amendmentOutput');
const outlineOutput = document.querySelector('#outlineOutput');
const complianceOutput = document.querySelector('#complianceOutput');
const rfpQuestion = document.querySelector('#rfpQuestion');
const proposalText = document.querySelector('#proposalText');
const charCount = document.querySelector('#charCount');
const termCount = document.querySelector('#termCount');
const answerConfidence = document.querySelector('#answerConfidence');
const requirementCount = document.querySelector('#requirementCount');
const amendmentCount = document.querySelector('#amendmentCount');
const outlineWarningCount = document.querySelector('#outlineWarningCount');
const complianceFlag = document.querySelector('#complianceFlag');
const documentStatus = document.querySelector('#documentStatus');
let uploadedDocuments = [];

const sample = `SECTION 1: SCOPE OF WORK
The COTR shall coordinate with the PWS-designated TPOC to ensure all deliverables comply with FAR Part 15 and applicable DFARS clauses prior to CPARS submission.

SECTION 2: SUBMISSION REQUIREMENTS
The vendor must provide weekly status reports, proof of general liability insurance of at least $1,000,000, three client references, and all required documentation before the end of the period of performance. All proposals must be received no later than 4:00 PM local time on August 15, 2026. A transition plan should be included when available.

SECTION 3: EVALUATION CRITERIA
Proposals will be evaluated on technical approach, past performance, and price.`;

const sampleAmendment = `Amendment 1: Section 2 (Submission Requirements) is revised to read: 'The vendor must provide proof of general liability insurance of at least $2,000,000 and submit proposals by July 15, 2026.'
Amendment 2: Section 3 (Evaluation Criteria) is struck in its entirety.`;

const sampleProposal = `Our support desk operates around the clock, every day of the year, and our team responds within 45 minutes.
We will provide proof of general liability insurance of $2,000,000 with the proposal.
Our transition manager can provide a transition plan after award.`;

function updateCount() {
  charCount.textContent = `${textArea.value.length.toLocaleString()} characters`;
}

function combinedDocumentText(documents = uploadedDocuments) {
  return documents
    .filter(document => document.text && document.text.trim())
    .map(document => `===== ${document.name} =====\n${document.text.trim()}`)
    .join('\n\n');
}

function analysisText() {
  return uploadedDocuments.length ? combinedDocumentText() : textArea.value;
}

function documentsFromCombinedText() {
  const text = textArea.value.trim();
  if (!text) return [];
  const documentPattern = /^===== (.+?) =====\n([\s\S]*?)(?=^===== .+? =====\n|\s*$)/gm;
  const documents = [];
  let match;
  while ((match = documentPattern.exec(text)) !== null) {
    const name = match[1].trim();
    const body = match[2].trim();
    if (name && body) documents.push({name, text: body});
  }
  return documents;
}

function jointSummaryDocuments() {
  if (uploadedDocuments.length >= 2) return uploadedDocuments;
  const parsedDocuments = documentsFromCombinedText();
  if (parsedDocuments.length >= 2) return parsedDocuments;
  return [];
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

function showAmendments(data) {
  amendmentOutput.className = 'tool-output';
  amendmentOutput.replaceChildren();
  if (!data.effective_sections.length) {
    amendmentOutput.className = 'tool-output empty-state compact-empty';
    amendmentOutput.innerHTML = '<h3>No sections found</h3><p>Add original RFP text and amendment language first.</p>';
    amendmentCount.textContent = '0 changes';
    return;
  }
  data.effective_sections.forEach(({section, heading, text, status, modified_by_amendment}) => {
    const card = document.createElement('article');
    card.className = 'section-card';
    const badge = document.createElement('span');
    badge.className = `status-badge ${status === 'struck' ? 'optional' : 'required'}`;
    badge.textContent = status;
    const title = document.createElement('h3');
    title.textContent = `${section} ${heading}`;
    const meta = document.createElement('span');
    meta.textContent = modified_by_amendment ? `Changed by amendment ${modified_by_amendment}` : 'Original text';
    const body = document.createElement('p');
    body.textContent = text || 'This section was struck and is no longer effective.';
    card.append(badge, title, meta, body);
    amendmentOutput.append(card);
  });
  if (data.unmatched_amendment_text.length) {
    const warning = document.createElement('p');
    warning.className = 'error';
    warning.textContent = `Needs review: ${data.unmatched_amendment_text.join(' ')}`;
    amendmentOutput.append(warning);
  }
  amendmentCount.textContent = `${data.changelog.length} ${data.changelog.length === 1 ? 'change' : 'changes'}`;
}

function createOutlineList(nodes) {
  if (!nodes.length) {
    const empty = document.createElement('p');
    empty.className = 'muted-note';
    empty.textContent = 'No numbered headings were found.';
    return empty;
  }
  const list = document.createElement('ol');
  list.className = 'outline-tree';
  nodes.forEach(node => {
    const item = document.createElement('li');
    const title = document.createElement('strong');
    title.textContent = `${node.number} ${node.heading}`;
    item.append(title);
    if (node.text) {
      const body = document.createElement('p');
      body.textContent = node.text;
      item.append(body);
    }
    item.append(createOutlineList(node.children || []));
    list.append(item);
  });
  return list;
}

function showOutline(data) {
  outlineOutput.className = 'tool-output';
  outlineOutput.replaceChildren(createOutlineList(data.outline));
  if (data.warnings.length) {
    const warningBox = document.createElement('div');
    warningBox.className = 'warning-list';
    const heading = document.createElement('h3');
    heading.textContent = 'Warnings';
    warningBox.append(heading);
    data.warnings.forEach(warning => {
      const item = document.createElement('p');
      item.textContent = warning.detail;
      warningBox.append(item);
    });
    outlineOutput.append(warningBox);
  }
  outlineWarningCount.textContent = `${data.warnings.length} ${data.warnings.length === 1 ? 'warning' : 'warnings'}`;
}

function showCompliance(data) {
  complianceOutput.className = 'tool-output';
  complianceOutput.replaceChildren();
  if (!data.matrix.length) {
    complianceOutput.className = 'tool-output empty-state compact-empty';
    complianceOutput.innerHTML = '<h3>No matrix built</h3><p>Extract requirements from the RFP and paste proposal text first.</p>';
    complianceFlag.textContent = 'Not checked';
    return;
  }
  data.matrix.forEach(({requirement_id, status, confidence, matched_passage, similarity_score, note}) => {
    const card = document.createElement('article');
    card.className = 'requirement-card';
    const badge = document.createElement('span');
    badge.className = `status-badge ${status === 'met' ? 'required' : 'optional'}`;
    badge.textContent = status.replaceAll('_', ' ');
    const title = document.createElement('h3');
    title.textContent = requirement_id;
    const meta = document.createElement('span');
    meta.textContent = `${confidence} confidence · score ${Number(similarity_score).toFixed(2)}`;
    const body = document.createElement('p');
    body.textContent = matched_passage || 'No matching proposal passage found.';
    card.append(badge, title, meta, body);
    if (note) {
      const noteText = document.createElement('p');
      noteText.className = 'muted-note';
      noteText.textContent = note;
      card.append(noteText);
    }
    complianceOutput.append(card);
  });
  complianceFlag.textContent = data.overall_flag.replaceAll('_', ' ');
}

function updateDocumentStatus() {
  if (!uploadedDocuments.length) {
    documentStatus.textContent = 'No PDFs loaded yet.';
    return;
  }
  const names = uploadedDocuments.map(document => document.name).join(', ');
  documentStatus.textContent = `${uploadedDocuments.length} PDF ${uploadedDocuments.length === 1 ? 'document' : 'documents'} ready: ${names}`;
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || '');
      resolve(result.includes(',') ? result.split(',')[1] : result);
    };
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.readAsDataURL(file);
  });
}

function placeUploadedDocuments() {
  if (!uploadedDocuments.length) return;
  textArea.value = combinedDocumentText();
  updateCount();
  updateDocumentStatus();
}

function showIndividualSummaries(items) {
  summary.className = 'summary';
  summary.replaceChildren();
  if (!items.length) {
    return showEmptySummary('Upload PDFs first, then click Each PDF.');
  }
  items.forEach(({name, summary: summaryText}) => {
    const card = document.createElement('article');
    card.className = 'summary-card';
    const heading = document.createElement('h3');
    heading.textContent = name;
    const body = document.createElement('p');
    body.textContent = summaryText || 'No summary was generated for this PDF.';
    card.append(heading, body);
    summary.append(card);
  });
}

function showJointSummary(data) {
  amendmentOutput.className = 'tool-output';
  amendmentOutput.replaceChildren();
  if (!data.summary) {
    amendmentOutput.className = 'tool-output empty-state compact-empty';
    amendmentOutput.innerHTML = '<h3>No joint summary yet</h3><p>Add at least one RFP or amendment document first.</p>';
    amendmentCount.textContent = '0 docs';
    return;
  }

  const summaryCard = document.createElement('article');
  summaryCard.className = 'answer-card';
  const heading = document.createElement('h3');
  heading.textContent = 'Combined plain-English summary';
  const body = document.createElement('p');
  body.textContent = data.summary;
  summaryCard.append(heading, body);
  amendmentOutput.append(summaryCard);

  if ((data.key_points || []).length) {
    const pointsCard = document.createElement('article');
    pointsCard.className = 'requirement-card';
    const pointsHeading = document.createElement('h3');
    pointsHeading.textContent = 'Important points';
    const list = document.createElement('ul');
    list.className = 'plain-list';
    data.key_points.forEach(point => {
      const item = document.createElement('li');
      item.textContent = point;
      list.append(item);
    });
    pointsCard.append(pointsHeading, list);
    amendmentOutput.append(pointsCard);
  }

  if ((data.differences || []).length) {
    const changesCard = document.createElement('article');
    changesCard.className = 'requirement-card';
    const changesHeading = document.createElement('h3');
    changesHeading.textContent = 'Updates or differences to review';
    const list = document.createElement('ul');
    list.className = 'plain-list';
    data.differences.forEach(change => {
      const item = document.createElement('li');
      item.textContent = change;
      list.append(item);
    });
    changesCard.append(changesHeading, list);
    amendmentOutput.append(changesCard);
  }
  amendmentCount.textContent = `${data.document_count || 0} ${data.document_count === 1 ? 'doc' : 'docs'}`;
}

async function readPdfs() {
  const files = Array.from(pdfFiles.files || []);
  if (!files.length) {
    documentStatus.textContent = 'Choose one or more PDF files first.';
    return;
  }
  uploadedDocuments = [];
  ocrButton.disabled = true;
  ocrButton.textContent = 'Reading PDFs…';
  documentStatus.textContent = 'Sending PDFs to Mistral OCR. This can take a moment.';
  try {
    for (const file of files) {
      const contentBase64 = await fileToBase64(file);
      const response = await fetch('/ocr-pdf', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({filename: file.name, content_base64: contentBase64})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Could not read ${file.name}.`);
      uploadedDocuments.push({name: data.filename, text: data.text});
    }
    placeUploadedDocuments();
    if (uploadedDocuments.length > 1) {
      amendmentCount.textContent = `${uploadedDocuments.length} docs`;
    }
  } catch (error) {
    documentStatus.textContent = error.message;
  } finally {
    ocrButton.disabled = false;
    ocrButton.textContent = 'Read PDFs';
  }
}

async function summarizeIndividualPdfs() {
  if (!uploadedDocuments.length) {
    showEmptySummary('Upload PDFs first, then click Each PDF.');
    return;
  }
  individualSummaryButton.disabled = true;
  individualSummaryButton.textContent = 'Summarizing…';
  try {
    const summaries = [];
    for (const document of uploadedDocuments) {
      const response = await fetch('/extract-glossary', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rfp_text: document.text})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Could not summarize ${document.name}.`);
      summaries.push({name: document.name, summary: data.summary});
    }
    showIndividualSummaries(summaries);
  } catch (error) {
    summary.className = 'summary';
    summary.innerHTML = `<p class="error">${error.message}</p>`;
  } finally {
    individualSummaryButton.disabled = false;
    individualSummaryButton.textContent = 'Each PDF';
  }
}

async function analyze() {
  const rfpText = analysisText().trim();
  analyzeButton.disabled = true;
  analyzeButton.querySelector('span').textContent = 'Reading…';
  try {
    showEmptySummary('Writing a plain-English overview…');
    const response = await fetch('/extract-glossary', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({rfp_text: rfpText})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not analyze the documents.');
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
    analyzeButton.querySelector('span').textContent = 'Analyze';
  }
}

async function segmentRfp() {
  segmentButton.disabled = true;
  segmentButton.textContent = 'Splitting…';
  try {
    const response = await fetch('/segment-rfp', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({rfp_text: analysisText()})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not split sections.');
    showSections(data.sections);
  } catch (error) {
    sectionsOutput.className = 'tool-output';
    sectionsOutput.innerHTML = `<p class="error">${error.message}</p>`;
  } finally {
    segmentButton.disabled = false;
    segmentButton.textContent = 'Split';
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
        body: JSON.stringify({rfp_text: analysisText(), question})
      }),
      fetch('/search-clauses', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rfp_text: analysisText(), query: question, top_k: 3})
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
    questionButton.querySelector('span').textContent = 'Search';
  }
}

async function extractRequirements() {
  requirementsButton.disabled = true;
  requirementsButton.querySelector('span').textContent = 'Extracting…';
  try {
    const response = await fetch('/extract-requirements', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({rfp_text: analysisText()})
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
    requirementsButton.querySelector('span').textContent = 'Extract';
  }
}

async function resolveAmendments() {
  amendmentButton.disabled = true;
  amendmentButton.querySelector('span').textContent = 'Summarizing…';
  try {
    const documents = jointSummaryDocuments();
    if (documents.length < 2) {
      throw new Error('Upload at least two PDFs first, then click Read PDFs so both documents appear in the main text box.');
    }
    const response = await fetch('/joint-summary', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({documents})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not create a joint summary.');
    showJointSummary(data);
  } catch (error) {
    amendmentOutput.className = 'tool-output';
    amendmentOutput.innerHTML = `<p class="error">${error.message}</p>`;
    amendmentCount.textContent = 'Error';
  } finally {
    amendmentButton.disabled = false;
    amendmentButton.querySelector('span').textContent = 'Create joint summary';
  }
}

async function buildOutline() {
  outlineButton.disabled = true;
  outlineButton.querySelector('span').textContent = 'Building…';
  try {
    const response = await fetch('/reconstruct-outline', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({document_text: analysisText()})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not build outline.');
    showOutline(data);
  } catch (error) {
    outlineOutput.className = 'tool-output';
    outlineOutput.innerHTML = `<p class="error">${error.message}</p>`;
    outlineWarningCount.textContent = 'Error';
  } finally {
    outlineButton.disabled = false;
    outlineButton.querySelector('span').textContent = 'Build';
  }
}

async function buildCompliance() {
  complianceButton.disabled = true;
  complianceButton.querySelector('span').textContent = 'Building…';
  try {
    const requirementResponse = await fetch('/extract-requirements', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({rfp_text: analysisText()})
    });
    const requirementData = await requirementResponse.json();
    if (!requirementResponse.ok) throw new Error(requirementData.detail || 'Could not extract requirements.');
    const requirements = requirementData.requirements.map((requirement, index) => ({
      id: `req-${index + 1}`,
      text: requirement.detail,
      mandatory: requirement.mandatory
    }));
    const response = await fetch('/build-compliance-matrix', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({requirements, proposal_text: proposalText.value})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not build compliance matrix.');
    showCompliance(data);
  } catch (error) {
    complianceOutput.className = 'tool-output';
    complianceOutput.innerHTML = `<p class="error">${error.message}</p>`;
    complianceFlag.textContent = 'Error';
  } finally {
    complianceButton.disabled = false;
    complianceButton.querySelector('span').textContent = 'Compare';
  }
}

textArea.addEventListener('input', updateCount);
analyzeButton.addEventListener('click', analyze);
ocrButton.addEventListener('click', readPdfs);
individualSummaryButton.addEventListener('click', summarizeIndividualPdfs);
segmentButton.addEventListener('click', segmentRfp);
questionButton.addEventListener('click', searchRfpQuestion);
requirementsButton.addEventListener('click', extractRequirements);
amendmentButton.addEventListener('click', resolveAmendments);
outlineButton.addEventListener('click', buildOutline);
complianceButton.addEventListener('click', buildCompliance);
sampleButton.addEventListener('click', () => {
  uploadedDocuments = [
    {name: 'demo_original_rfp.pdf', text: sample},
    {name: 'demo_amendment_rfp.pdf', text: sampleAmendment}
  ];
  textArea.value = combinedDocumentText();
  proposalText.value = sampleProposal;
  updateCount();
  updateDocumentStatus();
  amendmentCount.textContent = `${uploadedDocuments.length} docs`;
  textArea.focus();
});
textArea.addEventListener('keydown', event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') analyze(); });
rfpQuestion.addEventListener('keydown', event => { if (event.key === 'Enter') searchRfpQuestion(); });
pdfFiles.addEventListener('change', () => {
  uploadedDocuments = [];
  updateDocumentStatus();
  if (pdfFiles.files.length) {
    documentStatus.textContent = `${pdfFiles.files.length} PDF ${pdfFiles.files.length === 1 ? 'selected' : 'files selected'}. Click “Read PDFs” to extract the text.`;
  }
});
