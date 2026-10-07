"""
Job tracking routes (shorthand status endpoint).
GET /api/v1/jobs/<job_id>  – Quick status check (alias)
"""
from flask import Blueprint, jsonify
from app import db
from app.models import CertificateJob

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.route("/<string:job_id>", methods=["GET"])
def get_job_status(job_id: str):
    """Quick status/progress endpoint for a certificate job."""
    job = db.session.get(CertificateJob, job_id)
    if not job:
        return jsonify({"error": f"Job '{job_id}' not found."}), 404

    return jsonify({
        "job_id": job.id,
        "title": job.title,
        "status": job.status.value,
        "total_recipients": job.total_recipients,
        "completed_count": job.completed_count,
        "failed_count": job.failed_count,
        "progress_pct": job.progress_pct,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }), 200
