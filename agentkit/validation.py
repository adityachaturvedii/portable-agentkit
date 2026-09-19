"""Strict validation of bundled schemas and untrusted handoff proposals."""

import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 1_048_576
MAX_DEPTH = 32


class ValidationError(ValueError):
    pass


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("duplicate JSON property: " + key)
        result[key] = value
    return result


def _depth(value, depth=0):
    if depth > MAX_DEPTH:
        raise ValidationError("JSON nesting exceeds 32 levels")
    if isinstance(value, dict):
        for child in value.values():
            _depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _depth(child, depth + 1)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValidationError("JSON numbers must be finite")


def read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValidationError("JSON exceeds 1 MiB limit")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              ValidationError("non-finite JSON number")))
        _depth(data)
        return data
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValidationError("invalid JSON: " + str(exc)) from exc


def _type(value, name):
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "number": type(value) in (int, float),
        "boolean": type(value) is bool,
        "null": value is None,
    }[name]


def _equal(a, b):
    # Python considers True == 1; JSON Schema does not.
    return type(a) is type(b) and a == b


def _validate(value, schema, root, where="$"):
    allowed = {"$schema", "$id", "$defs", "$ref", "type", "const", "enum",
               "properties", "required", "additionalProperties", "items",
               "minLength", "pattern", "minimum", "oneOf"}
    if set(schema) - allowed:
        raise ValidationError("unsupported bundled schema keyword")
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/") or ref.count("/") != 2:
            raise ValidationError("only bundled local definitions are supported")
        _validate(value, root["$defs"][ref.split("/")[-1]], root, where)
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type(value, n) for n in names):
            raise ValidationError(where + ": expected " + "/".join(names))
    if "const" in schema and not _equal(value, schema["const"]):
        raise ValidationError(where + ": unexpected constant")
    if "enum" in schema and not any(_equal(value, x) for x in schema["enum"]):
        raise ValidationError(where + ": unknown value")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        missing = set(schema.get("required", [])) - set(value)
        if missing:
            raise ValidationError(where + ": missing " + ", ".join(sorted(missing)))
        if schema.get("additionalProperties") is False and set(value) - set(props):
            raise ValidationError(where + ": unknown properties " +
                                  ", ".join(sorted(set(value) - set(props))))
        for name in value.keys() & props.keys():
            _validate(value[name], props[name], root, where + "." + name)
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate(item, schema["items"], root, where + "[" + str(index) + "]")
    if isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            raise ValidationError(where + ": empty string")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise ValidationError(where + ": invalid identifier")
    if type(value) in (int, float) and "minimum" in schema and value < schema["minimum"]:
        raise ValidationError(where + ": below minimum")
    if "oneOf" in schema:
        successes = 0
        for branch in schema["oneOf"]:
            try:
                _validate(value, branch, root, where)
                successes += 1
            except ValidationError:
                pass
        if successes != 1:
            raise ValidationError(where + ": payload does not match exactly one skill format")


def validate_handoff(data):
    """Validate consistency only. Returns data; never authorizes an effect."""
    _depth(data)
    schema = read_json(ROOT / "contracts/handoff.schema.json")
    _validate(data, schema, schema)
    payload = data["payload"]
    complete = data["status"] == "complete"
    if not complete and (not data["limitations"] or not data["next_actions"]):
        raise ValidationError("incomplete/blocked requires limitations and next actions")
    evidence = {}
    for record in data["evidence"]:
        if record["id"] in evidence:
            raise ValidationError("duplicate evidence ID")
        evidence[record["id"]] = record
        if record["method"] == "self-report" and record["status"] in ("passed", "failed"):
            raise ValidationError("self-report cannot be measured evidence")
        if record["method"] == "command" and not record["command"]:
            raise ValidationError("command evidence requires argv")
        if record["status"] in ("passed", "failed") and not record["artifacts"]:
            raise ValidationError("observed pass/fail requires a hashed artifact")

    def refs(ids, status=None, current=False, method=None):
        if not ids:
            raise ValidationError("check requires evidence references")
        for identity in ids:
            if identity not in evidence:
                raise ValidationError("unknown evidence ID: " + identity)
            record = evidence[identity]
            if status and record["status"] != status:
                raise ValidationError("check/evidence status mismatch")
            if current and record["revision"] != data["revision"]:
                raise ValidationError("stale evidence for candidate")
            if method and record["method"] != method:
                raise ValidationError("wrong evidence method for check")

    kind = data["kind"]
    if kind in ("behavioral-testing", "browser-verification", "delivery-evidence"):
        key = {"behavioral-testing": "cases", "browser-verification": "flows",
               "delivery-evidence": "acceptance_results"}[kind]
        cases = payload[key]
        if complete and not cases:
            raise ValidationError("complete verification requires cases")
        if len({case["id"] for case in cases}) != len(cases):
            raise ValidationError("duplicate case ID")
        for case in cases:
            if complete and case["status"] != "passed":
                raise ValidationError("complete verification contains an unpassed case")
            if case["status"] in ("passed", "failed"):
                method = {"behavioral-testing": "command", "browser-verification": "browser"}.get(kind)
                refs(case["evidence_ids"], case["status"], True, method)
            elif case["evidence_ids"]:
                refs(case["evidence_ids"], case["status"], True)
    if kind == "behavioral-testing":
        if complete or payload["red_evidence"]:
            refs(payload["red_evidence"], "failed", method="command")
        if complete or payload["green_evidence"]:
            refs(payload["green_evidence"], "passed", True, "command")
    if kind in ("independent-review", "browser-verification") and complete:
        role = "reviewer" if kind == "independent-review" else "verifier"
        if not payload["implementation_authors"] or payload[role] in payload["implementation_authors"]:
            raise ValidationError("independence not established")
    if kind in ("independent-review", "delivery-evidence"):
        for finding in payload["findings"]:
            if finding["evidence_ids"]:
                refs(finding["evidence_ids"], current=True)
        if kind == "independent-review":
            if complete and payload["verdict"] == "blocked":
                raise ValidationError("blocked review cannot be complete")
            if payload["verdict"] == "no-findings" and payload["findings"]:
                raise ValidationError("no-findings verdict contradicts findings")
            if payload["verdict"] == "findings" and not payload["findings"]:
                raise ValidationError("findings verdict requires at least one finding")
        elif payload["head_revision"] != data["revision"]:
            raise ValidationError("delivery head differs from candidate")
        elif complete and any(f["disposition"] == "open" for f in payload["findings"]):
            raise ValidationError("open delivery findings require incomplete disposition")
    if kind == "change-impact":
        for risk in payload["risks"]:
            if risk["state"] == "cleared":
                refs(risk["evidence_ids"], "passed", True)
            elif risk["evidence_ids"]:
                refs(risk["evidence_ids"], current=True)
    if kind == "measured-optimisation":
        if payload["decision"] == "accepted" and (not complete or payload["correctness"] != "passed"):
            raise ValidationError("accepted optimization requires completed correctness")
        if complete:
            if payload["decision"] == "incomplete" or payload["correctness"] not in ("passed", "failed"):
                raise ValidationError("complete optimization requires a terminal decision and observed correctness")
            if not payload["experiments"]:
                raise ValidationError("complete optimization requires an experiment")
            observations = [e["id"] for e in evidence.values() if e["method"] == "command"
                            and e["status"] == payload["correctness"]
                            and e["revision"] == data["revision"]]
            refs(observations, payload["correctness"], True, "command")
    if kind == "task-contract" and complete:
        if not payload["scope"] or not payload["acceptance"]:
            raise ValidationError("complete contract requires scope and acceptance")
    return data
