#!/usr/bin/env python3
"""
CypherPulse public account analyzer.
Fetches recent tweets for any public account and produces an engagement breakdown.
Usage: python analyze_public_account.py <handle> [--api-key KEY]
"""
import sys
import json
import argparse
import requests
from datetime import datetime
from collections import defaultdict
from pathlib import Path

def fetch_tweets(handle: str, api_key: str, count: int = 40) -> list:
    resp = requests.get(
        "https://api.twitterapi.io/twitter/tweet/advanced_search",
        params={"query": f"from:{handle} -is:retweet", "queryType": "Latest", "count": count},
        headers={"X-API-Key": api_key},
        timeout=15
    )
    resp.raise_for_status()
    d = resp.json()
    tweets = d.get("data", {}).get("tweets", []) or d.get("tweets", [])
    if not tweets and d.get("data", {}).get("unavailable"):
        raise ValueError(f"Account @{handle} is unavailable: {d['data'].get('unavailableReason','unknown')}")
    return tweets

def analyze(handle: str, tweets: list) -> dict:
    by_hour = defaultdict(lambda: {"count": 0, "likes": 0, "rts": 0, "replies": 0})
    all_engagement = []

    for t in tweets:
        likes = int(t.get("likeCount", 0) or 0)
        rts = int(t.get("retweetCount", 0) or 0)
        replies = int(t.get("replyCount", 0) or 0)
        all_engagement.append(likes + rts + replies)

        created = t.get("createdAt", "")
        try:
            dt = datetime.strptime(created, "%a %b %d %H:%M:%S +0000 %Y")
            h = dt.hour
            by_hour[h]["count"] += 1
            by_hour[h]["likes"] += likes
            by_hour[h]["rts"] += rts
            by_hour[h]["replies"] += replies
        except ValueError:
            pass

    n = len(tweets)
    if n == 0:
        raise ValueError("No tweets found")

    best_hours = sorted(
        [(h, v) for h, v in by_hour.items() if v["count"] >= 2],
        key=lambda x: (x[1]["likes"] + x[1]["rts"]) / x[1]["count"],
        reverse=True
    )[:3]

    top_tweets = sorted(tweets, key=lambda t: int(t.get("likeCount", 0) or 0), reverse=True)[:3]

    return {
        "handle": handle,
        "tweets_analyzed": n,
        "avg_likes": round(sum(int(t.get("likeCount", 0) or 0) for t in tweets) / n, 1),
        "avg_rts": round(sum(int(t.get("retweetCount", 0) or 0) for t in tweets) / n, 1),
        "max_likes": max(int(t.get("likeCount", 0) or 0) for t in tweets),
        "best_hours": [
            {"hour": h, "avg_engagement": round((v["likes"] + v["rts"]) / v["count"], 1),
             "posts": v["count"], "likes": v["likes"], "rts": v["rts"]}
            for h, v in best_hours
        ],
        "top_tweets": [
            {"text": t.get("text", "")[:120], "likes": int(t.get("likeCount", 0) or 0),
             "rts": int(t.get("retweetCount", 0) or 0)}
            for t in top_tweets
        ]
    }

def print_report(result: dict):
    h = result["handle"]
    print(f"\n📊 CypherPulse Analysis — @{h}")
    print(f"{'─'*45}")
    print(f"Tweets analyzed:   {result['tweets_analyzed']}")
    print(f"Avg likes/tweet:   {result['avg_likes']}")
    print(f"Avg RTs/tweet:     {result['avg_rts']}")
    print(f"Best single tweet: {result['max_likes']} likes")

    if result["best_hours"]:
        print(f"\n⏰ Best posting hours (UTC):")
        for bh in result["best_hours"]:
            print(f"  {bh['hour']:02d}:00 — avg {bh['avg_engagement']} engagement ({bh['posts']} posts)")

    if result["top_tweets"]:
        print(f"\n🏆 Top tweet:")
        t = result["top_tweets"][0]
        print(f"  {t['likes']} likes, {t['rts']} RTs")
        print(f"  \"{t['text'][:80]}\"")

    print(f"\n→ Track your own: github.com/tibor-ai/cypherpulse")

def main():
    parser = argparse.ArgumentParser(description="Analyze a public X account with CypherPulse")
    parser.add_argument("handle", help="Twitter/X handle (without @)")
    parser.add_argument("--api-key", help="twitterapi.io API key")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    api_key = args.api_key
    if not api_key:
        secrets = Path("/root/.openclaw/secrets/twitterapi-io.json")
        if secrets.exists():
            api_key = json.loads(secrets.read_text())["api_key"]
        else:
            print("Error: provide --api-key or configure twitterapi-io.json", file=sys.stderr)
            sys.exit(1)

    try:
        tweets = fetch_tweets(args.handle, api_key)
        result = analyze(args.handle, tweets)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print_report(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
