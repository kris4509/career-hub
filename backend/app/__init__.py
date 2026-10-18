from flask import Flask, jsonify

from config import Config
from .extensions import db, jwt, cors


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Attach extensions to the app
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "message": "Jobsite API is running"})

    return app