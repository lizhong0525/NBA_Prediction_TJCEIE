# -*- coding: utf-8 -*-
"""
NBA预测API接口封装
提供简洁的调用方式和示例
"""

from typing import Dict, List, Optional, Any
from .predict import (
    predict_game_advanced,
    validate_params,
    validate_weights,
    DEFAULT_WEIGHTS,
    DEFAULT_HOME_PARAMS,
    DEFAULT_AWAY_PARAMS
)


# ==================== 便捷函数 ====================

def simple_predict(home_team: str, away_team: str) -> Dict:
    """
    简单预测 - 仅传入球队名称
    
    Args:
        home_team: 主队缩写
        away_team: 客队缩写
        
    Returns:
        预测结果
    """
    return predict_game_advanced(
        home_team=home_team,
        away_team=away_team,
        return_details=True
    )


def predict_with_injuries(
    home_team: str,
    away_team: str,
    home_injury_impact: float = 0,
    away_injury_impact: float = 0,
    home_players_out: Optional[List[str]] = None,
    away_players_out: Optional[List[str]] = None
) -> Dict:
    """
    考虑伤病情况的预测
    
    Args:
        home_team: 主队缩写
        away_team: 客队缩写
        home_injury_impact: 主队伤病影响 (-0.3 to 0)
        away_injury_impact: 客队伤病影响 (-0.3 to 0)
        home_players_out: 主队缺阵球员列表
        away_players_out: 客队缺阵球员列表
        
    Returns:
        预测结果
    """
    home_params = {
        'injury_impact': home_injury_impact,
        'key_player_out': home_players_out or []
    }
    away_params = {
        'injury_impact': away_injury_impact,
        'key_player_out': away_players_out or []
    }
    
    return predict_game_advanced(
        home_team=home_team,
        away_team=away_team,
        home_params=home_params,
        away_params=away_params
    )


def predict_with_schedule(
    home_team: str,
    away_team: str,
    home_rest_days: int = 2,
    away_rest_days: int = 2,
    home_back_to_back: bool = False,
    away_back_to_back: bool = False
) -> Dict:
    """
    考虑赛程安排的预测
    
    Args:
        home_team: 主队缩写
        away_team: 客队缩写
        home_rest_days: 主队休息天数
        away_rest_days: 客队休息天数
        home_back_to_back: 主队是否背靠背
        away_back_to_back: 客队是否背靠背
        
    Returns:
        预测结果
    """
    home_params = {
        'rest_days': home_rest_days,
        'back_to_back': home_back_to_back
    }
    away_params = {
        'rest_days': away_rest_days,
        'back_to_back': away_back_to_back
    }
    
    return predict_game_advanced(
        home_team=home_team,
        away_team=away_team,
        home_params=home_params,
        away_params=away_params
    )


def predict_with_custom_weights(
    home_team: str,
    away_team: str,
    recent_form: float = 0.25,
    home_advantage: float = 0.15,
    historical_matchup: float = 0.10,
    efficiency_diff: float = 0.40,
    cluster_similarity: float = 0.10
) -> Dict:
    """
    使用自定义权重的预测
    
    Args:
        home_team: 主队缩写
        away_team: 客队缩写
        recent_form: 近期状态权重
        home_advantage: 主场优势权重
        historical_matchup: 历史交锋权重
        efficiency_diff: 效率差权重
        cluster_similarity: 风格相似度权重
        
    Returns:
        预测结果
    """
    weights = {
        'recent_form': recent_form,
        'home_advantage': home_advantage,
        'historical_matchup': historical_matchup,
        'efficiency_diff': efficiency_diff,
        'cluster_similarity': cluster_similarity
    }
    
    return predict_game_advanced(
        home_team=home_team,
        away_team=away_team,
        weights=weights
    )


def full_advanced_predict(
    home_team: str,
    away_team: str,
    home_params: Optional[Dict] = None,
    away_params: Optional[Dict] = None,
    weights: Optional[Dict] = None,
    season: Optional[str] = None
) -> Dict:
    """
    完整高级预测 - 支持所有参数
    
    Args:
        home_team: 主队缩写 (如 'LAL')
        away_team: 客队缩写 (如 'BOS')
        home_params: 主队实时参数
            - recent_win_pct: 近期胜率 (0-1)
            - home_advantage: 主场加成 (-0.1 to 0.1)
            - injury_impact: 伤病影响 (-0.3 to 0)
            - rest_days: 休息天数 (>=0)
            - back_to_back: 是否背靠背
            - key_player_out: 缺阵球员列表
            - morale_boost: 士气加成 (-0.15 to 0.15)
            - custom_rating: 自定义实力评分 (0-100)
        away_params: 客队实时参数 (同上)
        weights: 权重配置
            - recent_form: 近期状态权重
            - home_advantage: 主场优势权重
            - historical_matchup: 历史交锋权重
            - efficiency_diff: 效率差权重
            - cluster_similarity: 风格相似度权重
        season: 赛季 (可选)
        
    Returns:
        预测结果
        
    Example:
        >>> result = full_advanced_predict(
        ...     home_team='LAL',
        ...     away_team='BOS',
        ...     home_params={
        ...         'injury_impact': -0.1,
        ...         'key_player_out': ['LeBron James'],
        ...         'rest_days': 1
        ...     },
        ...     away_params={
        ...         'back_to_back': True
        ...     },
        ...     weights={
        ...         'recent_form': 0.3,
        ...         'efficiency_diff': 0.35
        ...     }
        ... )
    """
    return predict_game_advanced(
        home_team=home_team,
        away_team=away_team,
        home_params=home_params,
        away_params=away_params,
        weights=weights,
        season=season,
        use_recent_form=True,
        return_details=True
    )


def batch_predict_advanced(matchups: List[Dict]) -> List[Dict]:
    """
    批量高级预测
    
    Args:
        matchups: 预测列表，每项包含:
            - home_team: 主队
            - away_team: 客队
            - home_params: 主队参数 (可选)
            - away_params: 客队参数 (可选)
            - weights: 权重配置 (可选)
            
    Returns:
        预测结果列表
    """
    results = []
    
    for i, matchup in enumerate(matchups, 1):
        try:
            result = predict_game_advanced(
                home_team=matchup['home_team'],
                away_team=matchup['away_team'],
                home_params=matchup.get('home_params'),
                away_params=matchup.get('away_params'),
                weights=matchup.get('weights')
            )
            results.append(result)
        except Exception as e:
            results.append({
                'home_team': matchup['home_team'],
                'away_team': matchup['away_team'],
                'error': str(e)
            })
    
    return results


# ==================== 参数验证辅助 ====================

def validate_prediction_params(
    home_params: Optional[Dict] = None,
    away_params: Optional[Dict] = None,
    weights: Optional[Dict] = None
) -> tuple[bool, str]:
    """
    验证预测参数
    
    Returns:
        (是否有效, 错误信息)
    """
    if home_params:
        valid, msg = validate_params(home_params, 'home')
        if not valid:
            return valid, msg
    
    if away_params:
        valid, msg = validate_params(away_params, 'away')
        if not valid:
            return valid, msg
    
    if weights:
        valid, msg = validate_weights(weights)
        if not valid:
            return valid, msg
    
    return True, ""


def get_default_params() -> Dict:
    """
    获取默认参数配置
    """
    return {
        'default_weights': DEFAULT_WEIGHTS.copy(),
        'default_home_params': DEFAULT_HOME_PARAMS.copy(),
        'default_away_params': DEFAULT_AWAY_PARAMS.copy()
    }


# ==================== 结果格式化 ====================

def format_prediction_summary(result: Dict) -> str:
    """
    格式化预测结果摘要
    
    Args:
        result: 预测结果
        
    Returns:
        格式化的字符串摘要
    """
    if 'error' in result:
        return f"预测失败: {result['error']}"
    
    lines = [
        f"{'='*50}",
        f"比赛预测: {result['home_team_cn']} vs {result['away_team_cn']}",
        f"{'='*50}",
        f"预测获胜: {result['predicted_winner_cn']}",
        f"主队胜率: {result['home_win_probability']*100:.1f}%",
        f"客队胜率: {result['away_win_probability']*100:.1f}%",
        f"置信度: {result['confidence_level']}",
        "",
        "关键因素:"
    ]
    
    for i, factor in enumerate(result.get('key_factors', [])[:5], 1):
        lines.append(f"  {i}. {factor['description']}")
    
    if 'adjustments_applied' in result:
        lines.append("")
        lines.append("调整详情:")
        adjustments = result['adjustments_applied']
        lines.append(f"  基础概率: {adjustments['base_probability']*100:.1f}%")
        lines.append(f"  最终概率: {adjustments['final_probability']*100:.1f}%")
    
    return "\n".join(lines)


# ==================== 使用示例 ====================

def show_examples():
    """展示使用示例"""
    examples = [
        """
        === 示例 1: 简单预测 ===
        
        from ml.api import simple_predict
        
        result = simple_predict('LAL', 'GSW')
        print(result['predicted_winner'])
        """,
        
        """
        === 示例 2: 考虑伤病 ===
        
        from ml.api import predict_with_injuries
        
        # 湖人缺少詹姆斯，勇士完整阵容
        result = predict_with_injuries(
            home_team='LAL',
            away_team='GSW',
            home_injury_impact=-0.15,
            home_players_out=['LeBron James']
        )
        """,
        
        """
        === 示例 3: 考虑赛程 ===
        
        from ml.api import predict_with_schedule
        
        # 湖人休息2天，勇士背靠背
        result = predict_with_schedule(
            home_team='LAL',
            away_team='GSW',
            home_rest_days=2,
            away_back_to_back=True
        )
        """,
        
        """
        === 示例 4: 自定义权重 ===
        
        from ml.api import predict_with_custom_weights
        
        # 更重视近期状态
        result = predict_with_custom_weights(
            home_team='LAL',
            away_team='BOS',
            recent_form=0.4,      # 提高近期权重
            efficiency_diff=0.3   # 降低效率权重
        )
        """,
        
        """
        === 示例 5: 完整高级预测 ===
        
        from ml.api import full_advanced_predict
        
        result = full_advanced_predict(
            home_team='LAL',
            away_team='BOS',
            home_params={
                'injury_impact': -0.1,
                'key_player_out': ['LeBron James'],
                'rest_days': 1,
                'back_to_back': False
            },
            away_params={
                'back_to_back': True,
                'rest_days': 0
            },
            weights={
                'recent_form': 0.3,
                'home_advantage': 0.2,
                'efficiency_diff': 0.35
            }
        )
        """
    ]
    
    print("\n" + "="*60)
    print("NBA预测API使用示例")
    print("="*60)
    
    for example in examples:
        print(example)


if __name__ == '__main__':
    show_examples()
