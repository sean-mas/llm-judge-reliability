"""Shared transport for the two Ollama-served tiers.

Tier 2 (hosted open-weights) and tier 3 (local open-weights) speak the identical
chat API. Only the host and the authorisation header differ. Keeping one
implementation means any difference the study measures between them is a
difference in the *model*, not in how we happened to call it, which is the whole
point of putting the same weights family at two scales.

Subclasses set ``judge_id``, ``model_requested``, ``default_host``, and override
``_headers`` and the two error hints where the remedy differs.
"""

from __future__ import annotations

import os

import httpx

from . import JudgeAdapter, JudgeError, RawResponse

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["FAITHFUL", "UNFAITHFUL"]},
        "span": {"type": ["string", "null"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
}


class OllamaChatJudge(JudgeAdapter):
    """POST /api/chat, non-streaming, reasoning disabled by default."""

    default_host = "http://localhost:11434"

    def __init__(self, schema: bool = False, think: bool = True,
                 host: str | None = None, **kw) -> None:
        kw.setdefault("max_tokens", 1000)
        super().__init__(**kw)
        self.schema = schema
        self.think = think
        self.host = (host or self._env_host() or self.default_host).rstrip("/")
        if schema:
            # Distinguish the constrained run in the stored data, so the two can
            # never be pooled by accident in analysis.
            self.judge_id += "_schema"
        if not think:
            # Reasoning ON is the primary condition, so it carries the clean
            # judge_id and the ablation is the one that is marked.
            self.judge_id += "_nothink"

    def _env_host(self) -> str | None:
        return os.environ.get("OLLAMA_HOST")

    def _headers(self) -> dict[str, str]:
        return {}

    def _connect_hint(self) -> str:
        return f"cannot reach Ollama at {self.host}."

    def _not_found_hint(self) -> str:
        return f"model {self.model_requested!r} not available."

    def _call(self, system: str, user: str) -> RawResponse:
        payload: dict = {
            "model": self.model_requested,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            # Qwen3 is a reasoning model. Left to itself it emits a long
            # <think> block that Ollama returns in message.thinking, and on a
            # 300-token budget it never reaches message.content at all: the
            # first smoke run produced 4 empty responses out of 5, each stopping
            # at exactly num_predict. Disabling it is also the comparable
            # condition, since tier 1 is a plain completion with no extended
            # reasoning enabled. Pass think=True to measure the difference; it
            # lands under a separate judge_id.
            "think": self.think,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        if self.schema:
            payload["format"] = VERDICT_SCHEMA

        try:
            r = httpx.post(f"{self.host}/api/chat", json=payload,
                           headers=self._headers(), timeout=self.timeout)
        except httpx.ConnectError as exc:
            raise JudgeError(f"{self.judge_id}: {self._connect_hint()}") from exc
        except httpx.HTTPError as exc:
            raise JudgeError(f"{self.judge_id} transport: {exc}", retryable=True) from exc

        if r.status_code in (401, 403):
            raise JudgeError(
                f"{self.judge_id}: not authorised ({r.status_code}). "
                f"Run `ollama signin`, or set OLLAMA_API_KEY in .env."
            )
        if r.status_code == 404:
            raise JudgeError(f"{self.judge_id}: {self._not_found_hint()}")
        if r.status_code == 429:
            # Retryable, but the in-place retries only cover a burst. The free
            # plan's *session* limit ran for roughly two hours on 08.08.2026 and
            # is outlasted by the launcher's progressive backoff, not here.
            raise JudgeError(
                f"{self.judge_id}: rate limited or quota exhausted (429). "
                f"{r.text[:200]}",
                retryable=True,
            )
        if r.status_code >= 400:
            raise JudgeError(f"{self.judge_id}: HTTP {r.status_code}: {r.text[:300]}")

        body = r.json()
        msg = body.get("message") or {}
        content = msg.get("content", "")
        thinking = msg.get("thinking") or ""

        # An empty content with a non-empty thinking block means the budget was
        # spent reasoning. Say so in the stored error rather than leaving a bare
        # "empty response", which hides the cause.
        if not content.strip() and thinking:
            content = (
                f"[NO ANSWER: {body.get('eval_count')} tokens spent in <think>, "
                f"content empty. thinking begins: {thinking[:200]!r}]"
            )

        return RawResponse(
            text=content,
            model_version=body.get("model"),
            latency_ms=0,
            input_tokens=body.get("prompt_eval_count"),
            output_tokens=body.get("eval_count"),
        )
