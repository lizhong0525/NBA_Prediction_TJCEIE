# -*- coding: utf-8 -*-
"""
SQLite database helpers for the NBA prediction project.

The original project stores crawled data, season summaries, clustering output
and prediction history in a single local database. This module keeps that API
stable while making prediction persistence tolerant of the newer web payloads.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

from config import DATABASE_CONFIG
from utils import logger, log_function_call


class DatabaseManager:
    """Thin SQLite wrapper used by the Flask app and utility scripts."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(DATABASE_CONFIG["path"])

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection: Optional[sqlite3.Connection] = None
        logger.info("DatabaseManager initialized at %s", self.db_path)

    def connect(self):
        if self.connection is None:
            self.connection = sqlite3.connect(
                self.db_path,
                timeout=DATABASE_CONFIG.get("timeout", 30),
                check_same_thread=DATABASE_CONFIG.get("check_same_thread", False),
            )
            self.connection.execute("PRAGMA foreign_keys = ON")
            logger.info("Database connection established")

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")

    @contextmanager
    def get_cursor(self):
        if self.connection is None:
            self.connect()

        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception as exc:
            self.connection.rollback()
            logger.error("Database operation failed: %s", exc)
            raise
        finally:
            cursor.close()

    @log_function_call
    def create_tables(self):
        self.connect()
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS team_game_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id VARCHAR(30) UNIQUE NOT NULL,
                    game_date DATE NOT NULL,
                    season VARCHAR(10) NOT NULL,
                    team_id VARCHAR(20) NOT NULL,
                    team_abbr VARCHAR(10) NOT NULL,
                    team_name VARCHAR(100),
                    opponent_id VARCHAR(20) NOT NULL,
                    opponent_abbr VARCHAR(10) NOT NULL,
                    opponent_name VARCHAR(100),
                    is_home BOOLEAN DEFAULT 0,
                    result VARCHAR(1),
                    points INTEGER,
                    opponent_points INTEGER,
                    point_diff INTEGER,
                    fg_made INTEGER,
                    fg_attempts INTEGER,
                    fg_pct REAL,
                    fg3_made INTEGER,
                    fg3_attempts INTEGER,
                    fg3_pct REAL,
                    ft_made INTEGER,
                    ft_attempts INTEGER,
                    ft_pct REAL,
                    rebounds INTEGER,
                    assists INTEGER,
                    steals INTEGER,
                    blocks INTEGER,
                    turnovers INTEGER,
                    fouls INTEGER,
                    plus_minus INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_game_date ON team_game_stats(game_date)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_team_season ON team_game_stats(team_abbr, season)"
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS team_season_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id VARCHAR(20) NOT NULL,
                    team_abbr VARCHAR(10) NOT NULL,
                    team_name VARCHAR(100),
                    season VARCHAR(10) NOT NULL,
                    games_played INTEGER,
                    wins INTEGER,
                    losses INTEGER,
                    win_pct REAL,
                    avg_points REAL,
                    avg_points_allowed REAL,
                    avg_fg_pct REAL,
                    avg_fg3_pct REAL,
                    avg_ft_pct REAL,
                    avg_rebounds REAL,
                    avg_assists REAL,
                    avg_steals REAL,
                    avg_blocks REAL,
                    avg_turnovers REAL,
                    avg_fouls REAL,
                    home_wins INTEGER,
                    home_losses INTEGER,
                    home_win_pct REAL,
                    away_wins INTEGER,
                    away_games INTEGER,
                    away_win_pct REAL,
                    point_diff REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(team_id, season)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS player_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id VARCHAR(30) UNIQUE,
                    player_name VARCHAR(100) NOT NULL,
                    team_id VARCHAR(20),
                    team_abbr VARCHAR(10),
                    season VARCHAR(10) NOT NULL,
                    position VARCHAR(10),
                    games_played INTEGER,
                    games_started INTEGER,
                    minutes REAL,
                    points REAL,
                    rebounds REAL,
                    assists REAL,
                    steals REAL,
                    blocks REAL,
                    fg_pct REAL,
                    fg3_pct REAL,
                    ft_pct REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS prediction_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_id VARCHAR(30) UNIQUE NOT NULL,
                    game_id VARCHAR(30),
                    home_team VARCHAR(100) NOT NULL,
                    away_team VARCHAR(100) NOT NULL,
                    predicted_winner VARCHAR(100),
                    win_probability REAL,
                    confidence_level VARCHAR(20),
                    key_factors TEXT,
                    model_version VARCHAR(20),
                    actual_result VARCHAR(1),
                    is_correct BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS team_clusters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id VARCHAR(20) NOT NULL,
                    team_abbr VARCHAR(10) NOT NULL,
                    team_name VARCHAR(100),
                    season VARCHAR(10) NOT NULL,
                    cluster_label INTEGER,
                    cluster_name VARCHAR(50),
                    cluster_features TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(team_id, season)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type VARCHAR(50) NOT NULL,
                    target VARCHAR(100),
                    status VARCHAR(20),
                    records_fetched INTEGER DEFAULT 0,
                    error_message TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        logger.info("Database tables created")

    @log_function_call
    def insert_game_data(self, games: List[Dict[str, Any]]) -> int:
        if not games:
            return 0

        self.connect()
        insert_sql = """
            INSERT OR REPLACE INTO team_game_stats
            (game_id, game_date, season, team_id, team_abbr, team_name,
             opponent_id, opponent_abbr, opponent_name, is_home, result,
             points, opponent_points, point_diff, fg_made, fg_attempts, fg_pct,
             fg3_made, fg3_attempts, fg3_pct, ft_made, ft_attempts, ft_pct,
             rebounds, assists, steals, blocks, turnovers, fouls)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        count = 0
        with self.get_cursor() as cursor:
            for game in games:
                cursor.execute(
                    insert_sql,
                    (
                        game.get("game_id", ""),
                        game.get("game_date", ""),
                        game.get("season", ""),
                        game.get("team_id", ""),
                        game.get("team_abbr", ""),
                        game.get("team_name", ""),
                        game.get("opponent_id", ""),
                        game.get("opponent_abbr", ""),
                        game.get("opponent_name", ""),
                        int(game.get("is_home", False)),
                        game.get("result", ""),
                        game.get("points", 0),
                        game.get("opponent_points", 0),
                        game.get("point_diff", 0),
                        game.get("fg_made", 0),
                        game.get("fg_attempts", 0),
                        game.get("fg_pct", 0),
                        game.get("fg3_made", 0),
                        game.get("fg3_attempts", 0),
                        game.get("fg3_pct", 0),
                        game.get("ft_made", 0),
                        game.get("ft_attempts", 0),
                        game.get("ft_pct", 0),
                        game.get("rebounds", 0),
                        game.get("assists", 0),
                        game.get("steals", 0),
                        game.get("blocks", 0),
                        game.get("turnovers", 0),
                        game.get("fouls", 0),
                    ),
                )
                count += 1
        logger.info("Inserted %s game records", count)
        return count

    @log_function_call
    def insert_season_stats(self, stats: List[Dict[str, Any]]) -> int:
        if not stats:
            return 0

        self.connect()
        insert_sql = """
            INSERT OR REPLACE INTO team_season_stats
            (team_id, team_abbr, team_name, season, games_played, wins, losses,
             win_pct, avg_points, avg_points_allowed, avg_fg_pct, avg_fg3_pct,
             avg_ft_pct, avg_rebounds, avg_assists, avg_steals, avg_blocks,
             avg_turnovers, avg_fouls, home_wins, home_losses, home_win_pct,
             away_wins, away_games, away_win_pct, point_diff)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        count = 0
        with self.get_cursor() as cursor:
            for stat in stats:
                cursor.execute(
                    insert_sql,
                    (
                        stat.get("team_id", ""),
                        stat.get("team_abbr", ""),
                        stat.get("team_name", ""),
                        stat.get("season", ""),
                        stat.get("games_played", 0),
                        stat.get("wins", 0),
                        stat.get("losses", 0),
                        stat.get("win_pct", 0),
                        stat.get("avg_points", 0),
                        stat.get("avg_points_allowed", 0),
                        stat.get("avg_fg_pct", 0),
                        stat.get("avg_fg3_pct", 0),
                        stat.get("avg_ft_pct", 0),
                        stat.get("avg_rebounds", 0),
                        stat.get("avg_assists", 0),
                        stat.get("avg_steals", 0),
                        stat.get("avg_blocks", 0),
                        stat.get("avg_turnovers", 0),
                        stat.get("avg_fouls", 0),
                        stat.get("home_wins", 0),
                        stat.get("home_losses", 0),
                        stat.get("home_win_pct", 0),
                        stat.get("away_wins", 0),
                        stat.get("away_games", 0),
                        stat.get("away_win_pct", 0),
                        stat.get("point_diff", 0),
                    ),
                )
                count += 1
        logger.info("Inserted %s season stat records", count)
        return count

    @log_function_call
    def insert_prediction(self, prediction: Dict[str, Any]) -> bool:
        self.connect()

        insert_sql = """
            INSERT OR REPLACE INTO prediction_results
            (prediction_id, game_id, home_team, away_team, predicted_winner,
             win_probability, confidence_level, key_factors, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        win_probability = prediction.get("win_probability")
        if win_probability is None:
            win_probability = prediction.get("home_win_probability")
        if win_probability is None:
            win_probability = prediction.get("home_win_prob", 0.5)
        win_probability = float(win_probability)

        confidence_level = (
            prediction.get("confidence_level")
            or prediction.get("confidence")
            or "MEDIUM"
        )
        confidence_level = str(confidence_level).upper()

        key_factors = prediction.get("key_factors", [])
        if not isinstance(key_factors, str):
            key_factors = json.dumps(key_factors, ensure_ascii=False)

        model_version = (
            prediction.get("model_version")
            or prediction.get("mode")
            or "2.0"
        )

        with self.get_cursor() as cursor:
            cursor.execute(
                insert_sql,
                (
                    prediction.get("prediction_id", ""),
                    prediction.get("game_id", ""),
                    prediction.get("home_team", ""),
                    prediction.get("away_team", ""),
                    prediction.get("predicted_winner", ""),
                    win_probability,
                    confidence_level,
                    key_factors,
                    str(model_version),
                ),
            )

        return True

    def get_game_data(
        self,
        team_abbr: str = None,
        season: str = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        self.connect()
        query = "SELECT * FROM team_game_stats WHERE 1=1"
        params: List[Any] = []

        if team_abbr:
            query += " AND (team_abbr = ? OR opponent_abbr = ?)"
            params.extend([team_abbr, team_abbr])
        if season:
            query += " AND season = ?"
            params.append(season)

        query += " ORDER BY game_date DESC LIMIT ?"
        params.append(limit)
        return pd.read_sql_query(query, self.connection, params=params)

    def get_team_season_stats(
        self,
        team_abbr: str = None,
        season: str = None,
    ) -> pd.DataFrame:
        self.connect()
        query = "SELECT * FROM team_season_stats WHERE 1=1"
        params: List[Any] = []

        if team_abbr:
            query += " AND team_abbr = ?"
            params.append(team_abbr)
        if season:
            query += " AND season = ?"
            params.append(season)

        query += " ORDER BY win_pct DESC"
        return pd.read_sql_query(query, self.connection, params=params)

    def get_recent_predictions(self, limit: int = 10) -> List[Dict[str, Any]]:
        self.connect()
        df = pd.read_sql_query(
            """
            SELECT *
            FROM prediction_results
            ORDER BY created_at DESC
            LIMIT ?
            """,
            self.connection,
            params=[limit],
        )
        if df.empty:
            return []

        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        df["created_at"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")

        results: List[Dict[str, Any]] = []
        for row in df.to_dict("records"):
            key_factors = row.get("key_factors") or "[]"
            if isinstance(key_factors, str):
                try:
                    key_factors = json.loads(key_factors)
                except json.JSONDecodeError:
                    key_factors = []

            home_win_prob = float(row.get("win_probability") or 0.5)
            home_win_prob = min(max(home_win_prob, 0.0), 1.0)
            confidence_level = str(row.get("confidence_level") or "MEDIUM").upper()

            results.append(
                {
                    "prediction_id": row.get("prediction_id"),
                    "game_id": row.get("game_id"),
                    "home_team": row.get("home_team"),
                    "away_team": row.get("away_team"),
                    "predicted_winner": row.get("predicted_winner"),
                    "home_win_prob": round(home_win_prob, 4),
                    "away_win_prob": round(1.0 - home_win_prob, 4),
                    "home_win_probability": round(home_win_prob, 4),
                    "away_win_probability": round(1.0 - home_win_prob, 4),
                    "confidence_level": confidence_level,
                    "confidence": confidence_level.lower(),
                    "key_factors": key_factors,
                    "model_version": row.get("model_version"),
                    "actual_result": row.get("actual_result"),
                    "is_correct": row.get("is_correct"),
                    "prediction_time": row.get("created_at"),
                    "created_at": row.get("created_at"),
                }
            )

        return results

    def get_prediction_accuracy(self) -> Dict[str, Any]:
        self.connect()
        df = pd.read_sql_query(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_correct IS NOT NULL THEN 1 ELSE 0 END) as evaluated,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
                AVG(
                    CASE
                        WHEN is_correct IS NOT NULL THEN
                            CASE WHEN is_correct = 1 THEN 1.0 ELSE 0.0 END
                        ELSE NULL
                    END
                ) as accuracy,
                AVG(
                    CASE
                        WHEN win_probability IS NOT NULL THEN
                            CASE
                                WHEN win_probability >= 0.5 THEN win_probability
                                ELSE 1.0 - win_probability
                            END
                        ELSE NULL
                    END
                ) as avg_confidence
            FROM prediction_results
            """,
            self.connection,
        )

        if df.empty:
            return {
                "total": 0,
                "evaluated": 0,
                "correct": 0,
                "accuracy": 0.0,
                "avg_confidence": 0.0,
            }

        row = df.iloc[0].to_dict()
        return {
            "total": int(row.get("total") or 0),
            "evaluated": int(row.get("evaluated") or 0),
            "correct": int(row.get("correct") or 0),
            "accuracy": float(row.get("accuracy") or 0.0),
            "avg_confidence": float(row.get("avg_confidence") or 0.0),
        }

    def update_prediction_result(self, prediction_id: str, actual_result: str) -> bool:
        self.connect()
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE prediction_results
                SET actual_result = ?,
                    is_correct = CASE
                        WHEN predicted_winner = ? THEN 1
                        ELSE 0
                    END
                WHERE prediction_id = ?
                """,
                (actual_result, actual_result, prediction_id),
            )
        return True

    def execute_query(self, query: str, params: tuple = None) -> List[tuple]:
        self.connect()
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()

    def get_table_stats(self) -> Dict[str, int]:
        self.connect()
        tables = [
            "team_game_stats",
            "team_season_stats",
            "player_stats",
            "prediction_results",
            "team_clusters",
        ]
        stats: Dict[str, int] = {}
        with self.get_cursor() as cursor:
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = int(cursor.fetchone()[0])
        return stats


def init_database(db_path: str = None) -> DatabaseManager:
    db = DatabaseManager(db_path)
    db.create_tables()
    logger.info("Database initialized")
    return db


if __name__ == "__main__":
    db = init_database()
    print(db.get_table_stats())
    db.close()
