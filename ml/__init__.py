# -*- coding: utf-8 -*-
"""Public exports for the ML package.

Prediction-related functions are always available. Feature engineering and
clustering helpers are imported lazily so the web app can still run in minimal
environments where optional plotting libraries are missing.
"""

from __future__ import annotations

from .predict import (
    DEFAULT_AWAY_PARAMS,
    DEFAULT_HOME_PARAMS,
    DEFAULT_WEIGHTS,
    batch_predict,
    predict_game,
    predict_game_advanced,
    run_demo_predictions,
    validate_params,
    validate_weights,
)

try:
    from .features import (
        calculate_advanced_features,
        calculate_rolling_features,
        load_game_data,
        run_feature_engineering,
    )
except Exception:  # pragma: no cover - optional dependency path
    calculate_advanced_features = None
    calculate_rolling_features = None
    load_game_data = None
    run_feature_engineering = None

try:
    from .cluster import load_team_features, perform_clustering, run_clustering_analysis
except Exception:  # pragma: no cover - optional dependency path
    load_team_features = None
    perform_clustering = None
    run_clustering_analysis = None

__all__ = [
    "run_feature_engineering",
    "load_game_data",
    "calculate_rolling_features",
    "calculate_advanced_features",
    "run_clustering_analysis",
    "load_team_features",
    "perform_clustering",
    "predict_game",
    "batch_predict",
    "run_demo_predictions",
    "predict_game_advanced",
    "validate_params",
    "validate_weights",
    "DEFAULT_WEIGHTS",
    "DEFAULT_HOME_PARAMS",
    "DEFAULT_AWAY_PARAMS",
]
