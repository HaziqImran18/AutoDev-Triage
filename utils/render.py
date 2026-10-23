import re

_FENCE = re.compile(r"^\s*```(?:markdown|md)?\s*\n(.*?)\n```\s*$", re.S)
_ICONS = {"summary": "📝", "root": "🎯", "evidence": "🔎", "fix": "🛠️", "reference": "🔗"}


def strip_fence(text: str | None) -> str:
    """LLMs sometimes wrap the whole report in ```markdown fences; remove them."""
    t = text or ""
    m = _FENCE.match(t)
    return (m.group(1) if m else t).strip()


def split_sections(md: str | None) -> list[dict]:
    parts = re.split(r"(?m)^##\s+(.+)$", md or "")
    out = []
    for i in range(1, len(parts), 2):
        title, body = parts[i].strip(), parts[i + 1].strip()
        icon = next((v for k, v in _ICONS.items() if k in title.lower()), "📄")
        out.append({"title": title, "body": body, "icon": icon})
    if not out and (md or "").strip():
        out = [{"title": "Report", "body": md.strip(), "icon": "📄"}]
    return out
