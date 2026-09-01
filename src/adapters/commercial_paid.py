"""Tier 1: commercial premium, a frontier model behind a paid developer API.

Anthropic Messages API. Plain HTTP via httpx rather than the vendor SDK, so all
three tiers are structurally identical and the appendix can show one request
shape per tier without SDK indirection in the way.

Key: ANTHROPIC_API_KEY. This is a Console key and is billed separately from any
Claude Pro subscription, which does not carry API credit.

Costs roughly 11 EUR for the 2,250 billable judgments in this study.
"""

from __future__ import annotations

import httpx

from . import JudgeAdapter, JudgeError, RawResponse, _require_env

ENDPOINT = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class PaidJudge(JudgeAdapter):
    judge_id = "tier1_paid"

    #: Opus 5, not Sonnet 5, decided 06.08.2026.
    #:
    #: Tier 1 is defined as "the organisation has a budget and buys the best".
    #: Opus is the frontier model; Sonnet is the mid-tier one. The paper's likely
    #: headline is that even the strongest available judge misses a large share
    #: of unfaithful summaries, and that claim only holds if the strongest one
    #: was actually run. Measured cost difference over the full 2,250 judgments
    #: is about 8 EUR (19 against 10 at intro pricing), which is not a constraint
    #: at this scale and does not justify weakening the central claim.
    model_requested = "claude-opus-5"

    rate_limit_rpm = None  # paid tier limits are far above what this study needs

    #: Sending `temperature` to claude-sonnet-5 returns HTTP 400,
    #: "`temperature` is deprecated for this model" (observed 06.08.2026).
    #:
    #: The other two tiers are pinned to temperature 0, so the three cannot be
    #: equalised on sampling. This must be stated in the method chapter rather
    #: than glossed: tier 1's three repeats measure whatever the provider's
    #: default sampling does, not a temperature this study chose. It also makes
    #: the within-judge variance figures not strictly comparable across tiers,
    #: which is worth a sentence in the Diskussion. A provider withdrawing a
    #: reproducibility control is precisely the kind of drift this paper is about.
    supports_temperature = False

    def __init__(self, think: bool = True, effort: str = "high", **kw) -> None:
        kw.setdefault("max_tokens", 1000)
        # 120s was too tight and cost an eight hour run on 08.08.2026. Opus 5
        # with adaptive reasoning on a full-length source is occasionally slow,
        # and a timeout here is not a finding about the tier, it is a lost
        # judgment. Raised well above the observed worst case.
        kw.setdefault("timeout", 300.0)
        super().__init__(**kw)
        self.think = think
        self.effort = effort
        if not think:
            # Reasoning ON is the primary condition, so it carries the clean
            # judge_id and the ablation is the one that is marked.
            self.judge_id += "_nothink"

    def _call(self, system: str, user: str) -> RawResponse:
        key = _require_env("ANTHROPIC_API_KEY")
        payload: dict = {
            "model": self.model_requested,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            # Omitting `thinking` does NOT mean "no thinking" on Sonnet 5 or
            # Opus 5: both run adaptive thinking by default. Left implicit, tier 1
            # would reason while tiers 2 and 3 ran with think=False, which is an
            # uncontrolled variable sitting on the study's central comparison.
            # It is therefore always sent explicitly, in both directions.
            "thinking": {"type": "adaptive"} if self.think else {"type": "disabled"},
            # Disabled thinking is rejected above effort "high" on Opus 5, so the
            # level is pinned rather than left to the provider's default.
            "output_config": {"effort": self.effort},
        }
        if self.supports_temperature:
            payload["temperature"] = self.temperature
        try:
            r = httpx.post(
                ENDPOINT,
                headers={
                    "x-api-key": key,
                    "anthropic-version": API_VERSION,
                    "content-type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise JudgeError(f"tier1 transport: {exc}", retryable=True) from exc

        if r.status_code == 401:
            raise JudgeError("tier1: ANTHROPIC_API_KEY rejected (401)")
        if r.status_code == 429:
            raise JudgeError("tier1: rate limited (429)", retryable=True)
        if r.status_code >= 400:
            raise JudgeError(f"tier1: HTTP {r.status_code}: {r.text[:300]}")

        body = r.json()
        content = body.get("content", [])
        blocks = [b.get("text", "") for b in content if b.get("type") == "text"]
        usage = body.get("usage") or {}

        # With thinking on, reasoning arrives as separate `thinking` blocks and
        # is billed as output. If it consumed the whole budget before any text
        # block, say so in the stored response rather than leaving a bare empty
        # string, exactly as the Ollama tiers do.
        text = "".join(blocks)
        if not text.strip() and any(b.get("type") == "thinking" for b in content):
            text = (
                f"[NO ANSWER: {usage.get('output_tokens')} output tokens spent, "
                f"thinking blocks present, no text block. "
                f"stop_reason={body.get('stop_reason')}]"
            )

        return RawResponse(
            text=text,
            # What the API actually served, which may differ from the alias we
            # asked for. store.version_drift() compares the two.
            model_version=body.get("model"),
            latency_ms=0,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
