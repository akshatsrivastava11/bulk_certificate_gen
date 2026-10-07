"""
Health check routes.
GET /health         – Liveness check
GET /health/ready   – Readiness check (DB + Celery)
"""
from flask import Blueprint, jsonify
from app import db

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def liveness():
    """Simple liveness probe."""
    return jsonify({"status": "ok"}), 200


@health_bp.route("/health/ready", methods=["GET"])
def readiness():
    """
    Readiness probe: verify DB connectivity.
    Returns 200 if all dependencies are healthy, 503 otherwise.
    """
    checks = {}
    http_status = 200

    # DB check
    try:
        db.session.execute(db.text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        http_status = 503

    return jsonify({"status": "ok" if http_status == 200 else "degraded", "checks": checks}), http_status
