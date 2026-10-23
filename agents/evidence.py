"""Evidence ledger: every fact a report may rest on gets an id (E1 issue, T1 trace, S1.. sources, P1 package)."""
import json
import re
from typing import Optional
from pydantic import BaseModel


class Evidence(BaseModel):
    id: str
    kind: str  # issue | trace | source | package
    text: str
    url: Optional[str] = None


_SIGNALS = [re.compile(p) for p in (
    r"Traceback \(most recent call last\)",
    r"\b[\w.]*(?:Error|Exception)\s*[:\[(]",          # KeyError: / Error [ERR_X]: / HTTPError(
    r'File "[^"]+", line \d+',
    r"\bat\s+(?:[\w.<>$]+\s+)?\(?[^\s()]+:\d+:\d+\)?",  # JS stack frame
    r"\bERR_[A-Z_]+\b",
)]


def has_error_signal(issue: Optional[dict], frames: list[str]) -> bool:
    """Deterministic gate: does the issue contain ANY concrete failure evidence (trace / exception text)?
    If not, a root cause cannot be derived, so the pipeline abstains instead of guessing."""
    if frames:
        return True
    if not issue:
        return False
    text = f"{issue.get('title', '')}\n{issue.get('body', '')}"
    return any(p.search(text) for p in _SIGNALS)


def build_ledger(state) -> list[Evidence]:
    led: list[Evidence] = []
    iss = state.issue or {}
    if iss:
        body = (f"TITLE: {iss.get('title', '')}\nLABELS: {', '.join(iss.get('labels', []))}\n"
                f"BODY:\n{(iss.get('body') or '')[:3000]}")
        for c in (iss.get("comments") or [])[:2]:
            body += f"\nCOMMENT: {c[:500]}"
        led.append(Evidence(id="E1", kind="issue", text=body, url=iss.get("url")))
    if state.stack_frames:
        led.append(Evidence(id="T1", kind="trace", text="\n".join(state.stack_frames)))
    seen, n = set(), 0
    for s in state.findings.sources:
        if s.url in seen:
            continue
        seen.add(s.url)
        n += 1
        led.append(Evidence(id=f"S{n}", kind="source", text=f"{s.title}\n{s.snippet}", url=s.url))
    if state.findings.package_info:
        led.append(Evidence(id="P1", kind="package", text=json.dumps(state.findings.package_info, default=str)[:1500]))
    return led


_URL_RE = re.compile(r"https?://[^\s)>\]\"'`]+")


def allowed_urls(ledger: list[Evidence]) -> set[str]:
    """The ONLY URLs a report may contain: the issue link, URLs written in the issue text itself,
    and URLs returned by the search tool."""
    out = set()
    for e in ledger:
        if e.url:
            out.add(e.url)
        if e.kind == "issue":
            out |= {u.rstrip(".,;:") for u in _URL_RE.findall(e.text)}
    return out