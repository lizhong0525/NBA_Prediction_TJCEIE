# -*- coding: utf-8 -*-
"""
Flask routes for the NBA prediction web app.

The original routes expected fully-populated SQLite tables. The updated version
uses the shared repository layer so the UI can still work when the database is
partially empty but exported CSV artifacts are available.
"""

from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify, render_template, request

import sys

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import TEAM_INFO
from data_repository import (
    get_available_seasons,
    get_dataset_counts,
    get_latest_season,
    get_recent_games,
    get_team_detail_data,
    get_team_profiles,
    get_team_rankings,
    get_today_games,
    normalize_team_abbr,
)
from ml import (
    DEFAULT_AWAY_PARAMS,
    DEFAULT_HOME_PARAMS,
    DEFAULT_WEIGHTS,
    predict_game_advanced,
    validate_params,
    validate_weights,
)
from ml.predict import get_model_diagnostics
from utils import logger


api_bp = Blueprint("api", __name__)
page_bp = Blueprint("pages", __name__)


def _error(message: str, status_code: int = 400):
    return jsonify({"success": False, "message": message}), status_code


def _sanitize_structure(value: Any):
    if isinstance(value, dict):
        return {key: _sanitize_structure(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_structure(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _serialize_prediction(prediction: Dict[str, Any], mode: str) -> Dict[str, Any]:
    home_win_probability = prediction.get("home_win_probability")
    if home_win_probability is None:
        home_win_probability = prediction.get("home_win_prob", 0.5)

    away_win_probability = prediction.get("away_win_probability")
    if away_win_probability is None:
        away_win_probability = prediction.get("away_win_prob", 1.0 - float(home_win_probability))

    confidence_level = str(prediction.get("confidence_level") or "MEDIUM").upper()
    key_factors = prediction.get("key_factors") or []
    if not isinstance(key_factors, list):
        key_factors = []

    return {
        "prediction_id": prediction.get("prediction_id"),
        "prediction_time": prediction.get("prediction_time"),
        "season": prediction.get("season"),
        "home_team": prediction.get("home_team"),
        "home_team_name": prediction.get("home_team_name"),
        "home_team_cn": prediction.get("home_team_cn"),
        "away_team": prediction.get("away_team"),
        "away_team_name": prediction.get("away_team_name"),
        "away_team_cn": prediction.get("away_team_cn"),
        "predicted_winner": prediction.get("predicted_winner"),
        "predicted_winner_name": prediction.get("predicted_winner_name"),
        "predicted_winner_cn": prediction.get("predicted_winner_cn"),
        "home_win_probability": round(float(home_win_probability), 4),
        "away_win_probability": round(float(away_win_probability), 4),
        "home_win_prob": round(float(home_win_probability), 4),
        "away_win_prob": round(float(away_win_probability), 4),
        "predicted_margin": prediction.get("predicted_margin"),
        "margin_range": prediction.get("margin_range"),
        "confidence_level": confidence_level,
        "confidence": confidence_level.lower(),
        "key_factors": key_factors,
        "adjustments_applied": prediction.get("adjustments_applied", {}),
        "feature_importance": prediction.get("feature_importance", []),
        "model_inputs": prediction.get("model_inputs", {}),
        "head_to_head": prediction.get("head_to_head", {}),
        "home_cluster": prediction.get("home_cluster"),
        "away_cluster": prediction.get("away_cluster"),
        "mode": mode,
    }


def _persist_prediction(prediction: Dict[str, Any], mode: str):
    try:
        current_app.db.insert_prediction(
            {
                "prediction_id": prediction.get("prediction_id"),
                "game_id": prediction.get("game_id"),
                "home_team": prediction.get("home_team"),
                "away_team": prediction.get("away_team"),
                "predicted_winner": prediction.get("predicted_winner"),
                "home_win_probability": prediction.get("home_win_probability"),
                "confidence_level": prediction.get("confidence_level"),
                "key_factors": prediction.get("key_factors", []),
                "model_version": f"web-{mode}-v2",
            }
        )
    except Exception as exc:
        logger.warning("Failed to persist prediction: %s", exc)


def _get_selected_season(requested: str = None) -> str | None:
    return get_latest_season(requested)


def _build_team_rows(season: str | None) -> List[Dict[str, Any]]:
    teams = get_team_rankings(season)
    for index, team in enumerate(teams, start=1):
        team["rank"] = index
        team["conference_cn"] = "东部" if team.get("conference") == "Eastern" else "西部"
    return teams


@api_bp.route("/home", methods=["GET"])
def get_home_data():
    try:
        requested_season = request.args.get("season")
        date_str = request.args.get("date")
        season = _get_selected_season(requested_season)
        teams = _build_team_rows(season)
        diagnostics = get_model_diagnostics(season)
        accuracy = current_app.db.get_prediction_accuracy()
        recent_predictions = current_app.db.get_recent_predictions(limit=5)
        today_games = get_today_games(date_str)

        conference_summary: List[Dict[str, Any]] = []
        if teams:
            profiles = get_team_profiles(season)
            grouped = (
                profiles.groupby("conference", dropna=False)["win_pct"]
                .agg(["mean", "count"])
                .reset_index()
            )
            for row in grouped.to_dict("records"):
                conference_summary.append(
                    {
                        "conference": row.get("conference") or "Unknown",
                        "average_win_pct": round(float(row.get("mean") or 0.0), 4),
                        "teams": int(row.get("count") or 0),
                    }
                )

        return jsonify(
            {
                "success": True,
                "data": _sanitize_structure({
                    "season": season,
                    "available_seasons": get_available_seasons(),
                    "today_games": today_games,
                    "recent_predictions": recent_predictions,
                    "model_accuracy": diagnostics.get("pairwise_accuracy", 0.0),
                    "total_predictions": accuracy.get("total", 0),
                    "evaluated_predictions": accuracy.get("evaluated", 0),
                    "average_confidence": accuracy.get("avg_confidence", 0.0),
                    "top_teams": teams[:10],
                    "conference_summary": conference_summary,
                    "diagnostics": diagnostics,
                }),
            }
        )
    except Exception as exc:
        logger.error("Failed to load home data: %s", exc)
        return _error(str(exc), 500)


@api_bp.route("/seasons", methods=["GET"])
def get_seasons():
    seasons = get_available_seasons()
    return jsonify(
        {
            "success": True,
            "data": seasons,
            "latest_season": seasons[0] if seasons else None,
        }
    )


@api_bp.route("/teams", methods=["GET"])
def get_teams():
    try:
        requested_season = request.args.get("season")
        conference = (request.args.get("conference") or "").strip().lower()
        season = _get_selected_season(requested_season)
        teams = _build_team_rows(season)

        if conference in {"eastern", "western"}:
            teams = [team for team in teams if str(team.get("conference", "")).lower() == conference]

        return jsonify(
            {
                "success": True,
                "season": season,
                "available_seasons": get_available_seasons(),
                "data": _sanitize_structure(teams),
            }
        )
    except Exception as exc:
        logger.error("Failed to load teams: %s", exc)
        return _error(str(exc), 500)


@api_bp.route("/team/<team_abbr>", methods=["GET"])
def get_team_detail(team_abbr):
    try:
        season = _get_selected_season(request.args.get("season"))
        team_abbr = normalize_team_abbr(team_abbr)

        if team_abbr not in TEAM_INFO:
            return _error(f"Unknown team: {team_abbr}", 404)

        team_data = get_team_detail_data(team_abbr, season)
        if not team_data:
            return _error(f"No data available for {team_abbr}", 404)

        team_data["season"] = season
        team_data["available_seasons"] = get_available_seasons()
        return jsonify({"success": True, "data": _sanitize_structure(team_data)})
    except Exception as exc:
        logger.error("Failed to load team detail for %s: %s", team_abbr, exc)
        return _error(str(exc), 500)


@api_bp.route("/predict", methods=["POST"])
def api_predict_game():
    try:
        data = request.get_json(silent=True) or {}
        home_team = normalize_team_abbr(data.get("home_team", ""))
        away_team = normalize_team_abbr(data.get("away_team", ""))

        if not home_team or not away_team:
            return _error("Missing home_team or away_team")
        if home_team == away_team:
            return _error("Home and away teams must be different")
        if home_team not in TEAM_INFO or away_team not in TEAM_INFO:
            return _error("One or both team abbreviations are invalid")

        mode = str(data.get("mode") or "simple").lower()
        season = _get_selected_season(data.get("season"))
        home_params = data.get("home_params") if mode == "advanced" else None
        away_params = data.get("away_params") if mode == "advanced" else None
        weights = data.get("weights") if mode == "advanced" else None

        if home_params:
            valid, message = validate_params(home_params, "home")
            if not valid:
                return _error(f"Invalid home_params: {message}")
        if away_params:
            valid, message = validate_params(away_params, "away")
            if not valid:
                return _error(f"Invalid away_params: {message}")
        if weights:
            valid, message = validate_weights(weights)
            if not valid:
                return _error(f"Invalid weights: {message}")

        prediction = predict_game_advanced(
            home_team=home_team,
            away_team=away_team,
            home_params=home_params,
            away_params=away_params,
            weights=weights,
            season=season,
            use_recent_form=True,
            return_details=True,
        )

        serialized = _serialize_prediction(prediction, mode)
        _persist_prediction(serialized, mode)

        return jsonify({"success": True, "data": _sanitize_structure(serialized), "mode": mode})
    except ValueError as exc:
        logger.warning("Prediction validation failed: %s", exc)
        return _error(str(exc))
    except Exception as exc:
        logger.error("Prediction failed: %s", exc)
        return _error(str(exc), 500)


@api_bp.route("/predict/validate", methods=["POST"])
def validate_prediction_payload():
    try:
        data = request.get_json(silent=True) or {}
        errors: List[str] = []

        if data.get("home_params"):
            valid, message = validate_params(data["home_params"], "home")
            if not valid:
                errors.append(f"home_params: {message}")

        if data.get("away_params"):
            valid, message = validate_params(data["away_params"], "away")
            if not valid:
                errors.append(f"away_params: {message}")

        if data.get("weights"):
            valid, message = validate_weights(data["weights"])
            if not valid:
                errors.append(f"weights: {message}")

        if errors:
            return jsonify({"success": False, "message": "Validation failed", "errors": errors}), 400

        return jsonify(
            {
                "success": True,
                "message": "Validation passed",
                "defaults": {
                    "weights": DEFAULT_WEIGHTS,
                    "home_params": DEFAULT_HOME_PARAMS,
                    "away_params": DEFAULT_AWAY_PARAMS,
                },
            }
        )
    except Exception as exc:
        logger.error("Failed to validate prediction params: %s", exc)
        return _error(str(exc), 500)


@api_bp.route("/predict/params", methods=["GET"])
def get_prediction_params():
    return jsonify(
        {
            "success": True,
            "data": {
                "default_weights": DEFAULT_WEIGHTS,
                "default_home_params": DEFAULT_HOME_PARAMS,
                "default_away_params": DEFAULT_AWAY_PARAMS,
                "available_seasons": get_available_seasons(),
                "weights_description": {
                    "recent_form": "近期状态权重",
                    "home_advantage": "主客场差异权重",
                    "historical_matchup": "历史交锋权重",
                    "efficiency_diff": "效率指标权重",
                    "cluster_similarity": "球队风格相似度权重",
                },
                "params_description": {
                    "recent_win_pct": "手动覆盖近期胜率",
                    "home_advantage": "附加主场修正",
                    "injury_impact": "伤病影响，范围 -0.35 到 0",
                    "rest_days": "休息天数",
                    "back_to_back": "是否背靠背",
                    "key_player_out": "缺阵核心球员",
                    "morale_boost": "士气加成",
                    "custom_rating": "自定义球队评分",
                },
            },
        }
    )


@api_bp.route("/predictions/history", methods=["GET"])
def get_prediction_history():
    try:
        limit = request.args.get("limit", 20, type=int)
        predictions = current_app.db.get_recent_predictions(limit=limit)
        accuracy = current_app.db.get_prediction_accuracy()

        return jsonify(
            {
                "success": True,
                "data": {
                    "predictions": _sanitize_structure(predictions),
                    "total": accuracy.get("total", 0),
                    "evaluated": accuracy.get("evaluated", 0),
                    "correct": accuracy.get("correct", 0),
                    "accuracy": accuracy.get("accuracy", 0.0),
                    "avg_confidence": accuracy.get("avg_confidence", 0.0),
                },
            }
        )
    except Exception as exc:
        logger.error("Failed to load prediction history: %s", exc)
        return _error(str(exc), 500)


@api_bp.route("/games", methods=["GET"])
def get_games():
    try:
        team_abbr = request.args.get("team")
        date_str = request.args.get("date")
        limit = request.args.get("limit", 20, type=int)

        if team_abbr:
            games = get_recent_games(normalize_team_abbr(team_abbr), limit=limit)
        else:
            games = get_today_games(date_str)

        return jsonify({"success": True, "data": _sanitize_structure(games)})
    except Exception as exc:
        logger.error("Failed to load games: %s", exc)
        return _error(str(exc), 500)


@api_bp.route("/stats/ranking", methods=["GET"])
def get_stats_ranking():
    try:
        requested_type = request.args.get("type", "win_pct")
        season = _get_selected_season(request.args.get("season"))
        profiles = get_team_profiles(season)
        if profiles.empty:
            return jsonify({"success": True, "data": []})

        field_map = {
            "win_pct": "win_pct",
            "avg_points": "avg_points",
            "avg_rebounds": "avg_rebounds",
            "avg_assists": "avg_assists",
            "offense": "offensive_rating",
            "offensive_rating": "offensive_rating",
            "defense": "defensive_rating",
            "defensive_rating": "defensive_rating",
            "net_rating": "net_rating",
            "pace": "pace",
            "recent_5_win_pct": "recent_5_win_pct",
            "true_shooting_pct": "true_shooting_pct",
            "effective_fg_pct": "effective_fg_pct",
        }
        stat_field = field_map.get(requested_type, requested_type)
        if stat_field not in profiles.columns:
            return _error(f"Unsupported ranking field: {requested_type}")

        ascending = stat_field == "defensive_rating"
        ranked = profiles.sort_values(stat_field, ascending=ascending).reset_index(drop=True)
        data = []
        for index, row in enumerate(ranked.to_dict("records"), start=1):
            data.append(
                {
                    "rank": index,
                    "team_abbr": row.get("team_abbr"),
                    "team_name": row.get("team_name"),
                    "season": row.get("season"),
                    "stat_type": stat_field,
                    "stat_value": round(float(row.get(stat_field) or 0.0), 4),
                }
            )

        return jsonify({"success": True, "season": season, "data": _sanitize_structure(data)})
    except Exception as exc:
        logger.error("Failed to load ranking data: %s", exc)
        return _error(str(exc), 500)


@api_bp.route("/health", methods=["GET"])
def health_check():
    try:
        return jsonify(
            {
                "success": True,
                "status": "healthy",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "dataset_counts": _sanitize_structure(get_dataset_counts()),
                "database_tables": _sanitize_structure(current_app.db.get_table_stats()),
                "available_seasons": get_available_seasons(),
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "status": "unhealthy", "error": str(exc)}), 500


@page_bp.route("/")
def index():
    return render_template("index.html")


@page_bp.route("/predict")
def predict_page():
    return render_template("predict.html")


@page_bp.route("/team/<team_abbr>")
def team_page(team_abbr):
    return render_template("team.html", team_abbr=normalize_team_abbr(team_abbr))


@page_bp.route("/data")
def data_page():
    return render_template("data.html")


@page_bp.route("/about")
def about_page():
    return render_template("about.html")
