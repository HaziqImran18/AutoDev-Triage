import os
import sys
import time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from typing import Optional
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from pydantic import BaseModel, Field, ValidationError, field_validator
from utils.render import split_sections

load_dotenv()
app = Flask(__name__, template_folder=os.path.join(ROOT, "templates"),
            static_folder=os.path.join(ROOT, "static"))


class TriageRequest(BaseModel):
    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
    issue_number: int = Field(gt=0)
    post_to_github: bool = False
    post_to_slack: bool = False
    github_token: Optional[str] = Field(None, max_length=255)

    @field_validator("github_token")
    @classmethod
    def blank_to_none(cls, v):
        return (v or "").strip() or None


def _run(req: TriageRequest):
    from agents.workflow import run_triage  # lazy import keeps cold start light
    return run_triage(**req.model_dump())


def _scrub(text: str, token: Optional[str]) -> str:
    return text.replace(token, "***") if token else text


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/triage")
def triage_form():
    f = request.form
    try:
        req = TriageRequest(
            repo=f.get("repo", "").strip(), issue_number=f.get("issue_number", ""),
            post_to_github="post_to_github" in f, post_to_slack="post_to_slack" in f,
            github_token=f.get("github_token"))
    except ValidationError:
        return render_template("index.html", repo=f.get("repo", ""), issue=f.get("issue_number", ""),
                               error="Enter a repo as owner/name and a positive issue number."), 400
    t0 = time.time()
    try:
        state = _run(req)
    except Exception as e:  # never leak the token in an error page
        return render_template("index.html", repo=req.repo, issue=req.issue_number,
                               error=_scrub(f"{type(e).__name__}: {e}", req.github_token)), 500
    return render_template("report.html", s=state, sections=split_sections(state.rca_report),
                           secs=round(time.time() - t0))


@app.post("/api/triage")
def triage_api():
    try:
        req = TriageRequest.model_validate(request.get_json(force=True))
    except ValidationError as e:
        return jsonify(error=e.errors(include_url=False, include_context=False)), 422
    return jsonify(_run(req).model_dump())  # github_token is excluded from model_dump


@app.get("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
