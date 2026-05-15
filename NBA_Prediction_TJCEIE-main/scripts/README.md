# NBA比赛数据爬虫使用说明

## 快速开始

### 1. 安装依赖

```bash
cd NBA比赛预测项目/scripts
pip install -r requirements.txt
```

或者直接安装：

```bash
pip install nba_api pandas tqdm
```

### 2. 运行脚本

#### 抓取所有赛季数据（2015-2026）
```bash
python fetch_nba_data.py
```

#### 抓取指定赛季
```bash
# 单个赛季
python fetch_nba_data.py --season 2023-24

# 多个赛季
python fetch_nba_data.py --seasons 2020-21 2021-22 2022-23
```

#### 拆分按赛季文件
```bash
python fetch_nba_data.py --split
```

## 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--season` | 指定单个赛季 | `--season 2023-24` |
| `--seasons` | 指定多个赛季 | `--seasons 2020-21 2021-22` |
| `--output` | 指定输出文件 | `--output data/my_data.csv` |
| `--split` | 拆分按赛季文件 | `--split` |
| `--include-details` | 获取详细Box Score | `--include-details` |
| `--help` | 显示帮助 | `--help` |

## 输出文件

运行后会生成以下文件：

```
NBA比赛预测项目/
├── data/
│   ├── nba_all_seasons.csv      # 合并的所有赛季数据
│   ├── nba_2015_16.csv          # 2015-16赛季数据 (使用--split时)
│   ├── nba_2016_17.csv          # 2016-17赛季数据
│   └── ...
└── scripts/
    └── fetch_nba_data.py        # 爬虫脚本
```

## 数据字段说明

| 字段 | 说明 |
|------|------|
| GAME_ID | 比赛唯一ID |
| TEAM_ID | 球队ID |
| TEAM_ABBREVIATION | 球队缩写 (如 LAL, GSW) |
| TEAM_NAME | 球队全名 |
| GAME_DATE | 比赛日期 |
| MATCHUP | 对阵信息 (如 LAL vs. GSW 表示主场) |
| WL | 胜负 (W=胜, L=负) |
| PTS | 得分 |
| FGM/FGA/FG_PCT | 投篮 命中数/尝试数/命中率 |
| FG3M/FG3A/FG3_PCT | 三分 命中数/尝试数/命中率 |
| FTM/FTA/FT_PCT | 罚球 命中数/尝试数/命中率 |
| OREB/DREB/REB | 前场篮板/后场篮板/总篮板 |
| AST | 助攻 |
| STL | 抢断 |
| BLK | 盖帽 |
| TOV | 失误 |
| PF | 犯规 |
| PLUS_MINUS | 正负值 |
| IS_HOME | 是否主场 (1=是, 0=否) |
| SEASON | 赛季标识 |

## 注意事项

1. **运行时间**：抓取10个赛季数据约需30-60分钟，请耐心等待
2. **网络要求**：需要稳定的网络连接，脚本会自动重试失败的请求
3. **速率限制**：NBA API有请求限制，脚本默认0.6秒请求间隔
4. **数据量**：约15,000+场比赛，每场2条记录（主客队各一条）

## 常见问题

### Q: 报错 "ModuleNotFoundError: No module named 'nba_api'"
A: 运行 `pip install nba_api pandas tqdm`

### Q: 报错 "API请求超时"
A: 检查网络连接，脚本会自动重试3次

### Q: 数据抓取太慢
A: 可以适当调整脚本中的 `API_REQUEST_DELAY` 参数（默认0.6秒）

### Q: 想抓取季后赛数据
A: 修改脚本中 `season_type_nullable` 参数为 'Playoffs'

## 数据用途

此数据适用于：
- NBA比赛结果预测模型
- 球队表现分析
- 球员历史数据统计
- 特征工程与机器学习
