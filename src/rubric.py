"""The judge rubric. One prompt, three tiers, binary verdict.

Design decision, recorded because it shapes every downstream statistic:
**the judge returns a binary verdict, not FaithBench's four-level label.**

Reasons:

1. "Questionable" is not a property of the text. In FaithBench it means the human
   annotators were unsure. Asking a model to emit it asks it to simulate human
   uncertainty, which is a different task from detecting unfaithfulness.
2. "Benign" versus "Unwanted" is a harm judgement layered on top of a
   faithfulness judgement. Two tasks in one call, and the weaker tier will fail
   the second one for reasons unrelated to faithfulness.
3. TPR and TNR are undefined for multi-class without nominating a positive
   class, so a four-way judge would be binarised in analysis anyway.
4. A production gate is binary. The judge should do the job the gate does.

The four human levels are still used, on the human side: to build the reference
label (see loader.summary_label) and to slice the error analysis by difficulty.

The wording must match the reference label, or the study measures the wrong thing
------------------------------------------------------------------------------
The reference label uses FaithBench's own binarisation, in which ``Benign``
counts as faithful. v0.1 of this prompt said a summary is unfaithful if any claim
is unsupported "even if it seems harmless", which is the *strict* rule. Judge and
label were therefore answering different questions.

The first five-item pilot on qwen3:14b exposed it immediately: five items labelled
``Benign``, five UNFAITHFUL verdicts, and every stated reason correct. The judge
was not wrong, it was answering the question it had been asked. Pooled over 6,750
judgments this would have depressed every tier's measured accuracy for a reason
that has nothing to do with the judges.

v0.2 aligns the wording with the canonical binarisation. The strict binarisation
remains available as a sensitivity analysis, but it re-groups the *reference
labels* only. The judge is always instructed under the canonical definition, and
the paper states so, because scoring a judge against a rule it was never given
measures instruction mismatch rather than judgment.

v0.3 was drafted, tested and rejected. Recorded because a rejected iteration is
part of the instrument's provenance
---------------------------------------------------------------------------
The 20-item stratified pilot surfaced ``batch_1:0``: the source says "budget",
the summary says "production budget", and two annotators independently marked it
``Unwanted.Intrinsic`` on the reasoning that a film budget may also cover
distribution and advertising. All three judges passed it, and all three gave the
same reason: the *numbers* matched. None checked whether the *label attached to
the number* had changed. The criteria above list only things a summary **adds**
or **contradicts**, with no clause for a term it **narrows**, so this looked like
a genuine gap rather than annotator over-strictness.

v0.3 added a third bullet: "makes a term from the source more specific than the
source supports, so that the summary asserts a narrower claim than the source
does." All 60 judgments were re-run. Two pre-registered checks:

1. Specificity must not drop. **Passed.** Consistent 5/5 and Benign 5/5 on every
   judge under both versions, 30 of 30 negatives correct.
2. ``batch_1:0`` must flip to UNFAITHFUL. **Failed.** It stayed FAITHFUL on all
   three, and tier 1 explained why: "describing the budget as a production
   budget is a harmless paraphrase." The judge applied the new clause, weighed it
   against the harmless-detail sentence below, and the exemption won.

Rejected for a reason stronger than the failed check. The clause *does* work: it
flipped ``batch_1:35`` on tier 1, whose new reason quotes it almost verbatim
("'over 25' asserts a narrower, altered figure"). But tiers 2 and 3 already
caught that item **without** the clause. So v0.3's only real effect was to hand
the weakest-performing judge an explicit hint that let it match the other two.
In a study whose purpose is measuring differences between judges, prompting away
the differences is the one thing the instrument must not do. v0.3 also left the
rubric internally contradictory, since narrowing won on a numeric case and the
harmless-paraphrase exemption won on a noun modifier, with nothing to say which
governs. An instrument with an internal conflict is worse than one without, even
at marginally higher recall.

The Poseidon blind spot is therefore not patched, it is **reported**: it becomes
error analysis in the discussion chapter, where "every judge verified the
quantity and none verified its referent" is a finding rather than a defect.

Freeze protocol: iterate this file on the dev split only. When it stops changing,
record PROMPT_VERSION and the hash from `rubric_hash()` in appendix/prompts.md
together with the freeze date, then never touch it again before the test run.
"""

from __future__ import annotations

import hashlib
import json
import re

# Bump on every wording change. The hash is what actually goes in the appendix,
# but a human-readable version makes the run log readable.
#: FROZEN 08.08.2026. The `-dev` suffix is gone deliberately: this string and the
#: two below are now fixed for the remainder of the study. See appendix/prompts.md.
PROMPT_VERSION = "v0.2"

SYSTEM = """You are a careful fact-checker evaluating whether a summary is faithful to its source document.

A summary is UNFAITHFUL if it contains a claim that:
- contradicts the source document, or
- adds substantive information that the source does not support and that a reader would rely on, such as a name, number, date, outcome, quantity or causal claim that does not appear in the source.

A summary is FAITHFUL if every substantive claim is supported by the source. Not every unsupported detail makes a summary unfaithful. Treat a claim as acceptable when it is unsupported but harmless: a paraphrase, a reasonable generalisation, or a detail that does not change what a reader would take away from the summary. Judge the summary as a whole.

Judge only faithfulness to the source. Do not reward or penalise fluency, length, style, coverage, or how interesting the summary is. Do not use outside knowledge to decide whether a claim is true: the question is whether the source supports it, not whether it is correct in the world.

Respond with a single JSON object and nothing else:
{"verdict": "FAITHFUL" | "UNFAITHFUL", "span": "<the shortest quoted text from the summary that is unsupported, or null if FAITHFUL>", "reason": "<one sentence>"}"""

USER = """SOURCE DOCUMENT:
{source}

SUMMARY TO EVALUATE:
{summary}

Return the JSON object now."""


def render(source: str, summary: str) -> tuple[str, str]:
    """Return (system, user) message content for one judgment."""
    return SYSTEM, USER.format(source=source.strip(), summary=summary.strip())


def rubric_hash() -> str:
    """Stable hash of the exact prompt text. Goes on every stored judgment row.

    Any wording change produces a different hash, which is what makes the freeze
    verifiable after the fact rather than merely asserted.
    """
    payload = (SYSTEM + "\x00" + USER).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


# --- parsing ---------------------------------------------------------------

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class ParseError(ValueError):
    """Raised when a judge response cannot be read as a verdict.

    Not swallowed. A tier that cannot produce parseable output is a finding
    about that tier, so parse failures are counted and reported, never retried
    silently into a fake result.
    """


def parse(raw: str) -> dict:
    """Extract {verdict, span, reason} from a judge response.

    Tolerates the two things every model does anyway: fenced code blocks and
    prose wrapped around the JSON. Does not tolerate a missing or unrecognised
    verdict, because guessing there would manufacture data.
    """
    if not raw or not raw.strip():
        raise ParseError("empty response")

    match = _JSON_RE.search(raw)
    if not match:
        raise ParseError(f"no JSON object found in: {raw[:200]!r}")

    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ParseError(f"malformed JSON: {exc}; got {match.group(0)[:200]!r}") from exc

    verdict = str(obj.get("verdict", "")).strip().upper()
    if verdict not in {"FAITHFUL", "UNFAITHFUL"}:
        raise ParseError(f"unrecognised verdict {verdict!r}")

    return {
        "verdict": verdict,
        "unfaithful": verdict == "UNFAITHFUL",
        "span": obj.get("span") or None,
        "reason": (obj.get("reason") or "").strip(),
    }


if __name__ == "__main__":
    print(f"PROMPT_VERSION : {PROMPT_VERSION}")
    print(f"rubric_hash    : {rubric_hash()}")
    print(f"system chars   : {len(SYSTEM)}")
    ok = parse('```json\n{"verdict":"UNFAITHFUL","span":"production budget","reason":"Source says budget."}\n```')
    print(f"parse smoke    : {ok}")
