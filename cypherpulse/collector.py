"""Tweet scanning and metrics collection for CypherPulse."""

import logging
import requests
import sqlite3
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from .db import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Measure engagement at 1 day, 3 days, and 7 days to track engagement decay patterns.
# These intervals capture initial viral spread (24h), sustained interest (72h), and long-tail discovery (168h).
SNAPSHOT_HOURS = [24, 72, 168]


def _should_continue_pagination(cursor: Optional[str], tweets: List[Dict], 
                               cutoff: datetime) -> bool:
    """Check if pagination should continue.
    
    Args:
        cursor: Next page cursor
        tweets: Current page of tweets
        cutoff: Cutoff datetime for filtering
        
    Returns:
        True if pagination should continue, False otherwise
    """
    if not cursor:
        return False
    
    if not tweets:
        return False
    
    # Check if oldest tweet is beyond the cutoff
    oldest = tweets[-1].get("createdAt", "")
    if oldest:
        try:
            oldest_dt = datetime.strptime(oldest, '%a %b %d %H:%M:%S +0000 %Y').replace(tzinfo=timezone.utc)
            if oldest_dt < cutoff:
                return False
        except ValueError:
            pass
    
    return True


def fetch_recent_tweets(username: str, api_key: str, days: int = 7, max_pages: int = 20) -> List[Dict[str, Any]]:
    """Fetch tweets from the last N days using cursor pagination (20 per page).
    
    Args:
        username: Twitter username (without @)
        api_key: twitterapi.io API key
        days: Number of days of history to fetch
        max_pages: Maximum number of pages to retrieve
        
    Returns:
        List of tweet data dictionaries
    """
    if not username or not api_key:
        logger.error("Username and API key are required")
        return []
    since_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    all_tweets = []
    seen_ids = set()
    cursor = None

    for page in range(max_pages):
        params = {
            "query": f"from:{username} since:{since_date}",
            "queryType": "Latest",
        }
        if cursor:
            params["cursor"] = cursor

        try:
            resp = requests.get(
                "https://api.twitterapi.io/twitter/tweet/advanced_search",
                headers={"X-API-Key": api_key},
                params=params,
                timeout=20
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching tweets (page {page + 1}): {e}")
            break

        tweets = data.get("tweets", [])
        if not tweets:
            break

        for t in tweets:
            tid = str(t.get("id", ""))
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                all_tweets.append(t)

        cursor = data.get("next_cursor") or data.get("cursor")
        if not _should_continue_pagination(cursor, tweets, cutoff):
            break

    return all_tweets


def fetch_tweet_metrics(tweet_id: str, api_key: str) -> Optional[Dict[str, int]]:
    """Fetch metrics for a specific tweet.
    
    Args:
        tweet_id: Twitter tweet ID
        api_key: twitterapi.io API key
        
    Returns:
        Dict with likes, replies, retweets, quotes, impressions, or None if failed
    """
    if not tweet_id or not api_key:
        logger.error("Tweet ID and API key are required")
        return None
    try:
        resp = requests.get(
            "https://api.twitterapi.io/twitter/tweets",
            headers={"X-API-Key": api_key},
            params={"tweet_ids": tweet_id},
            timeout=15
        )
        resp.raise_for_status()
        tweets = resp.json().get("tweets", [])
        
        if tweets:
            t = tweets[0]
            return {
                "likes": t.get("likeCount", 0) or 0,
                "replies": t.get("replyCount", 0) or 0,
                "retweets": t.get("retweetCount", 0) or 0,
                "quotes": t.get("quoteCount", 0) or 0,
                "impressions": t.get("viewCount", 0) or 0,
            }
    except requests.RequestException as e:
        logger.error(f"Error fetching metrics for {tweet_id}: {e}")
    
    return None


def detect_post_type(tweet_data: dict) -> str:
    """Detect post type from tweet data.
    
    Analyzes tweet metadata to determine if it's a reply, retweet, or original tweet.
    
    Args:
        tweet_data: Raw tweet data dictionary from API
        
    Returns:
        Post type: 'reply' if in reply to another tweet, 'retweet' if retweeting,
        or 'tweet' for original posts
    """
    is_reply = tweet_data.get("isReply", False) or bool(tweet_data.get("inReplyToId"))
    is_retweet = bool(tweet_data.get("retweeted_tweet"))
    
    if is_reply:
        return "reply"
    elif is_retweet:
        return "retweet"
    else:
        return "tweet"


def parse_twitter_date(date_str: str) -> str:
    """Parse Twitter date format to ISO 8601 format.
    
    Converts Twitter's custom date format to ISO 8601 for consistent storage.
    Falls back to current time if parsing fails.
    
    Args:
        date_str: Twitter date string (e.g., 'Wed Oct 10 20:19:24 +0000 2018')
        
    Returns:
        ISO 8601 formatted datetime string (e.g., '2018-10-10T20:19:24+00:00')
    """
    try:
        dt = datetime.strptime(date_str, '%a %b %d %H:%M:%S +0000 %Y')
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def scan_tweets(username: str, api_key: str, db_path: Optional[str] = None) -> int:
    """Scan and register new tweets from the specified username.
    
    Args:
        username: Twitter username (without @)
        api_key: twitterapi.io API key
        db_path: Optional path to database file
        
    Returns:
        Number of new tweets registered
        
    Raises:
        ValueError: If username contains invalid characters
    """
    # Validate username against injection patterns
    if not re.match(r'^[A-Za-z0-9_]{1,50}$', username):
        raise ValueError(f"Invalid username format: {username}. Only alphanumeric and underscore allowed.")
    
    logger.info(f"Scanning tweets from @{username}...")
    
    tweets = fetch_recent_tweets(username, api_key)
    logger.info(f"Found {len(tweets)} recent tweets")
    
    if not tweets:
        return 0
    
    try:
        conn = get_db(db_path)
        
        # Get existing tweet IDs
        existing = {
            r[0] for r in conn.execute("SELECT tweet_id FROM tweet_performance").fetchall()
        }
        
        new_count = 0
        
        for tweet in tweets:
            tweet_id = str(tweet.get("id", ""))
            
            if not tweet_id or tweet_id in existing:
                continue
            
            post_type = detect_post_type(tweet)
            text = tweet.get("text", "")[:280]
            created_at = parse_twitter_date(tweet.get("createdAt", ""))
            
            conn.execute("""
                INSERT OR IGNORE INTO tweet_performance 
                (tweet_id, post_type, posted_at, tweet_text)
                VALUES (?, ?, ?, ?)
            """, (tweet_id, post_type, created_at, text))
            
            new_count += 1
            logger.info(f"  + [{post_type}] {tweet_id} — {text[:60]}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Registered {new_count} new tweets")
        return new_count
    except sqlite3.Error as e:
        logger.error(f"Database error during tweet scan: {e}")
        raise


def _collect_snapshot_for_tweet(conn: sqlite3.Connection, row: sqlite3.Row, 
                                api_key: str, now: datetime) -> int:
    """Collect due snapshots for a single tweet.
    
    Args:
        conn: Database connection
        row: Tweet row with tweet_id, post_type, posted_at
        api_key: twitterapi.io API key
        now: Current timestamp
        
    Returns:
        Number of snapshots collected for this tweet
    """
    try:
        posted = datetime.fromisoformat(row["posted_at"])
    except ValueError:
        return 0
    
    age_hours = (now - posted).total_seconds() / 3600
    snapshots_collected = 0
    
    for snap_hours in SNAPSHOT_HOURS:
        # Skip if not due yet
        if age_hours < snap_hours:
            continue
        
        # Check if snapshot already exists
        exists = conn.execute("""
            SELECT 1 FROM tweet_snapshots 
            WHERE tweet_id = ? AND snapshot_hours = ?
        """, (row["tweet_id"], snap_hours)).fetchone()
        
        if exists:
            continue
        
        # Fetch and store metrics
        metrics = fetch_tweet_metrics(row["tweet_id"], api_key)
        
        if not metrics:
            continue
        
        conn.execute("""
            INSERT OR IGNORE INTO tweet_snapshots
            (tweet_id, snapshot_hours, snapshot_at, likes, replies, 
             retweets, quotes, impressions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["tweet_id"], snap_hours, now.isoformat(),
            metrics["likes"], metrics["replies"], metrics["retweets"],
            metrics["quotes"], metrics["impressions"]
        ))
        
        snapshots_collected += 1
        snap_label = {24: "24h", 72: "72h", 168: "7d"}.get(snap_hours, f"{snap_hours}h")
        logger.info(f"  [{snap_label}] {row['post_type']:<8} {row['tweet_id'][:16]} "
              f"likes={metrics['likes']} replies={metrics['replies']} "
              f"retweets={metrics['retweets']} impressions={metrics['impressions']}")
    
    return snapshots_collected


def collect_snapshots(api_key: str, db_path: Optional[str] = None) -> int:
    """Collect metrics snapshots for tweets at their due measurement points.
    
    Args:
        api_key: twitterapi.io API key
        db_path: Optional path to database file
        
    Returns:
        Number of snapshots collected
    """
    logger.info("Collecting metric snapshots...")
    
    try:
        conn = get_db(db_path)
        now = datetime.now(timezone.utc)
        
        # Get recent tweets
        rows = conn.execute("""
            SELECT tweet_id, post_type, posted_at 
            FROM tweet_performance
            ORDER BY posted_at DESC LIMIT 500
        """).fetchall()
        
        updated = 0
        for row in rows:
            updated += _collect_snapshot_for_tweet(conn, row, api_key, now)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Collected {updated} snapshots")
        return updated
    except sqlite3.Error as e:
        logger.error(f"Database error during snapshot collection: {e}")
        raise
