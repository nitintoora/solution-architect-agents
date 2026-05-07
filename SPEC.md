# Solution Architecture Multi-Agent System — Build Spec

## Project overview

A multi-agent system built with LangGraph that takes business requirements as input and produces a complete solution architecture deliverable: brief, architecture document, Mermaid diagram, decisions, risks, and review notes.

The system runs locally. Users clone the repo, set their Anthropic API key, drop their requirements into an input file, and run a single command.

This is open source. Code quality, README quality, and prompt quality all matter — people will read all of it.

## Goals and non-goals

**Goals**
- Linear multi-agent flow with 7 specialised agents
- Markdown-first output, designed to be human-readable
- Mermaid diagrams generated as text (renders in GitHub/markdown viewers)
- Prompts stored as separate `.md` files so contributors can tune them without editing Python
- README-driven, with a working example input/output committed to the repo
- Minimal dependencies, easy to clone and run

**Non-goals (defer to v2)**
- Human-in-the-loop checkpoints
- Loops or conditional branching
- Multi-provider LLM support (Anthropic only for v1)
- Web UI
- RAG over org-specific patterns
- PDF/Word export
- Requirements validation agent (future feature)

## Tech stack

- Python 3.11+
- LangGraph (latest stable)
- Anthropic Python SDK (`anthropic` package)
- `python-dotenv` for API key management
- `pydantic` for state validation
- No web framework, no database, no vector store

Use `uv` for dependency management if available, otherwise standard `pip` + `requirements.txt`.

## Repository structure

```
solution-architect-agents/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── main.py                       # CLI entry point
├── src/
│   ├── __init__.py
│   ├── graph.py                  # LangGraph definition
│   ├── state.py                  # State schema (Pydantic/TypedDict)
│   ├── llm.py                    # Claude client wrapper
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── business_analyst.py
│   │   ├── solutioning.py
│   │   ├── architect.py
│   │   ├── risk_reviewer.py
│   │   ├── doc_writer.py
│   │   ├── doc_reviewer.py
│   │   └── editor.py
│   ├── prompts/
│   │   ├── business_analyst.md
│   │   ├── solutioning.md
│   │   ├── architect.md
│   │   ├── risk_reviewer.md
│   │   ├── doc_writer.md
│   │   ├── doc_reviewer.md
│   │   └── editor.md
│   └── utils/
│       ├── __init__.py
│       ├── output_writer.py      # Writes folder output
│       └── prompt_loader.py      # Loads prompts from .md files
├── examples/
│   ├── sample_input.md
│   └── sample_output/
│       ├── business_brief.md
│       ├── options_considered.md
│       ├── solution_design.md
│       ├── architecture.mmd
│       ├── decisions.md
│       ├── risks.md
│       └── review_notes.md
└── tests/
    └── test_smoke.py             # One end-to-end smoke test
```

## Agent flow

Linear, no branching, no loops:

```
START
  ↓
business_analyst    → produces business_brief
  ↓
solutioning         → produces 2-3 candidate approaches with tradeoffs
  ↓
architect           → picks an approach, produces architecture + Mermaid + decisions
  ↓
risk_reviewer       → produces risk register
  ↓
doc_writer          → produces full draft solution design doc
  ↓
doc_reviewer        → produces review feedback
  ↓
editor              → produces final polished doc, applying review feedback
  ↓
END (output_writer writes everything to /output)
```

## State schema

Use Pydantic for validation. Single state object passed through the graph:

```python
from pydantic import BaseModel, Field
from typing import Optional

class CandidateApproach(BaseModel):
    name: str
    summary: str
    key_components: list[str]
    tradeoffs: str
    suitability_score: int  # 1-10

class Risk(BaseModel):
    description: str
    likelihood: str  # "low" | "medium" | "high"
    impact: str      # "low" | "medium" | "high"
    mitigation: str

class Decision(BaseModel):
    title: str
    context: str
    decision: str
    reasoning: str
    alternatives_considered: list[str]

class ArchitectureState(BaseModel):
    # Input
    requirements_input: str
    
    # Agent outputs
    business_brief: Optional[str] = None
    candidate_approaches: list[CandidateApproach] = Field(default_factory=list)
    chosen_approach: Optional[str] = None
    chosen_approach_reasoning: Optional[str] = None
    architecture: Optional[str] = None
    mermaid_diagram: Optional[str] = None
    decisions: list[Decision] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    draft_doc: Optional[str] = None
    review_feedback: Optional[str] = None
    final_doc: Optional[str] = None
```

## Agent specifications

Each agent is a Python function that takes the state, calls Claude with the agent's prompt and relevant state context, parses the response, and returns updated state.

### Common pattern

```python
from src.llm import call_claude
from src.utils.prompt_loader import load_prompt

def business_analyst(state: ArchitectureState) -> ArchitectureState:
    system_prompt = load_prompt("business_analyst")
    user_message = f"Business requirements:\n\n{state.requirements_input}"
    response = call_claude(system_prompt, user_message)
    state.business_brief = response
    return state
```

The LLM client (`src/llm.py`) should be a thin wrapper around the Anthropic SDK that handles retries, model selection, and returns clean text. Use `claude-opus-4-7` as the default model.

### Agent 1: business_analyst

**Input from state:** `requirements_input`
**Output to state:** `business_brief` (markdown string)

Produces a structured business brief with:
- Problem statement
- Stakeholders
- Success criteria
- Constraints
- Assumptions
- Out of scope (initial cut)

### Agent 2: solutioning

**Input from state:** `business_brief`
**Output to state:** `candidate_approaches` (list of 2-3 CandidateApproach)

Generates 2-3 genuinely distinct architectural approaches. Must avoid trivial variations. Each approach has tradeoffs explicitly written out. Output should be parseable as structured data — ask Claude for JSON wrapped in a code fence, then parse.

### Agent 3: architect

**Input from state:** `business_brief`, `candidate_approaches`
**Output to state:** `chosen_approach`, `chosen_approach_reasoning`, `architecture`, `mermaid_diagram`, `decisions`

Picks one approach (or synthesises across them), justifies why others were rejected, produces detailed architecture description, generates a Mermaid diagram as text, and lists key decisions with reasoning.

The Mermaid diagram should use `flowchart TD` or `graph LR` syntax. Keep it readable — under 20 nodes for v1.

### Agent 4: risk_reviewer

**Input from state:** `business_brief`, `architecture`
**Output to state:** `risks` (list of Risk)

Identifies 5-10 risks with likelihood, impact, and mitigation. Structured output, parsed as JSON.

### Agent 5: doc_writer

**Input from state:** everything produced so far
**Output to state:** `draft_doc` (full markdown document)

Produces a complete draft solution design document with sections:
- Context and drivers
- Current state (if applicable, otherwise note as N/A)
- Options considered (summary, with full version in separate file)
- Proposed architecture (with Mermaid embedded)
- Key decisions
- Risks and mitigations
- Assumptions
- Out of scope

No introduction. No conclusion. No executive summary. The doc should be ready to be opened in any markdown viewer.

### Agent 6: doc_reviewer

**Input from state:** `business_brief`, `draft_doc`
**Output to state:** `review_feedback` (markdown string)

Critiques the draft. Looks for:
- Gaps (something promised in the brief but missing in the doc)
- Unclear sections
- Weak reasoning
- Inconsistencies between sections
- Missing context

Does NOT rewrite. Only critiques. Output is structured feedback the editor can act on.

### Agent 7: editor

**Input from state:** `draft_doc`, `review_feedback`
**Output to state:** `final_doc`

Applies the reviewer's feedback to produce the final polished document. This is what gets written to disk as `solution_design.md`.

## Prompt files

Each prompt lives in `src/prompts/<agent_name>.md`. Loaded at runtime by the prompt_loader. This means contributors can tune prompts without editing Python.

Each prompt file should contain:
- Role definition
- Specific output format requirements (especially for agents that need structured output)
- Constraints (what NOT to do)
- Tone/style guidance

Example prompt structure for `business_analyst.md`:

```markdown
# Business Analyst Agent

You are an experienced business analyst working with a solution architect.
Your job is to take raw business requirements and produce a clean, structured
business brief that the architect can use to design a solution.

## Output format

Produce a markdown document with these sections, in this order:

1. **Problem statement** — 2-3 sentences, plain language
2. **Stakeholders** — bulleted list with one-line role description for each
3. **Success criteria** — measurable outcomes, bulleted
4. **Constraints** — technical, business, regulatory; bulleted
5. **Assumptions** — what you're inferring from the requirements; bulleted
6. **Out of scope** — explicit; bulleted

## Constraints

- No introduction or preamble
- No conclusion
- No "executive summary"
- If a section has no content, write "None identified" rather than skipping it
- Do not invent stakeholders or success criteria not implied by the input
- Flag ambiguities with `[NEEDS CLARIFICATION: ...]` rather than guessing
```

Use the same structural pattern for each agent's prompt file. Specificity here determines output quality more than any other factor.

## Output writer

`src/utils/output_writer.py` takes the final state and writes:

```
output/
├── business_brief.md
├── options_considered.md
├── solution_design.md       ← the main file (final_doc)
├── architecture.mmd          ← standalone Mermaid source
├── decisions.md              ← ADR-style format
├── risks.md                  ← risk register table
└── review_notes.md           ← the doc_reviewer's feedback (transparency)
```

The `decisions.md` file should be formatted as a series of ADRs:

```markdown
# Architecture Decision Records

## ADR-001: <Decision title>

**Context:** ...
**Decision:** ...
**Reasoning:** ...
**Alternatives considered:** ...

---

## ADR-002: ...
```

The `risks.md` file should be a markdown table:

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R1 | ... | High | Medium | ... |

## CLI (main.py)

Single command:

```bash
python main.py --input path/to/requirements.md --output ./output
```

Defaults:
- `--input`: `examples/sample_input.md`
- `--output`: `./output`

Should print progress as each agent completes:

```
[1/7] Business analyst... done (3.2s)
[2/7] Solutioning... done (4.1s)
[3/7] Architect... done (6.8s)
...
✓ Complete. Output written to ./output/
```

This progress feedback matters — without it, users staring at a silent terminal will assume it's broken.

## Sample input

`examples/sample_input.md` should be a realistic mid-sized requirement. Something like:

> We need to build an internal employee onboarding portal that integrates with our existing HR system (Workday), provisions accounts in Microsoft 365, and tracks completion of mandatory training modules. The system should support 500-1000 new hires per year, work across our offices in Australia and the UK, and integrate with our existing identity provider (Entra ID). Compliance requirements include data residency in-region and audit logging of all account provisioning actions.

This gives all the agents enough to work with and produces interesting output users can actually look at.

## Sample output

Critical: ship `examples/sample_output/` with a complete, real, run output committed to the repo. People will judge the project on this folder before they install anything. Do not skip this step or commit a placeholder.

## README requirements

The README is the single most important file for adoption. Structure:

1. **One-line description** at the top
2. **Demo GIF or short video** (record once it works, before publishing)
3. **What this is** — 2-3 sentences
4. **Quick start** — clone, install, set API key, run, four commands max
5. **Example output** — link to `examples/sample_output/`
6. **How it works** — Mermaid diagram of the agent flow
7. **Customising prompts** — explain that prompts live in `src/prompts/` and how to modify
8. **Limitations** — be honest. List what v1 doesn't do.
9. **Roadmap** — short list of what's planned for v2 (requirements validation agent, multi-provider, human-in-the-loop)
10. **Contributing** — how to add agents, modify prompts, submit PRs
11. **License** — MIT

## .env.example

```
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-opus-4-7
```

## .gitignore essentials

```
.env
__pycache__/
*.pyc
output/
.venv/
.pytest_cache/
```

Note: `output/` is gitignored because it's user-generated. The `examples/sample_output/` is committed because it's part of the repo.

## Testing

One smoke test in `tests/test_smoke.py` that runs the full pipeline with a tiny input and checks that all expected files are produced. Mock the Claude calls so it doesn't burn API credits in CI.

Don't over-test. This is an open source project where the value is the prompts and the flow, not test coverage.

## Build order recommendation

For Claude Code to build efficiently, suggest building in this order:

1. Repo skeleton (folders, empty files, pyproject.toml, .gitignore, .env.example)
2. State schema (`src/state.py`)
3. LLM wrapper (`src/llm.py`) — get a single call to Claude working
4. Prompt loader utility
5. Output writer utility
6. One agent end-to-end (start with business_analyst — simplest)
7. Wire that one agent into a minimal LangGraph and verify it runs
8. Add remaining agents one at a time, each with its prompt file
9. Sample input
10. Run the full pipeline and capture sample output, commit it
11. Smoke test
12. README (write last, when you know what actually works)

## Final notes for the builder

- Prompt quality matters more than code quality. Spend time on the prompts.
- Resist scope creep. Every "while we're at it..." should be added to the v2 roadmap, not built.
- Commit `examples/sample_output/` with real output. This is non-negotiable.
- The README should make someone want to clone the repo within 30 seconds of landing on it. If it doesn't, it needs another pass.
