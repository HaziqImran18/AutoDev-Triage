"""LLM-as-judge. The judge never sees which system wrote the report (blind evaluation)."""
import json
import os
from pydantic import BaseModel, Field
from agents import llm

JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "gpt-4o")  # stronger than the 4o-mini systems under test

_RULES = """You are a strict evaluator of root-cause-analysis (RCA) reports for GitHub issues.
You get the GROUND TRUTH and a REPORT. Judge ONLY against the ground truth.
- root_cause_correct: the report identifies the same underlying cause (wording may differ).
  If expected_type is 'insufficient_info': true ONLY if the report clearly says the evidence is
  insufficient / it is a feature request / no root cause can be determined, AND it does not assert
  a specific bug cause as fact.
- fix_reasonable: the suggested fix matches or is equivalent to the ground-truth fix
  (for insufficient_info: it asks for / recommends gathering specifics instead of guessing)."""

SYSTEM = _RULES + """
- invented_facts: the report asserts concrete facts that appear in NONE of: the issue text (title+body),
  the retrieved_evidence, or the ground truth (made-up versions, error messages, changelog entries, links).
Be strict: vague, partial or hedged-wrong answers are false."""

# the ORIGINAL judge: it only saw the issue TITLE, so facts from the issue body were easy to mis-flag
SYSTEM_LEGACY = _RULES + """
- invented_facts: the report asserts concrete facts unsupported by the issue (made-up versions,
  error messages, changelog entries, links).
Be strict: vague, partial or hedged-wrong answers are false."""


class Verdict(BaseModel):
    root_cause_correct: bool
    fix_reasonable: bool
    invented_facts: bool
    reasoning: str = Field(description="1-2 sentences")


def judge(item: dict, report: str, evidence: list[str] | None = None, legacy: bool = False) -> Verdict:
    if not report.strip():
        return Verdict(root_cause_correct=False, fix_reasonable=False, invented_facts=False,
                       reasoning="empty report")
    payload = {"expected_type": item["type"], "ground_truth_root_cause": item["root_cause"],
               "ground_truth_fix": item["fix"], "issue_title": item["title"], "REPORT": report}
    if not legacy:
        payload["issue_body"] = item["body"]
        payload["retrieved_evidence"] = (evidence or [])[:12]
    r = llm.client().beta.chat.completions.parse(
        model=JUDGE_MODEL, temperature=0, response_format=Verdict,
        messages=[{"role": "system", "content": SYSTEM_LEGACY if legacy else SYSTEM},
                  {"role": "user", "content": json.dumps(payload)}])
    return r.choices[0].message.parsed  # judge tokens are NOT tracked: they are not system cost