# -*- coding: utf-8 -*-
"""
Flask应用初始化
"""

from flask import Flask
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import FLASK_CONFIG


def create_app():
    """
    创建Flask应用实例
    
    Returns:
        Flask应用对象
    """
    app = Flask(__name__)
    
    # 配置
    app.config['SECRET_KEY'] = FLASK_CONFIG['secret_key']
    app.config['DEBUG'] = FLASK_CONFIG.get('debug', False)
    
    # 注册蓝图
    from .views import api_bp, page_bp
    
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(page_bp)
    
    # 初始化数据库
    from .models import init_database
    db = init_database()
    app.db = db
    
    return app
