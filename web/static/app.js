// ── State ─────────────────────────────────────────────────────────────────
let runId = null;
let eventSource = null;
let resultData = null;
let selectedApproach = null;

// All steps in pipeline order (agent steps + HITL checkpoints)
const STEPS = [
  { key: 'business_analyst',  label: 'Business Analyst',          type: 'agent' },
  { key: 'review_brief',      label: 'Review: Business Brief',    type: 'hitl'  },
  { key: 'solutioning',       label: 'Solutioning',               type: 'agent' },
  { key: 'review_approaches', label: 'Review: Approaches',        type: 'hitl'  },
  { key: 'architect',         label: 'Architect',                 type: 'agent' },
  { key: 'risk_reviewer',     label: 'Risk Reviewer',             type: 'agent' },
  { key: 'doc_writer',        label: 'Doc Writer',                type: 'agent' },
  { key: 'doc_reviewer',      label: 'Doc Reviewer',              type: 'agent' },
  { key: 'editor',            label: 'Editor',                    type: 'agent' },
];

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

// ── Start run ──────────────────────────────────────────────────────────────
async function startRun() {
  const requirements = document.getElementById('requirements').value.trim();
  if (!requirements) {
    showError('Please enter your business requirements before generating.');
    return;
  }

  const btn = document.getElementById('btn-submit');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Starting…';

  try {
    const res = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirements }),
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const { run_id } = await res.json();
    runId = run_id;
  } catch (err) {
    showError(`Failed to start run: ${err.message}`);
    btn.disabled = false;
    btn.innerHTML = 'Generate architecture <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    return;
  }

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
    // Only show error if we haven't already completed
    if (runId && !resultData) showError('Connection to server lost. The pipeline may still be running — refresh to check.');
  };
}

function handleProgress(data) {
  updateStep(data.step, data.status, data.elapsed_s);
}

function handleCheckpoint(data) {
  if (data.checkpoint === 'brief') {
    updateStep('review_brief', 'waiting');
    showBriefPanel(data.business_brief);
  } else if (data.checkpoint === 'approaches') {
    updateStep('review_approaches', 'waiting');
    showApproachesPanel(data.candidate_approaches);
  }
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

// ── Panel helpers ──────────────────────────────────────────────────────────
function showIdlePanel() {
  document.getElementById('panel-idle').classList.remove('hidden');
  document.getElementById('panel-brief').classList.add('hidden');
  document.getElementById('panel-approaches').classList.add('hidden');
}

function showBriefPanel(brief) {
  document.getElementById('panel-idle').classList.add('hidden');
  document.getElementById('brief-text').value = brief || '';
  document.getElementById('panel-brief').classList.remove('hidden');
}

function showApproachesPanel(approaches) {
  document.getElementById('panel-idle').classList.add('hidden');
  selectedApproach = null;
  const list = document.getElementById('approaches-list');
  list.innerHTML = '';

  approaches.forEach(a => {
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
    card.addEventListener('click', () => {
      list.querySelectorAll('.approach-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      selectedApproach = a.name;
    });
    list.appendChild(card);
  });

  document.getElementById('panel-approaches').classList.remove('hidden');
}

// ── Checkpoint responses ───────────────────────────────────────────────────
async function approveBrief(saveChanges) {
  const brief = saveChanges ? document.getElementById('brief-text').value.trim() : null;
  await respondToCheckpoint({ checkpoint: 'brief', business_brief: brief });
  updateStep('review_brief', 'done');
  document.getElementById('panel-brief').classList.add('hidden');
  showIdlePanel();
}

async function submitSelectedApproach() {
  if (!selectedApproach) {
    showError('Please select an approach first, or click "Let architect decide".');
    return;
  }
  await submitApproach(selectedApproach);
}

async function submitApproach(name) {
  await respondToCheckpoint({ checkpoint: 'approaches', selected_approach: name });
  updateStep('review_approaches', 'done');
  document.getElementById('panel-approaches').classList.add('hidden');
  showIdlePanel();
}

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
  // Populate tabs
  document.getElementById('tab-solution').innerHTML =
    `<div class="prose">${marked.parse(data.final_doc || '_No output generated._')}</div>`;

  document.getElementById('tab-decisions').innerHTML =
    `<div class="prose">${marked.parse(data.decisions_md || '_No decisions recorded._')}</div>`;

  document.getElementById('tab-risks').innerHTML =
    `<div class="prose">${marked.parse(data.risks_md || '_No risks recorded._')}</div>`;

  // Mermaid diagram
  renderMermaid(data.mermaid_diagram);

  // Downloads
  buildDownloadGrid(data);

  showView('results');

  // Wire up tabs
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
    // Fallback: show raw source
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
      <button class="btn-ghost" style="font-size:13px;padding:7px 14px;" onclick="downloadFile('${name}', this)">
        Download
      </button>
    `;
    card._content = content;
    card.querySelector('button').addEventListener('click', () => {
      downloadBlob(name, content);
    });
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
  document.getElementById('requirements').value = '';
  document.getElementById('btn-submit').disabled = false;
  document.getElementById('btn-submit').innerHTML =
    'Generate architecture <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
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
