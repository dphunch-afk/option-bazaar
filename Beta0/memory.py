from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class Experience:
    id: int
    subject: str
    observation: str
    source: str
    created_at: str


@dataclass(frozen=True)
class Belief:
    id: int
    subject: str
    statement: str
    confidence: float
    status: str
    based_on_experience_id: int
    created_at: str


class MemoryStore:
    """Persistent Beta-0 memory.

    Experiences are append-only. Beliefs are versioned interpretations that can
    change over time without deleting the original experience history.
    """

    def __init__(self, db_path: str | Path = "beta0_memory.db") -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                observation TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'human',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS beliefs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                statement TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                status TEXT NOT NULL CHECK(status IN ('believed','uncertain','contradicted','known')),
                based_on_experience_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (based_on_experience_id) REFERENCES experiences(id)
            );
            """
        )
        self.conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_experience(self, subject: str, observation: str, source: str = "human") -> int:
        cur = self.conn.execute(
            "INSERT INTO experiences(subject, observation, source, created_at) VALUES (?, ?, ?, ?)",
            (subject.strip(), observation.strip(), source.strip(), self._now()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_belief(
        self,
        subject: str,
        statement: str,
        confidence: float,
        based_on_experience_id: int,
        status: str = "believed",
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO beliefs(subject, statement, confidence, status,
                                based_on_experience_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                subject.strip(),
                statement.strip(),
                float(confidence),
                status,
                based_on_experience_id,
                self._now(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def experiences_for(self, subject: str) -> list[Experience]:
        rows = self.conn.execute(
            "SELECT * FROM experiences WHERE subject = ? ORDER BY id ASC",
            (subject.strip(),),
        ).fetchall()
        return [Experience(**dict(row)) for row in rows]

    def latest_belief(self, subject: str) -> Optional[Belief]:
        row = self.conn.execute(
            "SELECT * FROM beliefs WHERE subject = ? ORDER BY id DESC LIMIT 1",
            (subject.strip(),),
        ).fetchone()
        return Belief(**dict(row)) if row else None

    def belief_history(self, subject: str) -> list[Belief]:
        rows = self.conn.execute(
            "SELECT * FROM beliefs WHERE subject = ? ORDER BY id ASC",
            (subject.strip(),),
        ).fetchall()
        return [Belief(**dict(row)) for row in rows]

    def subjects(self) -> Iterable[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT subject FROM experiences ORDER BY subject"
        ).fetchall()
        return [row[0] for row in rows]

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
