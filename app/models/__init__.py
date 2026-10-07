"""
Database Models
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from app import db


def utcnow():
    return datetime.now(timezone.utc)


def generate_uuid():
    return str(uuid.uuid4())


# ─── Enumerations ─────────────────────────────────────────────────────────────

class JobStatus(PyEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


class CertificateStatus(PyEnum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


# ─── Certificate Job ───────────────────────────────────────────────────────────

class CertificateJob(db.Model):
    """
    Represents a bulk certificate generation request.
    One job may contain many recipients.
    """
    __tablename__ = "certificate_jobs"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_name = db.Column(db.String(255), nullable=False)
    event_date = db.Column(db.Date, nullable=True)
    issued_by = db.Column(db.String(255), nullable=False)

    # Status tracking
    status = db.Column(
        db.Enum(JobStatus, name="job_status_enum"),
        nullable=False,
        default=JobStatus.PENDING,
    )
    total_recipients = db.Column(db.Integer, nullable=False, default=0)
    completed_count = db.Column(db.Integer, nullable=False, default=0)
    failed_count = db.Column(db.Integer, nullable=False, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Celery task ID for tracking
    celery_task_id = db.Column(db.String(255), nullable=True)

    # Relationships
    recipients = db.relationship(
        "Recipient", back_populates="job", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def progress_pct(self) -> float:
        if self.total_recipients == 0:
            return 0.0
        processed = self.completed_count + self.failed_count
        return round((processed / self.total_recipients) * 100, 2)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "event_name": self.event_name,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "issued_by": self.issued_by,
            "status": self.status.value,
            "total_recipients": self.total_recipients,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "progress_pct": self.progress_pct,
            "celery_task_id": self.celery_task_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self):
        return f"<CertificateJob {self.id} [{self.status.value}]>"


# ─── Recipient ─────────────────────────────────────────────────────────────────

class Recipient(db.Model):
    """
    Represents an individual certificate recipient within a job.
    """
    __tablename__ = "recipients"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    job_id = db.Column(
        db.String(36),
        db.ForeignKey("certificate_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Recipient details
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    course_name = db.Column(db.String(255), nullable=True)
    grade = db.Column(db.String(50), nullable=True)
    extra_fields = db.Column(db.JSON, nullable=True)  # flexible additional data

    # Status
    status = db.Column(
        db.Enum(CertificateStatus, name="cert_status_enum"),
        nullable=False,
        default=CertificateStatus.PENDING,
    )
    error_message = db.Column(db.Text, nullable=True)

    # Generated certificate reference
    certificate_filename = db.Column(db.String(512), nullable=True)
    certificate_url = db.Column(db.String(1024), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    job = db.relationship("CertificateJob", back_populates="recipients")

    def to_dict(self, include_job: bool = False) -> dict:
        data = {
            "id": self.id,
            "job_id": self.job_id,
            "full_name": self.full_name,
            "email": self.email,
            "course_name": self.course_name,
            "grade": self.grade,
            "extra_fields": self.extra_fields,
            "status": self.status.value,
            "error_message": self.error_message,
            "certificate_filename": self.certificate_filename,
            "certificate_url": self.certificate_url,
            "created_at": self.created_at.isoformat(),
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
        }
        if include_job and self.job:
            data["job"] = self.job.to_dict()
        return data

    def __repr__(self):
        return f"<Recipient {self.full_name} [{self.status.value}]>"
