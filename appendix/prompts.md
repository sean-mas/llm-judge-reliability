# Appendix: the frozen judge prompt

**Frozen 08.08.2026.** Every judgment in the main run was produced with the exact
text below. Nothing here may be edited before the test split has been read.

| Field | Value |
|---|---|
| `PROMPT_VERSION` | `v0.2` |
| `rubric_hash()` | `3b14635aa1c3eecd` |
| Hash algorithm | `sha256(SYSTEM + "\x00" + USER)`, first 16 hex characters |
| Freeze date | 08.08.2026 |
| System prompt length | 1241 characters |

## Verifying this appendix

The hash is stored on every row of the results database, so the claim that all
6,750 judgments used one prompt is checkable rather than asserted:

```bash
cd faithbench-judge-study && .venv/bin/python src/rubric.py
```

That prints the version and hash of the file as it stands. It must read
`3b14635aa1c3eecd`. To confirm no judgment used a different prompt:

```sql
SELECT prompt_version, prompt_hash, COUNT(*) FROM judgments GROUP BY 1, 2;
```

A single row means the freeze held.

## System prompt, verbatim

```
You are a careful fact-checker evaluating whether a summary is faithful to its source document.

A summary is UNFAITHFUL if it contains a claim that:
- contradicts the source document, or
- adds substantive information that the source does not support and that a reader would rely on, such as a name, number, date, outcome, quantity or causal claim that does not appear in the source.

A summary is FAITHFUL if every substantive claim is supported by the source. Not every unsupported detail makes a summary unfaithful. Treat a claim as acceptable when it is unsupported but harmless: a paraphrase, a reasonable generalisation, or a detail that does not change what a reader would take away from the summary. Judge the summary as a whole.

Judge only faithfulness to the source. Do not reward or penalise fluency, length, style, coverage, or how interesting the summary is. Do not use outside knowledge to decide whether a claim is true: the question is whether the source supports it, not whether it is correct in the world.

Respond with a single JSON object and nothing else:
{"verdict": "FAITHFUL" | "UNFAITHFUL", "span": "<the shortest quoted text from the summary that is unsupported, or null if FAITHFUL>", "reason": "<one sentence>"}
```

## User message template, verbatim

```
SOURCE DOCUMENT:
{source}

SUMMARY TO EVALUATE:
{summary}

Return the JSON object now.
```

`{source}` and `{summary}` are substituted with the stripped text of each item.
No other content is sent: notably the human annotator's span and note are **not**
included, since that would leak the reference label into the judge's input.

## What was frozen and what was not

Frozen: the two strings above. Nothing else in the repository is covered by this
appendix.

Not frozen, and edited freely afterwards: everything under `analysis/`, which
reads the stored judgments and never writes them; the dev/test split, which is
deterministic and derived; and the served model version strings, which drift on
the providers' side and are therefore recorded per row rather than controlled.

Fixed in practice and recorded in `appendix/hyperparameters.md` rather than here:
temperature, maximum tokens and reasoning mode per tier.

## Iteration history

**v0.1**, discarded before any run. Defined a summary as unfaithful if any claim
was unsupported "even if it seems harmless", which is the *strict* rule, while
the reference labels use FaithBench's canonical binarisation in which `Benign`
counts as faithful. A five-item pilot on `qwen3:14b` returned five `Benign` items
as UNFAITHFUL with every stated reason correct. The judge was not wrong; it was
answering the question it had been asked.

**v0.2**, frozen. Aligns the wording with the canonical binarisation.

**v0.3**, drafted, tested on all 60 pilot judgments, and rejected. It added a
third UNFAITHFUL criterion for a term the summary *narrows*, to address
`batch_1:0`, where the source says "budget", the summary says "production
budget", and two annotators independently marked it `Unwanted.Intrinsic`.
Specificity survived the change (Consistent and Benign stayed 5/5 on all three
judges), but the target item did not flip, and tier 1 stated why: "describing the
budget as a production budget is a harmless paraphrase". It was rejected for a
stronger reason than the failed check. The clause did work on `batch_1:35`, but
tiers 2 and 3 already caught that item without it, so its only real effect was to
give the weakest judge a hint that let it match the other two. In a study
measuring differences between judges, prompting those differences away is the one
thing the instrument must not do. Full record in the `src/rubric.py` docstring.
