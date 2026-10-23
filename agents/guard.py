"""Deterministic guards (no LLM): lexical grounding, URL sanitising, verdict logic."""
import re

_URL = re.compile(r"https?://[^\s)>\]\"'`]+")
_MDLINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
_TOKENS = [
    re.compile(r"\b\d+(?:\.\d+)+\b"),                          # versions: 1.24
    re.compile(r"`([^`\n]{2,40})`"),                           # `backticked` code
    re.compile(r"\b[A-Za-z_]\w*(?:[._]\w+)+\b"),               # np.float, pydantic_settings
    re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+\b"),      # CamelCase names
    re.compile(r"\b[A-Z]{2,}(?:_[A-Z0-9]+)+\b"),               # ERR_REQUIRE_ESM
]
_STOP = {"e.g", "i.e", "etc"}


def _norm(s: str) -> str:
    return re.sub(r"[\s`]+", "", s).lower().strip("():;,.")


def specific_tokens(text: str) -> set[str]:
    """Checkable specifics in a claim: versions, identifiers, code spans, error codes."""
    text = _URL.sub(" ", text)
    out = set()
    for p in _TOKENS:
        for m in p.finditer(text):
            t = _norm(m.group(1) if p.groups else m.group(0))
            if 2 <= len(t) <= 40 and t not in _STOP:
                out.add(t)
    return out


def lexically_grounded(claim: str, evidence_texts: list[str]) -> tuple[bool, list[str]]:
    blob = re.sub(r"[\s`]+", "", " ".join(evidence_texts)).lower()
    missing = sorted(t for t in specific_tokens(claim) if t not in blob)
    return (not missing, missing)


def sanitize_urls(text: str, allowed: set[str]) -> tuple[str, list[str]]:
    """Remove every URL that is not in `allowed`. Returns (clean_text, removed_urls)."""
    ok = {u.rstrip("/") for u in allowed if u}
    removed: list[str] = []

    def md(m):
        if m.group(2).rstrip("/") in ok:
            return m.group(0)
        removed.append(m.group(2))
        return m.group(1)

    def bare(m):
        u = m.group(0).rstrip(".,;:")
        trail = m.group(0)[len(u):]
        if u.rstrip("/") in ok:
            return m.group(0)
        removed.append(u)
        return "[link removed]" + trail

    return _URL.sub(bare, _MDLINK.sub(md, text)), removed


def decide_verdict(results) -> str:
    shown = [c for c in results if c.status != "REJECTED" and c.role in ("root_cause", "fix")]
    grounded_rc = [c for c in shown if c.role == "root_cause" and c.status == "GROUNDED"]
    if not grounded_rc:
        return "UNVERIFIED"
    return "VERIFIED" if all(c.status == "GROUNDED" for c in shown) else "PARTIALLY_VERIFIED"