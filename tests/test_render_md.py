from evals import render_md


def row(sys_, id_, ok, verdict=None, **kw):
    base = dict(system=sys_, id=id_, type="bug", correct=ok, fix_ok=ok, invented=False, kw_recall=1.0,
                bad_urls=[], latency=2.0, cost=0.001, error=False, verdict=verdict, n_claims=2, n_grounded=1)
    return {**base, **kw}


def test_markdown_has_all_systems_verdicts_and_emoji(tmp_path):
    rows = [row("single_llm", "a", True), row("3_agent_v1", "a", False), row("3_agent_v2", "a", True, "VERIFIED"),
            row("single_llm", "c", False, type="insufficient_info"),
            row("3_agent_v2", "c", True, "INSUFFICIENT_EVIDENCE", type="insufficient_info")]
    md = render_md.build_markdown(rows, "o/r", "original", "stamp", "gpt-4o")
    assert "3_agent_v2" in md and "INSUFFICIENT_EVIDENCE" in md and "✅" in md and "❌" in md
    f = tmp_path / "latest.md"
    f.write_text(md, encoding="utf-8")          # the exact call that crashed on Windows without encoding=
    assert f.read_text(encoding="utf-8") == md


def test_old_runs_without_verdicts_still_render():
    rows = [row("single_llm", "a", True), row("3_agent", "a", True)]
    for r in rows:
        r.pop("verdict"); r.pop("n_claims"); r.pop("n_grounded")
    assert "3_agent" in render_md.build_markdown(rows, "o/r", "original", "s", "gpt-4o")