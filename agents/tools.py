"""Tool definitions: Pydantic arg models -> OpenAI schemas -> validated execution."""
import os
import re
import json
import httpx
from pydantic import BaseModel, Field, ValidationError
from utils import github_client


# ---------- argument schemas (runtime validation of LLM tool calls) ----------
class GetIssueArgs(BaseModel):
    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$", description="owner/name")
    issue_number: int = Field(gt=0)


class ParseStacktraceArgs(BaseModel):
    text: str = Field(description="Raw issue body or log containing a stack trace")


class WebSearchArgs(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    max_results: int = Field(5, ge=1, le=8)


class PackageMetaArgs(BaseModel):
    package: str = Field(pattern=r"^[@\w./-]+$")
    ecosystem: str = Field(pattern="^(pypi|npm)$")


class GithubCommentArgs(BaseModel):
    repo: str
    issue_number: int
    body: str = Field(min_length=1)


class SlackArgs(BaseModel):
    text: str = Field(min_length=1)


# ---------- implementations ----------
def get_github_issue_tool(a: GetIssueArgs, ctx: dict | None = None) -> dict:
    return github_client.get_issue(a.repo, a.issue_number, (ctx or {}).get("github_token"))


_PY_FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')
_JS_FRAME = re.compile(r"at (?:(\S+) )?\(?([^\s()]+):(\d+):(\d+)\)?")
_ERR_LINE = re.compile(r"^(\w+(?:\.\w+)*(?:Error|Exception))[:\s](.*)$", re.M)


def parse_stacktrace_tool(a: ParseStacktraceArgs, ctx: dict | None = None) -> dict:
    frames = [f"{f}:{l} in {fn}" for f, l, fn in _PY_FRAME.findall(a.text)]
    frames += [f"{f}:{l} in {fn or '<anon>'}" for fn, f, l, _ in _JS_FRAME.findall(a.text)]
    err = _ERR_LINE.search(a.text)
    return {
        "frames": frames[:15],
        "error": f"{err.group(1)}: {err.group(2).strip()}" if err else None,
        "has_stacktrace": bool(frames),
    }


def web_search_tool(a: WebSearchArgs, ctx: dict | None = None) -> dict:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return {"error": "TAVILY_API_KEY not set", "results": []}
    r = httpx.post("https://api.tavily.com/search", timeout=20,
                   headers={"Authorization": f"Bearer {key}"},
                   json={"query": a.query, "max_results": a.max_results})
    r.raise_for_status()
    return {"results": [{"title": x["title"], "url": x["url"], "snippet": x["content"][:400]}
                        for x in r.json().get("results", [])]}


def fetch_package_metadata_tool(a: PackageMetaArgs, ctx: dict | None = None) -> dict:
    url = (f"https://pypi.org/pypi/{a.package}/json" if a.ecosystem == "pypi"
           else f"https://registry.npmjs.org/{a.package}/latest")
    r = httpx.get(url, timeout=15)
    if r.status_code != 200:
        return {"error": f"{a.package} not found on {a.ecosystem}"}
    d = r.json()
    if a.ecosystem == "pypi":
        i = d["info"]
        return {"name": i["name"], "latest_version": i["version"], "summary": i["summary"],
                "requires_python": i.get("requires_python"), "home": i.get("project_urls")}
    return {"name": d["name"], "latest_version": d["version"], "description": d.get("description"),
            "deprecated": d.get("deprecated")}


def github_comment_tool(a: GithubCommentArgs, ctx: dict | None = None) -> dict:
    return {"url": github_client.post_comment(a.repo, a.issue_number, a.body, (ctx or {}).get("github_token"))}


def slack_alert_tool(a: SlackArgs, ctx: dict | None = None) -> dict:
    hook = os.getenv("SLACK_WEBHOOK_URL")
    if not hook:
        return {"error": "SLACK_WEBHOOK_URL not set"}
    r = httpx.post(hook, json={"text": a.text}, timeout=10)
    return {"ok": r.status_code == 200}


# ---------- registry + OpenAI plumbing ----------
REGISTRY = {
    "get_github_issue_tool": (GetIssueArgs, get_github_issue_tool, "Fetch a GitHub issue (title, body, labels, comments)."),
    "parse_stacktrace_tool": (ParseStacktraceArgs, parse_stacktrace_tool, "Extract frames and error line from a stack trace."),
    "web_search_tool": (WebSearchArgs, web_search_tool, "Search the live web for fixes, patches, changelogs."),
    "fetch_package_metadata_tool": (PackageMetaArgs, fetch_package_metadata_tool, "Get latest version / deprecation info from PyPI or npm."),
    "github_comment_tool": (GithubCommentArgs, github_comment_tool, "Post a comment on a GitHub issue."),
    "slack_alert_tool": (SlackArgs, slack_alert_tool, "Send a Slack alert."),
}


def schemas(names: list[str]) -> list[dict]:
    out = []
    for n in names:
        model, _, desc = REGISTRY[n]
        out.append({"type": "function", "function": {
            "name": n, "description": desc, "parameters": model.model_json_schema()}})
    return out


def execute(name: str, raw_args: str, allowed: list[str], ctx: dict | None = None) -> str:
    """Validate LLM-supplied args with Pydantic; return errors to the LLM so it can self-correct."""
    if name not in allowed:
        return json.dumps({"error": f"tool {name} not available to this agent"})
    model, fn, _ = REGISTRY[name]
    try:
        args = model.model_validate_json(raw_args)
    except ValidationError as e:
        return json.dumps({"validation_error": e.errors(include_url=False, include_context=False)}, default=str)
    try:
        return json.dumps(fn(args, ctx), default=str)[:12000]
    except Exception as e:  # tool failure is data for the agent, not a crash
        return json.dumps({"tool_error": f"{type(e).__name__}: {e}"})
