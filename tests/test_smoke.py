import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents import tools, workflow, llm
from agents.state import Diagnosis

TRACE = '''Traceback (most recent call last):
  File "app/main.py", line 42, in handler
    x = data["k"]
KeyError: 'k'
'''

def test_stacktrace_parser():
    r = tools.parse_stacktrace_tool(tools.ParseStacktraceArgs(text=TRACE))
    assert r["has_stacktrace"] and r["frames"][0].startswith("app/main.py:42")

def test_pydantic_blocks_bad_tool_args():
    out = json.loads(tools.execute("get_github_issue_tool", '{"repo":"bad repo","issue_number":-1}',
                                   ["get_github_issue_tool"]))
    assert "validation_error" in out

def test_tool_allowlist():
    out = json.loads(tools.execute("slack_alert_tool", '{"text":"x"}', ["web_search_tool"]))
    assert "error" in out

def test_graph_retries_then_reports(monkeypatch):
    calls = {"research": 0}
    def fake_loop(system, *a, **k):
        if "Researcher" in system:
            calls["research"] += 1
            return ([{"role": "assistant", "content": "none"}], [])
        return ([{"role": "tool", "content": json.dumps({"title": "T", "body": TRACE, "url": "u"})}], ["get_issue"])
    monkeypatch.setattr(llm, "run_tool_loop", fake_loop)
    monkeypatch.setattr(llm, "structured", lambda m, s: Diagnosis(
        summary="s", library_involved="requests", ecosystem="pypi", search_query="q"))
    class R:  # fake OpenAI response
        choices = [type("C", (), {"message": type("M", (), {"content": "## Summary\nok"})()})()]
    fake = type("F", (), {"chat": type("Ch", (), {"completions": type("Co", (), {
        "create": staticmethod(lambda **k: R)})()})()})()
    monkeypatch.setattr(llm, "client", lambda: fake)
    s = workflow.run_triage("o/r", 1, mode="legacy")
    assert calls["research"] == 2          # cyclic retry fired
    assert s.rca_report.startswith("## Summary")