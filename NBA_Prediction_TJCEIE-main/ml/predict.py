# -*- coding: utf-8 -*-
"""
Prediction engine for the NBA project.

The original project mixed empty-database fallbacks, hand-tuned weights and
UI-unfriendly payloads, which made predictions unstable and difficult to render
outside the console. This module replaces that flow with:

1. Cached data loading from SQLite or ``output/*.csv``.
2. A light-weight ridge model that estimates team strength from season features.
3. Pairwise probability calibration built from historical season matchups.
4. Normalized advanced weights so parameter tweaks stay bounded.
5. UI-friendly result payloads including probability, margin and factor impact.
"""

from __future__ import annotations

from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import TEAM_INFO
from data_repository import (
    get_latest_season,
    load_game_logs_frame,
    load_team_clusters_frame,
    load_team_features_frame,
    normalize_team_abbr,
    season_to_key,
)


OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

TEAM_NAMES_CN = {
    "ATL": "老鹰",
    "BOS": "凯尔特人",
    "BRK": "篮网",
    "CHI": "公牛",
    "CHO": "黄蜂",
    "CLE": "骑士",
    "DAL": "独行侠",
    "DEN": "掘金",
    "DET": "活塞",
    "GSW": "勇士",
    "HOU": "火箭",
    "IND": "步行者",
    "LAC": "快船",
    "LAL": "湖人",
    "MEM": "灰熊",
    "MIA": "热火",
    "MIL": "雄鹿",
    "MIN": "森林狼",
    "NOP": "鹈鹕",
    "NYK": "尼克斯",
    "OKC": "雷霆",
    "ORL": "魔术",
    "PHI": "76人",
    "PHO": "太阳",
    "POR": "开拓者",
    "SAC": "国王",
    "SAS": "马刺",
    "TOR": "猛龙",
    "UTA": "爵士",
    "WAS": "奇才",
}

MODEL_FEATURES = [
    "avg_points",
    "avg_points_allowed",
    "point_diff_avg",
    "recent_5_win_pct",
    "home_win_pct",
    "away_win_pct",
    "offensive_rating",
    "defensive_rating",
    "net_rating",
    "effective_fg_pct",
    "true_shooting_pct",
    "avg_assists",
    "avg_rebounds",
    "pace",
]

DEFAULT_WEIGHTS = {
    "recent_form": 0.22,
    "home_advantage": 0.18,
    "historical_matchup": 0.12,
    "efficiency_diff": 0.36,
    "cluster_similarity": 0.12,
}

DEFAULT_HOME_PARAMS = {
    "recent_win_pct": None,
    "home_advantage": 0.03,
    "injury_impact": 0.0,
    "rest_days": 2,
    "back_to_back": False,
    "key_player_out": [],
    "morale_boost": 0.0,
    "custom_rating": None,
}

DEFAULT_AWAY_PARAMS = {
    "recent_win_pct": None,
    "home_advantage": 0.0,
    "injury_impact": 0.0,
    "rest_days": 2,
    "back_to_back": False,
    "key_player_out": [],
    "morale_boost": 0.0,
    "custom_rating": None,
}


def normalize_team(team_abbr: str) -> str:
    """Normalize external abbreviations to the internal standard."""
    return normalize_team_abbr(team_abbr)


def _sigmoid(values: np.ndarray | float) -> np.ndarray | float:
    clipped = np.clip(values, -35, 35)
    return 1.0 / (1.0 + np.exp(-clipped))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _normalize_weights(weights: Optional[Dict[str, float]]) -> Dict[str, float]:
    merged = {**DEFAULT_WEIGHTS, **(weights or {})}
    cleaned = {
        key: max(_safe_float(value, DEFAULT_WEIGHTS[key]), 0.0)
        for key, value in merged.items()
    }
    total = sum(cleaned.values()) or 1.0
    return {key: value / total for key, value in cleaned.items()}


def _join_feature_styles(
    team_features: pd.DataFrame,
    team_clusters: pd.DataFrame,
) -> pd.DataFrame:
    if team_features.empty:
        return team_features

    features = team_features.copy()
    if team_clusters.empty:
        if "style" not in features.columns:
            features["style"] = None
        return features

    cluster_cols = [col for col in ("team_abbr", "season", "style", "cluster") if col in team_clusters.columns]
    merged = features.merge(team_clusters[cluster_cols], on=["team_abbr", "season"], how="left")
    return merged


def load_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load features, clusters and game logs with CSV fallbacks."""
    team_features = load_team_features_frame()
    team_clusters = load_team_clusters_frame()
    games = load_game_logs_frame()
    team_features = _join_feature_styles(team_features, team_clusters)
    return team_features, team_clusters, games


def get_team_latest_stats(
    team_abbr: str,
    team_features: pd.DataFrame,
    season: Optional[str] = None,
) -> Dict[str, Any]:
    team_abbr = normalize_team(team_abbr)
    if team_features.empty:
        return {}

    team_rows = team_features[team_features["team_abbr"] == team_abbr].copy()
    if team_rows.empty:
        return {}

    if season:
        preferred = team_rows[team_rows["season"] == season]
        if not preferred.empty:
            team_rows = preferred

    team_rows = team_rows.sort_values("season", key=lambda s: s.map(season_to_key), ascending=False)
    return team_rows.iloc[0].to_dict()


def get_team_cluster(
    team_abbr: str,
    team_clusters: pd.DataFrame,
    season: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    team_abbr = normalize_team(team_abbr)
    if team_clusters.empty:
        return None

    rows = team_clusters[team_clusters["team_abbr"] == team_abbr].copy()
    if rows.empty:
        return None

    if season:
        preferred = rows[rows["season"] == season]
        if not preferred.empty:
            rows = preferred

    rows = rows.sort_values("season", key=lambda s: s.map(season_to_key), ascending=False)
    return rows.iloc[0].to_dict()


def get_head_to_head(
    home_team: str,
    away_team: str,
    games: pd.DataFrame,
    max_games: int = 12,
) -> Dict[str, Any]:
    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)

    if games.empty:
        return {"total": 0, "home_wins": 0, "away_wins": 0, "home_win_pct": 0.5, "recent_results": []}

    h2h = games[
        ((games["team_abbr"] == home_team) & (games["opponent_abbr"] == away_team))
        | ((games["team_abbr"] == away_team) & (games["opponent_abbr"] == home_team))
    ].sort_values("game_date", ascending=False).head(max_games)

    if h2h.empty:
        return {"total": 0, "home_wins": 0, "away_wins": 0, "home_win_pct": 0.5, "recent_results": []}

    home_wins = len(h2h[(h2h["team_abbr"] == home_team) & (h2h["result"] == "W")])
    away_wins = len(h2h[(h2h["team_abbr"] == away_team) & (h2h["result"] == "W")])

    recent_results = []
    for row in h2h.to_dict("records"):
        is_home_row = bool(row.get("is_home"))
        if row["team_abbr"] == home_team:
            home_points = row.get("points") if is_home_row else row.get("opponent_points")
            away_points = row.get("opponent_points") if is_home_row else row.get("points")
        else:
            home_points = row.get("opponent_points") if is_home_row else row.get("points")
            away_points = row.get("points") if is_home_row else row.get("opponent_points")
        recent_results.append(
            {
                "game_date": row.get("game_date"),
                "home_team": home_team,
                "away_team": away_team,
                "home_points": home_points,
                "away_points": away_points,
                "winner": home_team if (home_points or 0) > (away_points or 0) else away_team,
            }
        )

    return {
        "total": int(len(h2h)),
        "home_wins": int(home_wins),
        "away_wins": int(away_wins),
        "home_win_pct": float(home_wins / len(h2h)) if len(h2h) else 0.5,
        "recent_results": recent_results,
    }


def _default_team_row(team_features: pd.DataFrame) -> Dict[str, Any]:
    if team_features.empty:
        return {
            "win_pct": 0.5,
            "recent_5_win_pct": 0.5,
            "home_win_pct": 0.55,
            "away_win_pct": 0.45,
            "avg_points": 110.0,
            "avg_points_allowed": 110.0,
            "avg_assists": 25.0,
            "avg_rebounds": 44.0,
            "offensive_rating": 112.0,
            "defensive_rating": 112.0,
            "net_rating": 0.0,
            "effective_fg_pct": 0.53,
            "true_shooting_pct": 0.57,
            "point_diff_avg": 0.0,
            "pace": 100.0,
            "style": None,
        }

    medians = team_features[MODEL_FEATURES].median(numeric_only=True).to_dict()
    medians.update(
        {
            "win_pct": float(team_features["win_pct"].median()),
            "style": None,
        }
    )
    return medians


def _prepare_training_frame(team_features: pd.DataFrame, season: Optional[str]) -> pd.DataFrame:
    if team_features.empty:
        return team_features

    df = team_features.copy()
    df["season_key"] = df["season"].map(season_to_key)

    if season:
        target_key = season_to_key(season)
        historical = df[df["season_key"] < target_key].copy()
        if len(historical) >= 45:
            return historical

    if len(df) > 45:
        latest_key = df["season_key"].max()
        historical = df[df["season_key"] < latest_key].copy()
        if len(historical) >= 45:
            return historical

    return df


def _fit_ridge_regression(X: np.ndarray, y: np.ndarray, alpha: float = 1.5) -> Tuple[np.ndarray, float]:
    design = np.column_stack([np.ones(len(X)), X])
    ridge = alpha * np.eye(design.shape[1])
    ridge[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + ridge, design.T @ y)
    intercept = float(coefficients[0])
    beta = coefficients[1:]
    return beta, intercept


def _fit_logistic_calibration(edges: np.ndarray, labels: np.ndarray) -> Tuple[float, float]:
    if len(edges) == 0:
        return 0.0, 6.5

    X = np.column_stack([np.ones(len(edges)), edges])
    params = np.array([0.0, 6.0], dtype=float)
    regularization = np.diag([0.0, 0.05])

    for _ in range(20):
        logits = X @ params
        probs = _sigmoid(logits)
        weights = np.clip(probs * (1.0 - probs), 1e-5, None)
        gradient = (X.T @ (probs - labels)) / len(edges) + regularization @ params
        hessian = (X.T * weights) @ X / len(edges) + regularization
        step = np.linalg.solve(hessian, gradient)
        params -= step
        if np.max(np.abs(step)) < 1e-7:
            break

    return float(params[0]), float(params[1])


def _build_strength_model(team_features: pd.DataFrame, season: Optional[str] = None) -> Dict[str, Any]:
    if team_features.empty:
        return {
            "means": np.zeros(len(MODEL_FEATURES)),
            "stds": np.ones(len(MODEL_FEATURES)),
            "beta": np.zeros(len(MODEL_FEATURES)),
            "intercept": 0.5,
            "cluster_strengths": {},
            "calibration_intercept": 0.0,
            "calibration_slope": 6.0,
            "feature_importance": [],
        }

    training = _prepare_training_frame(team_features, season)
    frame = training.copy()

    medians = frame[MODEL_FEATURES].median(numeric_only=True)
    X = frame[MODEL_FEATURES].fillna(medians).astype(float).to_numpy()
    y = frame["win_pct"].astype(float).to_numpy()

    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds[stds < 1e-6] = 1.0
    X_scaled = (X - means) / stds

    beta, intercept = _fit_ridge_regression(X_scaled, y, alpha=1.2)

    feature_importance = [
        {"feature": feature, "importance": float(abs(weight))}
        for feature, weight in sorted(zip(MODEL_FEATURES, beta), key=lambda item: abs(item[1]), reverse=True)
    ]

    cluster_strengths = (
        frame.dropna(subset=["style"])
        .groupby("style")["win_pct"]
        .mean()
        .to_dict()
        if "style" in frame.columns
        else {}
    )

    pair_edges: List[float] = []
    pair_labels: List[float] = []
    normalized_weights = _normalize_weights(None)

    for _, season_rows in frame.groupby("season"):
        records = season_rows.to_dict("records")
        if len(records) < 2:
            continue
        for left, right in combinations(records, 2):
            if abs(_safe_float(left.get("win_pct")) - _safe_float(right.get("win_pct"))) < 1e-9:
                continue
            edge, _ = _compose_factor_breakdown(
                left,
                right,
                normalized_weights,
                {
                    "means": means,
                    "stds": stds,
                    "beta": beta,
                    "intercept": intercept,
                    "cluster_strengths": cluster_strengths,
                },
                {"total": 0, "home_win_pct": 0.5},
                {"style": left.get("style")},
                {"style": right.get("style")},
                include_home_edge=True,
            )
            pair_edges.extend([edge, -edge])
            pair_labels.extend([
                1.0 if _safe_float(left.get("win_pct")) > _safe_float(right.get("win_pct")) else 0.0,
                1.0 if _safe_float(right.get("win_pct")) > _safe_float(left.get("win_pct")) else 0.0,
            ])

    calibration_intercept, calibration_slope = _fit_logistic_calibration(
        np.asarray(pair_edges, dtype=float),
        np.asarray(pair_labels, dtype=float),
    )

    return {
        "means": means,
        "stds": stds,
        "beta": beta,
        "intercept": intercept,
        "cluster_strengths": cluster_strengths,
        "calibration_intercept": calibration_intercept,
        "calibration_slope": calibration_slope,
        "feature_importance": feature_importance,
        "training_rows": len(training),
    }


def _predict_strength(row: Dict[str, Any], model: Dict[str, Any]) -> float:
    values = np.array([_safe_float(row.get(feature), 0.0) for feature in MODEL_FEATURES], dtype=float)
    scaled = (values - model["means"]) / model["stds"]
    strength = model["intercept"] + float(scaled @ model["beta"])
    return float(np.clip(strength, 0.05, 0.95))


def _compose_factor_breakdown(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    weights: Dict[str, float],
    model: Dict[str, Any],
    h2h: Dict[str, Any],
    home_cluster: Optional[Dict[str, Any]],
    away_cluster: Optional[Dict[str, Any]],
    include_home_edge: bool = True,
) -> Tuple[float, Dict[str, Dict[str, float]]]:
    home_strength = _predict_strength(home_stats, model)
    away_strength = _predict_strength(away_stats, model)
    strength_edge = home_strength - away_strength

    net_edge = (
        (_safe_float(home_stats.get("net_rating")) - _safe_float(away_stats.get("net_rating"))) / 14.0
        + (_safe_float(home_stats.get("point_diff_avg")) - _safe_float(away_stats.get("point_diff_avg"))) / 12.0
    ) / 2.0
    shooting_edge = (
        (_safe_float(home_stats.get("true_shooting_pct"), 0.57) - _safe_float(away_stats.get("true_shooting_pct"), 0.57)) * 4.5
        + (_safe_float(home_stats.get("effective_fg_pct"), 0.53) - _safe_float(away_stats.get("effective_fg_pct"), 0.53)) * 4.0
    ) / 2.0
    efficiency_edge = 0.65 * strength_edge + 0.2 * net_edge + 0.15 * shooting_edge

    recent_edge = _safe_float(home_stats.get("recent_5_win_pct"), 0.5) - _safe_float(
        away_stats.get("recent_5_win_pct"), 0.5
    )
    home_edge = (
        _safe_float(home_stats.get("home_win_pct"), 0.55)
        - _safe_float(away_stats.get("away_win_pct"), 0.45)
    ) if include_home_edge else 0.0
    historical_edge = _safe_float(h2h.get("home_win_pct"), 0.5) - 0.5

    home_style = (home_cluster or {}).get("style") or home_stats.get("style")
    away_style = (away_cluster or {}).get("style") or away_stats.get("style")
    cluster_strengths = model.get("cluster_strengths", {})
    cluster_edge = _safe_float(cluster_strengths.get(home_style), 0.5) - _safe_float(
        cluster_strengths.get(away_style), 0.5
    )

    contributions = {
        "recent_form": {
            "edge": recent_edge,
            "weight": weights["recent_form"],
            "contribution": recent_edge * weights["recent_form"],
        },
        "home_advantage": {
            "edge": home_edge,
            "weight": weights["home_advantage"],
            "contribution": home_edge * weights["home_advantage"],
        },
        "historical_matchup": {
            "edge": historical_edge,
            "weight": weights["historical_matchup"],
            "contribution": historical_edge * weights["historical_matchup"],
        },
        "efficiency_diff": {
            "edge": efficiency_edge,
            "weight": weights["efficiency_diff"],
            "contribution": efficiency_edge * weights["efficiency_diff"],
        },
        "cluster_similarity": {
            "edge": cluster_edge,
            "weight": weights["cluster_similarity"],
            "contribution": cluster_edge * weights["cluster_similarity"],
        },
    }

    total_edge = sum(item["contribution"] for item in contributions.values())
    return total_edge, contributions


def calculate_weighted_probability(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    h2h: Dict[str, Any],
    home_cluster: Optional[Dict[str, Any]],
    away_cluster: Optional[Dict[str, Any]],
    weights: Dict[str, float],
) -> Tuple[float, Dict[str, Dict[str, float]]]:
    team_features, _, _ = load_data()
    model = _build_strength_model(team_features, season=home_stats.get("season"))
    normalized_weights = _normalize_weights(weights)
    edge, contributions = _compose_factor_breakdown(
        home_stats,
        away_stats,
        normalized_weights,
        model,
        h2h,
        home_cluster,
        away_cluster,
    )
    probability = float(
        _sigmoid(model["calibration_intercept"] + model["calibration_slope"] * edge)
    )
    return probability, contributions


def calculate_win_probability(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    h2h: Dict[str, Any],
    home_cluster: Optional[Dict[str, Any]],
    away_cluster: Optional[Dict[str, Any]],
) -> Tuple[float, Dict[str, Dict[str, float]]]:
    return calculate_weighted_probability(
        home_stats,
        away_stats,
        h2h,
        home_cluster,
        away_cluster,
        DEFAULT_WEIGHTS,
    )


def validate_params(params: Dict, param_type: str = "home") -> Tuple[bool, str]:
    del param_type
    valid_keys = set(DEFAULT_HOME_PARAMS.keys())
    for key in params.keys():
        if key not in valid_keys:
            return False, f"Unknown parameter: {key}"

    if "recent_win_pct" in params and params["recent_win_pct"] is not None:
        if not 0 <= _safe_float(params["recent_win_pct"], -1) <= 1:
            return False, "recent_win_pct must be between 0 and 1"

    if "home_advantage" in params:
        if not -0.15 <= _safe_float(params["home_advantage"], 99) <= 0.15:
            return False, "home_advantage must be between -0.15 and 0.15"

    if "injury_impact" in params:
        if not -0.35 <= _safe_float(params["injury_impact"], 99) <= 0.0:
            return False, "injury_impact must be between -0.35 and 0"

    if "rest_days" in params:
        try:
            rest_days = int(params["rest_days"])
        except Exception:
            return False, "rest_days must be an integer"
        if rest_days < 0 or rest_days > 10:
            return False, "rest_days must be between 0 and 10"

    if "morale_boost" in params:
        if not -0.2 <= _safe_float(params["morale_boost"], 99) <= 0.2:
            return False, "morale_boost must be between -0.2 and 0.2"

    if "custom_rating" in params and params["custom_rating"] is not None:
        if not 0 <= _safe_float(params["custom_rating"], -1) <= 100:
            return False, "custom_rating must be between 0 and 100"

    return True, ""


def validate_weights(weights: Dict) -> Tuple[bool, str]:
    valid_keys = set(DEFAULT_WEIGHTS.keys())
    for key, value in weights.items():
        if key not in valid_keys:
            return False, f"Unknown weight: {key}"
        try:
            numeric = float(value)
        except Exception:
            return False, f"Weight {key} must be numeric"
        if numeric < 0:
            return False, f"Weight {key} cannot be negative"
    return True, ""


def merge_params(default_params: Dict, custom_params: Optional[Dict]) -> Dict:
    merged = dict(default_params)
    if custom_params:
        merged.update(custom_params)
    return merged


def apply_realtime_adjustments(
    base_edge: float,
    home_params: Dict[str, Any],
    away_params: Dict[str, Any],
    model: Dict[str, Any],
    home_strength: float,
    away_strength: float,
) -> Tuple[float, Dict[str, Any]]:
    adjusted_edge = base_edge
    summary: List[Dict[str, Any]] = []

    injury_effect = _safe_float(home_params.get("injury_impact")) - _safe_float(away_params.get("injury_impact"))
    if abs(injury_effect) > 1e-9:
        adjusted_edge += injury_effect
        summary.append(
            {
                "name": "Injuries",
                "effect": round(injury_effect, 4),
                "description": f"Injury adjustment {'favours home' if injury_effect > 0 else 'hurts home'} by {abs(injury_effect)*100:.1f} pts",
            }
        )

    rest_effect = np.clip(
        (int(home_params.get("rest_days", 2)) - int(away_params.get("rest_days", 2))) * 0.015,
        -0.06,
        0.06,
    )
    if abs(rest_effect) > 1e-9:
        adjusted_edge += float(rest_effect)
        summary.append(
            {
                "name": "Rest days",
                "effect": round(float(rest_effect), 4),
                "description": f"Rest differential adds {float(rest_effect)*100:.1f} pts to the home edge",
            }
        )

    back_to_back_effect = 0.0
    if home_params.get("back_to_back"):
        back_to_back_effect -= 0.03
    if away_params.get("back_to_back"):
        back_to_back_effect += 0.03
    if abs(back_to_back_effect) > 1e-9:
        adjusted_edge += back_to_back_effect
        summary.append(
            {
                "name": "Back-to-back",
                "effect": round(back_to_back_effect, 4),
                "description": "Second night of a back-to-back changes the matchup balance",
            }
        )

    morale_effect = _safe_float(home_params.get("morale_boost")) - _safe_float(away_params.get("morale_boost"))
    if abs(morale_effect) > 1e-9:
        adjusted_edge += morale_effect
        summary.append(
            {
                "name": "Momentum",
                "effect": round(morale_effect, 4),
                "description": f"Momentum swing contributes {morale_effect*100:.1f} pts",
            }
        )

    custom_effect = 0.0
    if home_params.get("custom_rating") is not None:
        custom_effect += (_safe_float(home_params["custom_rating"]) / 100.0) - home_strength
    if away_params.get("custom_rating") is not None:
        custom_effect -= (_safe_float(away_params["custom_rating"]) / 100.0) - away_strength
    if abs(custom_effect) > 1e-9:
        adjusted_edge += custom_effect
        summary.append(
            {
                "name": "Manual override",
                "effect": round(custom_effect, 4),
                "description": "Custom team rating overrides part of the learned strength score",
            }
        )

    if home_params.get("recent_win_pct") is not None or away_params.get("recent_win_pct") is not None:
        home_recent = home_params.get("recent_win_pct")
        away_recent = away_params.get("recent_win_pct")
        if home_recent is not None and away_recent is not None:
            recent_override = (_safe_float(home_recent) - _safe_float(away_recent)) * 0.20
            adjusted_edge += recent_override
            summary.append(
                {
                    "name": "Manual recent form",
                    "effect": round(recent_override, 4),
                    "description": "Manual recent win-rate inputs refined the short-term form signal",
                }
            )

    base_probability = float(_sigmoid(model["calibration_intercept"] + model["calibration_slope"] * base_edge))
    final_probability = float(
        np.clip(_sigmoid(model["calibration_intercept"] + model["calibration_slope"] * adjusted_edge), 0.05, 0.95)
    )

    return adjusted_edge, {
        "base_probability": round(base_probability, 4),
        "final_probability": round(final_probability, 4),
        "summary": summary,
        "total_edge_shift": round(adjusted_edge - base_edge, 4),
    }


def _build_factor_item(
    factor_type: str,
    name: str,
    description: str,
    impact: float,
    team: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "type": factor_type,
        "team": team,
        "team_cn": TEAM_NAMES_CN.get(team, team) if team else None,
        "name": name,
        "description": description,
        "impact": round(float(impact), 4),
        "importance": round(abs(float(impact)), 4),
        "contribution": round(float(impact), 4),
    }


def analyze_key_factors(
    home_team: str,
    away_team: str,
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    factors: Dict[str, Dict[str, float]],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    if abs(factors["efficiency_diff"]["contribution"]) > 0.01:
        better_team = home_team if factors["efficiency_diff"]["contribution"] >= 0 else away_team
        better_name = TEAM_INFO.get(better_team, {}).get("name", better_team)
        items.append(
            _build_factor_item(
                "efficiency",
                "Efficiency edge",
                f"{better_name} owns the stronger efficiency profile entering this matchup",
                factors["efficiency_diff"]["contribution"],
                better_team,
            )
        )

    if abs(factors["recent_form"]["contribution"]) > 0.01:
        better_team = home_team if factors["recent_form"]["contribution"] >= 0 else away_team
        better_name = TEAM_INFO.get(better_team, {}).get("name", better_team)
        items.append(
            _build_factor_item(
                "form",
                "Recent form",
                f"{better_name} has the stronger recent win-rate trend",
                factors["recent_form"]["contribution"],
                better_team,
            )
        )

    if abs(factors["home_advantage"]["contribution"]) > 0.01:
        items.append(
            _build_factor_item(
                "home",
                "Home/road split",
                f"{TEAM_INFO.get(home_team, {}).get('name', home_team)} gets a home-court boost from recent split performance",
                factors["home_advantage"]["contribution"],
                home_team,
            )
        )

    if abs(factors["historical_matchup"]["contribution"]) > 0.005:
        better_team = home_team if factors["historical_matchup"]["contribution"] >= 0 else away_team
        better_name = TEAM_INFO.get(better_team, {}).get("name", better_team)
        items.append(
            _build_factor_item(
                "history",
                "Head-to-head",
                f"Recent head-to-head history tilts toward {better_name}",
                factors["historical_matchup"]["contribution"],
                better_team,
            )
        )

    if abs(factors["cluster_similarity"]["contribution"]) > 0.005:
        better_team = home_team if factors["cluster_similarity"]["contribution"] >= 0 else away_team
        items.append(
            _build_factor_item(
                "style",
                "Style matchup",
                "Historical style strength slightly shifts the matchup balance",
                factors["cluster_similarity"]["contribution"],
                better_team,
            )
        )

    items = sorted(items, key=lambda item: abs(item["impact"]), reverse=True)
    return items[:5]


def analyze_key_factors_advanced(
    home_team: str,
    away_team: str,
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    contributions: Dict[str, Dict[str, float]],
    home_params: Dict[str, Any],
    away_params: Dict[str, Any],
    adjustments_summary: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    factors = analyze_key_factors(home_team, away_team, home_stats, away_stats, contributions)

    for adjustment in adjustments_summary or []:
        effect = _safe_float(adjustment.get("effect"))
        if abs(effect) < 1e-9:
            continue
        factors.append(
            _build_factor_item(
                "adjustment",
                adjustment.get("name", "Adjustment"),
                adjustment.get("description", "Manual matchup adjustment"),
                effect,
                home_team if effect >= 0 else away_team,
            )
        )

    for team_key, params in ((home_team, home_params), (away_team, away_params)):
        if params.get("key_player_out"):
            factors.append(
                _build_factor_item(
                    "availability",
                    "Key player availability",
                    f"{TEAM_INFO.get(team_key, {}).get('name', team_key)} missing: {', '.join(params['key_player_out'])}",
                    -0.015 if team_key == home_team else 0.015,
                    team_key,
                )
            )

    factors = sorted(factors, key=lambda item: abs(item["impact"]), reverse=True)
    return factors[:6]


def determine_confidence(
    home_win_prob: float,
    key_factors: List[Dict[str, Any]],
    h2h: Dict[str, Any],
) -> str:
    certainty = abs(home_win_prob - 0.5) * 2.0
    factor_support = min(sum(abs(f["impact"]) for f in key_factors[:3]) / 0.18, 1.0)
    history_support = min(_safe_float(h2h.get("total")) / 8.0, 1.0) if h2h else 0.0
    score = 0.55 * certainty + 0.30 * factor_support + 0.15 * history_support

    if score >= 0.72:
        return "HIGH"
    if score >= 0.45:
        return "MEDIUM"
    return "LOW"


def determine_confidence_advanced(
    home_win_prob: float,
    key_factors: List[Dict[str, Any]],
    h2h: Dict[str, Any],
    adjustments: Dict[str, Any],
) -> str:
    base = determine_confidence(home_win_prob, key_factors, h2h)
    adjustment_count = len(adjustments.get("summary", []))
    certainty = abs(home_win_prob - 0.5) * 2.0
    if base == "LOW" and certainty > 0.28 and adjustment_count >= 2:
        return "MEDIUM"
    return base


def _predict_margin(home_stats: Dict[str, Any], away_stats: Dict[str, Any], home_win_prob: float) -> float:
    point_diff_edge = _safe_float(home_stats.get("point_diff_avg")) - _safe_float(away_stats.get("point_diff_avg"))
    net_edge = _safe_float(home_stats.get("net_rating")) - _safe_float(away_stats.get("net_rating"))
    probability_edge = (home_win_prob - 0.5) * 18.0
    margin = 0.55 * point_diff_edge + 0.35 * net_edge + probability_edge
    return float(np.clip(margin, -22.0, 22.0))


def _format_team_name(team_abbr: str) -> str:
    return TEAM_INFO.get(team_abbr, {}).get("name", team_abbr)


def predict_game(home_team: str, away_team: str) -> Dict[str, Any]:
    return predict_game_advanced(
        home_team=home_team,
        away_team=away_team,
        home_params=None,
        away_params=None,
        weights=None,
        season=None,
        use_recent_form=True,
        return_details=True,
    )


def predict_game_advanced(
    home_team: str,
    away_team: str,
    home_params: Optional[Dict] = None,
    away_params: Optional[Dict] = None,
    weights: Optional[Dict] = None,
    season: Optional[str] = None,
    use_recent_form: bool = True,
    return_details: bool = True,
) -> Dict[str, Any]:
    if home_params:
        valid, message = validate_params(home_params, "home")
        if not valid:
            raise ValueError(message)
    if away_params:
        valid, message = validate_params(away_params, "away")
        if not valid:
            raise ValueError(message)
    if weights:
        valid, message = validate_weights(weights)
        if not valid:
            raise ValueError(message)

    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)

    team_features, team_clusters, games = load_data()
    default_stats = _default_team_row(team_features)
    selected_season = get_latest_season(season)

    home_stats = {**default_stats, **get_team_latest_stats(home_team, team_features, selected_season)}
    away_stats = {**default_stats, **get_team_latest_stats(away_team, team_features, selected_season)}
    home_stats["season"] = home_stats.get("season", selected_season)
    away_stats["season"] = away_stats.get("season", selected_season)

    merged_home_params = merge_params(DEFAULT_HOME_PARAMS, home_params)
    merged_away_params = merge_params(DEFAULT_AWAY_PARAMS, away_params)
    normalized_weights = _normalize_weights(weights)

    if use_recent_form:
        if merged_home_params.get("recent_win_pct") is not None:
            home_stats["recent_5_win_pct"] = merged_home_params["recent_win_pct"]
        if merged_away_params.get("recent_win_pct") is not None:
            away_stats["recent_5_win_pct"] = merged_away_params["recent_win_pct"]

    if merged_home_params.get("home_advantage") is not None:
        home_stats["home_win_pct"] = np.clip(
            _safe_float(home_stats.get("home_win_pct"), 0.55) + _safe_float(merged_home_params["home_advantage"]),
            0.25,
            0.85,
        )

    home_cluster = get_team_cluster(home_team, team_clusters, selected_season)
    away_cluster = get_team_cluster(away_team, team_clusters, selected_season)
    h2h = get_head_to_head(home_team, away_team, games)

    model = _build_strength_model(team_features, selected_season)
    home_strength = _predict_strength(home_stats, model)
    away_strength = _predict_strength(away_stats, model)

    base_edge, contributions = _compose_factor_breakdown(
        home_stats,
        away_stats,
        normalized_weights,
        model,
        h2h,
        home_cluster,
        away_cluster,
    )
    base_probability = float(
        np.clip(_sigmoid(model["calibration_intercept"] + model["calibration_slope"] * base_edge), 0.05, 0.95)
    )

    adjusted_edge, adjustments = apply_realtime_adjustments(
        base_edge,
        merged_home_params,
        merged_away_params,
        model,
        home_strength,
        away_strength,
    )

    home_win_probability = float(
        np.clip(_sigmoid(model["calibration_intercept"] + model["calibration_slope"] * adjusted_edge), 0.05, 0.95)
    )
    away_win_probability = 1.0 - home_win_probability
    predicted_winner = home_team if home_win_probability >= 0.5 else away_team
    predicted_margin = _predict_margin(home_stats, away_stats, home_win_probability)
    if predicted_winner == away_team:
        predicted_margin = -abs(predicted_margin)
    else:
        predicted_margin = abs(predicted_margin)

    key_factors = analyze_key_factors_advanced(
        home_team,
        away_team,
        home_stats,
        away_stats,
        contributions,
        merged_home_params,
        merged_away_params,
        adjustments.get("summary", []),
    )
    confidence_level = determine_confidence_advanced(
        home_win_probability,
        key_factors,
        h2h,
        adjustments,
    )

    result: Dict[str, Any] = {
        "prediction_id": f"ADV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "prediction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "season": selected_season,
        "home_team": home_team,
        "home_team_name": _format_team_name(home_team),
        "home_team_cn": TEAM_NAMES_CN.get(home_team, _format_team_name(home_team)),
        "away_team": away_team,
        "away_team_name": _format_team_name(away_team),
        "away_team_cn": TEAM_NAMES_CN.get(away_team, _format_team_name(away_team)),
        "predicted_winner": predicted_winner,
        "predicted_winner_name": _format_team_name(predicted_winner),
        "predicted_winner_cn": TEAM_NAMES_CN.get(predicted_winner, _format_team_name(predicted_winner)),
        "home_win_probability": round(home_win_probability, 4),
        "away_win_probability": round(away_win_probability, 4),
        "predicted_margin": round(predicted_margin, 1),
        "margin_range": [round(predicted_margin - 4.5, 1), round(predicted_margin + 4.5, 1)],
        "confidence_level": confidence_level,
        "key_factors": key_factors,
    }

    if return_details:
        result["model_inputs"] = {
            "weights_used": normalized_weights,
            "home_strength": round(home_strength, 4),
            "away_strength": round(away_strength, 4),
            "training_rows": model.get("training_rows", 0),
        }
        result["home_stats"] = {
            key: round(_safe_float(value), 4) if isinstance(value, (int, float, np.number)) else value
            for key, value in home_stats.items()
            if key in MODEL_FEATURES or key in {"win_pct", "style", "season"}
        }
        result["away_stats"] = {
            key: round(_safe_float(value), 4) if isinstance(value, (int, float, np.number)) else value
            for key, value in away_stats.items()
            if key in MODEL_FEATURES or key in {"win_pct", "style", "season"}
        }
        result["adjustments_applied"] = {
            **adjustments,
            "contributions": {
                key: {
                    "edge": round(values["edge"], 4),
                    "weight": round(values["weight"], 4),
                    "contribution": round(values["contribution"], 4),
                }
                for key, values in contributions.items()
            },
            "base_probability": round(base_probability, 4),
        }
        result["head_to_head"] = h2h
        result["home_cluster"] = (home_cluster or {}).get("style") or home_stats.get("style")
        result["away_cluster"] = (away_cluster or {}).get("style") or away_stats.get("style")
        result["feature_importance"] = model.get("feature_importance", [])[:8]

    print(
        f"[Predict] {home_team} vs {away_team} | "
        f"home={home_win_probability:.3f} away={away_win_probability:.3f} "
        f"winner={predicted_winner} margin={predicted_margin:.1f}"
    )

    return result


def batch_predict(matchups: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for home_team, away_team in matchups:
        try:
            results.append(predict_game(home_team, away_team))
        except Exception as exc:
            results.append({"home_team": home_team, "away_team": away_team, "error": str(exc)})
    return results


def get_model_diagnostics(season: Optional[str] = None) -> Dict[str, Any]:
    team_features, _, _ = load_data()
    if team_features.empty:
        return {
            "pairwise_accuracy": 0.0,
            "quality_mae": 0.0,
            "samples": 0,
            "season_breakdown": [],
            "feature_importance": [],
        }

    seasons = sorted(team_features["season"].dropna().unique(), key=season_to_key)
    backtest_rows: List[Dict[str, Any]] = []
    total_correct = 0
    total_samples = 0
    mae_values: List[float] = []

    for target_season in seasons[1:]:
        model = _build_strength_model(team_features, target_season)
        target_rows = team_features[team_features["season"] == target_season].copy()
        if len(target_rows) < 2:
            continue

        target_rows["predicted_strength"] = target_rows.apply(
            lambda row: _predict_strength(row.to_dict(), model),
            axis=1,
        )
        mae = float(np.mean(np.abs(target_rows["predicted_strength"] - target_rows["win_pct"])))
        mae_values.append(mae)

        correct = 0
        samples = 0
        records = target_rows.to_dict("records")
        for left, right in combinations(records, 2):
            if abs(_safe_float(left.get("win_pct")) - _safe_float(right.get("win_pct"))) < 1e-9:
                continue
            edge, _ = _compose_factor_breakdown(
                left,
                right,
                _normalize_weights(None),
                model,
                {"total": 0, "home_win_pct": 0.5},
                {"style": left.get("style")},
                {"style": right.get("style")},
                include_home_edge=True,
            )
            predicted_home = _sigmoid(model["calibration_intercept"] + model["calibration_slope"] * edge) >= 0.5
            actual_home = _safe_float(left.get("win_pct")) > _safe_float(right.get("win_pct"))
            correct += int(predicted_home == actual_home)
            samples += 1

        if samples:
            total_correct += correct
            total_samples += samples
            backtest_rows.append(
                {
                    "season": target_season,
                    "pairwise_accuracy": round(correct / samples, 4),
                    "quality_mae": round(mae, 4),
                    "samples": samples,
                }
            )

    latest_model = _build_strength_model(team_features, season)
    pairwise_accuracy = round(total_correct / total_samples, 4) if total_samples else 0.0
    quality_mae = round(float(np.mean(mae_values)), 4) if mae_values else 0.0

    return {
        "pairwise_accuracy": pairwise_accuracy,
        "quality_mae": quality_mae,
        "samples": total_samples,
        "season_breakdown": backtest_rows,
        "feature_importance": latest_model.get("feature_importance", [])[:8],
    }


def visualize_prediction(result: Dict[str, Any]) -> Optional[Path]:
    """
    Kept for compatibility with older scripts.

    The web UI now handles visualization directly, so this function simply
    returns ``None`` instead of generating a static image dependency.
    """

    del result
    return None


def run_demo_predictions() -> List[Dict[str, Any]]:
    profiles = load_team_features_frame()
    if profiles.empty:
        return []

    latest_season = get_latest_season()
    latest_profiles = profiles[profiles["season"] == latest_season].sort_values("win_pct", ascending=False)
    teams = latest_profiles["team_abbr"].tolist()
    if len(teams) < 6:
        return []

    demo_matchups = [
        (teams[0], teams[1]),
        (teams[2], teams[3]),
        (teams[4], teams[5]),
    ]
    return batch_predict(demo_matchups)
