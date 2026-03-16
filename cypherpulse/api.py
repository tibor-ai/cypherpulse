"""FastAPI backend for CypherPulse dashboard."""

import logging
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Union
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
    get_trends_by_type
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CypherPulse API", version="0.1.0")

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


@app.get("/")
async def root() -> Union[FileResponse, Dict[str, str]]:
    """Serve the dashboard."""
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    logger.warning(f"Dashboard index.html not found at {index_file}, falling back to API response")
    return {"message": "CypherPulse API", "version": "0.1.0"}


@app.get("/api/stats")
async def api_stats() -> JSONResponse:
    """Get summary statistics."""
    try:
        return JSONResponse(get_stats())
    except sqlite3.Error as e:
        logger.error(f"Database error fetching stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")


@app.get("/api/performance/{snapshot_hours}")
async def api_performance(snapshot_hours: int) -> JSONResponse:
    """Get performance metrics by post type for a specific snapshot interval."""
    if snapshot_hours not in [24, 72, 168]:
        raise HTTPException(status_code=400, detail="snapshot_hours must be 24, 72, or 168")
    try:
        data = get_performance_by_type(snapshot_hours)
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch performance data")


@app.get("/api/top-posts")
async def api_top_posts(limit: int = Query(default=10, ge=1, le=100)) -> JSONResponse:
    """Get top posts by impressions."""
    try:
        data = get_top_posts(limit)
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching top posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch top posts")


@app.get("/api/hourly-performance")
async def api_hourly() -> JSONResponse:
    """Get performance by hour of day."""
    try:
        data = get_hourly_performance()
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching hourly performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch hourly performance")


@app.get("/api/daily-performance")
async def api_daily() -> JSONResponse:
    """Get performance by day of week."""
    try:
        data = get_daily_performance()
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching daily performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch daily performance")


@app.get("/api/trends/{snapshot_hours}")
async def api_trends(
    snapshot_hours: int,
    days: int = Query(default=30, ge=1, le=365)
) -> JSONResponse:
    """Get engagement trends over time by post type."""
    if snapshot_hours not in [24, 72, 168]:
        raise HTTPException(status_code=400, detail="snapshot_hours must be 24, 72, or 168")
    try:
        data = get_trends_by_type(snapshot_hours, days)
        return JSONResponse(data)
    except sqlite3.Error as e:
        logger.error(f"Database error fetching trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trends")


# Mount static assets if they exist
if (WEB_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")
