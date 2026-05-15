#!/usr/bin/env python3
"""
ESPN NBA数据爬虫 - 补充2024-25和2025-26赛季数据
"""
import json
import sqlite3
import requests
import time
from datetime import datetime, timedelta
import os

# 配置
DB_PATH = 'data/nba.db'
API_BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
TEAMS_API = f'{API_BASE}/teams'

# 赛季日期范围
SEASONS = {
    '2024-25': {
        'start': '20241022',
        'end': '20250420',
        'year': 2024
    },
    '2025-26': {
        'start': '20251021',
        'end': '20260423',
        'year': 2025
    }
}

def get_teams():
    """获取所有NBA球队信息"""
    print("获取球队列表...")
    response = requests.get(TEAMS_API, timeout=30)
    data = response.json()
    
    teams = {}
    for sport in data.get('sports', []):
        for league in sport.get('leagues', []):
            for team_data in league.get('teams', []):
                team = team_data.get('team', {})
                teams[team.get('abbreviation')] = {
                    'id': team.get('id'),
                    'name': team.get('displayName'),
                    'abbr': team.get('abbreviation'),
                    'location': team.get('location'),
                    'nickname': team.get('nickname')
                }
    print(f"获取到 {len(teams)} 支球队")
    return teams

def get_games_for_date(date_str):
    """获取指定日期的比赛"""
    url = f'{API_BASE}/scoreboard?dates={date_str}'
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return []
        return response.json().get('events', [])
    except Exception as e:
        print(f"Error fetching {date_str}: {e}")
        return []

def parse_game(event, teams_dict):
    """解析比赛数据"""
    game_id = event.get('id')
    date_str = event.get('date', '')[:10]  # YYYY-MM-DD
    comp = event.get('competitions', [{}])[0]
    
    game_records = []
    competitors = comp.get('competitors', [])
    
    if len(competitors) != 2:
        return game_records
    
    # 解析主客场
    home_idx = None
    for i, c in enumerate(competitors):
        if c.get('homeAway') == 'home':
            home_idx = i
            break
    
    # 如果没有明确标识，尝试通过venue判断
    venue = comp.get('venue', {})
    if home_idx is None and venue:
        venue_name = venue.get('fullName', '')
        for i, c in enumerate(competitors):
            team_abbr = c.get('team', {}).get('abbreviation')
            # 简单判断：通常主队在前
            
    for i, c in enumerate(competitors):
        team_info = c.get('team', {})
        team_abbr = team_info.get('abbreviation')
        
        if team_abbr not in teams_dict:
            continue
            
        opponent_c = competitors[1 - i]
        opponent_info = opponent_c.get('team', {})
        opponent_abbr = opponent_info.get('abbreviation')
        
        points = c.get('score')
        opponent_points = opponent_c.get('score')
        
        if points is None or opponent_points is None:
            continue
        
        is_home = (i == 0)  # 简单假设第一个是主队
        
        # 判断胜负
        if int(points) > int(opponent_points):
            result = 'W'
        elif int(points) < int(opponent_points):
            result = 'L'
        else:
            result = 'T'
        
        # 确定赛季
        game_date = datetime.strptime(date_str, '%Y-%m-%d')
        if game_date.month >= 10:
            season = f"{game_date.year}-{str(game_date.year + 1)[-2:]}"
        else:
            season = f"{game_date.year - 1}-{str(game_date.year)[-2:]}"
        
        record = {
            'game_id': f"{game_id}_{team_abbr}",
            'game_date': date_str,
            'season': season,
            'team_id': teams_dict[team_abbr]['id'],
            'team_abbr': team_abbr,
            'team_name': teams_dict[team_abbr]['name'],
            'opponent_id': teams_dict.get(opponent_abbr, {}).get('id', ''),
            'opponent_abbr': opponent_abbr,
            'opponent_name': teams_dict.get(opponent_abbr, {}).get('name', ''),
            'is_home': is_home,
            'result': result,
            'points': int(points),
            'opponent_points': int(opponent_points),
            'point_diff': int(points) - int(opponent_points),
            # 详细统计数据 ESPN API不提供
            'fg_made': None,
            'fg_attempts': None,
            'fg_pct': None,
            'fg3_made': None,
            'fg3_attempts': None,
            'fg3_pct': None,
            'ft_made': None,
            'ft_attempts': None,
            'ft_pct': None,
            'rebounds': None,
            'assists': None,
            'steals': None,
            'blocks': None,
            'turnovers': None,
            'fouls': None,
            'plus_minus': int(points) - int(opponent_points),
            'data_source': 'espn_api'
        }
        
        game_records.append(record)
    
    return game_records

def date_range(start_str, end_str):
    """生成日期范围"""
    start = datetime.strptime(start_str, '%Y%m%d')
    end = datetime.strptime(end_str, '%Y%m%d')
    current = start
    while current <= end:
        yield current.strftime('%Y%m%d')
        current += timedelta(days=1)

def crawl_season(season_name, season_config):
    """爬取单个赛季数据"""
    print(f"\n{'='*50}")
    print(f"开始爬取 {season_name} 赛季...")
    print(f"日期范围: {season_config['start']} - {season_config['end']}")
    print('='*50)
    
    all_records = []
    dates = list(date_range(season_config['start'], season_config['end']))
    total_dates = len(dates)
    
    for idx, date_str in enumerate(dates):
        if idx % 30 == 0:
            print(f"进度: {idx}/{total_dates} ({100*idx/total_dates:.1f}%)")
        
        events = get_games_for_date(date_str)
        
        for event in events:
            records = parse_game(event, teams)
            all_records.extend(records)
        
        # 避免请求过快
        if idx % 7 == 0:
            time.sleep(0.5)
    
    print(f"爬取完成: 共获取 {len(all_records)} 条记录")
    return all_records

def save_to_db(records):
    """保存到数据库"""
    if not records:
        print("没有新记录需要保存")
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for record in records:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO team_game_stats 
                (game_id, game_date, season, team_id, team_abbr, team_name,
                 opponent_id, opponent_abbr, opponent_name, is_home, result,
                 points, opponent_points, point_diff, fg_made, fg_attempts, fg_pct,
                 fg3_made, fg3_attempts, fg3_pct, ft_made, ft_attempts, ft_pct,
                 rebounds, assists, steals, blocks, turnovers, fouls,
                 plus_minus, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record['game_id'], record['game_date'], record['season'],
                record['team_id'], record['team_abbr'], record['team_name'],
                record['opponent_id'], record['opponent_abbr'], record['opponent_name'],
                record['is_home'], record['result'], record['points'],
                record['opponent_points'], record['point_diff'],
                record['fg_made'], record['fg_attempts'], record['fg_pct'],
                record['fg3_made'], record['fg3_attempts'], record['fg3_pct'],
                record['ft_made'], record['ft_attempts'], record['ft_pct'],
                record['rebounds'], record['assists'], record['steals'],
                record['blocks'], record['turnovers'], record['fouls'],
                record['plus_minus'], record['data_source']
            ))
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            skipped += 1
            print(f"Error inserting {record['game_id']}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"数据库更新: 新增 {inserted} 条, 跳过 {skipped} 条(已存在)")
    return inserted

def export_csv():
    """导出CSV"""
    import csv
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM team_game_stats ORDER BY game_date, team_abbr')
    rows = cursor.fetchall()
    
    columns = [desc[0] for desc in cursor.description]
    
    with open('data/team_game_stats.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    
    conn.close()
    print(f"已导出CSV: {len(rows)} 条记录")

def export_excel():
    """导出Excel"""
    try:
        import pandas as pd
        
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query('SELECT * FROM team_game_stats ORDER BY game_date, team_abbr', conn)
        conn.close()
        
        df.to_excel('data/nba_data_all.xlsx', index=False, engine='openpyxl')
        print(f"已导出Excel: {len(df)} 条记录")
    except Exception as e:
        print(f"导出Excel失败: {e}")

if __name__ == '__main__':
    print("=" * 60)
    print("NBA数据爬虫 - 补充2024-25和2025-26赛季")
    print("=" * 60)
    
    # 获取球队列表
    teams = get_teams()
    
    # 爬取两个赛季的数据
    all_records = []
    for season_name, season_config in SEASONS.items():
        records = crawl_season(season_name, season_config)
        all_records.extend(records)
        time.sleep(2)  # 赛季之间暂停
    
    # 保存到数据库
    print(f"\n总计获取 {len(all_records)} 条记录")
    inserted = save_to_db(all_records)
    
    # 导出文件
    export_csv()
    export_excel()
    
    # 统计最终结果
    print("\n" + "=" * 60)
    print("爬取完成!")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT season, COUNT(*) as count 
        FROM team_game_stats 
        GROUP BY season 
        ORDER BY season
    ''')
    print("\n各赛季数据统计:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} 条")
    
    cursor.execute('SELECT COUNT(*) FROM team_game_stats')
    total = cursor.fetchone()[0]
    print(f"\n数据库总计: {total} 条记录")
    
    # 统计详细统计覆盖率
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN rebounds IS NOT NULL THEN 1 ELSE 0 END) as with_rebounds
        FROM team_game_stats
    ''')
    stats_row = cursor.fetchone()
    print(f"\n详细统计覆盖率: {stats_row[1]}/{stats_row[0]} ({100*stats_row[1]/stats_row[0]:.1f}%)")
    
    conn.close()
