"""Run items x judges x repeats. Cached, resumable, and honest about failures.

    python3 src/runner.py --tier mock --limit 20
    python3 src/runner.py --tier local --split dev --repeats 3
    python3 src/runner.py --tier paid --split test --repeats 3

Four rules from the plan of record, section 4, all enforced here:

1. Cache everything, keyed on item, judge, model and prompt hash. Anything
   already in the store is skipped without a call.
2. Record the model version on every row.
3. Be resumable. Killing this at judgment 2000 and restarting costs nothing;
   the store is consulted first and only missing keys are requested.
4. One row per judgment, never per item.

A transport failure aborts the run rather than being retried silently. Failing
loudly once is better than discovering at analysis time that a tier quietly
returned nothing for two hours. A *parse* failure is different: it is recorded
as data, because a tier that cannot follow the output contract is a finding.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import adapters  # noqa: E402
from loader import SEVERITY, Sample, load_samples  # noqa: E402
from rubric import PROMPT_VERSION, ParseError, parse, render, rubric_hash  # noqa: E402
from store import Judgment, Store  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "data/raw/FaithBench/data_for_release"


def split_corpus(samples: list[Sample], dev_frac: float = 1 / 3) -> dict[str, list[Sample]]:
    """Deterministic dev/test split, stratified by summariser AND reference label.

    Both dimensions are needed. Stratifying on the summariser alone keeps all ten
    models in each half but lets the label mix drift, which measured at a 12-point
    gap in the consistent rate: dev came out systematically harder than test, so a
    rubric tuned on dev would be tuned against the wrong difficulty.

    Stratifying on the reference label as well is not leakage. The labels are
    fixed human annotations that exist before any judge runs, and no judge output
    enters the split. What must not happen, and does not, is choosing the split
    after seeing how the judges performed.

    Deterministic by construction, taking every ``1/dev_frac``-th item of each
    stratum, so the split reproduces from the code with no RNG seed to record.
    """
    strata: dict[tuple[str, str], list[Sample]] = {}
    for s in sorted(samples, key=lambda x: (x.summarizer, x.summary_label(), x.batch, x.sample_id)):
        strata.setdefault((s.summarizer, s.summary_label()), []).append(s)

    dev, test = [], []
    step = round(1 / dev_frac)
    for items in strata.values():
        for i, s in enumerate(items):
            (dev if i % step == 0 else test).append(s)
    return {"dev": dev, "test": test, "all": samples}


def stratified_sample(samples: list[Sample], n: int) -> list[Sample]:
    """Draw ``n`` items spread evenly across labels, and across summarisers within them.

    ``samples[:n]`` is the wrong pilot set. The split is ordered by batch, so the
    first four dev items are all *Benign* and the first twenty all come from a
    single summariser. A judge scored against either looks ready without ever
    having been shown a contradiction or a second error style. A pilot exists to
    expose the rubric to the hard cases, so it has to span the range by
    construction rather than by luck.

    Round-robins over the four severity labels in canonical order, and inside
    each label round-robins over summarisers. The summariser rotation is offset
    by the label's position, otherwise every label draws the same alphabetically
    first systems and a draw of twenty covers only five of the ten. With the
    offset it covers eight.

    Deterministic, so the pilot set reproduces from the code with no RNG seed to
    record. Note this is a *pilot* draw, not the split: it deliberately
    over-represents rare labels relative to the corpus, which is correct for
    rubric development and would be wrong for anything reported as a rate.
    """
    by_label: dict[str, list[Sample]] = {}
    for s in sorted(samples, key=lambda x: (x.batch, x.sample_id)):
        by_label.setdefault(s.summary_label(), []).append(s)

    order = [lab for lab in SEVERITY if lab in by_label]

    for offset, label in enumerate(order):
        items = by_label[label]
        by_sum: dict[str, list[Sample]] = {}
        for s in items:
            by_sum.setdefault(s.summarizer, []).append(s)
        keys = sorted(by_sum)
        keys = keys[offset % len(keys):] + keys[:offset % len(keys)]
        woven: list[Sample] = []
        i = 0
        while len(woven) < len(items):
            for k in keys:
                if len(by_sum[k]) > i:
                    woven.append(by_sum[k][i])
            i += 1
        by_label[label] = woven

    out: list[Sample] = []
    i = 0
    while len(out) < n and any(len(by_label[lab]) > i for lab in order):
        for lab in order:
            if len(out) < n and len(by_label[lab]) > i:
                out.append(by_label[lab][i])
        i += 1
    return out


def run(tier: str, split: str = "dev", repeats: int = 3, limit: int | None = None,
        stratified: bool = False, db: str = "data/judgments.sqlite",
        **adapter_kw) -> None:
    judge = adapters.build(tier, **adapter_kw)
    store = Store(ROOT / db)
    phash = rubric_hash()

    samples = split_corpus(load_samples(RELEASE))[split]
    if limit:
        samples = stratified_sample(samples, limit) if stratified else samples[:limit]

    done = store.done_keys(judge.judge_id, judge.model_requested, phash)
    todo = [(s, r) for s in samples for r in range(repeats) if (s.uid, r) not in done]

    mix: dict[str, int] = {}
    for s in samples:
        mix[s.summary_label()] = mix.get(s.summary_label(), 0) + 1

    print(f"judge      : {judge.describe()}")
    print(f"prompt     : {PROMPT_VERSION} / {phash}")
    print(f"split      : {split}, {len(samples)} items x {repeats} repeats"
          f"{' (stratified draw)' if stratified and limit else ''}")
    print(f"labels     : " + ", ".join(f"{lab} {mix[lab]}" for lab in SEVERITY if lab in mix))
    print(f"cached     : {len(samples) * repeats - len(todo)}")
    print(f"to request : {len(todo)}\n")
    if not todo:
        print("nothing to do.")
        return

    parse_failures = 0
    for i, (sample, rep) in enumerate(todo, 1):
        system, user = render(sample.source, sample.summary)
        try:
            raw = judge.judge(system, user)
        except adapters.JudgeError as exc:
            print(f"\nABORTED after {i - 1} of {len(todo)}: {exc}")
            print("Nothing is lost. Fix the cause and re-run; the store resumes.")
            store.close()
            raise SystemExit(1)

        verdict = span = reason = error = None
        unfaithful = None
        try:
            p = parse(raw.text)
            verdict, unfaithful, span, reason = p["verdict"], p["unfaithful"], p["span"], p["reason"]
            ok = True
        except ParseError as exc:
            ok = False
            error = str(exc)
            parse_failures += 1

        store.add(Judgment(
            item_uid=sample.uid, batch=sample.batch, summarizer=sample.summarizer,
            judge_id=judge.judge_id, model_requested=judge.model_requested,
            model_version=raw.model_version, prompt_hash=phash,
            prompt_version=PROMPT_VERSION, repeat_idx=rep,
            verdict=verdict, unfaithful=unfaithful, span=span, reason=reason,
            parse_ok=ok, error=error, raw_response=raw.text,
            latency_ms=raw.latency_ms,
            input_tokens=raw.input_tokens, output_tokens=raw.output_tokens,
        ))

        if i % 25 == 0 or i == len(todo):
            pct = 100 * i / len(todo)
            print(f"  {i:>5}/{len(todo)} ({pct:5.1f}%)  parse failures: {parse_failures}")

    print(f"\ndone. {len(todo)} requested, {parse_failures} unparseable "
          f"({100 * parse_failures / len(todo):.1f}%).")

    drift = store.version_drift()
    if drift:
        print("\nWARNING: model version changed mid-study. Report this, do not hide it.")
        for d in drift:
            print(f"  {d['judge_id']}: {d['model_version']} x{d['n']} "
                  f"({d['first_seen']} .. {d['last_seen']})")
    store.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tier", required=True, choices=("mock",) + adapters.ALL_TIERS)
    ap.add_argument("--split", default="dev", choices=("dev", "test", "all"))
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--limit", type=int, help="cap items, for smoke tests")
    ap.add_argument("--stratified", action="store_true",
                    help="with --limit, draw evenly across labels and summarisers "
                         "instead of taking the first N")
    ap.add_argument("--model", help="override the tier's default model")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--schema", action="store_true",
                    help="Ollama tiers only: constrain output to a JSON schema")
    ap.add_argument("--no-think", dest="no_think", action="store_true",
                    help="all three arms: DISABLE the model's reasoning mode. "
                         "Reasoning is on by default; this runs the ablation "
                         "under a separate judge_id ending in _nothink")
    ap.add_argument("--db", default="data/judgments.sqlite")
    a = ap.parse_args()

    if a.stratified and not a.limit:
        ap.error("--stratified needs --limit; without a cap the whole split is used")

    kw: dict = {"temperature": a.temperature}
    if a.model:
        kw["model"] = a.model
    if a.schema:
        if a.tier not in adapters.OLLAMA_TIERS:
            ap.error(f"--schema applies to {' and '.join(adapters.OLLAMA_TIERS)} only")
        kw["schema"] = True
    if a.no_think:
        # gemini-3.5-flash-lite has no reasoning mode; mock has no model.
        if a.tier not in adapters.TIERS:
            ap.error("--no-think applies to the three arms only, not aux tiers")
        kw["think"] = False

    run(tier=a.tier, split=a.split, repeats=a.repeats, limit=a.limit,
        stratified=a.stratified, db=a.db, **kw)


if __name__ == "__main__":
    main()
