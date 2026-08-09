"""Validate our aggregation against the benchmark authors' own sample-level labels.

FaithBench ships two things we can check ourselves against:

1. ``scripts/binarize.py``, the authors' aggregation code, which encodes the
   severity order (Benign 1 < Questionable 2 < Unwanted 3) and whose default
   ``aggregation_strategy="worst"`` is the same most-severe-wins rule we use.
2. ``FaithBench.csv``, which ships pre-computed ``worst-label`` and
   ``best-label`` per item for all 16 batches.

If ``loader.summary_label()`` reproduces their ``worst-label``, the aggregation
is right. If it does not, something is wrong with ours and every downstream
statistic is suspect. This runs in a second and belongs in the appendix.

    python3 analysis/validate_loader.py
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loader import PASS_CANONICAL, PASS_STRICT, SEVERITY, load_samples  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "data/raw/FaithBench"

# The CSV carries no sample_id, so the join is on text. Truncating keeps the key
# cheap; collisions are detected rather than silently resolved.
_KEY_LEN = 300


def _key(source: str, summary: str) -> tuple[str, str]:
    return source.strip()[:_KEY_LEN], summary.strip()[:_KEY_LEN]


def main() -> None:
    samples = load_samples(ROOT / "data_for_release")
    rows = list(csv.DictReader(open(ROOT / "FaithBench.csv", encoding="utf-8")))

    print("=" * 68)
    print("VALIDATION: our aggregation vs the authors' shipped worst-label")
    print("=" * 68)
    print(f"\n  release samples : {len(samples)}  (15 batches; batch 13 absent)")
    print(f"  CSV rows        : {len(rows)}  (all 16 batches, so 50 items we cannot use:")
    print("                     the CSV gives their labels but not the span annotations,")
    print("                     so batch 13 has no annotator information and is excluded)")

    theirs: dict[tuple[str, str], set[str]] = {}
    for r in rows:
        theirs.setdefault(_key(r["source"], r["summary"]), set()).add(r["worst-label"])

    agree = disagree = ambiguous = unmatched = 0
    pairs: Counter[tuple[str, str]] = Counter()
    for s in samples:
        k = _key(s.source, s.summary)
        if k not in theirs:
            unmatched += 1
            continue
        if len(theirs[k]) > 1:      # key collision, not a disagreement
            ambiguous += 1
            continue
        their_label = next(iter(theirs[k]))
        if their_label == s.summary_label():
            agree += 1
        else:
            disagree += 1
            pairs[(s.summary_label(), their_label)] += 1

    joinable = agree + disagree
    print(f"\n  joinable rows   : {joinable}")
    print(f"  agree           : {agree}")
    print(f"  disagree        : {disagree}")
    print(f"  ambiguous key   : {ambiguous}  (same 300-char prefix maps to >1 CSV label)")
    print(f"  unmatched       : {unmatched}")
    if pairs:
        print("\n  disagreements (ours -> theirs):")
        for (mine, their), n in pairs.most_common():
            print(f"    {mine:<14} -> {their:<14} {n}")
    print(f"\n  AGREEMENT: {100 * agree / joinable:.2f}%")

    # --- the two binarisations ------------------------------------------
    print("\n" + "=" * 68)
    print("BINARISATION: canonical (authors' default) vs strict")
    print("=" * 68)
    dist = Counter(s.summary_label() for s in samples)
    print(f"\n  {'label':<14} {'n':>5}")
    for lab in SEVERITY:
        print(f"  {lab:<14} {dist[lab]:>5}")

    n = len(samples)
    print(f"\n  {'rule':<34} {'PASS':>6} {'FAIL':>6} {'constant-judge':>16}")
    for name, ps in (
        ("canonical (Consistent+Benign pass)", PASS_CANONICAL),
        ("strict    (Consistent only passes)", PASS_STRICT),
    ):
        n_pass = sum(1 for s in samples if s.is_faithful(ps))
        n_fail = n - n_pass
        print(f"  {name:<34} {n_pass:>6} {n_fail:>6} {100 * max(n_pass, n_fail) / n:>15.1f}%")

    print("\n  The authors' released binarize.py sets hallucinated_classes to")
    print("  [Questionable, Unwanted, Unwanted_Intrinsic, Unwanted_Extrinsic],")
    print("  so Benign counts as faithful. Following it keeps our numbers comparable")
    print("  with everything published on this benchmark. Strict is reported as a")
    print("  sensitivity analysis rather than as the headline.")


if __name__ == "__main__":
    main()
