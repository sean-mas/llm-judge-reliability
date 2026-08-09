"""Primary analysis. DEV SPLIT ONLY.

    .venv/bin/python analysis/stats.py

Reads `data/main.sqlite` and refuses to touch the test split. Test is read once,
at the end, by `--split test`, and that decision is deliberate and irreversible:
looking at test, adjusting anything, and looking again destroys the meaning of
the headline number with no way to repair it.

Every statistic is reported under all three of FaithBench's binarisation schemes,
following the benchmark authors, who report detectors under U, U+Q and U+Q+B
rather than nominating one. The schemes re-group the reference labels only, so
they cost no additional judgments.

Parse failures are reported as their own rate and then excluded from the
agreement statistics, because a judgment that could not be read is a fact about
the tier's reliability, not evidence about its judgment.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import adapters  # noqa: E402
from loader import load_samples  # noqa: E402
from runner import RELEASE, split_corpus  # noqa: E402

DB = Path(__file__).resolve().parents[1] / "data" / "main.sqlite"
BOOTSTRAP = 2000
SEED = 20260809

#: Positive (unfaithful) classes per scheme. Anything not listed and not in the
#: negative set is dropped from that scheme entirely, which is what U does.
SCHEMES: dict[str, tuple[set[str], set[str]]] = {
    "U": ({"Unwanted"}, {"Consistent"}),
    "U+Q": ({"Unwanted", "Questionable"}, {"Consistent", "Benign"}),
    "U+Q+B": ({"Unwanted", "Questionable", "Benign"}, {"Consistent"}),
}

ARMS = ("tier1_paid", "tier2_hosted_open", "tier3_local")
AUX = ("tier2_free",)  # NOT an arm. Never pooled. See outline TODO 8.


def kappa(pairs: list[tuple[bool, bool]]) -> float:
    """Cohen's kappa for two binary raters over the same items."""
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(t == p for t, p in pairs) / n
    pt = sum(t for t, _ in pairs) / n
    pp = sum(p for _, p in pairs) / n
    pe = pt * pp + (1 - pt) * (1 - pp)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def stats(pairs: list[tuple[bool, bool]]) -> dict[str, float]:
    n = len(pairs)
    tp = sum(1 for t, p in pairs if t and p)
    fn = sum(1 for t, p in pairs if t and not p)
    tn = sum(1 for t, p in pairs if not t and not p)
    fp = sum(1 for t, p in pairs if not t and p)
    po = (tp + tn) / n if n else float("nan")
    k = kappa(pairs)
    return {
        "n": n,
        "raw": po,
        "kappa": k,
        "pabak": 2 * po - 1,
        "deflation": po - k,
        "tpr": tp / (tp + fn) if tp + fn else float("nan"),
        "tnr": tn / (tn + fp) if tn + fp else float("nan"),
        "flag": (tp + fp) / n if n else float("nan"),
        "balacc": 0.5 * ((tp / (tp + fn) if tp + fn else 0) + (tn / (tn + fp) if tn + fp else 0)),
    }


def boot_ci(by_item: dict[str, list[tuple[bool, bool]]], key: str) -> tuple[float, float]:
    """Percentile bootstrap over ITEMS, not judgments.

    Resampling judgments would treat the three repeats of one item as
    independent observations, which they are not, and would report an interval
    narrower than the data supports.
    """
    rng = random.Random(SEED)
    uids = list(by_item)
    if not uids:
        return float("nan"), float("nan")
    vals = []
    for _ in range(BOOTSTRAP):
        draw = [rng.choice(uids) for _ in uids]
        pairs = [pr for u in draw for pr in by_item[u]]
        v = stats(pairs)[key]
        if v == v:  # drop NaN
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", default="dev", choices=("dev", "test"))
    ap.add_argument("--i-am-ready-to-spend-the-test-split", action="store_true")
    args = ap.parse_args()

    if args.split == "test" and not args.i_am_ready_to_spend_the_test_split:
        raise SystemExit(
            "Refusing. The test split may be read once and the reading cannot be\n"
            "undone. Re-run with --i-am-ready-to-spend-the-test-split when the\n"
            "dev analysis is final and no further change to anything is planned."
        )

    ref = {s.uid: s for s in split_corpus(load_samples(RELEASE))[args.split]}
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [r for r in con.execute("SELECT * FROM judgments") if r["item_uid"] in ref]

    print("=" * 92)
    print(f"PRIMARY ANALYSIS  |  split={args.split}  |  {len(ref)} items")
    print("=" * 92)
    vers = {(r["prompt_version"], r["prompt_hash"]) for r in rows}
    print(f"\nprompt: {vers}   <- one entry means the freeze held\n")

    print("PARSE FAILURES (reliability of the tier, reported before any agreement)")
    print(f"  {'judge':<20}{'judgments':>11}{'failed':>9}{'rate':>8}")
    for j in ARMS + AUX:
        rs = [r for r in rows if r["judge_id"] == j]
        if not rs:
            continue
        bad = sum(1 for r in rs if not r["parse_ok"])
        tag = "" if j in ARMS else "   (auxiliary, not an arm)"
        print(f"  {j:<20}{len(rs):>11}{bad:>9}{100 * bad / len(rs):>7.1f}%{tag}")

    for scheme, (pos, neg) in SCHEMES.items():
        print("\n" + "=" * 92)
        print(f"SCHEME {scheme}   positives={sorted(pos)}   negatives={sorted(neg)}")
        if scheme == "U+Q":
            print("  PRIMARY. This is the rule the frozen rubric actually gives the judge.")
        else:
            print("  Sensitivity analysis. The judge was not instructed under this rule.")
        if scheme == "U+Q+B":
            print("  Also the scheme used by FaithJudge (Vectara 2025), so this row is the")
            print("  one that is numerically comparable to the closest prior work.")
        print("=" * 92)
        print(f"  {'judge':<20}{'n':>6}{'raw':>7}{'kappa':>8}{'95% CI':>16}"
              f"{'PABAK':>8}{'defl':>7}{'TPR':>7}{'TNR':>7}{'flag':>7}")

        for j in ARMS + AUX:
            by_item: dict[str, list[tuple[bool, bool]]] = {}
            for r in rows:
                if r["judge_id"] != j or not r["parse_ok"]:
                    continue
                lab = ref[r["item_uid"]].summary_label()
                if lab in pos:
                    truth = True
                elif lab in neg:
                    truth = False
                else:
                    continue
                by_item.setdefault(r["item_uid"], []).append((truth, bool(r["unfaithful"])))
            pairs = [p for v in by_item.values() for p in v]
            if not pairs:
                continue
            s = stats(pairs)
            lo, hi = boot_ci(by_item, "kappa")
            mark = " " if j in ARMS else "*"
            print(f" {mark}{j:<20}{s['n']:>6}{s['raw']:>7.3f}{s['kappa']:>8.3f}"
                  f"  [{lo:>6.3f},{hi:>6.3f}]{s['pabak']:>8.3f}{s['deflation']:>7.3f}"
                  f"{s['tpr']:>7.3f}{s['tnr']:>7.3f}{s['flag']:>7.3f}")

        # Variance across the three repeats, primary scheme only.
        if scheme == "U+Q":
            print("\n  Variance across the three repeats (kappa per repeat, temperature 0):")
            for j in ARMS:
                ks = []
                for rep in (0, 1, 2):
                    pr = []
                    for r in rows:
                        if r["judge_id"] != j or r["repeat_idx"] != rep or not r["parse_ok"]:
                            continue
                        lab = ref[r["item_uid"]].summary_label()
                        if lab in pos:
                            pr.append((True, bool(r["unfaithful"])))
                        elif lab in neg:
                            pr.append((False, bool(r["unfaithful"])))
                    if pr:
                        ks.append(kappa(pr))
                if ks:
                    print(f"    {j:<20}" + "  ".join(f"{k:.3f}" for k in ks)
                          + f"   spread {max(ks) - min(ks):.3f}")

    print("\n* auxiliary, reported but never pooled with the three arms.")
    print("Agreement statistics exclude unparseable judgments; see the parse table above.")


if __name__ == "__main__":
    main()
