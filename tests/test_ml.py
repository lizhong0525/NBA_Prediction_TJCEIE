# -*- coding: utf-8 -*-
"""
机器学习模块测试
"""

import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.features import FeatureEngineer
from ml.cluster import TeamClusterAnalyzer
from ml.predict import GamePredictor


class TestFeatureEngineer:
    """测试FeatureEngineer类"""
    
    @pytest.fixture
    def engineer(self):
        """创建特征工程实例"""
        return FeatureEngineer()
    
    def test_engineer_initialization(self, engineer):
        """测试初始化"""
        assert engineer.scaler is not None
        assert engineer.pca is None
    
    def test_prepare_features(self, engineer):
        """测试准备特征"""
        df = pd.DataFrame({
            'points': [100, 110, 120],
            'opponent_points': [95, 100, 105],
            'fg_pct': [0.45, 0.48, 0.50]
        })
        
        features = engineer.prepare_features(df)
        
        assert not features.empty
        assert len(features) == 3
    
    def test_scale_features(self, engineer):
        """测试特征标准化"""
        df = pd.DataFrame({
            'col1': [1, 2, 3, 4, 5],
            'col2': [10, 20, 30, 40, 50]
        })
        
        scaled, scaler = engineer.scale_features(df)
        
        assert scaled.shape == (5, 2)
        # 标准化后均值应接近0
        assert abs(scaled.mean(axis=0).max()) < 1e-10
    
    def test_reduce_dimensions(self, engineer):
        """测试PCA降维"""
        np.random.seed(42)
        features = np.random.randn(100, 10)
        
        reduced, pca = engineer.reduce_dimensions(features, variance_threshold=0.95)
        
        assert reduced.shape[1] <= 10
        assert pca.explained_variance_ratio_.sum() <= 1.0
    
    def test_compute_team_features(self, engineer):
        """测试计算球队特征"""
        df = pd.DataFrame({
            'team_abbr': ['LAL'] * 10,
            'game_date': pd.date_range('2024-01-01', periods=10),
            'points': np.random.randint(100, 125, 10),
            'opponent_points': np.random.randint(95, 115, 10),
            'result': np.random.choice(['W', 'L'], 10),
            'fg_pct': np.random.uniform(0.40, 0.55, 10),
            'fg3_pct': np.random.uniform(0.30, 0.45, 10),
            'rebounds': np.random.randint(35, 50, 10),
            'assists': np.random.randint(20, 35, 10),
            'is_home': np.random.choice([True, False], 10)
        })
        
        features = engineer.compute_team_features(df, 'LAL', recent_games=5)
        
        assert 'win_pct' in features
        assert 'avg_points' in features
        assert features['games_played'] == 5


class TestTeamClusterAnalyzer:
    """测试TeamClusterAnalyzer类"""
    
    @pytest.fixture
    def analyzer(self):
        """创建聚类分析器实例"""
        return TeamClusterAnalyzer()
    
    def test_analyzer_initialization(self, analyzer):
        """测试初始化"""
        assert analyzer.kmeans is None
        assert analyzer.cluster_labels is None
    
    def test_fit_cluster(self, analyzer):
        """测试聚类拟合"""
        np.random.seed(42)
        # 生成4个簇的数据
        n = 30
        features = np.vstack([
            np.random.randn(n, 5) + [3, 3, 3, 3, 3],  # 簇1
            np.random.randn(n, 5) + [-3, 3, -3, 3, -3],  # 簇2
            np.random.randn(n, 5) + [3, -3, 3, -3, 3],  # 簇3
            np.random.randn(n, 5) + [-3, -3, -3, -3, -3],  # 簇4
        ])
        
        labels, metrics = analyzer.fit_cluster(features, n_clusters=4)
        
        assert len(labels) == 120
        assert 'silhouette' in metrics
        assert 'is_acceptable' in metrics
    
    def test_find_optimal_clusters(self, analyzer):
        """测试寻找最优聚类数"""
        np.random.seed(42)
        features = np.random.randn(50, 8)
        
        optimal_k, results = analyzer.find_optimal_clusters(features, max_k=6)
        
        assert 2 <= optimal_k <= 6
        assert len(results) <= 5
    
    def test_assign_cluster_labels(self, analyzer):
        """测试分配聚类标签"""
        np.random.seed(42)
        features = np.random.randn(30, 5)
        labels = np.random.randint(0, 4, 30)
        teams = [f'TEAM_{i}' for i in range(30)]
        
        df = analyzer.assign_cluster_labels(teams, labels)
        
        assert len(df) == 30
        assert 'cluster' in df.columns
        assert 'cluster_name' in df.columns
    
    def test_get_cluster_summary(self, analyzer):
        """测试获取聚类摘要"""
        np.random.seed(42)
        features = np.random.randn(40, 5)
        
        analyzer.fit_cluster(features, n_clusters=4)
        summary = analyzer.get_cluster_summary(features)
        
        assert not summary.empty
        assert len(summary) == 4


class TestGamePredictor:
    """测试GamePredictor类"""
    
    @pytest.fixture
    def predictor(self):
        """创建预测器实例"""
        return GamePredictor()
    
    def test_predictor_initialization(self, predictor):
        """测试初始化"""
        assert predictor.home_advantage > 0
        assert predictor.model is None
    
    def test_predict_game(self, predictor):
        """测试比赛预测"""
        home_stats = {
            'win_pct': 0.65,
            'home_win_pct': 0.75,
            'avg_points': 118.5,
            'avg_points_allowed': 110.2,
            'avg_fg3_pct': 0.38,
            'avg_rebounds': 45.5,
            'avg_assists': 28.0,
            'recent_5_win_pct': 0.8
        }
        
        away_stats = {
            'win_pct': 0.55,
            'away_win_pct': 0.45,
            'avg_points': 115.0,
            'avg_points_allowed': 112.0,
            'avg_fg3_pct': 0.35,
            'avg_rebounds': 43.0,
            'avg_assists': 25.0,
            'recent_5_win_pct': 0.6
        }
        
        result = predictor.predict_game('LAL', 'GSW', home_stats, away_stats)
        
        assert 'prediction_id' in result
        assert 'home_win_probability' in result
        assert 'confidence_level' in result
        assert 'key_factors' in result
        assert result['home_win_probability'] > 0.5  # 主场优势
        assert result['predicted_winner'] == 'LAL'
    
    def test_predict_game_away_win(self, predictor):
        """测试预测客队获胜"""
        home_stats = {
            'win_pct': 0.4,
            'home_win_pct': 0.45,
            'avg_points': 105.0,
            'avg_points_allowed': 115.0,
            'avg_fg3_pct': 0.32,
            'avg_rebounds': 40.0,
            'avg_assists': 22.0,
            'recent_5_win_pct': 0.4
        }
        
        away_stats = {
            'win_pct': 0.7,
            'away_win_pct': 0.65,
            'avg_points': 120.0,
            'avg_points_allowed': 105.0,
            'avg_fg3_pct': 0.40,
            'avg_rebounds': 48.0,
            'avg_assists': 30.0,
            'recent_5_win_pct': 0.9
        }
        
        result = predictor.predict_game('LAL', 'GSW', home_stats, away_stats)
        
        assert result['home_win_probability'] < 0.5
        assert result['predicted_winner'] == 'GSW'
    
    def test_determine_confidence(self, predictor):
        """测试置信度判断"""
        # 高置信度
        high_conf = predictor._determine_confidence(0.8, ['factor1', 'factor2', 'factor3'])
        assert high_conf == 'HIGH'
        
        # 低置信度
        low_conf = predictor._determine_confidence(0.52, [])
        assert low_conf == 'LOW'
    
    def test_generate_prediction_id(self, predictor):
        """测试生成预测ID"""
        id1 = predictor._generate_prediction_id()
        id2 = predictor._generate_prediction_id()
        
        assert id1.startswith('PRE')
        assert len(id1) == 18
        assert id1 != id2
    
    def test_evaluate_predictions(self, predictor):
        """测试评估预测"""
        predictions = [
            {'predicted_winner': 'LAL'},
            {'predicted_winner': 'GSW'},
            {'predicted_winner': 'LAL'}
        ]
        
        actual_results = ['LAL', 'GSW', 'GSW']
        
        evaluation = predictor.evaluate_predictions(predictions, actual_results)
        
        assert evaluation['total'] == 3
        assert evaluation['correct'] >= 0
        assert 0 <= evaluation['accuracy'] <= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
