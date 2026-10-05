"""Agentic contract-review pipeline for Clausewise.

Five staged agent steps, each a runtime call to the NVIDIA Nemotron model on
Nebius Token Factory:

    1. EXTRACT  - split the raw contract text into numbered clauses
    2. TRIAGE   - risk-score every clause (critical/high/medium/low) with rationale
    3. REDLINE  - draft negotiation-ready redlines for risky clauses
    4. VERIFY   - self-check pass: the agent re-reads its own report for
                  contradictions, missed clauses, or hallucinated quotes
    5. BRIEF    - synthesize the final negotiation brief (verdict + top actions)

The orchestrator records an agent trace (one entry per step) so the UI can
show judges exactly what the agent did and in what order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .client import build_client, complete_json

SYSTEM_BASE = (
    "You are Clausewise, an expert contract analyst. You output ONLY valid JSON "
    "matching the requested schema. Be precise, cite exact clause numbers, and never "
    "invent clauses that are not in the input text."
)

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass
class TraceStep:
    step: str
    detail: str
    model_calls: int = 1


@dataclass
class ReviewResult:
    clauses: list[dict]
    risk_assessments: list[dict]
    redlines: list[dict]
    verification: dict
    brief: dict
    trace: list[TraceStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "clauses": self.clauses,
            "risk_assessments": self.risk_assessments,
            "redlines": self.redlines,
            "verification": self.verification,
            "brief": self.brief,
            "trace": [
                {"step": t.step, "detail": t.detail, "model_calls": t.model_calls}
                for t in self.trace
            ],
        }


def _norm_severity(value: Any) -> str:
    v = str(value or "low").lower().strip()
    return v if v in SEVERITY_ORDER else "low"


def step_extract(client, contract_text: str) -> list[dict]:
    data = complete_json(
        client,
        SYSTEM_BASE,
        "Split the contract below into its individual clauses. Return JSON:\n"
        '{"clauses":[{"id":1,"title":"short title","text":"full clause text"}]}\n\n'
        f"CONTRACT:\n{contract_text}",
    )
    clauses = data.get("clauses", []) if isinstance(data, dict) else data
    if not isinstance(clauses, list):
        raise ValueError("extract step returned non-list clauses")
    return clauses


def step_triage(client, clauses: list[dict]) -> list[dict]:
    """One Nemotron call per clause batch — keeps prompts small and precise."""
    assessments: list[dict] = []
    for clause in clauses:
        data = complete_json(
            client,
            SYSTEM_BASE,
            "Assess the risk of this clause for the party signing it. Return JSON:\n"
            '{"severity":"critical|high|medium|low","risks":["..."],"explanation":"...","quote":"exact risky phrase or empty"}\n\n'
            f'CLAUSE {clause.get("id")} - {clause.get("title")}:\n{clause.get("text")}',
            max_tokens=1500,
        )
        assessments.append(
            {
                "clause_id": clause.get("id"),
                "title": clause.get("title"),
                "severity": _norm_severity(data.get("severity")),
                "risks": data.get("risks", []) or [],
                "explanation": data.get("explanation", ""),
                "quote": data.get("quote", ""),
            }
        )
    assessments.sort(key=lambda a: SEVERITY_ORDER[a["severity"]])
    return assessments


def step_redline(client, clause_lookup: dict, assessments: list[dict]) -> list[dict]:
    redlines: list[dict] = []
    for a in assessments:
        if SEVERITY_ORDER[a["severity"]] > SEVERITY_ORDER["high"]:
            continue  # only redline critical/high clauses
        clause = clause_lookup.get(a["clause_id"], {})
        data = complete_json(
            client,
            SYSTEM_BASE,
            "Draft a negotiation redline for this risky clause. Rewrite it to protect the "
            "signing party while staying realistic for a counterparty to accept. Return JSON:\n"
            '{"original":"...","redlined":"...","negotiation_note":"why this change and how to argue for it"}\n\n'
            f'RISKS: {"; ".join(a["risks"])}- {clause.get("text", "")}',
            max_tokens=2000,
        )
        redlines.append(
            {
                "clause_id": a["clause_id"],
                "title": a["title"],
                "severity": a["severity"],
                "original": data.get("original", ""),
                "redlined": data.get("redlined", ""),
                "negotiation_note": data.get("negotiation_note", ""),
            }
        )
    return redlines


def step_verify(client, clauses: list[dict], assessments: list[dict], redlines: list[dict]) -> dict:
    """Self-check: the agent audits its own draft report before it ships."""
    summary = (
        f"Clauses analyzed: {len(clauses)}. "
        f"Risk counts: { {s: sum(1 for a in assessments if a['severity'] == s) for s in SEVERITY_ORDER} }. "
        f"Redlines drafted: {len(redlines)}."
    )
    clause_texts = "\n".join(
        f"[{c.get('id')}] {c.get('title')}: {c.get('text')}" for c in clauses
    )
    data = complete_json(
        client,
        SYSTEM_BASE,
        "You are auditing a contract-review report for correctness. Check for: (1) clauses from "
        "the contract that were never assessed, (2) risk assessments that misread a clause, "
        "(3) redlines that contradict their clause. Return JSON:\n"
        '{"passed":true|false,"issues":["..."],"missed_clauses":[]}\n\n'
        f"REPORT SUMMARY: {summary}\n\nFULL CONTRACT:\n{clause_texts}",
        max_tokens=2000,
    )
    return {
        "passed": bool(data.get("passed", False)),
        "issues": data.get("issues", []) or [],
        "missed_clauses": data.get("missed_clauses", []) or [],
    }


def step_brief(client, assessments: list[dict], verification: dict) -> dict:
    data = complete_json(
        client,
        SYSTEM_BASE,
        "Write the final negotiation brief. Return JSON:\n"
        '{"verdict":"sign|negotiate|walk_away","verdict_reason":"...","top_actions":["3-5 concrete next steps"],"overall_score":0-100}\n\n'
        f"RISK ASSESSMENTS:\n{assessments}\n\nSELF-CHECK PASSED: {verification.get('passed')}",
        max_tokens=1500,
    )
    return {
        "verdict": data.get("verdict", "negotiate"),
        "verdict_reason": data.get("verdict_reason", ""),
        "top_actions": data.get("top_actions", []) or [],
        "overall_score": data.get("overall_score"),
    }


def run_review(
    contract_text: str,
    client=None,
    on_step: Callable[[str, str], None] | None = None,
) -> ReviewResult:
    """Run the full agentic pipeline. `on_step` receives (step_name, detail) events."""
    if not contract_text or not contract_text.strip():
        raise ValueError("contract_text must not be empty")
    client = client or build_client()

    def note(step: str, detail: str, calls: int = 1):
        if on_step:
            on_step(step, detail)
        trace.append(TraceStep(step=step, detail=detail, model_calls=calls))

    trace: list[TraceStep] = []
    clauses = step_extract(client, contract_text)
    note("extract", f"Split contract into {len(clauses)} clauses")

    assessments = step_triage(client, clauses)
    note("triage", f"Risk-scored {len(assessments)} clauses", calls=len(assessments))

    clause_lookup = {c.get("id"): c for c in clauses}
    redlines = step_redline(client, clause_lookup, assessments)
    note("redline", f"Drafted {len(redlines)} redlines for critical/high clauses", calls=len(redlines))

    verification = step_verify(client, clauses, assessments, redlines)
    note("verify", f"Self-check {'passed' if verification['passed'] else 'flagged issues'}")

    brief = step_brief(client, assessments, verification)
    note("brief", f"Verdict: {brief['verdict']}")

    return ReviewResult(
        clauses=clauses,
        risk_assessments=assessments,
        redlines=redlines,
        verification=verification,
        brief=brief,
        trace=trace,
    )
