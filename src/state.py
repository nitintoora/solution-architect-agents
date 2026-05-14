from typing import Optional
from pydantic import BaseModel, Field


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

    # Human-in-the-loop fields (populated only when --interactive is used)
    human_brief_feedback: Optional[str] = None
    human_selected_approach: Optional[str] = None
    human_architect_feedback: Optional[str] = None
    human_risk_feedback: Optional[str] = None
    human_review_note: Optional[str] = None
