# Appendix: the development record

**What this is.** Every statistic computed on the **development split**, 262 items,
before the test split was read. Created 10.08.2026 by moving these tables out of
chapter 4, where they had no place once test existed.

**Why it exists rather than being deleted.** The development split is what the
rubric was tuned on and what the fourteen predictions in `appendix/predictions.md`
were written from. **A reader cannot judge whether those predictions were
demanding without seeing the numbers they were written against.** Deleting the dev
tables would leave the pre-registration unauditable, which would defeat its
purpose.

**What it is not.** These are **not results**. Dev is the split the instrument was
built on, so agreement statistics computed on it are optimistic by construction.
Every claim in the paper rests on the test split. Nothing here should be quoted as
a finding, and chapter 4 references this appendix rather than reproducing it.

Source: `analysis/stats-dev-2026-08-09.txt` and
`analysis/production-dev-2026-08-09.txt`, prompt `v0.2` / `3b14635aa1c3eecd`.

The auxiliary judge `tier2_free` (`gemini-3.5-flash-lite`) appears here marked with
an asterisk. It ran on dev only and is **never pooled with the three arms**, for
the reason recorded in `drafts/outline.md`: its `judge_id` shares a string prefix
with tier 2, so any analysis grouping by prefix would silently merge them.

---

## D1. Parse failures, development split

| Judge | Judgments | Failed | Rate |
|---|---|---|---|
| Tier 1 paid | 786 | 4 | 0.5% |
| Tier 2 hosted | 786 | 18 | 2.3% |
| Tier 3 local | 786 | 27 | 3.4% |
| *Auxiliary free | 262 | 2 | 0.8% |

**This is the table that produced prediction 7 and it is the reason that prediction
half held.** On dev the failure rate orders monotonically down the deployment
ladder, 0.5 / 2.3 / 3.4%, which read as parse reliability tracking model scale. On
test the ordering breaks: 0.5 / 2.9 / 2.5%. The paid tier's advantage survives; the
ladder reading does not.

## D2. Agreement under all three binarisation schemes, development split

**Scheme U** (positives: Unwanted)

| Judge | n | Raw | Kappa | 95% CI | PABAK | Deflation | TPR | TNR | Flag |
|---|---|---|---|---|---|---|---|---|---|
| Tier 1 paid | 629 | 0.493 | 0.170 | [0.102, 0.244] | -0.014 | 0.323 | 0.306 | 0.946 | 0.232 |
| Tier 2 hosted | 619 | 0.549 | 0.210 | [0.129, 0.295] | 0.099 | 0.340 | 0.413 | 0.874 | 0.328 |
| Tier 3 local | 609 | 0.542 | 0.216 | [0.136, 0.303] | 0.084 | 0.325 | 0.374 | 0.925 | 0.282 |
| *Auxiliary | 210 | 0.471 | 0.127 | [0.048, 0.209] | -0.057 | 0.345 | 0.297 | 0.887 | 0.243 |

**Scheme U+Q, primary.** The rule the frozen rubric gives the judge.

| Judge | n | Raw | Kappa | 95% CI | PABAK | Deflation | TPR | TNR | Flag |
|---|---|---|---|---|---|---|---|---|---|
| Tier 1 paid | 782 | 0.486 | 0.152 | [0.092, 0.216] | -0.028 | 0.334 | 0.260 | 0.949 | 0.192 |
| Tier 2 hosted | 768 | 0.538 | 0.190 | [0.118, 0.268] | 0.076 | 0.347 | 0.372 | 0.874 | 0.290 |
| Tier 3 local | 759 | 0.530 | 0.194 | [0.121, 0.271] | 0.059 | 0.336 | 0.327 | 0.926 | 0.241 |
| *Auxiliary | 260 | 0.469 | 0.110 | [0.035, 0.186] | -0.062 | 0.359 | 0.264 | 0.884 | 0.215 |

**Scheme U+Q+B.** Also FaithJudge's scheme.

| Judge | n | Raw | Kappa | 95% CI | PABAK | Deflation | TPR | TNR | Flag |
|---|---|---|---|---|---|---|---|---|---|
| Tier 1 paid | 782 | 0.402 | 0.098 | [0.052, 0.148] | -0.197 | 0.304 | 0.234 | 0.946 | 0.192 |
| Tier 2 hosted | 768 | 0.469 | 0.129 | [0.070, 0.191] | -0.062 | 0.340 | 0.342 | 0.874 | 0.290 |
| Tier 3 local | 759 | 0.449 | 0.129 | [0.071, 0.191] | -0.101 | 0.321 | 0.295 | 0.925 | 0.241 |
| *Auxiliary | 260 | 0.400 | 0.075 | [0.015, 0.137] | -0.200 | 0.325 | 0.247 | 0.887 | 0.215 |

**Deflation is 30.4 to 35.9 points across every arm and every scheme**, which is
the band prediction 1 was written from and which test confirmed at 33.7 to 35.2.

## D3. Variance across the three repeats, kappa, temperature 0, scheme U+Q

| Judge | Repeat 0 | Repeat 1 | Repeat 2 | Spread |
|---|---|---|---|---|
| Tier 1 paid | 0.159 | 0.144 | 0.154 | 0.015 |
| Tier 2 hosted | 0.204 | 0.206 | 0.160 | **0.046** |
| Tier 3 local | 0.202 | 0.203 | 0.177 | 0.026 |

**This is the table behind the study's one overturned prediction and it should be
read alongside chapter 4, Table 3.** Tier 2's spread of 0.046 exceeds the 0.042
gap between the best and worst arm on dev, which is what licensed the claim that a
judge re-run on identical inputs moves further than the distance between deployment
tiers. On the 488-item test split the spreads collapse to 0.014 to 0.020 against a
0.033 gap and the claim does not survive. **Prediction 4, overturned.**

## D4. Detection by severity level, development split, scheme U+Q

Items per level: Consistent 62, Benign 24, Questionable 27, Unwanted 149.

| Judge | Consistent | Benign | Questionable | Unwanted |
|---|---|---|---|---|
| Tier 1 paid | 5% (10/184) | 4% (3/72) | **1% (1/81)** | 31% (136/445) |
| Tier 2 hosted | 13% (23/183) | 13% (9/71) | 14% (11/78) | 41% (180/436) |
| Tier 3 local | 8% (14/186) | 7% (5/71) | 8% (6/79) | 37% (158/423) |
| *Auxiliary | 11% (7/62) | 12% (3/24) | 8% (2/26) | 30% (44/148) |

Prediction 8, the *Questionable* inversion, was written from tier 1's 1% against
5% here. On test it held at 4% against 9%, and appeared on tier 3 as well.

## D5. Release-gate threshold simulation, development split

True unfaithful rate on dev: **67.2%**.

| Judge | Flag rate | Ships but truth blocks for T in |
|---|---|---|
| Tier 1 paid | 19.2% | [19.2%, 67.2%) |
| Tier 2 hosted | 29.0% | [29.0%, 67.2%) |
| Tier 3 local | 24.1% | [24.1%, 67.2%) |

Divergence band **38.1 points**. On test it widened to 40.6.

## D6. Rogan-Gladen on dev, and why these numbers are worthless

| Judge | Flag | TPR | TNR | J | Corrected | 95% CI |
|---|---|---|---|---|---|---|
| Tier 1 paid | 19.2% | 0.260 | 0.949 | 0.210 | 67.3% | [61.7%, 72.8%] |
| Tier 2 hosted | 29.0% | 0.372 | 0.874 | 0.246 | 66.9% | [61.1%, 72.6%] |
| Tier 3 local | 24.1% | 0.327 | 0.926 | 0.253 | 66.1% | [60.5%, 71.7%] |

True rate 67.2%. All three land within 1.1 points, which looks like a triumph.

**It is not a result, it is an identity check.** Calibrating sensitivity and
specificity on the same sample whose flag rate is then corrected returns the true
rate as algebra, for any judge however bad. Substituting
`flag = TPR*p + (1-TNR)*(1-p)` into the estimator recovers `p` exactly. **The only
informative quantity in this table is the interval width**, roughly plus or minus
5.5 points, which says how precisely a calibration set of 262 items pins the rate
down.

**This table is precisely why E1 carried no directional prediction.** Dev offered
no honest basis for guessing what a genuine out-of-sample transfer would do. The
non-circular result is chapter 4, Table 6.

## D7. Stratification by annotator agreement, development split

Strata: 46 unanimous, 101 disagreed, 53 single annotator, 62 no annotation.

| Judge | Unanimous | Disagreed | Single annotator | No annotation |
|---|---|---|---|---|
| Tier 1 paid | 52.6% (n=137) | 23.5% (n=302) | 39.6% (n=159) | 94.6% (n=184) |
| Tier 2 hosted | 59.1% (n=132) | 36.7% (n=294) | 42.1% (n=159) | 87.4% (n=183) |
| Tier 3 local | 56.2% (n=128) | 30.4% (n=289) | 44.9% (n=156) | 92.5% (n=186) |

**The table that produced prediction 14 and the "judges fail where humans found it
hard" reading.** On dev the *disagreed* stratum is the hardest for every arm, and
tier 2 shows a 22.4-point gap between unanimous (59.1%) and disagreed (36.7%). On
test that gap shrinks to under four points and the hardest stratum becomes *single
annotator* for tiers 2 and 3. **Prediction 14, half held**, and chapter 5 reports
the difficulty reading as available for tier 1 only.

---

## What the development split cost, and what it bought

262 of 750 items, 35% of the corpus, spent before any result was reported.

**What it bought**, in the order the paper uses it:

1. **A tuned and then frozen rubric.** Three iterations on dev, then `v0.2` frozen
   with a hash on every row. A fourth iteration, `v0.3`, was drafted, tested on all
   60 pilot judgments and rejected, because its only measurable effect was to give
   the weakest judge a hint that let it match the other two.
2. **Fourteen falsifiable predictions**, which cost the study one claim it was
   attached to and weakened two others.
3. **The calibration for E1**, the sensitivity and specificity transported onto
   test. **This is the one use of dev that produced a headline result**, and it
   required dev to be genuinely untouched by test.
4. **The knowledge that same-sample Rogan-Gladen is an identity**, which is what
   made the non-circular design necessary rather than optional.

**Whether 35% was the right price is a fair question and the paper should not dodge
it.** A smaller development split would have left more items for the test estimate
and narrowed every confidence interval. What it would also have done is weaken the
E1 calibration, which is the study's most interesting finding and the one that
depends most directly on dev being large enough to estimate two rates stably.
