import os
import httpx

API = "https://api.github.com"

_HINTS = {
    401: "Bad or expired GITHUB_TOKEN.",
    403: "Token lacks permission (Issues: Read and write) or rate limit hit.",
    404: "Not found. Issue/repo does not exist, OR it is private and the token has no access to it.",
}


def _check(r: httpx.Response) -> None:
    if r.status_code >= 400:
        raise RuntimeError(f"GitHub {r.status_code} on {r.request.method} {r.request.url.path}. "
                           f"{_HINTS.get(r.status_code, '')}")



def _headers(token: str | None = None) -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token := (token or os.getenv("GITHUB_TOKEN")):
        h["Authorization"] = f"Bearer {token}"
    return h


def get_issue(repo: str, number: int, token: str | None = None) -> dict:
    with httpx.Client(timeout=15) as c:
        r = c.get(f"{API}/repos/{repo}/issues/{number}", headers=_headers(token))
        _check(r)
        d = r.json()
        comments = []
        if d.get("comments"):
            cr = c.get(d["comments_url"], headers=_headers(token), params={"per_page": 5})
            if cr.status_code == 200:
                comments = [x["body"][:1500] for x in cr.json()]
    return {
        "title": d["title"],
        "body": (d.get("body") or "")[:8000],
        "labels": [l["name"] for l in d.get("labels", [])],
        "state": d["state"],
        "url": d["html_url"],
        "comments": comments,
    }


def post_comment(repo: str, number: int, body: str, token: str | None = None) -> str:
    with httpx.Client(timeout=15) as c:
        r = c.post(f"{API}/repos/{repo}/issues/{number}/comments",
                   headers=_headers(token), json={"body": body})
        _check(r)
        return r.json()["html_url"]
