# -*- coding: utf-8 -*-
"""
NBA比赛预测接口测试脚本
用于验证实时参数预测功能是否正常工作
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from ml.predict import (
    predict_game_advanced,
    validate_params,
    validate_weights,
    DEFAULT_WEIGHTS,
    DEFAULT_HOME_PARAMS,
    DEFAULT_AWAY_PARAMS
)
from ml.api import (
    simple_predict,
    predict_with_injuries,
    predict_with_schedule,
    predict_with_custom_weights,
    full_advanced_predict,
    batch_predict_advanced,
    validate_prediction_params,
    get_default_params,
    format_prediction_summary
)


def test_validate_params():
    """测试参数验证"""
    print("\n" + "="*50)
    print("测试 1: 参数验证")
    print("="*50)
    
    # 测试有效参数
    valid, msg = validate_params({'injury_impact': -0.15}, 'home')
    assert valid, f"应该通过: {msg}"
    print("✓ 有效参数验证通过")
    
    # 测试无效参数
    valid, msg = validate_params({'injury_impact': 0.5}, 'home')
    assert not valid, "应该失败"
    print(f"✓ 无效参数正确拒绝: {msg}")
    
    # 测试权重验证
    valid, msg = validate_weights({'recent_form': 0.3})
    assert valid, f"权重验证应该通过: {msg}"
    print("✓ 权重验证通过")


def test_default_params():
    """测试默认参数"""
    print("\n" + "="*50)
    print("测试 2: 默认参数")
    print("="*50)
    
    defaults = get_default_params()
    assert defaults['default_weights'] == DEFAULT_WEIGHTS
    assert defaults['default_home_params'] == DEFAULT_HOME_PARAMS
    assert defaults['default_away_params'] == DEFAULT_AWAY_PARAMS
    print(f"默认权重: {DEFAULT_WEIGHTS}")
    print(f"默认主队参数: {DEFAULT_HOME_PARAMS}")
    print("✓ 默认参数获取成功")


def test_simple_predict():
    """测试简单预测"""
    print("\n" + "="*50)
    print("测试 3: 简单预测")
    print("="*50)
    
    result = simple_predict('LAL', 'BOS')
    assert 'predicted_winner' in result
    assert 'home_win_probability' in result
    assert 'key_factors' in result
    print(f"✓ 简单预测成功")
    print(f"  预测获胜: {result['predicted_winner_cn']}")
    print(f"  主队胜率: {result['home_win_probability']:.2%}")


def test_predict_with_injuries():
    """测试带伤病参数的预测"""
    print("\n" + "="*50)
    print("测试 4: 带伤病参数预测")
    print("="*50)
    
    result = predict_with_injuries(
        'LAL', 'BOS',
        home_injury_impact=-0.15,
        home_players_out=['LeBron James']
    )
    assert 'injury' in [f['type'] for f in result['key_factors']]
    print("✓ 带伤病参数预测成功")
    print(f"  主队胜率: {result['home_win_probability']:.2%}")


def test_predict_with_schedule():
    """测试带赛程参数的预测"""
    print("\n" + "="*50)
    print("测试 5: 带赛程参数预测")
    print("="*50)
    
    result = predict_with_schedule(
        'LAL', 'BOS',
        home_rest_days=3,
        away_back_to_back=True
    )
    print("✓ 带赛程参数预测成功")
    print(f"  主队胜率: {result['home_win_probability']:.2%}")


def test_predict_with_custom_weights():
    """测试自定义权重预测"""
    print("\n" + "="*50)
    print("测试 6: 自定义权重预测")
    print("="*50)
    
    result = predict_with_custom_weights(
        'LAL', 'BOS',
        recent_form=0.5,
        efficiency_diff=0.2
    )
    assert result['model_inputs']['weights_used']['recent_form'] == 0.5
    print("✓ 自定义权重预测成功")
    print(f"  使用权重: {result['model_inputs']['weights_used']}")


def test_full_advanced_predict():
    """测试完整高级预测"""
    print("\n" + "="*50)
    print("测试 7: 完整高级预测")
    print("="*50)
    
    result = full_advanced_predict(
        home_team='LAL',
        away_team='BOS',
        home_params={
            'injury_impact': -0.1,
            'key_player_out': ['LeBron James'],
            'rest_days': 1
        },
        away_params={
            'back_to_back': True,
            'rest_days': 0
        },
        weights={
            'recent_form': 0.3,
            'efficiency_diff': 0.35
        }
    )
    
    # 验证返回结构
    assert 'prediction_id' in result
    assert 'adjustments_applied' in result
    assert 'realtime_params' in result
    assert 'confidence_level' in result
    
    print("✓ 完整高级预测成功")
    print(f"  基础概率: {result['adjustments_applied']['base_probability']:.2%}")
    print(f"  最终概率: {result['adjustments_applied']['final_probability']:.2%}")
    print(f"  置信度: {result['confidence_level']}")
    print(f"  关键因素数量: {len(result['key_factors'])}")


def test_batch_predict():
    """测试批量预测"""
    print("\n" + "="*50)
    print("测试 8: 批量预测")
    print("="*50)
    
    matchups = [
        {'home_team': 'LAL', 'away_team': 'BOS'},
        {'home_team': 'GSW', 'away_team': 'DEN'},
        {'home_team': 'MIA', 'away_team': 'NYK'},
    ]
    
    results = batch_predict_advanced(matchups)
    assert len(results) == 3
    print(f"✓ 批量预测成功，预测了 {len(results)} 场比赛")
    for r in results:
        if 'error' not in r:
            print(f"  {r['home_team']} vs {r['away_team']}: {r['predicted_winner_cn']}")


def test_format_summary():
    """测试结果格式化"""
    print("\n" + "="*50)
    print("测试 9: 结果格式化")
    print("="*50)
    
    result = simple_predict('LAL', 'BOS')
    summary = format_prediction_summary(result)
    assert '比赛预测' in summary
    assert '主队胜率' in summary
    print("✓ 结果格式化成功")
    print("\n" + summary)


def run_all_tests():
    """运行所有测试"""
    print("\n" + "#"*60)
    print("# NBA比赛预测实时参数接口测试")
    print("#"*60)
    
    tests = [
        test_validate_params,
        test_default_params,
        test_simple_predict,
        test_predict_with_injuries,
        test_predict_with_schedule,
        test_predict_with_custom_weights,
        test_full_advanced_predict,
        test_batch_predict,
        test_format_summary,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("="*60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
