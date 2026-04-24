# -*- coding: utf-8 -*-
"""
NBA历史数据爬虫 - 使用NBA官方API
通过nba_api库获取2011-2026赛季的比赛数据
"""

import os
import sys
import time
import random
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

from nba_api.stats.endpoints import leaguegamefinder, boxscoretraditionalv2
from nba_api.stats.static import teams
# 不使用 SeasonAll，直接使用字符串指定赛季

import pandas as pd

# 项目配置
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
DB_PATH = DATA_DIR / 'nba.db'
LOG_FILE = DATA_DIR / 'crawl_log.txt'

# API配置
API_RETRY_TIMES = 3
API_RETRY_DELAY = 3
API_REQUEST_DELAY = 0.6
BATCH_SIZE = 100


class NBACrawler:
    """NBA数据爬虫类 - 使用官方API"""
    
    def __init__(self):
        # 确保数据目录存在
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        self.stats = {
            'total_games': 0,
            'total_seasons': 0,
            'seasons_completed': 0,
            'failed_requests': 0,
            'successful_requests': 0
        }
        
        # 获取球队映射
        self.nba_teams = {team['abbreviation']: team['id'] for team in teams.get_teams()}
        self.team_names = {team['abbreviation']: team['full_name'] for team in teams.get_teams()}
        
        self._log("NBA官方API爬虫初始化完成")
        self._log(f"已加载 {len(self.nba_teams)} 支球队信息")
    
    def _log(self, message: str):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    
    def _safe_get(self, df: pd.DataFrame, row: int, col: str, default=None):
        """安全获取DataFrame值"""
        try:
            if col in df.columns:
                val = df.iloc[row][col]
                if pd.isna(val):
                    return default
                return val
            return default
        except (IndexError, KeyError):
            return default
    
    def fetch_season_games(self, season: str, retries: int = 3) -> pd.DataFrame:
        """
        获取指定赛季的所有比赛数据
        
        Args:
            season: 赛季字符串，格式为 "2011-12"
            retries: 重试次数
            
        Returns:
            包含比赛数据的DataFrame
        """
        for attempt in range(retries):
            try:
                self._log(f"正在获取 {season} 赛季数据...")
                
                gamefinder = leaguegamefinder.LeagueGameFinder(
                    season_nullable=season,
                    season_type_nullable='Regular Season'
                )
                
                games = gamefinder.get_data_frames()[0]
                
                self.stats['successful_requests'] += 1
                self._log(f"获取到 {len(games)} 场比赛记录")
                
                return games
                
            except Exception as e:
                self._log(f"获取 {season} 数据失败 (尝试 {attempt + 1}/{retries}): {e}")
                self.stats['failed_requests'] += 1
                if attempt < retries - 1:
                    wait_time = API_RETRY_DELAY * (2 ** attempt)
                    self._log(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
        
        return pd.DataFrame()
    
    def fetch_playoff_games(self, season: str, retries: int = 3) -> pd.DataFrame:
        """
        获取指定赛季的季后赛数据
        
        Args:
            season: 赛季字符串
            retries: 重试次数
            
        Returns:
            包含季后赛数据的DataFrame
        """
        for attempt in range(retries):
            try:
                self._log(f"正在获取 {season} 赛季季后赛数据...")
                
                gamefinder = leaguegamefinder.LeagueGameFinder(
                    season_nullable=season,
                    season_type_nullable='Playoffs'
                )
                
                games = gamefinder.get_data_frames()[0]
                
                self._log(f"获取到 {len(games)} 场季后赛记录")
                
                return games
                
            except Exception as e:
                self._log(f"获取 {season} 季后赛数据失败 (尝试 {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    wait_time = API_RETRY_DELAY * (2 ** attempt)
                    time.sleep(wait_time)
        
        return pd.DataFrame()
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 创建比赛数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_game_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id VARCHAR(30) UNIQUE NOT NULL,
                game_date DATE NOT NULL,
                season VARCHAR(10) NOT NULL,
                team_id VARCHAR(20) NOT NULL,
                team_abbr VARCHAR(10) NOT NULL,
                team_name VARCHAR(100),
                opponent_id VARCHAR(20),
                opponent_abbr VARCHAR(10),
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
                minutes VARCHAR(10),
                plus_minus INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_date ON team_game_stats(game_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_season ON team_game_stats(team_abbr, season)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_id ON team_game_stats(game_id)")
        
        conn.commit()
        self._log("数据库表初始化完成")
        
        return conn
    
    def save_games_to_db(self, conn: sqlite3.Connection, games_df: pd.DataFrame, season: str) -> int:
        """
        将比赛数据保存到数据库
        
        Args:
            conn: 数据库连接
            games_df: 比赛数据DataFrame
            season: 赛季字符串
            
        Returns:
            保存的记录数
        """
        if games_df.empty:
            return 0
        
        cursor = conn.cursor()
        saved_count = 0
        
        for idx, row in games_df.iterrows():
            try:
                # 解析比赛数据
                game_id = str(row.get('GAME_ID', ''))
                game_date = str(row.get('GAME_DATE', ''))[:10]  # 取日期部分
                
                team_abbr = str(row.get('TEAM_ABBREVIATION', ''))
                team_name = str(row.get('TEAM_NAME', ''))
                team_id = str(row.get('TEAM_ID', ''))
                
                opponent_abbr = str(row.get('MATCHUP', ''))
                is_home = 1 if 'vs.' in opponent_abbr else 0
                
                # 提取对手缩写
                if '@' in opponent_abbr:
                    opponent_abbr = opponent_abbr.split(' @ ')[-1].strip()
                elif 'vs.' in opponent_abbr:
                    opponent_abbr = opponent_abbr.split(' vs. ')[-1].strip()
                else:
                    opponent_abbr = ''
                
                opponent_name = self.team_names.get(opponent_abbr, opponent_abbr)
                opponent_id = self.nba_teams.get(opponent_abbr, '')
                
                # 获取比分和胜负
                WL = str(row.get('WL', ''))
                PTS = int(row.get('PTS', 0)) if pd.notna(row.get('PTS')) else 0
                opponent_pts = int(row.get('OPP_PTS', 0)) if pd.notna(row.get('OPP_PTS')) else 0
                point_diff = PTS - opponent_pts
                
                # 获取详细统计
                FGM = int(row.get('FGM', 0)) if pd.notna(row.get('FGM')) else 0
                FGA = int(row.get('FGA', 0)) if pd.notna(row.get('FGA')) else 0
                FG_PCT = float(row.get('FG_PCT', 0)) if pd.notna(row.get('FG_PCT')) else None
                
                FG3M = int(row.get('FG3M', 0)) if pd.notna(row.get('FG3M')) else 0
                FG3A = int(row.get('FG3A', 0)) if pd.notna(row.get('FG3A')) else 0
                FG3_PCT = float(row.get('FG3_PCT', 0)) if pd.notna(row.get('FG3_PCT')) else None
                
                FTM = int(row.get('FTM', 0)) if pd.notna(row.get('FTM')) else 0
                FTA = int(row.get('FTA', 0)) if pd.notna(row.get('FTA')) else 0
                FT_PCT = float(row.get('FT_PCT', 0)) if pd.notna(row.get('FT_PCT')) else None
                
                REB = int(row.get('REB', 0)) if pd.notna(row.get('REB')) else 0
                AST = int(row.get('AST', 0)) if pd.notna(row.get('AST')) else 0
                STL = int(row.get('STL', 0)) if pd.notna(row.get('STL')) else 0
                BLK = int(row.get('BLK', 0)) if pd.notna(row.get('BLK')) else 0
                TOV = int(row.get('TOV', 0)) if pd.notna(row.get('TOV')) else 0
                PF = int(row.get('PF', 0)) if pd.notna(row.get('PF')) else 0
                PLUS_MINUS = int(row.get('PLUS_MINUS', 0)) if pd.notna(row.get('PLUS_MINUS')) else 0
                
                minutes = str(row.get('MIN', '0:00'))
                
                # 插入数据库
                cursor.execute("""
                    INSERT OR REPLACE INTO team_game_stats (
                        game_id, game_date, season, team_id, team_abbr, team_name,
                        opponent_id, opponent_abbr, opponent_name, is_home, result,
                        points, opponent_points, point_diff,
                        fg_made, fg_attempts, fg_pct,
                        fg3_made, fg3_attempts, fg3_pct,
                        ft_made, ft_attempts, ft_pct,
                        rebounds, assists, steals, blocks, turnovers, fouls,
                        minutes, plus_minus
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_id, game_date, season, team_id, team_abbr, team_name,
                    opponent_id, opponent_abbr, opponent_name, is_home, WL,
                    PTS, opponent_pts, point_diff,
                    FGM, FGA, FG_PCT,
                    FG3M, FG3A, FG3_PCT,
                    FTM, FTA, FT_PCT,
                    REB, AST, STL, BLK, TOV, PF,
                    minutes, PLUS_MINUS
                ))
                
                saved_count += 1
                
            except Exception as e:
                self._log(f"保存比赛记录失败: {e}")
                continue
        
        conn.commit()
        return saved_count
    
    def crawl_season(self, conn: sqlite3.Connection, season: str) -> int:
        """
        爬取单个赛季的数据
        """
        self._log(f"=" * 50)
        self._log(f"开始爬取 {season} 赛季")
        
        # 获取常规赛数据
        regular_games = self.fetch_season_games(season)
        
        # 获取季后赛数据
        playoff_games = self.fetch_playoff_games(season)
        
        # 合并数据
        all_games = pd.concat([regular_games, playoff_games], ignore_index=True) if not regular_games.empty else regular_games
        
        if all_games.empty:
            self._log(f"{season} 赛季无数据")
            return 0
        
        # 保存到数据库
        saved_count = self.save_games_to_db(conn, all_games, season)
        
        self.stats['total_games'] += len(all_games)
        self.stats['seasons_completed'] += 1
        
        self._log(f"{season} 赛季完成: {saved_count} 条记录")
        self._log(f"=" * 50)
        
        return saved_count
    
    def historical_crawl(self, start_year: int = 2012, end_year: int = 2026):
        """
        历史数据全量爬取
        """
        self._log("=" * 60)
        self._log(f"开始历史数据全量爬取")
        self._log(f"赛季范围: {start_year-1}-{str(start_year)[2:]} 至 {end_year-1}-{str(end_year)[2:]}")
        self._log("=" * 60)
        
        # 初始化数据库
        conn = self.init_database()
        
        start_time = datetime.now()
        total_saved = 0
        
        # 遍历每个赛季
        for year in range(start_year, end_year + 1):
            season = f"{year-1}-{str(year)[2:]}"
            
            try:
                saved = self.crawl_season(conn, season)
                total_saved += saved
                
                # 打印进度
                elapsed = (datetime.now() - start_time).total_seconds()
                seasons_done = year - start_year + 1
                seasons_total = end_year - start_year + 1
                estimated_total = (elapsed / seasons_done * seasons_total) if seasons_done > 0 else 0
                
                self._log(f"进度: {seasons_done}/{seasons_total} 赛季, "
                         f"总记录: {self.stats['total_games']}, "
                         f"耗时: {elapsed/60:.1f}分钟, "
                         f"预计总耗时: {estimated_total/60:.1f}分钟")
                
            except Exception as e:
                self._log(f"爬取 {season} 赛季失败: {e}")
                continue
        
        conn.close()
        
        # 打印最终统计
        elapsed_total = (datetime.now() - start_time).total_seconds()
        
        self._log("=" * 60)
        self._log("历史数据爬取完成!")
        self._log(f"总计: {self.stats['total_games']} 场比赛记录")
        self._log(f"成功请求: {self.stats['successful_requests']}")
        self._log(f"失败请求: {self.stats['failed_requests']}")
        self._log(f"总耗时: {elapsed_total/60:.1f} 分钟")
        self._log(f"数据库: {DB_PATH}")
        self._log("=" * 60)
        
        return self.stats


def main():
    """主函数"""
    crawler = NBACrawler()
    
    # 爬取2011-12到2025-26赛季
    stats = crawler.historical_crawl(start_year=2012, end_year=2026)
    
    return stats


if __name__ == '__main__':
    main()
