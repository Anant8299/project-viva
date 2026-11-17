"""Thin wrapper over any OpenAI-compatible chat API (Groq, Gemini, OpenAI, local servers)."""
from __future__ import annotations

import json
import re
import time

PROVIDERS = {
    "Groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "Gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "model": "gemini-2.5-flash"},
    "OpenAI": {"base_url": None, "model": "gpt-4o-mini"},
}

_SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(\w*(?:api[_-]?key|secret|token|password|passwd)\w*)(\s*[:=]\s*)(['\"])[^'\"]{6,}\3"),
     r"\1\2\3[REDACTED]\3"),
    (re.compile(r"\b(sk|gsk|ghp|github_pat|xox[bp])[-_][A-Za-z0-9_\-]{16,}"), "[REDACTED_KEY]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{30,}"), "[REDACTED_GOOGLE_KEY]"),
]


class LLMError(Exception):
    pass


def redact(text: str) -> str:
    """Strip obvious secrets before code leaves the machine."""
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def extract_json(text: str) -> dict:
    """Models sometimes wrap JSON in prose or code fences. Pull out the first object."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise LLMError("model reply had no JSON object")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError as exc:
                    raise LLMError(f"could not parse model JSON: {exc}") from exc
    raise LLMError("unterminated JSON in model reply")


class LLMClient:
    def __init__(self, api_key: str, provider: str = "Groq", model: str | None = None,
                 base_url: str | None = None, temperature: float = 0.0, max_retries: int = 2):
        from openai import OpenAI  # imported lazily so offline mode needs no package

        cfg = PROVIDERS.get(provider, {})
        self.model = model or cfg.get("model")
        self.temperature = temperature
        self.max_retries = max_retries
        self._client = OpenAI(api_key=api_key, base_url=base_url or cfg.get("base_url"))

    def chat_json(self, system: str, user: str) -> dict:
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    response_format={"type": "json_object"},
                )
                return extract_json(resp.choices[0].message.content or "")
            except LLMError as exc:
                last_err = exc
            except Exception as exc:  # network, auth, rate limit
                last_err = exc
                if "401" in str(exc) or "invalid api key" in str(exc).lower():
                    break
            time.sleep(1.5 * (attempt + 1))
        raise LLMError(f"LLM call failed: {last_err}")
