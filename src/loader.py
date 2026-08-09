"""Load FaithBench release batches and aggregate span annotations to summary level.

FaithBench ships one JSON file per batch under ``data_for_release/batch_{id}.json``
(ids 1 to 16, with 13 absent). Each file is ``{"samples": [...]}``.

A sample looks like::

    {
      "sample_id": 0,                      # unique WITHIN the batch only
      "source":    "...",
      "summary":   "...",
      "annotations": [ {...}, ... ],       # span level, may be empty
      "metadata":  {"summarizer": "...", "hhemv1": 0.99, ..., "raw_sample_id": 123}
    }

An annotation looks like::

    {
      "annot_id": 1,
      "annotator_id":   "a3ac21668e6249b7978617da547f2708",
      "annotator_name": "forrest",
      "label": ["Unwanted", "Unwanted.Intrinsic"],
      "note":  "...",
      "summary_span": "production", "summary_start": 78, "summary_end": 88,
      "source_span":  null,         "source_start":  null, "source_end": null
    }

Two things that will bite if forgotten:

1. ``sample_id`` restarts at 0 in every batch. Always key on ``uid``
   (``"batch_1:0"``), never on ``sample_id`` alone.
2. "Consistent" is not a label anyone writes down. It is the *absence* of
   annotations. That asymmetry is why ``annotator_count`` is unknowable for
   consistent samples: nobody records who looked and found nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Coarse label vocabulary, least to most severe.
#
# VERIFIED 05.08.2026 against the benchmark authors' own aggregation script,
# data_for_release/../scripts/binarize.py, which encodes:
#
#     Benign: 1        # least severe, best
#     Questionable: 2
#     Unwanted: 3      # most severe, worst
#
# so Benign does rank below Questionable. Their aggregation_strategy="worst" is
# the same most-severe-wins rule implemented in Sample.summary_label below.
SEVERITY: tuple[str, ...] = ("Consistent", "Benign", "Questionable", "Unwanted")

CONSISTENT = "Consistent"

# Binarisation rules. Names refer to what counts as PASS.
#
# CANONICAL is the authors' released default: binarize.py sets
# hallucinated_classes = [Questionable, Unwanted, Unwanted_Intrinsic,
# Unwanted_Extrinsic], so Benign counts as faithful. Their taxonomy says so
# explicitly: "not all hallucinations are bad. Some are benign."
#
# STRICT treats any unsupported content as a failure. It is reported as a
# sensitivity analysis, not as the headline, because deviating from a
# benchmark's own binarisation makes results incomparable to everything
# published on it.
PASS_CANONICAL: frozenset[str] = frozenset({CONSISTENT, "Benign"})
PASS_STRICT: frozenset[str] = frozenset({CONSISTENT})


@dataclass(frozen=True)
class Annotation:
    annot_id: int
    annotator_id: str
    annotator_name: str
    labels: tuple[str, ...]  # raw, e.g. ("Unwanted", "Unwanted.Intrinsic")
    #: Free-text rationale the human wrote. Often empty, but where present it is
    #: the only record of *why* a span was marked, which is what makes a
    #: judge-versus-human disagreement adjudicable instead of just countable.
    #: Never fed to the judge: it is read during error analysis only, and
    #: including it in the prompt would leak the reference label.
    note: str = ""
    #: The exact span of the summary the human objected to, with offsets into
    #: ``Sample.summary``. Directly comparable to the ``span`` field the judge
    #: returns, so the two can be checked against each other.
    summary_span: str | None = None
    summary_start: int | None = None
    summary_end: int | None = None
    source_span: str | None = None

    @property
    def coarse_labels(self) -> frozenset[str]:
        """Top-level categories only: 'Unwanted.Intrinsic' collapses to 'Unwanted'."""
        return frozenset(lab.split(".")[0] for lab in self.labels)


@dataclass(frozen=True)
class Sample:
    uid: str  # "batch_1:0", globally unique, unlike sample_id
    batch: str
    sample_id: int
    source: str
    summary: str
    summarizer: str
    annotations: tuple[Annotation, ...] = field(default_factory=tuple)

    @property
    def annotator_ids(self) -> frozenset[str]:
        """Distinct annotators who left at least one annotation on this sample.

        Empty for consistent samples. That is a limit of the release format, not
        evidence that only one person reviewed the sample.
        """
        return frozenset(a.annotator_id for a in self.annotations)

    @property
    def coarse_labels(self) -> frozenset[str]:
        return frozenset().union(*(a.coarse_labels for a in self.annotations)) if self.annotations else frozenset()

    def summary_label(self, severity: tuple[str, ...] = SEVERITY) -> str:
        """Aggregate span annotations to one summary-level label: the most severe present.

        Most-severe is the conservative choice for a quality gate. A summary with
        one unwanted hallucination and nine benign spans is not a benign summary.
        The alternative (majority vote over annotations) is recorded in
        ``analysis/`` as a sensitivity check rather than used as the primary rule.
        """
        present = self.coarse_labels
        if not present:
            # Either no annotations, or (3 cases in the 2025 release) every
            # annotation marks a span but assigns no category. Both mean "no
            # label evidence against this summary", so both read as Consistent.
            return CONSISTENT
        return max(present, key=lambda lab: severity.index(lab) if lab in severity else -1)

    def is_faithful(self, pass_set: frozenset[str] = PASS_CANONICAL) -> bool:
        """Binary reference label. Defaults to the authors' released binarisation."""
        return self.summary_label() in pass_set


def load_samples(release_dir: str | Path) -> list[Sample]:
    """Read every ``batch_*.json`` under *release_dir*, sorted by batch number."""
    release_dir = Path(release_dir)
    paths = sorted(
        release_dir.glob("batch_*.json"),
        key=lambda p: int(p.stem.split("_")[1]),
    )
    if not paths:
        raise FileNotFoundError(f"no batch_*.json under {release_dir}")

    samples: list[Sample] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for raw in payload["samples"]:
            samples.append(
                Sample(
                    uid=f"{path.stem}:{raw['sample_id']}",
                    batch=path.stem,
                    sample_id=raw["sample_id"],
                    source=raw["source"],
                    summary=raw["summary"],
                    summarizer=(raw.get("metadata") or {}).get("summarizer", "unknown"),
                    annotations=tuple(
                        Annotation(
                            annot_id=a["annot_id"],
                            annotator_id=a["annotator_id"],
                            annotator_name=a["annotator_name"],
                            labels=tuple(a["label"]),
                            note=(a.get("note") or "").strip(),
                            summary_span=a.get("summary_span"),
                            summary_start=a.get("summary_start"),
                            summary_end=a.get("summary_end"),
                            source_span=a.get("source_span"),
                        )
                        for a in raw.get("annotations") or []
                    ),
                )
            )
    return samples
