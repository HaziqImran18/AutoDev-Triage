from evals.dataset import ISSUES, ORIGINAL, HELDOUT
from evals import metrics


def test_dataset_integrity():
    ids = [i["id"] for i in ISSUES]
    assert len(ids) == len(set(ids)) == 17 and len(ORIGINAL) == 12 and len(HELDOUT) == 5
    for i in ISSUES:
        assert {"id", "type", "labels", "title", "body", "root_cause", "fix", "keywords"} <= i.keys()
        assert i["type"] in ("bug", "insufficient_info")
        if i["type"] == "bug":
            assert i["keywords"] and ("Traceback" in i["body"] or "    at " in i["body"])
    assert sum(i["type"] == "insufficient_info" for i in ORIGINAL) == 2


def test_keyword_recall_with_alternatives():
    rep = "numpy 1.24 removed np.float; use float64"
    assert metrics.keyword_recall(rep, ["1.24", "removed|deprecated", "float64|builtin"]) == 1.0
    assert metrics.keyword_recall("nothing", ["abc"]) == 0.0
    assert metrics.keyword_recall("x", []) is None


def test_hallucinated_urls():
    rep = "see https://good.com/a and (https://fake.io/x)."
    assert metrics.hallucinated_urls(rep, {"https://good.com/a"}) == ["https://fake.io/x"]
    assert metrics.hallucinated_urls("no links", set()) == []


def test_cost():
    assert round(metrics.cost_usd(1_000_000, 1_000_000), 2) == round(metrics.PRICE_IN + metrics.PRICE_OUT, 2)


def test_summarize():
    base = dict(type="bug", fix_ok=True, invented=False, kw_recall=1.0, bad_urls=[], latency=2.0, cost=0.001, error=False)
    rows = [dict(system="a", correct=True, **base), dict(system="a", correct=False, **base),
            dict(system="b", correct=True, **{**base, "bad_urls": ["u"]})]
    s = metrics.summarize(rows)
    assert s["a"]["root_cause_correct"] == 0.5 and s["b"]["reports_with_bad_urls"] == 1.0


def test_regrade_urls_keeps_only_truly_ungrounded():
    body = "code: requests.get(f'https://a.com/x/{id}')"
    assert metrics.regrade_urls(["https://a.com/x/{id}", "https://evil.io/p"], body) == ["https://evil.io/p"]