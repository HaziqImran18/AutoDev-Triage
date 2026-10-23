import pytest
from api.index import app
from agents.state import TriageState


@pytest.fixture
def client():
    return app.test_client()


def fake_state(**kw):
    return TriageState(repo="o/r", issue_number=1, rca_report="## Summary\nok",
                       trace=["diagnoser: x"], **kw)


def test_health_and_home(client):
    assert client.get("/health").json == {"status": "ok"}
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("payload", [
    {"repo": "x", "issue_number": 1}, {"repo": "a/b", "issue_number": 0}, {"repo": "a/b"}, {}])
def test_api_rejects_bad_input(client, payload):
    assert client.post("/api/triage", json=payload).status_code == 422


def test_api_happy_path(client, monkeypatch):
    monkeypatch.setattr("agents.workflow.run_triage", lambda **k: fake_state())
    r = client.post("/api/triage", json={"repo": "a/b", "issue_number": 5})
    assert r.status_code == 200 and r.json["rca_report"].startswith("## Summary")


def test_form_happy_path(client, monkeypatch):
    monkeypatch.setattr("agents.workflow.run_triage", lambda **k: fake_state())
    r = client.post("/triage", data={"repo": "a/b", "issue_number": "5"})
    assert r.status_code == 200 and b"Summary" in r.data


def test_form_bad_input_shows_error(client):
    r = client.post("/triage", data={"repo": "nope", "issue_number": "5"})
    assert r.status_code == 400 and b"owner/name" in r.data


def test_flags_passed_through(client, monkeypatch):
    seen = {}
    monkeypatch.setattr("agents.workflow.run_triage", lambda **k: seen.update(k) or fake_state())
    client.post("/triage", data={"repo": "a/b", "issue_number": "5", "post_to_slack": "on"})
    assert seen["post_to_slack"] is True and seen["post_to_github"] is False
