# -*- coding: utf-8 -*-
"""
NBA比赛预测系统 - 主运行脚本
整合特征工程、聚类分析和预测功能
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_full_pipeline():
    """
    运行完整的机器学习流程
    """
    print_header("NBA比赛预测系统 - 机器学习模块")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 特征工程
    print_header("步骤1: 特征工程")
    print("正在计算衍生特征...")
    from ml.features import run_feature_engineering
    team_features, game_features = run_feature_engineering()
    
    # 2. 聚类分析
    print_header("步骤2: 聚类分析")
    print("正在进行球队风格聚类...")
    from ml.cluster import run_clustering_analysis
    cluster_result, style_mapping, scaler, pca = run_clustering_analysis()
    
    # 3. 预测演示
    print_header("步骤3: 预测演示")
    print("正在进行比赛预测...")
    from ml.predict import run_demo_predictions
    predictions = run_demo_predictions()
    
    # 4. 输出总结
    print_header("执行总结")
    print(f"""
✅ 特征工程完成:
   - 生成了 {len(team_features)} 条球队赛季特征记录
   - 导出了 team_features.csv 和 game_features.csv
   
✅ 聚类分析完成:
   - 将球队分为 {len(style_mapping)} 种风格类型
   - 风格类型: {', '.join(set(style_mapping.values()))}
   - 保存了聚类可视化图表
   
✅ 预测系统就绪:
   - 可使用 predict_game(home_team, away_team) 进行预测
   - 已演示 {len(predictions)} 场比赛预测
   
📁 输出文件位置: output/
   - team_features.csv       - 球队特征数据
   - team_clusters.csv       - 聚类结果
   - cluster_styles.csv      - 风格映射
   - cluster_evaluation.png  - 聚类评估图
   - team_clusters_pca.png   - PCA散点图
   - team_clusters_radar.png - 雷达图
   - prediction_*.png        - 预测可视化图

📊 数据库表:
   - team_features           - 球队特征
   - game_features           - 比赛级别特征
   - team_clusters           - 聚类结果
""")
    
    print_header("使用示例")
    print("""
# 导入预测模块
from ml.predict import predict_game

# 预测单场比赛
result = predict_game('LAL', 'BOS')
print(result['predicted_winner'])
print(result['home_win_probability'])

# 批量预测
from ml.predict import batch_predict
results = batch_predict([('LAL', 'BOS'), ('GSW', 'PHO')])
""")
    
    return {
        'team_features': team_features,
        'cluster_result': cluster_result,
        'predictions': predictions,
        'style_mapping': style_mapping
    }


if __name__ == "__main__":
    results = run_full_pipeline()
