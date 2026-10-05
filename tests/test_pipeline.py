"""Unit tests for the Clausewise agent — no network, no API key.

All Nebius Token Factory calls are mocked at the client boundary, so the
pipeline logic can be tested fully offline.
"""

import json
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import client as client_mod  # noqa: E402
from agent import pipeline  # noqa: E402


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class MockCompletions:
    """Scripted mock for client.chat.completions."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []  # record kwargs of each call

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("response_format"):
            # emulate an SDK that accepts response_format — first payload
            pass
        if not self.payloads:
            raise AssertionError("mock ran out of scripted payloads")
        return _Resp(json.dumps(self.payloads.pop(0)))


class MockClient:
    def __init__(self, payloads):
        self.chat = type("Chat", (), {})()
        self.chat.completions = MockCompletions(payloads)


SAMPLE_CLAUSES = {
    "clauses": [
        {"id": 1, "title": "Confidentiality", "text": "You must keep everything secret."},
        {"id": 2, "title": "Non-Compete", "text": "You may not work for competitors for 5 years."},
        {"id": 3, "title": "Payment", "text": "Payment within 30 days of invoice."},
    ]
}


def triage_payload(severity):
    return {
        "severity": severity,
        "risks": ["risk one"],
        "explanation": "explanation",
        "quote": "",
    }


class TestExtract(unittest.TestCase):
    def test_extract_returns_clauses(self):
        c = MockClient([SAMPLE_CLAUSES])
        clauses = pipeline.step_extract(c, "some contract text")
        self.assertEqual(len(clauses), 3)
        self.assertEqual(clauses[0]["title"], "Confidentiality")

    def test_extract_rejects_non_list(self):
        c = MockClient([{"clauses": "nope"}])
        with self.assertRaises(ValueError):
            pipeline.step_extract(c, "text")


class TestTriage(unittest.TestCase):
    def test_triage_sorts_by_severity(self):
        c = MockClient(
            [triage_payload("low"), triage_payload("critical"), triage_payload("medium")]
        )
        out = pipeline.step_triage(c, SAMPLE_CLAUSES["clauses"])
        self.assertEqual([a["severity"] for a in out], ["critical", "medium", "low"])
        self.assertEqual(c.chat.completions.calls[0]["model"], client_mod.DEFAULT_MODEL)

    def test_triage_normalizes_unknown_severity(self):
        c = MockClient([triage_payload("extreme")])
        out = pipeline.step_triage(c, [SAMPLE_CLAUSES["clauses"][0]])
        self.assertEqual(out[0]["severity"], "low")


class TestRedline(unittest.TestCase):
    def test_redline_only_risky_clauses(self):
        assessments = [
            {"clause_id": 1, "title": "A", "severity": "critical", "risks": ["r"]},
            {"clause_id": 2, "title": "B", "severity": "medium", "risks": ["r"]},
            {"clause_id": 3, "title": "C", "severity": "low", "risks": ["r"]},
        ]
        lookup = {i: {"id": i, "text": "t"} for i in (1, 2, 3)}
        c = MockClient(
            [{"original": "o", "redlined": "r", "negotiation_note": "n"}]
        )
        out = pipeline.step_redline(c, lookup, assessments)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["clause_id"], 1)


class TestVerifyAndBrief(unittest.TestCase):
    def test_verify_parses(self):
        c = MockClient([{"passed": True, "issues": [], "missed_clauses": []}])
        v = pipeline.step_verify(c, [], [], [])
        self.assertTrue(v["passed"])

    def test_brief_parses(self):
        c = MockClient(
            [
                {
                    "verdict": "negotiate",
                    "verdict_reason": "why",
                    "top_actions": ["a", "b"],
                    "overall_score": 62,
                }
            ]
        )
        b = pipeline.step_brief(c, [], {"passed": True})
        self.assertEqual(b["verdict"], "negotiate")
        self.assertEqual(b["overall_score"], 62)


class TestRunReviewEndToEnd(unittest.TestCase):
    def test_full_pipeline_with_trace(self):
        payloads = [
            SAMPLE_CLAUSES,
            triage_payload("high"),  # clause 1
            triage_payload("low"),  # clause 2
            triage_payload("critical"),  # clause 3
            {"original": "o1", "redlined": "r1", "negotiation_note": "n1"},  # clause 3
            {"original": "o2", "redlined": "r2", "negotiation_note": "n2"},  # clause 1
            {"passed": True, "issues": [], "missed_clauses": []},
            {
                "verdict": "negotiate",
                "verdict_reason": "ok",
                "top_actions": ["x"],
                "overall_score": 55,
            },
        ]
        c = MockClient(payloads)
        events = []
        result = pipeline.run_review(
            "full contract text", client=c, on_step=lambda s, d: events.append(s)
        )
        self.assertEqual(len(result.clauses), 3)
        self.assertEqual(result.risk_assessments[0]["severity"], "critical")
        self.assertEqual(len(result.redlines), 2)  # critical + high only
        self.assertTrue(result.verification["passed"])
        self.assertEqual(result.brief["verdict"], "negotiate")
        self.assertEqual([t.step for t in result.trace], ["extract", "triage", "redline", "verify", "brief"])
        self.assertEqual(events, ["extract", "triage", "redline", "verify", "brief"])

    def test_empty_contract_rejected(self):
        with self.assertRaises(ValueError):
            pipeline.run_review("   ", client=MockClient([]))


class TestClient(unittest.TestCase):
    def test_missing_key_raises_helpful_error(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "NEBIUS_API_KEY"}
        with unittest.mock.patch.dict("os.environ", env, clear=True):
            with self.assertRaises(client_mod.NebiusConfigError) as ctx:
                client_mod.build_client()
        self.assertIn("NEBIUS_API_KEY", str(ctx.exception))
        self.assertIn("tokenfactory.nebius.com", str(ctx.exception))

    def test_default_model_is_nemotron_super(self):
        self.assertEqual(client_mod.DEFAULT_MODEL, "nvidia/nemotron-3-super-120b-a12b")


if __name__ == "__main__":
    unittest.main()
