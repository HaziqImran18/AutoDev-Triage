"""Baseline: ONE LLM call, no tools, no web search, no stack-trace parser.
Uses the SAME model, SAME report prompt and SAME issue text as the pipeline, so the only
difference being measured is: multi-agent + tools vs. a single plain call."""
import json
from agents import llm
from agents.integrator import SYSTEM
from utils.render import strip_fence


def run(issue: dict) -> str:
    ctx = {"issue": issue, "sources": [],
           "note": "No web access. Answer from the issue text and your own knowledge only."}
    r = llm.client().chat.completions.create(
        model=llm.MODEL, temperature=0.2,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": json.dumps(ctx, default=str)[:20000]}])
    llm.track(r)
    return strip_fence(r.choices[0].message.content)
