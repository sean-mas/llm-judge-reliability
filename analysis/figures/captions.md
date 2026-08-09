# Figures

Numbered, captioned, and referenced from the prose. The module brief requires all three.

Export note: `.svg` is the master. Word 2016 and later imports SVG directly (Insert, Pictures). For LaTeX use the `svg` package, or convert with `rsvg-convert -f pdf` or `cairosvg`. Do not export to PNG for the paper; vector stays sharp at print resolution.

---

## Figure 1: Study pipeline

**File:** `figure-1-pipeline.svg`
**Belongs in:** chapter 3, Methode. Place after the data subsection and before the analysis subsection.
**Status:** placeholder, numbers current as of 05.08.2026. Re-export if the dev/test split or corpus counts change.

**Draft caption.** Rewrite in own voice before submission.

> Figure 1: Study pipeline. The human reference path (left) aggregates FaithBench's span annotations to one label per summary using the most-severe-wins rule and the benchmark's own binarisation, then splits the corpus into development and test sets. The judge path (right) sends a single frozen rubric, identical across tiers, to three judges chosen to span deployment models rather than capability. Each of the 750 items is judged three times by each tier, yielding 6,750 individual judgments. The analysis compares judge verdicts against the reference labels and reports four quantities: chance-corrected agreement, the two error rates separately, the release verdict across a threshold sweep, and the failure rate corrected for measured judge error.

**Referenced from the prose as:** "The overall design is shown in Figure 1."

**What the reader should take from it:** that the reference labels and the judge verdicts are produced independently and meet only in the analysis, and that the three judges differ by deployment tier rather than by capability ranking.

---

## Figures 2 to 6: generated, not drawn

**Produced 09.08.2026 by `analysis/figures.py`.** Regenerate all five with one
command, which is also what rebuilds them when the test split is read:

```bash
.venv/bin/python analysis/figures.py --split dev
```

Files are suffixed with the split, so `no-skill-baseline-dev.svg` and
`no-skill-baseline-test.svg` coexist and the dev versions survive as the
development record. The script imports its statistics from the frozen
`analysis/stats.py` rather than recomputing them, so a figure cannot disagree
with the table it sits beside. See `appendix/analysis.md`.

| Figure | File | Chapter | What the reader should take from it |
|---|---|---|---|
| 2 | `no-skill-baseline-<split>.svg` | 4, section 4.2 | Every judge agrees with the humans less often than a rule that flags everything without reading. The single strongest image in the paper. |
| 3 | `luck-vs-earned-<split>.svg` | 4, section 4.2 | Most of the observed agreement is what chance delivers at these flag rates. Kappa is the small earned remainder divided by the room that was available. |
| 4 | `tpr-tnr-<split>.svg` | 4, section 4.4 | The judges are conservative rather than broken: they almost never raise a false alarm and miss roughly two thirds of what they exist to catch. One accuracy figure would hide the left column. |
| 5 | `gate-divergence-<split>.svg` | 4, section 4.5 | No threshold turns these judges into a gate. Between the highest flag rate and the true rate, every judge ships what should have been blocked. |
| 6 | `scheme-sensitivity-<split>.svg` | 4, section 4.7 | Regrouping the reference labels moves kappa further than switching deployment tier does. The paper's own argument on a second axis. |

**Captions still to write in Sean's voice.** Each needs a numbered caption that
states what the figure shows and a sentence in the body that references it, since
the brief penalises unreferenced visuals. Figure 5 is the one to reference from
the research question directly.

**Not produced, and the reason is worth one line in the text.** A figure for the
Rogan-Gladen correction was planned. On dev the correction is algebraically an
identity, so a figure of it would look like a strong result and show nothing.
Decide after the test split, where the calibrate-on-dev version is informative.
