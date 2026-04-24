#!/usr/bin/env python3
"""
NBA数据爬虫 - 极简版
"""
import sqlite3
import requests
import time
from datetime import datetime, timedelta

DB_PATH = 'data/nba.db'
API = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
teams = {}

def init():
    global teams
    r = requests.get(f'{API}/teams', timeout=15)
    for sport in r.json().get('sports', []):
        for lg in sport.get('leagues', []):
            for td in lg.get('teams', []):
                t = td.get('team', {})
                teams[t.get('abbreviation')] = {'id': t.get('id'), 'name': t.get('displayName')}

def fetch(date):
    try:
        r = requests.get(f'{API}/scoreboard?dates={date}', timeout=10)
        return r.json().get('events', [])
    except:
        return []

def parse(event):
    game_id = event.get('id')
    d = event.get('date', '')[:10]
    comp = event.get('competitions', [{}])[0]
    cs = comp.get('competitors', [])
    if len(cs) != 2:
        return []
    
    home = None
    for c in cs:
        if c.get('homeAway') == 'home':
            home = c.get('team', {}).get('abbreviation')
    
    recs = []
    for i, c in enumerate(cs):
        t = c.get('team', {})
        ta = t.get('abbreviation')
        if ta not in teams:
            continue
        oc = cs[1-i]
        oa = oc.get('team', {}).get('abbreviation')
        p, op = c.get('score'), oc.get('score')
        if p is None or op is None:
            continue
        gd = datetime.strptime(d, '%Y-%m-%d')
        season = f"{gd.year}-{str(gd.year+1)[-2:]}" if gd.month >= 10 else f"{gd.year-1}-{str(gd.year)[-2:]}"
        recs.append((
            f"{game_id}_{ta}", d, season,
            teams[ta]['id'], ta, teams[ta]['name'],
            teams.get(oa, {}).get('id', ''), oa, teams.get(oa, {}).get('name', ''),
            ta == home if home else i==0,
            'W' if int(p) > int(op) else ('L' if int(p) < int(op) else 'T'),
            int(p), int(op), int(p)-int(op),
            None, None, None, None, None, None, None, None, None,
            None, None, None, None, None, None,
            int(p)-int(op), 'espn_api'
        ))
    return recs

def save(recs):
    if not recs:
        return 0
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cnt = 0
    for r in recs:
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
    init()
    print(f"球队: {len(teams)}")
    
    all_recs = []
    # 2024-25: 2024年10月-2025年4月
    d = datetime(2024, 10, 22)
    end = datetime(2025, 4, 20)
    
    while d <= end:
        events = fetch(d.strftime('%Y%m%d'))
        for e in events:
            all_recs.extend(parse(e))
        d += timedelta(days=1)
        time.sleep(0.05)
    
    print(f"2024-25: {len(all_recs)} 条")
    cnt = save(all_recs)
    print(f"新增: {cnt}")
    
    # 2025-26: 2025年10月-2026年4月
    d = datetime(2025, 10, 21)
    end = datetime(2026, 4, 23)
    all_recs = []
    
    while d <= end:
        events = fetch(d.strftime('%Y%m%d'))
        for e in events:
            all_recs.extend(parse(e))
        d += timedelta(days=1)
        time.sleep(0.05)
    
    print(f"2025-26: {len(all_recs)} 条")
    cnt = save(all_recs)
    print(f"新增: {cnt}")
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT season, COUNT(*) FROM team_game_stats GROUP BY season ORDER BY season')
    print("\n各赛季:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]}")
    cur.execute('SELECT COUNT(*) FROM team_game_stats')
    print(f"总计: {cur.fetchone()[0]}")
    conn.close()
