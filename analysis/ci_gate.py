"""Continuous evaluation gate. Run in CI on every push.

    python analysis/ci_gate.py

This is a regression test on the published result. The judgment store is
committed, so every statistic in the README is deterministic from it: the same
store and the same code must produce the same numbers forever. If they do not,
either the analysis changed or the store did, and both are things a reader of
this repository deserves to be told about by a red build rather than by finding
a discrepancy themselves.

Three classes of assertion, in increasing order of what they would catch.

1. **Integrity.** The prompt freeze held, no model drifted mid-run, and the
   judgment counts are what the paper claims. These fail if the store is
   replaced or truncated.
2. **Reproduction.** Raw agreement, Cohen's kappa, recall and flag rate for all
   three arms reproduce to three decimal places. These fail if the analysis
   code changes behaviour.
3. **The headline claim.** Every arm flags less often than the corpus is
   actually unfaithful, which is the finding the whole paper rests on. This
   fails if the result itself stops holding.

No API keys and no spend: the gate reads cached judgments. That is a property of
the cache-everything design rather than a workaround, and it is the reason
continuous evaluation is affordable here at all.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "analysis"))

from loader import load_samples  # noqa: E402
from runner import RELEASE, split_corpus  # noqa: E402
from stats import ARMS, SCHEMES, stats  # noqa: E402

DB = ROOT / "data" / "main.sqlite"
TOL = 5e-4  # three decimal places, the precision the README quotes

#: Frozen at the test read, commit 828fb4d. Changing a number here without a
#: corresponding change to the README and the paper is exactly the drift this
#: gate exists to catch.
EXPECTED = {
    "prompt": ("v0.2", "3b14635aa1c3eecd"),
    "models": {
        "tier1_paid": "claude-opus-5",
        "tier2_hosted_open": "gpt-oss:120b-cloud",
        "tier3_local": "gpt-oss:20b",
        "tier2_free": "gemini-3.5-flash-lite",
    },
    "counts": {
        "tier1_paid": 2250,
        "tier2_hosted_open": 2250,
        "tier3_local": 2250,
        "tier2_free": 262,
    },
    "test_uq": {
        #                     raw    kappa    tpr     flag
        "tier1_paid": (0.466, 0.129, 0.253, 0.196),
        "tier2_hosted_open": (0.514, 0.162, 0.349, 0.280),
        "tier3_local": (0.473, 0.131, 0.269, 0.211),
    },
    "true_unfaithful_rate": 0.686,
}

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(label)


def close(got: float, want: float, label: str) -> None:
    check(label, abs(got - want) <= TOL, f"got {got:.3f}, expected {want:.3f}")


def main() -> int:
    if not DB.exists():
        print(f"FATAL: {DB} is missing. The judgment store must be committed.")
        return 1
    if not RELEASE.exists():
        print(f"FATAL: {RELEASE} is missing. Run: python data/download_faithbench.py")
        return 1

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = list(con.execute("SELECT * FROM judgments"))

    print("\n1. INTEGRITY\n")
    prompts = {(r["prompt_version"], r["prompt_hash"]) for r in rows}
    check(
        "prompt freeze held: exactly one (version, hash) over the whole store",
        prompts == {EXPECTED["prompt"]},
        f"{sorted(prompts)}",
    )
    served = {(r["judge_id"], r["model_version"]) for r in rows}
    check(
        "no model drift: one served version per judge",
        served == set(EXPECTED["models"].items()),
        f"{len(served)} distinct (judge, version) pairs",
    )
    for judge, want in EXPECTED["counts"].items():
        got = sum(1 for r in rows if r["judge_id"] == judge)
        check(f"judgment count, {judge}", got == want, f"got {got}, expected {want}")
    check("total judgments", len(rows) == 7012, f"got {len(rows)}")

    print("\n2. REPRODUCTION  (test split, scheme U+Q, the primary result)\n")
    ref = {s.uid: s for s in split_corpus(load_samples(RELEASE))["test"]}
    check("test split size", len(ref) == 488, f"got {len(ref)}")
    pos, neg = SCHEMES["U+Q"]

    for judge in ARMS:
        pairs = []
        for r in rows:
            if r["judge_id"] != judge or not r["parse_ok"] or r["item_uid"] not in ref:
                continue
            lab = ref[r["item_uid"]].summary_label()
            if lab in pos:
                pairs.append((True, bool(r["unfaithful"])))
            elif lab in neg:
                pairs.append((False, bool(r["unfaithful"])))
        s = stats(pairs)
        raw, kap, tpr, flag = EXPECTED["test_uq"][judge]
        close(s["raw"], raw, f"{judge}: raw agreement")
        close(s["kappa"], kap, f"{judge}: Cohen's kappa")
        close(s["tpr"], tpr, f"{judge}: recall on unfaithful items")
        close(s["flag"], flag, f"{judge}: flag rate")

    print("\n3. THE HEADLINE CLAIM\n")
    truth = EXPECTED["true_unfaithful_rate"]
    for judge in ARMS:
        flag = EXPECTED["test_uq"][judge][3]
        check(
            f"{judge} under-flags against a {truth:.1%} true unfaithful rate",
            flag < truth,
            f"flags {flag:.1%}",
        )
    worst = max(EXPECTED["test_uq"][j][3] for j in ARMS)
    check(
        "a gate threshold band exists where every arm ships what truth blocks",
        worst < truth,
        f"band {worst:.1%} to {truth:.1%}, {100 * (truth - worst):.1f} points wide",
    )

    print()
    if failures:
        print(f"GATE FAILED: {len(failures)} check(s)\n")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("GATE PASSED: the published result reproduces from the committed store.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
