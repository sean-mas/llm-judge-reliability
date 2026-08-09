"""Result store. One row per judgment, never per item.

SQLite, because it is a single file, needs no server, survives a crash mid-run,
and can be queried directly from the analysis notebook. The file is the study's
raw data and ships with the repository.

The central rule from project-plan.md section 4: **one row per judgment**.
Aggregation happens in analysis, so the aggregation rule can change without
re-running 6,750 API calls.

Cache key
---------
``(item_uid, judge_id, model_requested, prompt_hash, repeat_idx)``

Note that the key uses ``model_requested``, the string we asked for, not
``model_version``, the string the provider resolved it to. The second is not
known until after the call, so keying on it would make every lookup a miss.
Both are stored: ``model_requested`` makes the cache work, ``model_version``
makes drift detectable. If a provider silently retargets an alias mid-run, the
two columns diverge and ``version_drift()`` reports it.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS judgments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,

    item_uid         TEXT NOT NULL,   -- "batch_1:0", unique across batches
    batch            TEXT NOT NULL,
    summarizer       TEXT NOT NULL,   -- which LLM wrote the summary being judged

    judge_id         TEXT NOT NULL,   -- "tier1_paid", stable across the study
    model_requested  TEXT NOT NULL,   -- what we asked for
    model_version    TEXT,            -- what the provider says it gave us
    prompt_hash      TEXT NOT NULL,   -- rubric.rubric_hash()
    prompt_version   TEXT NOT NULL,   -- rubric.PROMPT_VERSION, human readable
    repeat_idx       INTEGER NOT NULL,

    verdict          TEXT,            -- FAITHFUL | UNFAITHFUL | NULL on failure
    unfaithful       INTEGER,         -- 1 | 0 | NULL, convenience for analysis
    span             TEXT,
    reason           TEXT,

    parse_ok         INTEGER NOT NULL,
    error            TEXT,            -- parse error or transport error
    raw_response     TEXT,            -- kept verbatim: spot-checks need it

    latency_ms       INTEGER,
    input_tokens     INTEGER,
    output_tokens    INTEGER,

    created_at       TEXT NOT NULL,

    UNIQUE (item_uid, judge_id, model_requested, prompt_hash, repeat_idx)
);

CREATE INDEX IF NOT EXISTS idx_item  ON judgments (item_uid);
CREATE INDEX IF NOT EXISTS idx_judge ON judgments (judge_id);
CREATE INDEX IF NOT EXISTS idx_ok    ON judgments (parse_ok);
"""


@dataclass(frozen=True)
class Judgment:
    """One judge's verdict on one item on one repeat. Maps 1:1 to a row."""

    item_uid: str
    batch: str
    summarizer: str
    judge_id: str
    model_requested: str
    model_version: str | None
    prompt_hash: str
    prompt_version: str
    repeat_idx: int
    verdict: str | None
    unfaithful: bool | None
    span: str | None
    reason: str | None
    parse_ok: bool
    error: str | None
    raw_response: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None


class Store:
    """Thin wrapper over SQLite. Open it, write judgments, ask what is missing."""

    def __init__(self, path: str | Path = "data/judgments.sqlite") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # --- writing ---------------------------------------------------------

    def add(self, j: Judgment) -> bool:
        """Insert one judgment. Returns False if the key already existed.

        Uses INSERT OR IGNORE rather than REPLACE: a cached result is never
        silently overwritten, so a re-run cannot quietly change stored data.
        """
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO judgments (
                   item_uid, batch, summarizer, judge_id, model_requested,
                   model_version, prompt_hash, prompt_version, repeat_idx,
                   verdict, unfaithful, span, reason, parse_ok, error,
                   raw_response, latency_ms, input_tokens, output_tokens, created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                j.item_uid, j.batch, j.summarizer, j.judge_id, j.model_requested,
                j.model_version, j.prompt_hash, j.prompt_version, j.repeat_idx,
                j.verdict, None if j.unfaithful is None else int(j.unfaithful),
                j.span, j.reason, int(j.parse_ok), j.error, j.raw_response,
                j.latency_ms, j.input_tokens, j.output_tokens,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # --- resuming --------------------------------------------------------

    def done_keys(self, judge_id: str, model_requested: str, prompt_hash: str) -> set[tuple[str, int]]:
        """(item_uid, repeat_idx) already stored for this judge and prompt.

        A failed judgment counts as done. Re-running would re-bill for a call
        that already told us something, namely that this tier cannot answer.
        Use ``clear_failures`` to deliberately retry them.
        """
        rows = self.conn.execute(
            """SELECT item_uid, repeat_idx FROM judgments
               WHERE judge_id = ? AND model_requested = ? AND prompt_hash = ?""",
            (judge_id, model_requested, prompt_hash),
        )
        return {(r["item_uid"], r["repeat_idx"]) for r in rows}

    def clear_failures(self, judge_id: str | None = None) -> int:
        """Delete unparseable rows so they can be retried. Returns rows removed."""
        sql = "DELETE FROM judgments WHERE parse_ok = 0"
        args: tuple = ()
        if judge_id:
            sql += " AND judge_id = ?"
            args = (judge_id,)
        cur = self.conn.execute(sql, args)
        self.conn.commit()
        return cur.rowcount

    # --- inspecting ------------------------------------------------------

    def summary(self) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            """SELECT judge_id,
                      COUNT(*)                                   AS n,
                      SUM(parse_ok)                              AS parsed,
                      SUM(CASE WHEN unfaithful = 1 THEN 1 END)   AS flagged,
                      COUNT(DISTINCT model_version)              AS versions,
                      ROUND(AVG(latency_ms))                     AS avg_ms,
                      SUM(input_tokens)                          AS tok_in,
                      SUM(output_tokens)                         AS tok_out
               FROM judgments GROUP BY judge_id ORDER BY judge_id"""
        ))

    def version_drift(self) -> list[sqlite3.Row]:
        """Judges whose resolved model_version changed during the study.

        Any row here invalidates the reproducibility claim for that judge and
        must be reported rather than quietly re-run.
        """
        return list(self.conn.execute(
            """SELECT judge_id, model_requested, model_version, COUNT(*) AS n,
                      MIN(created_at) AS first_seen, MAX(created_at) AS last_seen
               FROM judgments
               WHERE judge_id IN (
                   SELECT judge_id FROM judgments
                   WHERE model_version IS NOT NULL
                   GROUP BY judge_id HAVING COUNT(DISTINCT model_version) > 1
               )
               GROUP BY judge_id, model_requested, model_version
               ORDER BY judge_id, first_seen"""
        ))

    def export_jsonl(self, path: str | Path) -> int:
        """Dump every row to JSONL for the appendix and for anyone without SQLite."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.conn.execute("SELECT * FROM judgments ORDER BY id")
        n = 0
        with path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(dict(r), ensure_ascii=False) + "\n")
                n += 1
        return n

    def close(self) -> None:
        self.conn.close()
