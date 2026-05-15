# NBA比赛预测系统 - 规格说明文档

## 1. 项目概述

### 1.1 项目目标
构建一个基于历史数据的NBA比赛预测系统，通过爬取球队统计数据，利用无监督学习挖掘影响比赛结果的关键因素，最终通过Web界面提供比赛预测服务。

### 1.2 技术栈
- **爬虫层**: Python + requests/BeautifulSoup + Selenium
- **数据处理**: Pandas + NumPy
- **机器学习**: Scikit-learn（无监督学习：K-Means、PCA等）
- **后端**: Flask
- **前端**: HTML/CSS/JavaScript + Bootstrap/ECharts
- **数据库**: SQLite/MySQL

### 1.3 系统架构
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   爬虫模块   │ →  │  数据存储层  │ →  │  分析预测层  │
└─────────────┘    └─────────────┘    └─────────────┘
                                            ↓
       ┌────────────────────────────────────────┐
       │            Flask Web服务层              │
       │  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
       │  │ 首页    │  │ 预测页  │  │ 数据页  │ │
       │  └─────────┘  └─────────┘  └─────────┘ │
       └────────────────────────────────────────┘
```

---

## 2. 数据规范

### 2.1 数据来源
- **主数据源**: Basketball Reference (basketball-reference.com)
  - 业界公认最权威的NBA历史数据库
  - 数据完整、结构规范、无反爬限制
- **备选数据源**: 
  - NBA官网 (nba.com/stats) - 官方实时数据
  - 虎扑NBA (nba.hupu.com) - 中文展示

### 2.1.1 Basketball Reference 数据页面说明
| 数据类型 | URL模式 | 说明 |
|----------|---------|------|
| 球队赛季 | `/teams/{team}/{year}.html` | 如 `/teams/LAL/2026.html` |
| 赛季总览 | `/leagues/NBA_{year}.html` | 某赛季所有球队/球员数据 |
| 球员生涯 | `/players/{first_letter}/{player}.html` | 如 `/players/j/jamesle01.html` |
| 比赛记录 | `/boxscores/{game_id}.html` | 单场比赛详细数据 |
| 历史赛程 | `/leagues/NBA_{year}_games.html` | 某赛季完整赛程 |

**球队缩写对照（Basketball Reference格式）:**
ATL(老鹰), BOS(凯尔特人), BRK(篮网), CHI(公牛), CHO(黄蜂), CLE(骑士), DET(活塞), IND(步行者), MIA(热火), MIL(雄鹿), NYK(尼克斯), ORL(魔术), PHI(76人), TOR(猛龙), WAS(奇才), DAL(独行侠), DEN(掘金), GSW(勇士), HOU(火箭), LAC(快船), LAL(湖人), MEM(灰熊), MIN(森林狼), NOP(鹈鹕), OKC(雷霆), PHO(太阳), POR(开拓者), SAC(国王), SAS(马刺), UTA(爵士)

### 2.2 数据字段定义

#### 2.2.1 球队比赛数据（TeamGameStats）
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| game_id | VARCHAR(20) | 比赛唯一标识 | "0022300001" |
| game_date | DATE | 比赛日期 | 2024-01-15 |
| season | VARCHAR(10) | 赛季 | "2023-24" |
| team_id | VARCHAR(10) | 球队ID | "1610612744" |
| team_name | VARCHAR(50) | 球队名称 | "Golden State Warriors" |
| opponent_id | VARCHAR(10) | 对手ID | "1610612745" |
| opponent_name | VARCHAR(50) | 对手名称 | "Los Angeles Lakers" |
| is_home | BOOLEAN | 是否主场 | true |
| result | VARCHAR(1) | 比赛结果 | W/L |
| points | INT | 得分 | 118 |
| opponent_points | INT | 对手得分 | 112 |
| fg_made | INT | 投篮命中数 | 45 |
| fg_attempts | INT | 投篮出手数 | 92 |
| fg_pct | FLOAT | 投篮命中率 | 0.489 |
| fg3_made | INT | 三分命中数 | 16 |
| fg3_attempts | INT | 三分出手数 | 38 |
| fg3_pct | FLOAT | 三分命中率 | 0.421 |
| ft_made | INT | 罚球命中数 | 12 |
| ft_attempts | INT | 罚球出手数 | 15 |
| ft_pct | FLOAT | 罚球命中率 | 0.800 |
| rebounds_off | INT | 进攻篮板 | 12 |
| rebounds_def | INT | 防守篮板 | 35 |
| rebounds_total | INT | 总篮板 | 47 |
| assists | INT | 助攻 | 28 |
| steals | INT | 抢断 | 9 |
| blocks | INT | 盖帽 | 5 |
| turnovers | INT | 失误 | 14 |
| fouls | INT | 犯规 | 18 |
| plus_minus | INT | 正负值 | +6 |

#### 2.2.2 球队赛季统计（TeamSeasonStats）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| team_id | VARCHAR(10) | 球队ID |
| season | VARCHAR(10) | 赛季 |
| games_played | INT | 比赛场次 |
| wins | INT | 胜场 |
| losses | INT | 负场 |
| win_pct | FLOAT | 胜率 |
| avg_points | FLOAT | 场均得分 |
| avg_points_allowed | FLOAT | 场均失分 |
| avg_fg_pct | FLOAT | 场均投篮命中率 |
| avg_fg3_pct | FLOAT | 场均三分命中率 |
| avg_rebounds | FLOAT | 场均篮板 |
| avg_assists | FLOAT | 场均助攻 |
| avg_steals | FLOAT | 场均抢断 |
| avg_blocks | FLOAT | 场均盖帽 |
| avg_turnovers | FLOAT | 场均失误 |
| home_win_pct | FLOAT | 主场胜率 |
| away_win_pct | FLOAT | 客场胜率 |

#### 2.2.3 预测结果（PredictionResult）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| prediction_id | VARCHAR(20) | 预测ID |
| game_id | VARCHAR(20) | 比赛ID |
| home_team | VARCHAR(50) | 主队 |
| away_team | VARCHAR(50) | 客队 |
| predicted_winner | VARCHAR(50) | 预测胜队 |
| win_probability | FLOAT | 胜率预测 |
| confidence_level | VARCHAR(10) | 置信度等级 |
| key_factors | TEXT | 关键因素(JSON) |
| model_version | VARCHAR(20) | 模型版本 |
| created_at | DATETIME | 预测时间 |

### 2.3 数据存储规范
- 数据库: SQLite（开发）/ MySQL（生产）
- 数据更新频率: 每日一次（北京时间上午，NBA比赛结束后）
- 历史数据范围: **2011-2012赛季 至今**（约15个赛季）
  - 2011-12, 2012-13, 2013-14, 2014-15, 2015-16
  - 2016-17, 2017-18, 2018-19, 2019-20, 2020-21
  - 2021-22, 2022-23, 2023-24, 2024-25, 2025-26(当前)

### 2.4 数据量估算
- 每赛季: 30队 × 82场 ÷ 2 ≈ 1,230场比赛
- 15赛季总计: 约 **18,450场比赛记录**
- 数据采集周期: 首次全量爬取约需 2-3 小时

---

## 3. 功能模块规范

### 3.1 爬虫模块

#### 3.1.1 功能需求
- 支持爬取NBA官网比赛数据
- 支持增量更新（只爬取新比赛）
- 支持异常处理和重试机制
- 遵守robots.txt，设置合理请求间隔

#### 3.1.2 接口设计
```python
class BasketballReferenceSpider:
    """Basketball Reference数据爬虫"""
    
    def __init__(self):
        """初始化爬虫"""
        self.base_url = "https://www.basketball-reference.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.request_delay = 3  # 请求间隔(秒)，遵守robots.txt
    
    def fetch_season_summary(self, year: int) -> dict:
        """获取赛季总览数据
        
        Args:
            year: 赛季结束年份，如2026表示2025-26赛季
        Returns:
            包含球队排名、球员统计等数据的字典
        URL: /leagues/NBA_{year}.html
        """
        pass
    
    def fetch_team_season_stats(self, team_abbr: str, year: int) -> dict:
        """获取球队赛季统计
        
        Args:
            team_abbr: 球队缩写如 "LAL", "GSW"
            year: 赛季结束年份
        URL: /teams/{team}/{year}.html
        """
        pass
    
    def fetch_team_game_log(self, team_abbr: str, year: int) -> List[dict]:
        """获取球队赛季每场比赛数据
        
        URL: /teams/{team}/{year}_games.html
        Returns:
            每场比赛的详细数据列表
        """
        pass
    
    def fetch_season_schedule(self, year: int) -> List[dict]:
        """获取赛季完整赛程和结果
        
        URL: /leagues/NBA_{year}_games.html
        Returns:
            该赛季所有比赛列表
        """
        pass
    
    def fetch_box_score(self, game_id: str) -> dict:
        """获取单场比赛详细数据
        
        Args:
            game_id: 比赛ID，如 "20260101LALGSW"
        URL: /boxscores/{game_id}.html
        """
        pass
    
    def fetch_player_stats(self, year: int, stat_type: str = "per_game") -> List[dict]:
        """获取球员赛季统计
        
        Args:
            year: 赛季年份
            stat_type: 统计类型
                - per_game: 场均
                - totals: 总计
                - advanced: 高阶数据
        URL: /leagues/NBA_{year}_{stat_type}.html
        """
        pass
    
    def historical_crawl(self, start_year: int = 2012, end_year: int = 2026) -> int:
        """历史数据全量爬取
        
        Args:
            start_year: 起始赛季（如2012表示2011-12赛季）
            end_year: 结束赛季
        Returns:
            爬取的比赛总数
        """
        pass
    
    def incremental_update(self) -> int:
        """增量更新数据（昨日比赛），返回新增记录数"""
        pass
```

#### 3.1.3 异常处理
- 网络超时: 重试3次，间隔递增（1s, 2s, 4s）
- 反爬机制: 检测到封禁后等待10分钟再试
- 数据格式变化: 记录日志，跳过该条数据

### 3.2 数据分析模块

#### 3.2.1 特征工程
**原始特征（基于单场数据）:**
- 得分、失分、分差
- 投篮命中率、三分命中率、罚球命中率
- 篮板、助攻、抢断、盖帽、失误、犯规

**衍生特征（需计算）:**
- 近5场平均得分/失分
- 近5场胜率
- 主客场战绩差异
- 球队进攻效率 (Offensive Rating)
- 球队防守效率 (Defensive Rating)
- 净效率值 (Net Rating)
- 节奏 (Pace)
- 真实命中率 (True Shooting %)
- 有效命中率 (Effective FG%)
- 对阵历史胜率

#### 3.2.2 无监督学习分析

**目标:**
1. 球队聚类：将球队按风格分类（进攻型、防守型、平衡型等）
2. 特征降维：找到预测比赛结果的关键因素
3. 异常检测：发现异常比赛表现

**方法选择:**

| 任务 | 方法 | 参数 | 输出 |
|------|------|------|------|
| 球队风格聚类 | K-Means | k=4-6 | 球队类别标签 |
| 特征降维 | PCA | n_components=0.95 | 主成分权重 |
| 关键特征筛选 | 方差分析 + 相关性 | threshold=0.1 | 特征重要性排序 |

**评估指标:**
- 轮廓系数 (Silhouette Score) > 0.5
- 解释方差比累计 > 0.85

#### 3.2.3 预测模型（可选扩展）
如需有监督预测，可扩展：
- 逻辑回归
- 随机森林
- XGBoost

### 3.3 Flask后端模块

#### 3.3.1 API设计

**首页数据**
```
GET /api/home
Response: {
    "today_games": [...],
    "recent_predictions": [...],
    "model_accuracy": 0.68
}
```

**球队列表**
```
GET /api/teams
Response: [
    {"id": "1610612744", "name": "Warriors", "win_pct": 0.65},
    ...
]
```

**球队详情**
```
GET /api/team/<team_id>
Response: {
    "info": {...},
    "stats": {...},
    "recent_games": [...]
}
```

**比赛预测**
```
POST /api/predict
Request: {
    "home_team": "Warriors",
    "away_team": "Lakers"
}
Response: {
    "predicted_winner": "Warriors",
    "win_probability": 0.62,
    "confidence": "HIGH",
    "key_factors": ["主场优势", "近期状态更好", "三分命中率更高"]
}
```

**历史预测记录**
```
GET /api/predictions/history
Response: {
    "total": 150,
    "correct": 102,
    "accuracy": 0.68,
    "predictions": [...]
}
```

#### 3.3.2 路由设计
| 路由 | 方法 | 功能 |
|------|------|------|
| / | GET | 首页 |
| /predict | GET | 预测页面 |
| /team/<id> | GET | 球队详情页 |
| /data | GET | 数据浏览页 |
| /api/* | - | API接口 |

### 3.4 前端模块

#### 3.4.1 页面设计

**首页**
- 今日比赛列表（卡片展示）
- 近期预测准确率
- 模型说明简介

**预测页**
- 球队选择器（下拉/搜索）
- 预测按钮
- 结果展示区：
  - 胜负预测
  - 胜率可视化（进度条/饼图）
  - 关键因素列表
  - 历史对战数据

**数据页**
- 球队数据表格（可排序、筛选）
- 数据可视化图表（ECharts）
  - 胜率排名
  - 得分分布
  - 球队雷达图

**球队详情页**
- 球队基本信息
- 赛季统计图表
- 近期比赛记录
- 球队风格标签

#### 3.4.2 UI规范
- 配色: NBA风格（橙蓝色调）
- 图表: ECharts
- 响应式设计: 支持移动端
- 交互: 加载动画、错误提示

---

## 4. 接口规范

### 4.1 响应格式
```json
{
    "success": true,
    "data": {...},
    "message": "操作成功"
}
```

### 4.2 错误码
| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器错误 |

---

## 5. 测试规范

### 5.1 单元测试
- 爬虫模块: 模拟HTTP响应测试
- 数据处理: 边界值测试
- API: 接口响应测试

### 5.2 集成测试
- 完整预测流程测试
- 数据更新流程测试

### 5.3 准确性验证
- 使用历史数据回测
- 统计预测准确率
- 与博彩赔率对比

---

## 6. 部署规范

### 6.1 开发环境
- Python 3.10+
- 虚拟环境: venv/conda

### 6.2 依赖管理
```
requirements.txt:
flask==3.0.0
pandas==2.1.0
numpy==1.26.0
scikit-learn==1.3.0
requests==2.31.0
beautifulsoup4==4.12.0
selenium==4.15.0
```

### 6.3 部署方式
- 开发: Flask内置服务器
- 生产: Gunicorn + Nginx

---

## 7. 项目里程碑

| 阶段 | 任务 | 预计时间 | 备注 |
|------|------|----------|------|
| Phase 1 | 爬虫模块开发 + 数据存储 | 4天 | 含虎扑页面解析调试 |
| Phase 1.5 | 历史数据全量爬取 | 1天 | 2011-2026约1.8万场比赛 |
| Phase 2 | 数据分析 + 无监督学习 | 3天 | 含特征工程、模型调优 |
| Phase 3 | Flask后端 + API | 2天 | |
| Phase 4 | 前端页面开发 | 3天 | |
| Phase 5 | 测试 + 优化 + 部署 | 2天 | |
| **总计** | | **15天** | |

---

## 8. 风险与注意事项

### 8.1 爬虫风险
- NBA官网可能更新页面结构
- 可能触发反爬机制
- 建议: 设置请求间隔 > 2秒，使用User-Agent轮换

### 8.2 数据质量
- 比赛延期、取消需特殊处理
- 加时赛数据需正确统计
- 建议: 数据清洗时增加校验逻辑

### 8.3 预测准确性
- 体育比赛存在不确定性
- 模型仅供参考，不构成投注建议
- 建议: 页面显著位置添加免责声明

---

## 附录

### A. NBA球队缩写对照表（Basketball Reference格式）
```json
{
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics", 
    "BRK": "Brooklyn Nets",
    "CHI": "Chicago Bulls",
    "CHO": "Charlotte Hornets",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHO": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards"
}
```

### B. 开发检查清单
- [ ] 环境配置完成
- [ ] 爬虫模块可运行
- [ ] 数据库表结构创建
- [ ] 分析脚本可运行
- [ ] Flask服务可启动
- [ ] 前端页面可访问
- [ ] API接口测试通过
- [ ] 预测功能正常
