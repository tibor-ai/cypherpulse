"""FastAPI backend for CypherPulse dashboard."""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .db import (
    get_stats,
    get_performance_by_type,
    get_top_posts,
    get_hourly_performance,
    get_daily_performance,
    get_trends_by_type
)

app = FastAPI(title="CypherPulse API", version="0.1.0")

# Determine web directory
WEB_DIR = Path(__file__).parent.parent / "web"


@app.get("/")
async def root():
    """Serve the dashboard."""
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "CypherPulse API", "version": "0.1.0"}


@app.get("/api/stats")
async def api_stats():
    """Get summary statistics."""
    try:
        return JSONResponse(get_stats())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/performance/{snapshot_hours}")
async def api_performance(snapshot_hours: int):
    """Get performance metrics by post type for a specific snapshot interval."""
    try:
        data = get_performance_by_type(snapshot_hours)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/top-posts")
async def api_top_posts(limit: int = 10):
    """Get top posts by impressions."""
    try:
        data = get_top_posts(limit)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/hourly-performance")
async def api_hourly():
    """Get performance by hour of day."""
    try:
        data = get_hourly_performance()
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/daily-performance")
async def api_daily():
    """Get performance by day of week."""
    try:
        data = get_daily_performance()
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/trends/{snapshot_hours}")
async def api_trends(snapshot_hours: int, days: int = 30):
    """Get engagement trends over time by post type."""
    try:
        data = get_trends_by_type(snapshot_hours, days)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# Mount static assets if they exist
if (WEB_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")
