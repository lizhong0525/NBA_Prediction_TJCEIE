# -*- coding: utf-8 -*-
"""
Basketball Reference数据爬虫
负责从basketball-reference.com爬取NBA历史比赛数据
"""

import time
import random
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from config import CRAWLER_CONFIG, TEAM_INFO
from utils.logger import logger, log_function_call, log_crawler_progress


class BasketballReferenceSpider:
    """
    Basketball Reference数据爬虫类
    
    功能：
    - 爬取NBA赛季总览数据
    - 爬取球队赛季统计
    - 爬取球队比赛日志
    - 爬取比赛详细数据(boxscore)
    - 支持历史数据全量爬取和增量更新
    """
    
    def __init__(self):
        """
        初始化爬虫
        - 设置基础URL
        - 配置请求头
        - 创建Session（支持自动重试）
        """
        self.base_url = CRAWLER_CONFIG['base_url']
        self.headers = CRAWLER_CONFIG['headers']
        self.request_delay = CRAWLER_CONFIG['request_delay']
        self.max_retries = CRAWLER_CONFIG['max_retries']
        self.retry_backoff = CRAWLER_CONFIG['retry_backoff']
        self.timeout = CRAWLER_CONFIG['timeout']
        
        # 创建带重试机制的Session
        self.session = self._create_session()
        
        logger.info("BasketballReferenceSpider初始化完成")
    
    def _create_session(self) -> requests.Session:
        """
        创建带有自动重试机制的Session
        
        Returns:
            配置好的requests.Session对象
        """
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _fetch_page(self, url: str, encoding: str = 'utf-8') -> Optional[str]:
        """
        获取网页内容（带重试机制）
        
        Args:
            url: 目标URL
            encoding: 响应编码
            
        Returns:
            网页HTML内容，失败返回None
        """
        for attempt in range(self.max_retries):
            try:
                # 添加随机延迟，避免被封禁
                if attempt > 0:
                    delay = self.retry_backoff[min(attempt, len(self.retry_backoff) - 1)]
                    logger.debug(f"重试 {attempt}，等待 {delay}s")
                    time.sleep(delay)
                else:
                    # 正常请求间隔
                    time.sleep(self.request_delay + random.uniform(0, 1))
                
                response = self.session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                response.encoding = encoding
                
                logger.debug(f"成功获取页面: {url}")
                return response.text
                
            except requests.exceptions.Timeout:
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries}): {url}")
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    # 被限流，等待更长时间
                    logger.warning(f"触发限流，等待10分钟...")
                    time.sleep(600)
                else:
                    logger.warning(f"HTTP错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
        
        logger.error(f"获取页面最终失败: {url}")
        return None
    
    @log_function_call
    def fetch_season_summary(self, year: int) -> Optional[Dict[str, Any]]:
        """
        获取赛季总览数据
        
        Args:
            year: 赛季结束年份，如2026表示2025-26赛季
            
        Returns:
            包含球队排名、球员统计等数据的字典
        """
        url = f"{self.base_url}/leagues/NBA_{year}.html"
        logger.info(f"正在获取 {year} 赛季总览数据...")
        
        html = self._fetch_page(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'lxml')
        data = {
            'season': f"{year-1}-{str(year)[2:]}",
            'teams': [],
            'fetch_time': datetime.now().isoformat()
        }
        
        # 解析东部联盟排名
        eastern_table = soup.find('table', {'id': 'standings_E'})
        if eastern_table:
            data['eastern_teams'] = self._parse_standings_table(eastern_table)
        
        # 解析西部联盟排名
        western_table = soup.find('table', {'id': 'standings_W'})
        if western_table:
            data['western_teams'] = self._parse_standings_table(western_table)
        
        logger.info(f"成功解析 {year} 赛季总览数据")
        return data
    
    def _parse_standings_table(self, table) -> List[Dict[str, Any]]:
        """
        解析排名表格
        
        Args:
            table: BeautifulSoup表格对象
            
        Returns:
            球队排名列表
        """
        teams = []
        tbody = table.find('tbody')
        if not tbody:
            return teams
        
        for row in tbody.find_all('tr'):
            # 跳过表头行
            if 'thead' in row.get('class', []):
                continue
            
            cells = row.find_all(['th', 'td'])
            if len(cells) < 6:
                continue
            
            try:
                team_data = {
                    'rank': cells[0].get_text(strip=True),
                    'team_name': cells[1].get_text(strip=True),
                    'wins': int(cells[2].get_text(strip=True)),
                    'losses': int(cells[3].get_text(strip=True)),
                    'win_pct': float(cells[4].get_text(strip=True)),
                    'conf_record': cells[5].get_text(strip=True) if len(cells) > 5 else ''
                }
                teams.append(team_data)
            except (ValueError, IndexError) as e:
                logger.warning(f"解析排名行失败: {e}")
                continue
        
        return teams
    
    @log_function_call
    def fetch_team_season_stats(self, team_abbr: str, year: int) -> Optional[Dict[str, Any]]:
        """
        获取球队赛季统计
        
        Args:
            team_abbr: 球队缩写如 "LAL", "GSW"
            year: 赛季结束年份
            
        Returns:
            球队赛季统计数据字典
        """
        url = f"{self.base_url}/teams/{team_abbr}/{year}.html"
        logger.info(f"正在获取 {team_abbr} {year} 赛季统计...")
        
        html = self._fetch_page(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'lxml')
        
        # 解析球队基本信息
        team_info = self._parse_team_info(soup, team_abbr, year)
        
        # 解析球队赛季统计数据
        stats = self._parse_team_stats_table(soup)
        
        return {**team_info, **stats}
    
    def _parse_team_info(self, soup: BeautifulSoup, team_abbr: str, year: int) -> Dict[str, Any]:
        """
        解析球队基本信息
        """
        info = {
            'team_abbr': team_abbr,
            'season': f"{year-1}-{str(year)[2:]}",
            'year': year
        }
        
        # 从页面头部获取球队名称
        title = soup.find('h1')
        if title:
            info['team_name'] = title.get_text(strip=True)
        
        return info
    
    def _parse_team_stats_table(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        解析球队统计表格
        """
        stats = {}
        
        # 尝试获取球队排名数据
        table = soup.find('table', {'id': 'team_stats'})
        if not table:
            return stats
        
        tbody = table.find('tbody')
        if not tbody:
            return stats
        
        row = tbody.find('tr')
        if not row or row.get('class') == ['thead']:
            # 可能需要找下一行
            rows = tbody.find_all('tr')
            for r in rows:
                if r.get('class') != ['thead']:
                    row = r
                    break
        
        if not row:
            return stats
        
        cells = row.find_all('td')
        stat_names = ['games', 'minutes', 'fg', 'fga', 'fg_pct', 'fg3', 'fg3a', 'fg3_pct',
                      'ft', 'fta', 'ft_pct', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts']
        
        for i, cell in enumerate(cells):
            if i < len(stat_names):
                try:
                    value = cell.get_text(strip=True)
                    stats[stat_names[i]] = float(value) if value and value != '' else None
                except ValueError:
                    stats[stat_names[i]] = None
        
        return stats
    
    @log_function_call
    def fetch_team_game_log(self, team_abbr: str, year: int) -> List[Dict[str, Any]]:
        """
        获取球队赛季每场比赛数据
        
        Args:
            team_abbr: 球队缩写
            year: 赛季结束年份
            
        Returns:
            每场比赛的详细数据列表
        """
        url = f"{self.base_url}/teams/{team_abbr}/{year}_games.html"
        logger.info(f"正在获取 {team_abbr} {year} 赛季比赛日志...")
        
        html = self._fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        games = []
        
        # 查找比赛日志表格
        table = soup.find('table', {'id': 'games'})
        if not table:
            logger.warning(f"未找到 {team_abbr} 的比赛日志表格")
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
                game = self._parse_game_row(cells, team_abbr)
                if game:
                    games.append(game)
            except Exception as e:
                logger.warning(f"解析比赛行失败: {e}")
                continue
        
        logger.info(f"成功获取 {len(games)} 场 {team_abbr} 比赛数据")
        return games
    
    def _parse_game_row(self, cells, team_abbr: str) -> Optional[Dict[str, Any]]:
        """
        解析单场比赛行数据
        
        Args:
            cells: 表格单元格列表
            team_abbr: 球队缩写
            
        Returns:
            比赛数据字典
        """
        try:
            # 获取日期和对手
            date_cell = cells[0]
            date_link = date_cell.find('a')
            game_date = date_link.get_text(strip=True) if date_link else date_cell.get_text(strip=True)
            
            # 解析对手信息
            opponent_cell = cells[1]
            opponent_abbr = opponent_cell.get_text(strip=True)
            is_home = '@' not in opponent_cell.get_text(strip=True)
            
            # 获取比分
            result_cell = cells[2]
            result = result_cell.get_text(strip=True)  # W 或 L
            
            points_cell = cells[5]
            opponent_points_cell = cells[6]
            
            points = int(points_cell.get_text(strip=True))
            opponent_points = int(opponent_points_cell.get_text(strip=True))
            
            game = {
                'game_date': datetime.strptime(game_date, '%Y-%m-%d').strftime('%Y-%m-%d'),
                'team_abbr': team_abbr,
                'opponent_abbr': opponent_abbr.replace('@', ''),
                'is_home': is_home,
                'result': result,
                'points': points,
                'opponent_points': opponent_points,
                'point_diff': points - opponent_points
            }
            
            # 解析详细统计
            if len(cells) >= 19:
                game.update({
                    'fg_made': self._safe_int(cells[8]),
                    'fg_attempts': self._safe_int(cells[9]),
                    'fg_pct': self._safe_float(cells[10]),
                    'fg3_made': self._safe_int(cells[11]),
                    'fg3_attempts': self._safe_int(cells[12]),
                    'fg3_pct': self._safe_float(cells[13]),
                    'ft_made': self._safe_int(cells[14]),
                    'ft_attempts': self._safe_int(cells[15]),
                    'ft_pct': self._safe_float(cells[16]),
                    'rebounds': self._safe_int(cells[17]),
                    'assists': self._safe_int(cells[18]),
                    'steals': self._safe_int(cells[19]) if len(cells) > 19 else 0,
                    'blocks': self._safe_int(cells[20]) if len(cells) > 20 else 0,
                    'turnovers': self._safe_int(cells[21]) if len(cells) > 21 else 0,
                    'fouls': self._safe_int(cells[22]) if len(cells) > 22 else 0
                })
            
            return game
            
        except Exception as e:
            logger.debug(f"解析比赛行异常: {e}")
            return None
    
    def _safe_int(self, cell) -> int:
        """安全转换为整数"""
        try:
            text = cell.get_text(strip=True)
            return int(text) if text else 0
        except (ValueError, AttributeError):
            return 0
    
    def _safe_float(self, cell) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            text = cell.get_text(strip=True)
            return float(text) if text else None
        except (ValueError, AttributeError):
            return None
    
    @log_function_call
    def fetch_season_schedule(self, year: int) -> List[Dict[str, Any]]:
        """
        获取赛季完整赛程和结果
        
        Args:
            year: 赛季结束年份
            
        Returns:
            该赛季所有比赛列表
        """
        url = f"{self.base_url}/leagues/NBA_{year}_games.html"
        logger.info(f"正在获取 {year} 赛季完整赛程...")
        
        html = self._fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        games = []
        
        # 尝试获取赛程表格
        table = soup.find('table', {'id': 'games'})
        if not table:
            # 尝试其他可能的表格ID
            table = soup.find('table', {'class': 'stats_table'})
        
        if not table:
            logger.warning(f"未找到 {year} 赛季赛程表格")
            return games
        
        tbody = table.find('tbody')
        if not tbody:
            return games
        
        for row in tbody.find_all('tr'):
            if row.get('class') == ['thead']:
                continue
            
            cells = row.find_all('td')
            if len(cells) < 8:
                continue
            
            try:
                game = {
                    'date': cells[0].get_text(strip=True),
                    'start_time': cells[1].get_text(strip=True) if len(cells) > 1 else '',
                    'away_team': cells[2].get_text(strip=True),
                    'home_team': cells[4].get_text(strip=True),
                    'away_points': self._safe_int(cells[3]),
                    'home_points': self._safe_int(cells[5]),
                    'box_score': cells[6].find('a')['href'] if cells[6].find('a') else '',
                    'attendance': cells[7].get_text(strip=True) if len(cells) > 7 else ''
                }
                games.append(game)
            except Exception as e:
                logger.warning(f"解析赛程行失败: {e}")
                continue
        
        logger.info(f"成功获取 {len(games)} 场 {year} 赛季比赛")
        return games
    
    @log_function_call
    def fetch_box_score(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单场比赛详细数据
        
        Args:
            game_id: 比赛ID，如 "20260101LALGSW"
            
        Returns:
            比赛详细数据字典
        """
        url = f"{self.base_url}/boxscores/{game_id}.html"
        logger.info(f"正在获取比赛详细数据: {game_id}")
        
        html = self._fetch_page(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'lxml')
        
        # 解析两队数据
        game_data = {
            'game_id': game_id,
            'teams': {}
        }
        
        # 获取页面标题中的日期
        title = soup.find('title')
        if title:
            game_data['title'] = title.get_text(strip=True)
        
        # 解析两支球队的表格
        tables = soup.find_all('table', {'class': 'stats_table'})
        for table in tables[:2]:  # 通常只有两队数据
            team_data = self._parse_box_score_table(table)
            if team_data:
                game_data['teams'][team_data['team']] = team_data
        
        return game_data
    
    def _parse_box_score_table(self, table) -> Optional[Dict[str, Any]]:
        """
        解析boxscore表格
        """
        team_data = {'players': []}
        
        # 获取球队名称
        caption = table.find('caption')
        if caption:
            team_data['team'] = caption.get_text(strip=True)
        
        tbody = table.find('tbody')
        if not tbody:
            return team_data
        
        for row in tbody.find_all('tr'):
            if row.get('class') == ['thead']:
                continue
            
            cells = row.find_all(['th', 'td'])
            if len(cells) < 20:
                continue
            
            try:
                player = {
                    'player_name': cells[0].get_text(strip=True),
                    'minutes': cells[1].get_text(strip=True),
                    'fg': self._safe_int(cells[2]),
                    'fga': self._safe_int(cells[3]),
                    'fg3': self._safe_int(cells[4]),
                    'fg3a': self._safe_int(cells[5]),
                    'ft': self._safe_int(cells[6]),
                    'fta': self._safe_int(cells[7]),
                    'orb': self._safe_int(cells[8]),
                    'drb': self._safe_int(cells[9]),
                    'trb': self._safe_int(cells[10]),
                    'ast': self._safe_int(cells[11]),
                    'stl': self._safe_int(cells[12]),
                    'blk': self._safe_int(cells[13]),
                    'tov': self._safe_int(cells[14]),
                    'pf': self._safe_int(cells[15]),
                    'pts': self._safe_int(cells[16]),
                    'plus_minus': cells[17].get_text(strip=True) if len(cells) > 17 else '0'
                }
                team_data['players'].append(player)
            except Exception as e:
                logger.debug(f"解析球员数据失败: {e}")
                continue
        
        return team_data
    
    @log_function_call
    def fetch_player_stats(self, year: int, stat_type: str = "per_game") -> List[Dict[str, Any]]:
        """
        获取球员赛季统计
        
        Args:
            year: 赛季年份
            stat_type: 统计类型
                - per_game: 场均
                - totals: 总计
                - advanced: 高阶数据
                
        Returns:
            球员统计数据列表
        """
        url = f"{self.base_url}/leagues/NBA_{year}_{stat_type}.html"
        logger.info(f"正在获取 {year} 赛季球员{stat_type}数据...")
        
        html = self._fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        players = []
        
        # 查找球员统计表格
        table = soup.find('table', {'id': f'players_{stat_type}'})
        if not table:
            # 尝试其他表格ID
            table = soup.find('table', {'class': 'stats_table'})
        
        if not table:
            logger.warning(f"未找到 {year} 赛季球员{stat_type}数据表格")
            return players
        
        tbody = table.find('tbody')
        if not tbody:
            return players
        
        for row in tbody.find_all('tr'):
            if row.get('class') == ['thead']:
                continue
            
            cells = row.find_all(['th', 'td'])
            if len(cells) < 5:
                continue
            
            try:
                player = {
                    'player_name': cells[1].get_text(strip=True),
                    'position': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                    'age': self._safe_int(cells[3]) if len(cells) > 3 else None,
                    'games': self._safe_int(cells[4]) if len(cells) > 4 else 0
                }
                players.append(player)
            except Exception as e:
                logger.warning(f"解析球员行失败: {e}")
                continue
        
        logger.info(f"成功获取 {len(players)} 名球员数据")
        return players
    
    @log_crawler_progress
    def historical_crawl(self, start_year: int = 2012, end_year: int = 2026) -> Dict[str, int]:
        """
        历史数据全量爬取
        
        Args:
            start_year: 起始赛季（如2012表示2011-12赛季）
            end_year: 结束赛季
            
        Returns:
            爬取统计信息字典
        """
        logger.info(f"开始历史数据全量爬取: {start_year}-{end_year}赛季")
        
        stats = {
            'total_games': 0,
            'total_seasons': end_year - start_year,
            'seasons_completed': 0
        }
        
        for year in range(start_year, end_year + 1):
            logger.info(f"正在爬取 {year-1}-{str(year)[2:]} 赛季...")
            
            # 爬取每支球队的比赛数据
            for team_abbr in TEAM_INFO.keys():
                games = self.fetch_team_game_log(team_abbr, year)
                stats['total_games'] += len(games)
                
                # 每支球队之间也添加延迟
                time.sleep(self.request_delay)
            
            stats['seasons_completed'] += 1
            logger.info(f"赛季 {year} 爬取完成，当前总计: {stats['total_games']} 场比赛")
        
        logger.info(f"历史数据全量爬取完成！总计: {stats['total_games']} 场比赛")
        return stats
    
    @log_crawler_progress
    def incremental_update(self) -> Dict[str, int]:
        """
        增量更新数据（昨日比赛）
        
        Returns:
            更新统计信息字典
        """
        logger.info("开始增量更新...")
        
        stats = {'new_games': 0}
        
        # 获取当前赛季
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # NBA赛季通常是10月到次年6月
        if current_month < 7:
            season_year = current_year
        else:
            season_year = current_year + 1
        
        # 获取今日和近期的赛程
        schedule = self.fetch_season_schedule(season_year)
        
        # 过滤出今天的比赛
        today = datetime.now().strftime('%Y-%m-%d')
        today_games = [g for g in schedule if g.get('date', '').startswith(today)]
        
        stats['new_games'] = len(today_games)
        logger.info(f"增量更新完成，新增 {stats['new_games']} 场比赛")
        
        return stats
    
    def close(self):
        """关闭Session"""
        self.session.close()
        logger.info("爬虫Session已关闭")


# 测试代码
if __name__ == '__main__':
    spider = BasketballReferenceSpider()
    
    # 测试获取单个球队的比赛数据
    print("测试爬虫功能...")
    
    # 测试获取球队信息
    lal_info = spider.fetch_team_season_stats('LAL', 2026)
    print(f"LAL 2025-26赛季信息: {lal_info}")
    
    # 测试获取比赛日志
    games = spider.fetch_team_game_log('GSW', 2026)
    print(f"GSW 2025-26赛季比赛数: {len(games)}")
    
    spider.close()
    print("爬虫测试完成")
