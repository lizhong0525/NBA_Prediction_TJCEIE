# -*- coding: utf-8 -*-
"""
比赛预测模块
基于历史数据和机器学习进行比赛结果预测

功能：
- 基于球队特征的胜率预测
- 关键因素分析
- 预测结果生成与置信度评估
- 历史对阵数据整合
- 实时参数支持（球队状态、主客场、伤病情况等）
"""

import numpy as np
import pandas as pd
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import random
import warnings
import copy
warnings.filterwarnings('ignore')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# ==================== 配置 ====================
DATABASE_PATH = Path(__file__).parent.parent / 'data' / 'nba.db'
OUTPUT_DIR = Path(__file__).parent.parent / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)

# 球队缩写标准化映射
TEAM_ABBR_NORMALIZE = {
    'BKN': 'BRK', 'CHA': 'CHO', 'NO': 'NOP', 'NY': 'NYK', 'PHX': 'PHO', 'GS': 'GSW'
}

# 球队中文名映射
TEAM_NAMES_CN = {
    'ATL': '老鹰', 'BOS': '凯尔特人', 'BRK': '篮网', 'CHI': '公牛', 'CHO': '黄蜂',
    'CLE': '骑士', 'DAL': '独行侠', 'DEN': '掘金', 'DET': '活塞', 'GSW': '勇士',
    'HOU': '火箭', 'IND': '步行者', 'LAC': '快船', 'LAL': '湖人', 'MEM': '灰熊',
    'MIA': '热火', 'MIL': '雄鹿', 'MIN': '森林狼', 'NOP': '鹈鹕', 'NYK': '尼克斯',
    'OKC': '雷霆', 'ORL': '魔术', 'PHI': '76人', 'PHO': '太阳', 'POR': '开拓者',
    'SAC': '国王', 'SAS': '马刺', 'TOR': '猛龙', 'UTA': '爵士', 'WAS': '奇才'
}


def normalize_team(team_abbr: str) -> str:
    """标准化球队缩写"""
    return TEAM_ABBR_NORMALIZE.get(team_abbr.upper(), team_abbr.upper())


def load_data():
    """
    加载所需数据
    
    Returns:
        (球队特征DataFrame, 球队聚类DataFrame, 历史比赛DataFrame)
    """
    conn = sqlite3.connect(DATABASE_PATH)
    
    # 加载球队特征
    try:
        team_features = pd.read_sql_query("SELECT * FROM team_features", conn)
    except:
        team_features = pd.DataFrame()
    
    # 加载球队聚类
    try:
        team_clusters = pd.read_sql_query("SELECT * FROM team_clusters", conn)
    except:
        team_clusters = pd.DataFrame()
    
    # 加载原始比赛数据
    games = pd.read_sql_query("""
        SELECT * FROM team_game_stats 
        ORDER BY game_date DESC
    """, conn)
    
    conn.close()
    
    # 标准化球队名称
    if len(team_features) > 0:
        team_features['team_abbr'] = team_features['team_abbr'].apply(normalize_team)
    if len(team_clusters) > 0:
        team_clusters['team_abbr'] = team_clusters['team_abbr'].apply(normalize_team)
    if len(games) > 0:
        games['team_abbr'] = games['team_abbr'].apply(normalize_team)
        games['opponent_abbr'] = games['opponent_abbr'].apply(normalize_team)
    
    return team_features, team_clusters, games


def get_team_latest_stats(team_abbr: str, team_features: pd.DataFrame,
                          season: str = None) -> Dict:
    """
    获取球队最新统计数据
    
    Args:
        team_abbr: 球队缩写
        team_features: 球队特征数据
        season: 赛季（可选，默认最新赛季）
        
    Returns:
        球队统计字典
    """
    team_abbr = normalize_team(team_abbr)
    
    if len(team_features) == 0:
        return {}
    
    # 筛选球队
    team_data = team_features[team_features['team_abbr'] == team_abbr]
    
    if len(team_data) == 0:
        return {}
    
    # 获取最新赛季或指定赛季
    if season:
        team_data = team_data[team_data['season'] == season]
    
    if len(team_data) == 0:
        # 使用最新的可用数据
        team_data = team_features[team_features['team_abbr'] == team_abbr].sort_values('season', ascending=False)
    
    if len(team_data) == 0:
        return {}
    
    latest = team_data.iloc[0].to_dict()
    return latest


def get_team_cluster(team_abbr: str, team_clusters: pd.DataFrame) -> Optional[Dict]:
    """
    获取球队聚类信息
    
    Args:
        team_abbr: 球队缩写
        team_clusters: 聚类数据
        
    Returns:
        聚类信息字典
    """
    team_abbr = normalize_team(team_abbr)
    
    if len(team_clusters) == 0:
        return None
    
    team_cluster = team_clusters[team_clusters['team_abbr'] == team_abbr]
    
    if len(team_cluster) == 0:
        return None
    
    return team_cluster.iloc[0].to_dict()


def get_head_to_head(home_team: str, away_team: str, games: pd.DataFrame,
                    max_games: int = 10) -> Dict:
    """
    获取两队历史交锋记录
    
    Args:
        home_team: 主队
        away_team: 客队
        games: 历史比赛数据
        max_games: 最大查询场次
        
    Returns:
        对阵记录字典
    """
    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)
    
    if len(games) == 0:
        return {'total': 0, 'home_wins': 0, 'away_wins': 0, 'home_win_pct': 0.5}
    
    # 查找两队交锋记录
    h2h = games[
        ((games['team_abbr'] == home_team) & (games['opponent_abbr'] == away_team)) |
        ((games['team_abbr'] == away_team) & (games['opponent_abbr'] == home_team))
    ].head(max_games)
    
    if len(h2h) == 0:
        return {'total': 0, 'home_wins': 0, 'away_wins': 0, 'home_win_pct': 0.5}
    
    # 统计主场队获胜次数
    home_wins = len(h2h[(h2h['team_abbr'] == home_team) & (h2h['result'] == 'W')])
    away_wins = len(h2h[(h2h['team_abbr'] == away_team) & (h2h['result'] == 'W')])
    
    return {
        'total': len(h2h),
        'home_wins': home_wins,
        'away_wins': away_wins,
        'home_win_pct': home_wins / len(h2h) if len(h2h) > 0 else 0.5,
        'recent_results': h2h[['game_date', 'team_abbr', 'opponent_abbr', 'result', 'points', 'opponent_points']].to_dict('records')
    }


def calculate_win_probability(home_stats: Dict, away_stats: Dict,
                              h2h: Dict, home_cluster: Optional[Dict],
                              away_cluster: Optional[Dict]) -> Tuple[float, Dict]:
    """
    计算主队获胜概率
    
    Args:
        home_stats: 主队统计
        away_stats: 客队统计
        h2h: 历史对阵记录
        home_cluster: 主队聚类信息
        away_cluster: 客队聚类信息
        
    Returns:
        (主队胜率, 贡献因子字典)
    """
    if not home_stats or not away_stats:
        return 0.5, {}
    
    # 基础概率
    base_prob = 0.5
    
    # 因子权重
    factors = {}
    
    # 1. 近期战绩因子 (权重: 0.25)
    home_recent = home_stats.get('recent_5_win_pct', 0.5)
    away_recent = away_stats.get('recent_5_win_pct', 0.5)
    recent_diff = home_recent - away_recent
    factors['recent_form'] = {
        'home': home_recent,
        'away': away_recent,
        'contribution': recent_diff * 0.25
    }
    base_prob += recent_diff * 0.25
    
    # 2. 进攻效率因子 (权重: 0.20)
    home_off = home_stats.get('offensive_rating', 110)
    away_off = away_stats.get('offensive_rating', 110)
    off_diff = (home_off - away_off) / 100  # 标准化
    factors['offense'] = {
        'home': home_off,
        'away': away_off,
        'contribution': off_diff * 0.20
    }
    base_prob += off_diff * 0.20
    
    # 3. 防守效率因子 (权重: 0.20)
    home_def = home_stats.get('defensive_rating', 110)
    away_def = away_stats.get('defensive_rating', 110)
    def_diff = (away_def - home_def) / 100  # 防守越好（数值越小），主队优势越大
    factors['defense'] = {
        'home': home_def,
        'away': away_def,
        'contribution': def_diff * 0.20
    }
    base_prob += def_diff * 0.20
    
    # 4. 主场优势因子 (权重: 0.15)
    home_home_win = home_stats.get('home_win_pct', 0.5)
    factors['home_advantage'] = {
        'home_win_pct': home_home_win,
        'contribution': (home_home_win - 0.5) * 0.30  # 主场胜率超出50%的部分
    }
    base_prob += (home_home_win - 0.5) * 0.30
    
    # 5. 历史交锋因子 (权重: 0.10)
    if h2h and h2h['total'] > 0:
        h2h_adv = (h2h['home_win_pct'] - 0.5) * 0.20
        factors['head_to_head'] = {
            'home_win_pct': h2h['home_win_pct'],
            'total_games': h2h['total'],
            'contribution': h2h_adv
        }
        base_prob += h2h_adv
    else:
        factors['head_to_head'] = {'contribution': 0}
    
    # 6. 聚类风格克制 (权重: 0.10)
    if home_cluster and away_cluster:
        # 不同风格对战有微调
        style_modifier = 0.02  # 默认微调
        factors['style_matchup'] = {
            'home_style': home_cluster.get('style', 'Unknown'),
            'away_style': away_cluster.get('style', 'Unknown'),
            'contribution': style_modifier
        }
        base_prob += style_modifier
    else:
        factors['style_matchup'] = {'contribution': 0}
    
    # 限制概率范围
    base_prob = max(0.15, min(0.85, base_prob))
    
    return base_prob, factors


def analyze_key_factors(home_team: str, away_team: str,
                        home_stats: Dict, away_stats: Dict,
                        factors: Dict) -> List[Dict]:
    """
    分析关键因素
    
    Args:
        home_team: 主队
        away_team: 客队
        home_stats: 主队统计
        away_stats: 客队统计
        factors: 各因子贡献
        
    Returns:
        关键因素列表
    """
    key_factors = []
    
    home_cn = TEAM_NAMES_CN.get(normalize_team(home_team), home_team)
    away_cn = TEAM_NAMES_CN.get(normalize_team(away_team), away_team)
    
    # 分析进攻
    home_off = home_stats.get('offensive_rating', 0)
    away_off = away_stats.get('offensive_rating', 0)
    if home_off > away_off + 2:
        key_factors.append({
            'type': 'offense',
            'team': home_team,
            'team_cn': home_cn,
            'description': f'{home_cn}进攻效率更优 ({home_off:.1f} vs {away_off:.1f})',
            'importance': abs(home_off - away_off) / 5
        })
    elif away_off > home_off + 2:
        key_factors.append({
            'type': 'offense',
            'team': away_team,
            'team_cn': away_cn,
            'description': f'{away_cn}进攻效率更优 ({away_off:.1f} vs {home_off:.1f})',
            'importance': abs(away_off - home_off) / 5
        })
    
    # 分析防守
    home_def = home_stats.get('defensive_rating', 0)
    away_def = away_stats.get('defensive_rating', 0)
    if home_def < away_def - 2:  # 数值越小越好
        key_factors.append({
            'type': 'defense',
            'team': home_team,
            'team_cn': home_cn,
            'description': f'{home_cn}防守更稳固 ({home_def:.1f} vs {away_def:.1f})',
            'importance': abs(away_def - home_def) / 5
        })
    elif away_def < home_def - 2:
        key_factors.append({
            'type': 'defense',
            'team': away_team,
            'team_cn': away_cn,
            'description': f'{away_cn}防守更稳固 ({away_def:.1f} vs {home_def:.1f})',
            'importance': abs(home_def - away_def) / 5
        })
    
    # 分析近期状态
    home_recent = home_stats.get('recent_5_win_pct', 0.5)
    away_recent = away_stats.get('recent_5_win_pct', 0.5)
    if home_recent > away_recent + 0.1:
        key_factors.append({
            'type': 'form',
            'team': home_team,
            'team_cn': home_cn,
            'description': f'{home_cn}近期状态更佳 ({(home_recent*100):.0f}% vs {(away_recent*100):.0f}%)',
            'importance': abs(home_recent - away_recent) * 5
        })
    elif away_recent > home_recent + 0.1:
        key_factors.append({
            'type': 'form',
            'team': away_team,
            'team_cn': away_cn,
            'description': f'{away_cn}近期状态更佳 ({(away_recent*100):.0f}% vs {(home_recent*100):.0f}%)',
            'importance': abs(away_recent - home_recent) * 5
        })
    
    # 分析主场优势
    home_win_pct = home_stats.get('home_win_pct', 0.5)
    if home_win_pct > 0.6:
        key_factors.append({
            'type': 'home',
            'team': home_team,
            'team_cn': home_cn,
            'description': f'{home_cn}主场强势 ({home_win_pct*100:.0f}%胜率)',
            'importance': (home_win_pct - 0.5) * 3
        })
    
    # 按重要性排序
    key_factors = sorted(key_factors, key=lambda x: x['importance'], reverse=True)
    
    return key_factors[:5]  # 返回前5个


def determine_confidence(home_win_prob: float, key_factors: List[Dict],
                         h2h: Dict) -> str:
    """
    确定预测置信度
    
    Args:
        home_win_prob: 主队胜率
        h2h: 对阵记录
        
    Returns:
        置信度等级
    """
    # 计算概率偏向程度
    prob_swing = abs(home_win_prob - 0.5) * 2  # 0-1范围
    
    # 因子一致性
    factor_count = len(key_factors)
    
    # 对阵数据支持度
    h2h_support = 0
    if h2h and h2h['total'] >= 3:
        h2h_support = min(0.1, h2h['total'] * 0.02)
    
    # 综合评分
    confidence_score = prob_swing * 0.4 + factor_count * 0.1 + h2h_support
    
    if confidence_score > 0.7:
        return "高"
    elif confidence_score > 0.4:
        return "中"
    else:
        return "低"


def predict_game(home_team: str, away_team: str) -> Dict:
    """
    预测单场比赛结果
    
    Args:
        home_team: 主队缩写
        away_team: 客队缩写
        
    Returns:
        预测结果字典
    """
    print(f"\n{'='*60}")
    print(f"比赛预测: {home_team} (主场) vs {away_team} (客场)")
    print(f"{'='*60}")
    
    # 加载数据
    team_features, team_clusters, games = load_data()
    
    # 标准化球队名称
    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)
    
    # 获取球队统计
    home_stats = get_team_latest_stats(home_team, team_features)
    away_stats = get_team_latest_stats(away_team, team_features)
    
    # 获取聚类信息
    home_cluster = get_team_cluster(home_team, team_clusters)
    away_cluster = get_team_cluster(away_team, team_clusters)
    
    # 获取历史对阵
    h2h = get_head_to_head(home_team, away_team, games)
    
    # 检查数据完整性
    if not home_stats:
        print(f"[警告] 未找到 {home_team} 的统计数据")
        home_stats = {}
    if not away_stats:
        print(f"[警告] 未找到 {away_team} 的统计数据")
        away_stats = {}
    
    # 计算胜率
    home_win_prob, factors = calculate_win_probability(
        home_stats, away_stats, h2h, home_cluster, away_cluster
    )
    
    # 分析关键因素
    key_factors = analyze_key_factors(home_team, away_team, home_stats, away_stats, factors)
    
    # 确定置信度
    confidence = determine_confidence(home_win_prob, key_factors, h2h)
    
    # 预测结果
    predicted_winner = home_team if home_win_prob > 0.5 else away_team
    predicted_winner_cn = TEAM_NAMES_CN.get(predicted_winner, predicted_winner)
    
    away_win_prob = 1 - home_win_prob
    
    # 组装结果
    result = {
        'prediction_id': f"PRD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'prediction_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'home_team': home_team,
        'home_team_cn': TEAM_NAMES_CN.get(home_team, home_team),
        'away_team': away_team,
        'away_team_cn': TEAM_NAMES_CN.get(away_team, away_team),
        'predicted_winner': predicted_winner,
        'predicted_winner_cn': predicted_winner_cn,
        'home_win_probability': round(home_win_prob, 4),
        'away_win_probability': round(away_win_prob, 4),
        'confidence_level': confidence,
        'key_factors': key_factors,
        'home_stats': {k: round(v, 2) if isinstance(v, float) else v 
                       for k, v in home_stats.items() if isinstance(v, (int, float))},
        'away_stats': {k: round(v, 2) if isinstance(v, float) else v 
                      for k, v in away_stats.items() if isinstance(v, (int, float))},
        'head_to_head': h2h,
        'home_cluster': home_cluster.get('style') if home_cluster else None,
        'away_cluster': away_cluster.get('style') if away_cluster else None
    }
    
    # 打印结果
    print(f"\n📊 预测分析:")
    print(f"   {home_team} ({result['home_team_cn']}) 主场胜率: {home_win_prob*100:.1f}%")
    print(f"   {away_team} ({result['away_team_cn']}) 客场胜率: {away_win_prob*100:.1f}%")
    print(f"   预测获胜: {predicted_winner} ({predicted_winner_cn})")
    print(f"   置信度: {confidence}")
    
    if key_factors:
        print(f"\n🔑 关键因素:")
        for i, factor in enumerate(key_factors, 1):
            print(f"   {i}. {factor['description']}")
    
    if h2h and h2h['total'] > 0:
        print(f"\n📈 历史对阵 ({home_team} 主场): {h2h['home_wins']}胜 {h2h['away_wins']}负 (共{h2h['total']}场)")
    
    if home_cluster and away_cluster:
        print(f"\n🏀 球队风格:")
        print(f"   {home_team}: {home_cluster.get('style', 'Unknown')}")
        print(f"   {away_team}: {away_cluster.get('style', 'Unknown')}")
    
    return result


def batch_predict(matchups: List[Tuple[str, str]]) -> List[Dict]:
    """
    批量预测多场比赛
    
    Args:
        matchups: 比赛对阵列表 [(主队, 客队), ...]
        
    Returns:
        预测结果列表
    """
    print(f"\n{'='*60}")
    print(f"批量预测: {len(matchups)} 场比赛")
    print(f"{'='*60}")
    
    results = []
    
    for i, (home, away) in enumerate(matchups, 1):
        print(f"\n[{i}/{len(matchups)}]")
        try:
            result = predict_game(home, away)
            results.append(result)
        except Exception as e:
            print(f"[错误] 预测失败: {e}")
            results.append({
                'home_team': home,
                'away_team': away,
                'error': str(e)
            })
    
    return results


# ==================== 实时参数预测接口 ====================

# 默认权重配置
DEFAULT_WEIGHTS = {
    'recent_form': 0.25,           # 近期状态权重
    'home_advantage': 0.15,        # 主场优势权重
    'historical_matchup': 0.10,   # 历史交锋权重
    'efficiency_diff': 0.40,      # 效率差权重（进攻+防守）
    'cluster_similarity': 0.10,   # 风格相似度权重
}

# 默认实时参数
DEFAULT_HOME_PARAMS = {
    'recent_win_pct': None,        # 近期胜率（手动输入）
    'home_advantage': 0.06,        # 主场优势加成（0-0.1）
    'injury_impact': 0,            # 伤病影响（-0.2 to 0）
    'rest_days': 2,                # 休息天数
    'back_to_back': False,         # 是否背靠背
    'key_player_out': [],         # 缺阵核心球员
    'morale_boost': 0,             # 士气加成（-0.1 to 0.1）
    'custom_rating': None,         # 自定义实力评分（覆盖计算值）
}

DEFAULT_AWAY_PARAMS = {
    'recent_win_pct': None,
    'home_advantage': 0,           # 客场无主场加成
    'injury_impact': 0,
    'rest_days': 2,
    'back_to_back': False,
    'key_player_out': [],
    'morale_boost': 0,
    'custom_rating': None,
}


def validate_params(params: Dict, param_type: str = 'home') -> Tuple[bool, str]:
    """
    验证实时参数的有效性
    
    Args:
        params: 待验证的参数字典
        param_type: 参数类型 ('home' 或 'away')
        
    Returns:
        (是否有效, 错误信息)
    """
    valid_keys = set(DEFAULT_HOME_PARAMS.keys())
    
    for key in params.keys():
        if key not in valid_keys:
            return False, f"未知参数: {key}"
    
    # 验证数值范围
    if 'recent_win_pct' in params and params['recent_win_pct'] is not None:
        if not 0 <= params['recent_win_pct'] <= 1:
            return False, "recent_win_pct 必须在 0-1 之间"
    
    if 'home_advantage' in params:
        if not -0.1 <= params['home_advantage'] <= 0.1:
            return False, "home_advantage 必须在 -0.1 到 0.1 之间"
    
    if 'injury_impact' in params:
        if not -0.3 <= params['injury_impact'] <= 0:
            return False, "injury_impact 必须在 -0.3 到 0 之间"
    
    if 'rest_days' in params:
        if not isinstance(params['rest_days'], int) or params['rest_days'] < 0:
            return False, "rest_days 必须是 >= 0 的整数"
    
    if 'morale_boost' in params:
        if not -0.15 <= params['morale_boost'] <= 0.15:
            return False, "morale_boost 必须在 -0.15 到 0.15 之间"
    
    if 'custom_rating' in params and params['custom_rating'] is not None:
        if not 0 <= params['custom_rating'] <= 100:
            return False, "custom_rating 必须在 0-100 之间"
    
    return True, ""


def validate_weights(weights: Dict) -> Tuple[bool, str]:
    """
    验证权重配置的有效性
    
    Args:
        weights: 权重配置字典
        
    Returns:
        (是否有效, 错误信息)
    """
    valid_keys = set(DEFAULT_WEIGHTS.keys())
    
    for key in weights.keys():
        if key not in valid_keys:
            return False, f"未知权重: {key}"
        
        if not isinstance(weights[key], (int, float)):
            return False, f"权重 {key} 必须是数值类型"
        
        if weights[key] < 0:
            return False, f"权重 {key} 不能为负数"
    
    return True, ""


def merge_params(default_params: Dict, custom_params: Optional[Dict]) -> Dict:
    """
    合并默认参数和自定义参数
    
    Args:
        default_params: 默认参数
        custom_params: 自定义参数
        
    Returns:
        合并后的参数字典
    """
    merged = copy.deepcopy(default_params)
    
    if custom_params:
        merged.update(custom_params)
    
    return merged


def apply_realtime_adjustments(
    base_prob: float,
    home_params: Dict,
    away_params: Dict,
    weights: Dict
) -> Tuple[float, Dict]:
    """
    应用实时参数调整
    
    Args:
        base_prob: 基础胜率
        home_params: 主队实时参数
        away_params: 客队实时参数
        weights: 权重配置
        
    Returns:
        (调整后胜率, 调整详情)
    """
    adjustments = {}
    adjusted_prob = base_prob
    
    # 1. 伤病影响调整
    injury_home = home_params.get('injury_impact', 0)
    injury_away = away_params.get('injury_impact', 0)
    injury_diff = injury_home - injury_away  # 负值对主队不利
    adjustments['injury_impact'] = {
        'home': injury_home,
        'away': injury_away,
        'effect': injury_diff,
        'description': f"伤病影响: {'+' if injury_diff >= 0 else ''}{injury_diff:.3f}"
    }
    adjusted_prob += injury_diff * weights.get('recent_form', 0.25)
    
    # 2. 休息天数调整
    rest_home = home_params.get('rest_days', 2)
    rest_away = away_params.get('rest_days', 2)
    # 休息天数越多越有利，但边际效益递减
    rest_home_factor = min(0.03, rest_home * 0.015)
    rest_away_factor = min(0.03, rest_away * 0.015)
    rest_diff = rest_home_factor - rest_away_factor
    adjustments['rest_days'] = {
        'home': rest_home,
        'away': rest_away,
        'effect': rest_diff,
        'description': f"休息调整: {'+' if rest_diff >= 0 else ''}{rest_diff:.3f}"
    }
    adjusted_prob += rest_diff
    
    # 3. 背靠背惩罚
    btb_penalty = 0
    if home_params.get('back_to_back', False):
        btb_penalty -= 0.02
    if away_params.get('back_to_back', False):
        btb_penalty += 0.02
    adjustments['back_to_back'] = {
        'home': home_params.get('back_to_back', False),
        'away': away_params.get('back_to_back', False),
        'effect': btb_penalty,
        'description': f"背靠背: {'+' if btb_penalty >= 0 else ''}{btb_penalty:.3f}"
    }
    adjusted_prob += btb_penalty
    
    # 4. 士气加成
    morale_home = home_params.get('morale_boost', 0)
    morale_away = away_params.get('morale_boost', 0)
    morale_diff = morale_home - morale_away
    adjustments['morale_boost'] = {
        'home': morale_home,
        'away': morale_away,
        'effect': morale_diff,
        'description': f"士气调整: {'+' if morale_diff >= 0 else ''}{morale_diff:.3f}"
    }
    adjusted_prob += morale_diff
    
    # 5. 缺阵球员信息
    home_players_out = home_params.get('key_player_out', [])
    away_players_out = away_params.get('key_player_out', [])
    adjustments['key_players_out'] = {
        'home': home_players_out,
        'away': away_players_out,
        'effect': 0,
        'description': f"缺阵: {', '.join(home_players_out) if home_players_out else '无'} vs {', '.join(away_players_out) if away_players_out else '无'}"
    }
    
    # 限制概率范围
    adjusted_prob = max(0.10, min(0.90, adjusted_prob))
    
    return adjusted_prob, adjustments


def calculate_weighted_probability(
    home_stats: Dict,
    away_stats: Dict,
    h2h: Dict,
    home_cluster: Optional[Dict],
    away_cluster: Optional[Dict],
    weights: Dict
) -> Tuple[float, Dict]:
    """
    使用可配置权重计算胜率
    
    Args:
        home_stats: 主队统计
        away_stats: 客队统计
        h2h: 历史对阵
        home_cluster: 主队聚类
        away_cluster: 客队聚类
        weights: 权重配置
        
    Returns:
        (主队胜率, 贡献因子)
    """
    base_prob = 0.5
    contributions = {}
    
    # 1. 近期状态 (权重可调)
    recent_weight = weights.get('recent_form', 0.25)
    home_recent = home_stats.get('recent_5_win_pct', 0.5)
    away_recent = away_stats.get('recent_5_win_pct', 0.5)
    recent_diff = home_recent - away_recent
    contributions['recent_form'] = {
        'home': round(home_recent, 4),
        'away': round(away_recent, 4),
        'diff': round(recent_diff, 4),
        'weight': recent_weight,
        'contribution': round(recent_diff * recent_weight, 4)
    }
    base_prob += recent_diff * recent_weight
    
    # 2. 进攻效率 (包含在efficiency_diff中)
    efficiency_weight = weights.get('efficiency_diff', 0.40)
    home_off = home_stats.get('offensive_rating', 110)
    away_off = away_stats.get('offensive_rating', 110)
    off_diff = (home_off - away_off) / 100
    
    home_def = home_stats.get('defensive_rating', 110)
    away_def = away_stats.get('defensive_rating', 110)
    def_diff = (away_def - home_def) / 100  # 防守越好贡献越大
    
    # 综合效率 = 进攻贡献 + 防守贡献
    net_diff = off_diff + def_diff
    contributions['efficiency'] = {
        'home_off': round(home_off, 1),
        'away_off': round(away_off, 1),
        'home_def': round(home_def, 1),
        'away_def': round(away_def, 1),
        'net_diff': round(net_diff, 4),
        'weight': efficiency_weight,
        'contribution': round(net_diff * efficiency_weight, 4)
    }
    base_prob += net_diff * efficiency_weight
    
    # 3. 主场优势 (权重可调)
    home_weight = weights.get('home_advantage', 0.15)
    home_home_win = home_stats.get('home_win_pct', 0.5)
    home_adv = (home_home_win - 0.5) * 0.5  # 主场胜率超出50%的部分
    contributions['home_advantage'] = {
        'home_win_pct': round(home_home_win, 4),
        'weight': home_weight,
        'contribution': round(home_adv * home_weight, 4)
    }
    base_prob += home_adv * home_weight
    
    # 4. 历史交锋 (权重可调)
    h2h_weight = weights.get('historical_matchup', 0.10)
    if h2h and h2h['total'] > 0:
        h2h_adv = (h2h['home_win_pct'] - 0.5) * 0.3
        contributions['historical_matchup'] = {
            'games': h2h['total'],
            'home_win_pct': round(h2h['home_win_pct'], 4),
            'weight': h2h_weight,
            'contribution': round(h2h_adv * h2h_weight, 4)
        }
        base_prob += h2h_adv * h2h_weight
    else:
        contributions['historical_matchup'] = {
            'games': 0,
            'weight': h2h_weight,
            'contribution': 0
        }
    
    # 5. 聚类风格 (权重可调)
    cluster_weight = weights.get('cluster_similarity', 0.10)
    if home_cluster and away_cluster:
        # 根据风格匹配调整
        style_modifier = 0.02
        contributions['style_matchup'] = {
            'home_style': home_cluster.get('style', 'Unknown'),
            'away_style': away_cluster.get('style', 'Unknown'),
            'weight': cluster_weight,
            'contribution': round(style_modifier * cluster_weight, 4)
        }
        base_prob += style_modifier * cluster_weight
    else:
        contributions['style_matchup'] = {
            'weight': cluster_weight,
            'contribution': 0
        }
    
    # 限制概率范围
    base_prob = max(0.15, min(0.85, base_prob))
    
    return base_prob, contributions


def predict_game_advanced(
    home_team: str,
    away_team: str,
    home_params: Optional[Dict] = None,
    away_params: Optional[Dict] = None,
    weights: Optional[Dict] = None,
    season: Optional[str] = None,
    use_recent_form: bool = True,
    return_details: bool = True
) -> Dict:
    """
    高级比赛预测接口 - 支持实时参数传入
    
    Args:
        home_team: 主队缩写 (如 'LAL')
        away_team: 客队缩写 (如 'BOS')
        home_params: 主队实时参数 (可选)
            - recent_win_pct: 近期胜率 (0-1)
            - home_advantage: 主场加成 (-0.1 to 0.1)
            - injury_impact: 伤病影响 (-0.3 to 0)
            - rest_days: 休息天数 (>=0)
            - back_to_back: 是否背靠背
            - key_player_out: 缺阵球员列表
            - morale_boost: 士气加成 (-0.15 to 0.15)
            - custom_rating: 自定义实力评分 (0-100)
        away_params: 客队实时参数 (同上)
        weights: 权重配置 (可选)
            - recent_form: 近期状态权重
            - home_advantage: 主场优势权重
            - historical_matchup: 历史交锋权重
            - efficiency_diff: 效率差权重
            - cluster_similarity: 风格相似度权重
        season: 赛季 (可选, 如 '2024-25')
        use_recent_form: 是否使用近期战绩 (默认True)
        return_details: 返回详细信息 (默认True)
        
    Returns:
        预测结果字典
    """
    print(f"\n{'='*60}")
    print(f"高级预测: {home_team} (主场) vs {away_team} (客场)")
    print(f"{'='*60}")
    
    # 参数验证
    if home_params:
        valid, msg = validate_params(home_params, 'home')
        if not valid:
            raise ValueError(f"主队参数错误: {msg}")
    
    if away_params:
        valid, msg = validate_params(away_params, 'away')
        if not valid:
            raise ValueError(f"客队参数错误: {msg}")
    
    if weights:
        valid, msg = validate_weights(weights)
        if not valid:
            raise ValueError(f"权重配置错误: {msg}")
    
    # 合并参数
    merged_home_params = merge_params(DEFAULT_HOME_PARAMS, home_params)
    merged_away_params = merge_params(DEFAULT_AWAY_PARAMS, away_params)
    merged_weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    
    print(f"\n📋 参数配置:")
    print(f"   主队参数: {merged_home_params}")
    print(f"   客队参数: {merged_away_params}")
    print(f"   权重配置: {merged_weights}")
    
    # 加载数据
    team_features, team_clusters, games = load_data()
    
    # 标准化球队名称
    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)
    
    # 获取球队统计
    home_stats = get_team_latest_stats(home_team, team_features, season)
    away_stats = get_team_latest_stats(away_team, team_features, season)
    
    # 获取聚类信息
    home_cluster = get_team_cluster(home_team, team_clusters)
    away_cluster = get_team_cluster(away_team, team_clusters)
    
    # 获取历史对阵
    h2h = get_head_to_head(home_team, away_team, games)
    
    # 检查数据完整性
    if not home_stats:
        print(f"[警告] 未找到 {home_team} 的统计数据，使用默认值")
        home_stats = {
            'win_pct': 0.5, 'home_win_pct': 0.5, 'offensive_rating': 110,
            'defensive_rating': 110, 'recent_5_win_pct': 0.5
        }
    if not away_stats:
        print(f"[警告] 未找到 {away_team} 的统计数据，使用默认值")
        away_stats = {
            'win_pct': 0.5, 'away_win_pct': 0.5, 'offensive_rating': 110,
            'defensive_rating': 110, 'recent_5_win_pct': 0.5
        }
    
    # 应用自定义近期胜率
    if merged_home_params.get('recent_win_pct') is not None and use_recent_form:
        home_stats['recent_5_win_pct'] = merged_home_params['recent_win_pct']
    if merged_away_params.get('recent_win_pct') is not None and use_recent_form:
        away_stats['recent_5_win_pct'] = merged_away_params['recent_win_pct']
    
    # 应用自定义主场加成
    if merged_home_params.get('home_advantage') is not None:
        home_stats['home_win_pct'] = 0.5 + merged_home_params['home_advantage']
    
    # 计算基础胜率（使用可配置权重）
    base_prob, contributions = calculate_weighted_probability(
        home_stats, away_stats, h2h, home_cluster, away_cluster, merged_weights
    )
    
    print(f"\n📊 基础胜率计算: {base_prob:.4f}")
    print(f"   各因子贡献: {contributions}")
    
    # 应用实时参数调整
    adjusted_prob, adjustments = apply_realtime_adjustments(
        base_prob, merged_home_params, merged_away_params, merged_weights
    )
    
    print(f"\n🔧 实时调整后胜率: {adjusted_prob:.4f}")
    for adj_name, adj_info in adjustments.items():
        print(f"   {adj_name}: {adj_info.get('description', '')}")
    
    # 分析关键因素
    key_factors = analyze_key_factors_advanced(
        home_team, away_team, home_stats, away_stats, 
        contributions, merged_home_params, merged_away_params
    )
    
    # 确定置信度
    confidence = determine_confidence_advanced(adjusted_prob, key_factors, h2h, adjustments)
    
    # 最终预测
    predicted_winner = home_team if adjusted_prob > 0.5 else away_team
    predicted_winner_cn = TEAM_NAMES_CN.get(predicted_winner, predicted_winner)
    home_win_prob = adjusted_prob
    away_win_prob = 1 - adjusted_prob
    
    # 构建结果
    result = {
        'prediction_id': f"ADV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'prediction_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'home_team': home_team,
        'home_team_cn': TEAM_NAMES_CN.get(home_team, home_team),
        'away_team': away_team,
        'away_team_cn': TEAM_NAMES_CN.get(away_team, away_team),
        'predicted_winner': predicted_winner,
        'predicted_winner_cn': predicted_winner_cn,
        'home_win_probability': round(home_win_prob, 4),
        'away_win_probability': round(away_win_prob, 4),
        'confidence_level': confidence,
        'key_factors': key_factors,
    }
    
    if return_details:
        # 添加详细信息
        result['model_inputs'] = {
            'home_stats': {k: round(v, 2) if isinstance(v, float) else v 
                          for k, v in home_stats.items() if isinstance(v, (int, float))},
            'away_stats': {k: round(v, 2) if isinstance(v, float) else v 
                          for k, v in away_stats.items() if isinstance(v, (int, float))},
            'weights_used': merged_weights,
        }
        
        result['adjustments_applied'] = {
            'base_probability': round(base_prob, 4),
            'final_probability': round(adjusted_prob, 4),
            'adjustment_details': adjustments,
            'contributions': contributions,
        }
        
        result['realtime_params'] = {
            'home_params': merged_home_params,
            'away_params': merged_away_params,
        }
        
        result['head_to_head'] = h2h
        result['home_cluster'] = home_cluster.get('style') if home_cluster else None
        result['away_cluster'] = away_cluster.get('style') if away_cluster else None
    
    # 打印结果
    print(f"\n📊 最终预测:")
    print(f"   {home_team} ({result['home_team_cn']}) 主场胜率: {home_win_prob*100:.1f}%")
    print(f"   {away_team} ({result['away_team_cn']}) 客场胜率: {away_win_prob*100:.1f}%")
    print(f"   预测获胜: {predicted_winner} ({predicted_winner_cn})")
    print(f"   置信度: {confidence}")
    
    if key_factors:
        print(f"\n🔑 关键因素:")
        for i, factor in enumerate(key_factors, 1):
            print(f"   {i}. {factor['description']}")
    
    return result


def analyze_key_factors_advanced(
    home_team: str,
    away_team: str,
    home_stats: Dict,
    away_stats: Dict,
    contributions: Dict,
    home_params: Dict,
    away_params: Dict
) -> List[Dict]:
    """
    分析关键因素（支持实时参数版本）
    
    Args:
        home_team: 主队
        away_team: 客队
        home_stats: 主队统计
        away_stats: 客队统计
        contributions: 因子贡献
        home_params: 主队实时参数
        away_params: 客队实时参数
        
    Returns:
        关键因素列表
    """
    key_factors = []
    
    home_cn = TEAM_NAMES_CN.get(normalize_team(home_team), home_team)
    away_cn = TEAM_NAMES_CN.get(normalize_team(away_team), away_team)
    
    # 1. 进攻效率
    home_off = home_stats.get('offensive_rating', 0)
    away_off = away_stats.get('offensive_rating', 0)
    if abs(home_off - away_off) > 2:
        winner = home_team if home_off > away_off else away_team
        winner_cn = home_cn if home_off > away_off else away_cn
        key_factors.append({
            'type': 'offense',
            'team': winner,
            'team_cn': winner_cn,
            'description': f'{winner_cn}进攻效率更优 ({max(home_off, away_off):.1f} vs {min(home_off, away_off):.1f})',
            'importance': abs(home_off - away_off) / 5,
            'contribution': contributions.get('efficiency', {}).get('contribution', 0)
        })
    
    # 2. 防守效率
    home_def = home_stats.get('defensive_rating', 0)
    away_def = away_stats.get('defensive_rating', 0)
    if abs(home_def - away_def) > 2:
        winner = home_team if home_def < away_def else away_team
        winner_cn = home_cn if home_def < away_def else away_cn
        key_factors.append({
            'type': 'defense',
            'team': winner,
            'team_cn': winner_cn,
            'description': f'{winner_cn}防守更稳固 ({min(home_def, away_def):.1f} vs {max(home_def, away_def):.1f})',
            'importance': abs(home_def - away_def) / 5,
            'contribution': contributions.get('efficiency', {}).get('contribution', 0)
        })
    
    # 3. 近期状态
    home_recent = home_stats.get('recent_5_win_pct', 0.5)
    away_recent = away_stats.get('recent_5_win_pct', 0.5)
    if abs(home_recent - away_recent) > 0.1:
        winner = home_team if home_recent > away_recent else away_team
        winner_cn = home_cn if home_recent > away_recent else away_cn
        key_factors.append({
            'type': 'form',
            'team': winner,
            'team_cn': winner_cn,
            'description': f'{winner_cn}近期状态更佳 ({(max(home_recent, away_recent)*100):.0f}% vs {(min(home_recent, away_recent)*100):.0f}%)',
            'importance': abs(home_recent - away_recent) * 5,
            'contribution': contributions.get('recent_form', {}).get('contribution', 0)
        })
    
    # 4. 主场优势
    home_home_win = home_stats.get('home_win_pct', 0.5)
    if home_home_win > 0.55:
        key_factors.append({
            'type': 'home',
            'team': home_team,
            'team_cn': home_cn,
            'description': f'{home_cn}主场强势 ({home_home_win*100:.0f}%胜率)',
            'importance': (home_home_win - 0.5) * 3,
            'contribution': contributions.get('home_advantage', {}).get('contribution', 0)
        })
    
    # 5. 伤病影响（实时参数）
    if home_params.get('injury_impact', 0) != 0:
        key_factors.append({
            'type': 'injury',
            'team': home_team,
            'team_cn': home_cn,
            'description': f'{home_cn}受到伤病影响 ({home_params["injury_impact"]:.2f})',
            'importance': abs(home_params['injury_impact']) * 10,
            'contribution': home_params['injury_impact']
        })
    
    if away_params.get('injury_impact', 0) != 0:
        key_factors.append({
            'type': 'injury',
            'team': away_team,
            'team_cn': away_cn,
            'description': f'{away_cn}受到伤病影响 ({away_params["injury_impact"]:.2f})',
            'importance': abs(away_params['injury_impact']) * 10,
            'contribution': away_params['injury_impact']
        })
    
    # 6. 背靠背（实时参数）
    if home_params.get('back_to_back', False):
        key_factors.append({
            'type': 'fatigue',
            'team': home_team,
            'team_cn': home_cn,
            'description': f'{home_cn}背靠背出战，体能堪忧',
            'importance': 2,
            'contribution': -0.02
        })
    
    if away_params.get('back_to_back', False):
        key_factors.append({
            'type': 'fatigue',
            'team': away_team,
            'team_cn': away_cn,
            'description': f'{away_cn}背靠背出战，体能堪忧',
            'importance': 2,
            'contribution': 0.02
        })
    
    # 7. 休息天数（实时参数）
    rest_diff = home_params.get('rest_days', 2) - away_params.get('rest_days', 2)
    if abs(rest_diff) >= 2:
        winner = home_team if rest_diff > 0 else away_team
        winner_cn = home_cn if rest_diff > 0 else away_cn
        key_factors.append({
            'type': 'rest',
            'team': winner,
            'team_cn': winner_cn,
            'description': f'{winner_cn}休息更充足 ({home_params.get("rest_days", 2)}天 vs {away_params.get("rest_days", 2)}天)',
            'importance': abs(rest_diff) * 1.5,
            'contribution': rest_diff * 0.015
        })
    
    # 按重要性排序
    key_factors = sorted(key_factors, key=lambda x: x['importance'], reverse=True)
    
    return key_factors[:6]


def determine_confidence_advanced(
    home_win_prob: float,
    key_factors: List[Dict],
    h2h: Dict,
    adjustments: Dict
) -> str:
    """
    确定预测置信度（支持实时参数版本）
    
    Args:
        home_win_prob: 主队胜率
        key_factors: 关键因素
        h2h: 对阵记录
        adjustments: 实时调整详情
        
    Returns:
        置信度等级 (HIGH/MEDIUM/LOW)
    """
    # 计算概率偏向程度
    prob_swing = abs(home_win_prob - 0.5) * 2  # 0-1范围
    
    # 因子数量和一致性
    factor_count = len(key_factors)
    
    # 因子贡献总和
    total_contribution = sum(abs(f.get('contribution', 0)) for f in key_factors)
    
    # 实时调整强度
    adjustment_count = sum(1 for adj in adjustments.values() 
                           if adj.get('effect', 0) != 0)
    adjustment_strength = min(1, adjustment_count * 0.15)
    
    # 历史数据支持度
    h2h_support = 0
    if h2h and h2h['total'] >= 3:
        h2h_support = min(0.2, h2h['total'] * 0.03)
    
    # 综合评分
    confidence_score = (
        prob_swing * 0.3 +
        min(factor_count / 5, 1) * 0.25 +
        min(total_contribution, 0.5) * 0.2 +
        adjustment_strength * 0.1 +
        h2h_support * 0.15
    )
    
    if confidence_score > 0.65:
        return "HIGH"
    elif confidence_score > 0.40:
        return "MEDIUM"
    else:
        return "LOW"


def visualize_prediction(result: Dict):
    """
    生成预测结果可视化
    
    Args:
        result: 预测结果字典
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    # 1. 胜率对比图
    ax1 = axes[0]
    teams = [result['home_team'], result['away_team']]
    probs = [result['home_win_probability'] * 100, result['away_win_probability'] * 100]
    colors = ['#4ECDC4', '#FF6B6B']
    
    bars = ax1.bar(teams, probs, color=colors, edgecolor='white', linewidth=2)
    ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.7)
    ax1.set_ylabel('Win Probability (%)', fontsize=12)
    ax1.set_title('Win Probability Comparison', fontsize=14, fontweight='bold')
    ax1.set_ylim(0, 100)
    
    # 添加数值标签
    for bar, prob in zip(bars, probs):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f'{prob:.1f}%', ha='center', fontsize=11, fontweight='bold')
    
    # 2. 关键指标雷达图
    ax2 = axes[1]
    ax2 = plt.subplot(132, polar=True)
    
    # 选择关键指标
    stats_labels = ['Points', 'Offense', 'Defense', 'Net Rating', 'eFG%']
    
    home_vals = [
        result['home_stats'].get('recent_5_avg_points', 0) / 2,  # 标准化
        result['home_stats'].get('offensive_rating', 110) / 2,
        120 - result['home_stats'].get('defensive_rating', 110),  # 反转（越小越好）
        result['home_stats'].get('net_rating', 0) + 10,  # 偏移到正数
        result['home_stats'].get('effective_fg_pct', 0.5) * 100
    ]
    
    away_vals = [
        result['away_stats'].get('recent_5_avg_points', 0) / 2,
        result['away_stats'].get('offensive_rating', 110) / 2,
        120 - result['away_stats'].get('defensive_rating', 110),
        result['away_stats'].get('net_rating', 0) + 10,
        result['away_stats'].get('effective_fg_pct', 0.5) * 100
    ]
    
    # 归一化到0-100
    max_vals = [max(h, a) for h, a in zip(home_vals, away_vals)]
    min_vals = [min(h, a) for h, a in zip(home_vals, away_vals)]
    
    for i in range(len(home_vals)):
        if max_vals[i] > min_vals[i]:
            home_vals[i] = (home_vals[i] - min_vals[i]) / (max_vals[i] - min_vals[i]) * 100
            away_vals[i] = (away_vals[i] - min_vals[i]) / (max_vals[i] - min_vals[i]) * 100
        else:
            home_vals[i] = 50
            away_vals[i] = 50
    
    angles = np.linspace(0, 2 * np.pi, len(stats_labels), endpoint=False).tolist()
    angles += angles[:1]
    home_vals += home_vals[:1]
    away_vals += away_vals[:1]
    
    ax2.plot(angles, home_vals, 'o-', linewidth=2, label=result['home_team'], color='#4ECDC4')
    ax2.fill(angles, home_vals, alpha=0.25, color='#4ECDC4')
    ax2.plot(angles, away_vals, 'o-', linewidth=2, label=result['away_team'], color='#FF6B6B')
    ax2.fill(angles, away_vals, alpha=0.25, color='#FF6B6B')
    
    ax2.set_xticks(angles[:-1])
    ax2.set_xticklabels(stats_labels, fontsize=10)
    ax2.set_ylim(0, 100)
    ax2.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
    ax2.set_title('Team Stats Comparison', fontsize=14, fontweight='bold', pad=20)
    
    # 3. 关键因素重要性
    ax3 = axes[2]
    
    if result['key_factors']:
        factors = [f['description'][:25] + '...' if len(f['description']) > 25 
                  else f['description'] for f in result['key_factors'][:5]]
        importance = [f['importance'] for f in result['key_factors'][:5]]
        
        colors_factor = ['#96CEB4' if f['team'] == result['home_team'] else '#DDA0DD' 
                        for f in result['key_factors'][:5]]
        
        y_pos = np.arange(len(factors))
        ax3.barh(y_pos, importance, color=colors_factor, edgecolor='white')
        ax3.set_yticks(y_pos)
        ax3.set_yticklabels(factors, fontsize=10)
        ax3.set_xlabel('Importance', fontsize=12)
        ax3.set_title('Key Factors', fontsize=14, fontweight='bold')
        
        # 添加图例
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#96CEB4', label=result['home_team']),
            Patch(facecolor='#DDA0DD', label=result['away_team'])
        ]
        ax3.legend(handles=legend_elements, loc='lower right')
    else:
        ax3.text(0.5, 0.5, 'No key factors available',
                ha='center', va='center', fontsize=12)
        ax3.set_title('Key Factors', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    # 保存图片
    filename = f"prediction_{result['home_team']}_vs_{result['away_team']}.png"
    filepath = OUTPUT_DIR / filename
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"\n📊 预测图表已保存: {filepath}")
    
    return filepath


def run_demo_predictions():
    """
    运行演示预测
    """
    print("\n" + "=" * 60)
    print("NBA比赛预测系统 - 演示预测")
    print("=" * 60)
    
    # 加载数据
    team_features, team_clusters, games = load_data()
    
    # 获取当前有数据的球队
    if len(team_features) > 0:
        available_teams = team_features['team_abbr'].unique()[:10]
    else:
        available_teams = ['LAL', 'GSW', 'BOS', 'MIA', 'DEN']
    
    print(f"\n可用球队: {', '.join(sorted(available_teams))}")
    
    # 预设几场经典对决
    demo_matchups = [
        ('LAL', 'BOS'),   # 湖人 vs 凯尔特人
        ('GSW', 'PHO'),  # 勇士 vs 太阳
        ('DEN', 'MIN'),  # 掘金 vs 森林狼
        ('MIA', 'BOS'),  # 热火 vs 凯尔特人
        ('DAL', 'LAC'),  # 独行侠 vs 快船
    ]
    
    # 过滤有效对阵
    valid_matchups = [(h, a) for h, a in demo_matchups 
                     if h in available_teams or a in available_teams]
    
    if valid_matchups:
        results = batch_predict(valid_matchups[:3])  # 限制3场
        
        # 生成可视化
        for result in results:
            if 'prediction_id' in result:
                visualize_prediction(result)
        
        return results
    
    return []


if __name__ == "__main__":
    # 运行演示预测
    results = run_demo_predictions()
