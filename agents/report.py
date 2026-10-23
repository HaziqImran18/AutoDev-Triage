"""Deterministic report composer. No LLM: it can only restate verified/labelled claims and ledger evidence,
so the Integrator cannot introduce new claims or URLs."""
import re
from agents import guard
from agents.evidence import allowed_urls

BANNER = {
    "VERIFIED": "every claim below is supported by the cited evidence (this does not guarantee the diagnosis is complete).",
    "PARTIALLY_VERIFIED": "the root cause is backed by cited evidence; items marked ⚠️ are NOT verified against retrieved evidence.",
    "UNVERIFIED": "no root cause could be confirmed against retrieved evidence. Anything marked ⚠️ is an unverified hypothesis.",
    "INSUFFICIENT_EVIDENCE": "the issue does not contain enough evidence to diagnose; no root cause is claimed.",
}
KIND = {
    "feature_request": "reads as a feature request, not a failure",
    "question": "reads as a question rather than a failure report",
    "bug": "describes a problem but gives no error message or stack trace",
    "unclear": "contains no error message, stack trace or other concrete failure evidence",
}
DEFAULT_MISSING = ["The exact error message or full stack trace", "Steps to reproduce",
                   "Environment (OS, runtime and library versions)", "Expected vs. actual behaviour"]


def _line(s: str, n: int) -> str:
    return re.sub(r"\s+", " ", s).strip()[:n]


def _clean(s: str) -> str:
    return _line(s, 90).replace("[", "(").replace("]", ")")


def render(state, ledger) -> tuple[str, list[str]]:
    by_id = {e.id: e for e in ledger}
    verdict = state.verdict or "UNVERIFIED"
    iss = state.issue or {}
    title = iss.get("title") or f"{state.repo}#{state.issue_number}"
    kind = state.diagnosis.issue_type if state.diagnosis else "unclear"
    shown = [c for c in state.claims if c.status != "REJECTED"]
    rc = [c for c in shown if c.role == "root_cause"]
    fx = [c for c in shown if c.role == "fix"]
    ctx = [c for c in shown if c.role == "context"]
    abstain = verdict == "INSUFFICIENT_EVIDENCE"

    def fmt(c):
        if c.status == "GROUNDED":
            return f"- {c.text} `[{', '.join(c.evidence_ids)}]`"
        return f"- ⚠️ **Unverified:** {c.text} _({c.reason})_"

    out = ["## Summary", f"**Status: {verdict}** - {BANNER[verdict]}", "", f"**Issue:** {title}"]
    if abstain:
        out.append(f"\nThis issue {KIND.get(kind, KIND['unclear'])}.")
    out += [fmt(c) for c in ctx]

    out += ["", "## Likely Root Cause"]
    if abstain:
        out.append("_Not determined. No root cause is claimed because the issue lacks failure evidence._")
    elif rc:
        out += [fmt(c) for c in rc]
    else:
        out.append("_No root cause could be confirmed from the retrieved evidence._")

    cited = []
    for c in shown:
        if c.status == "GROUNDED":
            for i in c.evidence_ids:
                if i in by_id and by_id[i].kind != "trace" and i not in cited:
                    cited.append(i)
    out += ["", "## Evidence"]
    if abstain:
        out.append("_The issue text contains no stack trace or exception message to analyse._")
    else:
        if "T1" in by_id:
            out.append("Stack frames parsed from the issue `[T1]`:\n\n```text\n"
                       + "\n".join(by_id["T1"].text.splitlines()[:8]) + "\n```")
        for i in cited:
            e = by_id[i]
            if e.kind == "source":
                head, _, snip = e.text.partition("\n")
                out.append(f"- `[{i}]` [{_clean(head)}]({e.url}) - {_line(snip, 220)}")
            elif e.kind == "issue":
                out.append(f"- `[{i}]` The issue text itself" + (f" ([{state.repo}#{state.issue_number}]({e.url}))" if e.url else ""))
            elif e.kind == "package":
                out.append(f"- `[{i}]` Package registry metadata")
        if "T1" not in by_id and not cited:
            out.append("_No evidence entries back any claim._")

    out += ["", "## Suggested Fix"]
    if fx:
        out += [fmt(c) for c in fx]
    elif abstain:
        out.append("_None proposed. To enable a real diagnosis please add:_")
    else:
        out.append("_No fix could be verified._")
    wanted = (state.missing_info or DEFAULT_MISSING) if (abstain or not fx) else []
    if wanted:
        out += ([] if abstain else ["", "_What would help:_"]) + [f"- {m}" for m in wanted]

    refs = []
    if iss.get("url"):
        refs.append(f"- [{state.repo}#{state.issue_number}]({iss['url']})")
    for i in cited:
        e = by_id[i]
        if e.kind == "source" and e.url:
            refs.append(f"- [{_clean(e.text.split(chr(10))[0])}]({e.url})")
    out += ["", "## References"] + (refs or ["_None._"])

    return guard.sanitize_urls("\n".join(out), allowed_urls(ledger))  # final URL safety net