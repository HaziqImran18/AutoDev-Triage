import json
from agents.state import TriageState, Findings, Source
from agents import llm

SYSTEM = """You are the Researcher agent. Use web_search_tool to find known fixes, patches or
changelog entries for the bug. If a library is involved use fetch_package_metadata_tool to check the
latest version / deprecation. Run at most 2 searches, then stop."""


def researcher_node(state: TriageState) -> dict:
    d = state.diagnosis
    attempt = state.research_attempts + 1
    # self-correction: on retry, broaden the query
    query = d.search_query if attempt == 1 else f"{d.library_involved or ''} {d.error_type or ''} fix"
    prompt = (f"Problem: {d.summary}\nLibrary: {d.library_involved} ({d.ecosystem})\n"
              f"Suggested query: {query}")
    try:
        msgs, trace = llm.run_tool_loop(
            SYSTEM, prompt, ["web_search_tool", "fetch_package_metadata_tool"], max_iters=4)
        sources, pkg = list(state.findings.sources), state.findings.package_info
        for m in msgs:
            if m.get("role") != "tool":
                continue
            r = json.loads(m["content"])
            for x in r.get("results", []):
                sources.append(Source(**x))
            if "latest_version" in r:
                pkg = r
        notes = msgs[-1].get("content") or ""
        return {"findings": Findings(sources=sources, package_info=pkg, notes=notes),
                "research_attempts": attempt,
                "trace": state.trace + [f"researcher#{attempt}: " + ", ".join(trace)]}
    except Exception as e:
        return {"research_attempts": attempt,
                "errors": state.errors + [f"researcher: {type(e).__name__}: {e}"]}
