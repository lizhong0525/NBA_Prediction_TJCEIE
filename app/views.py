# -*- coding: utf-8 -*-
"""
Flask路由和视图函数
"""

from flask import Blueprint, request, jsonify, render_template, current_app
import pandas as pd
from datetime import datetime, timedelta

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import TEAM_INFO, API_RESPONSE
from ml import predict_game, predict_game_advanced, validate_params, validate_weights
from ml import DEFAULT_WEIGHTS, DEFAULT_HOME_PARAMS, DEFAULT_AWAY_PARAMS
from utils import logger


# 创建蓝图
api_bp = Blueprint('api', __name__)
page_bp = Blueprint('pages', __name__)


# ==================== API路由 ====================

@api_bp.route('/home', methods=['GET'])
def get_home_data():
    """
    获取首页数据
    GET /api/home
    """
    try:
        db = current_app.db
        
        # 获取今日比赛
        today = datetime.now().strftime('%Y-%m-%d')
        today_games = db.get_game_data(limit=100)
        today_games = today_games[today_games['game_date'].str.startswith(today)] if not today_games.empty else pd.DataFrame()
        
        # 获取近期预测
        recent_predictions = db.get_recent_predictions(limit=5)
        
        # 获取预测准确率
        accuracy = db.get_prediction_accuracy()
        
        return jsonify({
            'success': True,
            'data': {
                'today_games': today_games.to_dict('records') if not today_games.empty else [],
                'recent_predictions': recent_predictions,
                'model_accuracy': accuracy.get('accuracy', 0),
                'total_predictions': accuracy.get('total', 0)
            }
        })
        
    except Exception as e:
        logger.error(f"获取首页数据失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_bp.route('/teams', methods=['GET'])
def get_teams():
    """
    获取所有球队列表
    GET /api/teams
    """
    try:
        db = current_app.db
        
        # 获取当前赛季
        current_year = datetime.now().year
        current_month = datetime.now().month
        if current_month < 7:
            season = f"{current_year - 1}-{str(current_year)[2:]}"
        else:
            season = f"{current_year}-{str(current_year + 1)[2:]}"
        
        # 获取球队赛季统计
        team_stats = db.get_team_season_stats(season=season)
        
        # 格式化球队信息
        teams = []
        for abbr, info in TEAM_INFO.items():
            team_data = {
                'id': info['id'],
                'abbr': abbr,
                'name': info['name'],
                'city': info['city']
            }
            
            # 添加最新统计数据
            stats = team_stats[team_stats['team_abbr'] == abbr]
            if not stats.empty:
                team_data['win_pct'] = stats.iloc[0]['win_pct']
                team_data['wins'] = int(stats.iloc[0]['wins'])
                team_data['losses'] = int(stats.iloc[0]['losses'])
            else:
                team_data['win_pct'] = 0.5
                team_data['wins'] = 0
                team_data['losses'] = 0
            
            teams.append(team_data)
        
        # 按胜率排序
        teams = sorted(teams, key=lambda x: x['win_pct'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': teams
        })
        
    except Exception as e:
        logger.error(f"获取球队列表失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_bp.route('/team/<team_abbr>', methods=['GET'])
def get_team_detail(team_abbr):
    """
    获取球队详情
    GET /api/team/<team_abbr>
    """
    try:
        db = current_app.db
        team_abbr = team_abbr.upper()
        
        # 获取球队基本信息
        if team_abbr not in TEAM_INFO:
            return jsonify({
                'success': False,
                'message': '球队不存在'
            }), 404
        
        team_info = TEAM_INFO[team_abbr]
        
        # 获取赛季
        season = request.args.get('season')
        if not season:
            current_year = datetime.now().year
            current_month = datetime.now().month
            if current_month < 7:
                season = f"{current_year - 1}-{str(current_year)[2:]}"
            else:
                season = f"{current_year}-{str(current_year + 1)[2:]}"
        
        # 获取球队统计数据
        team_stats = db.get_team_season_stats(team_abbr=team_abbr, season=season)
        
        # 获取近期比赛
        recent_games = db.get_game_data(team_abbr=team_abbr, limit=10)
        
        return jsonify({
            'success': True,
            'data': {
                'info': team_info,
                'stats': team_stats.to_dict('records')[0] if not team_stats.empty else {},
                'recent_games': recent_games.to_dict('records') if not recent_games.empty else []
            }
        })
        
    except Exception as e:
        logger.error(f"获取球队详情失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_bp.route('/predict', methods=['POST'])
def api_predict_game():
    """
    预测比赛结果 - 支持简单和高级模式
    POST /api/predict
    
    简单模式:
    {"home_team": "LAL", "away_team": "GSW"}
    
    高级模式:
    {
        "home_team": "LAL",
        "away_team": "GSW",
        "mode": "advanced",
        "home_params": {
            "recent_win_pct": 0.7,
            "injury_impact": -0.1,
            "rest_days": 2,
            "back_to_back": false,
            "key_player_out": ["LeBron James"],
            "morale_boost": 0.05
        },
        "away_params": {
            "recent_win_pct": 0.6,
            "injury_impact": 0,
            "rest_days": 1,
            "back_to_back": true
        },
        "weights": {
            "recent_form": 0.3,
            "home_advantage": 0.15,
            "historical_matchup": 0.1,
            "efficiency_diff": 0.35,
            "cluster_similarity": 0.1
        },
        "season": "2024-25"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据为空'
            }), 400
        
        home_team = data.get('home_team', '').upper()
        away_team = data.get('away_team', '').upper()
        
        if not home_team or not away_team:
            return jsonify({
                'success': False,
                'message': '缺少球队参数'
            }), 400
        
        if home_team == away_team:
            return jsonify({
                'success': False,
                'message': '主客队不能相同'
            }), 400
        
        # 验证球队
        if home_team not in TEAM_INFO:
            return jsonify({
                'success': False,
                'message': f'球队 {home_team} 不存在'
            }), 400
        
        if away_team not in TEAM_INFO:
            return jsonify({
                'success': False,
                'message': f'球队 {away_team} 不存在'
            }), 400
        
        # 判断使用简单模式还是高级模式
        mode = data.get('mode', 'simple')
        
        if mode == 'advanced':
            # 高级模式：使用新的预测接口
            return _predict_advanced(data, home_team, away_team)
        else:
            # 简单模式：使用原有预测接口
            return _predict_simple(data, home_team, away_team)
            
    except Exception as e:
        logger.error(f"预测失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


def _predict_simple(data: dict, home_team: str, away_team: str):
    """简单预测模式"""
    db = current_app.db
    
    # 直接调用预测函数
    prediction = predict_game(home_team, away_team)
    
    # 简化返回数据
    result = {
        'prediction_id': prediction.get('prediction_id'),
        'prediction_time': prediction.get('prediction_time'),
        'home_team': prediction.get('home_team'),
        'home_team_cn': prediction.get('home_team_cn'),
        'away_team': prediction.get('away_team'),
        'away_team_cn': prediction.get('away_team_cn'),
        'predicted_winner': prediction.get('predicted_winner'),
        'predicted_winner_cn': prediction.get('predicted_winner_cn'),
        'home_win_prob': prediction.get('home_win_probability'),
        'away_win_prob': prediction.get('away_win_probability'),
        'confidence_level': prediction.get('confidence_level'),
        'key_factors': prediction.get('key_factors', []),
        'mode': 'simple'
    }
    
    # 保存预测结果
    try:
        db.insert_prediction({
            'prediction_id': prediction.get('prediction_id'),
            'home_team': home_team,
            'away_team': away_team,
            'predicted_winner': prediction.get('predicted_winner'),
            'home_win_prob': prediction.get('home_win_probability'),
            'away_win_prob': prediction.get('away_win_probability'),
            'confidence': prediction.get('confidence_level'),
            'prediction_time': prediction.get('prediction_time'),
            'mode': 'simple'
        })
    except Exception as e:
        logger.warning(f"保存预测结果失败: {e}")
    
    return jsonify({
        'success': True,
        'data': result,
        'mode': 'simple'
    })


def _predict_advanced(data: dict, home_team: str, away_team: str):
    """高级预测模式 - 支持实时参数"""
    # 提取参数
    home_params = data.get('home_params')
    away_params = data.get('away_params')
    weights = data.get('weights')
    season = data.get('season')
    
    # 参数验证
    if home_params:
        valid, msg = validate_params(home_params, 'home')
        if not valid:
            return jsonify({
                'success': False,
                'message': f'主队参数错误: {msg}'
            }), 400
    
    if away_params:
        valid, msg = validate_params(away_params, 'away')
        if not valid:
            return jsonify({
                'success': False,
                'message': f'客队参数错误: {msg}'
            }), 400
    
    if weights:
        valid, msg = validate_weights(weights)
        if not valid:
            return jsonify({
                'success': False,
                'message': f'权重配置错误: {msg}'
            }), 400
    
    # 获取赛季
    if not season:
        current_year = datetime.now().year
        current_month = datetime.now().month
        if current_month < 7:
            season = f"{current_year - 1}-{str(current_year)[2:]}"
        else:
            season = f"{current_year}-{str(current_year + 1)[2:]}"
    
    # 执行高级预测
    prediction = predict_game_advanced(
        home_team=home_team,
        away_team=away_team,
        home_params=home_params,
        away_params=away_params,
        weights=weights,
        season=season,
        use_recent_form=True,
        return_details=True
    )
    
    # 保存预测结果到数据库
    try:
        db = current_app.db
        db.insert_prediction({
            'prediction_id': prediction['prediction_id'],
            'home_team': home_team,
            'away_team': away_team,
            'predicted_winner': prediction['predicted_winner'],
            'home_win_prob': prediction['home_win_probability'],
            'away_win_prob': prediction['away_win_probability'],
            'confidence': prediction['confidence_level'],
            'prediction_time': prediction['prediction_time'],
            'mode': 'advanced'
        })
    except Exception as e:
        logger.warning(f"保存预测结果失败: {e}")
    
    # 简化返回的数据结构
    result = {
        'prediction_id': prediction['prediction_id'],
        'prediction_time': prediction['prediction_time'],
        'home_team': prediction['home_team'],
        'home_team_cn': prediction['home_team_cn'],
        'away_team': prediction['away_team'],
        'away_team_cn': prediction['away_team_cn'],
        'predicted_winner': prediction['predicted_winner'],
        'predicted_winner_cn': prediction['predicted_winner_cn'],
        'home_win_probability': prediction['home_win_probability'],
        'away_win_probability': prediction['away_win_probability'],
        'confidence_level': prediction['confidence_level'],
        'key_factors': prediction['key_factors'],
        'adjustments_applied': prediction.get('adjustments_applied', {}),
        'mode': 'advanced'
    }
    
    return jsonify({
        'success': True,
        'data': result
    })


@api_bp.route('/predict/validate', methods=['POST'])
def validate_prediction_params():
    """
    验证预测参数
    POST /api/predict/validate
    
    Request:
    {
        "home_params": {...},
        "away_params": {...},
        "weights": {...}
    }
    """
    try:
        data = request.get_json() or {}
        
        home_params = data.get('home_params')
        away_params = data.get('away_params')
        weights = data.get('weights')
        
        errors = []
        
        if home_params:
            valid, msg = validate_params(home_params, 'home')
            if not valid:
                errors.append(f'home_params: {msg}')
        
        if away_params:
            valid, msg = validate_params(away_params, 'away')
            if not valid:
                errors.append(f'away_params: {msg}')
        
        if weights:
            valid, msg = validate_weights(weights)
            if not valid:
                errors.append(f'weights: {msg}')
        
        if errors:
            return jsonify({
                'success': False,
                'message': '参数验证失败',
                'errors': errors
            }), 400
        
        return jsonify({
            'success': True,
            'message': '参数验证通过',
            'defaults': {
                'weights': DEFAULT_WEIGHTS,
                'home_params': DEFAULT_HOME_PARAMS,
                'away_params': DEFAULT_AWAY_PARAMS
            }
        })
        
    except Exception as e:
        logger.error(f"参数验证失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_bp.route('/predict/params', methods=['GET'])
def get_prediction_params():
    """
    获取预测参数说明
    GET /api/predict/params
    """
    return jsonify({
        'success': True,
        'data': {
            'home_params': {
                'recent_win_pct': {
                    'type': 'float',
                    'range': [0, 1],
                    'description': '近期胜率'
                },
                'home_advantage': {
                    'type': 'float',
                    'range': [-0.1, 0.1],
                    'description': '主场加成'
                },
                'injury_impact': {
                    'type': 'float',
                    'range': [-0.3, 0],
                    'description': '伤病影响'
                },
                'rest_days': {
                    'type': 'int',
                    'range': [0, 10],
                    'description': '休息天数'
                },
                'back_to_back': {
                    'type': 'bool',
                    'description': '是否背靠背'
                },
                'key_player_out': {
                    'type': 'list',
                    'description': '缺阵核心球员列表'
                },
                'morale_boost': {
                    'type': 'float',
                    'range': [-0.15, 0.15],
                    'description': '士气加成'
                }
            },
            'weights': {
                'recent_form': {
                    'type': 'float',
                    'default': 0.25,
                    'description': '近期状态权重'
                },
                'home_advantage': {
                    'type': 'float',
                    'default': 0.15,
                    'description': '主场优势权重'
                },
                'historical_matchup': {
                    'type': 'float',
                    'default': 0.10,
                    'description': '历史交锋权重'
                },
                'efficiency_diff': {
                    'type': 'float',
                    'default': 0.40,
                    'description': '效率差权重'
                },
                'cluster_similarity': {
                    'type': 'float',
                    'default': 0.10,
                    'description': '风格相似度权重'
                }
            },
            'default_weights': DEFAULT_WEIGHTS,
            'default_home_params': DEFAULT_HOME_PARAMS,
            'default_away_params': DEFAULT_AWAY_PARAMS
        }
    })


@api_bp.route('/predictions/history', methods=['GET'])
def get_prediction_history():
    """
    获取预测历史
    GET /api/predictions/history
    """
    try:
        db = current_app.db
        
        limit = request.args.get('limit', 20, type=int)
        
        # 获取历史预测
        predictions = db.get_recent_predictions(limit=limit)
        
        # 获取准确率统计
        accuracy = db.get_prediction_accuracy()
        
        return jsonify({
            'success': True,
            'data': {
                'predictions': predictions,
                'total': accuracy.get('total', 0),
                'correct': accuracy.get('correct', 0),
                'accuracy': accuracy.get('accuracy', 0)
            }
        })
        
    except Exception as e:
        logger.error(f"获取预测历史失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_bp.route('/games', methods=['GET'])
def get_games():
    """
    获取比赛列表
    GET /api/games
    """
    try:
        db = current_app.db
        
        team_abbr = request.args.get('team')
        season = request.args.get('season')
        limit = request.args.get('limit', 50, type=int)
        
        games = db.get_game_data(team_abbr=team_abbr, season=season, limit=limit)
        
        return jsonify({
            'success': True,
            'data': games.to_dict('records') if not games.empty else []
        })
        
    except Exception as e:
        logger.error(f"获取比赛列表失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_bp.route('/stats/ranking', methods=['GET'])
def get_stats_ranking():
    """
    获取统计数据排名
    GET /api/stats/ranking
    """
    try:
        db = current_app.db
        
        stat_type = request.args.get('type', 'win_pct')
        season = request.args.get('season')
        
        if not season:
            current_year = datetime.now().year
            current_month = datetime.now().month
            if current_month < 7:
                season = f"{current_year - 1}-{str(current_year)[2:]}"
            else:
                season = f"{current_year}-{str(current_year + 1)[2:]}"
        
        # 获取赛季统计
        team_stats = db.get_team_season_stats(season=season)
        
        if team_stats.empty:
            return jsonify({
                'success': True,
                'data': []
            })
        
        # 按指定统计类型排序
        if stat_type in team_stats.columns:
            team_stats = team_stats.sort_values(stat_type, ascending=False)
        
        # 转换为列表
        ranking = []
        for i, row in team_stats.iterrows():
            ranking.append({
                'rank': len(ranking) + 1,
                'team_abbr': row['team_abbr'],
                'team_name': row.get('team_name', TEAM_INFO.get(row['team_abbr'], {}).get('name', row['team_abbr'])),
                'stat_value': row.get(stat_type, 0)
            })
        
        return jsonify({
            'success': True,
            'data': ranking
        })
        
    except Exception as e:
        logger.error(f"获取排名失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    健康检查
    GET /api/health
    """
    try:
        db = current_app.db
        stats = db.get_table_stats()
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'database': {
                'games': stats.get('team_game_stats', 0),
                'seasons': stats.get('team_season_stats', 0),
                'predictions': stats.get('prediction_results', 0)
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }), 500


# ==================== 页面路由 ====================

@page_bp.route('/')
def index():
    """首页"""
    return render_template('index.html')


@page_bp.route('/predict')
def predict_page():
    """预测页面"""
    return render_template('predict.html')


@page_bp.route('/team/<team_abbr>')
def team_page(team_abbr):
    """球队详情页"""
    return render_template('team.html', team_abbr=team_abbr)


@page_bp.route('/data')
def data_page():
    """数据页面"""
    return render_template('data.html')


@page_bp.route('/about')
def about_page():
    """关于页面"""
    return render_template('about.html')
