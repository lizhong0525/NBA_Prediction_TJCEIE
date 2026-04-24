# -*- coding: utf-8 -*-
"""
爬虫模块测试
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler.spider import BasketballReferenceSpider
from crawler.parser import DataParser


class TestBasketballReferenceSpider:
    """测试BasketballReferenceSpider类"""
    
    @pytest.fixture
    def spider(self):
        """创建爬虫实例"""
        return BasketballReferenceSpider()
    
    def test_spider_initialization(self, spider):
        """测试爬虫初始化"""
        assert spider.base_url == "https://www.basketball-reference.com"
        assert spider.request_delay >= 0
        assert spider.session is not None
    
    @patch('requests.Session.get')
    def test_fetch_page_success(self, mock_get, spider):
        """测试成功获取页面"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = spider._fetch_page("https://example.com")
        
        assert result is not None
        assert "Test" in result
    
    @patch('requests.Session.get')
    def test_fetch_page_timeout(self, mock_get, spider):
        """测试请求超时"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        result = spider._fetch_page("https://example.com")
        
        assert result is None
    
    @patch('crawler.spider.BasketballReferenceSpider._fetch_page')
    def test_fetch_season_summary(self, mock_fetch, spider):
        """测试获取赛季总览"""
        mock_html = """
        <html>
            <table id="standings_E">
                <tbody>
                    <tr><th>1</th><td>Team1</td><td>50</td><td>20</td><td>.714</td><td>30-10</td></tr>
                </tbody>
            </table>
        </html>
        """
        mock_fetch.return_value = mock_html
        
        result = spider.fetch_season_summary(2024)
        
        assert result is not None
        assert 'season' in result
    
    def test_safe_int(self, spider):
        """测试安全转换为整数"""
        mock_cell = Mock()
        mock_cell.get_text.return_value = "123"
        
        assert spider._safe_int(mock_cell) == 123
        
        mock_cell.get_text.return_value = ""
        assert spider._safe_int(mock_cell) == 0
    
    def test_safe_float(self, spider):
        """测试安全转换为浮点数"""
        mock_cell = Mock()
        mock_cell.get_text.return_value = "0.456"
        
        assert spider._safe_float(mock_cell) == 0.456
        
        mock_cell.get_text.return_value = ""
        assert spider._safe_float(mock_cell) is None


class TestDataParser:
    """测试DataParser类"""
    
    @pytest.fixture
    def parser(self):
        """创建解析器实例"""
        return DataParser()
    
    def test_parser_initialization(self, parser):
        """测试解析器初始化"""
        assert parser.team_info is not None
        assert len(parser.team_info) == 30
    
    def test_parse_game_data_empty(self, parser):
        """测试解析空数据"""
        df = parser.parse_game_data([])
        assert df.empty
    
    def test_parse_game_data(self, parser):
        """测试解析比赛数据"""
        raw_data = [
            {
                'game_date': '2024-01-15',
                'team_abbr': 'LAL',
                'opponent_abbr': 'GSW',
                'is_home': True,
                'result': 'W',
                'points': 118,
                'opponent_points': 112
            }
        ]
        
        df = parser.parse_game_data(raw_data)
        
        assert not df.empty
        assert 'team_name' in df.columns
        assert df.iloc[0]['team_name'] == 'Los Angeles Lakers'
    
    def test_get_season(self, parser):
        """测试获取赛季"""
        # 10月 -> 当年赛季
        oct_date = datetime(2024, 10, 15)
        assert parser._get_season(oct_date) == "2024-25"
        
        # 1月 -> 上年赛季
        jan_date = datetime(2024, 1, 15)
        assert parser._get_season(jan_date) == "2023-24"
    
    def test_compute_derived_features(self, parser):
        """测试计算衍生特征"""
        import pandas as pd
        
        df = pd.DataFrame({
            'team_abbr': ['LAL', 'LAL', 'LAL', 'GSW', 'GSW'],
            'game_date': pd.date_range('2024-01-10', periods=5),
            'points': [110, 115, 120, 108, 112],
            'opponent_points': [100, 105, 110, 105, 100],
            'result': ['W', 'W', 'L', 'L', 'W'],
            'fg_pct': [0.45, 0.48, 0.50, 0.42, 0.46],
            'fg3_pct': [0.35, 0.38, 0.40, 0.32, 0.36],
            'rebounds': [42, 45, 48, 40, 44],
            'assists': [25, 28, 30, 22, 26]
        })
        
        result = parser.compute_derived_features(df, window=3)
        
        assert 'recent_avg_points' in result.columns
        assert 'recent_win_pct' in result.columns
    
    def test_compute_team_season_stats(self, parser):
        """测试计算球队赛季统计"""
        import pandas as pd
        
        df = pd.DataFrame({
            'team_abbr': ['LAL', 'LAL', 'GSW', 'GSW'],
            'season': ['2023-24', '2023-24', '2023-24', '2023-24'],
            'game_date': pd.date_range('2024-01-10', periods=4),
            'points': [110, 115, 108, 112],
            'opponent_points': [100, 105, 105, 100],
            'result': ['W', 'W', 'L', 'W'],
            'fg_pct': [0.45, 0.48, 0.42, 0.46],
            'fg3_pct': [0.35, 0.38, 0.32, 0.36],
            'ft_pct': [0.80, 0.82, 0.78, 0.81],
            'rebounds': [42, 45, 40, 44],
            'assists': [25, 28, 22, 26],
            'steals': [8, 7, 6, 9],
            'blocks': [4, 5, 3, 4],
            'turnovers': [12, 14, 15, 13],
            'fouls': [18, 20, 19, 17],
            'is_home': [True, False, True, False]
        })
        
        stats = parser.compute_team_season_stats(df)
        
        assert not stats.empty
        assert 'win_pct' in stats.columns
        assert 'avg_points' in stats.columns
    
    def test_compute_head_to_head(self, parser):
        """测试计算对战数据"""
        import pandas as pd
        
        df = pd.DataFrame({
            'team_abbr': ['LAL', 'LAL', 'GSW', 'GSW', 'LAL'],
            'opponent_abbr': ['GSW', 'GSW', 'LAL', 'LAL', 'GSW'],
            'game_date': pd.date_range('2024-01-10', periods=5),
            'points': [110, 115, 108, 112, 118],
            'opponent_points': [100, 105, 110, 105, 108],
            'result': ['W', 'W', 'L', 'L', 'W']
        })
        
        h2h = parser.compute_head_to_head(df, 'LAL', 'GSW')
        
        assert h2h['total_games'] == 5
        assert h2h['games'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
