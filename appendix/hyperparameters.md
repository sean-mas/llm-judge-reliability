# Appendix: judge configuration and measured operating cost

Everything a reader needs to re-run the study, plus the operational properties
that no agreement statistic reports. Values are read from the source and from
`data/main.sqlite`, not transcribed from memory.

## Configuration per tier

| | Tier 1 paid | Tier 2 hosted | Tier 3 local | Auxiliary |
|---|---|---|---|---|
| Model requested | `claude-opus-5` | `gpt-oss:120b-cloud` | `gpt-oss:20b` | `gemini-3.5-flash-lite` |
| Host | Anthropic API | Ollama Cloud | Ollama, local | Google API |
| Temperature | not accepted | 0.0 | 0.0 | 0.0 |
| Max output tokens | 1000 | 1000 | 1000 | 300 |
| Reasoning | adaptive, effort high | on | on | default |
| Request timeout | 300 s | 120 s | 120 s | 120 s |
| Transport retries | 3, exponential backoff | 3 | 3 | 3 |
| Repeats per item | 3 | 3 | 3 | 3, dev only |

**Temperature is 0 wherever the provider accepts it and is not a guarantee of
determinism.** The three repeats exist to measure what remains, and they measure
something: see chapter 4, Table 3, and the single-item case in chapter 5 where one
judge returns two different verdicts on identical input.

**The paid tier does not accept a `temperature` parameter for this model.** The
adapter carries `supports_temperature = False` and omits the field rather than
sending a value the provider ignores. This is the first of the two version-drift
incidents recorded in `appendix/versions.md`.

**Reasoning modes are deliberately not equalised**, and this is argued in chapter
3 rather than hidden here. The paid tier decides adaptively how much to reason;
the two open-weight tiers are switched on. Since the study compares deployments
rather than architectures, the vendor's default is part of what a tier delivers.

## Measured cost, from the judgment store

All figures over the full 750-item run, three repeats, 2,250 judgments per arm.

| Judge | Judgments | Median latency | Input tokens | Output tokens | Median output |
|---|---|---|---|---|---|
| Tier 1 paid | 2,250 | **3.9 s** | 2,658,369 | 408,672 | 138 |
| Tier 2 hosted | 2,250 | **5.0 s** | 1,880,928 | 1,165,008 | 496 |
| Tier 3 local | 2,250 | **15.2 s** | 1,880,928 | 1,109,610 | 461 |
| Auxiliary free | 262 | 0.7 s | 204,666 | 12,084 | 39 |

Two operational findings that belong in the paper and appear in no agreement
statistic.

**The local tier is roughly four times slower per judgment than the paid API**,
15.2 s against 3.9 s median, on the hardware described below. For a gate that runs
on every pull request this is the difference between a check and an obstacle, and
it is a genuine argument for the paid tier that has nothing to do with judgment
quality.

**The paid tier is also far more concise**, 138 median output tokens against 496
and 461. Under adaptive reasoning it chose to reason less on this task while
reaching statistically indistinguishable agreement. The open-weight tiers emit
roughly 3.5 times more output for the same verdict.

## Cost reconciliation

✅ **Investigated 10.08.2026. The arithmetic is settled, the residual is named, and
the earlier hypothesis is disproven.**

| | |
|---|---|
| Store, tier 1, all 2,250 rows | 2,658,369 input, 408,672 output |
| List price, `claude-opus-5` | 5.00 USD / 1M input, 25.00 USD / 1M output |
| Input at list | 13.29 USD |
| Output at list | 10.22 USD |
| **Implied total at list** | **23.51 USD** |
| **Provider console, read after the run** | **22.21 USD** |
| Residual | 1.30 USD, **5.5%**, unexplained |

**Prompt caching is ruled out and should not be offered as the explanation.** The
earlier draft of this appendix guessed at caching on the repeated rubric prompt.
That is wrong: no adapter in `src/` sets `cache_control`, so the harness never
requests caching and the provider never applies it. A guess that survives into a
submitted paper as an explanation is worse than an acknowledged gap.

**Two facts make the direction of the residual genuinely odd, and both should be
stated rather than smoothed.** All 2,250 tier 1 rows carry `created_at` on
2026-08-08 with a single `model_version`, so the store is not mixing runs or
model versions. And the separate probe databases (`opus_probe.sqlite`,
`smoke.sqlite`, `thinking_probe.sqlite`, `gate_c.sqlite`) recorded further paid
calls that are **not** in `main.sqlite`, which should push the console figure
*above* the store's implied total rather than below it.

**What to quote in the paper.** Quote **22.21 USD** as the cost, because that is
what was actually billed and money is a fact about the invoice rather than about
arithmetic. Report the token totals as the store's record, and footnote that
list-price arithmetic over those tokens gives 23.51 USD, a 5.5% difference that is
not explained by caching. **Do not quote both figures without that footnote.**

🟡 **One action worth taking before submission, and it may close this entirely.**
Re-read the provider console now that the run has been complete for two days.
Usage reporting commonly lags and is bucketed by UTC day, and the original reading
was taken close to the end of the run. If the console now reads near 23.50 USD,
the residual was a reporting lag and the paper can quote a single number.

## Hardware for the local tier

🔴 **TODO: record the machine.** Chip, memory, and Ollama version. The 15.2 s
median above is meaningless without it, and it is the number a practitioner
would use to decide whether tier 3 is viable for them.

## Corpus and split

- FaithBench release as cloned by the command in `README.md`. 750 summaries, 10
  summarising models, span-level human annotation under four levels.
- Split: 262 development, 488 test, stratified by summarising model **and** by
  reference label. Stratifying by summariser alone produced a twelve-point
  difference in the consistent rate between halves.
- Reference label per summary: most-severe-wins over the span annotations.
- Bootstrap: 2,000 percentile resamples, seed `20260809`, resampled over **items**
  rather than judgments.
