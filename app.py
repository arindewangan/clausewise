"""Clausewise web server.

Serves the review UI and exposes POST /api/analyze, which runs the agentic
pipeline against NVIDIA Nemotron on Nebius Token Factory.

Run:
    export NEBIUS_API_KEY="<your key from https://tokenfactory.nebius.com>"
    pip install -r requirements.txt
    python app.py            # -> http://127.0.0.1:5000

Demo mode (no key — canned pipeline output, clearly labeled):
    CLAUSEWISE_DEMO=1 python app.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

from agent.client import NebiusConfigError, build_client
from agent.pipeline import ReviewResult, TraceStep, run_review

app = Flask(__name__)

SAMPLE_NDA = """MUTUAL NON-DISCLOSURE AGREEMENT

1. Confidential Information. "Confidential Information" means all information disclosed by either party, including but not limited to business plans, source code, customer lists, and any information marked confidential or that should reasonably be understood to be confidential.

2. Non-Use and Non-Disclosure. The Receiving Party shall not use Confidential Information for any purpose other than evaluating a potential business relationship, and shall not disclose it to any third party for a period of 10 (ten) years from disclosure.

3. Non-Compete. For a period of five (5) years after termination, the Receiving Party shall not, directly or indirectly, engage in any business competitive with the Disclosing Party anywhere in the world.

4. Non-Solicitation. The Receiving Party shall not solicit any employee of the Disclosing Party for 24 months.

5. Return of Materials. Upon request, all Confidential Information shall be returned or destroyed.

6. Remedies. The Receiving Party acknowledges that breach may cause irreparable harm and agrees the Disclosing Party is entitled to injunctive relief without proof of damages, in addition to all other remedies.

7. Governing Law. This Agreement shall be governed by the laws of the State of Delaware, without regard to conflict-of-law principles.
"""


def _demo_result() -> ReviewResult:
    """Canned pipeline output for keyless demo mode — never presented as a real review."""
    return ReviewResult(
        clauses=[
            {"id": 1, "title": "Confidential Information", "text": "Definition of confidential information..."},
            {"id": 2, "title": "Non-Use and Non-Disclosure", "text": "10-year non-disclosure obligation..."},
            {"id": 3, "title": "Non-Compete", "text": "5-year worldwide non-compete..."},
            {"id": 4, "title": "Non-Solicitation", "text": "24-month non-solicitation..."},
            {"id": 5, "title": "Return of Materials", "text": "Return or destroy on request..."},
            {"id": 6, "title": "Remedies", "text": "Injunctive relief without proof of damages..."},
            {"id": 7, "title": "Governing Law", "text": "Delaware governing law..."},
        ],
        risk_assessments=[
            {"clause_id": 3, "title": "Non-Compete", "severity": "critical",
             "risks": ["5-year worldwide ban is far beyond market norm (6-12 months, limited geography)",
                       "Could block future employment across the industry"],
             "explanation": "A five-year global non-compete is unenforceable in many jurisdictions and a major red flag.",
             "quote": "anywhere in the world"},
            {"clause_id": 6, "title": "Remedies", "severity": "high",
             "risks": ["Injunctive relief without proving damages lowers the bar for lawsuits against you"],
             "explanation": "One-sided remedies clause — the counterparty gets fast-track court orders.",
             "quote": "without proof of damages"},
            {"clause_id": 2, "title": "Non-Use and Non-Disclosure", "severity": "high",
             "risks": ["10-year secrecy term exceeds the typical 2-5 year market standard"],
             "explanation": "A decade-long obligation is unusually long for a mutual NDA.",
             "quote": "10 (ten) years"},
            {"clause_id": 4, "title": "Non-Solicitation", "severity": "medium",
             "risks": ["24 months is on the long side; 12 months is typical"],
             "explanation": "Broad but within the range seen in practice.", "quote": ""},
            {"clause_id": 7, "title": "Governing Law", "severity": "medium",
             "risks": ["Delaware law may be inconvenient if you are based elsewhere"],
             "explanation": "Check enforceability and dispute costs in your jurisdiction.", "quote": ""},
            {"clause_id": 1, "title": "Confidential Information", "severity": "low",
             "risks": [], "explanation": "Standard, balanced definition.", "quote": ""},
            {"clause_id": 5, "title": "Return of Materials", "severity": "low",
             "risks": [], "explanation": "Standard return-or-destroy clause.", "quote": ""},
        ],
        redlines=[
            {"clause_id": 3, "title": "Non-Compete", "severity": "critical",
             "original": "For a period of five (5) years after termination, the Receiving Party shall not engage in any competitive business anywhere in the world.",
             "redlined": "For a period of twelve (12) months after termination, the Receiving Party shall not engage in a directly competitive business within the territory where the Disclosing Party operates.",
             "negotiation_note": "Counter with 12 months + limited geography. Cite that 5-year global bans are unenforceable in California, India, and much of the EU — the counterparty gains nothing enforceable."},
            {"clause_id": 6, "title": "Remedies", "severity": "high",
             "original": "Entitled to injunctive relief without proof of damages.",
             "redlined": "Entitled to seek injunctive relief upon a showing of threatened irreparable harm, in addition to any other remedies available at law.",
             "negotiation_note": "Ask for mutual remedies or at least a 'threatened irreparable harm' standard."},
            {"clause_id": 2, "title": "Non-Use and Non-Disclosure", "severity": "high",
             "original": "Shall not disclose Confidential Information for 10 years.",
             "redlined": "Shall not disclose Confidential Information for 3 years from disclosure.",
             "negotiation_note": "10 years is unusual for a mutual NDA; 2-5 years is market. Trade secrets can stay perpetual separately."},
        ],
        verification={"passed": True, "issues": [], "missed_clauses": []},
        brief={"verdict": "negotiate",
               "verdict_reason": "The NDA is broadly standard but the non-compete and remedies clauses are one-sided and must be narrowed before signing.",
               "top_actions": ["Push back on the 5-year worldwide non-compete — ask for 12 months, limited territory",
                               "Cap the secrecy term at 3 years instead of 10",
                               "Make remedies mutual or add an irreparable-harm standard",
                               "Confirm which entity's law governs disputes and where you'd be sued"],
               "overall_score": 58},
        trace=[
            TraceStep("extract", "Split contract into 7 clauses"),
            TraceStep("triage", "Risk-scored 7 clauses", 7),
            TraceStep("redline", "Drafted 3 redlines for critical/high clauses", 3),
            TraceStep("verify", "Self-check passed"),
            TraceStep("brief", "Verdict: negotiate"),
        ],
    )


@app.get("/")
def index():
    return render_template(
        "index.html",
        sample_nda=SAMPLE_NDA,
        demo_mode=bool(os.environ.get("CLAUSEWISE_DEMO")),
    )


@app.post("/api/analyze")
def analyze():
    payload = request.get_json(force=True, silent=True) or {}
    contract_text = (payload.get("contract") or "").strip()
    if not contract_text:
        return jsonify({"error": "Paste or upload contract text first."}), 400
    if len(contract_text) > 120_000:
        return jsonify({"error": "Contract text is too long (max ~120k characters)."}), 400

    if os.environ.get("CLAUSEWISE_DEMO"):
        result = _demo_result()
        data = result.to_dict()
        data["simulated"] = True
        return jsonify(data)

    try:
        client = build_client()
    except NebiusConfigError as exc:
        return jsonify({"error": str(exc)}), 503
    try:
        result = run_review(contract_text, client=client)
    except Exception as exc:  # surface model/API errors honestly
        return jsonify({"error": f"Model call failed: {exc}"}), 502
    return jsonify(result.to_dict())


@app.get("/assets/<path:name>")
def assets(name):
    return send_from_directory(Path(__file__).resolve().parent / "assets", name)


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "demo_mode": bool(os.environ.get("CLAUSEWISE_DEMO"))})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
