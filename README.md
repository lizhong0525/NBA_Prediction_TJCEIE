# NBA比赛预测系统

基于15年NBA历史数据，使用机器学习（K-Means聚类、PCA降维）进行比赛预测的Web系统。

## 📋 项目概述

本系统通过爬取Basketball Reference网站的历史比赛数据，利用无监督学习方法分析球队风格特征，为用户提供NBA比赛结果预测服务。

### 核心功能

- 🕷️ **数据采集**：自动爬取2011-12赛季至今的NBA历史比赛数据
- 📊 **数据分析**：特征工程、数据清洗、统计报表
- 🤖 **机器学习**：K-Means聚类分析球队风格、PCA降维提取关键特征
- 🎯 **比赛预测**：基于历史数据和统计分析的胜负预测
- 🌐 **Web界面**：可视化数据展示、交互式预测

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 爬虫 | Python + requests + BeautifulSoup |
| 数据处理 | Pandas + NumPy |
| 机器学习 | Scikit-learn (K-Means, PCA) |
| 后端 | Flask |
| 前端 | HTML/CSS/JS + Bootstrap + ECharts |
| 数据库 | SQLite |

## 📁 项目结构

```
NBA比赛预测项目/
├── SPEC.md                 # 项目规格说明文档
├── README.md               # 项目说明文档
├── requirements.txt        # Python依赖
├── config.py               # 配置文件
├── run.py                  # 应用入口
│
├── app/                    # Flask应用
│   ├── __init__.py
│   ├── models/
│   │   └── database.py    # 数据库管理
│   ├── views.py           # 路由和视图
│   └── templates/          # HTML模板
│       ├── index.html
│       ├── predict.html
│       ├── team.html
│       ├── data.html
│       └── about.html
│
├── crawler/               # 爬虫模块
│   ├── spider.py          # Basketball Reference爬虫
│   └── parser.py          # 数据解析器
│
├── ml/                    # 机器学习模块
│   ├── features.py        # 特征工程
│   ├── cluster.py         # 聚类分析
│   └── predict.py         # 比赛预测
│
├── utils/                 # 工具模块
│   └── logger.py          # 日志记录
│
├── data/                  # 数据目录
│   ├── raw/               # 原始数据
│   ├── processed/         # 处理后数据
│   └── nba.db            # SQLite数据库
│
└── tests/                 # 测试模块
    ├── test_crawler.py
    └── test_ml.py
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.9+
- pip

### 2. 安装依赖

```bash
cd NBA比赛预测项目
pip install -r requirements.txt
```

### 3. 运行应用

```bash
python run.py
```

访问 http://localhost:5000 查看应用。

### 4. 运行测试

```bash
cd NBA比赛预测项目
pytest tests/ -v
```

## 📖 主要模块说明

### 爬虫模块 (crawler/)

**BasketballReferenceSpider** - 数据爬虫类

```python
from crawler import BasketballReferenceSpider

spider = BasketballReferenceSpider()

# 获取球队比赛日志
games = spider.fetch_team_game_log('LAL', 2024)

# 获取赛季赛程
schedule = spider.fetch_season_schedule(2024)

# 历史数据全量爬取
stats = spider.historical_crawl(start_year=2012, end_year=2024)

spider.close()
```

**DataParser** - 数据解析器

```python
from crawler import DataParser

parser = DataParser()

# 解析比赛数据
df = parser.parse_game_data(raw_games)

# 计算衍生特征
df = parser.compute_derived_features(df, window=5)

# 计算球队赛季统计
season_stats = parser.compute_team_season_stats(df)
```

### 机器学习模块 (ml/)

**FeatureEngineer** - 特征工程

```python
from ml import FeatureEngineer

engineer = FeatureEngineer()

# 准备特征
features = engineer.prepare_features(df)

# 标准化
scaled, scaler = engineer.scale_features(features)

# PCA降维
reduced, pca = engineer.reduce_dimensions(scaled)
```

**TeamClusterAnalyzer** - 球队聚类分析

```python
from ml import TeamClusterAnalyzer

analyzer = TeamClusterAnalyzer()

# 聚类分析
labels, metrics = analyzer.fit_cluster(features, n_clusters=4)

# 寻找最优聚类数
optimal_k, results = analyzer.find_optimal_clusters(features)
```

**GamePredictor** - 比赛预测

```python
from ml import GamePredictor

predictor = GamePredictor()

# 预测比赛
result = predictor.predict_game('LAL', 'GSW', home_stats, away_stats)

print(result['predicted_winner'])       # 预测胜者
print(result['win_probability'])        # 胜率
print(result['confidence_level'])       # 置信度
print(result['key_factors'])            # 关键因素
```

### 数据库模块 (app/models/)

```python
from app.models import init_database

db = init_database()

# 插入比赛数据
db.insert_game_data(games)

# 获取比赛数据
games = db.get_game_data(team_abbr='LAL', season='2023-24')

# 获取球队赛季统计
stats = db.get_team_season_stats(team_abbr='LAL')

# 保存预测结果
db.insert_prediction(prediction)

# 获取预测准确率
accuracy = db.get_prediction_accuracy()
```

## 🌐 API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/home` | GET | 获取首页数据 |
| `/api/teams` | GET | 获取球队列表 |
| `/api/team/<abbr>` | GET | 获取球队详情 |
| `/api/predict` | POST | 预测比赛结果 |
| `/api/predictions/history` | GET | 获取预测历史 |
| `/api/games` | GET | 获取比赛列表 |
| `/api/stats/ranking` | GET | 获取数据排名 |
| `/api/health` | GET | 健康检查 |

## 📊 数据字段

### 球队比赛数据 (team_game_stats)

- `game_id`: 比赛唯一ID
- `game_date`: 比赛日期
- `team_id/abbr/name`: 球队信息
- `opponent_*`: 对手信息
- `is_home`: 是否主场
- `result`: 比赛结果 (W/L)
- `points/opponent_points`: 得分/失分
- `fg_pct/fg3_pct/ft_pct`: 命中率
- `rebounds/assists/steals/blocks/turnovers`: 其他统计

### 衍生特征

- `recent_5_win_pct`: 近5场胜率
- `recent_avg_points`: 近5场平均得分
- `home_win_pct/away_win_pct`: 主/客场胜率
- `offensive_rating/defensive_rating`: 进攻/防守效率

## 🔧 配置说明

主要配置项在 `config.py` 中：

```python
# 数据库配置
DATABASE_CONFIG = {
    'type': 'sqlite',
    'path': 'data/nba.db'
}

# 爬虫配置
CRAWLER_CONFIG = {
    'base_url': 'https://www.basketball-reference.com',
    'request_delay': 3,  # 请求间隔(秒)
    'max_retries': 3
}

# 机器学习配置
ML_CONFIG = {
    'clustering': {'n_clusters': 4},
    'pca': {'n_components': 0.95}
}
```

## ⚠️ 免责声明

本系统仅供娱乐和学习研究使用。体育比赛结果存在不确定性，任何预测都无法保证100%准确。系统预测仅供参考，不构成任何形式的投注建议。请理性看待预测结果，切勿沉迷投注。

## 📅 开发计划

- [x] Phase 1: 爬虫模块 + 数据库
- [x] Phase 2: 机器学习分析
- [x] Phase 3: Flask后端 + API
- [x] Phase 4: 前端页面
- [ ] Phase 5: 测试优化 + 部署

## 📝 License

MIT License

---

*Built with ❤️ for NBA fans*
