# -*- coding: utf-8 -*-
"""
NBA历史数据爬虫 - 独立版本
直接从Basketball Reference爬取2011-2026赛季的比赛数据
使用更强的反反爬措施
"""

import os
import sys
import time
import random
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 项目配置
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
DB_PATH = DATA_DIR / 'nba.db'
LOG_FILE = DATA_DIR / 'crawl_log.txt'

# 爬虫配置 - 使用更真实的浏览器头
CRAWLER_CONFIG = {
    'base_url': 'https://www.basketball-reference.com',
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'Cookie': 'bbref=show'
    },
    'request_delay': 5,  # 增加延迟到5秒
    'max_retries': 5,    # 增加重试次数
    'timeout': 60        # 增加超时时间
}

# 球队信息
TEAM_INFO = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BRK': 'Brooklyn Nets', 
    'CHI': 'Chicago Bulls', 'CHO': 'Charlotte Hornets', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'Los Angeles Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
    'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHO': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
}

TEAM_IDS = {
    'ATL': '1610612737', 'BOS': '1610612738', 'BRK': '1610612751', 'CHI': '1610612741',
    'CHO': '1610612766', 'CLE': '1610612739', 'DAL': '1610612742', 'DEN': '1610612743',
    'DET': '1610612765', 'GSW': '1610612744', 'HOU': '1610612745', 'IND': '1610612754',
    'LAC': '1610612746', 'LAL': '1610612747', 'MEM': '1610612763', 'MIA': '1610612748',
    'MIL': '1610612749', 'MIN': '1610612750', 'NOP': '1610612740', 'NYK': '1610612752',
    'OKC': '1610612760', 'ORL': '1610612753', 'PHI': '1610612755', 'PHO': '1610612756',
    'POR': '1610612757', 'SAC': '1610612758', 'SAS': '1610612759', 'TOR': '1610612761',
    'UTA': '1610612762', 'WAS': '1610612764'
}


class NBACrawler:
    """NBA数据爬虫类"""
    
    def __init__(self):
        self.base_url = CRAWLER_CONFIG['base_url']
        self.headers = CRAWLER_CONFIG['headers']
        self.request_delay = CRAWLER_CONFIG['request_delay']
        self.max_retries = CRAWLER_CONFIG['max_retries']
        self.timeout = CRAWLER_CONFIG['timeout']
        
        # 创建Session
        self.session = self._create_session()
        
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
        
        # 初始化请求计数
        self.request_count = 0
        
        self._log("NBA爬虫初始化完成")
    
    def _create_session(self) -> requests.Session:
        """创建带重试的Session"""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=2,  # 增加退避时间
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=1)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def _log(self, message: str):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """获取页面内容"""
        # 检查是否需要等待（每分钟最多10个请求）
        self.request_count += 1
        if self.request_count > 10:
            self._log("请求频率限制，等待30秒...")
            time.sleep(30)
            self.request_count = 1
        
        for attempt in range(self.max_retries):
            try:
                # 添加随机延迟
                delay = self.request_delay + random.uniform(0, 2)
                self._log(f"等待 {delay:.1f}s 后请求...")
                time.sleep(delay)
                
                response = self.session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                
                # 检查响应状态
                if response.status_code == 403:
                    self._log(f"403 Forbidden (尝试 {attempt + 1}/{self.max_retries}): {url}")
                    # 如果被禁止，等待更长时间
                    wait_time = 60 * (attempt + 1)
                    self._log(f"被禁止访问，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                self.stats['successful_requests'] += 1
                
                # 检查是否获取到了有效内容
                if 'Please complete the security check' in response.text:
                    self._log("遇到安全检查页面，等待60秒...")
                    time.sleep(60)
                    continue
                
                return response.text
                
            except requests.exceptions.Timeout:
                self._log(f"请求超时 (尝试 {attempt + 1}/{self.max_retries}): {url}")
                if attempt < self.max_retries - 1:
                    time.sleep(10 * (attempt + 1))
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    self._log("触发限流，等待5分钟...")
                    time.sleep(300)
                else:
                    self._log(f"HTTP错误 ({attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(20 * (attempt + 1))
            except requests.exceptions.RequestException as e:
                self._log(f"请求失败 ({attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(20 * (attempt + 1))
        
        self.stats['failed_requests'] += 1
        self._log(f"获取页面最终失败: {url}")
        return None
    
    def _safe_int(self, text: str) -> int:
        """安全转换为整数"""
        try:
            return int(text) if text and text.strip() else 0
        except ValueError:
            return 0
    
    def _safe_float(self, text: str) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            return float(text) if text and text.strip() else None
        except ValueError:
            return None
    
    def fetch_team_game_log(self, team_abbr: str, year: int) -> List[Dict[str, Any]]:
        """
        获取球队赛季每场比赛数据
        """
        url = f"{self.base_url}/teams/{team_abbr}/{year}_games.html"
        self._log(f"获取 {team_abbr} {year} 赛季比赛日志...")
        
        html = self._fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        games = []
        
        # 查找比赛日志表格
        table = soup.find('table', {'id': 'games'})
        if not table:
            self._log(f"未找到 {team_abbr} 的比赛日志表格")
            return games
        
        tbody = table.find('tbody')
        if not tbody:
            return games
        
        for row in tbody.find_all('tr'):
            # 跳过表头行
            if row.get('class') == ['thead']:
                continue
            
            cells = row.find_all('td')
            if len(cells) < 20:
                continue
            
            try:
                # 获取日期
                date_cell = cells[0]
                date_link = date_cell.find('a')
                game_date = date_link.get_text(strip=True) if date_link else date_cell.get_text(strip=True)
                
                # 解析对手
                opponent_cell = cells[1]
                opponent_text = opponent_cell.get_text(strip=True)
                is_home = '@' not in opponent_text
                opponent_abbr = opponent_text.replace('@', '')
                
                # 获取胜负和比分
                result_cell = cells[2]
                result = result_cell.get_text(strip=True)
                
                points = self._safe_int(cells[5].get_text(strip=True))
                opponent_points = self._safe_int(cells[6].get_text(strip=True))
                
                # 生成game_id
                date_str = game_date.replace('-', '')
                game_id = f"{date_str}{team_abbr}{opponent_abbr}"
                
                game = {
                    'game_id': game_id,
                    'game_date': game_date,
                    'team_abbr': team_abbr,
                    'opponent_abbr': opponent_abbr,
                    'is_home': is_home,
                    'result': result,
                    'points': points,
                    'opponent_points': opponent_points,
                    'point_diff': points - opponent_points,
                    'fg_made': self._safe_int(cells[8].get_text(strip=True)) if len(cells) > 8 else 0,
                    'fg_attempts': self._safe_int(cells[9].get_text(strip=True)) if len(cells) > 9 else 0,
                    'fg_pct': self._safe_float(cells[10].get_text(strip=True)) if len(cells) > 10 else None,
                    'fg3_made': self._safe_int(cells[11].get_text(strip=True)) if len(cells) > 11 else 0,
                    'fg3_attempts': self._safe_int(cells[12].get_text(strip=True)) if len(cells) > 12 else 0,
                    'fg3_pct': self._safe_float(cells[13].get_text(strip=True)) if len(cells) > 13 else None,
                    'ft_made': self._safe_int(cells[14].get_text(strip=True)) if len(cells) > 14 else 0,
                    'ft_attempts': self._safe_int(cells[15].get_text(strip=True)) if len(cells) > 15 else 0,
                    'ft_pct': self._safe_float(cells[16].get_text(strip=True)) if len(cells) > 16 else None,
                    'rebounds': self._safe_int(cells[17].get_text(strip=True)) if len(cells) > 17 else 0,
                    'assists': self._safe_int(cells[18].get_text(strip=True)) if len(cells) > 18 else 0,
                    'steals': self._safe_int(cells[19].get_text(strip=True)) if len(cells) > 19 else 0,
                    'blocks': self._safe_int(cells[20].get_text(strip=True)) if len(cells) > 20 else 0,
                    'turnovers': self._safe_int(cells[21].get_text(strip=True)) if len(cells) > 21 else 0,
                    'fouls': self._safe_int(cells[22].get_text(strip=True)) if len(cells) > 22 else 0
                }
                games.append(game)
                
            except Exception as e:
                self._log(f"解析比赛行失败: {e}")
                continue
        
        self._log(f"获取 {len(games)} 场 {team_abbr} 比赛数据")
        return games
    
    def crawl_season(self, year: int, db_conn: sqlite3.Connection) -> int:
        """
        爬取单个赛季的所有球队数据
        """
        season_str = f"{year-1}-{str(year)[2:]}"
        self._log(f"=== 开始爬取 {season_str} 赛季 ===")
        
        season_games = 0
        
        for team_abbr in TEAM_INFO.keys():
            games = self.fetch_team_game_log(team_abbr, year)
            
            # 保存到数据库
            for game in games:
                try:
                    game['season'] = season_str
                    game['team_name'] = TEAM_INFO.get(team_abbr, team_abbr)
                    game['opponent_name'] = TEAM_INFO.get(game['opponent_abbr'], game['opponent_abbr'])
                    game['team_id'] = TEAM_IDS.get(team_abbr, '')
                    game['opponent_id'] = TEAM_IDS.get(game['opponent_abbr'], '')
                    
                    # 插入数据库
                    cursor = db_conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO team_game_stats (
                            game_id, game_date, season, team_id, team_abbr, team_name,
                            opponent_id, opponent_abbr, opponent_name, is_home, result,
                            points, opponent_points, point_diff,
                            fg_made, fg_attempts, fg_pct,
                            fg3_made, fg3_attempts, fg3_pct,
                            ft_made, ft_attempts, ft_pct,
                            rebounds, assists, steals, blocks, turnovers, fouls
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game['game_id'], game['game_date'], game['season'],
                        game['team_id'], game['team_abbr'], game['team_name'],
                        game['opponent_id'], game['opponent_abbr'], game['opponent_name'],
                        game['is_home'], game['result'], game['points'], game['opponent_points'],
                        game['point_diff'], game['fg_made'], game['fg_attempts'], game['fg_pct'],
                        game['fg3_made'], game['fg3_attempts'], game['fg3_pct'],
                        game['ft_made'], game['ft_attempts'], game['ft_pct'],
                        game['rebounds'], game['assists'], game['steals'], game['blocks'],
                        game['turnovers'], game['fouls']
                    ))
                    db_conn.commit()
                    season_games += 1
                    
                except sqlite3.Error as e:
                    self._log(f"数据库错误: {e}")
                    continue
            
            self.stats['total_games'] += len(games)
        
        self.stats['seasons_completed'] += 1
        self._log(f"=== {season_str} 赛季完成，共 {season_games} 条记录 ===")
        return season_games
    
    def historical_crawl(self, start_year: int = 2012, end_year: int = 2026):
        """
        历史数据全量爬取
        """
        self._log("=" * 60)
        self._log(f"开始历史数据全量爬取: {start_year}-{end_year} 赛季")
        self._log("=" * 60)
        
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        
        # 创建表
        cursor = conn.cursor()
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_date ON team_game_stats(game_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_season ON team_game_stats(team_abbr, season)")
        conn.commit()
        
        self._log("数据库表创建完成")
        
        total_season_games = 0
        start_time = datetime.now()
        
        for year in range(start_year, end_year + 1):
            season_start = datetime.now()
            season_games = self.crawl_season(year, conn)
            total_season_games += season_games
            
            elapsed = (datetime.now() - start_time).total_seconds()
            self._log(f"当前总进度: {self.stats['total_games']} 条比赛记录 ({elapsed/3600:.1f}小时)")
        
        conn.close()
        
        self._log("=" * 60)
        self._log(f"历史数据爬取完成!")
        self._log(f"总计: {self.stats['total_games']} 条比赛记录")
        self._log(f"成功请求: {self.stats['successful_requests']}")
        self._log(f"失败请求: {self.stats['failed_requests']}")
        self._log(f"总耗时: {(datetime.now() - start_time).total_seconds()/3600:.2f} 小时")
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
