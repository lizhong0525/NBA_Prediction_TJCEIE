# -*- coding: utf-8 -*-
"""
数据库管理模块
负责SQLite数据库的创建、表结构和数据操作
"""

import sqlite3
from typing import List, Dict, Optional, Any
from pathlib import Path
from contextlib import contextmanager
import pandas as pd
from datetime import datetime

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from config import DATABASE_CONFIG
from utils import logger, log_function_call


class DatabaseManager:
    """
    SQLite数据库管理器
    
    功能：
    - 数据库连接管理
    - 创建数据表
    - 增删改查操作
    - 数据导入导出
    """
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径，默认使用配置中的路径
        """
        if db_path is None:
            db_path = str(DATABASE_CONFIG['path'])
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.connection = None
        logger.info(f"数据库管理器初始化，数据库路径: {self.db_path}")
    
    def connect(self):
        """建立数据库连接"""
        if self.connection is None:
            self.connection = sqlite3.connect(
                self.db_path,
                timeout=DATABASE_CONFIG.get('timeout', 30),
                check_same_thread=DATABASE_CONFIG.get('check_same_thread', False)
            )
            # 启用外键约束
            self.connection.execute("PRAGMA foreign_keys = ON")
            logger.info("数据库连接已建立")
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("数据库连接已关闭")
    
    @contextmanager
    def get_cursor(self):
        """
        获取数据库游标的上下文管理器
        
        Usage:
            with db.get_cursor() as cursor:
                cursor.execute(...)
        """
        if self.connection is None:
            self.connect()
        
        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            cursor.close()
    
    @log_function_call
    def create_tables(self):
        """
        创建所有数据表
        """
        self.connect()
        
        with self.get_cursor() as cursor:
            # 球队比赛数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_game_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id VARCHAR(30) UNIQUE NOT NULL,
                    game_date DATE NOT NULL,
                    season VARCHAR(10) NOT NULL,
                    team_id VARCHAR(20) NOT NULL,
                    team_abbr VARCHAR(10) NOT NULL,
                    team_name VARCHAR(100),
                    opponent_id VARCHAR(20) NOT NULL,
                    opponent_abbr VARCHAR(10) NOT NULL,
                    opponent_name VARCHAR(100),
                    is_home BOOLEAN DEFAULT 0,
                    result VARCHAR(1),
                    points INTEGER,
                    opponent_points INTEGER,
                    point_diff INTEGER,
                    fg_made INTEGER,
                    fg_attempts INTEGER,
                    fg_pct REAL,
                    fg3_made INTEGER,
                    fg3_attempts INTEGER,
                    fg3_pct REAL,
                    ft_made INTEGER,
                    ft_attempts INTEGER,
                    ft_pct REAL,
                    rebounds INTEGER,
                    assists INTEGER,
                    steals INTEGER,
                    blocks INTEGER,
                    turnovers INTEGER,
                    fouls INTEGER,
                    plus_minus INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_date ON team_game_stats(game_date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_team_season ON team_game_stats(team_abbr, season)
            """)
            
            # 球队赛季统计表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_season_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id VARCHAR(20) NOT NULL,
                    team_abbr VARCHAR(10) NOT NULL,
                    team_name VARCHAR(100),
                    season VARCHAR(10) NOT NULL,
                    games_played INTEGER,
                    wins INTEGER,
                    losses INTEGER,
                    win_pct REAL,
                    avg_points REAL,
                    avg_points_allowed REAL,
                    avg_fg_pct REAL,
                    avg_fg3_pct REAL,
                    avg_ft_pct REAL,
                    avg_rebounds REAL,
                    avg_assists REAL,
                    avg_steals REAL,
                    avg_blocks REAL,
                    avg_turnovers REAL,
                    avg_fouls REAL,
                    home_wins INTEGER,
                    home_losses INTEGER,
                    home_win_pct REAL,
                    away_wins INTEGER,
                    away_games INTEGER,
                    away_win_pct REAL,
                    point_diff REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(team_id, season)
                )
            """)
            
            # 球员数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id VARCHAR(30) UNIQUE,
                    player_name VARCHAR(100) NOT NULL,
                    team_id VARCHAR(20),
                    team_abbr VARCHAR(10),
                    season VARCHAR(10) NOT NULL,
                    position VARCHAR(10),
                    games_played INTEGER,
                    games_started INTEGER,
                    minutes REAL,
                    points REAL,
                    rebounds REAL,
                    assists REAL,
                    steals REAL,
                    blocks REAL,
                    fg_pct REAL,
                    fg3_pct REAL,
                    ft_pct REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 预测结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prediction_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_id VARCHAR(30) UNIQUE NOT NULL,
                    game_id VARCHAR(30),
                    home_team VARCHAR(100) NOT NULL,
                    away_team VARCHAR(100) NOT NULL,
                    predicted_winner VARCHAR(100),
                    win_probability REAL,
                    confidence_level VARCHAR(20),
                    key_factors TEXT,
                    model_version VARCHAR(20),
                    actual_result VARCHAR(1),
                    is_correct BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 球队风格分类表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_clusters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id VARCHAR(20) NOT NULL,
                    team_abbr VARCHAR(10) NOT NULL,
                    team_name VARCHAR(100),
                    season VARCHAR(10) NOT NULL,
                    cluster_label INTEGER,
                    cluster_name VARCHAR(50),
                    cluster_features TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(team_id, season)
                )
            """)
            
            # 爬虫任务日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawl_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type VARCHAR(50) NOT NULL,
                    target VARCHAR(100),
                    status VARCHAR(20),
                    records_fetched INTEGER DEFAULT 0,
                    error_message TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        logger.info("数据库表创建完成")
    
    @log_function_call
    def insert_game_data(self, games: List[Dict[str, Any]]) -> int:
        """
        批量插入比赛数据
        
        Args:
            games: 比赛数据列表
            
        Returns:
            插入的记录数
        """
        if not games:
            return 0
        
        self.connect()
        
        insert_sql = """
            INSERT OR REPLACE INTO team_game_stats 
            (game_id, game_date, season, team_id, team_abbr, team_name,
             opponent_id, opponent_abbr, opponent_name, is_home, result,
             points, opponent_points, point_diff, fg_made, fg_attempts, fg_pct,
             fg3_made, fg3_attempts, fg3_pct, ft_made, ft_attempts, ft_pct,
             rebounds, assists, steals, blocks, turnovers, fouls)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        count = 0
        with self.get_cursor() as cursor:
            for game in games:
                values = (
                    game.get('game_id', ''),
                    game.get('game_date', ''),
                    game.get('season', ''),
                    game.get('team_id', ''),
                    game.get('team_abbr', ''),
                    game.get('team_name', ''),
                    game.get('opponent_id', ''),
                    game.get('opponent_abbr', ''),
                    game.get('opponent_name', ''),
                    int(game.get('is_home', False)),
                    game.get('result', ''),
                    game.get('points', 0),
                    game.get('opponent_points', 0),
                    game.get('point_diff', 0),
                    game.get('fg_made', 0),
                    game.get('fg_attempts', 0),
                    game.get('fg_pct', 0),
                    game.get('fg3_made', 0),
                    game.get('fg3_attempts', 0),
                    game.get('fg3_pct', 0),
                    game.get('ft_made', 0),
                    game.get('ft_attempts', 0),
                    game.get('ft_pct', 0),
                    game.get('rebounds', 0),
                    game.get('assists', 0),
                    game.get('steals', 0),
                    game.get('blocks', 0),
                    game.get('turnovers', 0),
                    game.get('fouls', 0)
                )
                cursor.execute(insert_sql, values)
                count += 1
        
        logger.info(f"成功插入 {count} 条比赛数据")
        return count
    
    @log_function_call
    def insert_season_stats(self, stats: List[Dict[str, Any]]) -> int:
        """
        批量插入球队赛季统计
        
        Args:
            stats: 赛季统计数据列表
            
        Returns:
            插入的记录数
        """
        if not stats:
            return 0
        
        self.connect()
        
        insert_sql = """
            INSERT OR REPLACE INTO team_season_stats
            (team_id, team_abbr, team_name, season, games_played, wins, losses,
             win_pct, avg_points, avg_points_allowed, avg_fg_pct, avg_fg3_pct,
             avg_ft_pct, avg_rebounds, avg_assists, avg_steals, avg_blocks,
             avg_turnovers, avg_fouls, home_wins, home_losses, home_win_pct,
             away_wins, away_games, away_win_pct, point_diff)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        count = 0
        with self.get_cursor() as cursor:
            for stat in stats:
                values = (
                    stat.get('team_id', ''),
                    stat.get('team_abbr', ''),
                    stat.get('team_name', ''),
                    stat.get('season', ''),
                    stat.get('games_played', 0),
                    stat.get('wins', 0),
                    stat.get('losses', 0),
                    stat.get('win_pct', 0),
                    stat.get('avg_points', 0),
                    stat.get('avg_points_allowed', 0),
                    stat.get('avg_fg_pct', 0),
                    stat.get('avg_fg3_pct', 0),
                    stat.get('avg_ft_pct', 0),
                    stat.get('avg_rebounds', 0),
                    stat.get('avg_assists', 0),
                    stat.get('avg_steals', 0),
                    stat.get('avg_blocks', 0),
                    stat.get('avg_turnovers', 0),
                    stat.get('avg_fouls', 0),
                    stat.get('home_wins', 0),
                    stat.get('home_losses', 0),
                    stat.get('home_win_pct', 0),
                    stat.get('away_wins', 0),
                    stat.get('away_games', 0),
                    stat.get('away_win_pct', 0),
                    stat.get('point_diff', 0)
                )
                cursor.execute(insert_sql, values)
                count += 1
        
        logger.info(f"成功插入 {count} 条赛季统计")
        return count
    
    @log_function_call
    def insert_prediction(self, prediction: Dict[str, Any]) -> bool:
        """
        插入预测结果
        
        Args:
            prediction: 预测数据字典
            
        Returns:
            是否成功
        """
        self.connect()
        
        insert_sql = """
            INSERT INTO prediction_results
            (prediction_id, game_id, home_team, away_team, predicted_winner,
             win_probability, confidence_level, key_factors, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        import json
        
        with self.get_cursor() as cursor:
            cursor.execute(insert_sql, (
                prediction.get('prediction_id', ''),
                prediction.get('game_id', ''),
                prediction.get('home_team', ''),
                prediction.get('away_team', ''),
                prediction.get('predicted_winner', ''),
                prediction.get('win_probability', 0.5),
                prediction.get('confidence_level', 'MEDIUM'),
                json.dumps(prediction.get('key_factors', [])),
                prediction.get('model_version', '1.0')
            ))
        
        return True
    
    def get_game_data(self, team_abbr: str = None, season: str = None, 
                      limit: int = 100) -> pd.DataFrame:
        """
        获取比赛数据
        
        Args:
            team_abbr: 球队缩写
            season: 赛季
            limit: 返回条数限制
            
        Returns:
            DataFrame格式的比赛数据
        """
        self.connect()
        
        query = "SELECT * FROM team_game_stats WHERE 1=1"
        params = []
        
        if team_abbr:
            query += " AND (team_abbr = ? OR opponent_abbr = ?)"
            params.extend([team_abbr, team_abbr])
        
        if season:
            query += " AND season = ?"
            params.append(season)
        
        query += " ORDER BY game_date DESC LIMIT ?"
        params.append(limit)
        
        df = pd.read_sql_query(query, self.connection, params=params)
        return df
    
    def get_team_season_stats(self, team_abbr: str = None, 
                              season: str = None) -> pd.DataFrame:
        """
        获取球队赛季统计
        
        Args:
            team_abbr: 球队缩写
            season: 赛季
            
        Returns:
            DataFrame格式的赛季统计
        """
        self.connect()
        
        query = "SELECT * FROM team_season_stats WHERE 1=1"
        params = []
        
        if team_abbr:
            query += " AND team_abbr = ?"
            params.append(team_abbr)
        
        if season:
            query += " AND season = ?"
            params.append(season)
        
        query += " ORDER BY win_pct DESC"
        
        df = pd.read_sql_query(query, self.connection, params=params)
        return df
    
    def get_recent_predictions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的预测记录
        
        Args:
            limit: 返回条数
            
        Returns:
            预测记录列表
        """
        self.connect()
        
        query = """
            SELECT * FROM prediction_results 
            ORDER BY created_at DESC 
            LIMIT ?
        """
        
        df = pd.read_sql_query(query, self.connection, params=[limit])
        
        # 转换日期格式
        df['created_at'] = pd.to_datetime(df['created_at'])
        
        return df.to_dict('records')
    
    def get_prediction_accuracy(self) -> Dict[str, Any]:
        """
        获取预测准确率统计
        
        Returns:
            准确率统计字典
        """
        self.connect()
        
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
                AVG(CASE WHEN is_correct = 1 THEN 1.0 ELSE 0.0 END) as accuracy,
                AVG(win_probability) as avg_confidence
            FROM prediction_results
            WHERE is_correct IS NOT NULL
        """
        
        df = pd.read_sql_query(query, self.connection)
        
        if len(df) > 0:
            return df.iloc[0].to_dict()
        return {'total': 0, 'correct': 0, 'accuracy': 0}
    
    def update_prediction_result(self, prediction_id: str, actual_result: str) -> bool:
        """
        更新预测结果
        
        Args:
            prediction_id: 预测ID
            actual_result: 实际结果（W/L）
            
        Returns:
            是否成功
        """
        self.connect()
        
        query = """
            UPDATE prediction_results 
            SET actual_result = ?,
                is_correct = CASE 
                    WHEN predicted_winner LIKE ? THEN 1 
                    ELSE 0 
                END
            WHERE prediction_id = ?
        """
        
        # 判断预测是否正确（简化逻辑）
        with self.get_cursor() as cursor:
            cursor.execute(query, (actual_result, f'%{actual_result}%', prediction_id))
        
        return True
    
    def execute_query(self, query: str, params: tuple = None) -> List[tuple]:
        """
        执行自定义查询
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        self.connect()
        
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()
    
    def get_table_stats(self) -> Dict[str, int]:
        """
        获取各表记录数统计
        
        Returns:
            表名和记录数字典
        """
        self.connect()
        
        tables = ['team_game_stats', 'team_season_stats', 'player_stats', 
                 'prediction_results', 'team_clusters']
        
        stats = {}
        with self.get_cursor() as cursor:
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
        
        return stats


def init_database(db_path: str = None) -> DatabaseManager:
    """
    初始化数据库
    
    Args:
        db_path: 数据库路径
        
    Returns:
        DatabaseManager实例
    """
    db = DatabaseManager(db_path)
    db.create_tables()
    logger.info("数据库初始化完成")
    return db


# 测试代码
if __name__ == '__main__':
    print("测试数据库模块...")
    
    # 初始化数据库
    db = init_database()
    
    # 创建测试数据
    test_games = [
        {
            'game_id': '20240115LALGSW',
            'game_date': '2024-01-15',
            'season': '2023-24',
            'team_id': '1610612747',
            'team_abbr': 'LAL',
            'team_name': 'Los Angeles Lakers',
            'opponent_id': '1610612744',
            'opponent_abbr': 'GSW',
            'opponent_name': 'Golden State Warriors',
            'is_home': True,
            'result': 'W',
            'points': 118,
            'opponent_points': 112,
            'point_diff': 6,
            'fg_made': 45,
            'fg_attempts': 92,
            'fg_pct': 0.489,
            'fg3_made': 16,
            'fg3_attempts': 38,
            'fg3_pct': 0.421,
            'ft_made': 12,
            'ft_attempts': 15,
            'ft_pct': 0.800,
            'rebounds': 47,
            'assists': 28,
            'steals': 9,
            'blocks': 5,
            'turnovers': 14,
            'fouls': 18
        }
    ]
    
    # 插入测试数据
    db.insert_game_data(test_games)
    
    # 查询数据
    df = db.get_game_data(limit=10)
    print(f"数据库中比赛记录数: {len(df)}")
    
    # 获取统计信息
    stats = db.get_table_stats()
    print(f"各表记录数: {stats}")
    
    db.close()
    print("数据库测试完成")
