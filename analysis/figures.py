"""Figure generation. Renders, computes nothing.

    .venv/bin/python analysis/figures.py --split dev

Written AFTER the analysis freeze of 09.08.2026 and deliberately not part of it.
Every number drawn here comes from `stats.stats()` and `stats.SCHEMES`, imported
from the frozen module rather than reimplemented, so a figure cannot disagree
with a table. The only thing this file decides is where to put ink.

Output is SVG. No third-party dependency is used anywhere in this study, which is
a reproducibility claim worth keeping: `pip install` is empty and the analysis
runs on a stock interpreter. SVG is also the right format for a PDF paper, and it
rescales to any screencast resolution without resampling.

The test split is guarded exactly as in `stats.py`. A figure is as much a look at
the data as a table is.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stats import ARMS, DB, SCHEMES, stats  # noqa: E402

from loader import load_samples  # noqa: E402
from runner import RELEASE, split_corpus  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures"

LABEL = {
    "tier1_paid": "Tier 1  paid  claude-opus-5",
    "tier2_hosted_open": "Tier 2  hosted  gpt-oss:120b",
    "tier3_local": "Tier 3  local  gpt-oss:20b",
}
SHORT = {"tier1_paid": "Tier 1", "tier2_hosted_open": "Tier 2", "tier3_local": "Tier 3"}

#: Chosen to stay distinguishable in greyscale, because the paper may be printed
#: in black and white and a figure that collapses to three identical bars is a
#: figure that failed.
INK = "#1a1a1a"
MUTED = "#6b6b6b"
RULE = "#d4d4d4"
FILL = {"tier1_paid": "#2f5d8c", "tier2_hosted_open": "#7fa8cc", "tier3_local": "#bcd3e6"}
WARN = "#a33"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x: float, y: float, s: str, size: float = 13, fill: str = INK,
         anchor: str = "start", weight: str = "normal") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}" '
            f'font-family="Helvetica Neue, Helvetica, Arial, sans-serif">{esc(s)}</text>')


def svg(width: float, height: float, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="Helvetica Neue, Helvetica, Arial, sans-serif">'
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>{body}</svg>')


def collect(split: str) -> tuple[dict, dict, float]:
    """Per-judge stats under every scheme, plus the prevalence, for one split.

    Returns (by_scheme, primary, prevalence) where by_scheme[scheme][judge] and
    primary[judge] are the dicts `stats.stats()` produces.
    """
    ref = {s.uid: s for s in split_corpus(load_samples(RELEASE))[split]}
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [r for r in con.execute("SELECT * FROM judgments") if r["item_uid"] in ref]

    by_scheme: dict[str, dict[str, dict]] = {}
    for scheme, (pos, neg) in SCHEMES.items():
        by_scheme[scheme] = {}
        for j in ARMS:
            pairs = []
            for r in rows:
                if r["judge_id"] != j or not r["parse_ok"]:
                    continue
                lab = ref[r["item_uid"]].summary_label()
                if lab in pos:
                    pairs.append((True, bool(r["unfaithful"])))
                elif lab in neg:
                    pairs.append((False, bool(r["unfaithful"])))
            if pairs:
                by_scheme[scheme][j] = stats(pairs)

    pos, neg = SCHEMES["U+Q"]
    labs = [s.summary_label() for s in ref.values()]
    kept = [x for x in labs if x in pos or x in neg]
    prev = sum(1 for x in kept if x in pos) / len(kept)
    return by_scheme, by_scheme["U+Q"], prev


def fig_no_skill(primary: dict, prev: float, split: str) -> str:
    """The chapter's load-bearing figure. One comparison, no statistics vocabulary.

    A judge that stamps UNFAITHFUL on everything without reading scores the
    prevalence as raw agreement and kappa exactly zero. Every arm sits below it.
    """
    W, H = 860, 400
    x0, top, bw, rowh = 300, 96, 460, 62
    parts = [
        text(40, 44, "Raw agreement against the no-skill baseline", 20, INK, weight="600"),
        text(40, 68, f"{split} split, scheme U+Q. A judge that flags every summary without "
                     f"reading scores {prev * 100:.1f}%.", 13, MUTED),
    ]

    def px(v: float) -> float:
        return x0 + bw * v

    for i, j in enumerate(ARMS):
        y = top + i * rowh
        s = primary[j]
        parts.append(text(x0 - 14, y + 22, LABEL[j], 13, INK, anchor="end"))
        parts.append(f'<rect x="{x0}" y="{y}" width="{bw}" height="30" fill="#f2f2f2"/>')
        parts.append(f'<rect x="{x0}" y="{y}" width="{bw * s["raw"]:.1f}" height="30" '
                     f'fill="{FILL[j]}"/>')
        parts.append(text(px(s["raw"]) + 10, y + 21, f'{s["raw"] * 100:.1f}%', 14, INK,
                          weight="600"))

    ybot = top + 3 * rowh - 14
    parts.append(f'<line x1="{px(prev):.1f}" y1="{top - 22}" x2="{px(prev):.1f}" '
                 f'y2="{ybot + 10}" stroke="{WARN}" stroke-width="2" stroke-dasharray="6 4"/>')
    parts.append(text(px(prev), top - 30, f"no skill  {prev * 100:.1f}%", 13, WARN,
                      anchor="middle", weight="600"))

    parts.append(f'<line x1="{x0}" y1="{ybot + 12}" x2="{x0 + bw}" y2="{ybot + 12}" '
                 f'stroke="{RULE}"/>')
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        parts.append(text(px(t), ybot + 32, f"{t * 100:.0f}%", 11, MUTED, anchor="middle"))

    parts.append(text(40, H - 26,
                      "All three judges agree with the human labels less often than a rule that "
                      "reads nothing. Cohen's kappa for that rule is exactly 0.", 13, INK))
    return svg(W, H, "".join(parts))


def fig_luck(primary: dict, split: str) -> str:
    """Kappa decomposed: what chance alone would deliver, and what was earned.

    pe = pt*pp + (1-pt)*(1-pp) is agreement two independent raters reach by
    coincidence given these two marginals. Kappa is the share of the room above
    it that the judge actually took.

    pe is recovered from the frozen statistics as pe = (po - k) / (1 - k) rather
    than recomputed from the corpus prevalence. The two are not the same number:
    each judge's pairs exclude that judge's own parse failures, so its pt differs
    slightly from the corpus rate. Inverting kappa's own definition guarantees the
    figure cannot disagree with the table.
    """
    W, H = 860, 430
    x0, top, bw, rowh = 300, 104, 460, 66
    parts = [
        text(40, 44, "Where the agreement comes from", 20, INK, weight="600"),
        text(40, 68, f"{split} split, scheme U+Q. Kappa is the earned part divided by the room "
                     f"that was available.", 13, MUTED),
    ]
    for i, j in enumerate(ARMS):
        y = top + i * rowh
        s = primary[j]
        pp = s["flag"]
        pe = (s["raw"] - s["kappa"]) / (1 - s["kappa"])
        earned = s["raw"] - pe
        parts.append(text(x0 - 14, y + 15, SHORT[j], 13, INK, anchor="end", weight="600"))
        parts.append(text(x0 - 14, y + 32, f'flags {pp * 100:.1f}%', 11, MUTED, anchor="end"))
        parts.append(f'<rect x="{x0}" y="{y}" width="{bw}" height="34" fill="#f2f2f2"/>')
        parts.append(f'<rect x="{x0}" y="{y}" width="{bw * pe:.1f}" height="34" fill="{RULE}"/>')
        parts.append(f'<rect x="{x0 + bw * pe:.1f}" y="{y}" width="{bw * earned:.1f}" '
                     f'height="34" fill="{FILL[j]}"/>')
        parts.append(text(x0 + bw * pe / 2, y + 22, f"{pe * 100:.0f}%", 12, INK,
                          anchor="middle"))
        parts.append(text(x0 + bw * s["raw"] + 10, y + 22,
                          f'+{earned * 100:.1f} pp earned    kappa {s["kappa"]:.3f}', 12, INK,
                          weight="600"))

    ybot = top + 3 * rowh - 20
    parts.append(f'<rect x="{x0}" y="{ybot + 28}" width="16" height="12" fill="{RULE}"/>')
    parts.append(text(x0 + 24, ybot + 38, "agreement chance alone would produce", 12, MUTED))
    parts.append(f'<rect x="{x0 + 292}" y="{ybot + 28}" width="16" height="12" '
                 f'fill="{FILL["tier1_paid"]}"/>')
    parts.append(text(x0 + 316, ybot + 38, "earned above chance", 12, MUTED))
    parts.append(text(40, H - 26,
                      "The grey block is what two raters hit by coincidence at these flag rates. "
                      "Only the coloured sliver is evidence of judgment.", 13, INK))
    return svg(W, H, "".join(parts))


def fig_tpr_tnr(primary: dict, split: str) -> str:
    """Why a single accuracy number must never be reported for these judges."""
    W, H = 860, 400
    x0, top, bw, rowh = 250, 108, 250, 66
    gap = 60
    parts = [
        text(40, 44, "Conservative, not degenerate", 20, INK, weight="600"),
        text(40, 68, f"{split} split, scheme U+Q. The two rates a single accuracy figure would "
                     f"average away.", 13, MUTED),
        text(x0 + bw / 2, top - 14, "caught, of the unfaithful  (TPR)", 12, MUTED,
             anchor="middle"),
        text(x0 + bw + gap + bw / 2, top - 14, "passed, of the faithful  (TNR)", 12, MUTED,
             anchor="middle"),
    ]
    for i, j in enumerate(ARMS):
        y = top + i * rowh
        s = primary[j]
        parts.append(text(x0 - 14, y + 22, SHORT[j], 13, INK, anchor="end", weight="600"))
        parts.append(f'<rect x="{x0}" y="{y}" width="{bw}" height="32" fill="#f2f2f2"/>')
        parts.append(f'<rect x="{x0}" y="{y}" width="{bw * s["tpr"]:.1f}" height="32" '
                     f'fill="{WARN}"/>')
        parts.append(text(x0 + 8, y + 22, f'{s["tpr"] * 100:.1f}%', 13, "#ffffff", weight="600"))
        xr = x0 + bw + gap
        parts.append(f'<rect x="{xr}" y="{y}" width="{bw}" height="32" fill="#f2f2f2"/>')
        parts.append(f'<rect x="{xr}" y="{y}" width="{bw * s["tnr"]:.1f}" height="32" '
                     f'fill="{FILL[j]}"/>')
        parts.append(text(xr + 8, y + 22, f'{s["tnr"] * 100:.1f}%', 13, INK, weight="600"))

    parts.append(text(40, H - 44,
                      "The judges almost never raise a false alarm and miss roughly two thirds of "
                      "what they exist to catch.", 13, INK))
    parts.append(text(40, H - 24,
                      "Averaged into one accuracy figure, the left column disappears.", 13, INK))
    return svg(W, H, "".join(parts))


def fig_gate(primary: dict, prev: float, split: str) -> str:
    """The release-gate divergence band, which is the research question in one line.

    A gate blocks when the flagged share exceeds a threshold T. Truth blocks
    whenever T is below the real unfaithful rate. Between the highest flag rate
    any judge produces and that real rate, every judge ships a release that should
    have been blocked, and no choice of T escapes it.
    """
    W, H = 860, 420
    x0, bw, axis = 90, 700, 226
    worst = max(primary[j]["flag"] for j in ARMS)
    parts = [
        text(40, 44, "No threshold makes these judges into a gate", 20, INK, weight="600"),
        text(40, 68, f"{split} split, scheme U+Q. The gate blocks the release when the flagged "
                     f"share exceeds the threshold T.", 13, MUTED),
    ]

    def px(v: float) -> float:
        return x0 + bw * v

    if worst < prev:
        # Stops short of the rule so the tick labels below it stay legible.
        parts.append(f'<rect x="{px(worst):.1f}" y="{axis - 100}" '
                     f'width="{bw * (prev - worst):.1f}" height="72" fill="#f2dede"/>')
        parts.append(text((px(worst) + px(prev)) / 2, axis - 74,
                          "every judge ships", 13, WARN, anchor="middle", weight="600"))
        parts.append(text((px(worst) + px(prev)) / 2, axis - 56,
                          "the truth blocks", 13, WARN, anchor="middle", weight="600"))

    # Ticks sit ABOVE the rule so the space below belongs entirely to the judge
    # markers. Otherwise a tick label and a judge stem land on the same pixels,
    # which on this data they do at 20%.
    parts.append(f'<line x1="{x0}" y1="{axis}" x2="{x0 + bw}" y2="{axis}" '
                 f'stroke="{INK}" stroke-width="1.5"/>')
    for t in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        parts.append(f'<line x1="{px(t):.1f}" y1="{axis - 6}" x2="{px(t):.1f}" y2="{axis}" '
                     f'stroke="{INK}"/>')
        parts.append(text(px(t), axis - 12, f"{t * 100:.0f}%", 11, MUTED, anchor="middle"))
    parts.append(text(x0 + bw / 2, axis + 132, "gate threshold T", 12, MUTED, anchor="middle"))

    parts.append(f'<line x1="{px(prev):.1f}" y1="{axis - 118}" x2="{px(prev):.1f}" '
                 f'y2="{axis}" stroke="{WARN}" stroke-width="2.5"/>')
    parts.append(text(px(prev), axis - 128, f"true unfaithful rate  {prev * 100:.1f}%", 13, WARN,
                      anchor="middle", weight="600"))

    # Stems first, then labels, each on its own white backing. Three vertical
    # stems and three horizontal labels in one strip collide otherwise.
    lanes = sorted(ARMS, key=lambda a: primary[a]["flag"])
    for i, j in enumerate(lanes):
        y = axis + 30 + i * 30
        parts.append(f'<line x1="{px(primary[j]["flag"]):.1f}" y1="{axis + 2}" '
                     f'x2="{px(primary[j]["flag"]):.1f}" y2="{y - 4}" '
                     f'stroke="{FILL[j]}" stroke-width="2.5"/>')
    for i, j in enumerate(lanes):
        f = primary[j]["flag"]
        y = axis + 30 + i * 30
        s = f'{SHORT[j]} flags {f * 100:.1f}%'
        parts.append(f'<rect x="{px(f) + 8:.1f}" y="{y - 14}" width="{6.6 * len(s):.0f}" '
                     f'height="19" fill="#ffffff"/>')
        parts.append(f'<circle cx="{px(f):.1f}" cy="{y - 4}" r="4.5" fill="{FILL[j]}"/>')
        parts.append(text(px(f) + 12, y, s, 12, INK))

    parts.append(text(40, H - 26,
                      f"For any T between {worst * 100:.1f}% and {prev * 100:.1f}%, a band "
                      f"{(prev - worst) * 100:.1f} points wide, all three judges pass a release "
                      f"that should have been blocked.", 13, INK))
    return svg(W, H, "".join(parts))


def fig_schemes(by_scheme: dict, split: str) -> str:
    """The paper's own argument on a second axis: the analyst moves the result more
    than the procurement decision does."""
    W, H = 860, 440
    left, right, top, plot_h = 300, 700, 110, 220
    order = ["U", "U+Q", "U+Q+B"]
    ks = [by_scheme[s][j]["kappa"] for s in order for j in ARMS if j in by_scheme[s]]
    kmax = max(0.25, max(ks) * 1.15)

    def yy(k: float) -> float:
        return top + plot_h - plot_h * (k / kmax)

    parts = [
        text(40, 44, "The choice of statistic outweighs the choice of model", 20, INK,
             weight="600"),
        text(40, 68, f"{split} split. Cohen's kappa for the same judgments, regrouped under "
                     f"FaithBench's three binarisation schemes.", 13, MUTED),
    ]
    for k in (0.0, 0.05, 0.10, 0.15, 0.20, 0.25):
        if k > kmax:
            continue
        parts.append(f'<line x1="{left - 40}" y1="{yy(k):.1f}" x2="{right + 40}" '
                     f'y2="{yy(k):.1f}" stroke="{RULE}" stroke-dasharray="2 4"/>')
        parts.append(text(left - 50, yy(k) + 4, f"{k:.2f}", 11, MUTED, anchor="end"))

    xs = {s: left + i * ((right - left) / 2) for i, s in enumerate(order)}
    for s in order:
        cap = "primary" if s == "U+Q" else ("FaithJudge's scheme" if s == "U+Q+B" else "")
        parts.append(text(xs[s], top + plot_h + 26, s, 14, INK, anchor="middle", weight="600"))
        if cap:
            parts.append(text(xs[s], top + plot_h + 44, cap, 11, MUTED, anchor="middle"))

    ends: list[tuple[float, str]] = []
    for j in ARMS:
        pts = [(xs[s], yy(by_scheme[s][j]["kappa"])) for s in order if j in by_scheme[s]]
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        parts.append(f'<path d="{d}" fill="none" stroke="{FILL[j]}" stroke-width="3"/>')
        for x, y in pts:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{FILL[j]}"/>')
        ends.append((pts[-1][1], j))

    # Two tiers can land on the same kappa, and on this data two of them do. Push
    # the end labels apart so the figure does not print one on top of another.
    ends.sort()
    placed: list[float] = []
    for y, j in ends:
        while placed and y - placed[-1] < 15:
            y = placed[-1] + 15
        placed.append(y)
        parts.append(text(right + 16, y + 4, SHORT[j], 12, INK, weight="600"))

    swing = max(abs(by_scheme["U"][j]["kappa"] - by_scheme["U+Q+B"][j]["kappa"]) for j in ARMS)
    spread = max(max(by_scheme[s][j]["kappa"] for j in ARMS)
                 - min(by_scheme[s][j]["kappa"] for j in ARMS) for s in order)
    parts.append(text(40, H - 46,
                      f"Regrouping the reference labels moves kappa by up to {swing:.3f}. The "
                      f"widest gap between the three deployment tiers,", 13, INK))
    parts.append(text(40, H - 26,
                      f"within any one scheme, is {spread:.3f}. Same judgments throughout: not one "
                      f"extra API call was made.", 13, INK))
    return svg(W, H, "".join(parts))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", default="dev", choices=("dev", "test"))
    ap.add_argument("--i-am-ready-to-spend-the-test-split", action="store_true")
    args = ap.parse_args()

    if args.split == "test" and not args.i_am_ready_to_spend_the_test_split:
        raise SystemExit(
            "Refusing. A figure is a look at the data exactly as a table is, and\n"
            "the test split may be looked at once. Re-run with\n"
            "--i-am-ready-to-spend-the-test-split together with stats.py."
        )

    by_scheme, primary, prev = collect(args.split)
    OUT.mkdir(exist_ok=True)
    figs = {
        "no-skill-baseline": fig_no_skill(primary, prev, args.split),
        "luck-vs-earned": fig_luck(primary, args.split),
        "tpr-tnr": fig_tpr_tnr(primary, args.split),
        "gate-divergence": fig_gate(primary, prev, args.split),
        "scheme-sensitivity": fig_schemes(by_scheme, args.split),
    }
    for name, body in figs.items():
        p = OUT / f"{name}-{args.split}.svg"
        p.write_text(body, encoding="utf-8")
        print(f"wrote {p.relative_to(Path(__file__).resolve().parents[1])}")
    print(f"\nprevalence on {args.split}: {prev * 100:.1f}% unfaithful under U+Q")


if __name__ == "__main__":
    main()
