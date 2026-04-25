# -*- coding: utf-8 -*-
"""Regression tests for the current prediction pipeline."""

from __future__ import annotations

import unittest
import uuid
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import init_database
from data_repository import get_available_seasons, get_team_detail_data, get_team_profiles, get_team_rankings
from ml.predict import (
    get_model_diagnostics,
    predict_game,
    predict_game_advanced,
    validate_params,
    validate_weights,
)


class RepositoryTests(unittest.TestCase):
    def test_team_profiles_can_load_from_cached_features(self):
        profiles = get_team_profiles()
        self.assertFalse(profiles.empty)
        self.assertIn("team_abbr", profiles.columns)
        self.assertIn("win_pct", profiles.columns)
        self.assertGreaterEqual(len(profiles), 30)

    def test_available_seasons_not_empty(self):
        seasons = get_available_seasons()
        self.assertTrue(seasons)
        self.assertRegex(seasons[0], r"^\d{4}-\d{2}$")

    def test_team_detail_contains_required_sections(self):
        detail = get_team_detail_data("LAL")
        self.assertIsNotNone(detail)
        self.assertIn("info", detail)
        self.assertIn("stats", detail)
        self.assertIn("recent_games", detail)
        self.assertIn("win_pct", detail["stats"])


class PredictionTests(unittest.TestCase):
    def test_predict_game_returns_ui_friendly_payload(self):
        result = predict_game("LAL", "GSW")
        self.assertIn("prediction_id", result)
        self.assertIn("home_win_probability", result)
        self.assertIn("away_win_probability", result)
        self.assertIn("predicted_margin", result)
        self.assertIn("key_factors", result)
        self.assertAlmostEqual(
            result["home_win_probability"] + result["away_win_probability"],
            1.0,
            places=3,
        )

    def test_advanced_prediction_includes_adjustments_and_weights(self):
        result = predict_game_advanced(
            home_team="BOS",
            away_team="MIL",
            home_params={
                "injury_impact": -0.08,
                "rest_days": 3,
                "morale_boost": 0.04,
            },
            away_params={
                "back_to_back": True,
                "rest_days": 1,
            },
            weights={
                "recent_form": 0.30,
                "home_advantage": 0.15,
                "historical_matchup": 0.10,
                "efficiency_diff": 0.35,
                "cluster_similarity": 0.10,
            },
            return_details=True,
        )
        self.assertIn("adjustments_applied", result)
        self.assertIn("model_inputs", result)
        self.assertIn("feature_importance", result)
        self.assertIn(result["confidence_level"], {"HIGH", "MEDIUM", "LOW"})
        self.assertAlmostEqual(
            sum(result["model_inputs"]["weights_used"].values()),
            1.0,
            places=6,
        )

    def test_parameter_validation(self):
        valid, message = validate_params({"injury_impact": -0.1, "rest_days": 2}, "home")
        self.assertTrue(valid, message)

        valid, _ = validate_params({"injury_impact": 0.2}, "home")
        self.assertFalse(valid)

        valid, message = validate_weights({"recent_form": 0.3, "efficiency_diff": 0.4})
        self.assertTrue(valid, message)

        valid, _ = validate_weights({"recent_form": -0.1})
        self.assertFalse(valid)

    def test_model_diagnostics_have_backtest_summary(self):
        diagnostics = get_model_diagnostics()
        self.assertIn("pairwise_accuracy", diagnostics)
        self.assertIn("quality_mae", diagnostics)
        self.assertIn("season_breakdown", diagnostics)
        self.assertIn("feature_importance", diagnostics)


class DatabaseTests(unittest.TestCase):
    def test_prediction_round_trip_supports_web_payload_shape(self):
        temp_root = Path(__file__).resolve().parent.parent / ".tmp" / "test_dbs"
        temp_root.mkdir(parents=True, exist_ok=True)
        db_path = temp_root / f"{uuid.uuid4().hex}.sqlite"
        db = init_database(str(db_path))

        try:
            db.insert_prediction(
                {
                    "prediction_id": "TEST-001",
                    "home_team": "LAL",
                    "away_team": "BOS",
                    "predicted_winner": "LAL",
                    "home_win_probability": 0.6123,
                    "confidence_level": "HIGH",
                    "key_factors": [{"name": "Recent form", "impact": 0.08}],
                    "mode": "advanced",
                }
            )

            rows = db.get_recent_predictions(limit=5)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["home_team"], "LAL")
            self.assertAlmostEqual(rows[0]["home_win_prob"], 0.6123, places=4)
            self.assertEqual(rows[0]["confidence_level"], "HIGH")
            self.assertIsInstance(rows[0]["key_factors"], list)

            accuracy = db.get_prediction_accuracy()
            self.assertEqual(accuracy["total"], 1)
            self.assertEqual(accuracy["evaluated"], 0)
        finally:
            db.close()
            if db_path.exists():
                db_path.unlink()


class ApiContractTests(unittest.TestCase):
    def test_team_rankings_return_frontend_friendly_team_fields(self):
        teams = get_team_rankings()
        self.assertTrue(teams)

        team = teams[0]
        for field in ("abbr", "name", "team_abbr", "team_name", "team_id", "conference_cn"):
            self.assertIn(field, team)

        self.assertEqual(team["abbr"], team["team_abbr"])
        self.assertEqual(team["name"], team["team_name"])

    def test_latest_season_metrics_are_normalized_for_ui(self):
        teams = get_team_rankings("2025-26")
        self.assertTrue(teams)

        team = teams[0]
        self.assertLessEqual(team["avg_fg_pct"], 1.0)
        self.assertLessEqual(team["avg_fg3_pct"], 1.0)
        self.assertLessEqual(team["avg_ft_pct"], 1.0)
        self.assertGreater(team["offensive_rating"], 50.0)
        self.assertGreater(team["defensive_rating"], 50.0)
        self.assertGreater(team["pace"], 90.0)


if __name__ == "__main__":
    unittest.main()
