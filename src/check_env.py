"""Check that every tier can actually answer. Run this before any real run.

    python3 src/check_env.py

Sends one tiny request per tier and reports what came back. Costs a fraction of
a cent on tier 1 and nothing on the others. Closes Gate C.

Prints only whether a key is present and its last four characters, never the key
itself, so the output is safe to paste into a chat or a screencast.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import adapters  # noqa: E402
from adapters import JudgeError  # noqa: E402

#: The probe uses the *real* rubric on a trivial item rather than asking the
#: model to echo a fixed string. An echo prompt made Opus 5 spot a typo in the
#: string it was told to repeat and narrate the correction, emitting two JSON
#: objects and failing the parser, while the same model handled the actual
#: judging contract cleanly. A probe that does not exercise the real contract
#: reports failures the study will never see, and hides ones it will.
def _probe() -> tuple[str, str]:
    from rubric import render  # noqa: PLC0415

    return render(
        source="The cat sat on the mat. It was a sunny afternoon in June.",
        summary="The cat sat on the mat.",
    )

KEYS = {
    "paid": "ANTHROPIC_API_KEY",
    "hosted": "OLLAMA_API_KEY",
    "local": None,
    "free": "GOOGLE_API_KEY",  # not an arm, the dev-only free-tier anchor
}


def masked(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        return "MISSING"
    return f"set, ends ...{val[-4:]}" if len(val) > 8 else "set, very short"


def main() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    print("=" * 62)
    print("GATE C: can all three tiers answer?")
    print("=" * 62)
    print(f"\n.env file : {env_file}")
    print(f"           {'found' if env_file.exists() else 'NOT FOUND'}\n")

    for tier, key in KEYS.items():
        print(f"  {tier + ':':<8} key {masked(key) if key else 'not required (local)'}")

    print()
    failures = 0
    for tier in adapters.ALL_TIERS:
        judge = adapters.build(tier)
        arm = "arm " if tier in adapters.TIERS else "aux "
        label = f"{arm}{tier} ({judge.model_requested})"
        try:
            resp = judge.judge(*_probe())
        except JudgeError as exc:
            if tier in adapters.TIERS:
                failures += 1  # only the three arms block Gate C
            print(f"  [FAIL] {label}\n         {exc}")
            continue

        from rubric import ParseError, parse  # noqa: PLC0415

        try:
            parse(resp.text)
            verdict = "parsed cleanly"
        except ParseError as exc:
            verdict = f"UNPARSEABLE: {exc}"
        print(f"  [ OK ] {label}")
        print(f"         version={resp.model_version}  {resp.latency_ms}ms  {verdict}")

    print()
    if failures:
        print(f"{failures} of {len(adapters.TIERS)} arms not ready. "
              f"Fix the keys above, then re-run.")
        raise SystemExit(1)
    print("All three arms answered. Gate C is closed.")
    print("(aux tiers are not arms; a failure there does not block the study.)")


if __name__ == "__main__":
    main()
