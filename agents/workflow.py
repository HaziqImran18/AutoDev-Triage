from langgraph.graph import StateGraph, END
from agents.state import TriageState
from agents.diagnoser import diagnoser_node
from agents.researcher import researcher_node
from agents.verifier import verifier_node
from agents.integrator import integrator_node, legacy_integrator_node, abstain_node
from agents.evidence import has_error_signal

MAX_RESEARCH_ATTEMPTS = 2


# ---- v1 (legacy) routing ----
def after_diagnoser(state: TriageState) -> str:
    return "researcher" if state.diagnosis else END


def after_researcher(state: TriageState) -> str:
    # cyclic edge: retry with a broader query if nothing useful was found
    if not state.findings.sources and state.research_attempts < MAX_RESEARCH_ATTEMPTS:
        return "researcher"
    return "integrator"


# ---- v2 (grounded) routing ----
def after_diagnoser_grounded(state: TriageState) -> str:
    if not state.diagnosis:
        return END
    # deterministic gate: no stack trace / exception text in the issue -> abstain, skip research
    return "researcher" if has_error_signal(state.issue, state.stack_frames) else "abstain"


def after_researcher_grounded(state: TriageState) -> str:
    if not state.findings.sources and state.research_attempts < MAX_RESEARCH_ATTEMPTS:
        return "researcher"
    return "verifier"


def build_graph(mode: str = "grounded"):
    g = StateGraph(TriageState)
    g.add_node("diagnoser", diagnoser_node)
    g.add_node("researcher", researcher_node)
    g.set_entry_point("diagnoser")
    if mode == "legacy":
        g.add_node("integrator", legacy_integrator_node)
        g.add_conditional_edges("diagnoser", after_diagnoser, {"researcher": "researcher", END: END})
        g.add_conditional_edges("researcher", after_researcher,
                                {"researcher": "researcher", "integrator": "integrator"})
        g.add_edge("integrator", END)
    elif mode == "grounded":
        g.add_node("verifier", verifier_node)
        g.add_node("integrator", integrator_node)
        g.add_node("abstain", abstain_node)
        g.add_conditional_edges("diagnoser", after_diagnoser_grounded,
                                {"researcher": "researcher", "abstain": "abstain", END: END})
        g.add_conditional_edges("researcher", after_researcher_grounded,
                                {"researcher": "researcher", "verifier": "verifier"})
        g.add_edge("verifier", "integrator")
        g.add_edge("integrator", END)
        g.add_edge("abstain", END)
    else:
        raise ValueError(f"unknown mode {mode!r}")
    return g.compile()


def run_triage(repo: str, issue_number: int, post_to_github=False, post_to_slack=False,
               github_token: str | None = None, mode: str = "grounded") -> TriageState:
    final = build_graph(mode).invoke(TriageState(
        repo=repo, issue_number=issue_number,
        post_to_github=post_to_github, post_to_slack=post_to_slack, github_token=github_token))
    return TriageState.model_validate(final)