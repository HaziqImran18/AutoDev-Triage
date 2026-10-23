import os
import threading
from openai import OpenAI
from agents import tools

MODEL = "gpt-4o-mini"
_client = None
_lock = threading.Lock()
_usage = {"prompt": 0, "completion": 0, "calls": 0}


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def track(resp) -> None:
    """Accumulate token usage from any OpenAI response (used for cost metrics)."""
    u = getattr(resp, "usage", None)
    if u is None:
        return
    with _lock:
        _usage["prompt"] += getattr(u, "prompt_tokens", 0) or 0
        _usage["completion"] += getattr(u, "completion_tokens", 0) or 0
        _usage["calls"] += 1


def snapshot() -> dict:
    with _lock:
        return dict(_usage)


def run_tool_loop(system: str, user: str, tool_names: list[str], max_iters: int = 5, ctx: dict | None = None):
    """Generic agent loop: call model -> execute validated tool calls -> repeat.
    Returns (messages, tool_trace)."""
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    trace = []
    for _ in range(max_iters):
        resp = client().chat.completions.create(
            model=MODEL, messages=msgs, tools=tools.schemas(tool_names), temperature=0)
        track(resp)
        m = resp.choices[0].message
        msgs.append(m.model_dump(exclude_none=True))
        if not m.tool_calls:
            break
        for tc in m.tool_calls:
            result = tools.execute(tc.function.name, tc.function.arguments, tool_names, ctx)
            trace.append(f"{tc.function.name}({tc.function.arguments[:80]}...)")
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return msgs, trace


def structured(msgs: list, schema):
    """Final structured extraction, validated against a Pydantic model."""
    r = client().beta.chat.completions.parse(
        model=MODEL, messages=msgs, response_format=schema, temperature=0)
    track(r)
    return r.choices[0].message.parsed