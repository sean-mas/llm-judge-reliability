"""The four analyses that turn agreement statistics into a production answer.

    .venv/bin/python analysis/production.py [--split dev]

Companion to `stats.py`, which reports how well each judge agrees with the human
labels. This module asks the question a practitioner actually has:

  4a. Detection by severity. Where in FaithBench's four levels do judges fail?
  4b. Threshold simulation. At which release thresholds does the judge's verdict
      diverge from the truth?
  4c. Rogan-Gladen. Can a judge's observed flag rate be corrected into a usable
      estimate of the true failure rate, given its measured TPR and TNR?
  4d. Stratification by annotator agreement. Does a judge err where the humans
      also disagreed, which is defensible, or where they agreed, which is not?

DEV SPLIT ONLY unless explicitly overridden, same discipline as `stats.py`.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loader import load_samples  # noqa: E402
from runner import RELEASE, split_corpus  # noqa: E402

DB = Path(__file__).resolve().parents[1] / "data" / "main.sqlite"
ARMS = ("tier1_paid", "tier2_hosted_open", "tier3_local")
AUX = ("tier2_free",)
POS = {"Unwanted", "Questionable"}          # primary scheme U+Q
LEVELS = ("Consistent", "Benign", "Questionable", "Unwanted")
BOOTSTRAP = 2000
SEED = 20260809


def agreement_stratum(sample) -> str:
    """How much did the humans agree about this item?

    Four strata, and the distinction matters for the error analysis: a judge that
    errs where two experts disagreed is behaving defensibly, one that errs where
    they agreed is not.
    """
    anns = sample.annotations
    if not anns:
        return "no annotation"
    if len({a.annotator_id for a in anns}) == 1:
        return "single annotator"
    labels = {frozenset(a.coarse_labels) for a in anns}
    return "unanimous" if len(labels) == 1 else "disagreed"


def rates(pairs: list[tuple[bool, bool]]) -> tuple[float, float, float]:
    """Return (TPR, TNR, observed flag rate)."""
    tp = sum(1 for t, p in pairs if t and p)
    fn = sum(1 for t, p in pairs if t and not p)
    tn = sum(1 for t, p in pairs if not t and not p)
    fp = sum(1 for t, p in pairs if not t and p)
    return (
        tp / (tp + fn) if tp + fn else float("nan"),
        tn / (tn + fp) if tn + fp else float("nan"),
        (tp + fp) / len(pairs) if pairs else float("nan"),
    )


def rogan_gladen(flag: float, tpr: float, tnr: float) -> float:
    """Correct an observed positive rate into an estimated true prevalence.

    prevalence = (observed + specificity - 1) / (sensitivity + specificity - 1)

    The denominator is Youden's J. As it approaches zero the estimator blows up,
    which is exactly the regime a weak judge sits in, so the interval matters far
    more than the point estimate here.
    """
    denom = tpr + tnr - 1.0
    if abs(denom) < 1e-9:
        return float("nan")
    return (flag + tnr - 1.0) / denom


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", default="dev", choices=("dev", "test"))
    ap.add_argument("--i-am-ready-to-spend-the-test-split", action="store_true")
    args = ap.parse_args()
    if args.split == "test" and not args.i_am_ready_to_spend_the_test_split:
        raise SystemExit("Refusing. See stats.py for why. Test is read once.")

    ref = {s.uid: s for s in split_corpus(load_samples(RELEASE))[args.split]}
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [r for r in con.execute("SELECT * FROM judgments")
            if r["item_uid"] in ref and r["parse_ok"]]

    def pairs_for(judge: str, uids: set[str] | None = None) -> list[tuple[bool, bool]]:
        return [
            (ref[r["item_uid"]].summary_label() in POS, bool(r["unfaithful"]))
            for r in rows
            if r["judge_id"] == judge and (uids is None or r["item_uid"] in uids)
        ]

    print("=" * 88)
    print(f"PRODUCTION ANALYSIS  |  split={args.split}  |  {len(ref)} items  |  scheme U+Q")
    print("=" * 88)

    # ---- 4a. detection by severity --------------------------------------
    print("\n4a. DETECTION BY SEVERITY LEVEL")
    print("    Of the items at each human severity level, how many did the judge flag?\n")
    counts = {lev: sum(1 for s in ref.values() if s.summary_label() == lev) for lev in LEVELS}
    print(f"    items per level: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    print(f"\n    {'judge':<20}" + "".join(f"{lev:>16}" for lev in LEVELS))
    for j in ARMS + AUX:
        cells = []
        for lev in LEVELS:
            rs = [r for r in rows if r["judge_id"] == j
                  and ref[r["item_uid"]].summary_label() == lev]
            if not rs:
                cells.append("n/a")
                continue
            flagged = sum(1 for r in rs if r["unfaithful"])
            cells.append(f"{100 * flagged / len(rs):.0f}% ({flagged}/{len(rs)})")
        mark = " " if j in ARMS else "*"
        print(f"   {mark}{j:<20}" + "".join(f"{c:>16}" for c in cells))
    print("\n    Consistent and Benign are faithful under U+Q, so a LOW number is correct.")
    print("    Questionable and Unwanted are unfaithful, so a HIGH number is correct.")

    # ---- 4b. threshold simulation ---------------------------------------
    print("\n" + "=" * 88)
    print("4b. RELEASE-GATE THRESHOLD SIMULATION")
    print("    A gate blocks the release when the flagged share exceeds a threshold T.")
    print("    The truth would block whenever T < the real unfaithful rate.\n")
    true_rate = sum(1 for s in ref.values() if s.summary_label() in POS) / len(ref)
    print(f"    true unfaithful rate ......... {100 * true_rate:.1f}%")
    for j in ARMS:
        _, _, flag = rates(pairs_for(j))
        print(f"    {j:<22} flags {100 * flag:>5.1f}%   "
              f"judge SHIPS but truth BLOCKS for T in [{100 * flag:.1f}%, {100 * true_rate:.1f}%)")
    lo = max(rates(pairs_for(j))[2] for j in ARMS)
    print(f"\n    For ANY threshold between {100 * lo:.1f}% and {100 * true_rate:.1f}%,")
    print(f"    all three judges ship a release that should have been blocked.")
    print(f"    That band is {100 * (true_rate - lo):.1f} percentage points wide.")

    # ---- 4c. Rogan-Gladen ------------------------------------------------
    print("\n" + "=" * 88)
    print("4c. ROGAN-GLADEN CORRECTION")
    print("    Judges are poor gates. Are they usable as meters, if calibrated?")
    print()
    print("    *** READ THIS BEFORE USING THE NUMBERS BELOW. ***")
    print("    Calibrating TPR and TNR on the same sample whose flag rate is then")
    print("    corrected is CIRCULAR. Substituting flag = TPR*p + (1-TNR)*(1-p)")
    print("    into the estimator returns p exactly, as algebra, for any judge")
    print("    however bad. The point estimates below are therefore an identity")
    print("    check on the implementation, NOT evidence that the method works.")
    print("    Only the interval width is informative here: it says how precisely")
    print("    a calibration set of this size pins the rate down.")
    print()
    print("    The non-circular version is calibrate-on-dev, apply-to-test, and it")
    print("    runs from `--split test`. That is the number the paper reports.\n")
    rng = random.Random(SEED)
    print(f"    {'judge':<20}{'flag':>8}{'TPR':>7}{'TNR':>7}{'J':>7}"
          f"{'corrected':>11}{'95% CI':>18}")
    for j in ARMS:
        by_item: dict[str, list[tuple[bool, bool]]] = {}
        for r in rows:
            if r["judge_id"] != j:
                continue
            by_item.setdefault(r["item_uid"], []).append(
                (ref[r["item_uid"]].summary_label() in POS, bool(r["unfaithful"])))
        tpr, tnr, flag = rates([p for v in by_item.values() for p in v])
        est = rogan_gladen(flag, tpr, tnr)
        uids = list(by_item)
        vals = []
        for _ in range(BOOTSTRAP):
            draw = [rng.choice(uids) for _ in uids]
            ps = [p for u in draw for p in by_item[u]]
            t2, n2, f2 = rates(ps)
            v = rogan_gladen(f2, t2, n2)
            if v == v:
                vals.append(v)
        vals.sort()
        lo_, hi_ = vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]
        print(f"    {j:<20}{100 * flag:>7.1f}%{tpr:>7.3f}{tnr:>7.3f}{tpr + tnr - 1:>7.3f}"
              f"{100 * est:>10.1f}%   [{100 * lo_:>5.1f}%,{100 * hi_:>6.1f}%]")
    print(f"\n    true rate for comparison: {100 * true_rate:.1f}%")
    print("    J = Youden's J = TPR + TNR - 1, the estimator's denominator.")
    print("    A small J means the correction is arithmetically unstable, so read")
    print("    the interval rather than the point estimate.")

    if args.split == "test":
        print("\n    --- NON-CIRCULAR: TPR and TNR calibrated on DEV, applied to TEST ---")
        dev_ref = {s.uid: s for s in split_corpus(load_samples(RELEASE))["dev"]}
        dev_rows = [r for r in con.execute("SELECT * FROM judgments")
                    if r["item_uid"] in dev_ref and r["parse_ok"]]
        print(f"    {'judge':<20}{'dev TPR':>9}{'dev TNR':>9}"
              f"{'test flag':>11}{'estimate':>11}{'true':>8}{'error':>8}")
        for j in ARMS:
            dev_pairs = [(dev_ref[r["item_uid"]].summary_label() in POS,
                          bool(r["unfaithful"]))
                         for r in dev_rows if r["judge_id"] == j]
            tpr_d, tnr_d, _ = rates(dev_pairs)
            _, _, flag_t = rates(pairs_for(j))
            est = rogan_gladen(flag_t, tpr_d, tnr_d)
            print(f"    {j:<20}{tpr_d:>9.3f}{tnr_d:>9.3f}{100 * flag_t:>10.1f}%"
                  f"{100 * est:>10.1f}%{100 * true_rate:>7.1f}%"
                  f"{100 * (est - true_rate):>+7.1f}pp")
        print("\n    This one is a real test: the calibration never saw these items.")

    # ---- 4d. stratification by annotator agreement -----------------------
    print("\n" + "=" * 88)
    print("4d. STRATIFIED BY HOW MUCH THE HUMANS AGREED\n")
    strata: dict[str, set[str]] = {}
    for uid, s in ref.items():
        strata.setdefault(agreement_stratum(s), set()).add(uid)
    order = ["unanimous", "disagreed", "single annotator", "no annotation"]
    print("    " + ", ".join(f"{k} {len(strata.get(k, ()))}" for k in order))
    print(f"\n    {'judge':<20}" + "".join(f"{k[:14]:>17}" for k in order))
    for j in ARMS:
        cells = []
        for k in order:
            uids = strata.get(k, set())
            ps = pairs_for(j, uids)
            if not ps:
                cells.append("n/a")
                continue
            acc = sum(t == p for t, p in ps) / len(ps)
            cells.append(f"{100 * acc:.1f}% (n={len(ps)})")
        print(f"    {j:<20}" + "".join(f"{c:>17}" for c in cells))
    print("\n    Raw agreement per stratum. A judge that errs where the experts also")
    print("    disagreed is behaving defensibly; one that errs on the unanimous")
    print("    stratum is not, and that column is the one to argue from.")
    print("\n* auxiliary, never pooled with the arms.")


if __name__ == "__main__":
    main()
