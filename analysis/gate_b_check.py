"""Gate B: is FaithBench usable for this study?

Three questions, from project-plan.md section 2. The whole analysis plan assumes
all three, so they get answered before anything else is built.

    1. How many items are there?          -> can a 300-item stratified sample be drawn?
    2. How many annotators per item?      -> is there a human-human agreement ceiling?
    3. What is the label distribution?    -> is the minority class large enough to measure recall on?

Stdlib only, so it runs from a clean checkout with no install step.

    python3 analysis/gate_b_check.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loader import CONSISTENT, SEVERITY, load_samples  # noqa: E402

RELEASE_DIR = Path(__file__).resolve().parent.parent / "data/raw/FaithBench/data_for_release"


def pct(n: int, total: int) -> str:
    return f"{100 * n / total:5.1f}%" if total else "    n/a"


def main() -> None:
    samples = load_samples(RELEASE_DIR)
    total = len(samples)
    batches = sorted({s.batch for s in samples}, key=lambda b: int(b.split("_")[1]))

    print("=" * 68)
    print("GATE B: FaithBench usability check")
    print("=" * 68)

    # --- Q1: item count -------------------------------------------------
    print(f"\n[Q1] ITEM COUNT\n     {total} samples across {len(batches)} batches")
    per_batch = Counter(s.batch for s in samples)
    sizes = sorted(set(per_batch.values()))
    print(f"     per batch: {dict(sorted(per_batch.items(), key=lambda kv: int(kv[0].split('_')[1])))}")
    print(f"     batch sizes seen: {sizes}")
    dupe_ids = total - len({s.uid for s in samples})
    print(f"     duplicate uids: {dupe_ids}  (sample_id alone is NOT unique across batches)")

    # --- Q2: annotators per item ---------------------------------------
    print("\n[Q2] ANNOTATORS PER ITEM")
    annotated = [s for s in samples if s.annotations]
    consistent = [s for s in samples if not s.annotations]
    dist = Counter(len(s.annotator_ids) for s in annotated)
    print(f"     samples WITH annotations:    {len(annotated):>5} ({pct(len(annotated), total)})")
    print(f"     samples WITHOUT annotations: {len(consistent):>5} ({pct(len(consistent), total)})  <- 'Consistent'")
    print("     distinct annotators per annotated sample:")
    for k in sorted(dist):
        print(f"       {k} annotator(s): {dist[k]:>5} samples  ({pct(dist[k], len(annotated))} of annotated)")
    redundant = sum(v for k, v in dist.items() if k >= 2)
    print(f"     >= 2 annotators: {redundant} of {len(annotated)} annotated ({pct(redundant, len(annotated))})")
    print(f"                      {redundant} of {total} overall      ({pct(redundant, total)})")

    all_annotators = {a.annotator_id for s in samples for a in s.annotations}
    names = {a.annotator_id: a.annotator_name for s in samples for a in s.annotations}
    print(f"     distinct annotators in corpus: {len(all_annotators)}")
    load = Counter(a.annotator_id for s in samples for a in s.annotations)
    print("     annotations per annotator:")
    for aid, n in load.most_common():
        print(f"       {names[aid]:<12} {n:>5}")

    # --- Q3: label distribution ----------------------------------------
    print("\n[Q3] LABEL DISTRIBUTION")
    print("     (a) summary level, most-severe rule, all samples")
    summary_labels = Counter(s.summary_label() for s in samples)
    for lab in SEVERITY:
        print(f"       {lab:<14} {summary_labels.get(lab, 0):>5}  {pct(summary_labels.get(lab, 0), total)}")
    unknown = {k: v for k, v in summary_labels.items() if k not in SEVERITY}
    if unknown:
        print(f"       UNEXPECTED LABELS: {unknown}")

    print("\n     (b) annotation level, raw label strings")
    raw = Counter(lab for s in samples for a in s.annotations for lab in a.labels)
    n_annot = sum(len(s.annotations) for s in samples)
    for lab, n in raw.most_common():
        print(f"       {lab:<24} {n:>5}  {pct(n, n_annot)}")
    print(f"       {'TOTAL annotations':<24} {n_annot:>5}")

    print("\n     (c) minority class size, the number recall is computed on")
    unwanted = summary_labels.get("Unwanted", 0)
    print(f"       samples whose most-severe label is Unwanted: {unwanted}  ({pct(unwanted, total)})")
    non_consistent = total - summary_labels.get(CONSISTENT, 0)
    print(f"       samples with any annotation at all:          {non_consistent}  ({pct(non_consistent, total)})")

    # --- Q3d: what a constant judge scores ------------------------------
    # This is the number the whole study exists to attack. On SummEval the
    # trivial judge is "always pass". Here the skew runs the other way, so the
    # trivial judge is "always fail". Same failure mode, opposite direction.
    print("\n     (d) constant-judge baselines, the number to beat")
    binarisations = {
        "strict  (PASS = Consistent)": {CONSISTENT},
        "lenient (PASS = Consistent + Benign)": {CONSISTENT, "Benign"},
    }
    for name, pass_set in binarisations.items():
        n_pass = sum(1 for s in samples if s.summary_label() in pass_set)
        n_fail = total - n_pass
        best = max(n_pass, n_fail)
        verdict = "always-PASS" if n_pass > n_fail else "always-FAIL"
        print(f"       {name}")
        print(f"         PASS {n_pass:>4} ({pct(n_pass, total)})   FAIL {n_fail:>4} ({pct(n_fail, total)})")
        print(f"         a constant {verdict} judge scores {pct(best, total)} raw agreement and catches nothing")

    # --- Q2b: human ceiling ---------------------------------------------
    # Aggregate each annotator's own spans to a per-annotator summary label,
    # then ask whether annotators on the same sample agree. Computable only on
    # the 2+ annotator subset, which excludes every Consistent sample.
    print("\n[Q2b] HUMAN CEILING, summary level, most-severe rule per annotator")
    pairs_agree = pairs_total = 0
    unanimous = 0
    dropped = 0  # (annotator, sample) pairs with a span but no category
    pair_labels: list[tuple[str, str]] = []
    multi = [s for s in samples if len(s.annotator_ids) >= 2]
    for s in multi:
        per_annotator: dict[str, set[str]] = {}
        for a in s.annotations:
            per_annotator.setdefault(a.annotator_id, set()).update(a.coarse_labels)
        usable = [v for v in per_annotator.values() if v]
        dropped += len(per_annotator) - len(usable)
        if len(usable) < 2:
            continue
        labels = [
            max(v, key=lambda lab: SEVERITY.index(lab) if lab in SEVERITY else -1)
            for v in usable
        ]
        if len(set(labels)) == 1:
            unanimous += 1
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                pair_labels.append((labels[i], labels[j]))
                pairs_total += 1
                pairs_agree += labels[i] == labels[j]
    print(f"     samples with >= 2 annotators: {len(multi)}  ({pct(len(multi), total)} of corpus)")
    print(f"     unanimous across annotators:  {unanimous}  ({pct(unanimous, len(multi))} of those)")
    print(f"     pairwise raw agreement:       {pct(pairs_agree, pairs_total)}  ({pairs_agree}/{pairs_total} pairs)")
    print(f"     dropped, span marked but no category assigned: {dropped} (annotator, sample) pairs")
    print("     NOTE: computable only where >= 2 annotators left spans, so every")
    print("           Consistent sample is excluded. This is the ceiling on the hard")
    print("           subset only, not the ceiling for the full corpus.")

    # Matched comparison. The 76.7% above is over all 750; this ceiling is over
    # 443. Comparing them directly would mix denominators, so score the trivial
    # judge on the SAME 443 items and the same 4-way label space.
    sub = Counter(s.summary_label() for s in multi)
    mode_lab, mode_n = sub.most_common(1)[0]
    print(f"\n     MATCHED to the same {len(multi)} items, 4-way label space:")
    print(f"       humans, pairwise          {pct(pairs_agree, pairs_total)}")
    print(f"       constant '{mode_lab}' judge  {pct(mode_n, len(multi))}  ({mode_n}/{len(multi)})")
    print(f"       gap                       {100*mode_n/len(multi) - 100*pairs_agree/pairs_total:+.1f} points")
    print("     Use this pairing when comparing the two, not the corpus-wide figure,")
    print("     which is computed over all 750 and is a different denominator.")

    # Same matched logic, but on the binary task the paper actually reports.
    from loader import PASS_CANONICAL, PASS_STRICT  # noqa: PLC0415
    for rule_name, pass_set in (("canonical", PASS_CANONICAL), ("strict", PASS_STRICT)):
        bp = [(a in pass_set, b in pass_set) for a, b in pair_labels]
        b_agree = sum(x == y for x, y in bp)
        n_pass = sum(1 for s in multi if s.summary_label() in pass_set)
        const = max(n_pass, len(multi) - n_pass)
        if not bp:
            continue
        print(f"\n     MATCHED, binary, {rule_name} rule, same {len(multi)} items:")
        print(f"       humans, pairwise          {pct(b_agree, len(bp))}")
        print(f"       constant judge            {pct(const, len(multi))}  ({const}/{len(multi)})")
        print(f"       gap                       {100*const/len(multi) - 100*b_agree/len(bp):+.1f} points")

    # --- Q4: does the aggregation rule change the answer? ---------------
    # The reference label has to be built from several annotators who may
    # disagree. If the headline moved depending on that choice, the choice would
    # need defending at length. It does not, so one table settles it.
    print("\n[Q4] REFERENCE-LABEL ROBUSTNESS: most-severe vs majority vote")
    per_ann: dict[str, dict[str, str]] = {}
    for s in samples:
        acc: dict[str, set[str]] = {}
        for a in s.annotations:
            acc.setdefault(a.annotator_id, set()).update(a.coarse_labels)
        per_ann[s.uid] = {
            aid: max(v, key=lambda lab: SEVERITY.index(lab) if lab in SEVERITY else -1)
            for aid, v in acc.items() if v
        }

    def majority(s) -> str:
        votes = list(per_ann[s.uid].values())
        if not votes:
            return CONSISTENT
        counts = Counter(votes).most_common()
        top = counts[0][1]
        tied = [lab for lab, n in counts if n == top]
        return max(tied, key=lambda lab: SEVERITY.index(lab) if lab in SEVERITY else -1)

    sev_d = Counter(s.summary_label() for s in samples)
    maj_d = Counter(majority(s) for s in samples)
    print(f"       {'label':<14} {'most-severe':>12} {'majority':>10} {'delta':>7}")
    for lab in SEVERITY:
        print(f"       {lab:<14} {sev_d[lab]:>12} {maj_d[lab]:>10} {maj_d[lab]-sev_d[lab]:>+7}")
    for name, d in (("most-severe", sev_d), ("majority", maj_d)):
        f = total - d[CONSISTENT]
        print(f"       -> {name:<12} binary FAIL = {f}/{total} = {pct(f, total)}")
    print("     Both rules give the same binary split, because they only move items")
    print("     between Benign/Questionable/Unwanted, all of which are FAIL under the")
    print("     strict rule. The aggregation choice is therefore not load-bearing.")

    n2 = sum(1 for s in samples if len(per_ann[s.uid]) == 2)
    n2d = sum(1 for s in samples if len(per_ann[s.uid]) == 2
              and len(set(per_ann[s.uid].values())) > 1)
    n3 = sum(1 for s in samples if len(per_ann[s.uid]) >= 3)
    print(f"     Majority vote is UNDEFINED on {n2d} items (exactly 2 annotators, split 1-1).")
    print(f"     Defined on the {n3} items with 3+ annotators. Hence most-severe as primary.")

    # --- Q5: label-confidence strata ------------------------------------
    # Not every reference label is equally trustworthy. Reporting TPR/TNR on the
    # unanimous stratum and judge behaviour on the disagreed stratum separately
    # is more honest than one pooled number, and the disagreed stratum is where
    # the interesting question lives.
    print("\n[Q5] LABEL-CONFIDENCE STRATA, for stratified reporting in chapter 4")
    strata: dict[str, list] = {
        "no annotator (Consistent)": [],
        "single annotator": [],
        "2+ unanimous": [],
        "2+ disagreed": [],
    }
    for s in samples:
        labs = per_ann[s.uid]
        if not s.annotations:
            strata["no annotator (Consistent)"].append(s)
        elif len(labs) <= 1:
            strata["single annotator"].append(s)
        elif len(set(labs.values())) == 1:
            strata["2+ unanimous"].append(s)
        else:
            strata["2+ disagreed"].append(s)
    for name, items in strata.items():
        print(f"       {name:<28} {len(items):>4}  {pct(len(items), total)}")

    dis = strata["2+ disagreed"]
    print(f"\n     What the {len(dis)} disagreements are actually about:")
    combos = Counter(tuple(sorted(set(per_ann[s.uid].values()))) for s in dis)
    for combo, n in combos.most_common():
        print(f"       {' vs '.join(combo):<42} {n:>4}")
    print("     Every disagreement is about SEVERITY, never about whether to flag at")
    print("     all, because 'Consistent' is the absence of an annotation and so can")
    print("     never be one annotator's dissenting vote.")

    lenient = {CONSISTENT, "Benign"}
    straddle = sum(1 for s in dis
                   if {lab in lenient for lab in per_ann[s.uid].values()} == {True, False})
    print(f"     Under the LENIENT rule (PASS = Consistent or Benign), {straddle} items have")
    print(f"     annotators on both sides of the pass/fail line. Under STRICT, zero do.")

    # --- verdict --------------------------------------------------------
    print("\n" + "=" * 68)
    print("VERDICT")
    print("=" * 68)
    checks = [
        ("corpus large enough (no sampling)", total >= 500, f"{total} items, all used"),
        ("annotator redundancy present", redundant > 0, f"{redundant} samples have >= 2 annotators"),
        ("minority class measurable", unwanted >= 30, f"{unwanted} Unwanted samples"),
    ]
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<32} {detail}")


if __name__ == "__main__":
    main()
