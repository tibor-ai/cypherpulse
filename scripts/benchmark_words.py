#!/usr/bin/env python3
"""
CypherPulse Benchmark Word Analysis

Finds tweets with significantly higher impressions than average for the same handle,
then runs word frequency + avg-impression analysis on those outlier tweets.

Usage:
    python benchmark_words.py [--db PATH] [--sigma 1.5] [--min-tweets 2] [--top 50]

Outputs JSON to stdout (for piping into other tools) + a readable summary.
"""

import argparse
import json
import re
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

# ── Stopwords ─────────────────────────────────────────────────────────────────
STOPWORDS = {
    'the','a','an','is','are','was','were','be','been','being','have','has',
    'had','do','does','did','will','would','could','should','may','might',
    'shall','can','need','dare','ought','used','to','of','in','on','at','by',
    'for','with','about','against','between','into','through','during','before',
    'after','above','below','from','up','down','out','off','over','under',
    'again','further','then','once','and','but','or','nor','not','so','yet',
    'both','either','neither','whether','i','me','my','myself','we','our',
    'ourselves','you','your','yourself','he','him','his','himself','she','her',
    'herself','it','its','itself','they','them','their','themselves','what',
    'which','who','whom','this','that','these','those','am','if','as','until',
    'while','because','although','since','unless','however','therefore','thus',
    'hence','also','just','very','too','more','most','some','any','all','each',
    'every','no','only','same','than','how','when','where','why','via','vs',
    're','etc','get','got','like','know','make','think','want','one','two',
    'new','now','here','there','well','see','say','said','says','go','going',
    'come','coming','use','using','has','had','its','been','being',
}

URL_RE    = re.compile(r'https?://\S+')
MENTION_RE = re.compile(r'@\w+')
HASHTAG_RE = re.compile(r'#\w+')
PUNCT_RE  = re.compile(r'[^\w\s#]')


def tokenize(text: str) -> list[str]:
    """Extract meaningful words and #hashtags from tweet text."""
    text = URL_RE.sub(' ', text)
    text = MENTION_RE.sub(' ', text)

    hashtags = HASHTAG_RE.findall(text.lower())
    text_no_hashtags = HASHTAG_RE.sub(' ', text)
    text_clean = PUNCT_RE.sub(' ', text_no_hashtags).lower()

    words = []
    for w in text_clean.split():
        if len(w) < 3:
            continue
        if w.isdigit():
            continue
        if w in STOPWORDS:
            continue
        words.append(w)

    return words + hashtags


def find_outliers(rows: list[dict], sigma: float = 1.5) -> list[dict]:
    """Return tweets whose impressions are >= mean + sigma * std."""
    impressions = [r['impressions'] for r in rows]
    if len(impressions) < 3:
        # Not enough data for stats — return top 20% by impression
        threshold = sorted(impressions, reverse=True)[max(1, len(impressions) // 5)]
        return [r for r in rows if r['impressions'] >= threshold]

    mean = statistics.mean(impressions)
    std  = statistics.stdev(impressions)
    threshold = mean + sigma * std
    outliers = [r for r in rows if r['impressions'] >= threshold]

    print(f"  Stats: mean={mean:.1f}, std={std:.1f}, threshold={threshold:.1f} "
          f"(mean + {sigma}σ)", file=sys.stderr)
    print(f"  Outliers: {len(outliers)} / {len(rows)} tweets "
          f"({len(outliers)/len(rows)*100:.0f}%)", file=sys.stderr)
    return outliers


def word_analysis(tweets: list[dict], min_tweets: int = 2, top_n: int = 50) -> list[dict]:
    """Compute avg impressions per word across the given tweets."""
    word_data: dict[str, list[float]] = defaultdict(list)

    for t in tweets:
        text = t.get('tweet_text') or ''
        impr = float(t.get('impressions', 0))
        seen = set()
        for word in tokenize(text):
            if word not in seen:
                word_data[word].append(impr)
                seen.add(word)

    results = []
    for word, impressions_list in word_data.items():
        if len(impressions_list) < min_tweets:
            continue
        results.append({
            'word': word,
            'count': len(impressions_list),
            'avg_impressions': round(statistics.mean(impressions_list), 1),
            'is_hashtag': word.startswith('#'),
        })

    results.sort(key=lambda x: x['avg_impressions'], reverse=True)
    return results[:top_n]


def main():
    parser = argparse.ArgumentParser(description='Benchmark high-impression tweet word analysis')
    parser.add_argument('--db', default=None, help='Path to CypherPulse DB')
    parser.add_argument('--sigma', type=float, default=1.5,
                        help='Standard deviations above mean to define "high" (default: 1.5)')
    parser.add_argument('--min-tweets', type=int, default=2,
                        help='Minimum tweets a word must appear in (default: 2)')
    parser.add_argument('--top', type=int, default=50,
                        help='Number of top words to return (default: 50)')
    parser.add_argument('--json-out', action='store_true',
                        help='Output full JSON results')
    args = parser.parse_args()

    # Find DB
    db_path = args.db
    if not db_path:
        candidates = [
            Path.home() / '.cypherpulse' / 'analytics.db',
            Path('/opt/analytics/tweet_performance.db'),
        ]
        for c in candidates:
            if c.exists():
                db_path = str(c)
                break
    if not db_path:
        print('Error: could not find CypherPulse database. Use --db PATH.', file=sys.stderr)
        sys.exit(1)

    print(f"Using DB: {db_path}", file=sys.stderr)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Fetch all tweets with 24h snapshots
    try:
        rows = conn.execute("""
            SELECT p.tweet_id, p.tweet_text, p.post_type, p.posted_at,
                   s.impressions, s.likes, s.retweets
            FROM tweet_performance p
            JOIN tweet_snapshots s ON s.tweet_id = p.tweet_id
            WHERE s.snapshot_hours = 24 AND p.tweet_text IS NOT NULL
            ORDER BY s.impressions DESC
        """).fetchall()
    finally:
        conn.close()

    all_tweets = [dict(r) for r in rows]
    print(f"\nTotal tweets with 24h snapshots: {len(all_tweets)}", file=sys.stderr)

    if not all_tweets:
        print("No data found.", file=sys.stderr)
        sys.exit(1)

    # Find outliers
    print(f"\nFinding outliers (σ={args.sigma})...", file=sys.stderr)
    outliers = find_outliers(all_tweets, sigma=args.sigma)

    if not outliers:
        print("No outliers found — try lowering --sigma", file=sys.stderr)
        sys.exit(1)

    print(f"\nTop outlier tweets:", file=sys.stderr)
    for t in outliers[:10]:
        print(f"  [{t['impressions']} impr] {t['tweet_text'][:80]}", file=sys.stderr)

    # Word analysis on outliers
    print(f"\nRunning word analysis on {len(outliers)} outlier tweets...", file=sys.stderr)
    words = word_analysis(outliers, min_tweets=args.min_tweets, top_n=args.top)

    print(f"\n{'─'*60}", file=sys.stderr)
    print(f"TOP WORDS in HIGH-IMPRESSION tweets (benchmark):", file=sys.stderr)
    print(f"{'─'*60}", file=sys.stderr)
    for w in words[:20]:
        tag = ' [hashtag]' if w['is_hashtag'] else ''
        print(f"  {w['word']:20s} avg {w['avg_impressions']:6.1f} impr  (in {w['count']} tweets){tag}",
              file=sys.stderr)

    if args.json_out:
        print(json.dumps({
            'sigma': args.sigma,
            'total_tweets': len(all_tweets),
            'outlier_tweets': len(outliers),
            'words': words,
        }, indent=2))


if __name__ == '__main__':
    main()
