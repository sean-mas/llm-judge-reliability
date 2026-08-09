"""Read the 20-item stratified pilot by hand, with the machine doing the sorting.

    .venv/bin/python analysis/pilot_report.py

Prints a per-judge summary and then every judgment grouped so that the ones
worth reading come first. This is a reading aid for the pilot, not the analysis
for the paper: no chance correction, no confidence intervals, n=20.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loader import load_samples  # noqa: E402
from runner import RELEASE, split_corpus  # noqa: E402

DB = Path(__file__).resolve().parents[1] / "data" / "pilot.sqlite"


def wrap(label: str, text: str, indent: int = 4, width: int = 78) -> str:
    """Label a block of prose and hard-wrap it so long sources stay readable."""
    body = " ".join((text or "").split())
    pad = " " * indent
    head = f"{pad}{label}: "
    lines, line = [], head
    for word in body.split(" "):
        if len(line) + len(word) + 1 > width and line.strip() != head.strip():
            lines.append(line)
            line = " " * len(head) + word
        else:
            line = f"{line}{word} " if line.endswith(" ") else f"{line} {word}"
    lines.append(line)
    return "\n".join(lines).rstrip()


def main() -> None:
    ref = {s.uid: s for s in split_corpus(load_samples(RELEASE))["dev"]}
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = list(con.execute("SELECT * FROM judgments ORDER BY judge_id, item_uid"))

    judges = sorted({r["judge_id"] for r in rows})
    by_item: dict[str, dict[str, sqlite3.Row]] = {}
    for r in rows:
        by_item.setdefault(r["item_uid"], {})[r["judge_id"]] = r

    print("=" * 78)
    print("PILOT: 20 stratified dev items x 3 arms")
    print("=" * 78)
    print(f"\nprompt {rows[0]['prompt_version']} / {rows[0]['prompt_hash'][:16]}\n")

    print(f"{'judge':<20} {'model_version':<26} {'agree':>6} {'TPR':>6} {'TNR':>6} "
          f"{'flag%':>6} {'ms':>7} {'out':>5}")
    print("-" * 78)
    for j in judges:
        rs = [r for r in rows if r["judge_id"] == j]
        tp = fn = tn = fp = 0
        for r in rs:
            truth_unf = not ref[r["item_uid"]].is_faithful()
            pred_unf = bool(r["unfaithful"])
            if truth_unf and pred_unf:
                tp += 1
            elif truth_unf:
                fn += 1
            elif pred_unf:
                fp += 1
            else:
                tn += 1
        n = len(rs)
        lat = sum(r["latency_ms"] for r in rs) // n
        out = sum(r["output_tokens"] or 0 for r in rs) // n
        print(f"{j:<20} {rs[0]['model_version'][:26]:<26} "
              f"{(tp + tn)}/{n:<4} {tp}/{tp + fn:<4} {tn}/{tn + fp:<4} "
              f"{100 * (tp + fp) / n:5.0f}% {lat:6d}ms {out:5d}")

    print("\nTPR = of the truly unfaithful, how many were caught.")
    print("TNR = of the truly faithful, how many were correctly passed.")
    print("A judge that flags nothing scores TNR 10/10 and TPR 0/10.\n")

    unan_wrong, split_items, unan_right = [], [], []
    for uid, per in by_item.items():
        lab = ref[uid].summary_label()
        truth = not ref[uid].is_faithful()
        preds = {j: bool(per[j]["unfaithful"]) for j in judges if j in per}
        wrong = [j for j, p in preds.items() if p != truth]
        if len(wrong) == len(preds):
            unan_wrong.append(uid)
        elif wrong:
            split_items.append(uid)
        else:
            unan_right.append(uid)

    print(f"all three wrong : {len(unan_wrong):>2}  <- rubric suspects, read these first")
    print(f"judges disagree : {len(split_items):>2}  <- read these second")
    print(f"all three right : {len(unan_right):>2}  <- skim only")

    for header, uids, full in (
        ("ALL THREE WRONG", unan_wrong, True),
        ("JUDGES DISAGREE", split_items, True),
        ("ALL THREE RIGHT", unan_right, False),
    ):
        if not uids:
            continue
        print("\n" + "=" * 78)
        print(header)
        print("=" * 78)
        for uid in uids:
            s = ref[uid]
            lab = s.summary_label()
            truth = "UNFAITHFUL" if not s.is_faithful() else "faithful"
            print(f"\n{'-' * 78}")
            print(f"{uid}  [{lab}]  reference={truth}  summarizer={s.summarizer}")
            print("-" * 78)
            print(wrap("SOURCE ", s.source if full else s.source[:300] + " [...]"))
            print(wrap("SUMMARY", s.summary))

            print("\n  HUMAN ANNOTATORS")
            if not s.annotations:
                print("    (none: no annotator marked a span, which is what makes it Consistent)")
            for a in s.annotations:
                who = a.annotator_name or a.annotator_id[:8]
                print(f"    [{', '.join(a.labels) or 'no category'}] {who}")
                if a.summary_span:
                    print(f"      objected to: {a.summary_span!r}"
                          f"  (summary chars {a.summary_start}-{a.summary_end})")
                if a.source_span:
                    print(f"      against source: {a.source_span!r}")
                if a.note:
                    print(wrap("      why", a.note, indent=8))
                elif not a.summary_span:
                    print("      (no note and no span recorded in the release)")

            print("\n  JUDGES")
            for j in judges:
                r = by_item[uid].get(j)
                if r is None:
                    continue
                verdict = "UNFAITHFUL" if r["unfaithful"] else "faithful  "
                mark = " " if (bool(r["unfaithful"]) == (not s.is_faithful())) else "X"
                print(f"  {mark} {j:<18} {verdict}  span={(r['span'] or '')[:60]!r}")
                print(wrap("      reason", (r["reason"] or "").strip(), indent=8))


if __name__ == "__main__":
    main()
