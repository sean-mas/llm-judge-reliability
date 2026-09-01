"""Fetch the FaithBench corpus. Not redistributed here, and deliberately so.

    python data/download_faithbench.py

FaithBench is released by its authors under **CC BY-NC-SA 4.0**. That licence
permits redistribution with attribution under the same terms, but vendoring
somebody else's corpus into a third-party repository invites the share-alike
question to be asked about everything around it, and it would add fourteen
megabytes to a clone for no benefit. So this repository references the corpus by
item ID and fetches it from the original source instead.

What that means in practice: `data/main.sqlite` stores `item_uid` values like
`batch_1:0` and never stores the source text or the summary. The corpus is the
join key, not the payload.

The two columns that do carry fragments of it are `span`, the passage of the
summary a judge objected to, and `raw_response`, the judge's verbatim output,
which sometimes quotes the summary back. Both are short quotations rather than a
redistribution, and `raw_response` is what makes any judgment in this study
spot-checkable by hand, which is worth more than the tidiness of removing it.

Citation: Bao et al. (2025), FaithBench: A Diverse Hallucination Benchmark for
Summarization by Modern LLMs, NAACL 2025 (Short).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/vectara/FaithBench.git"
DEST = Path(__file__).resolve().parent / "raw" / "FaithBench"
NEEDED = "data_for_release"


def main() -> int:
    if (DEST / NEEDED).is_dir():
        n = len(list((DEST / NEEDED).glob("batch_*.json")))
        print(f"Already present: {DEST} ({n} batch files). Nothing to do.")
        return 0

    if shutil.which("git") is None:
        print("FATAL: git is not on PATH.", file=sys.stderr)
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Cloning {REPO}\n     -> {DEST}")
    r = subprocess.run(["git", "clone", "--depth", "1", REPO, str(DEST)])
    if r.returncode != 0:
        print("FATAL: clone failed.", file=sys.stderr)
        return r.returncode

    if not (DEST / NEEDED).is_dir():
        print(f"FATAL: cloned, but {NEEDED}/ is missing. Upstream layout changed?", file=sys.stderr)
        return 1

    n = len(list((DEST / NEEDED).glob("batch_*.json")))
    print(f"\nDone. {n} batch files in {DEST / NEEDED}")
    print("FaithBench is CC BY-NC-SA 4.0. Attribute Bao et al. (2025) if you use it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
