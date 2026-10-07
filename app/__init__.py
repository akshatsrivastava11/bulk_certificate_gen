"""
Flask Application Factory
Bulk Certificate Generation System
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()
celery_app = Celery()


def create_app(config_name: str = None) -> Flask:
    """Application factory pattern."""
    app = Flask(__name__, instance_relative_config=False)

    # Load configuration
    from app.config import config
    cfg = config.get(config_name or os.getenv("FLASK_ENV", "production"))
    app.config.from_object(cfg)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize Celery
    _configure_celery(app)

    # Ensure certificate output directory exists
    os.makedirs(app.config["CERTIFICATES_DIR"], exist_ok=True)

    # Register blueprints
    from app.routes.certificates import certificates_bp
    from app.routes.jobs import jobs_bp
    from app.routes.health import health_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(certificates_bp, url_prefix="/api/v1/certificates")
    app.register_blueprint(jobs_bp, url_prefix="/api/v1/jobs")

    # Register error handlers
    _register_error_handlers(app)

    return app


def _configure_celery(app: Flask) -> None:
    """Bind Celery to the Flask app context."""
    celery_app.config_from_object(
        {
            "broker_url": app.config["CELERY_BROKER_URL"],
            "result_backend": app.config["CELERY_RESULT_BACKEND"],
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
            "timezone": "UTC",
            "enable_utc": True,
            "task_routes": {
                "app.services.tasks.*": {"queue": "certificates"},
            },
            # Ensure workers import task modules on startup
            "imports": ["app.services.tasks"],
        }
    )

    class ContextTask(celery_app.Task):
        """Make Celery tasks run inside Flask app context."""

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask


def _register_error_handlers(app: Flask) -> None:
    """Register global error handlers."""
    from flask import jsonify

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad Request", "message": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not Found", "message": str(e)}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method Not Allowed", "message": str(e)}), 405

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
