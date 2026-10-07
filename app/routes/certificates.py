"""
Certificate Jobs API Routes

POST   /api/v1/certificates/jobs           – Create a new certificate generation job
GET    /api/v1/certificates/jobs           – List all jobs (with filters & pagination)
GET    /api/v1/certificates/jobs/<job_id>  – Get a specific job's status/details
DELETE /api/v1/certificates/jobs/<job_id>  – Cancel/delete a job
"""
import os
from flask import Blueprint, jsonify, request, send_file, abort, current_app
from marshmallow import ValidationError

from app import db
from app.models import CertificateJob, JobStatus, Recipient, CertificateStatus
from app.schemas import CreateJobSchema, JobFilterSchema
from app.services.tasks import process_certificate_job

certificates_bp = Blueprint("certificates", __name__)

create_schema = CreateJobSchema()
filter_schema = JobFilterSchema()


# ─── Create Job ─────────────────────────────────────────────────────────────

@certificates_bp.route("/jobs", methods=["POST"])
def create_job():
    """
    Create a bulk certificate generation job.

    Request body (JSON):
    {
        "title": "Q1 2024 Training",
        "description": "Optional description",
        "event_name": "Annual Developer Summit",
        "event_date": "2024-06-15",
        "issued_by": "Acme Corp",
        "recipients": [
            {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "course_name": "Python Mastery",
                "grade": "A+"
            }
        ]
    }

    Returns 202 Accepted with the job ID and tracking URL.
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        data = create_schema.load(request.get_json())
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 422

    import uuid
    job_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    # Create job record
    job = CertificateJob(
        id=job_id,
        title=data["title"],
        description=data.get("description"),
        event_name=data["event_name"],
        event_date=data.get("event_date"),
        issued_by=data["issued_by"],
        status=JobStatus.PENDING,
        celery_task_id=task_id,
        total_recipients=len(data["recipients"]),
    )
    db.session.add(job)

    # Add recipients
    for r in data["recipients"]:
        rec = Recipient(
            id=str(uuid.uuid4()),
            job_id=job_id,
            full_name=r["full_name"],
            email=r["email"],
            course_name=r.get("course_name"),
            grade=r.get("grade"),
            extra_fields=r.get("extra_fields"),
        )
        db.session.add(rec)

    db.session.commit()

    # Dispatch Celery task
    process_certificate_job.apply_async(args=[job_id], task_id=task_id)

    return jsonify({
        "message": "Certificate generation job accepted.",
        "job_id": job_id,
        "total_recipients": len(data["recipients"]),
        "status": JobStatus.PENDING.value,
        "status_url": f"/api/v1/jobs/{job_id}",
    }), 202


# ─── List Jobs ──────────────────────────────────────────────────────────────

@certificates_bp.route("/jobs", methods=["GET"])
def list_jobs():
    """
    List certificate jobs with optional status filter and pagination.

    Query params:
    - status: pending | in_progress | completed | failed | partially_completed
    - page: int (default 1)
    - per_page: int (default 20, max 100)
    """
    try:
        params = filter_schema.load(request.args)
    except ValidationError as err:
        return jsonify({"error": "Invalid query parameters", "details": err.messages}), 400

    query = CertificateJob.query.order_by(CertificateJob.created_at.desc())

    if params.get("status"):
        try:
            status_enum = JobStatus(params["status"])
            query = query.filter(CertificateJob.status == status_enum)
        except ValueError:
            valid = [s.value for s in JobStatus]
            return jsonify({
                "error": f"Invalid status. Valid values: {valid}"
            }), 400

    page = params["page"]
    per_page = params["per_page"]
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "jobs": [job.to_dict() for job in pagination.items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }), 200


# ─── Get Job ─────────────────────────────────────────────────────────────────

@certificates_bp.route("/jobs/<string:job_id>", methods=["GET"])
def get_job(job_id: str):
    """Get a specific job's details and progress."""
    job = db.session.get(CertificateJob, job_id)
    if not job:
        return jsonify({"error": f"Job '{job_id}' not found."}), 404

    include_recipients = request.args.get("include_recipients", "false").lower() == "true"
    job_data = job.to_dict()

    if include_recipients:
        recipients = job.recipients.all()
        job_data["recipients"] = [r.to_dict() for r in recipients]

    return jsonify(job_data), 200


# ─── Get Recipients for a Job ────────────────────────────────────────────────

@certificates_bp.route("/jobs/<string:job_id>/recipients", methods=["GET"])
def list_job_recipients(job_id: str):
    """List all recipients for a job with optional status filter."""
    job = db.session.get(CertificateJob, job_id)
    if not job:
        return jsonify({"error": f"Job '{job_id}' not found."}), 404

    status_filter = request.args.get("status")
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    query = job.recipients

    if status_filter:
        try:
            status_enum = CertificateStatus(status_filter)
            query = query.filter(Recipient.status == status_enum)
        except ValueError:
            valid = [s.value for s in CertificateStatus]
            return jsonify({"error": f"Invalid status. Valid values: {valid}"}), 400

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "job_id": job_id,
        "recipients": [r.to_dict() for r in pagination.items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }), 200


# ─── Download Certificate ────────────────────────────────────────────────────

@certificates_bp.route("/jobs/<string:job_id>/recipients/<string:recipient_id>/download", methods=["GET"])
def download_certificate(job_id: str, recipient_id: str):
    """Download the generated PDF certificate for a specific recipient."""
    recipient = Recipient.query.filter_by(id=recipient_id, job_id=job_id).first()
    if not recipient:
        return jsonify({"error": "Recipient not found."}), 404

    if recipient.status != CertificateStatus.COMPLETED:
        return jsonify({
            "error": "Certificate not yet generated.",
            "status": recipient.status.value,
        }), 409

    certs_dir = current_app.config["CERTIFICATES_DIR"]
    file_path = os.path.join(certs_dir, job_id, recipient.certificate_filename)

    if not os.path.exists(file_path):
        return jsonify({"error": "Certificate file not found on disk."}), 404

    safe_filename = f"certificate_{recipient.full_name.replace(' ', '_')}.pdf"
    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=safe_filename,
    )


# ─── Delete Job ──────────────────────────────────────────────────────────────

@certificates_bp.route("/jobs/<string:job_id>", methods=["DELETE"])
def delete_job(job_id: str):
    """Delete a job and all its associated certificates."""
    job = db.session.get(CertificateJob, job_id)
    if not job:
        return jsonify({"error": f"Job '{job_id}' not found."}), 404

    if job.status == JobStatus.IN_PROGRESS:
        return jsonify({
            "error": "Cannot delete a job that is currently in progress."
        }), 409

    # Clean up generated files
    certs_dir = current_app.config["CERTIFICATES_DIR"]
    import shutil
    job_dir = os.path.join(certs_dir, job_id)
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir, ignore_errors=True)

    db.session.delete(job)
    db.session.commit()

    return jsonify({"message": f"Job '{job_id}' deleted successfully."}), 200
