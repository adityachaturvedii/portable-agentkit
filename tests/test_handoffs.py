import copy
import json
from pathlib import Path
import tempfile
import unittest

from agentkit.validation import ROOT, ValidationError, read_json, validate_handoff


REV = "a" * 40
OLD = "b" * 40


def template(kind):
    data = read_json(ROOT / "contracts/examples" / (kind + ".json"))
    data["revision"] = REV
    if kind == "delivery-evidence":
        data["payload"]["head_revision"] = REV
    return data


def observation(identity="green", status="passed", revision=REV, method="command"):
    return {"id": identity, "revision": revision, "method": method,
            "status": status, "command": ["python3", "test_invoice.py"] if method == "command" else [],
            "environment_digest": "c" * 64,
            "artifacts": [{"path": "logs/check.txt", "sha256": "d" * 64}],
            "observation": "Observed the declared fixture result."}


def tested_handoff():
    data = template("behavioral-testing")
    data.update(status="complete", limitations=[], next_actions=[])
    data["evidence"] = [observation(), observation("red", "failed", OLD)]
    data["payload"] = {"seams": ["invoice_total(items, shipping, discount)"],
                       "expected_results": ["1000 merchandise at 10% off plus 200 shipping = 1100"],
                       "cases": [{"id": "shipping", "expected": "1100", "actual": "1100",
                                  "status": "passed", "evidence_ids": ["green"]}],
                       "red_evidence": ["red"], "green_evidence": ["green"]}
    return data


class HandoffTests(unittest.TestCase):
    def rejects(self, data):
        with self.assertRaises(ValidationError):
            validate_handoff(data)

    def test_valid_red_to_green_keeps_historical_revision(self):
        validate_handoff(tested_handoff())

    def test_unknown_version_kind_and_authority_fields_fail(self):
        for field, value in [("schema_version", 2), ("schema_version", True),
                             ("kind", "approval"), ("approved", True)]:
            data = tested_handoff()
            data[field] = value
            self.rejects(data)
        data = tested_handoff()
        data["payload"]["publish"] = True
        self.rejects(data)

    def test_missing_or_duplicate_evidence_fails(self):
        for mutation in ("missing", "duplicate", "artifact"):
            data = tested_handoff()
            if mutation == "missing":
                data["evidence"] = []
            elif mutation == "duplicate":
                data["evidence"].append(copy.deepcopy(data["evidence"][0]))
            else:
                data["evidence"][0]["artifacts"] = []
            self.rejects(data)

    def test_changed_code_invalidates_current_check(self):
        data = tested_handoff()
        data["revision"] = "e" * 40
        self.rejects(data)

    def test_self_report_cannot_be_promoted_to_pass(self):
        data = tested_handoff()
        data["evidence"][0]["method"] = "self-report"
        self.rejects(data)

    def test_unrun_or_failed_check_cannot_be_complete(self):
        for status in ("failed", "blocked", "not_run"):
            data = tested_handoff()
            data["payload"]["cases"][0]["status"] = status
            self.rejects(data)

    def test_missing_browser_stays_blocked_and_static_cannot_substitute(self):
        data = template("browser-verification")
        validate_handoff(data)
        data.update(status="complete", limitations=[], next_actions=[])
        data["payload"].update(verifier="verifier", implementation_authors=["builder"],
                               flows=[{"id": "checkout", "expected": "confirmation", "actual": "HTML contains confirmation",
                                       "status": "passed", "evidence_ids": ["html"]}])
        data["evidence"] = [observation("html", method="static-inspection")]
        self.rejects(data)

    def test_same_author_cannot_claim_independent_review(self):
        data = template("independent-review")
        data["status"] = "complete"
        data["payload"].update(reviewer="builder", implementation_authors=["builder"], verdict="no-findings")
        self.rejects(data)
        data["payload"]["reviewer"] = "reviewer"
        validate_handoff(data)  # Identity still requires trusted authentication later.

    def test_faster_but_incorrect_candidate_cannot_be_accepted(self):
        data = template("measured-optimisation")
        data["status"] = "complete"
        data["payload"].update(correctness="failed", decision="accepted")
        data["evidence"] = [observation()]
        self.rejects(data)

    def test_complete_optimization_requires_terminal_observed_experiment(self):
        data = template("measured-optimisation")
        data["status"] = "complete"
        self.rejects(data)
        data["payload"].update(correctness="failed", decision="rejected",
                               experiments=["Shortcut fails the independent output parity check."])
        self.rejects(data)  # A claim without a recorded observation is insufficient.
        data["evidence"] = [observation("parity", "failed")]
        validate_handoff(data)
        data["payload"]["experiments"] = []
        self.rejects(data)

    def test_findings_verdict_requires_actual_findings(self):
        data = template("independent-review")
        data["status"] = "complete"
        data["payload"].update(reviewer="reviewer", implementation_authors=["builder"], verdict="findings")
        self.rejects(data)

    def test_delivery_must_bind_head_and_keep_unknown_usage(self):
        data = template("delivery-evidence")
        validate_handoff(data)
        self.assertIsNone(data["payload"]["usage"]["api_money"])
        data["payload"]["head_revision"] = OLD
        self.rejects(data)

    def test_budget_proposal_does_not_enable_paid_usage(self):
        data = template("task-contract")
        data["payload"]["budget"]["paid_usage_authorized"] = True
        self.rejects(data)
        data["payload"]["budget"]["paid_usage_authorized"] = False
        data["payload"]["budget"]["max_attempts"] = True
        self.rejects(data)

    def test_json_reader_rejects_ambiguous_or_unbounded_input(self):
        bad = ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e9999}', '[' * 40 + '0' + ']' * 40,
               ' ' * 1_048_577, '{"x":']
        with tempfile.TemporaryDirectory(prefix="agentkit-json-") as tmp:
            path = Path(tmp) / "input.json"
            for text in bad:
                path.write_text(text)
                with self.subTest(text=text[:30]), self.assertRaises(ValidationError):
                    read_json(path)

    def test_command_and_paths_are_never_executed_or_followed(self):
        with tempfile.TemporaryDirectory(prefix="agentkit-proposal-") as tmp:
            sentinel = Path(tmp) / "should-not-exist"
            data = tested_handoff()
            data["evidence"][0]["command"] = ["sh", "-c", "touch " + str(sentinel)]
            data["evidence"][0]["artifacts"][0]["path"] = "/unreadable/secret"
            validate_handoff(data)
            self.assertFalse(sentinel.exists())


if __name__ == "__main__":
    unittest.main()
