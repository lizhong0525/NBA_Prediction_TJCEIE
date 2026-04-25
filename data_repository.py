# -*- coding: utf-8 -*-
"""
Shared data access helpers for the NBA prediction project.

This module keeps Flask views and the prediction engine decoupled from the
runtime database state. When SQLite tables are empty, it transparently falls
back to the cached CSV artifacts in ``output/`` so the UI can still render
meaningful results.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from config import TEAM_INFO


BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "nba.db"
TEAM_FEATURES_PATH = BASE_DIR / "output" / "team_features.csv"
TEAM_CLUSTERS_PATH = BASE_DIR / "output" / "team_clusters.csv"

TEAM_ABBR_NORMALIZE = {
    "BKN": "BRK",
    "CHA": "CHO",
    "GS": "GSW",
    "NO": "NOP",
    "NY": "NYK",
    "PHX": "PHO",
    "SA": "SAS",
    "UTAH": "UTA",
    "WSH": "WAS",
}

EASTERN_TEAMS = {
    "ATL", "BOS", "BRK", "CHI", "CHO", "CLE", "DET", "IND", "MIA", "MIL",
    "NYK", "ORL", "PHI", "TOR", "WAS",
}

TEAM_DIVISIONS = {
    "ATL": "Southeast", "CHO": "Southeast", "MIA": "Southeast",
    "ORL": "Southeast", "WAS": "Southeast",
    "BOS": "Atlantic", "BRK": "Atlantic", "NYK": "Atlantic",
    "PHI": "Atlantic", "TOR": "Atlantic",
    "CHI": "Central", "CLE": "Central", "DET": "Central",
    "IND": "Central", "MIL": "Central",
    "DAL": "Southwest", "HOU": "Southwest", "MEM": "Southwest",
    "NOP": "Southwest", "SAS": "Southwest",
    "DEN": "Northwest", "MIN": "Northwest", "OKC": "Northwest",
    "POR": "Northwest", "UTA": "Northwest",
    "GSW": "Pacific", "LAC": "Pacific", "LAL": "Pacific",
    "PHO": "Pacific", "SAC": "Pacific",
}


def normalize_team_abbr(team_abbr: str) -> str:
    """Normalize historical or external abbreviations to the app standard."""
    if not team_abbr:
        return team_abbr
    return TEAM_ABBR_NORMALIZE.get(str(team_abbr).upper(), str(team_abbr).upper())


def season_to_key(season: str) -> int:
    """Convert a season like ``2023-24`` into a sortable integer."""
    try:
        return int(str(season).split("-")[0])
    except Exception:
        return -1


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    query = """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
    """
    result = conn.execute(query, (table_name,)).fetchone()
    return result is not None


def _load_sql_table(table_name: str) -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()

    with sqlite3.connect(DB_PATH) as conn:
        if not _table_exists(conn, table_name):
            return pd.DataFrame()
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        except Exception:
            return pd.DataFrame()
    return df


def load_team_features_frame() -> pd.DataFrame:
    """Load cached team-season features from SQLite or the exported CSV."""
    df = _load_sql_table("team_features")
    if df.empty:
        df = _safe_read_csv(TEAM_FEATURES_PATH)

    if df.empty:
        return df

    df = df.copy()
    df["team_abbr"] = df["team_abbr"].map(normalize_team_abbr)
    df["season"] = df["season"].astype(str)
    df["wins"] = pd.to_numeric(df.get("wins", 0), errors="coerce").fillna(0).astype(int)
    total_games = pd.to_numeric(
        df.get("total_games", df.get("games_played", 0)),
        errors="coerce",
    ).fillna(0)
    df["total_games"] = total_games.astype(int)
    df["losses"] = (df["total_games"] - df["wins"]).clip(lower=0).astype(int)
    df["win_pct"] = pd.to_numeric(
        df.get("season_win_pct", df.get("win_pct", 0.5)),
        errors="coerce",
    ).fillna(0.5)
    df["avg_points"] = pd.to_numeric(df.get("points", 0), errors="coerce").fillna(0.0)
    df["avg_points_allowed"] = pd.to_numeric(
        df.get("opponent_points", 0), errors="coerce"
    ).fillna(0.0)
    df["avg_fg_pct"] = pd.to_numeric(df.get("fg_pct", 0), errors="coerce").fillna(0.0)
    df["avg_fg3_pct"] = pd.to_numeric(df.get("fg3_pct", 0), errors="coerce").fillna(0.0)
    df["avg_ft_pct"] = pd.to_numeric(df.get("ft_pct", 0), errors="coerce").fillna(0.0)
    df["avg_rebounds"] = pd.to_numeric(df.get("rebounds", 0), errors="coerce").fillna(0.0)
    df["avg_assists"] = pd.to_numeric(df.get("assists", 0), errors="coerce").fillna(0.0)
    df["avg_steals"] = pd.to_numeric(df.get("steals", 0), errors="coerce").fillna(0.0)
    df["avg_blocks"] = pd.to_numeric(df.get("blocks", 0), errors="coerce").fillna(0.0)
    df["avg_turnovers"] = pd.to_numeric(df.get("turnovers", 0), errors="coerce").fillna(0.0)
    df["avg_fouls"] = pd.to_numeric(df.get("fouls", 0), errors="coerce").fillna(0.0)
    df["offensive_rating"] = pd.to_numeric(
        df.get("offensive_rating", 0), errors="coerce"
    ).fillna(0.0)
    df["defensive_rating"] = pd.to_numeric(
        df.get("defensive_rating", 0), errors="coerce"
    ).fillna(0.0)
    df["net_rating"] = pd.to_numeric(df.get("net_rating", 0), errors="coerce").fillna(0.0)
    df["pace"] = pd.to_numeric(df.get("pace", 0), errors="coerce").fillna(0.0)
    df["effective_fg_pct"] = pd.to_numeric(
        df.get("effective_fg_pct", 0), errors="coerce"
    ).fillna(0.0)
    df["true_shooting_pct"] = pd.to_numeric(
        df.get("true_shooting_pct", 0), errors="coerce"
    ).fillna(0.0)
    df["recent_5_win_pct"] = pd.to_numeric(
        df.get("recent_5_win_pct", 0.5), errors="coerce"
    ).fillna(0.5)
    df["home_win_pct"] = pd.to_numeric(df.get("home_win_pct", 0.5), errors="coerce").fillna(0.5)
    df["away_win_pct"] = pd.to_numeric(df.get("away_win_pct", 0.5), errors="coerce").fillna(0.5)
    df["point_diff_avg"] = pd.to_numeric(
        df.get("point_diff_avg", df.get("point_diff", 0)),
        errors="coerce",
    ).fillna(0.0)

    df["team_name"] = df["team_abbr"].map(lambda abbr: TEAM_INFO.get(abbr, {}).get("name", abbr))
    df["city"] = df["team_abbr"].map(lambda abbr: TEAM_INFO.get(abbr, {}).get("city", abbr))
    df["team_id"] = df["team_abbr"].map(lambda abbr: TEAM_INFO.get(abbr, {}).get("id", ""))
    df["conference"] = df["team_abbr"].map(
        lambda abbr: "Eastern" if abbr in EASTERN_TEAMS else "Western"
    )
    df["division"] = df["team_abbr"].map(lambda abbr: TEAM_DIVISIONS.get(abbr, "Unknown"))
    return df


def load_team_clusters_frame() -> pd.DataFrame:
    """Load cached team cluster labels and styles."""
    df = _load_sql_table("team_clusters")
    if df.empty:
        df = _safe_read_csv(TEAM_CLUSTERS_PATH)

    if df.empty:
        return df

    df = df.copy()
    df["team_abbr"] = df["team_abbr"].map(normalize_team_abbr)
    df["season"] = df["season"].astype(str)
    return df


def load_game_logs_frame() -> pd.DataFrame:
    """Load raw game logs if they exist in SQLite."""
    df = _load_sql_table("team_game_stats")
    if df.empty:
        return df

    df = df.copy()
    df["team_abbr"] = df["team_abbr"].map(normalize_team_abbr)
    df["opponent_abbr"] = df["opponent_abbr"].map(normalize_team_abbr)
    df["game_date"] = df["game_date"].astype(str)
    return df


def get_available_seasons() -> List[str]:
    df = load_team_features_frame()
    if df.empty:
        return []
    seasons = sorted(df["season"].dropna().astype(str).unique(), key=season_to_key, reverse=True)
    return seasons


def get_latest_season(preferred: Optional[str] = None) -> Optional[str]:
    seasons = get_available_seasons()
    if not seasons:
        return None
    if preferred and preferred in seasons:
        return preferred
    return seasons[0]


def get_team_profiles(season: Optional[str] = None) -> pd.DataFrame:
    """Return the team profile table for a single season."""
    features = load_team_features_frame()
    if features.empty:
        return features

    selected_season = get_latest_season(season)
    profiles = features[features["season"] == selected_season].copy()

    clusters = load_team_clusters_frame()
    if not clusters.empty and selected_season is not None:
        clusters = clusters[clusters["season"] == selected_season][["team_abbr", "style", "cluster"]]
        profiles = profiles.merge(clusters, on="team_abbr", how="left")

    profiles = profiles.sort_values(["win_pct", "net_rating", "point_diff_avg"], ascending=False)
    profiles = profiles.reset_index(drop=True)
    return profiles


def get_team_rankings(season: Optional[str] = None) -> List[Dict]:
    profiles = get_team_profiles(season)
    if profiles.empty:
        return []
    return profiles.to_dict("records")


def get_recent_games(team_abbr: str, limit: int = 10) -> List[Dict]:
    """Return recent cached games in a UI-friendly home/away format."""
    logs = load_game_logs_frame()
    team_abbr = normalize_team_abbr(team_abbr)
    if logs.empty:
        return []

    team_logs = logs[logs["team_abbr"] == team_abbr].sort_values("game_date", ascending=False).head(limit)
    games: List[Dict] = []

    for row in team_logs.to_dict("records"):
        is_home = bool(row.get("is_home"))
        if is_home:
            home_team = row["team_abbr"]
            home_team_name = row.get("team_name") or TEAM_INFO.get(home_team, {}).get("name", home_team)
            away_team = row["opponent_abbr"]
            away_team_name = row.get("opponent_name") or TEAM_INFO.get(away_team, {}).get("name", away_team)
            home_points = row.get("points")
            away_points = row.get("opponent_points")
        else:
            away_team = row["team_abbr"]
            away_team_name = row.get("team_name") or TEAM_INFO.get(away_team, {}).get("name", away_team)
            home_team = row["opponent_abbr"]
            home_team_name = row.get("opponent_name") or TEAM_INFO.get(home_team, {}).get("name", home_team)
            away_points = row.get("points")
            home_points = row.get("opponent_points")

        games.append(
            {
                "game_id": row.get("game_id"),
                "game_date": row.get("game_date"),
                "team_abbr": team_abbr,
                "opponent_abbr": row.get("opponent_abbr"),
                "result": row.get("result"),
                "is_home": is_home,
                "home_team": home_team,
                "home_team_name": home_team_name,
                "away_team": away_team,
                "away_team_name": away_team_name,
                "home_points": home_points,
                "away_points": away_points,
                "points": row.get("points"),
                "opponent_points": row.get("opponent_points"),
                "point_diff": row.get("point_diff"),
            }
        )

    return games


def get_today_games(date_str: Optional[str] = None) -> List[Dict]:
    logs = load_game_logs_frame()
    if logs.empty:
        return []

    target_date = date_str or datetime.now().strftime("%Y-%m-%d")
    day_logs = logs[(logs["game_date"].str.startswith(target_date)) & (logs["is_home"] == 1)].copy()
    if day_logs.empty:
        return []

    records = []
    for row in day_logs.to_dict("records"):
        records.append(
            {
                "game_id": row.get("game_id"),
                "game_date": row.get("game_date"),
                "home_team": row.get("team_abbr"),
                "home_team_name": row.get("team_name") or TEAM_INFO.get(row.get("team_abbr"), {}).get("name"),
                "away_team": row.get("opponent_abbr"),
                "away_team_name": row.get("opponent_name") or TEAM_INFO.get(row.get("opponent_abbr"), {}).get("name"),
            }
        )
    return records


def get_team_detail_data(team_abbr: str, season: Optional[str] = None) -> Optional[Dict]:
    team_abbr = normalize_team_abbr(team_abbr)
    profiles = get_team_profiles(season)
    if profiles.empty:
        return None

    team_rows = profiles[profiles["team_abbr"] == team_abbr]
    if team_rows.empty:
        return None

    row = team_rows.iloc[0].to_dict()
    info = {
        **TEAM_INFO.get(team_abbr, {"id": "", "name": team_abbr, "city": team_abbr}),
        "abbr": team_abbr,
        "conference": row.get("conference", "Unknown"),
        "division": row.get("division", "Unknown"),
        "style": row.get("style"),
    }

    stats = {
        "season": row.get("season"),
        "wins": int(row.get("wins", 0)),
        "losses": int(row.get("losses", 0)),
        "win_pct": float(row.get("win_pct", 0.5)),
        "games_played": int(row.get("games_played", row.get("total_games", 0))),
        "avg_points": float(row.get("avg_points", 0.0)),
        "avg_points_allowed": float(row.get("avg_points_allowed", 0.0)),
        "avg_fg_pct": float(row.get("avg_fg_pct", 0.0)),
        "avg_fg3_pct": float(row.get("avg_fg3_pct", 0.0)),
        "avg_ft_pct": float(row.get("avg_ft_pct", 0.0)),
        "avg_rebounds": float(row.get("avg_rebounds", 0.0)),
        "avg_assists": float(row.get("avg_assists", 0.0)),
        "avg_steals": float(row.get("avg_steals", 0.0)),
        "avg_blocks": float(row.get("avg_blocks", 0.0)),
        "avg_turnovers": float(row.get("avg_turnovers", 0.0)),
        "avg_fouls": float(row.get("avg_fouls", 0.0)),
        "recent_5_win_pct": float(row.get("recent_5_win_pct", 0.5)),
        "home_win_pct": float(row.get("home_win_pct", 0.5)),
        "away_win_pct": float(row.get("away_win_pct", 0.5)),
        "offensive_rating": float(row.get("offensive_rating", 0.0)),
        "defensive_rating": float(row.get("defensive_rating", 0.0)),
        "net_rating": float(row.get("net_rating", 0.0)),
        "effective_fg_pct": float(row.get("effective_fg_pct", 0.0)),
        "true_shooting_pct": float(row.get("true_shooting_pct", 0.0)),
        "pace": float(row.get("pace", 0.0)),
        "style": row.get("style"),
    }

    return {
        "info": info,
        "stats": stats,
        "recent_games": get_recent_games(team_abbr, limit=10),
    }


def get_dataset_counts() -> Dict[str, int]:
    team_features = load_team_features_frame()
    team_clusters = load_team_clusters_frame()
    game_logs = load_game_logs_frame()
    return {
        "team_features": len(team_features),
        "team_clusters": len(team_clusters),
        "team_game_stats": len(game_logs),
        "available_seasons": len(get_available_seasons()),
    }
