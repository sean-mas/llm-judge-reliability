# Appendix: what dev predicted, before test was read

**Provenance, and it has to be exact, because a loose claim here undoes the point
of the file.**

- **Written 09.08.2026, before the test split was read**, and committed as part of
  `3b9f3be`, "Freeze everything before the test split is read". That commit holds
  the pre-test state of this file and anyone can diff against it.
- **Two things were appended after the test read and nothing else was touched**:
  the `Verdict` column of the prediction table, and the section headed "E1,
  answered". No prediction, threshold or claim has been reworded, softened,
  removed or added.
- **The `H` column is presentational and was added afterwards.** It groups the
  fourteen predictions into the five hypotheses that chapter 3.2 states. **The
  grouping is not itself pre-registered**; the predictions are, and they are what
  carry the evidential weight.

An earlier version of this header said simply "not edited afterwards", which was
wrong on its face given the verdict column below it. The precise version is both
more honest and more useful.

The rubric freeze fixed the question. The analysis freeze fixed the statistics.
This file fixes the *interpretation*, and it exists because the other two are not
enough on their own.

Chapter 5 was drafted against dev and instructs its author to revisit every claim
once test is read and mark it confirmed, weakened or overturned. That instruction
is worth nothing while the claims live as prose, because prose can be reread
generously. Below they are numbered, quantified and falsifiable. After the test
run, each row gets a verdict and none of them gets rewritten.

**How to read the verdict column.** A prediction that fails is a result, not an
embarrassment. Thirteen confirmations would say the dev/test split found nothing;
a mix is what an honest split looks like. The one thing that would damage the
paper is a claim quietly adjusted to match.

| # | H | Claim, from dev | Prediction for test | Verdict |
|---|---|---|---|---|
| 1 | H1 | Deflation, raw minus kappa, is 33.4 to 34.7 pp on every arm | 30 to 38 pp on all three, same direction | ✅ **held.** 33.7 / 35.2 / 34.1 |
| 2 | H1 | Kappa is 0.152 to 0.194 on the three arms | every arm in [0.10, 0.25] | ✅ **held.** 0.129 / 0.162 / 0.131, all lower than dev |
| 3 | H2 | All three bootstrap intervals overlap; no arm is distinguishable | still overlapping | ✅ **held.** Common overlap [0.109, 0.175] |
| 4 | H2 | Repeat-to-repeat spread (0.046 on tier 2) exceeds the best-to-worst tier gap (0.042) | at least one arm's spread still exceeds the between-tier gap | ❌ **overturned.** Largest spread 0.020 against a 0.033 gap |
| 5 | H1 | PABAK is -0.028, 0.076, 0.059 | every arm within 0.15 of zero | ✅ **held.** -0.069 / 0.029 / -0.055 |
| 6 | H3 | TNR 0.874 to 0.949 far exceeds TPR 0.260 to 0.372 | TNR > TPR on every arm, and every TPR below 0.50 | ✅ **held.** TNR 0.930 / 0.868 / 0.916 against TPR 0.253 / 0.349 / 0.269 |
| 7 | -- | Parse failures order down the ladder: 0.5 / 2.3 / 3.4% | tier 1 < tier 2 < tier 3, tier 1 below 1.5% | ⚠️ **half held.** 0.5 / 2.9 / 2.5: tier 1 still lowest and under 1.5%, but the ladder ordering breaks, tier 2 is now worst |
| 8 | H3 | Tier 1 flags *Questionable* (1%) less often than *Consistent* (5%), an inversion | tier 1's *Questionable* rate at or below its *Consistent* rate | ✅ **held.** 4% against 9% |
| 9 | H3 | Detection on *Unwanted*, the clearest class, is only 31 / 41 / 37% | every arm between 25 and 50% | ✅ **held.** 29 / 39 / 31% |
| 10 | H4 | A divergence band exists where all three judges ship what truth blocks, 38.1 pp wide | band exists and exceeds 25 pp | ✅ **held, and wider.** 40.6 pp |
| 11 | H5 | Kappa falls monotonically U > U+Q > U+Q+B on every arm | monotone on all three | ✅ **held**, but tier 1's first step is 0.130 to 0.129, which is flat rather than falling |
| 12 | H5 | The scheme swing (up to 0.088) exceeds the between-tier spread (0.046) | swing still larger than spread | ⚠️ **weakened to the edge.** Largest swing 0.069 against a largest spread of 0.065. The dev margin of 0.042 collapses to 0.004 |
| 13 | H1 | Raw agreement is below the no-skill baseline of 67.2% on every arm | still below the test-split prevalence on every arm | ✅ **held.** 46.6 / 51.4 / 47.3% against a test prevalence of 68.6% |
| 14 | H3 | Strata order: no annotation highest, disagreed lowest | same ordering | ⚠️ **half held.** No annotation is highest on all three, but *disagreed* is the lowest stratum only for tier 1. On tiers 2 and 3 the single-annotator stratum is now the hardest |

## Score: ten held, two half held, one weakened to the edge, one overturned

**Recorded because a clean sweep would have been the suspicious outcome.** A
dev/test split that confirms everything either found nothing or was not a real
split. Three claims moved, one of them the claim this study was most attached to.

**The overturned one, number 4, was load-bearing and is now gone.** On dev, tier 2
varied against itself by 0.046 across three repeats at temperature 0, more than
the 0.042 gap between the best and worst arm, and chapter 5 used that to argue
that any tier ranking is noise. On test the repeat spreads shrink to 0.014, 0.020
and 0.017 while the tier gap is 0.033, so the argument in that form does not
survive.

**The conclusion does survive, on the stronger evidence.** Prediction 3 held: the
bootstrap intervals still overlap across a common band of [0.109, 0.175], so no
arm is distinguishable from another at 95% confidence. The overlapping intervals
were always the better argument, and the repeat-variance argument was the
memorable one. Chapter 5 must lead with the interval and demote the variance claim
to what it now is: an observation that the instrument is stable enough at 488
items for the repeats to stop dominating, which is itself worth one sentence about
sample size.

## E1, as recorded before the test read

**Rogan-Gladen, calibrated on dev and applied to test.** No prediction is recorded
because none is honest. On dev the correction is algebraically an identity and
says nothing (see `appendix/analysis.md`), so dev provides no basis for guessing
whether transporting dev's TPR and TNR onto test recovers test's true rate.

Youden's J of 0.21 to 0.25 puts the estimator near its unstable regime, so the
interval is the reportable quantity and the point estimate should be treated with
suspicion whichever way it lands. If the corrected rate lands near the true test
rate with an interval narrow enough to be useful, chapter 5 gains its one
constructive recommendation: these judges fail as gates but work as meters, once
calibrated. If it does not, the paper says so, and the conclusion is simply that
the judges are not usable either way.

**This is the only part of the study whose result could still surprise its
author**, which makes it the honest place to point the reader's attention.

## E1, answered

**This section was appended after the test read. Everything above the previous
heading was frozen before it.**

**Rogan-Gladen calibrated on dev and applied to test.** The calibration never saw
these items, so this is the study's only genuine out-of-sample test.

| Judge | dev TPR | dev TNR | test flag rate | estimated true rate | actual | error |
|---|---|---|---|---|---|---|
| Tier 1 paid | 0.260 | 0.949 | 19.6% | 69.1% | 68.6% | **+0.5 pp** |
| Tier 2 hosted | 0.372 | 0.874 | 28.0% | 62.7% | 68.6% | -5.9 pp |
| Tier 3 local | 0.327 | 0.926 | 21.1% | 54.1% | 68.6% | -14.5 pp |

**This is the one result in the study that separates the tiers, and it separates
them in the opposite order to the agreement statistics.** Tier 1 has the lowest
kappa of the three and the lowest TPR, and it is the only judge that recovers the
true failure rate to within a point. Tier 3 misses by 14.5 points.

The mechanism is checkable rather than mysterious. What the estimator needs is not
a good judge but a *stable* one, because it transports dev's error rates onto test
and any drift in them propagates. TPR drift from dev to test was -0.007 for tier
1, -0.023 for tier 2 and -0.058 for tier 3, which is the same ranking as the
errors above. The amplification is the estimator's own sensitivity,
`dp/dTPR = -p/J`, roughly 2.7 at these values, so tier 3's six-point calibration
drift becomes a fifteen-point error in the estimate. Predicted -15.7 pp against an
observed -14.5 pp.

**No prediction was recorded for this row and none would have been right.** The
expected answer, if any, was that the better judges would make the better meters.

## Predictions this study does not make

Nothing is predicted about which findings the paper leads with, or about the
relative ordering of the three tiers beyond claim 3. Pre-committing to a narrative
would be the same error as post-hoc statistic shopping, in the opposite direction.
