# Clausewise — Devpost Submission Copy
Event: Nebius × NVIDIA Global AI Hackathon — https://nebiusglobalaihackathon.devpost.com/


## Title
Clausewise — Agentic Contract Review on NVIDIA Nemotron × Nebius


## Tagline
Paste any contract. An AI agent on NVIDIA Nemotron-3-Super finds the traps, redlines them, and hands you a negotiation brief — in 30 seconds.


## Description (long)


**The problem.** Solo professionals and freelancers sign NDAs, gig contracts, and offer
letters they barely read. One buried 5-year worldwide non-compete can end a career, and a
lawyer costs more than the gig pays. The fine print is where careers go to die — and almost
nobody reads it.


**The solution.** Clausewise is an agentic contract-review copilot. Paste a contract and a
five-step AI agent goes to work:


1. **Extract** — splits the document into numbered clauses
2. **Triage** — risk-scores every clause (critical / high / medium / low) with plain-English rationale
3. **Redline** — drafts negotiation-ready rewrites for every risky clause, with talking points
4. **Verify** — self-audits its own report for missed clauses and contradictions before it ships
5. **Brief** — delivers a verdict (sign / negotiate / walk away), a contract-health score, and your top actions


Every step is visible in a live agent trace, so you see *how* the agent reasoned — not just
what it concluded.


**The tech.** Every agent step is a runtime call to **Nebius Token Factory**, running on
**NVIDIA's open-source Nemotron-3-Super (120B MoE, 256K context)** via the OpenAI-compatible
endpoint `https://api.tokenfactory.nebius.com/v1/`. Structured JSON output keeps the pipeline
reliable and testable; the whole stack is a small Flask app — no vendor lock-in, no black box.


**Try it.** Run locally with a free Nebius key, use the keyless demo mode, or click through
the simulated showcase page — all in the repo.


## Tracks
- **Best Apps & Agents** (primary)


## Built with
Python, Flask, NVIDIA Nemotron-3-Super, Nebius Token Factory


## Links
- GitHub repo: https://github.com/arindewangan/clausewise
- Live demo: https://arindewangan.github.io/clausewise/demo/
- Demo video (YouTube, ≤3 min, public): TBD — added at submission time
