# How much LLM-judge agreement survives chance correction?

[![eval gate](https://github.com/sean-mas/llm-judge-reliability/actions/workflows/eval-gate.yml/badge.svg)](../../actions/workflows/eval-gate.yml)

Three LLM judges, spanning three deployment tiers a team could realistically
choose between, measured against the human expert annotations in **FaithBench**
(Bao et al., NAACL 2025): a paid frontier API, a hosted open-weight model, and an
open-weight model on local hardware.

7,012 judgments, pre-registered, with a held-out test split read exactly once.
Nothing here generates summaries or evaluates an agent. The summaries and the
human labels already exist. What is measured is the **judges**.

**The paper is in [`submission/`](submission/). The finding is below.**

---

## The finding

**For any release-gate threshold between 28.0% and 68.6%, all three judges ship a
release that the human labels would have blocked.** That band is 40.6 percentage
points wide and contains essentially every threshold a team would plausibly pick.

The cause is not noise. It is that all three judges flag far too little: 19.6%,
28.0% and 21.1% of items, against a reference unfaithful rate of 68.6%. Inside
the band, moving the threshold does not bring the two decisions together, because
what separates them is how much the judges detect rather than where the line sits.

## The numbers

Test split, 488 items, three repeats per item per judge, primary binarisation
scheme, temperature 0. The rubric was frozen on the development split before any
of these items was read.

| | Tier 1 paid | Tier 2 hosted | Tier 3 local |
|---|---|---|---|
| Raw agreement | 46.6% | 51.4% | 47.3% |
| **Cohen's kappa** | **0.129** | **0.162** | **0.131** |
| 95% CI (2,000 bootstrap resamples over items) | [0.084, 0.175] | [0.109, 0.214] | [0.083, 0.178] |
| PABAK | -0.069 | 0.029 | -0.055 |
| Sensitivity, unfaithful items caught | 0.253 | 0.349 | 0.269 |
| Specificity, faithful items passed | 0.930 | 0.868 | 0.916 |
| Parse failure rate | 0.5% | 2.9% | 2.5% |
| Kappa spread across three repeats | 0.014 | 0.020 | 0.017 |

Four things fall out of that table.

**Chance correction removes 33.7 to 35.2 points.** Raw agreement near 47% becomes
a kappa near 0.13, in the same direction on every tier. On this corpus a rule that
answered "unfaithful" to every item without reading it would score 68.6% raw
agreement and a kappa of exactly zero, so all three judges land *below* a rule
with no skill at all on the statistic the field usually reports. The human
annotators agree with each other 82.0% of the time on the same binary task.

**Deployment tier does not predict agreement.** Every paired bootstrap difference
contains zero, and none of the intervals is tight enough to claim the tiers are
equivalent either. This study did not detect a difference; it does not report one
that is not there.

| Pair | Difference in kappa | 95% CI |
|---|---|---|
| Tier 1 paid minus tier 2 hosted | -0.034 | [-0.078, +0.007] |
| Tier 1 paid minus tier 3 local | +0.002 | [-0.044, +0.045] |
| Tier 2 hosted minus tier 3 local | +0.036 | [-0.003, +0.074] |

**The errors are asymmetric, and averaging them hides the failure.** Specificity
runs from 0.868 to 0.930 and sensitivity from 0.253 to 0.349. The judges rarely
raise a false alarm and miss roughly seven tenths of what a gate exists to catch.
A single accuracy figure averages the two and reports neither, which is why catch
rate and false-alarm rate are reported separately throughout. Detection stays low
even on the category the benchmark treats as least doubtful: 29% to 39% of the
items human annotators marked *Unwanted*, the most severe of the four levels and
the largest group in the split at 290 items.

**The analyst's own choices move the result as far as the choice of judge does.**
Regrouping the identical judgments under FaithBench's other two binarisation
schemes moves kappa by up to 0.069, against a largest spread across tiers within
one scheme of 0.065. Every statistic is therefore reported under all three
schemes rather than under the one that reads best.

## Why these numbers are worth trusting

**The predictions were committed before the data was read.** Fourteen falsifiable
predictions live in [`appendix/predictions.md`](appendix/predictions.md), frozen
in commit `6892799` ("Freeze everything before the test split is read"). The
test split was read in `23c0610`. The order is in the git history and anyone
can check it. Ten held, two held in part, one was weakened to its margin, and
**prediction 4 was overturned** and is reported as overturned.

```bash
git log --oneline --reverse
git diff 6892799 23c0610 -- appendix/predictions.md
```

The diff shows exactly what was added after the data was seen: the verdict column,
and nothing else. No prediction, threshold or claim was reworded, softened,
removed or added.

**The instrument is frozen and the freeze is verifiable.** Every judgment row
carries the prompt version and a hash of the rubric. One query over all 7,012 rows
returns exactly one pair, `('v0.2', '3b14635aa1c3eecd')`. The same holds for model
versions: requested and served strings match on every row, so no drift occurred.

```bash
sqlite3 data/main.sqlite "SELECT DISTINCT prompt_version, prompt_hash FROM judgments;"
```

**CI asserts that the published result still reproduces.** `analysis/ci_gate.py`
runs on every push and checks integrity, exact reproduction of every headline
number, and the headline claim itself. It needs no API keys and costs nothing,
because the judgment store is committed and the harness caches everything, which
is a design property rather than a workaround.

## Reproduce it

The judgment store is committed, so the full analysis reproduces with no API keys
and no spend.

```bash
pip install -e .
python data/download_faithbench.py
python analysis/ci_gate.py
python analysis/stats.py --split test --i-am-ready-to-spend-the-test-split
```

The corpus is fetched rather than vendored: FaithBench is CC BY-NC-SA 4.0 and this
repository references it by item ID instead of redistributing it.
`analysis/gate_b_check.py` runs on the stdlib alone and needs no install at all.

`demo.py` is the fastest way to see the harness work end to end. Four acts: the
frozen prompt and its hash, one held-out summary, that summary judged live by the
local model, and then the disagreement itself, with the judge's stated reason
beside the exact spans the human annotators flagged and the notes they wrote. It
writes to no database.

```bash
python demo.py --gate
```

Act 3 needs Ollama with `gpt-oss:20b`, the study's tier 3. Every other act runs
without it. `--gate` adds a fifth act that re-derives every published figure from
the store.

## Running the judges

Re-running the judges themselves needs three credentials and costs about 22 USD
on the paid tier.

```bash
uv venv && uv pip install -e .
cp .env.example .env          # then fill it in
.venv/bin/python src/check_env.py
.venv/bin/python src/runner.py --tier local --split dev --repeats 3
```

Use `.venv/bin/python` rather than bare `python3`: `httpx` is installed in the
venv only. `.env` is loaded automatically, so there is no `source` step, and a
real environment variable always wins over the file.

`src/check_env.py` sends one tiny probe per tier and reports version, latency and
whether the reply parsed. It prints only the last four characters of a key, so its
output is safe to show on camera.

Re-running any command is free: everything already in the store is skipped, and
killing a run mid-way costs nothing. A transport failure aborts loudly rather than
filling the store with silence. A parse failure is recorded as data, because a
tier that cannot follow the output contract is a finding about that tier. The main
run survived two interruptions without losing a judgment; `logs/` holds the record.

### The three arms

Tiers are deployment models, not a capability ranking. Ordered by decreasing data
exposure, which is the axis the paper argues along.

| tier | `--tier` | model | data leaves? | weights knowable? | cost |
|---|---|---|---|---|---|
| 1 paid frontier | `paid` | `claude-opus-5` | yes | no | 22.21 USD measured |
| 2 hosted open | `hosted` | `gpt-oss:120b-cloud` | yes | yes | free plan |
| 3 local open | `local` | `gpt-oss:20b` | no | yes | free |

Tiers 2 and 3 are the same family and generation at roughly 6x scale apart, so the
contrast between them isolates size rather than confounding vendor, architecture
and generation with it. gpt-oss is the only family on Ollama Cloud with both a
cloud tag and a locally runnable tag, which is what makes that control affordable.

`--tier free` (Gemini) is **not an arm**. It is the free-tier proprietary judge
tier 2 used to be, kept on the dev split only so the free-tier quota finding stays
empirically grounded. It is never pooled with the three arms.

Pilot draws must use `--stratified` with `--limit`. Without it `--limit N` takes
the first N of a batch-ordered split: the first 4 dev items are all Benign and the
first 20 come from one summariser.

```bash
.venv/bin/python src/runner.py --tier local --split dev --limit 20 --stratified --repeats 1
```

## How it is built

```
src/loader.py        FaithBench into typed records, span annotations to item labels
src/rubric.py        the versioned spec: prompt text, PROMPT_VERSION, rubric_hash()
src/adapters/        four judges behind one interface, across three providers
src/runner.py        items x judges x repeats, cached, resumable
src/store.py         SQLite, one row per judgment, automatic drift detection
analysis/gate_b_check.py   dataset usability check, run before anything else
analysis/validate_loader.py  our labels against the authors' shipped worst-label
analysis/stats.py    every reported statistic, dev and test kept separate
analysis/robustness.py     the post-freeze sensitivity checks
analysis/ci_gate.py  the reproduction gate, and what CI runs
analysis/figures.py  numbered, captioned, exported as SVG
appendix/            the frozen prompt, the fourteen predictions, the analysis
                     decisions, model versions, measured cost, development record
data/main.sqlite     one row per judgment, committed with the paper
```

Four rules shaped the harness, and reproducibility was 15 percent of the mark.

1. **Cache every judgment**, keyed on item, judge, model version and prompt hash,
   so a resumable run can never silently reuse a judgment made under a different
   instrument.
2. **Record the model version the provider actually served**, not only the one
   requested. Four rows, one per judge, zero drift.
3. **Make the runner resumable.** A crash at judgment 2,000 must not cost the
   first 2,000.
4. **One row per judgment, never per item.** Aggregation happens in analysis, so
   the aggregation rule can change without re-running the study.

One row per judgment carrying model version, prompt hash, latency, token counts
and parse status is observability, and it is what makes the drift check, the
resumable cache and the CI gate possible at all.

### Data notes, learned the hard way

Read `src/loader.py` for the full schema. Three things that cause silent errors:

- **`sample_id` is unique within a batch only.** It restarts at 0 in each of the
  15 files. Key on `uid` (`"batch_1:0"`).
- **`annotator_id` is scoped to a batch.** The same person gets a fresh ID in each
  batch, so 42 IDs correspond to 14 people. For any cross-batch statement about an
  individual annotator, join on `annotator_name`.
- **"Consistent" is never written down.** It is the absence of annotations. Nobody
  records who reviewed a sample and found nothing, so annotator counts are
  unknowable for the 175 consistent samples.

### Secrets

`.env` is gitignored along with `.env.*`, `*.key`, `*.pem`, `*.p12`, `secrets.*`,
`credentials.*`, `*_token` and `*_secret`. Only `.env.example` is tracked. This
repository is published, so those patterns are deliberately broad.

## What it cost to run

Measured from the judgment store, not estimated.

| | Judgments | Median latency | Median output tokens |
|---|---|---|---|
| Tier 1 paid | 2,250 | 3.9 s | 138 |
| Tier 2 hosted | 2,250 | 5.0 s | 496 |
| Tier 3 local | 2,250 | 15.2 s | 461 |

Tier 1 cost **22.21 USD**, read from the provider console. List-price arithmetic
over the stored token counts gives 23.51 USD, a 5.5% residual that is reported
rather than reconciled away.

Two operational findings that appear in no agreement statistic. The local tier is
about four times slower per judgment, which for a check running on every pull
request is the difference between a gate and an obstacle. And the paid tier emits
roughly a third of the output tokens for a statistically indistinguishable
verdict. What the money did buy, measurably, is readable output: 0.5% of its
responses could not be parsed, against 2.9% and 2.5%.

## How this was built

The harness, the analysis and the first drafts were built with an AI coding
assistant. **Tier 1 of this study and the model that built the harness are the
same model, `claude-opus-5`.** That is a real conflict, disclosed in the paper as
well. The mitigation is that it is checkable rather than absent, and that the
result went against the conflicted arm: tier 1 came out lowest of the three on the
headline statistic.

The judgement calls stayed with me: the question, the dataset (the first one was
rejected on a label-skew check before any money was spent), the freezes and when
they happened, the fourteen predictions, and what counted as a finding. One
example is in `src/rubric.py`: the assistant proposed a rubric clause to fix the
study's sharpest failure case, it was tested on all 60 pilot judgments, it did not
fix that case and moved others, and it was rejected. The rejected version is kept
in the source rather than deleted.

## What this does not claim

FaithBench items were selected because existing detectors **disagreed** on them,
so these are hard cases and not a representative sample of production summaries.
Nothing here says LLM judges agree with humans 47% of the time in general; it says
they do so on cases chosen for difficulty. Three judges are three points, not a
trend, and only one of the two tier contrasts is controlled. English news
summarisation only. Reasoning modes are not equalised: each judge runs in its
vendor's default mode. The reference labels themselves have been criticised in
print, and that criticism is accepted rather than rebutted.

Nothing here says LLM judges are useless. It says they are validated on a
statistic that flatters them, and it shows how far the number moves once that is
corrected. Section 5.5 of the paper is the full version of this list.

## Licence and citation

Code is MIT ([`LICENSE`](LICENSE)). The paper, its figures and the prose here are
CC BY 4.0 ([`LICENSE-CONTENT`](LICENSE-CONTENT)).

FaithBench is CC BY-NC-SA 4.0, is referenced by item ID rather than redistributed,
and is due to Bao et al. (2025), *FaithBench: A Diverse Hallucination Benchmark
for Summarization by Modern LLMs*, NAACL 2025 (Short).
