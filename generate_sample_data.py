# -*- coding: utf-8 -*-
"""
NBA历史数据爬虫 - 简化版本
"""

import sqlite3
import random
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
DB_PATH = DATA_DIR / 'nba.db'

TEAM_INFO = {
    'ATL': {'id': '1610612737', 'name': 'Atlanta Hawks'},
    'BOS': {'id': '1610612738', 'name': 'Boston Celtics'},
    'BRK': {'id': '1610612751', 'name': 'Brooklyn Nets'},
    'CHI': {'id': '1610612741', 'name': 'Chicago Bulls'},
    'CHO': {'id': '1610612766', 'name': 'Charlotte Hornets'},
    'CLE': {'id': '1610612739', 'name': 'Cleveland Cavaliers'},
    'DAL': {'id': '1610612742', 'name': 'Dallas Mavericks'},
    'DEN': {'id': '1610612743', 'name': 'Denver Nuggets'},
    'DET': {'id': '1610612765', 'name': 'Detroit Pistons'},
    'GSW': {'id': '1610612744', 'name': 'Golden State Warriors'},
    'HOU': {'id': '1610612745', 'name': 'Houston Rockets'},
    'IND': {'id': '1610612754', 'name': 'Indiana Pacers'},
    'LAC': {'id': '1610612746', 'name': 'Los Angeles Clippers'},
    'LAL': {'id': '1610612747', 'name': 'Los Angeles Lakers'},
    'MEM': {'id': '1610612763', 'name': 'Memphis Grizzlies'},
    'MIA': {'id': '1610612748', 'name': 'Miami Heat'},
    'MIL': {'id': '1610612749', 'name': 'Milwaukee Bucks'},
    'MIN': {'id': '1610612750', 'name': 'Minnesota Timberwolves'},
    'NOP': {'id': '1610612740', 'name': 'New Orleans Pelicans'},
    'NYK': {'id': '1610612752', 'name': 'New York Knicks'},
    'OKC': {'id': '1610612760', 'name': 'Oklahoma City Thunder'},
    'ORL': {'id': '1610612753', 'name': 'Orlando Magic'},
    'PHI': {'id': '1610612755', 'name': 'Philadelphia 76ers'},
    'PHO': {'id': '1610612756', 'name': 'Phoenix Suns'},
    'POR': {'id': '1610612757', 'name': 'Portland Trail Blazers'},
    'SAC': {'id': '1610612758', 'name': 'Sacramento Kings'},
    'SAS': {'id': '1610612759', 'name': 'San Antonio Spurs'},
    'TOR': {'id': '1610612761', 'name': 'Toronto Raptors'},
    'UTA': {'id': '1610612762', 'name': 'Utah Jazz'},
    'WAS': {'id': '1610612764', 'name': 'Washington Wizards'}
}

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"初始化数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建表 - 简化为28列（不包括自增id和默认时间戳）
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
            plus_minus INTEGER,
            data_source VARCHAR(20)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_date ON team_game_stats(game_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_season ON team_game_stats(team_abbr, season)")
    conn.commit()
    
    print("数据库表创建完成")
    
    # 生成示例数据
    random.seed(42)
    total_games = 0
    
    for year in range(2020, 2025):  # 2020-2024
        season = f"{year-1}-{str(year)[2:]}"
        print(f"生成 {season} 赛季数据...")
        
        for team_abbr, team_info in TEAM_INFO.items():
            for _ in range(41):  # 每支球队约41场比赛
                month = random.randint(10, 12) if random.random() > 0.5 else random.randint(1, 6)
                day = random.randint(1, 28)
                game_date = f"20{year-1}-{month:02d}-{day:02d}" if month >= 10 else f"20{year}-{month:02d}-{day:02d}"
                
                opponent_abbr = random.choice([t for t in TEAM_INFO.keys() if t != team_abbr])
                opponent_info = TEAM_INFO[opponent_abbr]
                
                points = random.randint(85, 125)
                opponent_points = random.randint(85, 125)
                while abs(points - opponent_points) > 35:
                    opponent_points = random.randint(85, 125)
                
                result = 'W' if points > opponent_points else 'L'
                is_home = 1 if random.random() > 0.5 else 0
                game_id = f"{game_date.replace('-', '')}{team_abbr}{opponent_abbr}"
                
                cursor.execute("""
                    INSERT OR REPLACE INTO team_game_stats (
                        game_id, game_date, season, team_id, team_abbr, team_name,
                        opponent_id, opponent_abbr, opponent_name, is_home, result,
                        points, opponent_points, point_diff,
                        fg_made, fg_attempts, fg_pct,
                        fg3_made, fg3_attempts, fg3_pct,
                        ft_made, ft_attempts, ft_pct,
                        rebounds, assists, steals, blocks, turnovers, fouls,
                        plus_minus, data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_id,
                    game_date,
                    season,
                    team_info['id'],
                    team_abbr,
                    team_info['name'],
                    opponent_info['id'],
                    opponent_abbr,
                    opponent_info['name'],
                    is_home,
                    result,
                    points,
                    opponent_points,
                    points - opponent_points,
                    random.randint(30, 50),
                    random.randint(70, 95),
                    round(random.uniform(0.40, 0.52), 3),
                    random.randint(8, 18),
                    random.randint(25, 40),
                    round(random.uniform(0.32, 0.42), 3),
                    random.randint(12, 25),
                    random.randint(15, 30),
                    round(random.uniform(0.68, 0.85), 3),
                    random.randint(32, 50),
                    random.randint(18, 30),
                    random.randint(5, 12),
                    random.randint(2, 8),
                    random.randint(10, 18),
                    random.randint(15, 25),
                    random.randint(-15, 15),
                    'sample_data'
                ))
                total_games += 1
        
        conn.commit()
        print(f"  {season} 赛季完成")
    
    conn.close()
    
    print(f"\n数据生成完成!")
    print(f"总计: {total_games} 场比赛记录")
    print(f"数据库: {DB_PATH}")
    
    # 验证数据
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM team_game_stats")
    count = cursor.fetchone()[0]
    cursor.execute("SELECT DISTINCT season FROM team_game_stats ORDER BY season")
    seasons = [s[0] for s in cursor.fetchall()]
    cursor.execute("SELECT team_abbr, COUNT(*) as cnt FROM team_game_stats GROUP BY team_abbr ORDER BY cnt DESC LIMIT 5")
    top_teams = cursor.fetchall()
    conn.close()
    
    print(f"\n数据验证:")
    print(f"  总记录数: {count}")
    print(f"  赛季数: {len(seasons)}")
    print(f"  赛季列表: {seasons}")
    print(f"  球队记录数(前5): {top_teams}")

if __name__ == '__main__':
    main()
