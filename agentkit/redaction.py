"""Redact known sensitive fields and patterns before any event is persisted.

Not a general secret detector; callers must never supply real secrets as prompts.
"""

import json
import re


SENSITIVE = re.compile(r"authorization|cookie|password|secret|api.?key|access.?token|refresh.?token|id.?token|email|account.?id", re.I)


def redact_text(text):
    text = re.sub(r"(?i)\bBearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED_KEY]", text)
    text = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED_JWT]", text)
    text = re.sub(r"(?i)((?:password|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|cookie)[\"']?\s*[:=]\s*[\"']?)[^\s\"',}]+", r"\1[REDACTED]", text)
    text = re.sub(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", text)
    return text


def redact(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if SENSITIVE.search(k) or k in ("thinking", "signature") else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(x) for x in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redacted_stream(raw, truncated=False):
    text = raw.decode("utf-8", errors="replace")
    if truncated and text and not text.endswith("\n"):
        text = text.rsplit("\n", 1)[0] + "\n" if "\n" in text else ""
        text += "[incomplete fragment withheld]\n"
    lines = []
    for line in text.splitlines():
        try:
            lines.append(json.dumps(redact(json.loads(line)), ensure_ascii=False))
        except (ValueError, RecursionError):
            lines.append(redact_text(line))
    return "\n".join(lines) + ("\n" if lines else "")
