#!/usr/bin/env python3
"""
ESPN NBA数据爬虫 - 补充2024-25和2025-26赛季数据 (优化版)
"""
import json
import sqlite3
import requests
import time
from datetime import datetime, timedelta
import concurrent.futures

DB_PATH = 'data/nba.db'
API_BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
TEAMS_API = f'{API_BASE}/teams'

# 赛季配置
SEASONS = {
    '2024-25': ('20241022', '20250420'),
    '2025-26': ('20251021', '20260423')
}

# 球队缓存
teams_cache = {}

def get_teams():
    """获取球队列表"""
    global teams_cache
    if teams_cache:
        return teams_cache
    
    response = requests.get(TEAMS_API, timeout=30)
    data = response.json()
    
    for sport in data.get('sports', []):
        for league in sport.get('leagues', []):
            for team_data in league.get('teams', []):
                team = team_data.get('team', {})
                teams_cache[team.get('abbreviation')] = {
                    'id': team.get('id'),
                    'name': team.get('displayName'),
                }
    return teams_cache

def get_games_for_date(date_str):
    """获取指定日期的比赛"""
    url = f'{API_BASE}/scoreboard?dates={date_str}'
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            return []
        return response.json().get('events', [])
    except:
        return []

def parse_game(event):
    """解析比赛数据"""
    game_id = event.get('id')
    date_str = event.get('date', '')[:10]
    comp = event.get('competitions', [{}])[0]
    
    records = []
    competitors = comp.get('competitors', [])
    if len(competitors) != 2:
        return records
    
    # 尝试确定主队
    home_abbr = None
    for c in competitors:
        if c.get('homeAway') == 'home':
            home_abbr = c.get('team', {}).get('abbreviation')
    
    for i, c in enumerate(competitors):
        team_info = c.get('team', {})
        team_abbr = team_info.get('abbreviation')
        
        if team_abbr not in teams_cache:
            continue
        
        opp_c = competitors[1 - i]
        opp_info = opp_c.get('team', {})
        opp_abbr = opp_info.get('abbreviation')
        
        points = c.get('score')
        opp_points = opp_c.get('score')
        if points is None or opp_points is None:
            continue
        
        is_home = (team_abbr == home_abbr) if home_abbr else (i == 0)
        result = 'W' if int(points) > int(opp_points) else ('L' if int(points) < int(opp_points) else 'T')
        
        game_date = datetime.strptime(date_str, '%Y-%m-%d')
        season = f"{game_date.year}-{str(game_date.year + 1)[-2:]}" if game_date.month >= 10 else f"{game_date.year - 1}-{str(game_date.year)[-2:]}"
        
        records.append((
            f"{game_id}_{team_abbr}", date_str, season,
            teams_cache[team_abbr]['id'], team_abbr, teams_cache[team_abbr]['name'],
            teams_cache.get(opp_abbr, {}).get('id', ''), opp_abbr, teams_cache.get(opp_abbr, {}).get('name', ''),
            is_home, result, int(points), int(opp_points), int(points) - int(opp_points),
            None, None, None, None, None, None, None, None, None,
            None, None, None, None, None, None,
            int(points) - int(opp_points), 'espn_api'
        ))
    return records

def crawl_season(start_str, end_str):
    """快速爬取赛季数据"""
    print(f"爬取 {start_str} - {end_str}...")
    all_records = []
    dates = []
    current = datetime.strptime(start_str, '%Y%m%d')
    end = datetime.strptime(end_str, '%Y%m%d')
    
    # 只在10-4月期间查找（常规赛）
    while current <= end:
        if current.month in [10, 11, 12, 1, 2, 3, 4]:
            dates.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)
    
    print(f"检查 {len(dates)} 天...")
    
    for idx, d in enumerate(dates):
        events = get_games_for_date(d)
        for e in events:
            all_records.extend(parse_game(e))
        
        if (idx + 1) % 50 == 0:
            print(f"  进度: {idx+1}/{len(dates)}, 已获取 {len(all_records)} 条")
        
        time.sleep(0.1)  # 限速
    
    return all_records

def save_to_db(records):
    """保存到数据库"""
    if not records:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    inserted = 0
    
    for r in records:
        try:
            cur.execute('''INSERT OR IGNORE INTO team_game_stats 
                (game_id, game_date, season, team_id, team_abbr, team_name,
                 opponent_id, opponent_abbr, opponent_name, is_home, result,
                 points, opponent_points, point_diff, fg_made, fg_attempts, fg_pct,
                 fg3_made, fg3_attempts, fg3_pct, ft_made, ft_attempts, ft_pct,
                 rebounds, assists, steals, blocks, turnovers, fouls,
                 plus_minus, data_source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', r)
            if cur.rowcount > 0:
                inserted += 1
        except:
            pass
    
    conn.commit()
    conn.close()
    return inserted

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
    print(f"导出CSV: {len(rows)} 条")

def export_excel():
    """导出Excel"""
    try:
        import pandas as pd
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query('SELECT * FROM team_game_stats ORDER BY game_date, team_abbr', conn)
        conn.close()
        df.to_excel('data/nba_data_all.xlsx', index=False, engine='openpyxl')
        print(f"导出Excel: {len(df)} 条")
    except Exception as e:
        print(f"Excel导出失败: {e}")

if __name__ == '__main__':
    print("=" * 50)
    print("NBA数据爬虫 - 补充新赛季数据")
    print("=" * 50)
    
    get_teams()
    print(f"球队数: {len(teams_cache)}")
    
    all_records = []
    for season, (start, end) in SEASONS.items():
        print(f"\n>>> {season} <<<")
        recs = crawl_season(start, end)
        print(f"  获取 {len(recs)} 条记录")
        all_records.extend(recs)
        time.sleep(1)
    
    print(f"\n总计: {len(all_records)} 条")
    inserted = save_to_db(all_records)
    print(f"新增: {inserted} 条")
    
    export_csv()
    export_excel()
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT season, COUNT(*) FROM team_game_stats GROUP BY season ORDER BY season')
    print("\n各赛季数据:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} 条")
    cur.execute('SELECT COUNT(*) FROM team_game_stats')
    print(f"总计: {cur.fetchone()[0]} 条")
    conn.close()
