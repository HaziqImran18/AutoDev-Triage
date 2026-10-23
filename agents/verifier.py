"""Verifier agent. Works from the RAW evidence ledger only (not the Diagnoser summary or Researcher notes).
Step 1 proposes atomic claims with citations. Step 2 is a SEPARATE blind call that checks each claim against only
its cited evidence. Step 3 is deterministic (ids, lexical grounding, URL stripping)."""
import json
from agents import llm, guard
from agents.evidence import build_ledger, allowed_urls
from agents.state import TriageState, Proposal, Entailments, ClaimResult

PROPOSE = """You are the Verifier agent. You receive an EVIDENCE LEDGER about a GitHub issue. Ids:
E1 = the issue text, T1 = stack frames parsed from it, S1..Sn = web search results, P1 = package metadata.
Decide the root cause and a fix using ONLY what you can support, as atomic claims.
Rules:
1. One verifiable statement per claim. role is root_cause, fix or context.
2. evidence_ids = ids of the entries that DIRECTLY state or clearly imply the claim. Copy ids exactly.
   Use basis='evidence' only when you cite entries.
3. If a claim comes from your background knowledge and is not in the ledger, use basis='knowledge' and leave
   evidence_ids empty. Never present it as sourced.
4. Never invent versions, error messages, changelog entries or links. Do not output URLs.
5. If the ledger does not let you determine a root cause, emit NO root_cause claim and describe what is
   missing in missing_info. Do not guess; an honest 'unknown' is correct.
6. At most 8 claims, no filler."""

CHECK = """You verify claims against evidence. For each item decide whether the EVIDENCE ALONE supports the CLAIM.
supported = the evidence states or directly implies it. not_supported = the evidence does not establish it
(even if it might be true). contradicted = the evidence conflicts with it.
For 'supported' items, put in supporting_ids ONLY the evidence ids that themselves support the claim;
never list an entry that is irrelevant or merely on the same topic.
Use ONLY the evidence text provided; ignore your own knowledge."""

MAX_CLAIMS = 8


def verifier_node(state: TriageState) -> dict:
    ledger = build_ledger(state)
    by_id = {e.id: e for e in ledger}
    allowed = allowed_urls(ledger)
    try:
        payload = [{"id": e.id, "kind": e.kind, "text": e.text} for e in ledger]
        proposal = llm.structured(
            [{"role": "system", "content": PROPOSE},
             {"role": "user", "content": json.dumps({"evidence_ledger": payload})[:24000]}], Proposal)
        claims = proposal.claims[:MAX_CLAIMS]

        items = []
        for i, c in enumerate(claims):
            ids = [x for x in c.evidence_ids if x in by_id]
            if c.basis == "evidence" and ids:
                items.append({"i": i, "claim": c.text,
                              "evidence": [{"id": x, "text": by_id[x].text[:1200]} for x in ids]})
        verdicts = {}
        if items:
            ent = llm.structured([{"role": "system", "content": CHECK},
                                  {"role": "user", "content": json.dumps(items)}], Entailments)
            verdicts = {e.i: (e.verdict, e.supporting_ids) for e in ent.items}

        results = []
        for i, c in enumerate(claims):
            text, removed = guard.sanitize_urls(c.text, allowed)
            ids = [x for x in c.evidence_ids if x in by_id]
            if c.basis != "evidence" or not ids:
                status, reason = "UNVERIFIED", "not backed by retrieved evidence (model background knowledge)"
            else:
                v, sup = verdicts.get(i, ("not_supported", []))
                if v == "contradicted":
                    status, reason = "REJECTED", "contradicted by the cited evidence"
                elif v == "not_supported":
                    status, reason = "UNVERIFIED", "cited evidence does not establish this claim"
                else:
                    ids = [x for x in ids if x in sup]  # prune citations to entries that really support it
                    if not ids:
                        status, reason = "UNVERIFIED", "no single cited entry was confirmed to support this claim"
                    else:
                        ok, missing = guard.lexically_grounded(text, [by_id[x].text for x in ids])
                        status, reason = ("GROUNDED", "") if ok else (
                            "UNVERIFIED", "terms not found in cited evidence: " + ", ".join(missing[:4]))
            if removed and status != "REJECTED":
                reason = (reason + "; " if reason else "") + "ungrounded link removed"
            results.append(ClaimResult(text=text, role=c.role, evidence_ids=ids, status=status, reason=reason))

        g = sum(r.status == "GROUNDED" for r in results)
        u = sum(r.status == "UNVERIFIED" for r in results)
        r_ = sum(r.status == "REJECTED" for r in results)
        return {"claims": results, "missing_info": proposal.missing_info[:5],
                "verdict": guard.decide_verdict(results),
                "trace": state.trace + [f"verifier: {len(results)} claims -> {g} grounded, {u} unverified, {r_} rejected"]}
    except Exception as e:  # verification failure must never turn into a confident report
        return {"verdict": "UNVERIFIED", "claims": [],
                "missing_info": ["Automatic verification failed; see errors."],
                "errors": state.errors + [f"verifier: {type(e).__name__}: {e}"],
                "trace": state.trace + ["verifier: failed"]}