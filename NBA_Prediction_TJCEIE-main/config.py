# -*- coding: utf-8 -*-
"""
NBA比赛预测系统 - 配置文件
包含数据库配置、爬虫配置、机器学习参数等
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

# ==================== 数据库配置 ====================
DATABASE_CONFIG = {
    'type': 'sqlite',
    'path': BASE_DIR / 'data' / 'nba.db',
    'timeout': 30,
    'check_same_thread': False
}

# ==================== 爬虫配置 ====================
CRAWLER_CONFIG = {
    'base_url': 'https://www.basketball-reference.com',
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    },
    'request_delay': 3,  # 请求间隔(秒)，遵守robots.txt
    'max_retries': 3,
    'retry_backoff': [1, 2, 4],  # 重试间隔递增
    'timeout': 30  # 请求超时(秒)
}

# 数据爬取范围
CRAWL_SEASONS = {
    'start_year': 2012,  # 2011-12赛季
    'end_year': 2026     # 2025-26赛季
}

# ==================== NBA球队信息 ====================
TEAM_INFO = {
    'ATL': {'id': '1610612737', 'name': 'Atlanta Hawks', 'city': 'Atlanta'},
    'BOS': {'id': '1610612738', 'name': 'Boston Celtics', 'city': 'Boston'},
    'BRK': {'id': '1610612751', 'name': 'Brooklyn Nets', 'city': 'Brooklyn'},
    'CHI': {'id': '1610612741', 'name': 'Chicago Bulls', 'city': 'Chicago'},
    'CHO': {'id': '1610612766', 'name': 'Charlotte Hornets', 'city': 'Charlotte'},
    'CLE': {'id': '1610612739', 'name': 'Cleveland Cavaliers', 'city': 'Cleveland'},
    'DAL': {'id': '1610612742', 'name': 'Dallas Mavericks', 'city': 'Dallas'},
    'DEN': {'id': '1610612743', 'name': 'Denver Nuggets', 'city': 'Denver'},
    'DET': {'id': '1610612765', 'name': 'Detroit Pistons', 'city': 'Detroit'},
    'GSW': {'id': '1610612744', 'name': 'Golden State Warriors', 'city': 'Golden State'},
    'HOU': {'id': '1610612745', 'name': 'Houston Rockets', 'city': 'Houston'},
    'IND': {'id': '1610612754', 'name': 'Indiana Pacers', 'city': 'Indiana'},
    'LAC': {'id': '1610612746', 'name': 'Los Angeles Clippers', 'city': 'Los Angeles'},
    'LAL': {'id': '1610612747', 'name': 'Los Angeles Lakers', 'city': 'Los Angeles'},
    'MEM': {'id': '1610612763', 'name': 'Memphis Grizzlies', 'city': 'Memphis'},
    'MIA': {'id': '1610612748', 'name': 'Miami Heat', 'city': 'Miami'},
    'MIL': {'id': '1610612749', 'name': 'Milwaukee Bucks', 'city': 'Milwaukee'},
    'MIN': {'id': '1610612750', 'name': 'Minnesota Timberwolves', 'city': 'Minnesota'},
    'NOP': {'id': '1610612740', 'name': 'New Orleans Pelicans', 'city': 'New Orleans'},
    'NYK': {'id': '1610612752', 'name': 'New York Knicks', 'city': 'New York'},
    'OKC': {'id': '1610612760', 'name': 'Oklahoma City Thunder', 'city': 'Oklahoma City'},
    'ORL': {'id': '1610612753', 'name': 'Orlando Magic', 'city': 'Orlando'},
    'PHI': {'id': '1610612755', 'name': 'Philadelphia 76ers', 'city': 'Philadelphia'},
    'PHO': {'id': '1610612756', 'name': 'Phoenix Suns', 'city': 'Phoenix'},
    'POR': {'id': '1610612757', 'name': 'Portland Trail Blazers', 'city': 'Portland'},
    'SAC': {'id': '1610612758', 'name': 'Sacramento Kings', 'city': 'Sacramento'},
    'SAS': {'id': '1610612759', 'name': 'San Antonio Spurs', 'city': 'San Antonio'},
    'TOR': {'id': '1610612761', 'name': 'Toronto Raptors', 'city': 'Toronto'},
    'UTA': {'id': '1610612762', 'name': 'Utah Jazz', 'city': 'Utah'},
    'WAS': {'id': '1610612764', 'name': 'Washington Wizards', 'city': 'Washington'}
}

# ==================== 机器学习配置 ====================
ML_CONFIG = {
    # K-Means聚类参数
    'clustering': {
        'n_clusters': 4,  # 球队风格分类数
        'max_iter': 300,
        'n_init': 10,
        'random_state': 42
    },
    
    # PCA降维参数
    'pca': {
        'n_components': 0.95,  # 保留95%的方差
        'random_state': 42
    },
    
    # 特征重要性阈值
    'feature_threshold': 0.1,
    
    # 模型评估指标
    'evaluation': {
        'silhouette_threshold': 0.5,  # 轮廓系数阈值
        'variance_threshold': 0.85    # 累计解释方差阈值
    }
}

# ==================== Flask配置 ====================
FLASK_CONFIG = {
    'secret_key': 'nba-prediction-secret-key-change-in-production',
    'debug': True,
    'host': '0.0.0.0',
    'port': 5000
}

# ==================== 日志配置 ====================
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': BASE_DIR / 'logs' / 'nba_prediction.log',
    'max_bytes': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5
}

# ==================== 数据字段配置 ====================
# 原始特征列表
RAW_FEATURES = [
    'points', 'opponent_points', 'fg_made', 'fg_attempts', 'fg_pct',
    'fg3_made', 'fg3_attempts', 'fg3_pct', 'ft_made', 'ft_attempts', 'ft_pct',
    'rebounds_total', 'assists', 'steals', 'blocks', 'turnovers', 'fouls'
]

# 衍生特征（需要计算的）
DERIVED_FEATURES = [
    'recent_5_avg_points', 'recent_5_avg_points_allowed', 'recent_5_win_pct',
    'home_win_pct', 'away_win_pct',
    'offensive_rating', 'defensive_rating', 'net_rating',
    'pace', 'true_shooting_pct', 'effective_fg_pct',
    'head_to_head_win_pct'
]

# 球队风格标签
TEAM_STYLES = {
    0: '进攻型',
    1: '防守型',
    2: '平衡型',
    3: '快攻型'
}

# ==================== API响应配置 ====================
API_RESPONSE = {
    'success_code': 200,
    'error_codes': {
        400: '参数错误',
        404: '资源不存在',
        500: '服务器错误'
    }
}

# ==================== 路径配置 ====================
PATH_CONFIG = {
    'raw_data': BASE_DIR / 'data' / 'raw',
    'processed_data': BASE_DIR / 'data' / 'processed',
    'logs': BASE_DIR / 'logs',
    'templates': BASE_DIR / 'app' / 'templates',
    'static': BASE_DIR / 'app' / 'static'
}
