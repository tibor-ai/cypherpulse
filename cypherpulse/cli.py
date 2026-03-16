"""Command-line interface for CypherPulse."""

import os
import sys
from pathlib import Path
from typing import Tuple
from dotenv import load_dotenv
from .collector import scan_tweets, collect_snapshots
from .db import get_stats, get_performance_by_type, get_top_posts

DEFAULT_PORT = 8080


def load_config() -> Tuple[str, str]:
    """Load configuration from .env file.
    
    Returns:
        Tuple of (api_key, username)
        
    Raises:
        SystemExit: If required environment variables are not set
    """
    # Search order: script's own directory, cwd, cwd parent
    # Using __file__ ensures cron (which runs from /) still finds the .env
    _script_dir = Path(__file__).resolve().parent.parent
    _candidates = [
        _script_dir / ".env",
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
    ]
    env_path = next((p for p in _candidates if p.exists()), None)

    if env_path:
        load_dotenv(env_path)
    
    api_key = os.getenv("TWITTER_API_KEY")
    username = os.getenv("TWITTER_USERNAME")
    
    if not api_key or not username:
        print("Error: TWITTER_API_KEY and TWITTER_USERNAME must be set in .env file")
        print("\nCreate a .env file with:")
        print("  TWITTER_API_KEY=your_api_key_here")
        print("  TWITTER_USERNAME=your_username_here")
        sys.exit(1)
    
    return api_key, username


def cmd_scan() -> None:
    """Scan for new tweets from configured username."""
    api_key, username = load_config()
    scan_tweets(username, api_key)


def cmd_collect() -> None:
    """Collect metric snapshots for tracked tweets at their due measurement points."""
    api_key, _ = load_config()
    collect_snapshots(api_key)


def cmd_report() -> None:
    """Generate and print performance analytics report to console."""
    stats = get_stats()
    
    print("\n=== CypherPulse Analytics Report ===\n")
    print(f"Total tweets tracked: {stats['total_tweets']}")
    print(f"Total snapshots: {stats['total_snapshots']}")
    print(f"Average impressions (24h): {stats['avg_impressions_24h']}\n")
    
    # Performance by type
    for hours in [24, 72, 168]:
        label = {24: "24 hours", 72: "3 days", 168: "7 days"}[hours]
        print(f"\n=== Performance at {label} ===")
        
        data = get_performance_by_type(hours)
        
        if not data:
            print("  No data yet")
            continue
        
        print(f"{'Type':<12} {'Posts':>6} {'Avg ❤️':>8} {'Avg 💬':>8} "
              f"{'Avg 🔁':>8} {'Avg 👁️':>10}")
        print("-" * 62)
        
        for row in data:
            print(f"{row['post_type']:<12} {row['posts']:>6} "
                  f"{row['avg_likes']:>8} {row['avg_replies']:>8} "
                  f"{row['avg_retweets']:>8} {row['avg_impressions']:>10}")
    
    # Top posts
    print("\n=== Top 10 Posts by Impressions ===\n")
    top = get_top_posts(10)
    
    for i, post in enumerate(top, 1):
        text = (post['tweet_text'] or '')[:70]
        print(f"{i}. [{post['post_type']}] "
              f"👁️{post['impressions']} ❤️{post['likes']} 🔁{post['retweets']}")
        print(f"   {text}\n")


def cmd_serve() -> None:
    """Start the web dashboard server.
    
    Binds to 127.0.0.1 by default for security (localhost only).
    Set HOST=0.0.0.0 to allow external connections.
    Set PORT to change the default port (8080).
    """
    port = int(os.getenv("PORT", DEFAULT_PORT))
    host = os.getenv("HOST", "127.0.0.1")
    
    try:
        import uvicorn
        from .api import app
        
        print(f"\n🚀 Starting CypherPulse dashboard at http://{host}:{port}")
        if host == "127.0.0.1":
            print("   (Bound to localhost only — set HOST=0.0.0.0 to allow external access)")
        print("   Press Ctrl+C to stop\n")
        
        uvicorn.run(app, host=host, port=port, log_level="info")
    except ImportError:
        print("Error: uvicorn not installed. Run: pip install uvicorn")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point.
    
    Parses command-line arguments and dispatches to appropriate command handler.
    Available commands: scan, collect, report, serve
    """
    if len(sys.argv) < 2:
        print("CypherPulse - X/Twitter Analytics Dashboard\n")
        print("Usage:")
        print("  cypherpulse scan      Scan for new tweets")
        print("  cypherpulse collect   Collect metric snapshots")
        print("  cypherpulse report    Generate analytics report")
        print("  cypherpulse serve     Start web dashboard")
        sys.exit(1)
    
    command = sys.argv[1]
    
    commands = {
        "scan": cmd_scan,
        "collect": cmd_collect,
        "report": cmd_report,
        "serve": cmd_serve,
    }
    
    if command not in commands:
        print(f"Unknown command: {command}")
        print(f"Available commands: {', '.join(commands.keys())}")
        sys.exit(1)
    
    commands[command]()


if __name__ == "__main__":
    main()
