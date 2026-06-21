"""Import reviewed TweetClaw exports into the local CypherPulse database."""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .collector import TWEET_MAX_CHARS, detect_post_type, parse_twitter_date
from .db import get_db_context


_TWEET_URL_RE = re.compile(r"(?:x|twitter)\.com/[^/]+/status/(\d+)", re.I)


def _first_value(row: Dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return None


def _int_value(row: Dict[str, Any], names: Iterable[str]) -> int:
    value = _first_value(row, names)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _tweet_id(row: Dict[str, Any]) -> str:
    value = _first_value(row, ("id", "tweet_id", "tweetId", "tweetID"))
    if value not in (None, ""):
        return str(value)

    url = _first_value(row, ("url", "tweet_url", "tweetUrl", "link"))
    if isinstance(url, str):
        match = _TWEET_URL_RE.search(url)
        if match:
            return match.group(1)

    return ""


def _created_at(row: Dict[str, Any]) -> str:
    value = _first_value(
        row,
        (
            "createdAt",
            "created_at",
            "posted_at",
            "date",
            "timestamp",
        ),
    )
    if not value:
        return datetime.now(timezone.utc).isoformat()

    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return parse_twitter_date(text)


def _read_json_payload(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("tweets") or payload.get("data") or payload.get("items") or []
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def _read_json_lines(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_tweetclaw_export(path: str) -> List[Dict[str, Any]]:
    """Read a TweetClaw export file in JSON, JSONL, NDJSON, or CSV format."""
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return _read_csv(source)
    if suffix in {".jsonl", ".ndjson"}:
        return _read_json_lines(source)
    if suffix == ".json":
        return _read_json_payload(source)
    raise ValueError("TweetClaw export must be .json, .jsonl, .ndjson, or .csv")


def _normalize(row: Dict[str, Any]) -> Optional[Tuple[str, str, str, str, Dict[str, int]]]:
    tweet_id = _tweet_id(row)
    if not tweet_id:
        return None

    text = str(_first_value(row, ("text", "full_text", "tweet_text", "content")) or "")
    created_at = _created_at(row)
    post_type = str(_first_value(row, ("post_type", "type")) or detect_post_type(row))
    metrics = {
        "likes": _int_value(row, ("likes", "likeCount", "favorite_count")),
        "replies": _int_value(row, ("replies", "replyCount", "reply_count")),
        "retweets": _int_value(row, ("retweets", "retweetCount", "retweet_count")),
        "quotes": _int_value(row, ("quotes", "quoteCount", "quote_count")),
        "impressions": _int_value(row, ("impressions", "viewCount", "views")),
    }
    return tweet_id, post_type, created_at, text[:TWEET_MAX_CHARS], metrics


def import_tweetclaw_export(
    path: str,
    snapshot_hours: int = 24,
    db_path: Optional[str] = None,
) -> Dict[str, int]:
    """Import TweetClaw rows into CypherPulse.

    Existing tweet rows and snapshots are left unchanged.
    """
    rows = read_tweetclaw_export(path)
    imported_tweets = 0
    imported_snapshots = 0
    skipped = 0
    snapshot_at = datetime.now(timezone.utc).isoformat()

    with get_db_context(db_path) as conn:
        for row in rows:
            normalized = _normalize(row)
            if normalized is None:
                skipped += 1
                continue

            tweet_id, post_type, created_at, text, metrics = normalized
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO tweet_performance
                (tweet_id, post_type, posted_at, tweet_text)
                VALUES (?, ?, ?, ?)
                """,
                (tweet_id, post_type, created_at, text),
            )
            imported_tweets += cursor.rowcount

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO tweet_snapshots
                (tweet_id, snapshot_hours, snapshot_at, likes, replies,
                 retweets, quotes, impressions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tweet_id,
                    snapshot_hours,
                    snapshot_at,
                    metrics["likes"],
                    metrics["replies"],
                    metrics["retweets"],
                    metrics["quotes"],
                    metrics["impressions"],
                ),
            )
            imported_snapshots += cursor.rowcount

        conn.commit()

    return {
        "rows": len(rows),
        "tweets": imported_tweets,
        "snapshots": imported_snapshots,
        "skipped": skipped,
    }
