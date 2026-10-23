from typing import Literal, Optional
from pydantic import BaseModel, Field


class Diagnosis(BaseModel):
    summary: str = Field(description="One-paragraph summary of the problem")
    error_type: Optional[str] = Field(None, description="e.g. TypeError, timeout, race condition")
    suspected_component: Optional[str] = None
    library_involved: Optional[str] = Field(None, description="Main package name if any")
    ecosystem: Optional[str] = Field(None, description="'pypi' or 'npm' if a package is involved")
    issue_type: Literal["bug", "feature_request", "question", "unclear"] = Field(
        "unclear", description="'bug' only if the issue reports a concrete failure; otherwise feature_request, question or unclear")
    search_query: str = Field(description="Best web search query to find a fix")


class Source(BaseModel):
    title: str
    url: str
    snippet: str = ""


class Findings(BaseModel):
    sources: list[Source] = []
    package_info: Optional[dict] = None
    notes: str = ""


# ---- verification layer ----
class Claim(BaseModel):
    """One atomic statement proposed by the Verifier, tied to evidence ids."""
    text: str
    role: Literal["root_cause", "fix", "context"]
    evidence_ids: list[str] = []
    basis: Literal["evidence", "knowledge"] = "evidence"


class Proposal(BaseModel):
    claims: list[Claim]
    missing_info: list[str] = []


class Entailment(BaseModel):
    i: int
    verdict: Literal["supported", "not_supported", "contradicted"]
    supporting_ids: list[str] = []  # ONLY the cited ids that themselves support the claim
    reason: str = ""


class Entailments(BaseModel):
    items: list[Entailment]


class ClaimResult(BaseModel):
    text: str
    role: str
    evidence_ids: list[str] = []
    status: Literal["GROUNDED", "UNVERIFIED", "REJECTED"]
    reason: str = ""


class TriageState(BaseModel):
    # inputs
    repo: str
    issue_number: int
    post_to_github: bool = False
    post_to_slack: bool = False
    github_token: Optional[str] = Field(default=None, exclude=True)  # per-request, never serialized
    # working memory
    issue: Optional[dict] = None
    stack_frames: list[str] = []
    diagnosis: Optional[Diagnosis] = None
    findings: Findings = Findings()
    research_attempts: int = 0
    # verification outputs (grounded mode)
    verdict: Optional[str] = None  # VERIFIED | PARTIALLY_VERIFIED | UNVERIFIED | INSUFFICIENT_EVIDENCE
    claims: list[ClaimResult] = []
    missing_info: list[str] = []
    # outputs
    rca_report: Optional[str] = None
    github_comment_url: Optional[str] = None
    slack_sent: bool = False
    errors: list[str] = []
    trace: list[str] = []