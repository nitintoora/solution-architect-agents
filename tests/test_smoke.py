"""
Smoke test: runs the full pipeline with mocked Claude calls and verifies
that all expected output files are produced. Does not hit the Anthropic API.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.state import ArchitectureState
from src.graph import build_graph
from src.utils.output_writer import write_outputs

# ---------------------------------------------------------------------------
# Mock responses — one per agent call, in pipeline order
# ---------------------------------------------------------------------------

_MOCK_BUSINESS_BRIEF = """## Problem statement

The organisation needs an automated employee onboarding portal.

## Stakeholders

- HR team: manages new hire data in Workday
- IT team: responsible for account provisioning

## Success criteria

- New hire accounts provisioned within 4 hours of start date

## Constraints

- Must integrate with Workday and Entra ID
- Data residency: AU data in Australia, UK data in UK

## Assumptions

- Azure tenancy already exists

## Out of scope

- Contractor onboarding
"""

_MOCK_APPROACHES = json.dumps([
    {
        "name": "Azure-native managed services",
        "summary": "Use Azure Logic Apps and managed connectors to orchestrate provisioning.",
        "key_components": ["Azure Logic Apps", "Microsoft Graph API", "Entra ID"],
        "tradeoffs": "Low operational overhead but limited customisation.",
        "suitability_score": 8,
    },
    {
        "name": "Custom microservices on AKS",
        "summary": "Build bespoke provisioning services deployed on Azure Kubernetes Service.",
        "key_components": ["AKS", "Azure Service Bus", "Custom provisioning service"],
        "tradeoffs": "Full control but high operational complexity for a 3-person team.",
        "suitability_score": 5,
    },
])

_MOCK_ARCHITECT_RESPONSE = """
<CHOSEN_APPROACH>
Azure-native managed services
</CHOSEN_APPROACH>

<CHOSEN_APPROACH_REASONING>
The Azure-native approach best fits the team's size and preference for managed services.
The custom microservices option was rejected due to operational overhead.
</CHOSEN_APPROACH_REASONING>

<ARCHITECTURE>
The solution uses Azure Logic Apps to orchestrate the onboarding workflow.
When Workday triggers a new hire event, Logic Apps provisions the M365 account via
Microsoft Graph API and updates Entra ID. A static web app serves the onboarding portal.
</ARCHITECTURE>

<MERMAID>
flowchart TD
    A[Workday] -->|New hire event| B[Azure Logic Apps]
    B --> C[Microsoft Graph API]
    C --> D[Entra ID]
    B --> E[Onboarding Portal]
    B -->|On failure| F[ServiceNow]
</MERMAID>

<DECISIONS>
```json
[
  {
    "title": "Use Azure Logic Apps for orchestration",
    "context": "Small team prefers managed services over self-hosted infrastructure",
    "decision": "Azure Logic Apps with managed connectors",
    "reasoning": "Reduces operational burden; native connectors for M365 and Workday exist",
    "alternatives_considered": ["Azure Functions", "Custom AKS microservices"]
  }
]
```
</DECISIONS>
"""

_MOCK_RISKS = json.dumps([
    {
        "description": "Workday webhook delivery failure causing missed new hire events",
        "likelihood": "medium",
        "impact": "high",
        "mitigation": "Implement idempotent polling fallback every 15 minutes as a safety net",
    },
    {
        "description": "Data residency misconfiguration routing AU data through UK region",
        "likelihood": "low",
        "impact": "high",
        "mitigation": "Enforce region locks via Azure Policy; include region assertions in automated tests",
    },
])

_MOCK_DRAFT_DOC = """## Context and drivers

The organisation is replacing a manual onboarding process that takes 3-5 days.

## Current state

Manual process involving HR, IT, and hiring managers with no central tracking.

## Options considered

| Option | Summary | Suitability | Selected? |
|--------|---------|-------------|-----------|
| Azure-native | Logic Apps orchestration | 8/10 | Yes |
| Custom AKS | Bespoke microservices | 5/10 | No |

## Proposed architecture

The solution uses Azure Logic Apps.

```mermaid
flowchart TD
    A[Workday] --> B[Azure Logic Apps]
```

## Key decisions

**Use Azure Logic Apps for orchestration**
- **Context:** Small team
- **Decision:** Logic Apps
- **Reasoning:** Managed service
- **Alternatives considered:** Azure Functions

## Risks and mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R1 | Workday webhook failure | Medium | High | Polling fallback |

## Assumptions

- Azure tenancy exists

## Out of scope

- Contractor onboarding
"""

_MOCK_REVIEW_FEEDBACK = """### Summary

The draft is broadly sound with good structure.

### Issues found

**Issue 1: Missing data residency details**
- **Location:** Section 4: Proposed architecture
- **Problem:** Data residency constraints are not addressed in the architecture section
- **Suggestion:** Add a paragraph describing how AU/UK data separation is enforced

### What is working well

- Options table is clear and well-structured
- Risk section is appropriately concise
"""

_MOCK_FINAL_DOC = """## Context and drivers

The organisation is replacing a manual onboarding process that takes 3-5 days.
All architecture decisions account for the AU/UK data residency requirements.

## Current state

Manual process involving HR, IT, and hiring managers with no central tracking.

## Options considered

| Option | Summary | Suitability | Selected? |
|--------|---------|-------------|-----------|
| Azure-native | Logic Apps orchestration | 8/10 | Yes |
| Custom AKS | Bespoke microservices | 5/10 | No |

## Proposed architecture

The solution uses Azure Logic Apps deployed in region-specific Azure subscriptions
to enforce data residency. AU resources are deployed to australiaeast; UK resources
to uksouth.

```mermaid
flowchart TD
    A[Workday] --> B[Azure Logic Apps]
```

## Key decisions

**Use Azure Logic Apps for orchestration**
- **Context:** Small team
- **Decision:** Logic Apps
- **Reasoning:** Managed service
- **Alternatives considered:** Azure Functions

## Risks and mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R1 | Workday webhook failure | Medium | High | Polling fallback |

## Assumptions

- Azure tenancy exists

## Out of scope

- Contractor onboarding
"""

_MOCK_RESPONSES = [
    _MOCK_BUSINESS_BRIEF,
    f"```json\n{_MOCK_APPROACHES}\n```",
    _MOCK_ARCHITECT_RESPONSE,
    f"```json\n{_MOCK_RISKS}\n```",
    _MOCK_DRAFT_DOC,
    _MOCK_REVIEW_FEEDBACK,
    _MOCK_FINAL_DOC,
]

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

EXPECTED_FILES = [
    "business_brief.md",
    "options_considered.md",
    "solution_design.md",
    "architecture.mmd",
    "decisions.md",
    "risks.md",
    "review_notes.md",
]


def _make_mock_call_claude():
    responses = iter(_MOCK_RESPONSES)

    def mock_call(system_prompt: str, user_message: str, **kwargs) -> str:
        return next(responses)

    return mock_call


def test_full_pipeline_produces_all_output_files():
    """Full pipeline smoke test with mocked Claude calls."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("src.llm.call_claude", side_effect=_make_mock_call_claude()):
            graph = build_graph()
            initial_state = ArchitectureState(
                requirements_input="Build an employee onboarding portal."
            )
            final_state = graph.invoke(initial_state)

        write_outputs(final_state, tmp_dir)

        for filename in EXPECTED_FILES:
            path = Path(tmp_dir) / filename
            assert path.exists(), f"Expected output file not found: {filename}"
            assert path.stat().st_size > 0, f"Output file is empty: {filename}"


def test_full_pipeline_state_is_fully_populated():
    """Verify all state fields are populated after the pipeline runs."""
    with patch("src.llm.call_claude", side_effect=_make_mock_call_claude()):
        graph = build_graph()
        initial_state = ArchitectureState(
            requirements_input="Build an employee onboarding portal."
        )
        final_state = graph.invoke(initial_state)

    assert final_state["business_brief"] is not None
    assert len(final_state["candidate_approaches"]) == 2
    assert final_state["chosen_approach"] == "Azure-native managed services"
    assert final_state["mermaid_diagram"] is not None
    assert len(final_state["decisions"]) == 1
    assert len(final_state["risks"]) == 2
    assert final_state["draft_doc"] is not None
    assert final_state["review_feedback"] is not None
    assert final_state["final_doc"] is not None
    # HITL fields are absent/None in non-interactive mode
    assert final_state.get("human_brief_feedback") is None
    assert final_state.get("human_selected_approach") is None
