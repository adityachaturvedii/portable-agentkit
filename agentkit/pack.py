"""Bundled skill discovery and package integrity checks; no installation."""

import hashlib
import re

from .validation import ROOT, ValidationError, read_json, validate_handoff


def catalog():
    return read_json(ROOT / "catalog.json")


def select(intent):
    matches = [s for s in catalog()["skills"] if s["intent"] == intent]
    if len(matches) != 1:
        raise ValidationError("unknown intent; use list for the explicit vocabulary")
    return matches[0]


def render(skill, domain=None):
    entry = next((s for s in catalog()["skills"] if s["id"] == skill), None)
    if entry is None:
        raise ValidationError("unknown skill; use list")
    if domain is not None and domain not in catalog()["domains"]:
        raise ValidationError("unknown domain; use list")
    paths = [ROOT / entry["path"], ROOT / "docs/skill-contract.md", ROOT / "contracts/README.md"]
    if domain:
        paths.append(ROOT / "domains" / (domain + ".md"))
    return "\n\n".join(p.read_text() for p in paths)


def check_pack():
    cat = catalog()
    for field in ("id", "intent", "path", "output_kind"):
        if len({s[field] for s in cat["skills"]}) != len(cat["skills"]):
            raise ValidationError("duplicate catalog " + field)
    names = {s["id"] for s in cat["skills"]}
    if names != {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}:
        raise ValidationError("catalog/skill inventory mismatch")
    for entry in cat["skills"]:
        text = (ROOT / entry["path"]).read_text()
        if not text.startswith("---\nname: " + entry["id"] + "\ndescription: "):
            raise ValidationError("invalid skill frontmatter: " + entry["id"])
        render(entry["id"])
    for domain in cat["domains"]:
        if not (ROOT / "domains" / (domain + ".md")).is_file():
            raise ValidationError("missing domain: " + domain)
    for directory in ("skills", "domains", "docs", "contracts"):
        for path in (ROOT / directory).rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                target_path = (path.parent / target.split("#")[0]).resolve()
                if ROOT not in target_path.parents or not target_path.exists():
                    raise ValidationError("broken or escaping reference: " + str(path) + " -> " + target)
    lock = read_json(ROOT / "audit/sources.lock.json")
    for source in lock["sources"]:
        if not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
            raise ValidationError("source is not pinned")
        original = next(f for f in source["files"] if f["path"] == "LICENSE")
        actual = hashlib.sha256((ROOT / source["notice"]).read_bytes()).hexdigest()
        if original["sha256"] != actual:
            raise ValidationError("license notice does not match audited source")
    examples = list((ROOT / "contracts/examples").glob("*.json"))
    if {p.stem for p in examples} != names:
        raise ValidationError("example inventory mismatch")
    for path in examples:
        validate_handoff(read_json(path))
    return {"status": "passed", "skills": len(names), "domains": len(cat["domains"]),
            "examples": len(examples), "sources": len(lock["sources"]),
            "limits": "Offline structural checks only; no live source fetch, sandbox or provider verification."}
