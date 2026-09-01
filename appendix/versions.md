# Appendix: model versions and drift

**Version drift is treated here as a measurement problem rather than assumed
away.** A study that compares three judges is worthless if it cannot show that
each judge stayed the same judge for the duration, and "we used GPT-4" is not a
claim a reader can check. Every judgment row therefore records both the model
string that was *requested* and the version string the provider *served*, and the
two are compared automatically.

## What the store says

Query, and the result is the whole claim:

```sql
SELECT judge_id, model_requested, model_version, COUNT(*)
FROM judgments GROUP BY judge_id, model_requested, model_version;
```

| Judge | Requested | Served | Judgments |
|---|---|---|---|
| `tier1_paid` | `claude-opus-5` | `claude-opus-5` | 2,250 |
| `tier2_hosted_open` | `gpt-oss:120b-cloud` | `gpt-oss:120b-cloud` | 2,250 |
| `tier3_local` | `gpt-oss:20b` | `gpt-oss:20b` | 2,250 |
| `tier2_free` (auxiliary) | `gemini-3.5-flash-lite` | `gemini-3.5-flash-lite` | 262 |

**Four rows, one per judge. Zero drift across 7,012 judgments.** Had a provider
swapped a model mid-run, a fifth row would exist and the affected judgments would
be identifiable to the item.

The same discipline covers the prompt. Every row carries `prompt_version` and
`prompt_hash`, and the store contains exactly one distinct pair,
`('v0.2', '3b14635aa1c3eecd')`. See `appendix/prompts.md`.

## Two drift incidents, both during setup, both before the main run

Recorded because they are the evidence that the checking is not decorative. Both
were caught by the harness rather than noticed by accident.

**1. A parameter was withdrawn.** The paid provider stopped accepting the
`temperature` parameter for the selected model. Sending it produced an error
rather than being silently ignored, which is the better failure. The adapter now
carries `supports_temperature = False` and omits the field. The consequence for
the study is stated in chapter 3 rather than buried: tier 1 runs at the provider's
default sampling behaviour while tiers 2 and 3 run at an explicit temperature 0,
so "temperature 0 throughout" would be an overstatement and is not made.

**2. A model tag was retired.** A model tag on the open-weight host returned HTTP
410 together with a retirement date. This is the failure mode the version column
exists for: a study run three months earlier would have used a model a reader
cannot obtain today, and only a recorded version string makes that visible.

## Two interruptions during the main run, neither costing a judgment

Not version drift, but they belong in the same appendix because they are the other
half of the reproducibility claim: the run was interrupted twice and lost nothing.

The cache key is `(item, judge, model version, prompt hash)`, so a resumed run
recomputes only what is genuinely missing. **A judgment made under a different
model version or a different prompt could not be silently reused**, which is what
makes resumption safe rather than merely convenient.

**1. Read timeouts on the paid tier.** The run stopped at 59.5% of tier 1 when
repeated read timeouts exhausted the launcher's patience. Cause: a 120 s default
timeout against a reasoning model, and adapters with no retry on transport errors.
Fixed three ways: a `retryable` flag on the error type, a 300 s timeout on the paid
adapter, and exponential backoff in the adapter itself.

**2. A session usage limit on the hosted tier.** The hosted tier stopped at 78.8%
against a session quota that lasted roughly two hours, while the launcher's
backoff topped out at twenty minutes. Fixed by making the launcher's backoff
progressive: 120 s four times, then 600 s six times, then 1800 s fourteen times,
about nine hours in total.

**The verbatim error, from `logs/hosted.log`.** The account handle is replaced with
`<account>`; nothing else is altered.

```
ABORTED after 1774 of 2250: tier2_hosted_open: rate limited or quota exhausted (429).
{"error":"you (<account>) have reached your session usage limit, upgrade for higher
limits: https://ollama.com/upgrade (ref: 26ea75c6-e6c9-4fde-812d-cb8480f12a8d)"}
```

The run aborted loudly at judgment 1,774 of 2,250 rather than recording silence, and
the cache meant the resumed run repeated none of the completed work. Ten further
attempts returned the same error before the session window reset.

**The lesson worth one sentence in chapter 3 is not either bug.** It is that both
runs failed silently: the wrapper exited 0, the logs stopped, and nothing
announced that a nine-hour job had stopped after ninety minutes. The instrument
now retries; it still does not shout.
