"""FastAPI backend for CypherPulse dashboard."""

import json
import logging
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

# Load .env early so TWITTER_API_KEY is available to the API server
try:
    from dotenv import load_dotenv as _load_dotenv
    _env_search = [
        Path(__file__).resolve().parent.parent / ".env",   # worktree root
        Path.cwd() / ".env",                               # cwd
        Path.cwd().parent / ".env",                        # cwd parent
        Path.home() / ".cypherpulse" / ".env",            # ~/.cypherpulse/.env
        Path.home() / "projects" / "cypherpulse" / ".env", # ~/projects/cypherpulse/.env
    ]
    _loaded = False
    for _env_candidate in _env_search:
        if _env_candidate.exists():
            _load_dotenv(_env_candidate, override=False)
            _loaded = True
            break
    if not _loaded:
        # Try all candidates without breaking — load all that exist
        for _env_candidate in _env_search:
            if _env_candidate.exists():
                _load_dotenv(_env_candidate, override=False)
except ImportError:
    pass

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .db import (
    get_stats,
    get_performance_by_type,
    get_top_posts,
    get_hourly_performance,
    get_daily_performance,
    get_trends_by_type,
    get_decay_curve,
    get_heatmap,
    get_word_bubbles,
)
from . import __version__

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CypherPulse API", version=__version__)

# CORS configuration - read from environment variable
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Determine web directory
WEB_DIR = Path(__file__).parent.parent / "web"


@app.get("/", response_model=None)
async def root() -> Union[FileResponse, Dict[str, str]]:
    """Serve the dashboard."""
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    logger.warning(f"Dashboard index.html not found at {index_file}, falling back to API response")
    return {"message": "CypherPulse API", "version": __version__}


@app.get("/api/stats")
async def api_stats(
    days: Optional[int] = Query(default=None, ge=0, le=365, description="Rolling window in days; 0 or omit = all time"),
    from_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
) -> JSONResponse:
    """Get summary statistics."""
    try:
        stats = get_stats(days=days, from_date=from_date, to_date=to_date)
        stats["version"] = __version__
        return JSONResponse(stats)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")


@app.get("/api/performance/{snapshot_hours}")
async def api_performance(
    snapshot_hours: int,
    days: Optional[int] = Query(default=None, ge=0, le=365, description="Rolling window in days; 0 or omit = all time"),
    from_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
) -> JSONResponse:
    """Get performance metrics by post type for a specific snapshot interval."""
    if snapshot_hours not in [24, 72, 168]:
        raise HTTPException(status_code=400, detail="snapshot_hours must be 24, 72, or 168")
    try:
        data = get_performance_by_type(snapshot_hours, days=days, from_date=from_date, to_date=to_date)
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch performance data")


@app.get("/api/top-posts")
async def api_top_posts(
    limit: int = Query(default=10, ge=1, le=100),
    days: Optional[int] = Query(default=None, ge=0, le=365, description="Rolling window in days; 0 or omit = all time"),
    from_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
) -> JSONResponse:
    """Get top posts by impressions."""
    try:
        data = get_top_posts(limit, days=days, from_date=from_date, to_date=to_date)
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching top posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch top posts")


@app.get("/api/hourly-performance")
async def api_hourly(
    days: Optional[int] = Query(default=None, ge=0, le=365, description="Rolling window in days; 0 or omit = all time"),
    from_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
) -> JSONResponse:
    """Get performance by hour of day."""
    try:
        data = get_hourly_performance(days=days, from_date=from_date, to_date=to_date)
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching hourly performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch hourly performance")


@app.get("/api/daily-performance")
async def api_daily(
    days: Optional[int] = Query(default=None, ge=0, le=365, description="Rolling window in days; 0 or omit = all time"),
    from_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
) -> JSONResponse:
    """Get performance by day of week."""
    try:
        data = get_daily_performance(days=days, from_date=from_date, to_date=to_date)
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching daily performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch daily performance")


@app.get("/api/trends/{snapshot_hours}")
async def api_trends(
    snapshot_hours: int,
    days: Optional[int] = Query(default=None, ge=0, le=365, description="Rolling window in days; 0 or omit = all time"),
    from_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
) -> JSONResponse:
    """Get engagement trends over time by post type."""
    if snapshot_hours not in [24, 72, 168]:
        raise HTTPException(status_code=400, detail="snapshot_hours must be 24, 72, or 168")
    try:
        data = get_trends_by_type(snapshot_hours, days=days, from_date=from_date, to_date=to_date)
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trends")


@app.get("/api/decay-curve")
async def api_decay_curve(
    days: Optional[int] = Query(default=None, ge=0, le=365, description="Rolling window in days; 0 or omit = all time"),
    from_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
) -> JSONResponse:
    """Get impression decay curve grouped by post type.

    Only includes tweets with snapshots at all three checkpoints (24h, 72h, 168h).
    Returns list of {post_type, h24, h72, h168, count}.
    """
    try:
        data = get_decay_curve(days=days, from_date=from_date, to_date=to_date)
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching decay curve: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch decay curve data")


@app.get("/api/heatmap")
async def api_heatmap(
    days: Optional[int] = Query(default=None, ge=0, le=365, description="Rolling window in days; 0 or omit = all time"),
    from_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    post_type_filter: Optional[str] = Query(default=None, description="Filter: 'reply', 'post', or omit for all"),
) -> JSONResponse:
    """Get hour × day heatmap data.

    Returns list of {hour: 0-23, dow: 0-6 (Sun=0), avg_impressions, posts}.
    Accepts optional post_type_filter: 'reply' (replies only), 'post' (non-replies), or omit/all for no filter.
    """
    try:
        # Normalise filter value
        ptf = post_type_filter.lower().strip() if post_type_filter else None
        if ptf == 'all':
            ptf = None
        data = get_heatmap(days=days, from_date=from_date, to_date=to_date, post_type_filter=ptf)
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching heatmap: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch heatmap data")


@app.get("/api/word-bubbles")
async def api_word_bubbles(
    days: Optional[int] = Query(default=None, ge=0, le=365, description="Rolling window in days; 0 or omit = all time"),
    from_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    min_tweets: int = Query(default=2, ge=1, le=100, description="Minimum tweet count per word"),
    top_n: int = Query(default=50, ge=1, le=200, description="Maximum number of words to return"),
    mode: str = Query(default='words', description="Mode: 'words' (single words), 'pairs' (PMI bigrams), 'both' (merged)"),
) -> JSONResponse:
    """Get word frequency bubble chart data.

    Returns list of {word, count, avg_impressions, score, is_hashtag, is_bigram}.
    Mode 'words' = single words (default), 'pairs' = PMI bigrams, 'both' = merged.
    """
    if mode not in ('words', 'pairs', 'both'):
        raise HTTPException(status_code=400, detail="mode must be 'words', 'pairs', or 'both'")
    try:
        data = get_word_bubbles(
            days=days,
            from_date=from_date,
            to_date=to_date,
            min_tweets=min_tweets,
            top_n=top_n,
            mode=mode,
        )
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching word bubbles: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch word bubble data")


# ─── Benchmark helpers ────────────────────────────────────────────────────────

_TWITTERAPI_SECRET_PATH = Path(
    os.getenv("TWITTERAPI_SECRET_PATH", "/root/.openclaw/secrets/twitterapi-io.json")
)

def _load_twitterapi_key() -> str:
    """Load twitterapi.io API key.

    Priority order:
    1. TWITTERAPI_IO_KEY environment variable
    2. TWITTER_API_KEY environment variable (same key, set in .env during install)
    3. Secrets JSON file at TWITTERAPI_SECRET_PATH
    """
    # 1. Explicit env var
    key = os.getenv("TWITTERAPI_IO_KEY") or os.getenv("TWITTER_API_KEY")
    if key:
        return key
    # 2. Secrets file (server-side path)
    try:
        with open(_TWITTERAPI_SECRET_PATH) as f:
            return json.load(f)["api_key"]
    except Exception:
        pass
    logger.error("twitterapi.io key not found — set TWITTER_API_KEY in .env or TWITTERAPI_IO_KEY env var")
    return ""


async def fetch_handle_tweets(handle: str, api_key: str) -> List[Dict[str, Any]]:
    """Fetch top 40 tweets from a handle via twitterapi.io advanced_search.

    Returns a list of tweet dicts with keys: text, likeCount, retweetCount, createdAt.
    Returns empty list on any error (suspended/not found/network issue).
    """
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    params = {
        "query": f"from:{handle} -is:retweet",
        "queryType": "Top",
        "count": "40",
    }
    headers = {"X-API-Key": api_key}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"twitterapi.io returned {resp.status_code} for handle={handle}")
                return []
            data = resp.json()
            # API returns tweets at top level: {tweets: [...]} or nested {data: {tweets: [...]}}
            tweets = data.get("tweets") or data.get("data", {}).get("tweets", [])
            return tweets or []
    except Exception as e:
        logger.warning(f"fetch_handle_tweets failed for handle={handle}: {e}")
        return []


_STOPWORDS = {
    'the','a','an','is','are','was','were','be','been','being','have','has','had',
    'do','does','did','will','would','could','should','may','might','shall','can',
    'need','dare','ought','used','to','of','in','on','at','by','for','with','about',
    'against','between','into','through','during','before','after','above','below',
    'from','up','down','out','off','over','under','again','further','then','once',
    'and','but','or','nor','not','so','yet','both','either','neither','whether',
    'i','me','my','myself','we','our','ourselves','you','your','yourself','he',
    'him','his','himself','she','her','herself','it','its','itself','they','them',
    'their','themselves','what','which','who','whom','this','that','these','those',
    'am','if','as','until','while','because','although','since','unless','however',
    'therefore','thus','hence','also','just','very','too','more','most','some','any',
    'all','each','every','no','only','same','than','how','when','where','why','via',
    'its','vs','re','etc',
}


def _score_tweets(
    tweet_texts: List[str],
    mode: str = 'words',
    min_tweets: int = 1,
    top_n: int = 50,
) -> List[Dict[str, Any]]:
    """Tokenize tweet texts and compute IDF/PMI-scored word/bigram data.

    Returns same shape as get_word_bubbles():
    [{word, count, avg_impressions, score, is_hashtag, is_bigram}]

    avg_impressions is always 0 for external tweets (we don't have impression data).
    """
    total_tweets = len(tweet_texts)
    if total_tweets == 0:
        return []

    word_data: Dict[str, Any] = {}
    bigram_data: Dict[str, Any] = {}
    unigram_for_pmi: Dict[str, Any] = {}

    for idx, text in enumerate(tweet_texts):
        tweet_id = str(idx)

        # Extract hashtags before stripping
        hashtags = re.findall(r'#\w+', text.lower())

        text_clean = re.sub(r'https?://\S+', ' ', text.lower())
        text_clean = re.sub(r'@\w+', ' ', text_clean)
        text_clean = re.sub(r'#\w+', ' ', text_clean)
        text_clean = re.sub(r'[^\w\s]', ' ', text_clean)
        raw_words = text_clean.split()

        ordered_tokens = []
        for w in raw_words:
            w = w.strip()
            if (len(w) >= 3
                    and w not in _STOPWORDS
                    and not w.isnumeric()
                    and w.isalpha()):
                ordered_tokens.append(w)

        token_set = set(ordered_tokens)
        for h in hashtags:
            h = h.strip()
            if len(h) >= 3:
                token_set.add(h)

        for token in token_set:
            if token not in word_data:
                word_data[token] = {'tweets': set(), 'is_hashtag': token.startswith('#')}
            word_data[token]['tweets'].add(tweet_id)

        for token in set(ordered_tokens):
            if token not in unigram_for_pmi:
                unigram_for_pmi[token] = set()
            unigram_for_pmi[token].add(tweet_id)

        seen_bigrams: set = set()
        for i in range(len(ordered_tokens) - 1):
            a, b = ordered_tokens[i], ordered_tokens[i + 1]
            bigram = f"{a} {b}"
            if bigram not in seen_bigrams:
                seen_bigrams.add(bigram)
                if bigram not in bigram_data:
                    bigram_data[bigram] = {'tweets': set()}
                bigram_data[bigram]['tweets'].add(tweet_id)

    def _build_word_results() -> List[Dict[str, Any]]:
        results = []
        for word, data in word_data.items():
            count = len(data['tweets'])
            if count < min_tweets:
                continue
            idf = math.log(max(total_tweets, 1) / count) if total_tweets > 0 else 1.0
            score = round(idf, 4)  # no impression data → score by IDF only
            results.append({
                'word': word,
                'count': count,
                'avg_impressions': 0,
                'score': score,
                'is_hashtag': data['is_hashtag'],
                'is_bigram': False,
            })
        return results

    def _build_bigram_results() -> List[Dict[str, Any]]:
        results = []
        for bigram, data in bigram_data.items():
            count = len(data['tweets'])
            if count < min_tweets:
                continue
            a, b = bigram.split(' ', 1)
            pa = len(unigram_for_pmi.get(a, set())) / max(total_tweets, 1)
            pb = len(unigram_for_pmi.get(b, set())) / max(total_tweets, 1)
            pab = count / max(total_tweets, 1)
            pmi = math.log(pab / (pa * pb)) if pa > 0 and pb > 0 else 0.0
            pmi_weight = max(0.1, pmi)
            idf = math.log(max(total_tweets, 1) / count) if total_tweets > 0 else 1.0
            score = round(idf * pmi_weight, 4)
            results.append({
                'word': bigram,
                'count': count,
                'avg_impressions': 0,
                'score': score,
                'is_hashtag': False,
                'is_bigram': True,
            })
        return results

    if mode == 'pairs':
        results = _build_bigram_results()
    elif mode == 'both':
        results = _build_word_results() + _build_bigram_results()
    else:
        results = _build_word_results()

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_n]


_HANDLE_RE = re.compile(r'^[A-Za-z0-9_]{1,50}$')


@app.get("/api/benchmark")
async def api_benchmark(
    handle: str = Query(..., description="X/Twitter handle (without @)"),
    mode: str = Query(default='words', description="Mode: 'words', 'pairs', 'both'"),
    top_n: int = Query(default=50, ge=1, le=200),
    min_tweets: int = Query(default=1, ge=1, le=100),
) -> JSONResponse:
    """Fetch top 40 tweets from a handle and return word bubble data.

    Returns same shape as /api/word-bubbles.
    Returns empty list (not 500) if handle is unavailable/suspended.
    """
    # Strip leading @ and validate
    clean_handle = handle.lstrip('@')
    if not _HANDLE_RE.match(clean_handle):
        raise HTTPException(status_code=400, detail="Invalid handle: alphanumeric + underscore only, max 50 chars")
    if mode not in ('words', 'pairs', 'both'):
        raise HTTPException(status_code=400, detail="mode must be 'words', 'pairs', or 'both'")

    api_key = _load_twitterapi_key()
    if not api_key:
        logger.error("twitterapi.io key not available — returning empty benchmark")
        return JSONResponse([])

    tweets = await fetch_handle_tweets(clean_handle, api_key)
    if not tweets:
        return JSONResponse([])

    texts = [t.get('text', '') for t in tweets if t.get('text')]
    data = _score_tweets(texts, mode=mode, min_tweets=min_tweets, top_n=top_n)
    return JSONResponse(data)


# Mount static assets if they exist
if (WEB_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")
