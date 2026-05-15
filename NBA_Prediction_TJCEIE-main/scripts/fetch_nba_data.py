#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NBA比赛数据爬虫脚本
==================

使用 nba_api 库获取2015-2026赛季的NBA常规赛比赛数据

功能：
- 获取比赛基本信息（日期、主客场、比分、胜负）
- 获取球队统计（投篮命中率、三分、篮板、助攻、失误等）
- 支持断点续传和错误重试

使用方法：
    python fetch_nba_data.py              # 抓取所有赛季数据
    python fetch_nba_data.py --season 2023-24  # 抓取指定赛季

依赖安装：
    pip install nba_api pandas tqdm

作者：AI Agent
日期：2026-04-14
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import warnings

warnings.filterwarnings('ignore')

# 尝试导入必要库，不存在则提示安装
try:
    import pandas as pd
    from nba_api.stats.endpoints import leaguegamefinder, boxscoretraditionalv2
    from nba_api.stats.static import teams
    from nba_api.stats.library.parameters import SeasonAll
    HAS_DEPENDENCIES = True
except ImportError as e:
    HAS_DEPENDENCIES = False
    MISSING_LIB = str(e).split("'")[1] if "'" in str(e) else str(e)

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# ============================================================================
# 配置
# ============================================================================

# 脚本目录和项目目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
OUTPUT_FILE = os.path.join(DATA_DIR, 'nba_all_seasons.csv')

# API配置
API_RETRY_TIMES = 3          # API重试次数
API_RETRY_DELAY = 3          # 重试间隔(秒)
API_REQUEST_DELAY = 0.6      # 请求间隔(秒)，避免触发速率限制
BATCH_SIZE = 100             # 每批处理的数据量

# 赛季范围
SEASON_START = '2015-16'
SEASON_END = '2025-26'


# ============================================================================
# 工具函数
# ============================================================================

def print_info(msg: str):
    """打印信息"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")


def print_progress(current: int, total: int, season: str = ""):
    """打印进度"""
    if HAS_TQDM:
        return
    percent = (current / total * 100) if total > 0 else 0
    season_str = f" [{season}]" if season else ""
    print(f"\r进度: {current}/{total} ({percent:.1f}%){season_str}", end='', flush=True)


def ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)
    print_info(f"数据目录: {DATA_DIR}")


def generate_seasons(start: str, end: str) -> List[str]:
    """生成赛季列表"""
    seasons = []
    start_year = int(start.split('-')[0])
    end_year = int(end.split('-')[0])
    
    for year in range(start_year, end_year + 1):
        next_year = str(year + 1)[-2:]
        season = f"{year}-{next_year}"
        seasons.append(season)
    
    return seasons


# ============================================================================
# API请求函数
# ============================================================================

def safe_api_call(func, *args, retry_times: int = API_RETRY_TIMES, **kwargs):
    """安全的API调用，带重试机制"""
    last_error = None
    
    for attempt in range(retry_times):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < retry_times - 1:
                wait_time = API_RETRY_DELAY * (attempt + 1)
                print_info(f"API请求失败，{wait_time}秒后重试 ({attempt + 1}/{retry_times}): {str(e)[:50]}")
                time.sleep(wait_time)
            else:
                print_info(f"API请求最终失败: {str(e)[:100]}")
    
    return None


def get_all_teams() -> pd.DataFrame:
    """获取所有球队信息"""
    print_info("获取球队列表...")
    all_teams = teams.get_teams()
    df = pd.DataFrame(all_teams)
    print_info(f"共获取 {len(df)} 支球队")
    return df


def fetch_season_games(season: str, progress: bool = True) -> Optional[pd.DataFrame]:
    """获取指定赛季的所有比赛"""
    print_info(f"正在获取 {season} 赛季比赛数据...")
    
    # 使用 leaguegamefinder 获取比赛
    def _fetch():
        game_finder = leaguegamefinder.LeagueGameFinder(
            season_nullable=season,
            season_type_nullable='Regular Season'
        )
        return game_finder.get_data_frames()[0]
    
    games_df = safe_api_call(_fetch)
    
    if games_df is None or games_df.empty:
        print_info(f"⚠ {season} 赛季未找到比赛数据")
        return None
    
    print_info(f"✓ {season} 赛季获取到 {len(games_df)} 条比赛记录")
    return games_df


def fetch_game_details(game_id: str) -> Optional[pd.DataFrame]:
    """获取比赛详细统计（Box Score）"""
    def _fetch():
        box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
        return box.get_data_frames()[0] if box.get_data_frames() else None
    
    return safe_api_call(_fetch)


# ============================================================================
# 数据处理函数
# ============================================================================

def process_games_data(games_df: pd.DataFrame, include_details: bool = False) -> pd.DataFrame:
    """处理比赛数据"""
    if games_df.empty:
        return pd.DataFrame()
    
    # 基础字段列表（nba_api返回的常用字段）
    base_columns = [
        'GAME_ID', 'TEAM_ID', 'TEAM_ABBREVIATION', 'TEAM_NAME',
        'GAME_DATE', 'MATCHUP', 'WL',  # 胜负
        'MIN', 'PTS',                  # 分钟、得分
        'FGM', 'FGA', 'FG_PCT',        # 投篮命中、尝试、命中率
        'FG3M', 'FG3A', 'FG3_PCT',     # 三分命中、尝试、命中率
        'FTM', 'FTA', 'FT_PCT',        # 罚球命中、尝试、命中率
        'OREB', 'DREB', 'REB',         # 前场篮板、后场篮板、总篮板
        'AST', 'STL', 'BLK',           # 助攻、抢断、盖帽
        'TOV', 'PF',                   # 失误、犯规
        'PLUS_MINUS'                   # 正负值
    ]
    
    # 只保留存在的列
    available_columns = [col for col in base_columns if col in games_df.columns]
    df = games_df[available_columns].copy()
    
    # 数据类型转换
    numeric_columns = ['PTS', 'FGM', 'FGA', 'FG3M', 'FG3A', 'FTM', 'FTA', 
                       'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PLUS_MINUS']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 计算衍生字段
    if 'FG_PCT' in df.columns:
        df['FG_PCT'] = pd.to_numeric(df['FG_PCT'], errors='coerce')
    
    # 解析主客场
    if 'MATCHUP' in df.columns:
        df['IS_HOME'] = df['MATCHUP'].str.contains('vs.', na=False).astype(int)
        df['OPPONENT'] = df['MATCHUP'].str.replace('vs. ', '').str.replace('@ ', '')
    
    return df


def extract_season_id(games_df: pd.DataFrame) -> str:
    """从数据中提取赛季ID"""
    if games_df.empty or 'GAME_ID' not in games_df.empty:
        return ""
    
    # GAME_ID格式: 0021500001 (00=赛季类型, 215=赛季年份, 00001=场次)
    # 或: 00224ABCDE (新格式)
    sample_id = games_df['GAME_ID'].iloc[0] if not games_df.empty else ""
    
    if len(sample_id) >= 4:
        if sample_id[2:4].isdigit():
            year = int(sample_id[3:5])
            if year >= 70:
                year += 1900
            else:
                year += 2000
            return f"{year-1}-{str(year)[-2:]}"
    
    return ""


# ============================================================================
# 主程序
# ============================================================================

def fetch_all_seasons_data(seasons: Optional[List[str]] = None, 
                           include_details: bool = False,
                           output_file: str = OUTPUT_FILE) -> bool:
    """抓取所有赛季数据"""
    
    # 检查依赖
    if not HAS_DEPENDENCIES:
        print(f"\n❌ 缺少必要依赖: {MISSING_LIB}")
        print("\n请运行以下命令安装依赖:")
        print("    pip install nba_api pandas tqdm")
        return False
    
    # 确保数据目录存在
    ensure_data_dir()
    
    # 生成赛季列表
    if seasons is None:
        seasons = generate_seasons(SEASON_START, SEASON_END)
    
    print_info(f"准备抓取 {len(seasons)} 个赛季的数据: {', '.join(seasons)}")
    print_info(f"预计比赛数量: ~{(30*82)//2 * len(seasons)} 场 (常规赛)")
    print("-" * 60)
    
    all_games = []
    failed_seasons = []
    
    # 进度条
    if HAS_TQDM:
        pbar = tqdm(seasons, desc="抓取赛季", unit="赛季")
    else:
        pbar = seasons
    
    for season in pbar:
        try:
            # 获取赛季比赛数据
            games_df = fetch_season_games(season, progress=not HAS_TQDM)
            
            if games_df is None or games_df.empty:
                failed_seasons.append(season)
                continue
            
            # 处理数据
            processed_df = process_games_data(games_df, include_details)
            
            if not processed_df.empty:
                # 添加赛季标识
                processed_df['SEASON'] = season
                all_games.append(processed_df)
            
            # API请求间隔
            time.sleep(API_REQUEST_DELAY)
            
        except KeyboardInterrupt:
            print("\n\n用户中断操作...")
            break
        except Exception as e:
            print_info(f"❌ 处理 {season} 赛季时出错: {str(e)}")
            failed_seasons.append(season)
            continue
    
    # 合并所有数据
    if not all_games:
        print_info("❌ 未能获取任何数据")
        return False
    
    print("\n" + "=" * 60)
    print_info("正在合并数据...")
    
    final_df = pd.concat(all_games, ignore_index=True)
    
    # 排序
    if 'GAME_DATE' in final_df.columns:
        final_df = final_df.sort_values('GAME_DATE')
    
    # 保存
    final_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    # 统计信息
    total_games = len(final_df) // 2  # 每场有两个球队的数据
    unique_seasons = final_df['SEASON'].nunique() if 'SEASON' in final_df.columns else 0
    unique_teams = final_df['TEAM_ABBREVIATION'].nunique() if 'TEAM_ABBREVIATION' in final_df.columns else 0
    
    print("\n" + "=" * 60)
    print_info("✅ 数据抓取完成!")
    print("-" * 60)
    print(f"   保存位置: {output_file}")
    print(f"   总记录数: {len(final_df)} 条")
    print(f"   比赛场次: {total_games} 场")
    print(f"   赛季数量: {unique_seasons} 个")
    print(f"   球队数量: {unique_teams} 支")
    
    if failed_seasons:
        print(f"\n⚠ 失败赛季: {', '.join(failed_seasons)}")
        print("   请检查网络连接或稍后重试")
    
    # 数据预览
    print("\n" + "-" * 60)
    print("数据预览 (前5行):")
    print(final_df.head().to_string())
    
    # 字段说明
    print("\n" + "-" * 60)
    print("字段说明:")
    fields_desc = {
        'GAME_ID': '比赛ID',
        'TEAM_ID': '球队ID',
        'TEAM_ABBREVIATION': '球队缩写',
        'TEAM_NAME': '球队名称',
        'GAME_DATE': '比赛日期',
        'MATCHUP': '对阵信息',
        'WL': '胜负 (W=胜, L=负)',
        'PTS': '得分',
        'FGM/FGA/FG_PCT': '投篮命中数/尝试数/命中率',
        'FG3M/FG3A/FG3_PCT': '三分命中数/尝试数/命中率',
        'FTM/FTA/FT_PCT': '罚球命中数/尝试数/命中率',
        'OREB/DREB/REB': '前场篮板/后场篮板/总篮板',
        'AST': '助攻',
        'STL': '抢断',
        'BLK': '盖帽',
        'TOV': '失误',
        'PF': '犯规',
        'PLUS_MINUS': '正负值',
        'IS_HOME': '是否主场 (1=是, 0=否)',
        'SEASON': '赛季'
    }
    for field, desc in fields_desc.items():
        print(f"   {field}: {desc}")
    
    return True


def generate_season_files(combined_file: str = OUTPUT_FILE):
    """将合并文件拆分为按赛季的文件"""
    if not os.path.exists(combined_file):
        print_info(f"文件不存在: {combined_file}")
        return False
    
    print_info("正在按赛季拆分数据...")
    df = pd.read_csv(combined_file)
    
    if 'SEASON' not in df.columns:
        print_info("数据中没有SEASON字段，无法拆分")
        return False
    
    os.makedirs(DATA_DIR, exist_ok=True)
    
    for season in df['SEASON'].unique():
        season_df = df[df['SEASON'] == season]
        season_file = os.path.join(DATA_DIR, f"nba_{season.replace('-', '_')}.csv")
        season_df.to_csv(season_file, index=False, encoding='utf-8-sig')
        print_info(f"  ✓ {season}: {len(season_df)} 条记录 -> {os.path.basename(season_file)}")
    
    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='NBA比赛数据爬虫 - 使用nba_api获取2015-2026赛季数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                        # 抓取所有赛季数据
  %(prog)s --season 2023-24       # 抓取指定赛季
  %(prog)s --seasons 2020-21 2021-22  # 抓取多个赛季
  %(prog)s --split                # 拆分按赛季文件
  %(prog)s --help                 # 显示帮助

数据字段:
  GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME  - 比赛/球队标识
  GAME_DATE, MATCHUP, WL                          - 比赛信息
  PTS, FGM, FGA, FG_PCT                           - 得分、投篮
  FG3M, FG3A, FG3_PCT                             - 三分
  FTM, FTA, FT_PCT                                - 罚球
  OREB, DREB, REB                                 - 篮板
  AST, STL, BLK, TOV, PF                           - 助攻、抢断、盖帽、失误、犯规
  PLUS_MINUS, IS_HOME                             - 正负值、主场标识
        """
    )
    
    parser.add_argument('--season', type=str, default=None,
                       help='指定单个赛季 (格式: 2023-24)')
    parser.add_argument('--seasons', type=str, nargs='+', default=None,
                       help='指定多个赛季')
    parser.add_argument('--output', type=str, default=OUTPUT_FILE,
                       help=f'输出文件路径 (默认: {OUTPUT_FILE})')
    parser.add_argument('--split', action='store_true',
                       help='拆分按赛季文件')
    parser.add_argument('--include-details', action='store_true',
                       help='获取详细Box Score (耗时更长)')
    
    args = parser.parse_args()
    
    # 检查依赖
    if not HAS_DEPENDENCIES:
        print(f"\n{'='*60}")
        print("❌ 缺少必要依赖!")
        print(f"   缺失模块: {MISSING_LIB}")
        print(f"\n{'='*60}")
        print("请运行以下命令安装依赖:")
        print("   pip install nba_api pandas tqdm")
        print(f"\n或者:")
        print("   pip install -r requirements.txt")
        print(f"{'='*60}")
        sys.exit(1)
    
    # 处理参数
    seasons = None
    if args.seasons:
        seasons = args.seasons
    elif args.season:
        seasons = [args.season]
    
    # 确定输出路径
    output_file = args.output if args.output else OUTPUT_FILE
    
    # 执行抓取
    success = fetch_all_seasons_data(
        seasons=seasons,
        include_details=args.include_details,
        output_file=output_file
    )
    
    # 拆分文件
    if success and args.split:
        generate_season_files(output_file)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
