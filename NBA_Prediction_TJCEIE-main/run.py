# -*- coding: utf-8 -*-
"""
Flask应用入口
"""

from app import create_app

app = create_app()

if __name__ == '__main__':
    from config import FLASK_CONFIG
    
    app.run(
        host=FLASK_CONFIG.get('host', '0.0.0.0'),
        port=FLASK_CONFIG.get('port', 5000),
        debug=FLASK_CONFIG.get('debug', True)
    )
