import sqlite3
import time
from datetime import datetime, timezone, timedelta

import config

LIVE_DUR = "CASE WHEN leave_time IS NULL THEN ? - join_time ELSE duration END"


def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL DEFAULT 0,
            join_time REAL NOT NULL,
            leave_time REAL,
            duration REAL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS server_config (
            guild_id INTEGER PRIMARY KEY,
            study_vc_id INTEGER NOT NULL,
            role_name TEXT NOT NULL DEFAULT 'Studying'
        )
    """)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(study_sessions)").fetchall()]
    if "guild_id" not in cols:
        conn.execute("ALTER TABLE study_sessions ADD COLUMN guild_id INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    conn.close()


def set_server_config(guild_id: int, study_vc_id: int, role_name: str = "Studying"):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO server_config (guild_id, study_vc_id, role_name) VALUES (?, ?, ?)",
        (guild_id, study_vc_id, role_name),
    )
    conn.commit()
    conn.close()


def get_server_config(guild_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT study_vc_id, role_name FROM server_config WHERE guild_id = ?",
        (guild_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {"study_vc_id": row[0], "role_name": row[1]}


def start_session(user_id: int, guild_id: int = 0) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO study_sessions (user_id, guild_id, join_time) VALUES (?, ?, ?)",
        (user_id, guild_id, time.time()),
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return session_id


def end_session(user_id: int) -> float:
    conn = get_connection()
    row = conn.execute(
        "SELECT id, join_time FROM study_sessions WHERE user_id = ? AND leave_time IS NULL ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row is None:
        conn.close()
        return 0.0
    session_id, join_time = row
    now = time.time()
    duration = now - join_time
    conn.execute(
        "UPDATE study_sessions SET leave_time = ?, duration = ? WHERE id = ?",
        (now, duration, session_id),
    )
    conn.commit()
    conn.close()
    return duration


def get_leaderboard(guild_id: int, since: float = 0) -> list[tuple[int, float]]:
    now = time.time()
    conn = get_connection()
    rows = conn.execute(
        f"""
        SELECT user_id, SUM({LIVE_DUR}) as total
        FROM study_sessions
        WHERE guild_id = ? AND join_time >= ?
        GROUP BY user_id
        HAVING total > 0
        ORDER BY total DESC
        LIMIT 10
        """,
        (now, guild_id, since),
    ).fetchall()
    conn.close()
    return rows


def get_user_total(user_id: int, guild_id: int, since: float = 0) -> float:
    now = time.time()
    conn = get_connection()
    row = conn.execute(
        f"SELECT COALESCE(SUM({LIVE_DUR}), 0) FROM study_sessions WHERE user_id = ? AND guild_id = ? AND join_time >= ?",
        (now, user_id, guild_id, since),
    ).fetchone()
    conn.close()
    return row[0]


def get_session_count(user_id: int, guild_id: int, since: float = 0) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM study_sessions WHERE user_id = ? AND guild_id = ? AND join_time >= ?",
        (user_id, guild_id, since),
    ).fetchone()
    conn.close()
    return row[0]


def get_best_session(user_id: int, guild_id: int) -> float:
    now = time.time()
    conn = get_connection()
    row = conn.execute(
        f"SELECT COALESCE(MAX({LIVE_DUR}), 0) FROM study_sessions WHERE user_id = ? AND guild_id = ?",
        (now, user_id, guild_id),
    ).fetchone()
    conn.close()
    return row[0]


def get_user_rank(user_id: int, guild_id: int, since: float = 0) -> int:
    now = time.time()
    conn = get_connection()
    rows = conn.execute(
        f"""
        SELECT user_id FROM study_sessions
        WHERE guild_id = ? AND join_time >= ?
        GROUP BY user_id
        HAVING SUM({LIVE_DUR}) > 0
        ORDER BY SUM({LIVE_DUR}) DESC
        """,
        (guild_id, since, now, now),
    ).fetchall()
    conn.close()
    for i, (uid,) in enumerate(rows):
        if uid == user_id:
            return i + 1
    return 0


def get_study_streak(user_id: int, guild_id: int) -> int:
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT DATE(join_time, 'unixepoch') as d FROM study_sessions WHERE user_id = ? AND guild_id = ? ORDER BY d DESC",
        (user_id, guild_id),
    ).fetchall()
    conn.close()
    if not rows:
        return 0
    streak = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    expected = today
    for (d,) in rows:
        if d == expected:
            streak += 1
            prev = datetime.strptime(expected, "%Y-%m-%d")
            expected = (prev - timedelta(days=1)).strftime("%Y-%m-%d")
        elif d < expected:
            break
    return streak


def get_active_join_time(user_id: int, guild_id: int) -> float | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT join_time FROM study_sessions WHERE user_id = ? AND guild_id = ? AND leave_time IS NULL ORDER BY id DESC LIMIT 1",
        (user_id, guild_id),
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_recent_sessions(user_id: int, guild_id: int, limit: int = 10) -> list[tuple[float, float]]:
    now = time.time()
    conn = get_connection()
    rows = conn.execute(
        f"SELECT join_time, {LIVE_DUR} as dur FROM study_sessions WHERE user_id = ? AND guild_id = ? ORDER BY join_time DESC LIMIT ?",
        (now, user_id, guild_id, limit),
    ).fetchall()
    conn.close()
    return rows
