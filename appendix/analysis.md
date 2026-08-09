# Appendix: the frozen analysis

**Frozen 09.08.2026, before the test split was read.**

The rubric freeze (`appendix/prompts.md`) guarantees that every judgment answered
the same question. This second freeze guarantees something different and equally
necessary: that the *analysis* was fixed before the exam data was seen.

Without it, the dev/test split protects nothing. An analyst free to keep trying
statistics after reading test can always find one that flatters the result, and
no reader can distinguish that from an honest first attempt. Fixing the code
first is what makes "we read test once" a checkable claim rather than a promise.

| File | sha256, first 16 |
|---|---|
| `analysis/stats.py` | `8ad8cc2859a8cc4d` |
| `analysis/production.py` | `259c9cd335bdd91e` |
| `src/loader.py` | `0fa064bf415601c3` |
| `src/rubric.py` | `af8654b9fbba0391` |

Verify with:

```bash
shasum -a 256 analysis/stats.py analysis/production.py src/loader.py src/rubric.py
```

## What was settled before test was read

Every analysis decision below was made on the development split alone.

**Primary statistic.** Cohen's kappa, with raw agreement reported alongside so
the deflation between them is visible. PABAK reported as the prevalence-adjusted
check, following Byrt et al.'s own recommendation to report the adjustment
alongside kappa rather than in place of it.

**Binarisation.** All three FaithBench schemes (U, U+Q, U+Q+B), with U+Q primary
because it is the rule the frozen rubric gives the judge. The other two are
labelled sensitivity analyses.

**Confidence intervals.** Percentile bootstrap, 2,000 resamples, seed 20260809,
resampled over **items** rather than judgments, because the three repeats of one
item are not independent observations.

**Parse failures.** Reported as their own rate, then excluded from every
agreement statistic. A judgment that cannot be read is a fact about the tier's
operational reliability, not evidence about its judgment.

**Severity strata.** FaithBench's four levels, reported separately.

**Agreement strata.** Four levels: unanimous, disagreed, single annotator, no
annotation. Defined in `production.py:agreement_stratum`.

**Release-gate simulation.** A gate blocks when the flagged share exceeds a
threshold T. Reported as the band of T over which judge and truth disagree,
rather than at a single chosen threshold.

**Rogan-Gladen.** Calibrated on **dev**, applied to **test**. The same-sample
version is algebraically an identity and is printed only as an implementation
check, with a warning above it in the output. This distinction was written into
the code before test was read, which is the point of recording it here.

## Added after the freeze: `analysis/figures.py`

**Added 09.08.2026, after the four files above were frozen and still before test
was read.** Recorded here rather than quietly, because a file added to the
analysis directory after a freeze is exactly the kind of thing a freeze exists to
make visible.

| File | sha256, first 16 |
|---|---|
| `analysis/figures.py` | `95ef1930ce3c6dab` |

It computes nothing. Every value it draws comes from `stats.stats()` and
`stats.SCHEMES`, imported from the frozen module rather than reimplemented, and
the one quantity not returned directly by that function, the expected agreement
*pe*, is recovered by inverting kappa's own definition as `(po - k) / (1 - k)`
rather than recomputed from the corpus prevalence. Those two routes do not give
the same number, because each judge's pairs exclude that judge's own parse
failures, so its class balance differs slightly from the corpus rate. Inverting
the definition is what makes a figure structurally incapable of disagreeing with
the table above it.

It carries the same test-split guard as `stats.py`. A figure is a look at the data
exactly as a table is.

## What was deliberately not decided in advance

Which findings the paper leads with. That depends on what test says, and
pre-committing to a narrative would be the same error in the opposite direction.
