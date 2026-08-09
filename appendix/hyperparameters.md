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

🔴 **TODO before submission: reconcile the token counts above with the 22.21 USD
figure taken from the provider console.** At list prices the store's token totals
imply roughly 23.50 USD, so the two disagree by about a euro. Do not quote both
without an explanation. The likely cause is prompt caching on repeated system
prompts, which is billed below the input rate and which the store does not record
separately. Either establish that and say so, or quote the console figure alone
and describe the token counts as uncached equivalents.

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
