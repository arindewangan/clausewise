# Clausewise — Agentic Contract Review on NVIDIA Nemotron × Nebius

Paste an NDA, freelancer agreement, or offer letter. Clausewise runs a **5-step AI agent**
entirely on NVIDIA's open-source **Nemotron-3-Super (120B MoE)** via **Nebius Token Factory** —
it extracts clauses, risk-scores each one, drafts negotiation-ready redlines, self-checks its
own report, and delivers a negotiation brief. Built for the **Nebius × NVIDIA Global AI Hackathon**
(track: **Best Apps & Agents**).

## Why it matters
Solo professionals and freelancers routinely sign NDAs and gig contracts they barely read —
one 5-year worldwide non-compete can end a career. Lawyers are expensive; Clausewise gives you
an expert first pass in ~30 seconds, with every agent step visible so you can see *how* it reasoned.

## Quick start (live mode)

```bash
# 1. Get a free API key: sign up at https://tokenfactory.nebius.com
#    (API Keys -> Create New Key). Hackathon entrants get $25 credits via the
#    Devpost Resources page with code NEBIUS-DEVPOST-GLOBAL26.
export NEBIUS_API_KEY="eyJ..."

# 2. Install + run
pip install -r requirements.txt
python app.py
# -> http://127.0.0.1:5000
```

Paste the sample NDA (pre-loaded) and hit **Run agent review**. Watch the agent trace,
then read the risk report, redlines, and verdict.

## Keyless demo mode

```bash
CLAUSEWISE_DEMO=1 python app.py
```

Runs the same UI with canned pipeline output, **clearly labeled as simulated** — for judges
and reviewers without an API key.

## Static showcase page (no server needed)

Open `demo/index.html` in any browser — a fully clickable showcase of a real review,
visually tagged **SIMULATED** throughout. Perfect for GitHub Pages hosting.

## Tests

```bash
python -m unittest discover -s tests   # 11 tests, all with mocked API calls — no key needed
```

## How it meets the hackathon requirements

1. **Runtime call to Nebius Token Factory** — every agent step calls
   `https://api.tokenfactory.nebius.com/v1/` via the OpenAI-compatible API.
2. **NVIDIA open-source model** — built on `nvidia/nemotron-3-super-120b-a12b`
   (Nemotron-3-Super, 120B MoE, 256K context), configurable via `NEBIUS_MODEL`.
3. **Public GitHub repo, OSI license** — MIT `LICENSE`, full setup instructions above.
4. **Working demo** — live app + keyless demo mode + static `demo/index.html`.
5. **Demo video ≤ 3 min on YouTube** — recorded separately at submission time.

## Disclaimer

Clausewise is an AI assistant, **not a lawyer**. Its analysis is a first pass, not legal
advice. Always consult a qualified attorney before signing.
