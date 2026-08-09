"""Tier 0: a fake judge, for building and testing the pipeline without keys.

Not part of the study. It exists so runner, store and caching can be exercised
end to end before any money is spent, and so the test suite has something
deterministic to run against.

Its verdicts are a hash of the summary text, which makes them reproducible and
meaningless. It also emits malformed output on a fixed fraction of calls, so the
parse-failure path is exercised rather than assumed to work.
"""

from __future__ import annotations

import hashlib

from . import JudgeAdapter, RawResponse


class MockJudge(JudgeAdapter):
    judge_id = "tier0_mock"
    model_requested = "mock-v1"

    def __init__(self, break_every: int = 17, **kw) -> None:
        """`break_every`: emit unparseable output on every Nth item. 0 disables."""
        super().__init__(**kw)
        self.break_every = break_every

    def _call(self, system: str, user: str) -> RawResponse:
        digest = hashlib.sha256(user.encode("utf-8")).digest()
        n = int.from_bytes(digest[:4], "big")

        if self.break_every and n % self.break_every == 0:
            text = "I am not sure I can answer that in the requested format."
        else:
            unfaithful = bool(n % 3)
            verdict = "UNFAITHFUL" if unfaithful else "FAITHFUL"
            span = '"a fabricated detail"' if unfaithful else "null"
            text = (
                f'{{"verdict": "{verdict}", "span": {span}, '
                f'"reason": "deterministic mock verdict, carries no information"}}'
            )

        return RawResponse(
            text=text,
            model_version="mock-v1",
            latency_ms=0,
            input_tokens=len(system + user) // 4,
            output_tokens=len(text) // 4,
        )
