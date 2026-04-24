# NBA比赛预测系统 - 机器学习模块总结报告

## 执行时间
2026-04-24

## 一、数据概况

### 原始数据
- **数据来源**: SQLite数据库 `data/nba.db`
- **比赛记录**: 11,127 条
- **覆盖赛季**: 2019-2026 (7个赛季)
- **球队数量**: 33支（标准化后）

### 数据表结构
| 表名 | 记录数 | 说明 |
|------|--------|------|
| team_game_stats | 11,127 | 原始比赛数据 |
| team_features | 210 | 球队赛季特征 |
| game_features | 11,127 | 比赛级别衍生特征 |
| team_clusters | 210 | 聚类结果 |

## 二、特征工程

### 计算的衍生特征

#### 1. 滚动统计特征（近5场）
- `recent_5_win_pct` - 近5场胜率
- `recent_5_avg_points` - 近5场平均得分
- `recent_5_avg_points_allowed` - 近5场平均失分

#### 2. 赛季累计特征
- `home_win_pct` - 主场胜率
- `away_win_pct` - 客场胜率
- `point_diff_avg` - 场均分差

#### 3. 高级效率指标
- `offensive_rating` - 进攻效率（每100回合得分）
- `defensive_rating` - 防守效率（每100回合失分）
- `net_rating` - 净效率值
- `pace` - 比赛节奏
- `effective_fg_pct` - 有效命中率
- `true_shooting_pct` - 真实命中率

### 特征统计
| 指标 | 最小值 | 最大值 | 说明 |
|------|--------|--------|------|
| 进攻效率 | 97.0 | 312.8 | 存在异常值（数据质量问题） |
| 防守效率 | 93.6 | 298.1 | 存在异常值 |
| 净效率 | -75.2 | 76.3 | 正常范围 |

## 三、聚类分析

### 方法
1. **数据标准化**: StandardScaler
2. **降维**: PCA（保留95%方差 → 5个主成分）
3. **聚类**: K-Means（k=4）

### 聚类评估指标
| 指标 | 数值 | 说明 |
|------|------|------|
| 轮廓系数 | 0.27 | 中等聚类质量 |
| CH指数 | 75.13 | 中等分离度 |
| DB指数 | 1.20 | 合理的类内紧密度 |

### 球队风格分类

| 风格 | 特征描述 | 球队数量 |
|------|----------|----------|
| Elite Offense | 高进攻效率，正净效率 | 29 |
| Fast Pace | 快节奏比赛 | 56 (两组合并) |
| Middle Tier | 中等水平 | 30 |

### 输出文件
- `cluster_evaluation.png` - 肘部法则、轮廓系数评估图
- `team_clusters_pca.png` - PCA二维散点图
- `team_clusters_radar.png` - 雷达图对比

## 四、预测模型

### 预测逻辑
基于多因子加权模型：

| 因子 | 权重 | 说明 |
|------|------|------|
| 近期战绩 | 25% | 近5场胜率 |
| 进攻效率 | 20% | offensive_rating |
| 防守效率 | 20% | defensive_rating |
| 主场优势 | 15% | home_win_pct |
| 历史对阵 | 10% | head_to_head |
| 风格克制 | 10% | 聚类风格匹配 |

### 置信度评估
- **高置信度**: 概率偏差>70% 或 多因子一致
- **中置信度**: 概率偏差40-70%
- **低置信度**: 概率偏差<40%

### 演示预测结果

| 主队 | 客队 | 主队胜率 | 预测获胜 | 置信度 |
|------|------|----------|----------|--------|
| LAL | BOS | 35.7% | BOS | 中 |
| GSW | PHO | 45.4% | PHO | 低 |
| DEN | MIN | 39.9% | MIN | 低 |

## 五、使用方法

### 单场比赛预测
```python
from ml.predict import predict_game

result = predict_game('LAL', 'BOS')
print(f"预测获胜: {result['predicted_winner']}")
print(f"主队胜率: {result['home_win_probability']}")
```

### 批量预测
```python
from ml.predict import batch_predict

results = batch_predict([
    ('LAL', 'BOS'),
    ('GSW', 'PHO'),
    ('DEN', 'MIN')
])
```

### 重新运行特征工程
```bash
python ml/features.py
```

### 重新运行聚类分析
```bash
python ml/cluster.py
```

### 运行完整流程
```bash
python run_ml.py
```

## 六、输出文件列表

| 文件 | 大小 | 说明 |
|------|------|------|
| team_features.csv | 91KB | 球队特征数据 |
| team_clusters.csv | 115KB | 聚类结果 |
| cluster_styles.csv | 71B | 风格映射 |
| cluster_evaluation.png | 178KB | 聚类评估图 |
| team_clusters_pca.png | 139KB | PCA散点图 |
| team_clusters_radar.png | 255KB | 雷达图 |
| prediction_*.png | ~145KB | 预测可视化 |

## 七、后续优化建议

1. **数据清洗**: 处理进攻/防守效率的异常值
2. **特征增强**: 添加更多高级统计数据（如PER、Win Shares等）
3. **模型升级**: 
   - 引入监督学习模型（逻辑回归、XGBoost等）
   - 使用历史赛季数据训练
4. **实时更新**: 添加新比赛数据的增量更新机制
5. **Web界面**: 开发Flask Web应用提供交互式预测

---
*报告生成时间: 2026-04-24*
