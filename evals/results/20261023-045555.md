# Evaluation: single LLM vs 3-agent pipeline

Repo `HaziqImran18/autodev-triage-sandbox` - split `original` - 12 issues - 20261023-045555 - judge `gpt-4o`

| Metric | 3_agent_v2 |
|---|---|
| Root cause correct (all) | 92% |
|   - on real bugs | 90% |
|   - on control issues (honesty) | 100% |
| Fix reasonable | 83% |
| Invented facts (lower=better) | 17% |
| Keyword recall (bugs) | 83% |
| Reports with ungrounded URLs (lower=better) | 0% |
| Real bugs answered UNVERIFIED / INSUFFICIENT (cost of honesty) | 0% |
| Claims grounded in evidence | 79% |
| Run errors | 0% |
| Avg latency | 23.2s |
| Avg cost / issue | $0.0016 |

## Verdicts
- **3_agent_v2**: INSUFFICIENT_EVIDENCE x2, PARTIALLY_VERIFIED x5, VERIFIED x5

## Per issue (root cause correct)

| Issue | 3_agent_v2 | verdict |
|---|---|---|
| keyerror-user | ❌ | PARTIALLY_VERIFIED |
| distutils-312 | ✅ | VERIFIED |
| numpy-float | ✅ | VERIFIED |
| pydantic-basesettings | ✅ | PARTIALLY_VERIFIED |
| flask-app-context | ✅ | VERIFIED |
| asyncio-running-loop | ✅ | PARTIALLY_VERIFIED |
| node-fetch-esm | ✅ | PARTIALLY_VERIFIED |
| openai-429-quota | ✅ | VERIFIED |
| sqlite-locked | ✅ | VERIFIED |
| pandas-dup-index | ✅ | PARTIALLY_VERIFIED |
| control-feature-retry | ✅ | INSUFFICIENT_EVIDENCE |
| control-vague-slow | ✅ | INSUFFICIENT_EVIDENCE |

_n = 12 issues: differences of 1-2 issues are within noise. Cost = OpenAI tokens only (judge and Tavily excluded). URLs written in the issue text itself count as grounded._