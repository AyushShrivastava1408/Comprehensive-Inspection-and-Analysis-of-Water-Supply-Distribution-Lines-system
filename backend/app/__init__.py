import logging
import os
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify
from flask_cors import CORS

from .cli import register_cli
from .config import Config
from .errors import register_error_handlers
from .extensions import db, jwt


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    for key in ("ORIGINAL_FOLDER", "ANNOTATED_FOLDER"):
        os.makedirs(app.config[key], exist_ok=True)
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///"):
        db_file = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "", 1)
        if db_file != ":memory:" and os.path.dirname(db_file):
            os.makedirs(os.path.dirname(db_file), exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)
    origins = app.config["CORS_ORIGINS"]
    CORS(app, resources={r"/api/*": {"origins": origins.split(",") if origins != "*" else "*"}})

    from .api import register_blueprints
    register_blueprints(app)
    register_error_handlers(app)
    register_cli(app)

    @jwt.unauthorized_loader
    def _missing(reason):
        return jsonify({"error": "Authentication required", "details": reason}), 401

    @jwt.invalid_token_loader
    def _invalid(reason):
        return jsonify({"error": "Invalid token", "details": reason}), 401

    @jwt.expired_token_loader
    def _expired(h, p):
        return jsonify({"error": "Token expired"}), 401

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    if not os.path.exists(app.config["YOLO_WEIGHTS"]):
        app.logger.warning("YOLO weights not found at %s - analysis will return 503 until best.pt is placed there",
                           app.config["YOLO_WEIGHTS"])
    app.extensions["executor"] = ThreadPoolExecutor(max_workers=app.config["MAX_WORKERS"])
    with app.app_context():
        db.create_all()
    return app
