# -*- coding: utf-8 -*-
"""Application factory for the NBA prediction web app."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import FLASK_CONFIG


def create_app():
    from flask import Flask

    app = Flask(__name__)
    app.config["SECRET_KEY"] = FLASK_CONFIG["secret_key"]
    app.config["DEBUG"] = FLASK_CONFIG.get("debug", False)

    from .views import api_bp, page_bp
    from .models import init_database

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(page_bp)
    app.db = init_database()
    return app
