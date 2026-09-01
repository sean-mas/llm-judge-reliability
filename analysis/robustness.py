"""Post-freeze robustness analyses. NOT part of the frozen analysis plan.

    .venv/bin/python analysis/robustness.py --split test

Every number this script produces was computed AFTER the test split was read and
after the analysis freeze recorded in appendix/analysis.md. It is therefore
exploratory and is reported as such wherever it appears in the paper. It exists
because three criticisms of the primary analysis are correct and are cheaper to
answer with the data already collected than to concede.

1. COMPLETE-CASE BIAS. The primary analysis excludes unparseable judgments. If
   parse failure is associated with the reference label, that exclusion
   conditions on "the judge answered readably" and can flatter sensitivity,
   agreement and gate suitability. Section 1 tests the association and reports
   failure-inclusive alternatives.

2. OVERLAPPING INTERVALS ARE NOT A TEST. Two overlapping 95% intervals do not
   establish that a difference is indistinguishable from zero. Section 2
   bootstraps the paired difference in kappa directly, on the same resampled
   items, and reports the interval of the difference.

3. THE UNIT OF ANALYSIS. The primary tables pool three repeats per item, which
   reads as n = 1,456 independent observations when it is 488 items each judged
   up to three times. Section 3 aggregates to one decision per item first.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "analysis"))

from loader import load_samples  # noqa: E402
from runner import RELEASE, split_corpus  # noqa: E402
from stats import ARMS, SCHEMES, kappa, stats  # noqa: E402

DB = ROOT / "data" / "main.sqlite"
BOOTSTRAP = 2000
SEED = 20260809
#: Declared here, after the fact, and therefore reported as a stated reference
#: rather than as a pre-specified threshold. 0.03 kappa points is roughly one
#: fifth of the largest kappa measured, and smaller than the width of every
#: confidence interval in the primary table.
EQUIV_MARGIN = 0.03


def load(split: str):
    ref = {s.uid: s for s in split_corpus(load_samples(RELEASE))[split]}
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("SELECT * FROM judgments") if r["item_uid"] in ref]
    return ref, rows


def truth_of(ref, uid, pos, neg):
    lab = ref[uid].summary_label()
    return True if lab in pos else (False if lab in neg else None)


# ---------------------------------------------------------------------------
# 1. Parse failures: is the exclusion innocent?
# ---------------------------------------------------------------------------
def section_1(ref, rows, pos, neg):
    print("=" * 88)
    print("1. PARSE FAILURES: IS COMPLETE-CASE ANALYSIS BIASED?")
    print("=" * 88)
    print("\n1a. Failure rate by reference label. If these differ, the exclusion")
    print("    is label-associated and the complete-case estimate is conditional.\n")
    print(f"  {'judge':<20}{'fail | unfaithful':>20}{'fail | faithful':>18}{'difference':>13}")

    assoc = {}
    for j in ARMS:
        cnt = {True: [0, 0], False: [0, 0]}  # truth -> [failed, total]
        for r in rows:
            if r["judge_id"] != j:
                continue
            t = truth_of(ref, r["item_uid"], pos, neg)
            if t is None:
                continue
            cnt[t][1] += 1
            if not r["parse_ok"]:
                cnt[t][0] += 1
        fu = cnt[True][0] / cnt[True][1] if cnt[True][1] else float("nan")
        ff = cnt[False][0] / cnt[False][1] if cnt[False][1] else float("nan")
        assoc[j] = (fu, ff, cnt)
        print(f"  {j:<20}{fu:>19.1%}{ff:>18.1%}{fu - ff:>+12.1f}pp"
              .replace(f"{fu - ff:>+12.1f}pp", f"{100 * (fu - ff):>+11.1f}pp"))

    print("\n1b. Three scenarios for the same judgments, scheme U+Q.\n")
    print("    PRIMARY      unparseable dropped (the frozen analysis)")
    print("    GATE-SAFE    unparseable treated as a flag, i.e. routed to manual review")
    print("    WORST-CASE   unparseable counted as disagreeing with the human label\n")
    print(f"  {'judge':<20}{'scenario':<13}{'n':>6}{'raw':>8}{'kappa':>8}{'TPR':>8}{'flag':>8}")

    out = {}
    for j in ARMS:
        for scen in ("primary", "gate-safe", "worst-case"):
            pairs = []
            for r in rows:
                if r["judge_id"] != j:
                    continue
                t = truth_of(ref, r["item_uid"], pos, neg)
                if t is None:
                    continue
                if r["parse_ok"]:
                    pairs.append((t, bool(r["unfaithful"])))
                elif scen == "gate-safe":
                    pairs.append((t, True))
                elif scen == "worst-case":
                    pairs.append((t, not t))
            s = stats(pairs)
            out[(j, scen)] = s
            print(f"  {j:<20}{scen:<13}{s['n']:>6}{s['raw']:>8.3f}{s['kappa']:>8.3f}"
                  f"{s['tpr']:>8.3f}{s['flag']:>8.3f}")
    return assoc, out


# ---------------------------------------------------------------------------
# 2. Paired bootstrap of the difference between tiers
# ---------------------------------------------------------------------------
def section_2(ref, rows, pos, neg):
    print("\n" + "=" * 88)
    print("2. PAIRED DIFFERENCE IN KAPPA BETWEEN TIERS")
    print("=" * 88)
    print("\n   Resampled over items. Both judges are evaluated on the SAME resampled")
    print("   items in every draw, so the comparison is paired and the interval is")
    print("   the interval of the difference rather than of two separate estimates.\n")

    by_item = {j: {} for j in ARMS}
    for r in rows:
        if r["judge_id"] not in ARMS or not r["parse_ok"]:
            continue
        t = truth_of(ref, r["item_uid"], pos, neg)
        if t is None:
            continue
        by_item[r["judge_id"]].setdefault(r["item_uid"], []).append((t, bool(r["unfaithful"])))

    uids = sorted(set(by_item[ARMS[0]]) & set(by_item[ARMS[1]]) & set(by_item[ARMS[2]]))
    print(f"   items judged by all three arms: {len(uids)}\n")
    print(f"  {'pair':<38}{'d kappa':>9}{'95% CI of the difference':>28}{'verdict':>12}")

    res = {}
    for a in range(3):
        for b in range(a + 1, 3):
            ja, jb = ARMS[a], ARMS[b]
            point = kappa([p for u in uids for p in by_item[ja][u]]) - \
                    kappa([p for u in uids for p in by_item[jb][u]])
            rng = random.Random(SEED)
            diffs = []
            for _ in range(BOOTSTRAP):
                draw = [rng.choice(uids) for _ in uids]
                ka = kappa([p for u in draw for p in by_item[ja][u]])
                kb = kappa([p for u in draw for p in by_item[jb][u]])
                if ka == ka and kb == kb:
                    diffs.append(ka - kb)
            diffs.sort()
            lo, hi = diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]
            if lo > 0 or hi < 0:
                verdict = "differs"
            elif abs(lo) < EQUIV_MARGIN and abs(hi) < EQUIV_MARGIN:
                verdict = "equivalent"
            else:
                verdict = "undecided"
            res[(ja, jb)] = (point, lo, hi, verdict)
            print(f"  {ja + ' - ' + jb:<38}{point:>+9.3f}   [{lo:>+7.3f},{hi:>+7.3f}]{verdict:>15}")

    print(f"\n   'equivalent' means the whole interval lies inside +/-{EQUIV_MARGIN} kappa points.")
    print("   'undecided' means the data neither shows a difference nor rules out")
    print("   one large enough to matter. That is a statement about power, not about")
    print("   the judges, and it is the honest reading of an overlapping interval.")
    return res


# ---------------------------------------------------------------------------
# 3. One decision per item
# ---------------------------------------------------------------------------
def section_3(ref, rows, pos, neg):
    print("\n" + "=" * 88)
    print("3. ITEM-LEVEL AGGREGATION: ONE DECISION PER ITEM")
    print("=" * 88)
    print("\n   MAJORITY   the verdict returned by at least two of the three repeats")
    print("   ANY-FLAG   unfaithful if any repeat said so, the conservative gate rule\n")
    print(f"  {'judge':<20}{'rule':<10}{'items':>7}{'raw':>8}{'kappa':>8}{'TPR':>8}{'flag':>8}")

    out = {}
    for j in ARMS:
        per = {}
        for r in rows:
            if r["judge_id"] != j or not r["parse_ok"]:
                continue
            t = truth_of(ref, r["item_uid"], pos, neg)
            if t is None:
                continue
            per.setdefault(r["item_uid"], (t, []))[1].append(bool(r["unfaithful"]))
        for rule in ("majority", "any-flag"):
            pairs = []
            for _uid, (t, vs) in per.items():
                p = (sum(vs) > len(vs) / 2) if rule == "majority" else any(vs)
                pairs.append((t, p))
            s = stats(pairs)
            out[(j, rule)] = s
            print(f"  {j:<20}{rule:<10}{s['n']:>7}{s['raw']:>8.3f}{s['kappa']:>8.3f}"
                  f"{s['tpr']:>8.3f}{s['flag']:>8.3f}")

    print("\n3b. How often did the three repeats disagree with each other?\n")
    print(f"  {'judge':<20}{'items':>7}{'unanimous':>12}{'2:1 split':>12}")
    for j in ARMS:
        per = {}
        for r in rows:
            if r["judge_id"] != j or not r["parse_ok"]:
                continue
            per.setdefault(r["item_uid"], []).append(bool(r["unfaithful"]))
        full = [v for v in per.values() if len(v) == 3]
        una = sum(1 for v in full if len(set(v)) == 1)
        print(f"  {j:<20}{len(full):>7}{una / len(full):>11.1%}{1 - una / len(full):>11.1%}")
    return out



# ---------------------------------------------------------------------------
# 4. Leave-one-annotator-out: score a human the way the judge is scored
# ---------------------------------------------------------------------------
def section_4(ref, rows, pos, neg):
    from loader import SEVERITY
    ms = lambda ls: max(ls, key=lambda l: SEVERITY.index(l) if l in SEVERITY else -1)
    bi = lambda l: True if l in pos else (False if l in neg else None)

    print("\n" + "=" * 88)
    print("4. LEAVE-ONE-ANNOTATOR-OUT")
    print("=" * 88)
    print("\n   The headline comparison is asymmetric as it stands: a judge is scored")
    print("   against a reference aggregated from several annotators, while the human")
    print("   figure is one annotator against one other annotator. Here each annotator")
    print("   is held out in turn and scored against a reference built from the")
    print("   remaining annotators on the same item, which is exactly the procedure")
    print("   applied to the judges. Both are then restricted to the same items.\n")

    multi = {}
    for uid, s in ref.items():
        per = {}
        for a in s.annotations:
            per.setdefault(a.annotator_id, set()).update(a.coarse_labels)
        if len({k: v for k, v in per.items() if v}) >= 2:
            multi[uid] = s
    print(f"   comparison set: {len(multi)} items carrying two or more annotators\n")
    print(f"  {'rater':<26}{'n':>7}{'raw':>9}{'kappa':>9}{'TPR':>8}{'TNR':>8}")

    pairs = []
    for s in multi.values():
        per = {}
        for a in s.annotations:
            per.setdefault(a.annotator_id, set()).update(a.coarse_labels)
        us = {k: v for k, v in per.items() if v}
        for k in us:
            held = bi(ms(us[k]))
            rest = bi(ms([ms(us[o]) for o in us if o != k]))
            if held is not None and rest is not None:
                pairs.append((rest, held))
    s = stats(pairs)
    print(f"  {'human, leave-one-out':<26}{s['n']:>7}{s['raw']:>9.3f}{s['kappa']:>9.3f}"
          f"{s['tpr']:>8.3f}{s['tnr']:>8.3f}")

    for j in ARMS:
        pr = []
        for r in rows:
            if r["judge_id"] != j or not r["parse_ok"] or r["item_uid"] not in multi:
                continue
            t = truth_of(ref, r["item_uid"], pos, neg)
            if t is not None:
                pr.append((t, bool(r["unfaithful"])))
        s = stats(pr)
        print(f"  {j:<26}{s['n']:>7}{s['raw']:>9.3f}{s['kappa']:>9.3f}"
              f"{s['tpr']:>8.3f}{s['tnr']:>8.3f}")

    print("\n   This subset excludes every item with no annotation at all, which under")
    print("   the reference rule is exactly the Consistent items. It is therefore")
    print("   harder than the full split for both raters, and the judge figures here")
    print("   are lower than the headline ones for that reason. The comparison")
    print("   between the two rows is the point, not their absolute level.")



# ---------------------------------------------------------------------------
# 5. Uncertainty on the Rogan-Gladen transfer
# ---------------------------------------------------------------------------
def section_5(pos, neg):
    """Both sources of uncertainty, propagated together.

    The point estimates in the meter table carry two independent errors: the
    sensitivity and specificity are estimated on development, and the flag rate
    is estimated on test. Reporting the point estimate alone hides both. Each
    resample draws a fresh development sample for the calibration and a fresh
    test sample for the flag rate, then applies the estimator to the pair.
    """
    print("\n" + "=" * 88)
    print("5. ROGAN-GLADEN TRANSFER, WITH UNCERTAINTY")
    print("=" * 88)

    splits = split_corpus(load_samples(RELEASE))
    ref = {s.uid: s for split in ("dev", "test") for s in splits[split]}
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("SELECT * FROM judgments")]

    def per_item(split, judge):
        uids = {s.uid for s in splits[split]}
        d = {}
        for r in rows:
            if r["judge_id"] != judge or not r["parse_ok"] or r["item_uid"] not in uids:
                continue
            t = truth_of(ref, r["item_uid"], pos, neg)
            if t is None:
                continue
            d.setdefault(r["item_uid"], []).append((t, bool(r["unfaithful"])))
        return d

    truth_rate = None
    tp = sum(1 for s in splits["test"] if truth_of(ref, s.uid, pos, neg) is True)
    tn = sum(1 for s in splits["test"] if truth_of(ref, s.uid, pos, neg) is False)
    truth_rate = tp / (tp + tn)

    print(f"\n   true unfaithful rate on test: {truth_rate:.1%}")
    print(f"   {BOOTSTRAP} resamples, development resampled for TPR and TNR and test")
    print("   resampled for the flag rate, independently, in every draw.\n")
    print(f"  {'judge':<20}{'estimate':>10}{'95% CI':>22}{'true':>8}{'error':>9}{'unusable':>10}")

    for j in ARMS:
        dev, test = per_item("dev", j), per_item("test", j)
        dev_u, test_u = list(dev), list(test)
        rng = random.Random(SEED)
        est = []
        bad = 0
        for _ in range(BOOTSTRAP):
            dpairs = [p for u in (rng.choice(dev_u) for _ in dev_u) for p in dev[u]]
            tpairs = [p for u in (rng.choice(test_u) for _ in test_u) for p in test[u]]
            ds, ts = stats(dpairs), stats(tpairs)
            J = ds["tpr"] + ds["tnr"] - 1
            if J <= 0:
                bad += 1
                continue
            p_hat = (ts["flag"] - (1 - ds["tnr"])) / J
            est.append(min(max(p_hat, 0.0), 1.0))
        est.sort()
        lo, hi = est[int(0.025 * len(est))], est[int(0.975 * len(est)) - 1]
        med = est[len(est) // 2]
        print(f"  {j:<20}{med:>9.1%} [{lo:>7.1%},{hi:>7.1%}]{truth_rate:>8.1%}"
              f"{med - truth_rate:>+8.1f}pp{bad:>10}"
              .replace(f"{med - truth_rate:>+8.1f}pp", f"{100*(med-truth_rate):>+8.1f}pp"))

    print("\n   Which sample limits the precision? Holding one fixed and resampling")
    print("   the other separates the two contributions.\n")
    print(f"  {'judge':<20}{'both':>20}{'test only':>20}{'dev only':>20}")
    for j in ARMS:
        dev, test = per_item("dev", j), per_item("test", j)
        du, tu = list(dev), list(test)
        d0 = stats([q for u in du for q in dev[u]])
        t0 = stats([q for u in tu for q in test[u]])
        cells = []
        for mode in ("both", "test", "dev"):
            rng = random.Random(SEED)
            est = []
            for _ in range(BOOTSTRAP):
                ds = stats([q for u in (rng.choice(du) for _ in du) for q in dev[u]]) \
                     if mode in ("both", "dev") else d0
                ts = stats([q for u in (rng.choice(tu) for _ in tu) for q in test[u]]) \
                     if mode in ("both", "test") else t0
                J = ds["tpr"] + ds["tnr"] - 1
                if J <= 0:
                    continue
                est.append(min(max((ts["flag"] - (1 - ds["tnr"])) / J, 0.0), 1.0))
            est.sort()
            cells.append(f"[{est[int(0.025*len(est))]:>5.1%},{est[int(0.975*len(est))-1]:>6.1%}]")
        print(f"  {j:<20}{cells[0]:>20}{cells[1]:>20}{cells[2]:>20}")
    print("\n   The dev-only interval is nearly as wide as the full one, so the")
    print("   calibration set rather than the measured corpus is what limits precision.")

    print("\n   Estimates are clamped to [0, 1]; a prevalence cannot fall outside it.")
    print("   'unusable' counts resamples where Youden's J came out at or below zero,")
    print("   which makes the estimator undefined. A non-zero count is itself the")
    print("   finding: the correction sits close to the regime where it breaks.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", default="test", choices=("dev", "test"))
    args = ap.parse_args()

    ref, rows = load(args.split)
    pos, neg = SCHEMES["U+Q"]

    print("#" * 88)
    print(f"# POST-FREEZE ROBUSTNESS  |  split={args.split}  |  {len(ref)} items  |  scheme U+Q")
    print("# Computed after the test split was read. Exploratory, not confirmatory.")
    print("#" * 88 + "\n")

    section_1(ref, rows, pos, neg)
    section_2(ref, rows, pos, neg)
    section_3(ref, rows, pos, neg)
    section_4(ref, rows, pos, neg)
    section_5(pos, neg)
    print("\n" + "#" * 88)


if __name__ == "__main__":
    main()
