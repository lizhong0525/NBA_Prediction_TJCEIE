# -*- coding: utf-8 -*-
"""Small smoke-test script for the prediction helper API."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ml.api import (
    batch_predict_advanced,
    format_prediction_summary,
    full_advanced_predict,
    get_default_params,
    predict_with_custom_weights,
    predict_with_injuries,
    predict_with_schedule,
    simple_predict,
    validate_prediction_params,
)


def main() -> int:
    print("=" * 60)
    print("NBA Prediction API Smoke Test")
    print("=" * 60)

    defaults = get_default_params()
    print("Default weights:", defaults["default_weights"])

    valid, message = validate_prediction_params(
        home_params={"injury_impact": -0.1, "rest_days": 2},
        weights={"recent_form": 0.25, "efficiency_diff": 0.4},
    )
    assert valid, message
    print("Parameter validation: PASS")

    simple = simple_predict("LAL", "BOS")
    print(format_prediction_summary(simple))

    injuries = predict_with_injuries(
        "DEN",
        "PHO",
        home_injury_impact=-0.05,
        away_injury_impact=-0.12,
        away_players_out=["Primary scorer"],
    )
    assert "key_factors" in injuries
    print("Injury scenario winner:", injuries["predicted_winner"])

    schedule = predict_with_schedule(
        "NYK",
        "MIA",
        home_rest_days=3,
        away_rest_days=1,
        away_back_to_back=True,
    )
    assert "adjustments_applied" in schedule
    print("Schedule scenario confidence:", schedule["confidence_level"])

    weighted = predict_with_custom_weights(
        "OKC",
        "MIN",
        recent_form=0.35,
        efficiency_diff=0.30,
    )
    assert "model_inputs" in weighted
    print("Custom weight scenario margin:", weighted["predicted_margin"])

    advanced = full_advanced_predict(
        home_team="BOS",
        away_team="MIL",
        home_params={"injury_impact": -0.08, "rest_days": 3, "morale_boost": 0.04},
        away_params={"back_to_back": True, "rest_days": 1},
        weights={
            "recent_form": 0.30,
            "home_advantage": 0.15,
            "historical_matchup": 0.10,
            "efficiency_diff": 0.35,
            "cluster_similarity": 0.10,
        },
    )
    assert "feature_importance" in advanced
    print("Advanced scenario winner:", advanced["predicted_winner_cn"])

    batch = batch_predict_advanced(
        [
            {"home_team": "LAL", "away_team": "BOS"},
            {"home_team": "GSW", "away_team": "DEN"},
            {"home_team": "MIA", "away_team": "NYK"},
        ]
    )
    assert len(batch) == 3
    print("Batch scenario count:", len(batch))

    print("=" * 60)
    print("Smoke test finished successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
