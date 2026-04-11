"""SQLite database layer for tracking results."""

import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class TrackDatabase:
    """SQLite database for visibility tracking."""

    def __init__(self, db_path: str = "data/tracks.db"):
        """Initialize database connection and create tables if needed."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_hash TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS visibility_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER REFERENCES runs(id),
                    model_provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    response_text TEXT,
                    mentions_json TEXT,
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_run_id 
                ON visibility_records(run_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_model 
                ON visibility_records(model_name)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_detected_at 
                ON visibility_records(detected_at)
                """
            )

            conn.commit()
        finally:
            conn.close()

    def create_run(self, config_hash: Optional[str] = None) -> int:
        """Create a new run record. Returns run_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO runs (config_hash, started_at) VALUES (?, ?)",
                (config_hash, datetime.now(timezone.utc)),
            )
            conn.commit()
            lastrowid = cursor.lastrowid
            return lastrowid if lastrowid is not None else 0
        finally:
            conn.close()

    def complete_run(self, run_id: int) -> None:
        """Mark a run as completed."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE runs SET completed_at = ? WHERE id = ?",
                (datetime.now(timezone.utc), run_id),
            )
            conn.commit()
        finally:
            conn.close()

    def record_query(
        self,
        run_id: int,
        model_provider: str,
        model_name: str,
        prompt: str,
        response_text: str,
        mentions: Dict[str, int],
    ) -> int:
        """Record a single query result. Returns record id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO visibility_records 
                (run_id, model_provider, model_name, prompt, response_text, mentions_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    model_provider,
                    model_name,
                    prompt,
                    response_text,
                    json.dumps(mentions),
                ),
            )
            conn.commit()
            lastrowid = cursor.lastrowid
            return lastrowid if lastrowid is not None else 0
        finally:
            conn.close()

    def get_by_run(self, run_id: int) -> List[Dict[str, Any]]:
        """Get all records from a specific run."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT * FROM visibility_records 
                WHERE run_id = ? 
                ORDER BY detected_at
                """,
                (run_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_recent_runs(self, days: int = 90) -> List[Dict[str, Any]]:
        """Get recent runs within specified days."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cursor.execute(
                """
                SELECT * FROM runs 
                WHERE started_at > ? 
                ORDER BY started_at DESC
                """,
                (cutoff,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_trends(
        self, brand_keyword: str, days: int = 30, group_by_day: bool = True
    ) -> List[Dict[str, Any]]:
        """Get mention trends for a brand over time."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            if group_by_day:
                cursor.execute(
                    """
                    SELECT 
                        DATE(detected_at) as date,
                        model_name,
                        COUNT(*) as total_queries,
                        SUM(CASE 
                            WHEN mentions_json LIKE ? THEN 1 
                            ELSE 0 
                        END) as mention_count
                    FROM visibility_records
                    WHERE detected_at > ?
                    GROUP BY date, model_name
                    ORDER BY date ASC
                    """,
                    (f'%"{brand_keyword}%', cutoff),
                )
            else:
                cursor.execute(
                    """
                    SELECT 
                        model_name,
                        COUNT(*) as total_queries,
                        SUM(CASE 
                            WHEN mentions_json LIKE ? THEN 1 
                            ELSE 0 
                        END) as mention_count
                    FROM visibility_records
                    WHERE detected_at > ?
                    GROUP BY model_name
                    ORDER BY total_queries DESC
                    """,
                    (f'%"{brand_keyword}%', cutoff),
                )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_model_statistics(self, brand_keyword: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get per-model statistics for a brand."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            cursor.execute(
                """
                SELECT 
                    model_provider,
                    model_name,
                    COUNT(*) as total_runs,
                    SUM(CASE 
                        WHEN mentions_json LIKE ? THEN 1 
                        ELSE 0 
                    END) as total_mentions,
                    ROUND(100.0 * SUM(CASE 
                            WHEN mentions_json LIKE ? THEN 1 
                            ELSE 0 
                        END) / COUNT(*), 2) as mention_rate_pct
                FROM visibility_records
                WHERE detected_at > ?
                GROUP BY model_provider, model_name
                ORDER BY total_runs DESC
                """,
                (f'%"{brand_keyword}%', f'%"{brand_keyword}%', cutoff),
            )
            # Use SUM(CASE...) instead of COUNT(CASE...) to correctly count only matches

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_unique_brands(self) -> List[str]:
        """Get list of unique brand names from visibility records."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT mentions_json FROM visibility_records WHERE mentions_json IS NOT NULL AND mentions_json != '{}'"
            )
            brands = set()
            for row in cursor.fetchall():
                try:
                    mentions = json.loads(row["mentions_json"])
                    brands.update(mentions.keys())
                except (json.JSONDecodeError, TypeError):
                    pass
            return sorted(brands)
        finally:
            conn.close()

    def get_all_mentions(self, days: int = 90) -> List[Dict[str, Any]]:
        """Get all detected mentions in the specified period."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            cursor.execute(
                """
                SELECT * FROM visibility_records
                WHERE detected_at > ?
                AND mentions_json IS NOT NULL
                AND mentions_json != '{}'
                ORDER BY detected_at DESC
                """,
                (cutoff,),
            )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def export_to_csv(self, output_path: str, days: int = 90) -> None:
        """Export all data to CSV file."""
        import csv

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            cursor.execute(
                """
                SELECT 
                    v.id,
                    v.detected_at,
                    v.model_provider,
                    v.model_name,
                    v.prompt,
                    v.response_text,
                    v.mentions_json,
                    r.started_at as run_started
                FROM visibility_records v
                JOIN runs r ON v.run_id = r.id
                WHERE v.detected_at > ?
                ORDER BY v.detected_at DESC
                """,
                (cutoff,),
            )

            rows = cursor.fetchall()

            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            with open(output, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "id",
                        "detected_at",
                        "model_provider",
                        "model_name",
                        "prompt",
                        "response_text",
                        "mentions",
                        "run_started",
                    ]
                )
                for row in rows:
                    writer.writerow(
                        [
                            row["id"],
                            row["detected_at"],
                            row["model_provider"],
                            row["model_name"],
                            row["prompt"],
                            (row["response_text"] or "")[:500],
                            row["mentions_json"],
                            row["run_started"],
                        ]
                    )
        finally:
            conn.close()

    def export_to_json(self, output_path: str, days: int = 90) -> None:
        """Export all data to JSON file."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            cursor.execute(
                """
                SELECT 
                    v.id,
                    v.detected_at,
                    v.model_provider,
                    v.model_name,
                    v.prompt,
                    v.response_text,
                    v.mentions_json,
                    r.started_at as run_started
                FROM visibility_records v
                JOIN runs r ON v.run_id = r.id
                WHERE v.detected_at > ?
                ORDER BY v.detected_at DESC
                """,
                (cutoff,),
            )

            rows = cursor.fetchall()
            data = [dict(row) for row in rows]

            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            with open(output, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        finally:
            conn.close()

    def cleanup_old_runs(self, max_days: int = 90) -> int:
        """Delete runs older than max_days. Returns number of records deleted."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)

            cursor.execute("SELECT id FROM runs WHERE completed_at < ?", (cutoff,))
            runs_to_delete = [row["id"] for row in cursor.fetchall()]

            if not runs_to_delete:
                return 0

            placeholders = ",".join("?" * len(runs_to_delete))
            cursor.execute(
                f"DELETE FROM visibility_records WHERE run_id IN ({placeholders})",
                tuple(runs_to_delete),
            )
            records_deleted = cursor.rowcount

            cursor.execute(f"DELETE FROM runs WHERE id IN ({placeholders})", tuple(runs_to_delete))

            conn.commit()
            return records_deleted
        finally:
            conn.close()

    def get_all_records(self, brand: str = "*", days: int = 90) -> List[Dict[str, Any]]:
        """Get all records within specified days, optionally filtered by brand."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            current_time = datetime.now(timezone.utc)
            cutoff = current_time - timedelta(days=days)

            # Build query based on brand filter
            if brand != "*":
                cursor.execute(
                    """
                    SELECT
                        v.id,
                        v.run_id,
                        v.detected_at,
                        v.model_provider,
                        v.model_name,
                        v.prompt,
                        v.response_text,
                        v.mentions_json,
                        r.started_at as run_started_at,
                        r.completed_at as run_completed_at,
                        r.config_hash
                    FROM visibility_records v
                    JOIN runs r ON v.run_id = r.id
                    WHERE v.detected_at > ?
                        AND (v.mentions_json LIKE ? OR v.response_text LIKE ?)
                    ORDER BY v.detected_at DESC, v.id DESC
                    """,
                    (cutoff, f'%"{brand}"%', f'%"{brand}"%'),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        v.id,
                        v.run_id,
                        v.detected_at,
                        v.model_provider,
                        v.model_name,
                        v.prompt,
                        v.response_text,
                        v.mentions_json,
                        r.started_at as run_started_at,
                        r.completed_at as run_completed_at,
                        r.config_hash
                    FROM visibility_records v
                    JOIN runs r ON v.run_id = r.id
                    WHERE v.detected_at > ?
                    ORDER BY v.detected_at DESC, v.id DESC
                    """,
                    (cutoff,),
                )

            rows = cursor.fetchall()
            records = []
            for row in rows:
                record = {
                    "id": row["id"],
                    "run_id": row["run_id"],
                    "timestamp": row["detected_at"],
                    "model_provider": row["model_provider"],
                    "model_name": row["model_name"],
                    "prompt": row["prompt"],
                    "response_text": row["response_text"],
                    "mentions_json": row["mentions_json"],
                    "mentions_str": self._format_mentions_str(row["mentions_json"]),
                    "run_started_at": row["run_started_at"],
                    "run_completed_at": row["run_completed_at"],
                    "config_hash": row["config_hash"],
                }
                # Add formatted message
                if row["mentions_json"]:
                    mentions = json.loads(row["mentions_json"])
                    record["message"] = self._get_emoji_message(mentions)
                records.append(record)

            return records
        finally:
            conn.close()

    def _format_mentions_str(self, mentions_json: Optional[str]) -> str:
        """Format mentions_json into human-readable string."""
        if not mentions_json or mentions_json == "{}":
            return ""
        try:
            mentions = json.loads(mentions_json)
            parts = []
            for brand, count in sorted(mentions.items()):
                parts.append(f"{brand} ({count})")
            return "; ".join(parts) if parts else ""
        except:
            return mentions_json or ""

    def _get_emoji_message(self, mentions: Dict[str, int]) -> str:
        """Get emoji message for detected mentions."""
        if not mentions:
            return ""
        parts = []
        for brand, count in sorted(mentions.items()):
            emoji = "✅" if count > 0 else "🟡"
            parts.append(f"{emoji} {brand}: {count}")
        return "; ".join(parts)

    def get_all_runs(self, days: int = 90) -> List[Dict[str, Any]]:
        """Get all tracking runs within specified days."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            cursor.execute(
                """
                SELECT r.*,
                       COUNT(v.id) as record_count,
                       COUNT(CASE WHEN v.mentions_json AND v.mentions_json != '{}' THEN 1 END) as successful_count
                FROM runs r
                LEFT JOIN visibility_records v ON r.id = v.run_id
                WHERE r.completed_at IS NULL OR r.started_at > ?
                GROUP BY r.id
                ORDER BY r.started_at DESC
                """,
                (cutoff,),
            )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_record_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Get a single record by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    v.id,
                    v.run_id,
                    v.detected_at,
                    v.model_provider,
                    v.model_name,
                    v.prompt,
                    v.response_text,
                    v.mentions_json,
                    r.started_at as run_started_at,
                    r.completed_at as run_completed_at,
                    r.config_hash
                FROM visibility_records v
                JOIN runs r ON v.run_id = r.id
                WHERE v.id = ?
                """,
                (record_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            mentions = json.loads(row["mentions_json"]) if row["mentions_json"] else {}
            return {
                "id": row["id"],
                "run_id": row["run_id"],
                "timestamp": row["detected_at"],
                "model_provider": row["model_provider"],
                "model_name": row["model_name"],
                "prompt": row["prompt"],
                "response": row["response_text"],
                "mentions": mentions,
                "mentions_str": self._format_mentions_str(row["mentions_json"]),
                "run_started_at": row["run_started_at"],
                "run_completed_at": row["run_completed_at"],
                "config_hash": row["config_hash"],
            }
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get overall database statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM runs")
            total_runs = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM visibility_records")
            total_records = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT model_name) FROM visibility_records")
            unique_models = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM visibility_records WHERE mentions_json IS NOT NULL AND mentions_json != '{}'"
            )
            total_mentions = cursor.fetchone()[0]

            return {
                "total_runs": total_runs,
                "total_records": total_records,
                "unique_models": unique_models,
                "total_mentions": total_mentions,
            }
        finally:
            conn.close()
