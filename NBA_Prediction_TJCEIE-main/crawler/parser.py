# -*- coding: utf-8 -*-
"""
数据解析器模块
负责解析和清洗从爬虫获取的原始数据
"""

import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import numpy as np

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from config import TEAM_INFO, RAW_FEATURES
from utils.logger import logger, log_function_call


class DataParser:
    """
    数据解析器类
    
    功能：
    - 解析和验证爬取的原始数据
    - 数据清洗和格式标准化
    - 转换为DataFrame格式
    - 生成衍生特征
    """
    
    def __init__(self):
        """初始化解析器"""
        self.team_info = TEAM_INFO
        logger.info("DataParser初始化完成")
    
    @log_function_call
    def parse_game_data(self, raw_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        解析比赛原始数据
        
        Args:
            raw_data: 爬虫返回的原始比赛数据列表
            
        Returns:
            标准化后的DataFrame
        """
        if not raw_data:
            logger.warning("原始数据为空")
            return pd.DataFrame()
        
        df = pd.DataFrame(raw_data)
        
        # 数据清洗
        df = self._clean_game_data(df)
        
        # 数据验证
        df = self._validate_game_data(df)
        
        logger.info(f"成功解析 {len(df)} 条比赛数据")
        return df
    
    def _clean_game_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        数据清洗
        """
        # 删除空值过多的行
        df = df.dropna(thresh=5)
        
        # 转换日期格式
        if 'game_date' in df.columns:
            df['game_date'] = pd.to_datetime(df['game_date'], errors='coerce')
        
        # 标准化球队名称
        df['team_abbr'] = df['team_abbr'].str.upper().str.strip()
        df['opponent_abbr'] = df['opponent_abbr'].str.upper().str.strip()
        
        # 映射完整球队名称
        df['team_name'] = df['team_abbr'].map(lambda x: self.team_info.get(x, {}).get('name', x))
        df['opponent_name'] = df['opponent_abbr'].map(lambda x: self.team_info.get(x, {}).get('name', x))
        df['team_id'] = df['team_abbr'].map(lambda x: self.team_info.get(x, {}).get('id', ''))
        df['opponent_id'] = df['opponent_abbr'].map(lambda x: self.team_info.get(x, {}).get('id', ''))
        
        # 转换数值列
        numeric_columns = ['points', 'opponent_points', 'point_diff', 'fg_made', 'fg_attempts',
                          'fg3_made', 'fg3_attempts', 'ft_made', 'ft_attempts', 'rebounds',
                          'assists', 'steals', 'blocks', 'turnovers', 'fouls']
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 计算命中率
        if 'fg_made' in df.columns and 'fg_attempts' in df.columns:
            df['fg_pct'] = np.where(df['fg_attempts'] > 0, 
                                   df['fg_made'] / df['fg_attempts'], 0)
        
        if 'fg3_made' in df.columns and 'fg3_attempts' in df.columns:
            df['fg3_pct'] = np.where(df['fg3_attempts'] > 0,
                                    df['fg3_made'] / df['fg3_attempts'], 0)
        
        if 'ft_made' in df.columns and 'ft_attempts' in df.columns:
            df['ft_pct'] = np.where(df['ft_attempts'] > 0,
                                   df['ft_made'] / df['ft_attempts'], 0)
        
        # 添加赛季信息
        if 'game_date' in df.columns:
            df['season'] = df['game_date'].apply(self._get_season)
        
        # 生成比赛ID
        df['game_id'] = df.apply(lambda x: self._generate_game_id(x), axis=1)
        
        return df
    
    def _get_season(self, date: datetime) -> str:
        """
        根据日期获取赛季字符串
        
        Args:
            date: 比赛日期
            
        Returns:
            赛季字符串，如 "2023-24"
        """
        if pd.isna(date):
            return ""
        
        year = date.year
        month = date.month
        
        # 如果是10月到12月，是当年开始的赛季
        # 如果是1月到6月，是上一年开始的赛季
        if month >= 10:
            return f"{year}-{str(year + 1)[2:]}"
        else:
            return f"{year - 1}-{str(year)[2:]}"
    
    def _generate_game_id(self, row: Dict[str, Any]) -> str:
        """
        生成比赛唯一ID
        
        格式: YYYYMMDDTEAM1TEAM2
        例如: 20260115LALGSW
        """
        if pd.isna(row.get('game_date')):
            return ""
        
        date_str = row['game_date'].strftime('%Y%m%d')
        team = row.get('team_abbr', '')
        opponent = row.get('opponent_abbr', '')
        
        # 确保主场在前
        if row.get('is_home', False):
            return f"{date_str}{opponent}{team}"
        else:
            return f"{date_str}{team}{opponent}"
    
    def _validate_game_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        数据验证
        """
        initial_len = len(df)
        
        # 过滤无效数据
        df = df[df['points'] >= 0]
        df = df[df['opponent_points'] >= 0]
        df = df[df['game_date'].notna()]
        
        # 检查比赛结果一致性
        if 'result' in df.columns:
            df['result_check'] = df.apply(
                lambda x: (x['result'] == 'W' and x['points'] > x['opponent_points']) or
                         (x['result'] == 'L' and x['points'] < x['opponent_points']),
                axis=1
            )
            # 只保留结果一致的数据
            df = df[df['result_check']]
            df = df.drop('result_check', axis=1)
        
        dropped = initial_len - len(df)
        if dropped > 0:
            logger.warning(f"验证阶段删除了 {dropped} 条不一致数据")
        
        return df
    
    @log_function_call
    def parse_season_stats(self, raw_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        解析球队赛季统计数据
        
        Args:
            raw_data: 原始赛季统计数据
            
        Returns:
            标准化后的DataFrame
        """
        if not raw_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(raw_data)
        
        # 标准化列名
        df = df.rename(columns={
            'games': 'games_played',
            'pts': 'total_points'
        })
        
        # 计算场均数据
        if 'games_played' in df.columns and 'total_points' in df.columns:
            df['avg_points'] = df['total_points'] / df['games_played']
        
        return df
    
    @log_function_call
    def compute_derived_features(self, df: pd.DataFrame, 
                                  window: int = 5) -> pd.DataFrame:
        """
        计算衍生特征
        
        Args:
            df: 原始比赛DataFrame
            window: 滚动窗口大小（默认5场）
            
        Returns:
            添加衍生特征后的DataFrame
        """
        if df.empty:
            return df
        
        logger.info(f"开始计算衍生特征，窗口大小: {window}")
        
        # 按球队和日期排序
        df = df.sort_values(['team_abbr', 'game_date'])
        
        # 计算滚动特征
        grouped = df.groupby('team_abbr')
        
        # 近N场平均得分
        df['recent_avg_points'] = grouped['points'].transform(
            lambda x: x.rolling(window=window, min_periods=1).mean()
        )
        
        # 近N场平均失分
        df['recent_avg_points_allowed'] = grouped['opponent_points'].transform(
            lambda x: x.rolling(window=window, min_periods=1).mean()
        )
        
        # 近N场胜率
        df['recent_win'] = (df['result'] == 'W').astype(int)
        df['recent_win_pct'] = grouped['recent_win'].transform(
            lambda x: x.rolling(window=window, min_periods=1).mean()
        )
        
        # 近N场平均篮板
        if 'rebounds' in df.columns:
            df['recent_avg_rebounds'] = grouped['rebounds'].transform(
                lambda x: x.rolling(window=window, min_periods=1).mean()
            )
        
        # 近N场平均助攻
        if 'assists' in df.columns:
            df['recent_avg_assists'] = grouped['assists'].transform(
                lambda x: x.rolling(window=window, min_periods=1).mean()
            )
        
        # 近N场平均三分命中率
        if 'fg3_pct' in df.columns:
            df['recent_avg_fg3_pct'] = grouped['fg3_pct'].transform(
                lambda x: x.rolling(window=window, min_periods=1).mean()
            )
        
        # 清理临时列
        df = df.drop('recent_win', axis=1, errors='ignore')
        
        logger.info("衍生特征计算完成")
        return df
    
    @log_function_call
    def compute_team_season_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算球队赛季汇总统计
        
        Args:
            df: 比赛数据DataFrame
            
        Returns:
            球队赛季统计DataFrame
        """
        if df.empty:
            return pd.DataFrame()
        
        # 按球队和赛季分组
        grouped = df.groupby(['team_abbr', 'season'])
        
        season_stats = grouped.agg({
            'game_id': 'count',
            'points': ['sum', 'mean'],
            'opponent_points': ['sum', 'mean'],
            'fg_pct': 'mean',
            'fg3_pct': 'mean',
            'ft_pct': 'mean',
            'rebounds': 'mean',
            'assists': 'mean',
            'steals': 'mean',
            'blocks': 'mean',
            'turnovers': 'mean',
            'fouls': 'mean',
            'result': lambda x: (x == 'W').sum()
        }).reset_index()
        
        # 扁平化列名
        season_stats.columns = ['team_abbr', 'season', 'games_played', 
                               'total_points', 'avg_points',
                               'total_points_allowed', 'avg_points_allowed',
                               'avg_fg_pct', 'avg_fg3_pct', 'avg_ft_pct',
                               'avg_rebounds', 'avg_assists', 'avg_steals',
                               'avg_blocks', 'avg_turnovers', 'avg_fouls', 'wins']
        
        # 计算负场和胜率
        season_stats['losses'] = season_stats['games_played'] - season_stats['wins']
        season_stats['win_pct'] = season_stats['wins'] / season_stats['games_played']
        
        # 计算净胜分
        season_stats['point_diff'] = season_stats['avg_points'] - season_stats['avg_points_allowed']
        
        # 添加球队完整信息
        season_stats['team_name'] = season_stats['team_abbr'].map(
            lambda x: self.team_info.get(x, {}).get('name', x)
        )
        season_stats['team_id'] = season_stats['team_abbr'].map(
            lambda x: self.team_info.get(x, {}).get('id', '')
        )
        
        # 计算主场和客场战绩
        home_stats = df[df['is_home'] == True].groupby(['team_abbr', 'season']).agg({
            'result': lambda x: (x == 'W').sum()
        }).reset_index()
        home_stats.columns = ['team_abbr', 'season', 'home_wins']
        
        away_stats = df[df['is_home'] == False].groupby(['team_abbr', 'season']).agg({
            'result': lambda x: (x == 'W').sum(),
            'game_id': 'count'
        }).reset_index()
        away_stats.columns = ['team_abbr', 'season', 'away_wins', 'away_games']
        
        # 合并主场客场数据
        season_stats = season_stats.merge(home_stats, on=['team_abbr', 'season'], how='left')
        season_stats = season_stats.merge(away_stats, on=['team_abbr', 'season'], how='left')
        
        season_stats['home_losses'] = season_stats['games_played'] // 2 - season_stats['home_wins']
        season_stats['home_win_pct'] = season_stats['home_wins'] / (season_stats['games_played'] // 2)
        season_stats['away_win_pct'] = season_stats['away_wins'] / season_stats['away_games']
        
        logger.info(f"计算了 {len(season_stats)} 条球队赛季统计")
        return season_stats
    
    @log_function_call
    def compute_head_to_head(self, df: pd.DataFrame, 
                             team1: str, team2: str,
                             min_games: int = 3) -> Dict[str, Any]:
        """
        计算两队历史对战数据
        
        Args:
            df: 比赛数据DataFrame
            team1: 球队1缩写
            team2: 球队2缩写
            min_games: 最少比赛场次
            
        Returns:
            对战统计数据
        """
        # 筛选两队对战数据
        h2h = df[
            ((df['team_abbr'] == team1) & (df['opponent_abbr'] == team2)) |
            ((df['team_abbr'] == team2) & (df['opponent_abbr'] == team1))
        ]
        
        if len(h2h) < min_games:
            return {'games': 0}
        
        # 分别计算各队战绩
        team1_wins = len(h2h[(h2h['team_abbr'] == team1) & (h2h['result'] == 'W')])
        team2_wins = len(h2h[(h2h['team_abbr'] == team2) & (h2h['result'] == 'W')])
        
        total_games = len(h2h)
        
        return {
            'total_games': total_games,
            team1: {
                'wins': team1_wins,
                'win_pct': team1_wins / total_games if total_games > 0 else 0
            },
            team2: {
                'wins': team2_wins,
                'win_pct': team2_wins / total_games if total_games > 0 else 0
            },
            'avg_point_diff': h2h['point_diff'].mean(),
            'recent_results': h2h.tail(5)[['game_date', 'team_abbr', 'result', 'points', 'opponent_points']].to_dict('records')
        }
    
    def format_prediction_data(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化预测结果数据
        
        Args:
            prediction: 原始预测数据
            
        Returns:
            格式化后的预测数据
        """
        formatted = prediction.copy()
        
        # 添加置信度等级
        prob = prediction.get('win_probability', 0.5)
        if prob >= 0.7:
            formatted['confidence'] = 'HIGH'
        elif prob >= 0.55:
            formatted['confidence'] = 'MEDIUM'
        else:
            formatted['confidence'] = 'LOW'
        
        # 格式化关键因素
        if 'key_factors' in formatted and isinstance(formatted['key_factors'], list):
            formatted['key_factors'] = formatted['key_factors']
        
        # 添加预测时间
        formatted['created_at'] = datetime.now().isoformat()
        
        return formatted
    
    def export_to_csv(self, df: pd.DataFrame, filename: str) -> str:
        """
        导出数据到CSV
        
        Args:
            df: DataFrame
            filename: 文件名
            
        Returns:
            保存的文件路径
        """
        output_path = Path(__file__).parent.parent / 'data' / 'processed' / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"数据已导出到: {output_path}")
        
        return str(output_path)


# 测试代码
if __name__ == '__main__':
    parser = DataParser()
    
    # 测试数据
    sample_data = [
        {
            'game_date': '2024-01-15',
            'team_abbr': 'LAL',
            'opponent_abbr': 'GSW',
            'is_home': True,
            'result': 'W',
            'points': 118,
            'opponent_points': 112,
            'fg_made': 45,
            'fg_attempts': 92,
            'fg3_made': 16,
            'fg3_attempts': 38,
            'ft_made': 12,
            'ft_attempts': 15,
            'rebounds': 47,
            'assists': 28,
            'steals': 9,
            'blocks': 5,
            'turnovers': 14,
            'fouls': 18
        }
    ]
    
    df = parser.parse_game_data(sample_data)
    print(df)
    
    print("\n数据解析测试完成")
