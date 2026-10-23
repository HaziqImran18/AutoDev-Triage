import json
from api.index import app
from agents import tools
from agents.state import TriageState, Diagnosis, Findings, Source
from utils.render import strip_fence, split_sections

RPT = "```markdown\n## Summary\nhello\n\n## Suggested Fix\n- upgrade\n```"


def full_state(**kw):
    return TriageState(
        repo="o/r", issue_number=3, rca_report=strip_fence(RPT), trace=["diagnoser: x"], research_attempts=1,
        issue={"title": "Boom", "url": "https://github.com/o/r/issues/3", "state": "open", "labels": ["bug"]},
        diagnosis=Diagnosis(summary="s", error_type="KeyError", search_query="q"),
        findings=Findings(sources=[Source(title="T", url="https://x.com/a", snippet="snip")]), **kw)


def test_render_helpers():
    assert strip_fence(RPT).startswith("## Summary")
    secs = split_sections(strip_fence(RPT))
    assert [s["title"] for s in secs] == ["Summary", "Suggested Fix"] and secs[1]["icon"] == "🛠️"


def test_index_has_token_field_and_spinner():
    h = app.test_client().get("/").data
    assert b'type="password"' in h and b'id="overlay"' in h


def test_report_page_renders(monkeypatch):
    monkeypatch.setattr("agents.workflow.run_triage", lambda **k: full_state())
    r = app.test_client().post("/triage", data={"repo": "o/r", "issue_number": "3"})
    assert r.status_code == 200 and b"Boom" in r.data and b"Suggested Fix" in r.data and b"Sources found" in r.data


def test_token_never_returned_or_echoed(monkeypatch):
    monkeypatch.setattr("agents.workflow.run_triage", lambda **k: full_state(github_token=k["github_token"]))
    c = app.test_client()
    r = c.post("/api/triage", json={"repo": "o/r", "issue_number": 3, "github_token": "ghp_SECRET"})
    assert b"ghp_SECRET" not in r.data
    r = c.post("/triage", data={"repo": "o/r", "issue_number": "3", "github_token": "ghp_SECRET"})
    assert b"ghp_SECRET" not in r.data


def test_token_is_plumbed_to_github_client(monkeypatch):
    seen = {}
    monkeypatch.setattr(tools.github_client, "get_issue", lambda r, n, token=None: seen.update(t=token) or {})
    tools.execute("get_github_issue_tool", '{"repo":"a/b","issue_number":1}', ["get_github_issue_tool"], {"github_token": "tkn"})
    assert seen["t"] == "tkn"
