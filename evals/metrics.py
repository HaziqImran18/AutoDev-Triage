import re

# USD per 1M tokens for gpt-4o-mini. VERIFY on OpenAI's pricing page and edit if it changed.
PRICE_IN, PRICE_OUT = 0.15, 0.60
_URL = re.compile(r"https?://[^\s)>\]\"'`]+")


def urls_in(text: str | None) -> set[str]:
    return {u.rstrip(".,;:") for u in _URL.findall(text or "")}


def hallucinated_urls(report: str, allowed: set[str]) -> list[str]:
    """URLs in the report that do not come from the issue or from retrieved sources."""
    ok = [a.rstrip("/") for a in allowed if a]
    bad = []
    for u in sorted(urls_in(report)):
        v = u.rstrip("/")
        if not any(v == a or v.startswith(a) or a.startswith(v) for a in ok):
            bad.append(u)
    return bad


def regrade_urls(bad_urls: list[str], issue_text: str) -> list[str]:
    """Drop 'ungrounded' URLs that actually appear in the issue text (e.g. a URL inside the user's own code)."""
    return hallucinated_urls("\n".join(bad_urls), urls_in(issue_text))


def keyword_recall(report: str, keywords: list[str]) -> float | None:
    if not keywords:
        return None
    text = (report or "").lower()
    hits = sum(any(alt.strip().lower() in text for alt in kw.split("|")) for kw in keywords)
    return round(hits / len(keywords), 3)


def cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * PRICE_IN + completion_tokens * PRICE_OUT) / 1_000_000


def _avg(xs):
    return round(sum(xs) / len(xs), 3) if xs else None


def _rate(rows, key):
    return round(sum(1 for r in rows if r[key]) / len(rows), 3) if rows else None


def summarize(rows: list[dict]) -> dict:
    """rows: one dict per (issue, system). Optional keys: verdict, n_claims, n_grounded (grounded pipeline only)."""
    out = {}
    for name in sorted({r["system"] for r in rows}):
        rs = [r for r in rows if r["system"] == name]
        bugs = [r for r in rs if r["type"] == "bug"]
        ctrl = [r for r in rs if r["type"] != "bug"]
        vs = [r["verdict"] for r in rs if r.get("verdict")]
        abst = [r for r in bugs if r.get("verdict") in ("UNVERIFIED", "INSUFFICIENT_EVIDENCE")]
        claims = sum(r.get("n_claims", 0) for r in rs)
        out[name] = {
            "n": len(rs),
            "root_cause_correct": _rate(rs, "correct"),
            "bug_issues_correct": _rate(bugs, "correct"),
            "control_issues_correct": _rate(ctrl, "correct"),
            "fix_reasonable": _rate(rs, "fix_ok"),
            "invented_facts": _rate(rs, "invented"),
            "keyword_recall": _avg([r["kw_recall"] for r in bugs if r["kw_recall"] is not None]),
            "reports_with_bad_urls": round(sum(1 for r in rs if r["bad_urls"]) / len(rs), 3),
            "bug_abstained": round(len(abst) / len(bugs), 3) if bugs and vs else None,
            "claim_grounding": round(sum(r.get("n_grounded", 0) for r in rs) / claims, 3) if claims else None,
            "verdicts": {v: vs.count(v) for v in sorted(set(vs))},
            "run_errors": _rate(rs, "error"),
            "avg_latency_s": _avg([r["latency"] for r in rs]),
            "avg_cost_usd": round(sum(r["cost"] for r in rs) / len(rs), 5),
        }
    return out