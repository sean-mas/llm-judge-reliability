"""One interface, one module per deployment tier.

The tiers are chosen by *how an organisation runs a judge*, not by capability
ranking. That is the research question, so the interface deliberately hides
everything except what all three have in common: send a system and a user
message, get text back.

Every adapter must:

* declare a stable ``judge_id`` that never changes across the study, because it
  is a grouping key in the stored data;
* declare ``model_requested``, the string we ask for, which is part of the cache
  key;
* return ``model_version``, the string the provider says it actually used,
  which is what reproducibility depends on and what drift detection compares;
* raise ``JudgeError`` on transport failure rather than returning a fake answer.

Temperature is 0 everywhere by default. Production judges are run at 0, and the
three repeats are there to measure the residual nondeterminism that remains even
then. "The judge is not deterministic at temperature 0" is a stronger and more
relevant finding than variance deliberately injected by sampling.
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


class JudgeError(RuntimeError):
    """Transport, auth, or rate-limit failure. Never a parse failure.

    ``retryable`` marks the failures that say nothing about the tier and are
    worth another attempt: a read timeout, a dropped connection, a 429. A 401 or
    a 404 is a fact about the configuration and is raised straight through, since
    retrying it only wastes time and hides the cause.
    """

    def __init__(self, *args: object, retryable: bool = False) -> None:
        super().__init__(*args)
        self.retryable = retryable


@dataclass(frozen=True)
class RawResponse:
    text: str
    model_version: str | None
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class JudgeAdapter(ABC):
    """Base class. Subclasses implement `_call` only."""

    judge_id: str
    model_requested: str
    #: Requests per minute this tier tolerates. None means no throttling.
    rate_limit_rpm: int | None = None

    def __init__(self, model: str | None = None, temperature: float = 0.0,
                 max_tokens: int = 300, timeout: float = 120.0) -> None:
        if model:
            self.model_requested = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._last_call = 0.0

    #: In-place retries for transient transport failures. Added 08.08.2026 after
    #: a single read timeout on judgment 1,163 of 2,250 aborted an eight hour
    #: tier 1 run. The store made that recoverable, but recovering cost the rest
    #: of the evening, and one flaky socket should not end a run. Only errors
    #: flagged ``retryable`` qualify; a 401 or an unparseable body is a finding
    #: about the tier and is never retried into a fake success.
    max_transport_retries: int = 3

    def judge(self, system: str, user: str) -> RawResponse:
        """Send one judgment request, throttled if the tier needs it."""
        for attempt in range(self.max_transport_retries + 1):
            if self.rate_limit_rpm:
                min_gap = 60.0 / self.rate_limit_rpm
                elapsed = time.monotonic() - self._last_call
                if self._last_call and elapsed < min_gap:
                    time.sleep(min_gap - elapsed)
            start = time.monotonic()
            try:
                resp = self._call(system, user)
                break
            except JudgeError as exc:
                if not getattr(exc, "retryable", False) or attempt == self.max_transport_retries:
                    raise
                time.sleep(2.0 ** attempt)
            except Exception as exc:
                raise JudgeError(f"{self.judge_id}: {type(exc).__name__}: {exc}") from exc
            finally:
                self._last_call = time.monotonic()
        return RawResponse(
            text=resp.text,
            model_version=resp.model_version,
            latency_ms=int((time.monotonic() - start) * 1000),
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )

    @abstractmethod
    def _call(self, system: str, user: str) -> RawResponse:
        """Provider-specific request. Latency is filled in by `judge`."""

    def describe(self) -> str:
        return f"{self.judge_id} ({self.model_requested}, temp={self.temperature})"


def load_dotenv(path: str | None = None) -> int:
    """Read the project's .env into os.environ. Returns the number of keys set.

    Stdlib only, no python-dotenv dependency. Real environment variables always
    win, so `GOOGLE_API_KEY=... python3 src/runner.py ...` still overrides the
    file. Called automatically on import so no one has to remember to source it.
    """
    from pathlib import Path

    env_path = Path(path) if path else Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return 0
    n = 0
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if value and key not in os.environ:
            os.environ[key] = value
            n += 1
    return n


load_dotenv()


def _require_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise JudgeError(
            f"{name} is empty. Open faithbench-judge-study/.env and paste the key "
            f"after '{name}='. Then check it with: python3 src/check_env.py"
        )
    return val


def build(tier: str, **kw) -> JudgeAdapter:
    """Factory. Keeps runner.py free of provider imports."""
    if tier == "mock":
        from .mock import MockJudge
        return MockJudge(**kw)
    if tier == "paid":
        from .commercial_paid import PaidJudge
        return PaidJudge(**kw)
    if tier == "hosted":
        from .cloud_ollama import HostedOpenJudge
        return HostedOpenJudge(**kw)
    if tier == "local":
        from .local_ollama import LocalJudge
        return LocalJudge(**kw)
    if tier == "free":
        from .commercial_free import FreeTierJudge
        return FreeTierJudge(**kw)
    raise ValueError(
        f"unknown tier {tier!r}; expected one of {', '.join(ALL_TIERS)} or mock"
    )


#: The three arms of the study, by deployment model.
#:
#:   paid    proprietary frontier, billed API          data leaves, costs money
#:   hosted  open weights, too big for local, rented   data leaves, weights known
#:   local   open weights, on our own machine          data never leaves, free
#:
#: Ordered by decreasing data exposure, which is the axis the paper argues along.
TIERS = ("paid", "hosted", "local")

#: Not an arm. The free-tier proprietary judge that tier 2 used to be, kept as a
#: dev-split-only anchor so the free-tier quota finding (20 requests per day on
#: the full-size Flash models) stays empirically grounded rather than asserted.
#: Never pool this with TIERS in analysis.
EXTRA_TIERS = ("free",)

ALL_TIERS = TIERS + EXTRA_TIERS

#: Tiers served by the Ollama chat API, which alone accept schema= and think=.
OLLAMA_TIERS = ("hosted", "local")
