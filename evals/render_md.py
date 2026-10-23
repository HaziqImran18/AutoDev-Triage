"""Builds the markdown comparison report from result rows (shared by run_eval.py and make_report.py)."""
from evals import metrics

_P = lambda x: f"{x * 100:.0f}%"
METRIC_ROWS = [
    ("Root cause correct (all)", "root_cause_correct", _P),
    ("  - on real bugs", "bug_issues_correct", _P),
    ("  - on control issues (honesty)", "control_issues_correct", _P),
    ("Fix reasonable", "fix_reasonable", _P),
    ("Invented facts (lower=better)", "invented_facts", _P),
    ("Keyword recall (bugs)", "keyword_recall", _P),
    ("Reports with ungrounded URLs (lower=better)", "reports_with_bad_urls", _P),
    ("Real bugs answered UNVERIFIED / INSUFFICIENT (cost of honesty)", "bug_abstained", _P),
    ("Claims grounded in evidence", "claim_grounding", _P),
    ("Run errors", "run_errors", _P),
    ("Avg latency", "avg_latency_s", lambda x: f"{x:.1f}s"),
    ("Avg cost / issue", "avg_cost_usd", lambda x: f"${x:.4f}"),
]


def _unique(seq):
    out = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


def build_markdown(rows: list[dict], repo: str, split: str, stamp: str, judge_model: str,
                   legacy_judge: bool = False) -> str:
    systems = _unique(r["system"] for r in rows)
    ids = _unique(r["id"] for r in rows)
    summary = metrics.summarize(rows)
    has_verdict = any(r.get("verdict") for r in rows)

    md = ["# Evaluation: single LLM vs 3-agent pipeline", "",
          f"Repo `{repo}` - split `{split}` - {len(ids)} issues - {stamp} - judge `{judge_model}`"
          + (" (LEGACY title-only judge)" if legacy_judge else ""), "",
          "| Metric | " + " | ".join(systems) + " |", "|---|" + "---|" * len(systems)]
    for label, key, fmt in METRIC_ROWS:
        cells = [fmt(summary[s][key]) if summary[s][key] is not None else "-" for s in systems]
        md.append(f"| {label} | " + " | ".join(cells) + " |")

    if has_verdict:
        md += ["", "## Verdicts"]
        for s in systems:
            if summary[s]["verdicts"]:
                md.append(f"- **{s}**: " + ", ".join(f"{k} x{v}" for k, v in summary[s]["verdicts"].items()))

    md += ["", "## Per issue (root cause correct)", "",
           "| Issue | " + " | ".join(systems) + (" | verdict |" if has_verdict else " |"),
           "|---|" + "---|" * (len(systems) + (1 if has_verdict else 0))]
    for i in ids:
        rs = {r["system"]: r for r in rows if r["id"] == i}
        cells = ["✅" if rs.get(s, {}).get("correct") else "❌" for s in systems]
        if has_verdict:
            cells.append(next((r["verdict"] for r in rs.values() if r.get("verdict")), "-"))
        md.append(f"| {i} | " + " | ".join(cells) + " |")

    md += ["", f"_n = {len(ids)} issues: differences of 1-2 issues are within noise. Cost = OpenAI tokens only "
               "(judge and Tavily excluded). URLs written in the issue text itself count as grounded._"]
    return "\n".join(md)