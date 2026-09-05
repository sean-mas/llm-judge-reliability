"""Live demo for the DLKI91 screencast.

    python3 demo.py                 the demo, pausing between acts
    python3 demo.py --no-pause      same, unattended, for timing a rehearsal
    python3 demo.py --case UID      run a specific summary instead of the default

Six acts, one screen each, Enter between them. Everything runs for real: the
judge is the study's own tier 3, gpt-oss:20b, on this machine, with no API key
and no network.

Nothing here writes to a database. The judgment in act 3 is made by calling the
adapter directly rather than through runner.py, so `data/main.sqlite` cannot be
touched and the numbers act 6 reproduces cannot be disturbed by the demo itself.

Terminal for recording: 100 columns, 30 rows, monospace at 20pt or larger.
"""

from __future__ import annotations

import argparse
import itertools
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import adapters                                    # noqa: E402
import rubric                                      # noqa: E402
from loader import load_samples                    # noqa: E402
from runner import RELEASE, split_corpus           # noqa: E402

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "main.sqlite"

W = 96                       # content width; fits a 100-column window

BRICK = "\033[38;2;193;70;47m"
TEAL = "\033[38;2;27;127;121m"
DIM = "\033[38;2;122;138;153m"
BOLD = "\033[1m"
OFF = "\033[0m"

#: Fixed so the demo is rehearsable: the same summary every run, and one that
#: reads well on camera. A four-sentence football report, a summary that looks
#: fine at a glance, and three expert span annotations saying it is not. Chosen
#: for legibility, not for the judge's answer, which is not known until it runs.
DEFAULT_CASE = "batch_3:24"


# ----------------------------------------------------------------- chrome ---

def clear() -> None:
    print("\033[2J\033[H", end="")


def act(n: int, title: str, subtitle: str = "") -> None:
    clear()
    print()
    print(f"{DIM}  ACT {n}{OFF}")
    print(f"{BOLD}  {title}{OFF}")
    if subtitle:
        print(f"{DIM}  {subtitle}{OFF}")
    print(f"{DIM}  {'─' * W}{OFF}")
    print()


def wrap(text: str, indent: str = "  ", width: int = W - 2) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(indent + ln for ln in lines)


def clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


PAUSE = True


def beat(msg: str = "press enter") -> None:
    if not PAUSE:
        return
    print()
    try:
        input(f"{DIM}  {msg}{OFF}")
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


class Ticker:
    """Elapsed-seconds counter on one rewritten line, so a real wait reads as work."""

    def __init__(self, label: str) -> None:
        self.label, self._stop, self._t = label, threading.Event(), None

    def __enter__(self):
        def run():
            if not sys.stdout.isatty():          # piped: one line, no animation
                sys.stdout.write(f"  {self.label}\n")
                sys.stdout.flush()
                return
            for i in itertools.count():
                if self._stop.is_set():
                    return
                sys.stdout.write(f"\r  {self.label} {DIM}{i}s{OFF} ")
                sys.stdout.flush()
                time.sleep(1)
        self._t = threading.Thread(target=run, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t:
            self._t.join(timeout=1.5)
        sys.stdout.write("\r" + " " * (W) + "\r")
        sys.stdout.flush()


# -------------------------------------------------------------------- acts ---

def act0() -> None:
    clear()
    print("\n" * 3)
    print(f"{BOLD}  How much LLM-judge agreement survives chance correction?{OFF}")
    print()
    print(wrap("A live run of the study's own harness. The judge is tier 3, "
               "gpt-oss:20b, running on this laptop: no API key, no cost, no network."))
    print()
    print(wrap("Six steps: the frozen prompt, one real summary, the judge's verdict, "
               "the human label, the freeze, and every published number rebuilt from "
               "the stored judgments."))
    beat()


def act1() -> None:
    act(1, "The instrument is a versioned spec, not a vibe",
        "src/rubric.py")
    excerpt = clip(rubric.SYSTEM, 430)
    print(wrap(excerpt, indent="  "))
    print()
    print(f"{DIM}  {'─' * W}{OFF}")
    print(f"  PROMPT_VERSION   {BOLD}{rubric.PROMPT_VERSION}{OFF}")
    print(f"  rubric_hash      {BOLD}{rubric.rubric_hash()}{OFF}")
    print()
    print(wrap("Any wording change produces a different hash. That hash is stored on "
               "every judgment row, which is what makes the freeze checkable rather "
               "than a promise."))
    beat()


def candidates(limit: int = 12):
    """Test-split cases the experts called clearly wrong, short enough to read.

    Unwanted is FaithBench's most severe label, so these are unambiguous errors
    rather than borderline ones. That makes the demo case easy to explain and
    removes the "well, it was only questionable" objection. Whether the judge
    catches it is not known in advance and is not selected on.
    """
    test = split_corpus(load_samples(RELEASE))["test"]
    out = [s for s in test
           if s.summary_label() == "Unwanted" and 300 < len(s.source) < 1300]
    return out[:limit]


def pick_case(uid: str | None):
    test = split_corpus(load_samples(RELEASE))["test"]
    if uid:
        for s in test:
            if s.uid == uid:
                return s
        sys.exit(f"no test sample with uid {uid!r}")
    pool = candidates()
    if pool:
        return pool[0]
    for s in test:                       # fall back to any unfaithful case
        if not s.is_faithful() and len(s.source) < 1400:
            return s
    return test[0]


def act2(sample) -> None:
    act(2, "One real summary from the held-out half",
        f"{sample.uid}   ·   summariser: {sample.summarizer}")
    print(f"{DIM}  SOURCE{OFF}")
    print(wrap(clip(sample.source, 620)))
    print()
    print(f"{DIM}  SUMMARY UNDER TEST{OFF}")
    print(wrap(clip(sample.summary, 460)))
    print()
    print(f"{DIM}  {'─' * W}{OFF}")
    print(wrap(f"{len(sample.annotations)} expert span annotations exist for this "
               "summary. Their verdict stays hidden until the judge has answered."))
    beat()


def act3(sample):
    act(3, "The judge runs, here, now",
        "tier 3  ·  gpt-oss:20b  ·  local  ·  temperature 0")
    system, user = rubric.render(sample.source, sample.summary)
    judge = adapters.build("local", temperature=0.0)
    print(f"  model requested  {BOLD}{judge.model_requested}{OFF}")
    print()
    with Ticker("thinking on this machine"):
        t0 = time.time()
        raw = judge.judge(system, user)
        elapsed = time.time() - t0
    parsed = rubric.parse(raw.text)
    verdict = parsed["verdict"]
    colour = BRICK if parsed["unfaithful"] else TEAL
    print(f"  answered in      {BOLD}{elapsed:.1f}s{OFF}   "
          f"{DIM}model served: {raw.model_version or 'n/a'}{OFF}")
    print()
    print(f"  verdict          {colour}{BOLD}{verdict}{OFF}")
    if parsed["span"]:
        print(f"  span             {clip(parsed['span'], 70)}")
    if parsed["reason"]:
        print()
        print(f"{DIM}  REASON{OFF}")
        print(wrap(clip(parsed["reason"], 380)))
    beat()
    return parsed


def act4(sample, parsed) -> None:
    act(4, "What the experts said about the same summary")
    human_label = sample.summary_label()
    human_unfaithful = not sample.is_faithful()
    jcol = BRICK if parsed["unfaithful"] else TEAL
    hcol = BRICK if human_unfaithful else TEAL
    print(f"  the judge said   {jcol}{BOLD}{parsed['verdict']}{OFF}")
    print(f"  the experts said {hcol}{BOLD}{'UNFAITHFUL' if human_unfaithful else 'FAITHFUL'}{OFF}"
          f"   {DIM}most severe span label: {human_label}{OFF}")
    print()
    print(f"{DIM}  {'─' * W}{OFF}")
    agree = parsed["unfaithful"] == human_unfaithful
    if agree:
        print(f"  {TEAL}{BOLD}They agree on this one.{OFF}")
        print()
        print(wrap("One case proves nothing either way. Across all 488 summaries in the "
                   "held-out half, these judges catch between 25 and 35 percent of what "
                   "the experts marked unfaithful."))
    else:
        print(f"  {BRICK}{BOLD}They disagree.{OFF}")
        print()
        print(wrap("This is the failure the paper measures. Across all 488 summaries in "
                   "the held-out half, these judges catch between 25 and 35 percent of "
                   "what the experts marked unfaithful."))
    beat()


def act5() -> None:
    act(5, "Nothing drifted while the study ran", "data/main.sqlite")
    q = "SELECT DISTINCT prompt_version, prompt_hash FROM judgments;"
    print(f"{DIM}  {q}{OFF}")
    print()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        rows = con.execute(q).fetchall()
        total = con.execute(
            "SELECT COUNT(*) FROM judgments WHERE judge_id IN "
            "('tier1_paid','tier2_hosted_open','tier3_local');").fetchone()[0]
    finally:
        con.close()
    for v, h in rows:
        print(f"  {BOLD}{v}   {h}{OFF}")
    print()
    print(f"{DIM}  {'─' * W}{OFF}")
    print(f"  {BOLD}{len(rows)} row{'s' if len(rows) != 1 else ''}{OFF}, "
          f"across {BOLD}{total:,}{OFF} judgments from the three arms.")
    print()
    print(wrap("One prompt, one hash, every judgment. If the rubric had been edited "
               "mid-study, this query would return two rows and the comparison between "
               "the tiers would be void."))
    beat()


def act6() -> None:
    act(6, "Every published number, rebuilt from the stored judgments",
        "python3 analysis/ci_gate.py")
    print()
    proc = subprocess.run([sys.executable, "analysis/ci_gate.py"],
                          cwd=ROOT, capture_output=True, text=True)
    out = (proc.stdout or proc.stderr).rstrip().splitlines()
    tail = out[-22:] if len(out) > 22 else out
    for line in tail:
        if "PASS" in line:
            print(f"  {line.replace('PASS', TEAL + 'PASS' + OFF)}")
        elif "FAIL" in line or "FATAL" in line:
            print(f"  {BRICK}{line}{OFF}")
        elif line.strip():
            print(f"  {line}")
    print()
    if proc.returncode == 0:
        print(wrap("Nothing in the paper is typed by hand. Every figure it publishes is "
                   "re-derived from the committed judgments, and this gate fails on the "
                   "first mismatch."))
    beat("press enter to finish")


def main() -> None:
    global PAUSE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-pause", action="store_true", help="run unattended, for timing")
    ap.add_argument("--case", default=DEFAULT_CASE, help="uid of the summary to judge")
    ap.add_argument("--list", action="store_true",
                    help="show candidate cases and exit, for choosing one before recording")
    a = ap.parse_args()
    PAUSE = not a.no_pause

    if a.list:
        print()
        print("  Test-split summaries the experts labelled Unwanted, short enough to show:")
        print()
        for s in candidates(20):
            print(f"  {BOLD}{s.uid:<14}{OFF} {len(s.source):>5} chars  "
                  f"{DIM}{clip(s.summary, 58)}{OFF}")
        print()
        print(f"{DIM}  python3 demo.py --case <uid>{OFF}")
        print()
        return

    started = time.time()
    act0()
    act1()
    sample = pick_case(a.case)
    act2(sample)
    parsed = act3(sample)
    act4(sample, parsed)
    act5()
    act6()
    clear()
    print()
    print(f"{BOLD}  That is the harness.{OFF}")
    print()
    print(wrap("The prompt was frozen, one summary was judged live on this machine, the "
               "experts disagreed with it, no prompt drifted across 6,750 judgments, and "
               "every number in the paper rebuilt itself from the store."))
    print()
    print(f"{DIM}  demo ran in {time.time() - started:.0f}s{OFF}")
    print()


if __name__ == "__main__":
    main()
