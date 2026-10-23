import json
from agents.state import TriageState, Diagnosis
from agents import llm

SYSTEM = """You are the Diagnoser agent. Call get_github_issue_tool to fetch the issue,
then parse_stacktrace_tool on any logs/traces in it. Then stop calling tools and say you are done."""


def diagnoser_node(state: TriageState) -> dict:
    try:
        msgs, trace = llm.run_tool_loop(
            SYSTEM, f"Repo: {state.repo}\nIssue number: {state.issue_number}",
            ["get_github_issue_tool", "parse_stacktrace_tool"], ctx={"github_token": state.github_token})
        issue, frames, tool_err = None, [], None
        for m in msgs:
            if m.get("role") == "tool":
                d = json.loads(m["content"])
                if "title" in d and "body" in d:
                    issue = d
                if "frames" in d:
                    frames = d["frames"]
                if "tool_error" in d or "validation_error" in d:
                    tool_err = d.get("tool_error") or str(d.get("validation_error"))
        if issue is None:  # never diagnose an error message as if it were the bug
            return {"errors": state.errors + [
                f"diagnoser: could not fetch {state.repo}#{state.issue_number}: {tool_err or 'no issue returned'}"],
                "trace": state.trace + ["diagnoser: " + ", ".join(trace)]}
        msgs.append({"role": "user", "content":
                     "Produce the structured diagnosis now. search_query should be a concise web query."})
        diagnosis = llm.structured(msgs, Diagnosis)
        return {"issue": issue, "stack_frames": frames, "diagnosis": diagnosis,
                "trace": state.trace + ["diagnoser: " + ", ".join(trace)]}
    except Exception as e:
        return {"errors": state.errors + [f"diagnoser: {type(e).__name__}: {e}"]}
