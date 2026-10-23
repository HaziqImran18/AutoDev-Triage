import json
from agents.state import TriageState
from agents import llm, tools
from agents import report as rpt
from agents.evidence import build_ledger
from utils.render import strip_fence

SYSTEM = """You are the Integrator agent. Write a concise Root Cause Analysis in GitHub Markdown with
sections: ## Summary, ## Likely Root Cause, ## Evidence, ## Suggested Fix, ## References.
Output raw Markdown only - never wrap it in code fences. Only cite URLs from the provided sources. If evidence is weak, say so — do not invent facts."""


def _publish(state: TriageState, report: str, label: str) -> dict:
    """Deterministic side-effects, gated by explicit user flags (never left to the LLM)."""
    out, errors = {}, list(state.errors)
    ctx = {"github_token": state.github_token}
    if state.post_to_github:
        res = json.loads(tools.execute("github_comment_tool", json.dumps(
            {"repo": state.repo, "issue_number": state.issue_number, "body": report}),
            ["github_comment_tool"], ctx))
        out["github_comment_url"] = res.get("url")
        if "url" not in res:
            errors.append(f"github comment failed: {res}")
    if state.post_to_slack:
        title = (state.issue or {}).get("title", "")
        res = json.loads(tools.execute("slack_alert_tool", json.dumps(
            {"text": f"*{label}* for {state.repo}#{state.issue_number}: {title}"}), ["slack_alert_tool"]))
        out["slack_sent"] = bool(res.get("ok"))
    if errors != state.errors:
        out["errors"] = errors
    return out


def integrator_node(state: TriageState) -> dict:
    """Grounded integrator: composes the report ONLY from verified/labelled claims and ledger evidence."""
    try:
        st = state if state.verdict else state.model_copy(update={"verdict": "UNVERIFIED"})
        report, removed = rpt.render(st, build_ledger(st))
        note = f" ({len(removed)} ungrounded link(s) removed)" if removed else ""
        out = {"verdict": st.verdict, "rca_report": report,
               "trace": state.trace + [f"integrator: rendered {st.verdict} report from claims{note}"]}
        out.update(_publish(st, report, f"RCA {st.verdict}"))
        return out
    except Exception as e:
        return {"errors": state.errors + [f"integrator: {type(e).__name__}: {e}"]}


def abstain_node(state: TriageState) -> dict:
    """Issue has no failure evidence: say so honestly instead of forcing a diagnosis."""
    try:
        kind = state.diagnosis.issue_type if state.diagnosis else "unclear"
        st = state.model_copy(update={"verdict": "INSUFFICIENT_EVIDENCE", "claims": [],
                                      "missing_info": rpt.DEFAULT_MISSING})
        report, _ = rpt.render(st, build_ledger(st))
        out = {"verdict": "INSUFFICIENT_EVIDENCE", "claims": [], "missing_info": rpt.DEFAULT_MISSING,
               "rca_report": report,
               "trace": state.trace + [f"abstain: no error signal in issue (type={kind}); research skipped"]}
        out.update(_publish(st, report, "Needs more info"))
        return out
    except Exception as e:
        return {"errors": state.errors + [f"abstain: {type(e).__name__}: {e}"]}


# ---- legacy (v1) free-form integrator, kept ONLY so evals can compare before/after ----
def legacy_integrator_node(state: TriageState) -> dict:
    ctx = {
        "issue": state.issue, "diagnosis": state.diagnosis.model_dump() if state.diagnosis else None,
        "stack_frames": state.stack_frames,
        "sources": [s.model_dump() for s in state.findings.sources[:8]],
        "package_info": state.findings.package_info, "research_notes": state.findings.notes,
    }
    out = {"trace": state.trace + ["integrator: writing RCA"]}
    try:
        r = llm.client().chat.completions.create(
            model=llm.MODEL, temperature=0.2,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": json.dumps(ctx, default=str)[:20000]}])
        llm.track(r)
        report = strip_fence(r.choices[0].message.content)
        out["rca_report"] = report
        # Side-effects are deterministic and gated by explicit user flags (not left to the LLM)
        if state.post_to_github:
            res = json.loads(tools.execute("github_comment_tool", json.dumps(
                {"repo": state.repo, "issue_number": state.issue_number, "body": report}),
                ["github_comment_tool"], {"github_token": state.github_token}))
            out["github_comment_url"] = res.get("url")
            if "url" not in res:
                out["errors"] = state.errors + [f"github comment failed: {res}"]
        if state.post_to_slack:
            title = (state.issue or {}).get("title", "")
            res = json.loads(tools.execute("slack_alert_tool", json.dumps(
                {"text": f"*RCA ready* for {state.repo}#{state.issue_number}: {title}"}),
                ["slack_alert_tool"]))
            out["slack_sent"] = bool(res.get("ok"))
    except Exception as e:
        out["errors"] = state.errors + [f"integrator: {type(e).__name__}: {e}"]
    return out