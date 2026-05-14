// ── State ─────────────────────────────────────────────────────────────────
let runId = null;
let eventSource = null;
let resultData = null;
let selectedApproach = null;

// Checkpoint history for navigate-back (client-side only, no re-run)
let checkpointHistory = [];   // [{checkpoint, data}, ...]
let historyIndex = -1;        // index of the panel currently shown

// Per-checkpoint chat histories (for approaches: note accumulation)
let chatHistories = {};       // {checkpoint: [{role, text}, ...]}
let approachesNotes = [];     // accumulated chat notes for approaches checkpoint

// All steps in pipeline order (agent steps + HITL checkpoints)
const STEPS = [
  { key: 'business_analyst',  label: 'Business Analyst',             type: 'agent' },
  { key: 'review_brief',      label: 'Review: Business Brief',       type: 'hitl'  },
  { key: 'solutioning',       label: 'Solutioning',                  type: 'agent' },
  { key: 'review_approaches', label: 'Review: Approaches',           type: 'hitl'  },
  { key: 'architect',         label: 'Architect',                    type: 'agent' },
  { key: 'review_architect',  label: 'Review: Architecture',         type: 'hitl'  },
  { key: 'risk_reviewer',     label: 'Risk Reviewer',                type: 'agent' },
  { key: 'review_risks',      label: 'Review: Risks',                type: 'hitl'  },
  { key: 'doc_writer',        label: 'Doc Writer',                   type: 'agent' },
  { key: 'review_draft',      label: 'Review: Draft Document',       type: 'hitl'  },
  { key: 'doc_reviewer',      label: 'Doc Reviewer',                 type: 'agent' },
  { key: 'review_feedback',   label: 'Review: Critique',             type: 'hitl'  },
  { key: 'editor',            label: 'Editor',                       type: 'agent' },
  { key: 'review_final',      label: 'Review: Final Document',       type: 'hitl'  },
];

// Map checkpoint name → HITL step key for sidebar updates
const CHECKPOINT_STEP_KEY = {
  brief:           'review_brief',
  approaches:      'review_approaches',
  architect:       'review_architect',
  risks:           'review_risks',
  draft:           'review_draft',
  review_feedback: 'review_feedback',
  final:           'review_final',
};

// ── View helpers ───────────────────────────────────────────────────────────
function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(`view-${name}`).classList.add('active');
}

function showError(message) {
  document.getElementById('error-message').textContent = message;
  document.getElementById('error-bar').classList.remove('hidden');
}

// ── Step list ──────────────────────────────────────────────────────────────
function renderStepList() {
  const ul = document.getElementById('step-list');
  ul.innerHTML = '';
  STEPS.forEach(step => {
    const li = document.createElement('li');
    li.id = `step-${step.key}`;
    li.className = `step-item${step.type === 'hitl' ? ' hitl' : ''}`;
    li.innerHTML = `
      <span class="step-icon">${step.type === 'hitl' ? '⏸' : '·'}</span>
      <span class="step-label">${step.label}</span>
      <span class="step-elapsed"></span>
    `;
    ul.appendChild(li);
  });
}

function updateStep(key, status, elapsed = null) {
  const li = document.getElementById(`step-${key}`);
  if (!li) return;
  li.className = `step-item ${status}${li.classList.contains('hitl') ? ' hitl' : ''}`;

  const icon = li.querySelector('.step-icon');
  const elapsedEl = li.querySelector('.step-elapsed');

  if (status === 'running') {
    icon.innerHTML = '<span class="spinner"></span>';
    elapsedEl.textContent = '';
  } else if (status === 'done') {
    icon.textContent = '✓';
    elapsedEl.textContent = elapsed != null ? `${elapsed}s` : '';
  } else if (status === 'waiting') {
    icon.textContent = '⏸';
    elapsedEl.textContent = 'waiting';
  }
}

// ── Requirements clarification ─────────────────────────────────────────────
async function analyseRequirements() {
  const requirements = document.getElementById('requirements').value.trim();
  if (!requirements) {
    showError('Please enter your business requirements before analysing.');
    return;
  }

  const btn = document.getElementById('btn-analyse');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Analysing…';

  try {
    const res = await fetch('/api/clarify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirements }),
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const { questions } = await res.json();

    if (!questions || questions.length === 0) {
      // No questions — go straight to generation
      await startRun(false);
      return;
    }

    renderQuestions(questions);
    document.getElementById('clarification-area').classList.remove('hidden');
  } catch (err) {
    showError(`Failed to analyse requirements: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Analyse requirements <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }
}

function renderQuestions(questions) {
  const list = document.getElementById('questions-list');
  list.innerHTML = '';
  questions.forEach((q, i) => {
    const card = document.createElement('div');
    card.className = 'question-card';
    card.innerHTML = `
      <label class="question-label" for="question-${i}">${escapeHtml(q)}</label>
      <input type="text" id="question-${i}" class="question-input" data-question="${escapeHtml(q)}" placeholder="Your answer (optional)" />
    `;
    list.appendChild(card);
  });
}

function buildEnrichedRequirements() {
  const base = document.getElementById('requirements').value.trim();
  const inputs = document.querySelectorAll('.question-input');
  const answered = [];
  inputs.forEach(input => {
    const answer = input.value.trim();
    if (answer) answered.push(`Q: ${input.dataset.question}\nA: ${answer}`);
  });
  if (answered.length === 0) return base;
  return `${base}\n\n---\n\n**Clarifying answers provided before generation:**\n${answered.join('\n\n')}`;
}

// ── Start run ──────────────────────────────────────────────────────────────
async function startRun(useAnswers = true) {
  const rawRequirements = document.getElementById('requirements').value.trim();
  if (!rawRequirements) {
    showError('Please enter your business requirements before generating.');
    return;
  }
  const requirements = useAnswers ? buildEnrichedRequirements() : rawRequirements;

  const btn = document.getElementById('btn-submit');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Starting…';

  try {
    const res = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirements }),  // may be enriched with Q&A answers
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const { run_id } = await res.json();
    runId = run_id;
  } catch (err) {
    showError(`Failed to start run: ${err.message}`);
    btn.disabled = false;
    btn.innerHTML = 'Generate <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    return;
  }

  // Reset history for new run
  checkpointHistory = [];
  historyIndex = -1;

  showView('progress');
  renderStepList();
  showIdlePanel();
  openStream();
}

// ── SSE stream ─────────────────────────────────────────────────────────────
function openStream() {
  eventSource = new EventSource(`/api/runs/${runId}/stream`);

  eventSource.addEventListener('progress',   e => handleProgress(JSON.parse(e.data)));
  eventSource.addEventListener('checkpoint', e => handleCheckpoint(JSON.parse(e.data)));
  eventSource.addEventListener('complete',   e => handleComplete(JSON.parse(e.data)));
  eventSource.addEventListener('error',      e => {
    try { handlePipelineError(JSON.parse(e.data)); } catch (_) { /* connection error */ }
  });

  eventSource.onerror = () => {
    if (runId && !resultData) showError('Connection to server lost. The pipeline may still be running — refresh to check.');
  };
}

function handleProgress(data) {
  updateStep(data.step, data.status, data.elapsed_s);
}

function handleCheckpoint(data) {
  // Record in history
  checkpointHistory.push({ checkpoint: data.checkpoint, data });
  historyIndex = checkpointHistory.length - 1;

  // Mark sidebar
  const stepKey = CHECKPOINT_STEP_KEY[data.checkpoint];
  if (stepKey) updateStep(stepKey, 'waiting');

  renderCheckpointPanel(data.checkpoint, data, true);
}

function handleComplete(data) {
  eventSource.close();
  resultData = data;
  showResults(data);
}

function handlePipelineError(data) {
  eventSource.close();
  showError(data.message || 'An unexpected error occurred in the pipeline.');
}

// ── Checkpoint panel routing ───────────────────────────────────────────────
function renderCheckpointPanel(checkpoint, data, isLatest) {
  hideAllPanels();
  switch (checkpoint) {
    case 'brief':           showBriefPanel(data, isLatest); break;
    case 'approaches':      showApproachesPanel(data, isLatest); break;
    case 'architect':       showArchitectPanel(data, isLatest); break;
    case 'risks':           showRisksPanel(data, isLatest); break;
    case 'draft':           showDraftPanel(data, isLatest); break;
    case 'review_feedback': showReviewFeedbackPanel(data, isLatest); break;
    case 'final':           showFinalPanel(data, isLatest); break;
  }
}

// ── Navigate back / forward ────────────────────────────────────────────────
function goBack() {
  if (historyIndex <= 0) return;
  historyIndex--;
  const entry = checkpointHistory[historyIndex];
  renderCheckpointPanel(entry.checkpoint, entry.data, false);
}

function goForward() {
  if (historyIndex >= checkpointHistory.length - 1) return;
  historyIndex++;
  const entry = checkpointHistory[historyIndex];
  const isLatest = historyIndex === checkpointHistory.length - 1;
  renderCheckpointPanel(entry.checkpoint, entry.data, isLatest);
}

function _navButtons(isLatest, checkpointIndex) {
  const isFirst = checkpointIndex === 0;
  const backDisabled = isFirst ? 'disabled' : '';
  const backBtn = `<button class="btn-ghost" onclick="goBack()" ${backDisabled}>← Back</button>`;
  const fwdBtn = !isLatest
    ? `<button class="btn-ghost" onclick="goForward()">Forward →</button>`
    : '';
  return { backBtn, fwdBtn };
}

// ── Conversational refinement ──────────────────────────────────────────────
async function sendRefinement(checkpoint) {
  if (!runId) return;
  const inputEl = document.getElementById(`${checkpoint}-chat-input`);
  if (!inputEl) return;
  const message = inputEl.value.trim();
  if (!message) return;

  inputEl.disabled = true;
  appendChatMessage(checkpoint, 'user', message);
  inputEl.value = '';

  // Build request body based on checkpoint type
  const body = { checkpoint, message };
  if (checkpoint === 'architect') {
    body.current_output = document.getElementById('architect-architecture').textContent;
    body.current_decisions = _currentDecisions;
  } else if (checkpoint === 'risks') {
    body.current_risks = _currentRisks;
  } else if (checkpoint === 'approaches') {
    // No LLM call — just record the note
    approachesNotes.push(message);
    appendChatMessage(checkpoint, 'assistant', 'Noted — your input will be carried forward when you continue.');
    inputEl.disabled = false;
    return;
  } else {
    // Text checkpoints
    const outputEl = document.getElementById(_outputElId(checkpoint));
    body.current_output = outputEl ? (outputEl.value ?? outputEl.textContent) : '';
  }

  const loadingId = appendChatMessage(checkpoint, 'assistant', '…');

  try {
    const res = await fetch(`/api/runs/${runId}/refine`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();
    refreshOutputArea(checkpoint, data);
    updateChatMessage(checkpoint, loadingId, 'Updated above ✓');
  } catch (err) {
    updateChatMessage(checkpoint, loadingId, `Error: ${err.message}`);
  } finally {
    inputEl.disabled = false;
    inputEl.focus();
  }
}

function _setChatEnabled(checkpoint, enabled) {
  const input = document.getElementById(`${checkpoint}-chat-input`);
  if (input) input.disabled = !enabled;
  const btn = document.querySelector(`#panel-${checkpoint.replace('_','-')} .chat-send`);
  if (btn) btn.disabled = !enabled;
}

// Map checkpoint → output element id
function _outputElId(checkpoint) {
  const map = {
    brief:           'brief-text',
    draft:           'draft-text',
    final:           'final-text',
    review_feedback: 'review-feedback-output',
    architect:       'architect-architecture',
  };
  return map[checkpoint] || null;
}

// Update DOM output area after refinement
function refreshOutputArea(checkpoint, data) {
  if (checkpoint === 'architect') {
    if (data.updated_text) document.getElementById('architect-architecture').textContent = data.updated_text;
    if (data.updated_decisions) {
      _currentDecisions = data.updated_decisions;
      renderDecisionsList(data.updated_decisions);
    }
  } else if (checkpoint === 'risks') {
    if (data.updated_risks) {
      _currentRisks = data.updated_risks;
      renderRiskCards(data.updated_risks);
    }
  } else {
    const el = document.getElementById(_outputElId(checkpoint));
    if (!el || !data.updated_text) return;
    if (el.tagName === 'TEXTAREA') el.value = data.updated_text;
    else el.textContent = data.updated_text;
  }
}

// Mutable copies of structured data for refinement
let _currentDecisions = [];
let _currentRisks = [];

function renderDecisionsList(decisions) {
  const container = document.getElementById('architect-decisions');
  container.innerHTML = decisions.map(d => `
    <div class="decision-item">
      <strong>${escapeHtml(d.title || '')}</strong>
      <div class="decision-meta">Decision: ${escapeHtml(d.decision || '')}</div>
      <div class="decision-meta">Reasoning: ${escapeHtml(d.reasoning || '')}</div>
    </div>
  `).join('') || '<em>No decisions recorded.</em>';
}

function renderRiskCards(risks) {
  document.getElementById('risks-list').innerHTML = (risks || []).map((r, i) => `
    <div class="risk-item">
      <span class="risk-index">${i + 1}</span>
      <div class="risk-body">
        <div class="risk-desc">${escapeHtml(r.description || '')}</div>
        <div class="risk-meta">
          <span class="badge likelihood-${r.likelihood}">Likelihood: ${r.likelihood}</span>
          <span class="badge impact-${r.impact}">Impact: ${r.impact}</span>
        </div>
        <div class="risk-mitigation"><strong>Mitigation:</strong> ${escapeHtml(r.mitigation || '')}</div>
      </div>
    </div>
  `).join('') || '<em>No risks recorded.</em>';
}

// Chat log helpers
function appendChatMessage(checkpoint, role, text) {
  const log = document.getElementById(`${checkpoint}-chat-log`);
  if (!log) return null;
  const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const div = document.createElement('div');
  div.id = id;
  div.className = `chat-message chat-${role}`;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return id;
}

function updateChatMessage(checkpoint, id, text) {
  if (!id) return;
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// ── Panel helpers ──────────────────────────────────────────────────────────
function hideAllPanels() {
  [
    'panel-idle', 'panel-brief', 'panel-approaches',
    'panel-architect', 'panel-risks', 'panel-draft',
    'panel-review-feedback', 'panel-final',
  ].forEach(id => document.getElementById(id).classList.add('hidden'));
}

function showIdlePanel() {
  hideAllPanels();
  document.getElementById('panel-idle').classList.remove('hidden');
}

// ── Brief panel ────────────────────────────────────────────────────────────
function showBriefPanel(data, isLatest) {
  document.getElementById('brief-text').value = data.business_brief || '';
  _setCheckpointNav('brief', isLatest, 1);
  _setChatEnabled('brief', isLatest);
  document.getElementById('panel-brief').classList.remove('hidden');
  _toggleBriefSubmit(isLatest);
}

function _toggleBriefSubmit(isLatest) {
  document.getElementById('brief-submit-actions').classList.toggle('hidden', !isLatest);
  document.getElementById('brief-text').readOnly = !isLatest;
}

async function approveBrief(saveChanges) {
  const brief = saveChanges ? document.getElementById('brief-text').value.trim() : null;
  await respondToCheckpoint({ checkpoint: 'brief', business_brief: brief });
  updateStep('review_brief', 'done');
  showIdlePanel();
}

// ── Approaches panel ───────────────────────────────────────────────────────
function showApproachesPanel(data, isLatest) {
  selectedApproach = null;
  const list = document.getElementById('approaches-list');
  list.innerHTML = '';

  (data.candidate_approaches || []).forEach(a => {
    const card = document.createElement('div');
    card.className = 'approach-card';
    card.dataset.name = a.name;
    card.innerHTML = `
      <div class="approach-radio"></div>
      <div class="approach-body">
        <div class="approach-title">
          ${escapeHtml(a.name)}
          <span class="score-badge">${a.suitability_score}/10</span>
        </div>
        <div class="approach-summary">${escapeHtml(a.summary)}</div>
        <div class="approach-tradeoffs"><strong>Tradeoffs:</strong> ${escapeHtml(a.tradeoffs)}</div>
        <div class="approach-components">
          ${(a.key_components || []).map(c => `<span class="component-tag">${escapeHtml(c)}</span>`).join('')}
        </div>
      </div>
    `;
    if (isLatest) {
      card.addEventListener('click', () => {
        list.querySelectorAll('.approach-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedApproach = a.name;
      });
    }
    list.appendChild(card);
  });

  _setCheckpointNav('approaches', isLatest, 2);
  document.getElementById('panel-approaches').classList.remove('hidden');
  document.getElementById('approaches-submit-actions').classList.toggle('hidden', !isLatest);
}

async function submitSelectedApproach() {
  if (!selectedApproach) {
    showError('Please select an approach first, or click "Let architect decide".');
    return;
  }
  await submitApproach(selectedApproach);
}

async function submitApproach(name) {
  // Carry any chat notes forward as a note on the selected approach
  const notePayload = approachesNotes.length
    ? { selected_approach: name, approach_notes: approachesNotes.join('; ') }
    : { selected_approach: name };
  await respondToCheckpoint({ checkpoint: 'approaches', ...notePayload });
  approachesNotes = [];
  updateStep('review_approaches', 'done');
  showIdlePanel();
}

// ── Architect panel ────────────────────────────────────────────────────────
function showArchitectPanel(data, isLatest) {
  _currentDecisions = data.decisions || [];
  document.getElementById('architect-architecture').textContent = data.architecture || '';
  renderDecisionsList(_currentDecisions);
  document.getElementById('architect-feedback').value = '';
  document.getElementById('architect-feedback').disabled = !isLatest;
  _setChatEnabled('architect', isLatest);

  _setCheckpointNav('architect', isLatest, 3);
  document.getElementById('panel-architect').classList.remove('hidden');
  document.getElementById('architect-submit-actions').classList.toggle('hidden', !isLatest);
}

async function submitArchitectFeedback() {
  const feedback = document.getElementById('architect-feedback').value.trim();
  await respondToCheckpoint({ checkpoint: 'architect', architecture_feedback: feedback || null });
  updateStep('review_architect', 'done');
  showIdlePanel();
}

// ── Risks panel ────────────────────────────────────────────────────────────
function showRisksPanel(data, isLatest) {
  _currentRisks = data.risks || [];
  renderRiskCards(_currentRisks);
  document.getElementById('risks-feedback').value = '';
  document.getElementById('risks-feedback').disabled = !isLatest;
  _setChatEnabled('risks', isLatest);

  _setCheckpointNav('risks', isLatest, 4);
  document.getElementById('panel-risks').classList.remove('hidden');
  document.getElementById('risks-submit-actions').classList.toggle('hidden', !isLatest);
}

async function submitRisksFeedback() {
  const feedback = document.getElementById('risks-feedback').value.trim();
  await respondToCheckpoint({ checkpoint: 'risks', risk_feedback: feedback || null });
  updateStep('review_risks', 'done');
  showIdlePanel();
}

// ── Draft panel ────────────────────────────────────────────────────────────
function showDraftPanel(data, isLatest) {
  document.getElementById('draft-text').value = data.draft_doc || '';
  document.getElementById('draft-text').readOnly = !isLatest;

  _setCheckpointNav('draft', isLatest, 5);
  _setChatEnabled('draft', isLatest);
  document.getElementById('panel-draft').classList.remove('hidden');
  document.getElementById('draft-submit-actions').classList.toggle('hidden', !isLatest);
}

async function submitDraft(saveChanges) {
  const doc = saveChanges ? document.getElementById('draft-text').value.trim() : null;
  await respondToCheckpoint({ checkpoint: 'draft', draft_doc: doc });
  updateStep('review_draft', 'done');
  showIdlePanel();
}

// ── Review feedback panel ──────────────────────────────────────────────────
function showReviewFeedbackPanel(data, isLatest) {
  document.getElementById('review-feedback-output').textContent = data.review_feedback || '';
  document.getElementById('review-feedback-note').value = '';
  document.getElementById('review-feedback-note').disabled = !isLatest;

  _setCheckpointNav('review_feedback', isLatest, 6);
  _setChatEnabled('review_feedback', isLatest);
  document.getElementById('panel-review-feedback').classList.remove('hidden');
  document.getElementById('review-feedback-submit-actions').classList.toggle('hidden', !isLatest);
}

async function submitReviewFeedback() {
  const note = document.getElementById('review-feedback-note').value.trim();
  await respondToCheckpoint({ checkpoint: 'review_feedback', review_note: note || null });
  updateStep('review_feedback', 'done');
  showIdlePanel();
}

// ── Final panel ────────────────────────────────────────────────────────────
function showFinalPanel(data, isLatest) {
  document.getElementById('final-text').value = data.final_doc || '';
  document.getElementById('final-text').readOnly = !isLatest;

  _setCheckpointNav('final', isLatest, 7);
  _setChatEnabled('final', isLatest);
  document.getElementById('panel-final').classList.remove('hidden');
  document.getElementById('final-submit-actions').classList.toggle('hidden', !isLatest);
}

async function submitFinal(saveChanges) {
  const doc = saveChanges ? document.getElementById('final-text').value.trim() : null;
  await respondToCheckpoint({ checkpoint: 'final', final_doc: doc });
  updateStep('review_final', 'done');
  showIdlePanel();
}

// ── Navigation button injection ────────────────────────────────────────────
function _setCheckpointNav(checkpoint, isLatest, checkpointNumber) {
  const navContainerId = `${checkpoint.replace('_', '-')}-nav`;
  const el = document.getElementById(navContainerId);
  if (!el) return;

  const isFirst = historyIndex === 0;
  el.innerHTML = `
    <button class="btn-ghost" onclick="goBack()" ${isFirst ? 'disabled' : ''}>← Back</button>
    ${!isLatest ? `<button class="btn-ghost" onclick="goForward()">Forward →</button>` : ''}
  `;
}

// ── Checkpoint response ────────────────────────────────────────────────────
async function respondToCheckpoint(body) {
  try {
    const res = await fetch(`/api/runs/${runId}/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
  } catch (err) {
    showError(`Failed to send response: ${err.message}`);
  }
}

// ── Results view ───────────────────────────────────────────────────────────
function showResults(data) {
  document.getElementById('tab-solution').innerHTML =
    `<div class="prose">${marked.parse(data.final_doc || '_No output generated._')}</div>`;

  document.getElementById('tab-decisions').innerHTML =
    `<div class="prose">${marked.parse(data.decisions_md || '_No decisions recorded._')}</div>`;

  document.getElementById('tab-risks').innerHTML =
    `<div class="prose">${marked.parse(data.risks_md || '_No risks recorded._')}</div>`;

  renderMermaid(data.mermaid_diagram);
  buildDownloadGrid(data);
  showView('results');

  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
    });
  });
}

async function renderMermaid(diagram) {
  if (!diagram) {
    document.getElementById('mermaid-container').textContent = 'No diagram generated.';
    return;
  }
  try {
    const { svg } = await window.mermaid.render('arch-diagram', diagram);
    document.getElementById('mermaid-container').innerHTML = svg;
  } catch (err) {
    const pre = document.createElement('pre');
    pre.textContent = diagram;
    pre.style.cssText = 'font-size:12px;text-align:left;';
    document.getElementById('mermaid-container').appendChild(pre);
  }
}

function buildDownloadGrid(data) {
  const files = [
    { name: 'solution_design.md',    desc: 'Full solution design document',   content: data.final_doc },
    { name: 'architecture.mmd',      desc: 'Mermaid architecture diagram',     content: data.mermaid_diagram },
    { name: 'options_considered.md', desc: 'Candidate approaches evaluated',   content: data.options_md },
    { name: 'decisions.md',          desc: 'Architecture decision records',    content: data.decisions_md },
    { name: 'risks.md',              desc: 'Risk register',                    content: data.risks_md },
    { name: 'business_brief.md',     desc: 'AI-generated business brief',      content: data.business_brief },
    { name: 'review_notes.md',       desc: 'Doc reviewer feedback',            content: data.review_feedback },
  ];

  const grid = document.getElementById('download-grid');
  grid.innerHTML = '';

  files.forEach(({ name, desc, content }) => {
    if (!content) return;
    const card = document.createElement('div');
    card.className = 'download-card';
    card.innerHTML = `
      <div class="file-name">${name}</div>
      <div class="file-desc">${desc}</div>
      <button class="btn-ghost" style="font-size:13px;padding:7px 14px;">Download</button>
    `;
    card.querySelector('button').addEventListener('click', () => downloadBlob(name, content));
    grid.appendChild(card);
  });
}

function downloadBlob(filename, text) {
  const blob = new Blob([text], { type: 'text/plain; charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Misc ───────────────────────────────────────────────────────────────────
function startOver() {
  if (eventSource) { eventSource.close(); eventSource = null; }
  runId = null; resultData = null; selectedApproach = null;
  checkpointHistory = []; historyIndex = -1;
  chatHistories = {}; approachesNotes = [];
  _currentDecisions = []; _currentRisks = [];
  document.getElementById('requirements').value = '';
  document.getElementById('clarification-area').classList.add('hidden');
  document.getElementById('questions-list').innerHTML = '';
  document.getElementById('btn-analyse').disabled = false;
  document.getElementById('btn-analyse').innerHTML =
    'Analyse requirements <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  showView('input');
}

function loadExample() {
  document.getElementById('requirements').value =
`We need to build an internal employee onboarding portal that integrates with our existing HR system (Workday), provisions accounts in Microsoft 365, and tracks completion of mandatory training modules. The system should support 500-1000 new hires per year, work across our offices in Australia and the UK, and integrate with our existing identity provider (Entra ID). Compliance requirements include data residency in-region (AU data stays in Australia, UK data stays in the UK) and audit logging of all account provisioning actions.

The onboarding process currently takes 3-5 days and involves manual steps across HR, IT, and the hiring manager. The goal is to reduce this to same-day provisioning for standard roles. The portal should give new hires a single place to complete their onboarding checklist, and give managers visibility into where each new hire is in the process.

We have an existing IT service desk running ServiceNow, and any provisioning failures should automatically raise a ticket. The engineering team is small (3 engineers) and strongly prefers managed services over self-hosted infrastructure. We have an existing Azure tenancy and would prefer to stay within that ecosystem where possible.`;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
