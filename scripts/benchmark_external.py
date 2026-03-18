#!/usr/bin/env python3
"""
CypherPulse External Benchmark

Fetches top-performing tweets from one or more external X/Twitter handles,
then builds a word benchmark showing which words appear in high-impression content.

Usage:
    python benchmark_external.py @handle1 @handle2 ... [--top-tweets 20] [--top-words 50] [--json-out]

Example:
    python benchmark_external.py @levelsio @marc_louvion @arvidkahl --top-tweets 20 --top-words 30

API key is read from /root/.openclaw/secrets/twitterapi-io.json
"""

import argparse
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import requests

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
    'come','coming','use','using','its','been','being','still','even','back',
    'actually','really','great','good','first','time','people','things','way',
}

URL_RE     = re.compile(r'https?://\S+')
MENTION_RE = re.compile(r'@\w+')
HASHTAG_RE = re.compile(r'#\w+')
PUNCT_RE   = re.compile(r'[^\w\s#]')


def load_api_key() -> str:
    # Prefer environment variable; fall back to a configurable secrets file path.
    env_key = os.environ.get('TWITTERAPI_IO_KEY') or os.environ.get('TWITTER_API_KEY')
    if env_key:
        return env_key
    secrets_path = os.environ.get('TWITTERAPI_SECRET_PATH', '')
    path = Path(secrets_path) if secrets_path else Path.home() / '.cypherpulse' / 'twitterapi-io.json'
    if not path.exists():
        print(f"Error: API key not found. Set TWITTERAPI_IO_KEY env var or TWITTERAPI_SECRET_PATH.", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())['api_key']


def fetch_top_tweets(handle: str, api_key: str, top_n: int = 20) -> list[dict]:
    """Fetch recent tweets for a handle, return top N by likes+retweets."""
    handle = handle.lstrip('@')
    print(f"  Fetching @{handle}...", file=sys.stderr)
    
    resp = requests.get(
        'https://api.twitterapi.io/twitter/tweet/advanced_search',
        params={
            'query': f'from:{handle} -is:retweet',
            'queryType': 'Top',
            'count': 40,
        },
        headers={'X-API-Key': api_key},
        timeout=20,
    )
    resp.raise_for_status()
    d = resp.json()
    
    tweets = d.get('data', {}).get('tweets', []) or d.get('tweets', [])
    
    if not tweets:
        if d.get('data', {}).get('unavailable'):
            print(f"  ⚠️  @{handle} is unavailable/suspended", file=sys.stderr)
        else:
            print(f"  ⚠️  No tweets found for @{handle}", file=sys.stderr)
        return []
    
    # Sort by engagement (likes + retweets) and take top N
    def score(t):
        return (t.get('likeCount') or 0) + (t.get('retweetCount') or 0) * 3
    
    tweets.sort(key=score, reverse=True)
    top = tweets[:top_n]
    
    avg_likes = statistics.mean(t.get('likeCount', 0) or 0 for t in top)
    print(f"  ✓ {len(top)} tweets, avg likes in top {top_n}: {avg_likes:.0f}", file=sys.stderr)
    return top


def tokenize(text: str) -> list[str]:
    text = URL_RE.sub(' ', text)
    text = MENTION_RE.sub(' ', text)
    hashtags = HASHTAG_RE.findall(text.lower())
    text_no_ht = HASHTAG_RE.sub(' ', text)
    text_clean = PUNCT_RE.sub(' ', text_no_ht).lower()
    words = []
    for w in text_clean.split():
        if len(w) < 3 or w.isdigit() or w in STOPWORDS:
            continue
        words.append(w)
    return words + hashtags


def build_word_benchmark(
    handles_tweets: dict[str, list[dict]],
    min_handles: int = 1,
    top_n: int = 50,
) -> list[dict]:
    """
    Build benchmark words. Each word gets:
    - avg_engagement: avg (likes + rts*3) of tweets it appeared in
    - count: number of tweets it appeared in
    - handles: which handles used it
    - is_hashtag

    min_handles: word must appear in tweets from at least this many different handles
    """
    word_data: dict[str, dict] = defaultdict(lambda: {
        'engagements': [], 'handles': set()
    })

    for handle, tweets in handles_tweets.items():
        for t in tweets:
            text = t.get('text') or t.get('full_text') or ''
            engagement = (t.get('likeCount') or 0) + (t.get('retweetCount') or 0) * 3
            seen = set()
            for word in tokenize(text):
                if word not in seen:
                    word_data[word]['engagements'].append(engagement)
                    word_data[word]['handles'].add(handle)
                    seen.add(word)

    results = []
    for word, data in word_data.items():
        if len(data['handles']) < min_handles:
            continue
        results.append({
            'word': word,
            'count': len(data['engagements']),
            'avg_engagement': round(statistics.mean(data['engagements']), 1),
            'handles': sorted(data['handles']),
            'handle_count': len(data['handles']),
            'is_hashtag': word.startswith('#'),
        })

    results.sort(key=lambda x: x['avg_engagement'], reverse=True)
    return results[:top_n]


def print_table(words: list[dict], handles: list[str]):
    print(f"\n{'─'*70}", file=sys.stderr)
    print(f"BENCHMARK — top words in high-engagement tweets from: {', '.join(handles)}", file=sys.stderr)
    print(f"{'─'*70}", file=sys.stderr)
    print(f"  {'Word':<22} {'Avg Eng':>8}  {'Tweets':>7}  {'Handles':>8}  Tag", file=sys.stderr)
    print(f"  {'─'*22} {'─'*8}  {'─'*7}  {'─'*8}  {'─'*3}", file=sys.stderr)
    for w in words[:30]:
        tag = '🟠' if w['is_hashtag'] else '🔵'
        hdls = ','.join(w['handles'])
        print(f"  {w['word']:<22} {w['avg_engagement']:>8.1f}  {w['count']:>7}  {w['handle_count']:>8}  {tag}  [{hdls}]", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description='Benchmark word analysis from external X accounts')
    parser.add_argument('handles', nargs='+', help='Twitter/X handles (with or without @)')
    parser.add_argument('--top-tweets', type=int, default=20,
                        help='Top N tweets per handle to analyse (default: 20)')
    parser.add_argument('--top-words', type=int, default=50,
                        help='Top N words to return (default: 50)')
    parser.add_argument('--min-handles', type=int, default=1,
                        help='Word must appear across at least N handles (default: 1)')
    parser.add_argument('--json-out', action='store_true',
                        help='Print full JSON to stdout')
    args = parser.parse_args()

    api_key = load_api_key()
    handles = [h.lstrip('@') for h in args.handles]

    print(f"\nFetching top tweets for {len(handles)} handles...", file=sys.stderr)
    handles_tweets = {}
    for handle in handles:
        tweets = fetch_top_tweets(handle, api_key, top_n=args.top_tweets)
        if tweets:
            handles_tweets[handle] = tweets

    if not handles_tweets:
        print("No data retrieved. Check handles and API key.", file=sys.stderr)
        sys.exit(1)

    print(f"\nBuilding word benchmark...", file=sys.stderr)
    words = build_word_benchmark(handles_tweets, min_handles=args.min_handles, top_n=args.top_words)

    print_table(words, list(handles_tweets.keys()))

    if args.json_out:
        out = {
            'handles': list(handles_tweets.keys()),
            'tweets_per_handle': {h: len(t) for h, t in handles_tweets.items()},
            'words': words,
        }
        print(json.dumps(out, indent=2))
    
    print(f"\n✓ Done. {len(words)} benchmark words from {len(handles_tweets)} handles.", file=sys.stderr)


if __name__ == '__main__':
    main()
