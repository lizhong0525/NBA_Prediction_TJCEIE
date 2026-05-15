# visual_training.py —— 模型诊断与训练过程可视化（兼容任意环境）
import sys
import os
from pathlib import Path

# 确保项目根目录在 sys.path 最前面
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from ml.predict import get_model_diagnostics, predict_game_advanced, DEFAULT_WEIGHTS
from ml.cluster import find_optimal_k, load_team_features, prepare_clustering_data

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = Path('output')
OUTPUT_DIR.mkdir(exist_ok=True)

# ---- 1. 特征重要性条形图 ----
print("绘制特征重要性图...")
diag = get_model_diagnostics()
importance = diag.get('feature_importance', [])
if importance:
    imp_df = pd.DataFrame(importance)
    imp_df = imp_df.sort_values('importance')
    plt.figure(figsize=(10, 6))
    plt.barh(imp_df['feature'], imp_df['importance'], color='steelblue')
    plt.xlabel('重要性（回归系数绝对值）')
    plt.title('球队实力预测特征重要性')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'feature_importance.png', dpi=150)
    plt.close()

# ---- 2. 赛季回测准确率折线图 ----
print("绘制赛季回测准确率...")
season_bd = diag.get('season_breakdown', [])
if season_bd:
    df_season = pd.DataFrame(season_bd)
    df_season = df_season.sort_values('season')
    plt.figure(figsize=(10, 5))
    plt.plot(df_season['season'], df_season['pairwise_accuracy'], 'o-', color='coral')
    plt.axhline(y=0.5, color='gray', linestyle='--', label='随机猜测')
    plt.xlabel('赛季')
    plt.ylabel('成对比较准确率')
    plt.title('模型历史赛季回测准确率（两两球队胜负比较）')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'season_backtest_accuracy.png', dpi=150)
    plt.close()

# ---- 3. 预测概率分布直方图 ----
print("绘制预测概率分布...")
# 选一些球队进行预测（可从球队列表随机取）
from data_repository import load_team_features_frame
profiles = load_team_features_frame()
if not profiles.empty:
    latest_season = profiles['season'].max()
    teams = profiles[profiles['season'] == latest_season]['team_abbr'].unique()[:10]
    probs = []
    for i in range(len(teams)):
        for j in range(i+1, len(teams)):
            try:
                res = predict_game_advanced(teams[i], teams[j])
                probs.append(res['home_win_probability'])
            except:
                pass
    if probs:
        plt.figure(figsize=(8, 5))
        plt.hist(probs, bins=20, edgecolor='black', alpha=0.7)
        plt.xlabel('主队胜率预测')
        plt.ylabel('比赛场次')
        plt.title('模型预测概率分布')
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / 'pred_prob_distribution.png', dpi=150)
        plt.close()

# ---- 4. 聚类评估图（直接运行 cluster 里的，已有保存）----
print("聚类评估图已经在 cluster.py 中生成过，检查 output/cluster_evaluation.png")

# ========== 优化版：不同权重方案准确率对比（只训练一次，极快）==========
print("绘制权重方案对比（优化版）...")

from itertools import combinations
from ml.predict import (
    _build_strength_model,
    _normalize_weights,
    _compose_factor_breakdown,
    _sigmoid,
    load_data,
    DEFAULT_WEIGHTS,
)

# 1. 定义要对比的权重方案（原来漏掉了这个）
weight_schemes = {
    '默认权重': DEFAULT_WEIGHTS,
    '重视近期状态': {**DEFAULT_WEIGHTS, 'recent_form': 0.40, 'efficiency_diff': 0.25},
    '重视效率差': {**DEFAULT_WEIGHTS, 'recent_form': 0.15, 'efficiency_diff': 0.50},
}

# 2. 加载数据并只训练一次模型
team_features, _, _ = load_data()
latest_season = team_features['season'].max()
model = _build_strength_model(team_features, season=latest_season)

# 3. 提取每支球队的赛季统计（只提取一次）
season_data = team_features[team_features['season'] == latest_season]
teams_list = season_data['team_abbr'].unique()
team_stats = {}
for t in teams_list:
    t_data = season_data[season_data['team_abbr'] == t]
    if not t_data.empty:
        team_stats[t] = t_data.iloc[0].to_dict()

# 4. 快速对比不同权重
scheme_accuracies = {}
for scheme_name, weights in weight_schemes.items():
    correct = 0
    total = 0
    nw = _normalize_weights(weights)
    for t1, t2 in combinations(teams_list, 2):
        if t1 not in team_stats or t2 not in team_stats:
            continue
        h2h = {'total': 0, 'home_win_pct': 0.5}
        edge, _ = _compose_factor_breakdown(
            team_stats[t1], team_stats[t2], nw, model, h2h,
            {'style': team_stats[t1].get('style')},
            {'style': team_stats[t2].get('style')}
        )
        prob = _sigmoid(model['calibration_intercept'] + model['calibration_slope'] * edge)
        t1_winpct = team_stats[t1].get('win_pct', 0.5)
        t2_winpct = team_stats[t2].get('win_pct', 0.5)
        actual_winner = t1 if t1_winpct > t2_winpct else t2
        predicted_winner = t1 if prob >= 0.5 else t2
        if actual_winner == predicted_winner:
            correct += 1
        total += 1
    scheme_accuracies[scheme_name] = correct / total if total > 0 else 0

# 5. 画柱状图
plt.figure(figsize=(8, 5))
names = list(scheme_accuracies.keys())
values = list(scheme_accuracies.values())
bars = plt.bar(names, values, color=['steelblue', 'coral', 'seagreen'])
for bar, val in zip(bars, values):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
             f'{val:.2%}', ha='center', fontsize=12, fontweight='bold')
plt.ylabel('成对比较准确率')
plt.title('不同权重方案准确率对比')
plt.ylim(0, 1)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'weight_comparison.png', dpi=150)
plt.close()

print('图片已保存')