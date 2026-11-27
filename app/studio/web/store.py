"""Accès SQLite pour l'interface web et les traitements locaux."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def uuid4_hex() -> str:
    return uuid.uuid4().hex


JOB_COLUMNS = {
    "status", "progress", "message", "source_path", "source_url", "streamer",
    "note", "duration", "output_path", "thumbnail_path", "error", "validated_at",
    "source_hash", "source_title", "metadata_json",
}


class Store:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL DEFAULT 'short',
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    source_kind TEXT NOT NULL,
                    source_path TEXT,
                    source_url TEXT,
                    source_hash TEXT,
                    source_title TEXT,
                    streamer TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    duration REAL,
                    output_path TEXT,
                    thumbnail_path TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT,
                    rights_confirmed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    validated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS clips (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL UNIQUE,
                    source_hash TEXT,
                    source_path TEXT,
                    source_url TEXT,
                    source_title TEXT,
                    streamer TEXT NOT NULL DEFAULT '',
                    date_key TEXT NOT NULL,
                    duration REAL,
                    output_path TEXT,
                    thumbnail_path TEXT,
                    status TEXT NOT NULL DEFAULT 'ready',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(id)
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_clips_date ON clips(date_key);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_source_hash ON jobs(source_hash) WHERE source_hash IS NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_clips_source_hash ON clips(source_hash) WHERE source_hash IS NOT NULL;

                CREATE TABLE IF NOT EXISTS highlight_scans (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'queued',
                    progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    source_kind TEXT NOT NULL,
                    source_path TEXT,
                    source_url TEXT,
                    source_title TEXT,
                    streamer TEXT NOT NULL DEFAULT '',
                    source_duration REAL,
                    window_start REAL,
                    window_end REAL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT,
                    rights_confirmed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS highlight_candidates (
                    id TEXT PRIMARY KEY,
                    scan_id TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    media_start REAL NOT NULL,
                    media_end REAL NOT NULL,
                    score REAL NOT NULL,
                    audio_score REAL NOT NULL DEFAULT 0,
                    speech_score REAL NOT NULL DEFAULT 0,
                    reaction_score REAL NOT NULL DEFAULT 0,
                    opening_score REAL NOT NULL DEFAULT 0,
                    payoff_score REAL NOT NULL DEFAULT 0,
                    reasons_json TEXT NOT NULL DEFAULT '[]',
                    transcript TEXT NOT NULL DEFAULT '',
                    created_job_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(scan_id) REFERENCES highlight_scans(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_highlight_scans_created ON highlight_scans(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_highlight_candidates_scan ON highlight_candidates(scan_id, rank);
                """
            )
            candidate_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(highlight_candidates)")
            }
            if "opening_score" not in candidate_columns:
                connection.execute(
                    "ALTER TABLE highlight_candidates ADD COLUMN opening_score REAL NOT NULL DEFAULT 0"
                )
            if "payoff_score" not in candidate_columns:
                connection.execute(
                    "ALTER TABLE highlight_candidates ADD COLUMN payoff_score REAL NOT NULL DEFAULT 0"
                )

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def create_job(self, job: dict[str, Any]) -> None:
        now = self.now()
        payload = {
            "id": job["id"],
            "kind": job.get("kind", "short"),
            "status": job.get("status", "queued"),
            "progress": int(job.get("progress", 0)),
            "message": job.get("message", "En attente"),
            "source_kind": job["source_kind"],
            "source_path": job.get("source_path"),
            "source_url": job.get("source_url"),
            "source_hash": job.get("source_hash"),
            "source_title": job.get("source_title"),
            "streamer": job.get("streamer", ""),
            "note": job.get("note", ""),
            "metadata_json": json.dumps(job.get("metadata", {}), ensure_ascii=False),
            "rights_confirmed": int(bool(job.get("rights_confirmed"))),
            "created_at": now,
            "updated_at": now,
        }
        columns = ", ".join(payload.keys())
        placeholders = ", ".join("?" for _ in payload)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO jobs ({columns}) VALUES ({placeholders})",
                tuple(payload.values()),
            )

    def update_job(self, job_id: str, **fields: Any) -> None:
        unknown = set(fields) - JOB_COLUMNS
        if unknown:
            raise ValueError("Champs de job inconnus : " + ", ".join(sorted(unknown)))
        if not fields:
            return
        values = dict(fields)
        if "metadata_json" in values and not isinstance(values["metadata_json"], str):
            values["metadata_json"] = json.dumps(values["metadata_json"], ensure_ascii=False)
        values["updated_at"] = self.now()
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE jobs SET {assignments} WHERE id = ?",
                (*values.values(), job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job_dict(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._job_dict(row) for row in rows]

    def get_dashboard(self) -> dict[str, Any]:
        with self._connect() as connection:
            counts = connection.execute(
                """SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status IN ('queued', 'running', 'cancelling') THEN 1 ELSE 0 END) AS processing,
                    SUM(CASE WHEN status = 'ready' THEN 1 ELSE 0 END) AS review,
                    SUM(CASE WHEN status = 'validated' THEN 1 ELSE 0 END) AS validated
                   FROM jobs"""
            ).fetchone()
            clips = connection.execute("SELECT COUNT(*) AS total FROM clips").fetchone()
        return {
            "total_jobs": int(counts["total"] or 0),
            "processing": int(counts["processing"] or 0),
            "to_review": int(counts["review"] or 0),
            "validated": int(counts["validated"] or 0),
            "clip_bank": int(clips["total"] or 0),
            "recent_jobs": self.list_jobs(8),
        }

    def find_duplicate_hash(self, source_hash: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE source_hash = ? LIMIT 1", (source_hash,)
            ).fetchone()
        return self._job_dict(row) if row else None

    def validate_job_and_add_to_clip_bank(self, job_id: str) -> dict[str, Any] | None:
        """Valide un rendu et l'ajoute au clip bank dans une transaction SQLite.

        Seuls les clips explicitement validés par l'utilisateur entrent dans la
        bibliothèque qui alimentera les Best Of. Un double clic ne crée pas de
        doublon et un crash ne peut pas séparer la validation de l'insertion.
        """
        now = self.now()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None or row["status"] != "ready":
                return None

            connection.execute(
                """UPDATE jobs
                   SET status = 'validated', message = 'Short validé', validated_at = ?, updated_at = ?
                   WHERE id = ? AND status = 'ready'""",
                (now, now, job_id),
            )
            validated_row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if validated_row is None:
                return None
            job = self._job_dict(validated_row)
            created_at = str(job.get("created_at") or now)
            date_key = created_at[:10]
            connection.execute(
                """INSERT OR IGNORE INTO clips (
                    id, job_id, source_hash, source_path, source_url, source_title,
                    streamer, date_key, duration, output_path, thumbnail_path, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'validated', ?)""",
                (
                    job["id"], job["id"], job.get("source_hash"), job.get("source_path"),
                    job.get("source_url"), job.get("source_title"), job.get("streamer", ""),
                    date_key, job.get("duration"), job.get("output_path"),
                    job.get("thumbnail_path"), created_at,
                ),
            )
        return job

    def list_clips(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM clips ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def create_highlight_scan(self, scan: dict[str, Any]) -> None:
        now = self.now()
        payload = {
            "id": scan["id"],
            "status": scan.get("status", "queued"),
            "progress": int(scan.get("progress", 0)),
            "message": scan.get("message", "En attente"),
            "source_kind": scan["source_kind"],
            "source_path": scan.get("source_path"),
            "source_url": scan.get("source_url"),
            "source_title": scan.get("source_title"),
            "streamer": scan.get("streamer", ""),
            "source_duration": scan.get("source_duration"),
            "window_start": scan.get("window_start"),
            "window_end": scan.get("window_end"),
            "metadata_json": json.dumps(scan.get("metadata", {}), ensure_ascii=False),
            "rights_confirmed": int(bool(scan.get("rights_confirmed"))),
            "created_at": now,
            "updated_at": now,
        }
        columns = ", ".join(payload.keys())
        placeholders = ", ".join("?" for _ in payload)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO highlight_scans ({columns}) VALUES ({placeholders})",
                tuple(payload.values()),
            )

    def create_highlight_scans(self, scans: list[dict[str, Any]]) -> None:
        """Insert a batch of queued scans atomically."""
        if not scans:
            return
        now = self.now()
        payloads = []
        for scan in scans:
            payloads.append({
                "id": scan["id"],
                "status": scan.get("status", "queued"),
                "progress": int(scan.get("progress", 0)),
                "message": scan.get("message", "En attente"),
                "source_kind": scan["source_kind"],
                "source_path": scan.get("source_path"),
                "source_url": scan.get("source_url"),
                "source_title": scan.get("source_title"),
                "streamer": scan.get("streamer", ""),
                "source_duration": scan.get("source_duration"),
                "window_start": scan.get("window_start"),
                "window_end": scan.get("window_end"),
                "metadata_json": json.dumps(scan.get("metadata", {}), ensure_ascii=False),
                "rights_confirmed": int(bool(scan.get("rights_confirmed"))),
                "created_at": now,
                "updated_at": now,
            })
        columns = ", ".join(payloads[0].keys())
        placeholders = ", ".join("?" for _ in payloads[0])
        with self._connect() as connection:
            connection.executemany(
                f"INSERT INTO highlight_scans ({columns}) VALUES ({placeholders})",
                [tuple(payload.values()) for payload in payloads],
            )

    def update_highlight_scan(self, scan_id: str, **fields: Any) -> None:
        allowed = {
            "status", "progress", "message", "source_path", "source_title", "streamer",
            "source_duration", "window_start", "window_end", "metadata_json", "error",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError("Champs de scan inconnus : " + ", ".join(sorted(unknown)))
        if not fields:
            return
        values = dict(fields)
        if "metadata_json" in values and not isinstance(values["metadata_json"], str):
            values["metadata_json"] = json.dumps(values["metadata_json"], ensure_ascii=False)
        values["updated_at"] = self.now()
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE highlight_scans SET {assignments} WHERE id = ?",
                (*values.values(), scan_id),
            )

    def get_highlight_scan(self, scan_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM highlight_scans WHERE id = ?", (scan_id,)).fetchone()
        return self._highlight_scan_dict(row) if row else None

    def list_highlight_scans(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM highlight_scans ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._highlight_scan_dict(row) for row in rows]

    def save_highlight_candidates(self, scan_id: str, candidates: list[dict[str, Any]]) -> None:
        now = self.now()
        with self._connect() as connection:
            connection.execute("DELETE FROM highlight_candidates WHERE scan_id = ?", (scan_id,))
            for candidate in candidates:
                connection.execute(
                    """INSERT INTO highlight_candidates (
                        id, scan_id, rank, start_time, end_time, media_start, media_end,
                        score, audio_score, speech_score, reaction_score, opening_score, payoff_score, reasons_json,
                        transcript, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        candidate.get("id") or uuid4_hex(), scan_id, int(candidate["rank"]),
                        float(candidate["start_time"]), float(candidate["end_time"]),
                        float(candidate["media_start"]), float(candidate["media_end"]),
                        float(candidate["score"]), float(candidate.get("audio_score", 0)),
                        float(candidate.get("speech_score", 0)), float(candidate.get("reaction_score", 0)),
                        float(candidate.get("opening_score", 0)), float(candidate.get("payoff_score", 0)),
                        json.dumps(candidate.get("reasons", []), ensure_ascii=False),
                        str(candidate.get("transcript", "")), now,
                    ),
                )

    def list_highlight_candidates(self, scan_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM highlight_candidates WHERE scan_id = ? ORDER BY rank ASC", (scan_id,)
            ).fetchall()
        return [self._highlight_candidate_dict(row) for row in rows]

    def get_highlight_candidate(self, scan_id: str, candidate_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM highlight_candidates WHERE scan_id = ? AND id = ?",
                (scan_id, candidate_id),
            ).fetchone()
        return self._highlight_candidate_dict(row) if row else None

    def mark_highlight_candidate_created(self, scan_id: str, candidate_id: str, job_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE highlight_candidates SET created_job_id = ? WHERE scan_id = ? AND id = ?",
                (job_id, scan_id, candidate_id),
            )

    @staticmethod
    def _highlight_scan_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        try:
            result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        except json.JSONDecodeError:
            result["metadata"] = {}
        result["rights_confirmed"] = bool(result.get("rights_confirmed"))
        return result

    @staticmethod
    def _highlight_candidate_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        try:
            result["reasons"] = json.loads(result.pop("reasons_json") or "[]")
        except json.JSONDecodeError:
            result["reasons"] = []
        return result

    def recover_interrupted_highlight_scans(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE highlight_scans SET status='queued', progress=0, message='Reprise après redémarrage', updated_at=? WHERE status='running'",
                (self.now(),),
            )
            connection.execute(
                "UPDATE highlight_scans SET status='cancelled', message='Analyse annulée lors du redémarrage', updated_at=? WHERE status='cancelling'",
                (self.now(),),
            )

    @staticmethod
    def _job_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        try:
            result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        except json.JSONDecodeError:
            result["metadata"] = {}
        result["rights_confirmed"] = bool(result.get("rights_confirmed"))
        return result

    def recover_interrupted_jobs(self) -> None:
        """Replace les jobs interrompus dans la file après un arrêt du serveur."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET status='queued', progress=0, message='Reprise après redémarrage', updated_at=? WHERE status='running'",
                (self.now(),),
            )
            connection.execute(
                "UPDATE jobs SET status='cancelled', message='Traitement annulé lors du redémarrage', updated_at=? WHERE status='cancelling'",
                (self.now(),),
            )
