import json
import pytest
from agents import workflow, llm, guard
from agents.evidence import has_error_signal
from agents.state import Diagnosis, Proposal, Claim, Entailments, Entailment, ClaimResult
from evals.dataset import ISSUES
from evals import metrics

TRACE = 'Traceback (most recent call last):\n  File "app.py", line 6, in f\nAttributeError: module \'numpy\' has no attribute \'float\''
BUG = {"title": "np.float AttributeError", "body": TRACE, "url": "https://github.com/o/r/issues/3",
       "state": "open", "labels": ["bug"], "comments": []}
FEATURE = {"title": "Add retry logic", "body": "It would be nice if fetch_user retried 3 times.",
           "url": "https://github.com/o/r/issues/9", "state": "open", "labels": [], "comments": []}
SRC = [{"title": "NumPy 1.24 release notes", "url": "https://numpy.org/doc/1.24/release",
        "snippet": "np.float was removed in NumPy 1.24; use float or np.float64."}]


def mock(monkeypatch, issue, proposal=None, entail=None, sources=None, itype="bug", fail_proposal=False):
    calls = {"research": 0, "proposal": 0, "entail": 0}

    def loop(system, *a, **k):
        if "Researcher" in system:
            calls["research"] += 1
            return ([{"role": "tool", "content": json.dumps({"results": sources or []})},
                     {"role": "assistant", "content": "notes"}], [])
        msgs = [{"role": "tool", "content": json.dumps(issue)}]
        if "Traceback" in issue["body"]:
            msgs.append({"role": "tool", "content": json.dumps({"frames": ["app.py:6 in f"], "error": "x"})})
        return (msgs, [])

    def structured(msgs, schema):
        if schema is Diagnosis:
            return Diagnosis(summary="s", search_query="q", issue_type=itype)
        if schema is Proposal:
            calls["proposal"] += 1
            if fail_proposal:
                raise RuntimeError("boom")
            return proposal
        if schema is Entailments:
            calls["entail"] += 1
            return entail
    monkeypatch.setattr(llm, "run_tool_loop", loop)
    monkeypatch.setattr(llm, "structured", structured)
    return calls


# ---------- gate ----------
def test_gate_on_every_benchmark_issue():
    for it in ISSUES:
        expected = it["type"] == "bug" or it["id"] == "heldout-connection-reset"
        assert has_error_signal({"title": it["title"], "body": it["body"]}, []) == expected, it["id"]


@pytest.mark.parametrize("body,sig", [
    ("Error [ERR_REQUIRE_ESM]: require() of ES Module", True), ("KeyError: 'x'", True),
    ("at Object.<anonymous> (/app/server.js:2:15)", True), ("Improve error messages please", False), ("", False)])
def test_has_error_signal(body, sig):
    assert has_error_signal({"title": "t", "body": body}, []) is sig


# ---------- guards ----------
def test_sanitize_urls():
    ok = {"https://good.com/a"}
    txt, rem = guard.sanitize_urls("see https://good.com/a, [x](https://evil.io/p) and https://evil.io/q.", ok)
    assert "good.com/a" in txt and "evil.io" not in txt and len(rem) == 2


def test_lexical_grounding():
    assert guard.lexically_grounded("np.float was removed in NumPy 1.24", ["np.float removed NumPy 1.24"])[0]
    ok, missing = guard.lexically_grounded("pin `numpy==1.23`", ["np.float removed"])
    assert not ok and missing


def test_verdict_logic():
    mk = lambda role, st: ClaimResult(text="t", role=role, status=st)
    assert guard.decide_verdict([mk("root_cause", "GROUNDED"), mk("fix", "GROUNDED")]) == "VERIFIED"
    assert guard.decide_verdict([mk("root_cause", "GROUNDED"), mk("fix", "UNVERIFIED")]) == "PARTIALLY_VERIFIED"
    assert guard.decide_verdict([mk("root_cause", "UNVERIFIED")]) == "UNVERIFIED"
    assert guard.decide_verdict([]) == "UNVERIFIED"


# ---------- end-to-end (mocked LLM) ----------
def test_control_issue_abstains_without_research_or_verifier(monkeypatch):
    calls = mock(monkeypatch, FEATURE, itype="feature_request")
    s = workflow.run_triage("o/r", 9)
    assert s.verdict == "INSUFFICIENT_EVIDENCE" and calls["research"] == 0 and calls["proposal"] == 0
    assert "INSUFFICIENT_EVIDENCE" in s.rca_report and "feature request" in s.rca_report
    assert "## Likely Root Cause" in s.rca_report and not s.errors


def test_grounded_report_has_only_grounded_urls_and_labels_unverified(monkeypatch):
    prop = Proposal(claims=[
        Claim(text="np.float was removed in NumPy 1.24", role="root_cause", evidence_ids=["S1"]),
        Claim(text="Pin `numpy==1.23`", role="fix", evidence_ids=["S1"]),
        Claim(text="Docs at https://evil.example/x confirm this", role="context", evidence_ids=["E1"]),
        Claim(text="Use the other thing", role="fix", evidence_ids=["S9"]),
        Claim(text="np.float is a new function", role="root_cause", evidence_ids=["S1"]),
    ])
    ent = Entailments(items=[Entailment(i=0, verdict="supported", supporting_ids=["S1"]), Entailment(i=1, verdict="supported", supporting_ids=["S1"]),
                             Entailment(i=2, verdict="supported", supporting_ids=["E1"]), Entailment(i=4, verdict="contradicted")])
    mock(monkeypatch, BUG, prop, ent, SRC)
    s = workflow.run_triage("o/r", 3)
    assert s.verdict == "PARTIALLY_VERIFIED"
    assert "evil.example" not in s.rca_report and "np.float is a new function" not in s.rca_report
    assert "⚠️" in s.rca_report and "numpy.org/doc/1.24/release" in s.rca_report
    allowed = {BUG["url"], SRC[0]["url"]}
    assert metrics.hallucinated_urls(s.rca_report, allowed) == []
    assert {c.status for c in s.claims} == {"GROUNDED", "UNVERIFIED", "REJECTED"}


def test_no_root_cause_claim_gives_unverified(monkeypatch):
    mock(monkeypatch, BUG, Proposal(claims=[], missing_info=["server logs"]), Entailments(items=[]), SRC)
    s = workflow.run_triage("o/r", 3)
    assert s.verdict == "UNVERIFIED" and "server logs" in s.rca_report and "No root cause could be confirmed" in s.rca_report


def test_verifier_failure_never_yields_confident_report(monkeypatch):
    mock(monkeypatch, BUG, sources=SRC, fail_proposal=True)
    s = workflow.run_triage("o/r", 3)
    assert s.verdict == "UNVERIFIED" and any("verifier" in e for e in s.errors) and s.rca_report


def test_abstain_path_still_posts_with_request_token(monkeypatch):
    mock(monkeypatch, FEATURE, itype="feature_request")
    seen = {}
    monkeypatch.setattr("agents.tools.github_client.post_comment",
                        lambda repo, n, body, token=None: seen.update(t=token, b=body) or "https://github.com/o/r/issues/9#c1")
    s = workflow.run_triage("o/r", 9, post_to_github=True, github_token="tkn")
    assert s.github_comment_url and seen["t"] == "tkn" and "INSUFFICIENT_EVIDENCE" in seen["b"]


SRC2 = SRC + [{"title": "Pydantic validation", "url": "https://docs.pydantic.dev/x",
               "snippet": "ValidationError is raised for bad input."}]


def test_citations_pruned_to_entries_that_actually_support(monkeypatch):
    prop = Proposal(claims=[Claim(text="np.float was removed in NumPy 1.24", role="root_cause", evidence_ids=["S1", "S2"])])
    ent = Entailments(items=[Entailment(i=0, verdict="supported", supporting_ids=["S1"])])
    mock(monkeypatch, BUG, prop, ent, SRC2)
    s = workflow.run_triage("o/r", 3)
    assert s.claims[0].evidence_ids == ["S1"] and "docs.pydantic.dev" not in s.rca_report


def test_supported_without_a_confirmed_entry_is_unverified(monkeypatch):
    prop = Proposal(claims=[Claim(text="np.float was removed in NumPy 1.24", role="root_cause", evidence_ids=["S1"])])
    ent = Entailments(items=[Entailment(i=0, verdict="supported", supporting_ids=[])])
    mock(monkeypatch, BUG, prop, ent, SRC)
    s = workflow.run_triage("o/r", 3)
    assert s.claims[0].status == "UNVERIFIED" and s.verdict == "UNVERIFIED"


def test_urls_written_in_the_issue_text_are_allowed(monkeypatch):
    issue = {**BUG, "body": TRACE + "\nCalled https://api.example.com/users/1 and it failed"}
    prop = Proposal(claims=[Claim(text="The request to https://api.example.com/users/1 raised the error",
                                  role="context", evidence_ids=["E1"])])
    ent = Entailments(items=[Entailment(i=0, verdict="supported", supporting_ids=["E1"])])
    mock(monkeypatch, issue, prop, ent, SRC)
    s = workflow.run_triage("o/r", 3)
    assert "https://api.example.com/users/1" in s.rca_report