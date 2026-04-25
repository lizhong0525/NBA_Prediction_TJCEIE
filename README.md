# NBA 比赛结果预测系统

一个面向课程项目与演示答辩的 NBA 数据分析与比赛预测系统。项目围绕四个核心任务展开：

1. 获取球队历史比赛与赛季统计数据。
2. 构造近期状态、主客场、效率指标等结构化特征。
3. 同时完成胜负预测和分差预测，并支持不同特征组合对比。
4. 在 Web UI 中展示预测结果、关键影响因素与图表分析。

## 项目亮点

- 预测链路重构：原先参数稍微改动就可能让结果大幅漂移，现在会先对权重做归一化，再结合赛季特征构建稳定的强度模型。
- 结果直接上屏：预测结果不再只打印在控制台，UI 现在会展示胜负概率、预测分差、置信度、关键因素和特征重要性。
- 数据回退机制：当 SQLite 库中某些表为空时，系统会自动回退到 `output/team_features.csv` 与 `output/team_clusters.csv`，保证页面仍可展示完整内容。
- 界面栏目有实际意义：去掉了原来使用随机数或假数据的图表，所有首页/数据页/球队页图表都改为真实统计值驱动。

## 当前实现概览

### 数据来源

- 主要来源：Basketball Reference 历史比赛与球队统计数据
- 当前本地缓存：
  - `output/team_features.csv`
  - `output/team_clusters.csv`
  - `data/nba.db`

说明：

- 项目中保留了爬虫脚本，但当前 Web 演示优先使用本地数据库和缓存特征文件。
- 如需重新抓取数据，请遵守目标站点 `robots.txt` 与使用条款，不抓取隐私信息，不用于非法用途。

### 预测逻辑

当前预测引擎位于 [ml/predict.py](/C:/Users/24981/NBA_Prediction_TJCEIE/ml/predict.py)。

主要思路：

- 从赛季特征表中提取球队画像。
- 结合 `win_pct`、`recent_5_win_pct`、`home_win_pct`、`offensive_rating`、`defensive_rating`、`net_rating`、`pace` 等特征构建球队强度。
- 通过因子分解得到：
  - `recent_form`
  - `home_advantage`
  - `historical_matchup`
  - `efficiency_diff`
  - `cluster_similarity`
- 在高级模式下再叠加实时修正：
  - 伤病影响
  - 休息天数
  - 背靠背
  - 士气修正
- 输出：
  - 主队胜率 / 客队胜率
  - 预测胜方
  - 预测分差
  - 关键因素
  - 特征重要性
  - 回测诊断信息

## 项目结构

```text
NBA_Prediction_TJCEIE/
├─ app/
│  ├─ __init__.py
│  ├─ models/
│  │  └─ database.py
│  ├─ static/
│  │  ├─ css/style.css
│  │  └─ js/main.js
│  └─ templates/
│     ├─ base.html
│     ├─ index.html
│     ├─ predict.html
│     ├─ data.html
│     ├─ team.html
│     └─ about.html
├─ crawler/
├─ data/
│  └─ nba.db
├─ ml/
│  ├─ __init__.py
│  ├─ api.py
│  ├─ cluster.py
│  ├─ features.py
│  └─ predict.py
├─ output/
│  ├─ team_features.csv
│  └─ team_clusters.csv
├─ tests/
│  └─ test_ml.py
├─ data_repository.py
├─ run.py
├─ requirements.txt
└─ README.md
```

## 环境依赖

建议 Python 3.9 及以上。

安装依赖：

```bash
pip install -r requirements.txt
```

## 启动方式

```bash
python run.py
```

默认地址：

```text
http://127.0.0.1:5000
```

## 测试方式

核心离线测试：

```bash
python -m unittest tests.test_ml
```

补充烟雾测试：

```bash
python test_prediction_api.py
```

## 主要页面

### 1. 首页

- 展示今日比赛、最近预测、赛季球队排名
- 展示东西部平均胜率图与赛季回测走势

### 2. 比赛预测页

- 支持基础预测
- 支持高级模式参数调整
- 显示胜负概率、预测分差、关键因素、实时修正与特征重要性

### 3. 数据中心

- 球队总览卡片
- 胜率 / 进攻效率 / 防守效率 / 净效率榜单
- 预测历史表格
- 场均得分与东西部分布图

### 4. 球队详情页

- 赛季画像
- 能力雷达图
- 近期比赛
- 与其他球队的单指标对比图

## 关键 API

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/home` | GET | 首页聚合数据 |
| `/api/seasons` | GET | 可用赛季列表 |
| `/api/teams` | GET | 球队赛季画像列表 |
| `/api/team/<abbr>` | GET | 单支球队详情 |
| `/api/predict` | POST | 比赛预测 |
| `/api/predict/validate` | POST | 参数校验 |
| `/api/predict/params` | GET | 参数说明与默认值 |
| `/api/predictions/history` | GET | 预测历史 |
| `/api/games` | GET | 今日比赛或球队近期比赛 |
| `/api/stats/ranking` | GET | 统计榜单 |
| `/api/health` | GET | 健康检查 |

## 本次优化内容

针对当前问题，已完成以下修复：

### 1. 预测结果不稳定

- 重构 `ml/predict.py`
- 使用赛季画像构建更稳健的强度模型
- 对自定义权重进行归一化，降低参数敏感度
- 输出回测诊断信息，便于比较不同特征组合

### 2. 结果无法在 UI 中显示

- 统一后端接口字段
- 修复预测结果入库与历史回显字段不一致问题
- 前端改为直接消费接口返回的概率、分差、关键因素和置信度

### 3. UI 栏目无效

- 重写首页、预测页、数据页、球队页的交互逻辑
- 去除随机假数据图表
- 所有图表改为使用真实缓存特征
- 修复球队页、预测页中多个无效字段与按钮预填逻辑

## 已知事项

- 当前仓库自带的 `env1/` 虚拟环境路径失效，建议新建本地虚拟环境后重新安装依赖。
- 如果本地没有安装 Flask / scikit-learn / matplotlib 等依赖，Web 服务和部分分析脚本无法运行。
- 当前离线测试已通过，但由于本会话里无法安装额外依赖并直接启动 Flask，最终浏览器级联调仍建议在本地完整环境中再跑一遍。

## 引用与说明

- 数据源参考：Basketball Reference
- 项目实现遵循原创与合规原则：可借鉴开源思路，但仓库中的代码与文档需保持原创表达，并明确保留来源信息。

## License

MIT
