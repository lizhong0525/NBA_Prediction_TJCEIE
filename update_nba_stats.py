#!/usr/bin/env python3
"""
批量获取ESPN NBA详细统计数据并更新数据库
"""
import json
import sqlite3
import requests
import time
from datetime import datetime, timedelta

DB_PATH = 'data/nba.db'
API = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'

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
    for s in stats:
        if s.get('name') == name:
            val = s.get('displayValue', '0')
            try:
                return float(val.replace('%', ''))
            except:
                return None
    return None

def fetch_game_stats(date_str):
    """获取某一天的比赛数据"""
    url = f'{API}/scoreboard?dates={date_str}'
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except:
        return []
    
    events = data.get('events', [])
    results = []
    
    for event in events:
        game_id = event.get('id')
        game_date = event.get('date', '')[:10]
        comp = event.get('competitions', [{}])[0]
        competitors = comp.get('competitors', [])
        
        if len(competitors) != 2:
            continue
        
        for i, c in enumerate(competitors):
            team = c.get('team', {})
            team_abbr = team.get('abbreviation')
            
            if team_abbr not in TEAMS:
                continue
            
            stats = c.get('statistics', [])
            
            fg_made = get_stat(stats, 'fieldGoalsMade')
            fg_attempts = get_stat(stats, 'fieldGoalsAttempted')
            fg_pct = get_stat(stats, 'fieldGoalPct')
            fg3_made = get_stat(stats, 'threePointFieldGoalsMade')
            fg3_attempts = get_stat(stats, 'threePointFieldGoalsAttempted')
            fg3_pct = get_stat(stats, 'threePointFieldGoalPct')
            ft_made = get_stat(stats, 'freeThrowsMade')
            ft_attempts = get_stat(stats, 'freeThrowsAttempted')
            ft_pct = get_stat(stats, 'freeThrowPct')
            rebounds = get_stat(stats, 'rebounds')
            assists = get_stat(stats, 'assists')
            
            # game_id格式: {game_id}_{team_abbr}
            results.append({
                'game_id': f"{game_id}_{team_abbr}",
                'fg_made': int(fg_made) if fg_made else None,
                'fg_attempts': int(fg_attempts) if fg_attempts else None,
                'fg_pct': fg_pct,
                'fg3_made': int(fg3_made) if fg3_made else None,
                'fg3_attempts': int(fg3_attempts) if fg3_attempts else None,
                'fg3_pct': fg3_pct,
                'ft_made': int(ft_made) if ft_made else None,
                'ft_attempts': int(ft_attempts) if ft_attempts else None,
                'ft_pct': ft_pct,
                'rebounds': int(rebounds) if rebounds else None,
                'assists': int(assists) if assists else None,
            })
    
    return results

def update_db(records):
    """更新数据库"""
    if not records:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cnt = 0
    
    for r in records:
        cur.execute('''
            UPDATE team_game_stats SET
                fg_made = COALESCE(?, fg_made),
                fg_attempts = COALESCE(?, fg_attempts),
                fg_pct = COALESCE(?, fg_pct),
                fg3_made = COALESCE(?, fg3_made),
                fg3_attempts = COALESCE(?, fg3_attempts),
                fg3_pct = COALESCE(?, fg3_pct),
                ft_made = COALESCE(?, ft_made),
                ft_attempts = COALESCE(?, ft_attempts),
                ft_pct = COALESCE(?, ft_pct),
                rebounds = COALESCE(?, rebounds),
                assists = COALESCE(?, assists)
            WHERE game_id = ?
        ''', (
            r['fg_made'], r['fg_attempts'], r['fg_pct'],
            r['fg3_made'], r['fg3_attempts'], r['fg3_pct'],
            r['ft_made'], r['ft_attempts'], r['ft_pct'],
            r['rebounds'], r['assists'],
            r['game_id']
        ))
        if cur.rowcount > 0:
            cnt += 1
    
    conn.commit()
    conn.close()
    return cnt

def export_csv():
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
    print("ESPN NBA详细数据更新")
    print("=" * 50)
    
    total_updated = 0
    
    # 2024-25赛季: 2024年10月 - 2025年4月
    print("\n2024-25赛季:")
    d = datetime(2024, 10, 22)
    end = datetime(2025, 4, 20)
    cnt = 0
    days = 0
    while d <= end:
        date_str = d.strftime('%Y%m%d')
        records = fetch_game_stats(date_str)
        if records:
            updated = update_db(records)
            cnt += updated
        d += timedelta(days=1)
        days += 1
        time.sleep(0.05)
        if days % 30 == 0:
            print(f"  进度: {d.strftime('%Y-%m-%d')}, 已更新 {cnt} 条")
    
    total_updated += cnt
    print(f"  2024-25更新: {cnt} 条")
    
    # 2025-26赛季
    print("\n2025-26赛季:")
    d = datetime(2025, 10, 21)
    end = datetime(2026, 4, 23)
    cnt = 0
    days = 0
    while d <= end:
        date_str = d.strftime('%Y%m%d')
        records = fetch_game_stats(date_str)
        if records:
            updated = update_db(records)
            cnt += updated
        d += timedelta(days=1)
        days += 1
        time.sleep(0.05)
        if days % 30 == 0:
            print(f"  进度: {d.strftime('%Y-%m-%d')}, 已更新 {cnt} 条")
    
    total_updated += cnt
    print(f"  2025-26更新: {cnt} 条")
    
    print(f"\n总计更新: {total_updated} 条")
    
    # 导出
    print("\n导出CSV...")
    n = export_csv()
    print(f"CSV: {n} 条")
    
    print("\n导出Excel...")
    n = export_excel()
    print(f"Excel: {n} 条")
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT season, COUNT(*) as total,
               SUM(CASE WHEN rebounds IS NOT NULL THEN 1 ELSE 0 END) as with_stats
        FROM team_game_stats 
        GROUP BY season 
        ORDER BY season
    ''')
    print("\n各赛季数据:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} 条 (详细统计: {row[2]} 条)")
    cur.execute('SELECT COUNT(*) FROM team_game_stats')
    print(f"\n总计: {cur.fetchone()[0]} 条")
    conn.close()
