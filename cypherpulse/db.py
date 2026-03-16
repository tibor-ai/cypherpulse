"""Database management for CypherPulse."""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database schema definition
DB_SCHEMA = """
    CREATE TABLE IF NOT EXISTS tweet_performance (
        tweet_id         TEXT PRIMARY KEY,
        post_type        TEXT NOT NULL,
        posted_at        TEXT NOT NULL,
        tweet_text       TEXT
    );

    CREATE TABLE IF NOT EXISTS tweet_snapshots (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        tweet_id         TEXT NOT NULL,
        snapshot_hours   INTEGER NOT NULL,
        snapshot_at      TEXT NOT NULL,
        likes            INTEGER DEFAULT 0,
        replies          INTEGER DEFAULT 0,
        retweets         INTEGER DEFAULT 0,
        quotes           INTEGER DEFAULT 0,
        impressions      INTEGER DEFAULT 0,
        UNIQUE(tweet_id, snapshot_hours)
    );
    
    CREATE INDEX IF NOT EXISTS idx_snapshots_tweet 
    ON tweet_snapshots(tweet_id);
    
    CREATE INDEX IF NOT EXISTS idx_snapshots_hours 
    ON tweet_snapshots(snapshot_hours);
"""


def _validate_db_path(path_str: str) -> Path:
    """Validate database path against path traversal attacks.
    
    Args:
        path_str: The path string to validate
        
    Returns:
        Validated Path object
        
    Raises:
        ValueError: If path contains traversal patterns or is unsafe
    """
    path = Path(path_str).resolve()
    
    # Check for path traversal patterns
    if ".." in path.parts:
        raise ValueError("Database path contains path traversal patterns (..)")
    
    # Ensure path is within user's home directory or current working directory
    home = Path.home().resolve()
    cwd = Path.cwd().resolve()
    
    if not (str(path).startswith(str(home)) or str(path).startswith(str(cwd))):
        raise ValueError(f"Database path must be within home directory or working directory")
    
    return path


# Validate DB_PATH environment variable if set
_db_path_env = os.getenv("DB_PATH")
if _db_path_env:
    try:
        DEFAULT_DB_PATH = _validate_db_path(_db_path_env)
    except ValueError as e:
        logger.error(f"Invalid DB_PATH environment variable: {e}")
        DEFAULT_DB_PATH = Path.home() / ".cypherpulse" / "analytics.db"
else:
    DEFAULT_DB_PATH = Path.home() / ".cypherpulse" / "analytics.db"


@contextmanager
def get_db_context(db_path: Optional[str] = None):
    """Context manager for database connections.
    
    Args:
        db_path: Optional path to database file
        
    Yields:
        sqlite3.Connection: Active database connection
    """
    conn = get_db(db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get database connection with schema initialization.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        sqlite3.Connection: Configured database connection
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    else:
        db_path = Path(db_path)
    
    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # Initialize schema from module constant
    conn.executescript(DB_SCHEMA)
    conn.commit()
    return conn


def get_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Get summary statistics.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        Dict containing total_tweets, total_snapshots, and avg_impressions_24h
    """
    with get_db_context(db_path) as conn:
        total_tweets = conn.execute(
            "SELECT COUNT(*) as cnt FROM tweet_performance"
        ).fetchone()["cnt"]
        
        total_snapshots = conn.execute(
            "SELECT COUNT(*) as cnt FROM tweet_snapshots"
        ).fetchone()["cnt"]
        
        avg_impressions = conn.execute("""
            SELECT ROUND(AVG(impressions), 1) as avg_imp
            FROM tweet_snapshots WHERE snapshot_hours = 24
        """).fetchone()["avg_imp"] or 0
        
        return {
            "total_tweets": total_tweets,
            "total_snapshots": total_snapshots,
            "avg_impressions_24h": avg_impressions
        }


def get_performance_by_type(snapshot_hours: int = 24, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get performance metrics grouped by post type.
    
    Args:
        snapshot_hours: Snapshot interval to query (24, 72, or 168)
        db_path: Optional path to database file
        
    Returns:
        List of dicts with post_type, posts count, and average engagement metrics
    """
    with get_db_context(db_path) as conn:
        rows = conn.execute("""
            SELECT p.post_type,
                   COUNT(*) as posts,
                   ROUND(AVG(s.likes), 1) as avg_likes,
                   ROUND(AVG(s.replies), 1) as avg_replies,
                   ROUND(AVG(s.retweets), 1) as avg_retweets,
                   ROUND(AVG(s.impressions), 1) as avg_impressions,
                   MAX(s.impressions) as max_impressions
            FROM tweet_snapshots s
            JOIN tweet_performance p ON p.tweet_id = s.tweet_id
            WHERE s.snapshot_hours = ?
            GROUP BY p.post_type
            ORDER BY avg_impressions DESC
        """, (snapshot_hours,)).fetchall()
        
        return [dict(row) for row in rows]


def get_top_posts(limit: int = 10, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get top posts by impressions.
    
    Args:
        limit: Maximum number of posts to return
        db_path: Optional path to database file
        
    Returns:
        List of top posts with tweet_id, post_type, text, and engagement metrics
    """
    with get_db_context(db_path) as conn:
        rows = conn.execute("""
            SELECT p.tweet_id, p.post_type, p.tweet_text, p.posted_at,
                   MAX(s.impressions) as impressions,
                   MAX(s.likes) as likes,
                   MAX(s.retweets) as retweets
            FROM tweet_snapshots s
            JOIN tweet_performance p ON p.tweet_id = s.tweet_id
            GROUP BY p.tweet_id
            ORDER BY impressions DESC
            LIMIT ?
        """, (limit,)).fetchall()
        
        return [dict(row) for row in rows]


def get_hourly_performance(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get performance by hour of day (UTC).
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        List of dicts with hour_utc, posts count, and average metrics
    """
    with get_db_context(db_path) as conn:
        rows = conn.execute("""
            SELECT CAST(strftime('%H', p.posted_at) AS INTEGER) as hour_utc,
                   COUNT(*) as posts,
                   ROUND(AVG(s.impressions), 1) as avg_impressions,
                   ROUND(AVG(s.likes), 1) as avg_likes
            FROM tweet_snapshots s
            JOIN tweet_performance p ON p.tweet_id = s.tweet_id
            WHERE s.snapshot_hours = 24 AND p.posted_at IS NOT NULL
            GROUP BY hour_utc
            ORDER BY hour_utc
        """).fetchall()
        
        return [dict(row) for row in rows]


def get_daily_performance(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get performance by day of week.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        List of dicts with dow, day_name, posts count, and average metrics
    """
    with get_db_context(db_path) as conn:
        rows = conn.execute("""
            SELECT CAST(strftime('%w', p.posted_at) AS INTEGER) as dow,
                   COUNT(*) as posts,
                   ROUND(AVG(s.impressions), 1) as avg_impressions,
                   ROUND(AVG(s.likes), 1) as avg_likes
            FROM tweet_snapshots s
            JOIN tweet_performance p ON p.tweet_id = s.tweet_id
            WHERE s.snapshot_hours = 24 AND p.posted_at IS NOT NULL
            GROUP BY dow
            ORDER BY dow
        """).fetchall()
        
        # Map day numbers to names
        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        return [
            {
                **dict(row),
                "day_name": day_names[row["dow"]]
            }
            for row in rows
        ]


def get_trends_by_type(snapshot_hours: int = 24, days: int = 30, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get engagement trends over time, grouped by post type.
    
    Args:
        snapshot_hours: Snapshot interval to query (24, 72, or 168)
        days: Number of days of history to include
        db_path: Optional path to database file
        
    Returns:
        List of dicts with post_date, post_type, posts count, and average metrics
    """
    with get_db_context(db_path) as conn:
        rows = conn.execute("""
            SELECT date(p.posted_at) as post_date,
                   p.post_type,
                   COUNT(*) as posts,
                   ROUND(AVG(s.impressions), 1) as avg_impressions,
                   ROUND(AVG(s.likes), 1) as avg_likes,
                   ROUND(AVG(s.retweets), 1) as avg_retweets
            FROM tweet_snapshots s
            JOIN tweet_performance p ON p.tweet_id = s.tweet_id
            WHERE s.snapshot_hours = ?
              AND p.posted_at >= date('now', ? || ' days')
            GROUP BY post_date, p.post_type
            ORDER BY post_date ASC, p.post_type
        """, (snapshot_hours, -days)).fetchall()

        return [dict(row) for row in rows]
