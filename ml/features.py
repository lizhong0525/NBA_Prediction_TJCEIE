# -*- coding: utf-8 -*-
"""
特征工程模块
负责从原始比赛数据计算衍生特征

功能：
- 计算滚动统计特征（近5场表现）
- 计算累计统计特征（赛季主场/客场胜率）
- 计算高级效率指标（进攻/防守效率、净效率值）
- 计算投篮效率指标（有效命中率、真实命中率）
"""

import numpy as np
import pandas as pd
import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# ==================== 配置 ====================
DATABASE_PATH = Path(__file__).parent.parent / 'data' / 'nba.db'
OUTPUT_DIR = Path(__file__).parent.parent / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)


def load_game_data(db_path: str = None) -> pd.DataFrame:
    """
    从数据库加载比赛数据
    
    Args:
        db_path: 数据库路径
        
    Returns:
        比赛数据DataFrame
    """
    if db_path is None:
        db_path = DATABASE_PATH
    
    conn = sqlite3.connect(db_path)
    
    # 查询数据并按日期排序
    query = """
        SELECT 
            id, game_id, game_date, season, team_id, team_abbr, team_name,
            opponent_id, opponent_abbr, opponent_name, is_home, result,
            points, opponent_points, point_diff,
            fg_made, fg_attempts, fg_pct,
            fg3_made, fg3_attempts, fg3_pct,
            ft_made, ft_attempts, ft_pct,
            rebounds, assists, steals, blocks, turnovers, fouls,
            plus_minus
        FROM team_game_stats
        ORDER BY team_abbr, game_date
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"[特征工程] 加载数据完成: {len(df)} 条记录, {df['team_abbr'].nunique()} 支球队")
    
    return df


def normalize_team_abbr(df: pd.DataFrame) -> pd.DataFrame:
    """
    标准化球队缩写（处理历史名称变更）
    
    Args:
        df: 原始数据
        
    Returns:
        标准化后的数据
    """
    # 球队缩写映射（新名称 -> 统一名称）
    abbr_mapping = {
        'BKN': 'BRK',  # Brooklyn Nets
        'CHA': 'CHO',  # Charlotte Hornets  
        'NO': 'NOP',   # New Orleans Pelicans
        'NY': 'NYK',   # New York Knicks
        'PHX': 'PHO',  # Phoenix Suns
        'GS': 'GSW',   # Golden State Warriors
    }
    
    df = df.copy()
    df['team_abbr'] = df['team_abbr'].replace(abbr_mapping)
    
    return df


def calculate_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算滚动统计特征（近5场）
    
    特征包括：
    - recent_5_win_pct: 近5场胜率
    - recent_5_avg_points: 近5场平均得分
    - recent_5_avg_points_allowed: 近5场平均失分
    
    Args:
        df: 原始比赛数据（已按team_abbr和game_date排序）
        
    Returns:
        添加了滚动特征的DataFrame
    """
    print("\n[特征工程] 计算滚动统计特征（近5场）...")
    
    df = df.copy()
    
    # 创建胜负数值（1=胜, 0=负）
    df['win'] = (df['result'] == 'W').astype(int)
    
    # 按球队分组计算滚动统计
    rolling_features = []
    
    for team in df['team_abbr'].unique():
        team_df = df[df['team_abbr'] == team].copy()
        team_df = team_df.sort_values('game_date')
        
        # 计算近5场滚动统计
        team_df['recent_5_win_pct'] = team_df['win'].rolling(window=5, min_periods=1).mean()
        team_df['recent_5_avg_points'] = team_df['points'].rolling(window=5, min_periods=1).mean()
        team_df['recent_5_avg_points_allowed'] = team_df['opponent_points'].rolling(window=5, min_periods=1).mean()
        
        rolling_features.append(team_df)
    
    result_df = pd.concat(rolling_features, ignore_index=True)
    
    print(f"  - 完成 {result_df['team_abbr'].nunique()} 支球队的滚动特征计算")
    
    return result_df


def calculate_seasonal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算赛季累计特征
    
    特征包括：
    - home_win_pct: 主场胜率
    - away_win_pct: 客场胜率
    - point_diff_avg: 场均分差
    
    Args:
        df: 原始比赛数据
        
    Returns:
        添加了赛季特征的DataFrame
    """
    print("\n[特征工程] 计算赛季累计特征...")
    
    df = df.copy()
    
    # 创建胜负数值
    df['win'] = (df['result'] == 'W').astype(int)
    
    # 按球队+赛季+主客场分组
    seasonal_features = []
    
    for (team, season), group in df.groupby(['team_abbr', 'season']):
        group = group.sort_values('game_date')
        
        # 主场比赛
        home_games = group[group['is_home'] == 1]
        # 客场比赛
        away_games = group[group['is_home'] == 0]
        
        # 累计计算（每场比赛后更新）
        home_results = []
        away_results = []
        
        home_wins = 0
        home_total = 0
        away_wins = 0
        away_total = 0
        point_diffs = []
        
        for idx, row in group.iterrows():
            if row['is_home'] == 1:
                home_total += 1
                home_wins += row['win']
                home_win_pct = home_wins / home_total if home_total > 0 else 0
                away_win_pct = away_wins / away_total if away_total > 0 else 0
            else:
                away_total += 1
                away_wins += row['win']
                home_win_pct = home_wins / home_total if home_total > 0 else 0
                away_win_pct = away_wins / away_total if away_total > 0 else 0
            
            point_diffs.append(row['point_diff'] if len(point_diffs) == 0 else 
                              (point_diffs[-1] * 0.9 + row['point_diff'] * 0.1))  # 移动平均
            
            home_results.append({
                'id': idx,
                'home_win_pct': home_win_pct,
                'away_win_pct': away_win_pct,
                'point_diff_avg': np.mean(point_diffs[-10:]) if len(point_diffs) >= 5 else np.mean(point_diffs)
            })
        
        # 简化处理：使用分组聚合
        group['home_win_pct'] = home_games['win'].expanding().mean().reindex(group.index).fillna(0)
        group['away_win_pct'] = away_games['win'].expanding().mean().reindex(group.index).fillna(0)
        group['point_diff_avg'] = group['point_diff'].expanding().mean().reindex(group.index).fillna(0)
        
        seasonal_features.append(group)
    
    result_df = pd.concat(seasonal_features, ignore_index=True)
    
    print(f"  - 完成 {result_df['team_abbr'].nunique()} 支球队的赛季特征计算")
    
    return result_df


def calculate_advanced_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算高级效率指标
    
    特征包括：
    - offensive_rating: 进攻效率（每100回合得分，估算）
    - defensive_rating: 防守效率（每100回合失分，估算）
    - net_rating: 净效率值
    - pace: 比赛节奏（估算回合数）
    - effective_fg_pct: 有效命中率 = (FGM + 0.5*3PM) / FGA
    - true_shooting_pct: 真实命中率 = 得分 / (2*(FGA + 0.44*FTA))
    
    Args:
        df: 原始比赛数据
        
    Returns:
        添加了高级特征的DataFrame
    """
    print("\n[特征工程] 计算高级效率指标...")
    
    df = df.copy()
    
    # 有效命中率 (eFG%)
    # eFG% = (FGM + 0.5 * 3PM) / FGA
    df['effective_fg_pct'] = (df['fg_made'] + 0.5 * df['fg3_made']) / df['fg_attempts']
    df['effective_fg_pct'] = df['effective_fg_pct'].fillna(0).replace([np.inf, -np.inf], 0)
    
    # 真实命中率 (TS%)
    # TS% = 得分 / (2 * (FGA + 0.44 * FTA))
    df['true_shooting_pct'] = df['points'] / (2 * (df['fg_attempts'] + 0.44 * df['ft_attempts']))
    df['true_shooting_pct'] = df['true_shooting_pct'].fillna(0).replace([np.inf, -np.inf], 0)
    
    # 进攻效率估算（简化版：使用得分和估算的回合数）
    # 回合数 ≈ FGA - ORB + TOV + 0.44 * FTA
    df['possessions'] = df['fg_attempts'] - df['rebounds'] + df['turnovers'] + 0.44 * df['ft_attempts']
    df['possessions'] = df['possessions'].replace(0, 1)  # 避免除零
    
    # 进攻效率（每100回合得分）
    df['offensive_rating'] = (df['points'] / df['possessions']) * 100
    
    # 防守效率（每100回合失分）
    df['defensive_rating'] = (df['opponent_points'] / df['possessions']) * 100
    
    # 净效率值
    df['net_rating'] = df['offensive_rating'] - df['defensive_rating']
    
    # 比赛节奏（每48分钟回合数）
    df['pace'] = (df['possessions'] / 48) * 100  # 标准化到100回合
    
    # 清理临时列
    df = df.drop(columns=['possessions'], errors='ignore')
    
    print(f"  - 效率指标计算完成")
    print(f"    进攻效率范围: {df['offensive_rating'].min():.1f} - {df['offensive_rating'].max():.1f}")
    print(f"    防守效率范围: {df['defensive_rating'].min():.1f} - {df['defensive_rating'].max():.1f}")
    print(f"    净效率范围: {df['net_rating'].min():.1f} - {df['net_rating'].max():.1f}")
    
    return df


def calculate_team_season_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算球队赛季平均特征（用于聚类分析）
    
    Args:
        df: 包含所有衍生特征的比赛数据
        
    Returns:
        球队赛季平均特征DataFrame
    """
    print("\n[特征工程] 计算球队赛季平均特征...")
    
    # 需要聚合的特征列
    feature_cols = [
        'points', 'opponent_points', 'point_diff',
        'fg_pct', 'fg3_pct', 'ft_pct',
        'rebounds', 'assists', 'steals', 'blocks', 'turnovers', 'fouls',
        'recent_5_win_pct', 'recent_5_avg_points', 'recent_5_avg_points_allowed',
        'home_win_pct', 'away_win_pct', 'point_diff_avg',
        'offensive_rating', 'defensive_rating', 'net_rating',
        'effective_fg_pct', 'true_shooting_pct', 'pace'
    ]
    
    # 过滤存在的列
    available_cols = [col for col in feature_cols if col in df.columns]
    
    # 按球队+赛季分组计算平均值
    team_season_features = df.groupby(['team_abbr', 'season']).agg({
        col: 'mean' for col in available_cols
    }).reset_index()
    
    # 添加比赛场次
    game_counts = df.groupby(['team_abbr', 'season']).size().reset_index(name='games_played')
    team_season_features = team_season_features.merge(game_counts, on=['team_abbr', 'season'])
    
    # 添加胜负记录
    win_records = df.groupby(['team_abbr', 'season']).agg({
        'win': ['sum', 'count']
    }).reset_index()
    win_records.columns = ['team_abbr', 'season', 'wins', 'total_games']
    win_records['season_win_pct'] = win_records['wins'] / win_records['total_games']
    
    team_season_features = team_season_features.merge(
        win_records[['team_abbr', 'season', 'wins', 'total_games', 'season_win_pct']], 
        on=['team_abbr', 'season']
    )
    
    print(f"  - 生成 {len(team_season_features)} 条球队赛季特征记录")
    print(f"  - 涵盖 {team_season_features['team_abbr'].nunique()} 支球队")
    
    return team_season_features


def save_to_database(df: pd.DataFrame, table_name: str = 'team_features'):
    """
    保存特征数据到数据库
    
    Args:
        df: 特征数据
        table_name: 表名
    """
    print(f"\n[特征工程] 保存特征到数据库表: {table_name}")
    
    conn = sqlite3.connect(DATABASE_PATH)
    
    # 如果表存在，先删除
    cursor = conn.cursor()
    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    conn.commit()
    
    # 保存到数据库
    df.to_sql(table_name, conn, index=False, if_exists='replace')
    
    conn.close()
    
    print(f"  - 已保存 {len(df)} 条记录到 {table_name} 表")


def save_to_csv(df: pd.DataFrame, filename: str = 'team_features.csv'):
    """
    导出特征数据到CSV
    
    Args:
        df: 特征数据
        filename: 文件名
    """
    filepath = OUTPUT_DIR / filename
    
    print(f"\n[特征工程] 导出特征到CSV: {filepath}")
    
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    
    print(f"  - 已导出 {len(df)} 条记录")


def run_feature_engineering():
    """
    运行完整的特征工程流程
    """
    print("=" * 60)
    print("NBA比赛预测系统 - 特征工程模块")
    print("=" * 60)
    
    start_time = datetime.now()
    
    # 1. 加载原始数据
    print("\n[步骤 1/5] 加载原始比赛数据...")
    df = load_game_data()
    
    # 2. 标准化球队缩写
    print("\n[步骤 2/5] 标准化球队名称...")
    df = normalize_team_abbr(df)
    
    # 3. 计算滚动统计特征
    print("\n[步骤 3/5] 计算滚动统计特征...")
    df = calculate_rolling_features(df)
    
    # 4. 计算赛季累计特征
    print("\n[步骤 4/5] 计算赛季累计特征...")
    df = calculate_seasonal_features(df)
    
    # 5. 计算高级效率指标
    print("\n[步骤 5/5] 计算高级效率指标...")
    df = calculate_advanced_features(df)
    
    # 计算球队赛季平均特征
    team_season_features = calculate_team_season_features(df)
    
    # 保存结果
    save_to_database(team_season_features, 'team_features')
    save_to_csv(team_season_features, 'team_features.csv')
    
    # 也保存详细比赛级别特征
    save_to_database(df[['game_id', 'game_date', 'season', 'team_abbr', 'team_name',
                         'recent_5_win_pct', 'recent_5_avg_points', 'recent_5_avg_points_allowed',
                         'home_win_pct', 'away_win_pct', 'point_diff_avg',
                         'offensive_rating', 'defensive_rating', 'net_rating',
                         'effective_fg_pct', 'true_shooting_pct', 'pace']], 
                    'game_features')
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "=" * 60)
    print("特征工程完成!")
    print(f"总耗时: {duration:.2f} 秒")
    print("=" * 60)
    
    return team_season_features, df


if __name__ == "__main__":
    team_features, game_features = run_feature_engineering()
