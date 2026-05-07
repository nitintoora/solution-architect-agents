from pathlib import Path
from src.state import ArchitectureState


def write_outputs(state: ArchitectureState | dict, output_dir: str | Path) -> None:
    """Write all agent outputs to individual files in output_dir."""
    if isinstance(state, dict):
        state = ArchitectureState(**state)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    _write(out / "business_brief.md", state.business_brief)
    _write(out / "options_considered.md", _render_options(state))
    _write(out / "solution_design.md", state.final_doc)
    _write(out / "architecture.mmd", state.mermaid_diagram)
    _write(out / "decisions.md", _render_decisions(state))
    _write(out / "risks.md", _render_risks(state))
    _write(out / "review_notes.md", state.review_feedback)


# --- renderers ----------------------------------------------------------------

def _render_options(state: ArchitectureState) -> str:
    if not state.candidate_approaches:
        return "_No candidate approaches recorded._"

    lines = ["# Options Considered\n"]
    for i, approach in enumerate(state.candidate_approaches, start=1):
        lines.append(f"## Option {i}: {approach.name}\n")
        lines.append(f"{approach.summary}\n")
        lines.append("**Key components:**\n")
        for component in approach.key_components:
            lines.append(f"- {component}")
        lines.append(f"\n**Tradeoffs:** {approach.tradeoffs}\n")
        lines.append(f"**Suitability score:** {approach.suitability_score}/10\n")
        lines.append("---\n")
    return "\n".join(lines)


def _render_decisions(state: ArchitectureState) -> str:
    if not state.decisions:
        return "_No decisions recorded._"

    lines = ["# Architecture Decision Records\n"]
    for i, d in enumerate(state.decisions, start=1):
        adr_id = f"ADR-{i:03d}"
        lines.append(f"## {adr_id}: {d.title}\n")
        lines.append(f"**Context:** {d.context}\n")
        lines.append(f"**Decision:** {d.decision}\n")
        lines.append(f"**Reasoning:** {d.reasoning}\n")
        alternatives = ", ".join(d.alternatives_considered) if d.alternatives_considered else "None"
        lines.append(f"**Alternatives considered:** {alternatives}\n")
        lines.append("---\n")
    return "\n".join(lines)


def _render_risks(state: ArchitectureState) -> str:
    if not state.risks:
        return "_No risks recorded._"

    lines = [
        "# Risk Register\n",
        "| ID | Risk | Likelihood | Impact | Mitigation |",
        "|----|------|------------|--------|------------|",
    ]
    for i, risk in enumerate(state.risks, start=1):
        likelihood = risk.likelihood.capitalize()
        impact = risk.impact.capitalize()
        mitigation = risk.mitigation.replace("|", "\\|")
        description = risk.description.replace("|", "\\|")
        lines.append(f"| R{i} | {description} | {likelihood} | {impact} | {mitigation} |")
    return "\n".join(lines)


# --- helper -------------------------------------------------------------------

def _write(path: Path, content: str | None) -> None:
    if content is None:
        return
    path.write_text(content, encoding="utf-8")
