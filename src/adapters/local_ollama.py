"""Tier 3: local open-weights, executed on the researcher's own machine.

Ollama chat API on localhost. No key, no network, no per-token cost. This is the
tier that decides whether automated quality assurance is available at all to an
organisation that may not transmit data to an external provider, which is the
common situation for regulated firms in the German-speaking market.

Model choice, settled 06.08.2026 after two revisions
----------------------------------------------------
``gpt-oss:20b``, 13 GB, the same family and generation as tier 2's
``gpt-oss:120b-cloud`` at roughly a sixth of the parameters.

Holding family and generation fixed across tiers 2 and 3 turns that contrast
into a controlled comparison of *scale* rather than a confound of vendor,
architecture, generation and size at once. That is what separates "open weights
judge badly" from "what fits on a laptop judges badly", and only the second is a
statement about local deployment.

The route here is worth recording, because two earlier choices were wrong:

* ``qwen3:14b`` was chosen on capability alone, before tier 2 was open-weights,
  so it controlled for nothing.
* ``qwen3.5:9b`` was chosen to match a planned ``qwen3.5:397b-cloud`` tier 2.
  Probing on 06.08.2026 showed 397b is subscription-gated and **no qwen3.5 below
  397b is served on Ollama Cloud at all**, so that pairing cannot be built on the
  free plan. It also measured badly on the 8-item stratified pilot: 3/8 overall
  and TPR 0/4, passing every unfaithful summary including two Unwanted ones. A
  judge that never says no is the degenerate case this study exists to detect.

``gpt-oss:20b`` measured 5/8 with TPR 1/4 on the same draw, still weak but not
degenerate, and it uses the 24 GB machine properly where the 6.6 GB qwen did not.
A tier meant to represent "the best a team can run locally" should use the
hardware.

Cost: 21.5 s per judgment against qwen3.5:9b's 4.3 s, so the full 2,250 is about
13 hours rather than 3. That is one unattended overnight run, and the runner is
resumable, so it is a scheduling detail rather than a constraint.

Yang, Hou and Yang (2026) audited Qwen3 dense judges from 1.7B to 32B and found
only the 1.7B-to-4B step gave a robust adjacent gain. That prior now applies to
the family this tier no longer uses, so it moves from a design justification to
a comparison point in the Diskussion.

Structured output, and a trap
-----------------------------
Ollama can constrain generation to a JSON schema via ``format``. That would
repair almost any parse failure on this tier.

**It is off by default and must stay off for the main run.** The parse-failure
rate is a reported statistic, and constraining one tier while leaving the others
unconstrained would manufacture a difference between them. Run all three
unconstrained, report the failure rates honestly, then optionally re-run this
tier with ``schema=True`` and report that separately. "The local tier needed
schema-constrained decoding to be usable" is a genuine finding about what
on-premise deployment costs.
"""

from __future__ import annotations

from ._ollama_chat import VERDICT_SCHEMA, OllamaChatJudge  # noqa: F401

__all__ = ["LocalJudge", "VERDICT_SCHEMA"]


class LocalJudge(OllamaChatJudge):
    judge_id = "tier3_local"
    model_requested = "gpt-oss:20b"
    rate_limit_rpm = None  # local, the machine is the only limit
    default_host = "http://localhost:11434"

    def _connect_hint(self) -> str:
        return f"cannot reach Ollama at {self.host}. Run `ollama serve`."

    def _not_found_hint(self) -> str:
        return (f"model {self.model_requested!r} not pulled. "
                f"Run `ollama pull {self.model_requested}`.")
