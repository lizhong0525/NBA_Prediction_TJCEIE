# -*- coding: utf-8 -*-
"""
球队聚类分析模块
使用无监督学习方法对球队进行风格分类

功能：
- K-Means聚类分析
- PCA降维可视化
- 聚类质量评估（轮廓系数、肘部法则）
- 球队风格标签生成
- 可视化图表生成
"""

import numpy as np
import pandas as pd
import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# ==================== 配置 ====================
DATABASE_PATH = Path(__file__).parent.parent / 'data' / 'nba.db'
OUTPUT_DIR = Path(__file__).parent.parent / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 聚类特征列
CLUSTERING_FEATURES = [
    'offensive_rating',    # 进攻效率
    'defensive_rating',    # 防守效率
    'net_rating',          # 净效率值
    'pace',                # 比赛节奏
    'effective_fg_pct',    # 有效命中率
    'true_shooting_pct',   # 真实命中率
    'recent_5_win_pct',    # 近期胜率
    'home_win_pct',        # 主场胜率
    'point_diff_avg',      # 场均分差
]


def load_team_features(db_path: str = None) -> pd.DataFrame:
    """
    从数据库加载球队特征数据
    
    Args:
        db_path: 数据库路径
        
    Returns:
        球队特征DataFrame
    """
    if db_path is None:
        db_path = DATABASE_PATH
    
    conn = sqlite3.connect(db_path)
    
    # 尝试从team_features表加载
    try:
        df = pd.read_sql_query("SELECT * FROM team_features", conn)
        print(f"[聚类分析] 从team_features表加载: {len(df)} 条记录")
    except Exception as e:
        print(f"[聚类分析] team_features表不存在，将使用team_game_stats计算: {e}")
        conn.close()
        return None
    
    conn.close()
    
    return df


def prepare_clustering_data(df: pd.DataFrame) -> Tuple[np.ndarray, pd.DataFrame]:
    """
    准备聚类数据
    
    Args:
        df: 球队特征DataFrame
        
    Returns:
        特征数组和原始数据DataFrame
    """
    print("\n[聚类分析] 准备聚类数据...")
    
    # 过滤可用的特征列
    available_features = [f for f in CLUSTERING_FEATURES if f in df.columns]
    print(f"  - 可用特征: {available_features}")
    
    # 提取特征矩阵
    feature_df = df[available_features].copy()
    
    # 处理缺失值和无穷值
    # 使用中位数填充
    for col in feature_df.columns:
        median_val = feature_df[col].median()
        if pd.isna(median_val):
            median_val = 0
        feature_df[col] = feature_df[col].fillna(median_val)
    
    feature_df = feature_df.replace([np.inf, -np.inf], 0)
    
    # 移除含有过多NaN的行（全为0或全为NaN）
    valid_mask = (feature_df.notna()).any(axis=1) & (feature_df != 0).any(axis=1)
    feature_df = feature_df[valid_mask].reset_index(drop=True)
    df_valid = df[valid_mask].reset_index(drop=True)
    
    # 再次检查并处理任何残留NaN
    feature_df = feature_df.fillna(0)
    
    print(f"  - 有效样本数: {len(feature_df)}")
    print(f"  - NaN检查: {feature_df.isna().sum().sum()} 个NaN值")
    
    return feature_df.values, df_valid


def find_optimal_k(X: np.ndarray, k_range: range = range(2, 10)) -> Tuple[int, Dict]:
    """
    使用肘部法则和轮廓系数寻找最优聚类数
    
    Args:
        X: 标准化后的特征矩阵
        k_range: 待测试的k值范围
        
    Returns:
        最优k值和评估结果
    """
    print("\n[聚类分析] 寻找最优聚类数...")
    
    # 数据标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    results = {
        'k': [],
        'inertia': [],
        'silhouette': [],
        'calinski_harabasz': [],
        'davies_bouldin': []
    }
    
    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        
        results['k'].append(k)
        results['inertia'].append(kmeans.inertia_)
        
        # 轮廓系数（-1到1，越高越好）
        if k > 1:
            results['silhouette'].append(silhouette_score(X_scaled, labels))
            results['calinski_harabasz'].append(calinski_harabasz_score(X_scaled, labels))
            results['davies_bouldin'].append(davies_bouldin_score(X_scaled, labels))
        else:
            results['silhouette'].append(0)
            results['calinski_harabasz'].append(0)
            results['davies_bouldin'].append(float('inf'))
    
    # 绘制评估图
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # 肘部法则图
    axes[0, 0].plot(results['k'], results['inertia'], 'bo-', linewidth=2, markersize=8)
    axes[0, 0].set_xlabel('Number of Clusters (k)', fontsize=12)
    axes[0, 0].set_ylabel('Inertia (SSE)', fontsize=12)
    axes[0, 0].set_title('Elbow Method', fontsize=14, fontweight='bold')
    axes[0, 0].grid(True, alpha=0.3)
    
    # 轮廓系数图
    axes[0, 1].plot(results['k'], results['silhouette'], 'go-', linewidth=2, markersize=8)
    axes[0, 1].set_xlabel('Number of Clusters (k)', fontsize=12)
    axes[0, 1].set_ylabel('Silhouette Score', fontsize=12)
    axes[0, 1].set_title('Silhouette Analysis', fontsize=14, fontweight='bold')
    axes[0, 1].grid(True, alpha=0.3)
    
    # Calinski-Harabasz指数
    axes[1, 0].plot(results['k'], results['calinski_harabasz'], 'ro-', linewidth=2, markersize=8)
    axes[1, 0].set_xlabel('Number of Clusters (k)', fontsize=12)
    axes[1, 0].set_ylabel('Calinski-Harabasz Index', fontsize=12)
    axes[1, 0].set_title('Calinski-Harabasz Index', fontsize=14, fontweight='bold')
    axes[1, 0].grid(True, alpha=0.3)
    
    # Davies-Bouldin指数
    axes[1, 1].plot(results['k'], results['davies_bouldin'], 'mo-', linewidth=2, markersize=8)
    axes[1, 1].set_xlabel('Number of Clusters (k)', fontsize=12)
    axes[1, 1].set_ylabel('Davies-Bouldin Index', fontsize=12)
    axes[1, 1].set_title('Davies-Bouldin Index (Lower is Better)', fontsize=14, fontweight='bold')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'cluster_evaluation.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  - 评估图表已保存: {OUTPUT_DIR / 'cluster_evaluation.png'}")
    
    # 选择最优k（基于轮廓系数）
    optimal_idx = np.argmax(results['silhouette'])
    optimal_k = results['k'][optimal_idx]
    
    print(f"\n  评估结果汇总:")
    print(f"  - 轮廓系数最优k: {optimal_k} (分数: {results['silhouette'][optimal_idx]:.4f})")
    print(f"  - 建议使用k=4进行4分类（进攻型/防守型/平衡型/快攻型）")
    
    return 4, results  # 返回k=4（根据任务需求）


def perform_clustering(X: np.ndarray, n_clusters: int = 4) -> Tuple[KMeans, np.ndarray, StandardScaler, PCA]:
    """
    执行K-Means聚类
    
    Args:
        X: 原始特征矩阵
        n_clusters: 聚类数
        
    Returns:
        聚类模型、标签、标准化器和PCA模型
    """
    print(f"\n[聚类分析] 执行K-Means聚类 (k={n_clusters})...")
    
    # 标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # PCA降维（保留95%方差用于聚类）
    pca = PCA(n_components=0.95, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    
    print(f"  - PCA降维: {X.shape[1]} -> {X_pca.shape[1]} 维 (保留 {pca.explained_variance_ratio_.sum()*100:.1f}% 方差)")
    
    # K-Means聚类
    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=42,
        n_init=10,
        max_iter=300
    )
    
    labels = kmeans.fit_predict(X_pca)
    
    # 评估聚类质量
    sil_score = silhouette_score(X_scaled, labels)
    ch_score = calinski_harabasz_score(X_scaled, labels)
    db_score = davies_bouldin_score(X_scaled, labels)
    
    print(f"\n  聚类质量评估:")
    print(f"  - 轮廓系数 (Silhouette): {sil_score:.4f} (范围-1到1，越高越好)")
    print(f"  - CH指数 (Calinski-Harabasz): {ch_score:.2f} (越高越好)")
    print(f"  - DB指数 (Davies-Bouldin): {db_score:.4f} (越低越好)")
    
    return kmeans, labels, scaler, pca


def analyze_cluster_characteristics(df: pd.DataFrame, labels: np.ndarray, 
                                   features: List[str]) -> Dict[int, str]:
    """
    分析每个聚类的特征，确定球队风格标签
    
    Args:
        df: 包含特征的DataFrame
        labels: 聚类标签
        features: 特征列名
        
    Returns:
        聚类标签到风格名称的映射
    """
    print("\n[聚类分析] 分析各聚类特征...")
    
    df_with_labels = df.copy()
    df_with_labels['cluster'] = labels
    
    # 计算每个聚类的特征均值
    cluster_profiles = df_with_labels.groupby('cluster')[features].mean()
    
    print("\n  各聚类特征均值:")
    print(cluster_profiles.round(2).to_string())
    
    # 确定每个聚类的风格
    style_mapping = {}
    
    for cluster_id in cluster_profiles.index:
        profile = cluster_profiles.loc[cluster_id]
        
        # 分析特征判断风格
        offense = profile['offensive_rating']
        defense = profile['defensive_rating']
        pace = profile['pace']
        net = profile['net_rating']
        
        # 判断逻辑
        if net > 3 and offense > 110:
            style = "Elite Offense" if pace > 98 else "Balanced Elite"
        elif defense < 108 and net < 0:
            style = "Defensive" if pace < 96 else "Slow Defensive"
        elif pace > 99:
            style = "Fast Pace"
        elif abs(net) < 2:
            style = "Balanced"
        else:
            style = "Middle Tier"
        
        style_mapping[cluster_id] = style
    
    # 输出各聚类的球队
    print("\n  各风格球队分布:")
    for cluster_id, style in style_mapping.items():
        teams = df_with_labels[df_with_labels['cluster'] == cluster_id]['team_abbr'].unique()
        print(f"  [{style}] (Cluster {cluster_id}): {len(teams)} 支球队")
    
    return style_mapping


def visualize_clusters(df: pd.DataFrame, labels: np.ndarray, 
                       scaler: StandardScaler, pca: PCA,
                       style_mapping: Dict[int, str]):
    """
    生成聚类可视化图表
    
    Args:
        df: 原始数据
        labels: 聚类标签
        scaler: 标准化器
        pca: PCA模型
        style_mapping: 风格映射
    """
    print("\n[聚类分析] 生成可视化图表...")
    
    # 准备数据 - 确保没有NaN
    features = [f for f in CLUSTERING_FEATURES if f in df.columns]
    X = df[features].values.copy()
    
    # 处理NaN
    from sklearn.impute import SimpleImputer
    imputer = SimpleImputer(strategy='median')
    X = imputer.fit_transform(X)
    
    X_scaled = scaler.transform(X)
    X_pca = pca.transform(X_scaled)
    
    df_plot = df.copy().reset_index(drop=True)
    df_plot['cluster'] = labels
    df_plot['PC1'] = X_pca[:, 0]
    df_plot['PC2'] = X_pca[:, 1]
    df_plot['style'] = df_plot['cluster'].map(style_mapping)
    
    # 图1: PCA散点图
    fig, ax = plt.subplots(figsize=(12, 8))
    
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']
    
    for cluster_id in sorted(df_plot['cluster'].unique()):
        mask = df_plot['cluster'] == cluster_id
        style_name = style_mapping.get(cluster_id, f'Cluster {cluster_id}')
        color = colors[cluster_id % len(colors)]
        
        ax.scatter(df_plot.loc[mask, 'PC1'], df_plot.loc[mask, 'PC2'],
                  c=color, label=f'{style_name} (n={mask.sum()})',
                  alpha=0.7, s=100, edgecolors='white', linewidth=1)
    
    ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}% variance)', fontsize=12)
    ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}% variance)', fontsize=12)
    ax.set_title('NBA Team Clustering - PCA Visualization', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'team_clusters_pca.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  - PCA散点图已保存: {OUTPUT_DIR / 'team_clusters_pca.png'}")
    
    # 图2: 雷达图 - 各风格特征对比
    if len(features) >= 5:
        # 选择5个关键特征用于雷达图
        radar_features = ['offensive_rating', 'defensive_rating', 'pace', 
                         'effective_fg_pct', 'true_shooting_pct']
        radar_features = [f for f in radar_features if f in features]
        
        # 归一化到0-1
        cluster_means = df_plot.groupby('cluster')[radar_features].mean()
        
        # 标准化到百分比范围
        for col in radar_features:
            min_val = cluster_means[col].min()
            max_val = cluster_means[col].max()
            if max_val > min_val:
                cluster_means[col] = (cluster_means[col] - min_val) / (max_val - min_val)
            else:
                cluster_means[col] = 0.5
        
        # 绘制雷达图
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
        
        angles = np.linspace(0, 2 * np.pi, len(radar_features), endpoint=False).tolist()
        angles += angles[:1]  # 闭合
        
        for cluster_id in cluster_means.index:
            values = cluster_means.loc[cluster_id].values.tolist()
            values += values[:1]  # 闭合
            
            style_name = style_mapping.get(cluster_id, f'Cluster {cluster_id}')
            color = colors[cluster_id % len(colors)]
            
            ax.plot(angles, values, 'o-', linewidth=2, label=style_name, color=color)
            ax.fill(angles, values, alpha=0.25, color=color)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([f.replace('_', '\n') for f in radar_features], fontsize=11)
        ax.set_ylim(0, 1)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=10)
        ax.set_title('Team Style Profiles - Radar Chart', fontsize=14, fontweight='bold', pad=20)
        
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / 'team_clusters_radar.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"  - 雷达图已保存: {OUTPUT_DIR / 'team_clusters_radar.png'}")


def save_cluster_results(df: pd.DataFrame, labels: np.ndarray, 
                         style_mapping: Dict[int, str],
                         pca: PCA, scaler: StandardScaler):
    """
    保存聚类结果到数据库和CSV
    
    Args:
        df: 原始数据
        labels: 聚类标签
        style_mapping: 风格映射
        pca: PCA模型
        scaler: 标准化器
    """
    print("\n[聚类分析] 保存聚类结果...")
    
    # 添加聚类标签和风格
    df_result = df.copy().reset_index(drop=True)
    df_result['cluster'] = labels
    df_result['style'] = df_result['cluster'].map(style_mapping)
    
    # 添加PCA坐标
    features = [f for f in CLUSTERING_FEATURES if f in df.columns]
    X = df[features].values.copy()
    
    # 处理NaN
    from sklearn.impute import SimpleImputer
    imputer = SimpleImputer(strategy='median')
    X = imputer.fit_transform(X)
    
    X_scaled = scaler.transform(X)
    X_pca = pca.transform(X_scaled)
    
    for i in range(X_pca.shape[1]):
        df_result[f'pc_{i+1}'] = X_pca[:, i]
    
    # 保存到数据库
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 删除旧表
    cursor.execute("DROP TABLE IF EXISTS team_clusters")
    
    # 创建新表
    columns = ', '.join(df_result.columns)
    placeholders = ', '.join(['?' for _ in df_result.columns])
    cursor.execute(f"CREATE TABLE IF NOT EXISTS team_clusters ({columns})")
    
    # 插入数据
    df_result.to_sql('team_clusters', conn, index=False, if_exists='replace')
    
    conn.close()
    
    print(f"  - 已保存 {len(df_result)} 条记录到 team_clusters 表")
    
    # 保存CSV
    csv_path = OUTPUT_DIR / 'team_clusters.csv'
    df_result.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"  - 已导出CSV: {csv_path}")
    
    # 保存风格映射
    style_df = pd.DataFrame([
        {'cluster': k, 'style': v} for k, v in style_mapping.items()
    ])
    style_path = OUTPUT_DIR / 'cluster_styles.csv'
    style_df.to_csv(style_path, index=False, encoding='utf-8-sig')
    print(f"  - 已保存风格映射: {style_path}")
    
    return df_result


def run_clustering_analysis():
    """
    运行完整的聚类分析流程
    """
    print("=" * 60)
    print("NBA比赛预测系统 - 聚类分析模块")
    print("=" * 60)
    
    start_time = datetime.now()
    
    # 1. 加载数据
    print("\n[步骤 1/5] 加载球队特征数据...")
    df = load_team_features()
    
    if df is None or len(df) == 0:
        print("[错误] 无法加载数据，请先运行特征工程模块")
        return None
    
    # 2. 准备数据
    print("\n[步骤 2/5] 准备聚类数据...")
    X, df_valid = prepare_clustering_data(df)
    
    # 3. 寻找最优聚类数
    print("\n[步骤 3/5] 评估最优聚类数...")
    optimal_k, eval_results = find_optimal_k(X)
    
    # 4. 执行聚类
    print("\n[步骤 4/5] 执行K-Means聚类...")
    kmeans, labels, scaler, pca = perform_clustering(X, n_clusters=optimal_k)
    
    # 5. 分析聚类特征
    print("\n[步骤 5/5] 分析聚类特征和可视化...")
    features = [f for f in CLUSTERING_FEATURES if f in df_valid.columns]
    style_mapping = analyze_cluster_characteristics(df_valid, labels, features)
    
    # 生成可视化
    visualize_clusters(df_valid, labels, scaler, pca, style_mapping)
    
    # 保存结果
    result_df = save_cluster_results(df_valid, labels, style_mapping, pca, scaler)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "=" * 60)
    print("聚类分析完成!")
    print(f"总耗时: {duration:.2f} 秒")
    print("=" * 60)
    
    return result_df, style_mapping, scaler, pca


if __name__ == "__main__":
    result = run_clustering_analysis()
