"""Tier 2: hosted open-weights, a large open model served on rented infrastructure.

Ollama Cloud. Same chat API as tier 3, different host and a bearer token.

Why this replaced the free-tier proprietary judge (decided 06.08.2026)
----------------------------------------------------------------------
The original tier 2 was Google's free-tier Gemini. It answered "what does a team
with no budget get", but it left the design with two of three tiers in the same
cell, hosted and proprietary, differing only on price, and left the cell that
most compliance-constrained organisations actually occupy empty: **open weights,
too large for local hardware, served on infrastructure the organisation rents.**

Three consequences, all of which favour the change:

* It fills the empty cell. Paid-frontier / hosted-open / local-open covers the
  deployment space a product team actually chooses between.
* It makes tier 2 versus tier 3 a controlled comparison. Same family, same
  generation, ~9B against ~397B, so the contrast isolates scale.
* It *improves* reproducibility rather than harming it. ``gemini-3.5-flash-lite``
  cannot be re-run once Google retires it and its weights are secret. Anyone can
  obtain ``qwen3.5:397b`` and reproduce these numbers. For a study whose subject
  includes version drift, an arm with archivable weights is an asset.

What this tier is *not*
-----------------------
Ollama Cloud is a managed service on Ollama's GPUs, not a self-hosted deployment
in the organisation's own VPC. For a study measuring **judge quality** that
distinction does not affect the result, because the weights determine the
verdicts and the weights are the same ones a self-hoster would run. It does mean
no claim about latency, cost per token or throughput may be transferred from
this tier to a self-hosted setting. The limitations section says so explicitly.

Quota is the open risk. Ollama bills cloud usage by GPU time with session and
weekly windows and publishes no fixed request numbers, so unlike Gemini's RPM
and RPD this tier's limits cannot be cited. Whatever the pilot measures is
recorded in appendix/versions.md as an observation, not as a documented figure.
gpt-oss is a reasoning model and emitted ~490 output tokens per judgment against
Gemini's ~45, roughly ten times the work per item, so the GPU-time budget is
consumed faster than the request count suggests.

Model retirement is not hypothetical on this host. Probing ``qwen3-coder:480b``
on 06.08.2026 returned HTTP 410, "was retired at 2026-07-15": a dated, citable
instance of a tag that resolved and no longer does. Worth a sentence in the
Diskussion, since it is the paper's own subject observed on its own instruments.

Auth: ``OLLAMA_API_KEY`` from ollama.com/settings/keys, or ``ollama signin``,
which writes a key the CLI uses but which this adapter cannot read; the env var
is required for the harness.
"""

from __future__ import annotations

import os

from . import _require_env
from ._ollama_chat import OllamaChatJudge


class HostedOpenJudge(OllamaChatJudge):
    judge_id = "tier2_hosted_open"

    #: Same family and generation as tier 3, roughly 6x the parameters.
    #:
    #: The first choice was qwen3.5:397b-cloud, for a 44x scale gap against a
    #: qwen3.5:9b local tier. Probed 06.08.2026: it returns HTTP 403, "this model
    #: requires a subscription", and **no qwen3.5 below 397b is served on cloud
    #: at all** (9b/27b/35b/122b are download-only tags). So the matched-family
    #: qwen design is unavailable without the paid plan, not merely expensive.
    #:
    #: Free-plan models, measured by probing all 18 advertised tags:
    #:     gpt-oss:20b, gpt-oss:120b, gemma4:31b, minimax-m3,
    #:     nemotron-3-nano:30b, nemotron-3-super, nemotron-3-ultra
    #: Subscription-gated: qwen3.5:397b, deepseek-v4-*, glm-5.1, glm-5.2,
    #:     kimi-k2.6, kimi-k2.7-code, kimi-k3, minimax-m2.7, mistral-large-3:675b
    #:
    #: gpt-oss is the only family with both a cloud tag and a locally runnable
    #: tag, so it is the only free way to keep tiers 2 and 3 on one family and
    #: one generation. That control is worth more here than the wider scale gap.
    model_requested = "gpt-oss:120b-cloud"

    default_host = "https://ollama.com"

    #: Unpublished. Set conservatively until the pilot measures the real ceiling;
    #: override with OLLAMA_CLOUD_RPM once there is evidence.
    rate_limit_rpm = int(os.environ.get("OLLAMA_CLOUD_RPM", "20"))

    def _env_host(self) -> str | None:
        # Deliberately does NOT read OLLAMA_HOST: that variable points at the
        # local server, and inheriting it here would silently run tier 2 on the
        # laptop and record it as the hosted tier.
        return os.environ.get("OLLAMA_CLOUD_HOST")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {_require_env('OLLAMA_API_KEY')}"}

    def _connect_hint(self) -> str:
        return f"cannot reach Ollama Cloud at {self.host}."

    def _not_found_hint(self) -> str:
        return (f"model {self.model_requested!r} not available on Ollama Cloud. "
                f"Check ollama.com/search?c=cloud for the current tag.")
