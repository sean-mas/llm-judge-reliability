# Appendix: what dev predicted, before test was read

**Written 09.08.2026, before the test split was read. Not edited afterwards.**

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

| # | Claim, from dev | Prediction for test | Verdict |
|---|---|---|---|
| 1 | Deflation, raw minus kappa, is 33.4 to 34.7 pp on every arm | 30 to 38 pp on all three, same direction | |
| 2 | Kappa is 0.152 to 0.194 on the three arms | every arm in [0.10, 0.25] | |
| 3 | All three bootstrap intervals overlap; no arm is distinguishable | still overlapping | |
| 4 | Repeat-to-repeat spread (0.046 on tier 2) exceeds the best-to-worst tier gap (0.042) | at least one arm's spread still exceeds the between-tier gap | |
| 5 | PABAK is -0.028, 0.076, 0.059 | every arm within 0.15 of zero | |
| 6 | TNR 0.874 to 0.949 far exceeds TPR 0.260 to 0.372 | TNR > TPR on every arm, and every TPR below 0.50 | |
| 7 | Parse failures order down the ladder: 0.5 / 2.3 / 3.4% | tier 1 < tier 2 < tier 3, tier 1 below 1.5% | |
| 8 | Tier 1 flags *Questionable* (1%) less often than *Consistent* (5%), an inversion | tier 1's *Questionable* rate at or below its *Consistent* rate | |
| 9 | Detection on *Unwanted*, the clearest class, is only 31 / 41 / 37% | every arm between 25 and 50% | |
| 10 | A divergence band exists where all three judges ship what truth blocks, 38.1 pp wide | band exists and exceeds 25 pp | |
| 11 | Kappa falls monotonically U > U+Q > U+Q+B on every arm | monotone on all three | |
| 12 | The scheme swing (up to 0.088) exceeds the between-tier spread (0.046) | swing still larger than spread | |
| 13 | Raw agreement is below the no-skill baseline of 67.2% on every arm | still below the test-split prevalence on every arm | |
| 14 | Strata order: no annotation highest, disagreed lowest | same ordering | |

## The one genuinely open question

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

## Predictions this study does not make

Nothing is predicted about which findings the paper leads with, or about the
relative ordering of the three tiers beyond claim 3. Pre-committing to a narrative
would be the same error as post-hoc statistic shopping, in the opposite direction.
