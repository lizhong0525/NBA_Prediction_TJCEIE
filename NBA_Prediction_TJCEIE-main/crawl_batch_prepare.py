#!/usr/bin/env python3
"""
批量爬取ESPN NBA数据 - 使用fetch_web
"""
import json
import sqlite3
import time
from datetime import datetime, timedelta
import re

DB_PATH = 'data/nba.db'

# 球队信息
TEAMS = {
    'ATL': {'id': '1', 'name': 'Atlanta Hawks'},
    'BOS': {'id': '2', 'name': 'Boston Celtics'},
    'BKN': {'id': '3', 'name': 'Brooklyn Nets'},
    'CHA': {'id': '4', 'name': 'Charlotte Hornets'},
    'CHI': {'id': '5', 'name': 'Chicago Bulls'},
    'CLE': {'id': '6', 'name': 'Cleveland Cavaliers'},
    'DAL': {'id': '7', 'name': 'Dallas Mavericks'},
    'DEN': {'id': '8', 'name': 'Denver Nuggets'},
    'DET': {'id': '9', 'name': 'Detroit Pistons'},
    'GS': {'id': '10', 'name': 'Golden State Warriors'},
    'HOU': {'id': '11', 'name': 'Houston Rockets'},
    'IND': {'id': '12', 'name': 'Indiana Pacers'},
    'LAC': {'id': '13', 'name': 'LA Clippers'},
    'LAL': {'id': '14', 'name': 'Los Angeles Lakers'},
    'MEM': {'id': '15', 'name': 'Memphis Grizzlies'},
    'MIA': {'id': '16', 'name': 'Miami Heat'},
    'MIL': {'id': '17', 'name': 'Milwaukee Bucks'},
    'MIN': {'id': '18', 'name': 'Minnesota Timberwolves'},
    'NO': {'id': '19', 'name': 'New Orleans Pelicans'},
    'NY': {'id': '20', 'name': 'New York Knicks'},
    'OKC': {'id': '21', 'name': 'Oklahoma City Thunder'},
    'ORL': {'id': '22', 'name': 'Orlando Magic'},
    'PHI': {'id': '23', 'name': 'Philadelphia 76ers'},
    'PHX': {'id': '24', 'name': 'Phoenix Suns'},
    'POR': {'id': '25', 'name': 'Portland Trail Blazers'},
    'SA': {'id': '26', 'name': 'San Antonio Spurs'},
    'SAC': {'id': '27', 'name': 'Sacramento Kings'},
    'TOR': {'id': '28', 'name': 'Toronto Raptors'},
    'UTAH': {'id': '29', 'name': 'Utah Jazz'},
    'WSH': {'id': '30', 'name': 'Washington Wizards'},
}

def get_stat(stats, name):
    """从统计数据中获取特定值"""
    for s in stats:
        if s.get('name') == name:
            val = s.get('displayValue', '0')
            try:
                return float(val.replace('%', ''))
            except:
                return None
    return None

def parse_game(event):
    """解析比赛数据"""
    game_id = event.get('id')
    date_str = event.get('date', '')[:10]
    comp = event.get('competitions', [{}])[0]
    competitors = comp.get('competitors', [])
    
    if len(competitors) != 2:
        return []
    
    # 确定主队
    home_idx = None
    for i, c in enumerate(competitors):
        if c.get('homeAway') == 'home':
            home_idx = i
            break
    if home_idx is None:
        home_idx = 0
    
    records = []
    for i, c in enumerate(competitors):
        team = c.get('team', {})
        team_abbr = team.get('abbreviation')
        
        if team_abbr not in TEAMS:
            continue
        
        opp_c = competitors[1 - i]
        opp_team = opp_c.get('team', {})
        opp_abbr = opp_team.get('abbreviation')
        
        points = c.get('score')
        opp_points = opp_c.get('score')
        
        if points is None or opp_points is None:
            continue
        
        # 获取详细统计
        stats = c.get('statistics', [])
        
        # 投篮
        fg_made = get_stat(stats, 'fieldGoalsMade')
        fg_attempts = get_stat(stats, 'fieldGoalsAttempted')
        fg_pct = get_stat(stats, 'fieldGoalPct')
        
        # 三分
        fg3_made = get_stat(stats, 'threePointFieldGoalsMade')
        fg3_attempts = get_stat(stats, 'threePointFieldGoalsAttempted')
        fg3_pct = get_stat(stats, 'threePointFieldGoalPct')
        
        # 罚球
        ft_made = get_stat(stats, 'freeThrowsMade')
        ft_attempts = get_stat(stats, 'freeThrowsAttempted')
        ft_pct = get_stat(stats, 'freeThrowPct')
        
        # 其他统计
        rebounds = get_stat(stats, 'rebounds')
        assists = get_stat(stats, 'assists')
        
        # 判断胜负
        result = 'W' if int(points) > int(opp_points) else ('L' if int(points) < int(opp_points) else 'T')
        
        # 确定赛季
        game_date = datetime.strptime(date_str, '%Y-%m-%d')
        season = f"{game_date.year}-{str(game_date.year + 1)[-2:]}" if game_date.month >= 10 else f"{game_date.year - 1}-{str(game_date.year)[-2:]}"
        
        record = (
            f"{game_id}_{team_abbr}",           # game_id
            date_str,                            # game_date
            season,                              # season
            TEAMS[team_abbr]['id'],             # team_id
            team_abbr,                           # team_abbr
            TEAMS[team_abbr]['name'],           # team_name
            TEAMS.get(opp_abbr, {}).get('id', ''),  # opponent_id
            opp_abbr,                            # opponent_abbr
            TEAMS.get(opp_abbr, {}).get('name', ''),  # opponent_name
            i == home_idx,                       # is_home
            result,                              # result
            int(points),                        # points
            int(opp_points),                    # opponent_points
            int(points) - int(opp_points),     # point_diff
            int(fg_made) if fg_made else None, # fg_made
            int(fg_attempts) if fg_attempts else None,  # fg_attempts
            fg_pct,                             # fg_pct
            int(fg3_made) if fg3_made else None,  # fg3_made
            int(fg3_attempts) if fg3_attempts else None,  # fg3_attempts
            fg3_pct,                             # fg3_pct
            int(ft_made) if ft_made else None,  # ft_made
            int(ft_attempts) if ft_attempts else None,  # ft_attempts
            ft_pct,                             # ft_pct
            int(rebounds) if rebounds else None,  # rebounds
            int(assists) if assists else None,    # assists
            None,  # steals
            None,  # blocks
            None,  # turnovers
            None,  # fouls
            int(points) - int(opp_points),     # plus_minus
            'espn_api'                         # data_source
        )
        records.append(record)
    
    return records

def generate_urls(start_str, end_str, batch_size=5):
    """生成批量URL"""
    start = datetime.strptime(start_str, '%Y%m%d')
    end = datetime.strptime(end_str, '%Y%m%d')
    urls = []
    current = start
    while current <= end:
        urls.append(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={current.strftime('%Y%m%d')}")
        current += timedelta(days=1)
    return urls

def save_to_db(records):
    """保存到数据库"""
    if not records:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cnt = 0
    
    for r in records:
        try:
            cur.execute('''INSERT OR IGNORE INTO team_game_stats VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', r)
            if cur.rowcount > 0:
                cnt += 1
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    return cnt

def export_csv():
    """导出CSV"""
    import csv
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT * FROM team_game_stats ORDER BY game_date, team_abbr')
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    with open('data/team_game_stats.csv', 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(cols)
        csv.writer(f).writerows(rows)
    conn.close()
    return len(rows)

def export_excel():
    """导出Excel"""
    try:
        import pandas as pd
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query('SELECT * FROM team_game_stats ORDER BY game_date, team_abbr', conn)
        conn.close()
        df.to_excel('data/nba_data_all.xlsx', index=False, engine='openpyxl')
        return len(df)
    except:
        return 0

if __name__ == '__main__':
    print("=" * 50)
    print("ESPN NBA数据爬虫")
    print("=" * 50)
    print(f"球队数: {len(TEAMS)}")
    
    # 生成URL批次
    print("\n生成URL...")
    # 2024-25赛季
    s1_urls = generate_urls('20241022', '20250420')
    print(f"2024-25赛季: {len(s1_urls)} 天")
    
    # 2025-26赛季
    s2_urls = generate_urls('20251021', '20260423')
    print(f"2025-26赛季: {len(s2_urls)} 天")
    
    print("\n提示: 使用fetch_web工具并行获取以下URL:")
    print("\n=== 2024-25赛季 (第一批) ===")
    batch = s1_urls[:10]
    for u in batch:
        print(u)
