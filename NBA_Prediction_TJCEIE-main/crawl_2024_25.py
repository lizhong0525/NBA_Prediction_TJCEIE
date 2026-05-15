#!/usr/bin/env python3
"""
NBA数据爬虫 - 分段执行 (2024-25赛季)
"""
import sqlite3
import requests
import time
from datetime import datetime, timedelta

DB_PATH = 'data/nba.db'
API_BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'

teams_cache = {}

def get_teams():
    global teams_cache
    response = requests.get(f'{API_BASE}/teams', timeout=30)
    for sport in response.json().get('sports', []):
        for league in sport.get('leagues', []):
            for team_data in league.get('teams', []):
                t = team_data.get('team', {})
                teams_cache[t.get('abbreviation')] = {'id': t.get('id'), 'name': t.get('displayName')}
    return teams_cache

def get_games(date_str):
    try:
        r = requests.get(f'{API_BASE}/scoreboard?dates={date_str}', timeout=15)
        return r.json().get('events', [])
    except:
        return []

def parse_game(event):
    game_id = event.get('id')
    date_str = event.get('date', '')[:10]
    comp = event.get('competitions', [{}])[0]
    records = []
    comps = comp.get('competitors', [])
    if len(comps) != 2:
        return records
    
    home_abbr = None
    for c in comps:
        if c.get('homeAway') == 'home':
            home_abbr = c.get('team', {}).get('abbreviation')
    
    for i, c in enumerate(comps):
        t = c.get('team', {})
        ta = t.get('abbreviation')
        if ta not in teams_cache:
            continue
        oc = comps[1-i]
        oa = oc.get('team', {}).get('abbreviation')
        p, op = c.get('score'), oc.get('score')
        if p is None or op is None:
            continue
        gd = datetime.strptime(date_str, '%Y-%m-%d')
        season = f"{gd.year}-{str(gd.year+1)[-2:]}" if gd.month >= 10 else f"{gd.year-1}-{str(gd.year)[-2:]}"
        records.append((
            f"{game_id}_{ta}", date_str, season,
            teams_cache[ta]['id'], ta, teams_cache[ta]['name'],
            teams_cache.get(oa, {}).get('id', ''), oa, teams_cache.get(oa, {}).get('name', ''),
            ta == home_abbr if home_abbr else i==0,
            'W' if int(p) > int(op) else ('L' if int(p) < int(op) else 'T'),
            int(p), int(op), int(p)-int(op),
            None, None, None, None, None, None, None, None, None,
            None, None, None, None, None, None,
            int(p)-int(op), 'espn_api'
        ))
    return records

def save(records):
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
        except:
            pass
    conn.commit()
    conn.close()
    return cnt

if __name__ == '__main__':
    print("获取球队...")
    get_teams()
    
    # 2024-25赛季: 2024年10月 - 2025年4月
    start = datetime(2024, 10, 22)
    end = datetime(2025, 4, 20)
    
    dates = []
    d = start
    while d <= end:
        dates.append(d.strftime('%Y%m%d'))
        d += timedelta(days=1)
    
    all_recs = []
    for idx, dt in enumerate(dates):
        events = get_games(dt)
        for e in events:
            all_recs.extend(parse_game(e))
        if (idx+1) % 20 == 0:
            print(f"进度: {idx+1}/{len(dates)}, 获取 {len(all_recs)} 条")
        time.sleep(0.1)
    
    print(f"\n保存 {len(all_recs)} 条...")
    cnt = save(all_recs)
    print(f"新增 {cnt} 条")
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT season, COUNT(*) FROM team_game_stats GROUP BY season ORDER BY season')
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} 条")
    cur.execute('SELECT COUNT(*) FROM team_game_stats')
    print(f"总计: {cur.fetchone()[0]} 条")
    conn.close()
