"""Tier 2: commercial free tier, a hosted model available at no cost.

Google AI Studio, Gemini generateContent. Key from aistudio.google.com.

Two constraints shape this adapter and both belong in the paper.

Throughput. The free tier allows roughly 15 requests per minute, so the 2,250
judgments of this tier need days of wall clock rather than hours. The adapter
throttles itself rather than relying on the caller to be careful.

Data use. Free-tier inputs may be used to improve Google's products. That is
acceptable here only because FaithBench is public, and it is declared in the
limitations section rather than left implicit.

Since 01.04.2026 the Pro series is no longer on the free tier, so this slot is a
cheap-model tier rather than a second frontier model. That is a deliberate part
of the design, not a compromise: the question is what a team with no budget
actually gets.
"""

from __future__ import annotations

import os

import httpx

from . import JudgeAdapter, JudgeError, RawResponse, _require_env

BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class FreeTierJudge(JudgeAdapter):
    judge_id = "tier2_free"

    # Model choice is dictated by the daily cap, not by capability.
    #
    # Read off this account's AI Studio dashboard on 06.08.2026, requests per day:
    #
    #     gemini-2.5-flash        RPM  5   RPD    20   <- unusable
    #     gemini-3.5-flash        RPM  5   RPD    20   <- unusable
    #     gemini-3.6-flash        RPM  5   RPD    20   <- unusable
    #     gemini-3.5-flash-lite   RPM 15   RPD   500   <- chosen
    #     gemini-3.1-flash-lite   RPM 15   RPD   500
    #     gemma-4-31b-it          RPM 30   RPD 14400
    #
    # At 20 requests per day the full-size Flash models need 112 days for this
    # study's 2,250 tier-2 judgments. Flash-Lite at 500 per day needs about five.
    #
    # Gemma is not chosen despite its far higher cap, because it is open-weights
    # and would collapse the distinction between this tier and tier 3. Tier 2 is
    # defined as a *proprietary hosted model available at no cost*, and that
    # definition is what the research question rests on.
    #
    # This is itself a finding for the Diskussion: the free tier does not merely
    # offer a weaker model, it offers a model whose quota makes systematic
    # evaluation impractical unless you pick the smallest variant on offer.
    model_requested = "gemini-3.5-flash-lite"

    rate_limit_rpm = int(os.environ.get("GEMINI_RPM", "15"))
    #: Daily request cap. The runner reports it; the tier needs several days.
    rate_limit_rpd = int(os.environ.get("GEMINI_RPD", "500"))

    def _call(self, system: str, user: str) -> RawResponse:
        key = _require_env("GOOGLE_API_KEY")
        try:
            r = httpx.post(
                f"{BASE}/{self.model_requested}:generateContent",
                headers={"x-goog-api-key": key, "content-type": "application/json"},
                json={
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    "generationConfig": {
                        "temperature": self.temperature,
                        "maxOutputTokens": self.max_tokens,
                    },
                },
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise JudgeError(f"tier2 transport: {exc}") from exc

        if r.status_code in (401, 403):
            raise JudgeError(f"tier2: GOOGLE_API_KEY rejected ({r.status_code})")
        if r.status_code == 429:
            raise JudgeError("tier2: free-tier quota exhausted (429), resume tomorrow")
        if r.status_code >= 400:
            raise JudgeError(f"tier2: HTTP {r.status_code}: {r.text[:300]}")

        body = r.json()
        candidates = body.get("candidates") or []
        if not candidates:
            # Usually a safety block. Real information about this tier, so it is
            # surfaced as an error rather than silently recorded as no verdict.
            raise JudgeError(f"tier2: no candidate returned: {str(body)[:300]}")

        parts = candidates[0].get("content", {}).get("parts", []) or []
        usage = body.get("usageMetadata") or {}
        return RawResponse(
            text="".join(p.get("text", "") for p in parts),
            model_version=body.get("modelVersion"),
            latency_ms=0,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
        )
