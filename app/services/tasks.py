"""
Celery tasks for asynchronous certificate generation.
"""
import logging
import os
from datetime import datetime, timezone

from celery import Task, group
from celery.utils.log import get_task_logger

from app import celery_app, db
from app.models import CertificateJob, JobStatus, Recipient, CertificateStatus
from app.services.certificate_generator import generate_certificate_pdf

logger = get_task_logger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


class CertificateTask(Task):
    """Base task that ensures DB session cleanup."""

    abstract = True

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        db.session.remove()


@celery_app.task(
    bind=True,
    base=CertificateTask,
    name="app.services.tasks.process_certificate_job",
    max_retries=3,
    default_retry_delay=30,
    queue="certificates",
)
def process_certificate_job(self, job_id: str):
    """
    Main orchestrator task.
    Updates job status to IN_PROGRESS and fans out individual recipient tasks.
    """
    logger.info(f"[Job {job_id}] Starting certificate generation job.")

    job = CertificateJob.query.get(job_id)
    if not job:
        logger.error(f"[Job {job_id}] Job not found in DB.")
        return {"error": "job_not_found"}

    # Transition → IN_PROGRESS
    job.status = JobStatus.IN_PROGRESS
    db.session.commit()

    recipients = job.recipients.filter(
        Recipient.status == CertificateStatus.PENDING
    ).all()

    if not recipients:
        # Nothing to generate
        job.status = JobStatus.COMPLETED
        job.completed_at = _utcnow()
        db.session.commit()
        return {"message": "No pending recipients."}

    # Fan-out: dispatch individual tasks and collect with chord callback
    recipient_ids = [r.id for r in recipients]
    logger.info(f"[Job {job_id}] Dispatching {len(recipient_ids)} recipient tasks.")

    from celery import chord
    header = group(
        generate_single_certificate.s(job_id, rid) for rid in recipient_ids
    )
    callback = finalize_job.s(job_id)
    chord(header)(callback)

    return {"message": f"Dispatched {len(recipient_ids)} certificate tasks."}


@celery_app.task(
    bind=True,
    base=CertificateTask,
    name="app.services.tasks.generate_single_certificate",
    max_retries=2,
    default_retry_delay=10,
    queue="certificates",
)
def generate_single_certificate(self, job_id: str, recipient_id: str) -> dict:
    """
    Generate a PDF certificate for a single recipient.
    Returns a result dict consumed by the chord callback.
    """
    logger.info(f"[Job {job_id}] Generating certificate for recipient {recipient_id}.")

    recipient = Recipient.query.get(recipient_id)
    if not recipient:
        logger.error(f"Recipient {recipient_id} not found.")
        return {"success": False, "recipient_id": recipient_id, "error": "not_found"}

    # Mark as generating
    recipient.status = CertificateStatus.GENERATING
    db.session.commit()

    try:
        job = recipient.job
        certs_dir = os.getenv("CERTIFICATES_DIR", "generated_certificates")
        job_dir = os.path.join(certs_dir, job_id)
        os.makedirs(job_dir, exist_ok=True)

        safe_name = "".join(
            c if c.isalnum() or c in (" ", "-", "_") else "_"
            for c in recipient.full_name
        ).strip().replace(" ", "_")
        filename = f"{safe_name}_{recipient.id[:8]}.pdf"
        output_path = os.path.join(job_dir, filename)

        generate_certificate_pdf(
            output_path=output_path,
            recipient_name=recipient.full_name,
            event_name=job.event_name,
            issued_by=job.issued_by,
            course_name=recipient.course_name,
            grade=recipient.grade,
            event_date=job.event_date,
            certificate_id=recipient.id,
        )

        # Update recipient record
        recipient.status = CertificateStatus.COMPLETED
        recipient.certificate_filename = filename
        recipient.certificate_url = f"/api/v1/certificates/{job_id}/recipients/{recipient_id}/download"
        recipient.generated_at = _utcnow()
        db.session.commit()

        logger.info(f"[Job {job_id}] Certificate generated: {filename}")
        return {"success": True, "recipient_id": recipient_id}

    except Exception as exc:
        logger.exception(f"[Job {job_id}] Failed to generate for {recipient_id}: {exc}")
        recipient.status = CertificateStatus.FAILED
        recipient.error_message = str(exc)
        db.session.commit()

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"success": False, "recipient_id": recipient_id, "error": str(exc)}


@celery_app.task(
    name="app.services.tasks.finalize_job",
    queue="certificates",
)
def finalize_job(results: list, job_id: str):
    """
    Chord callback – runs after all recipient tasks finish.
    Tallies results and updates job status.
    """
    logger.info(f"[Job {job_id}] Finalizing. Results: {results}")

    job = CertificateJob.query.get(job_id)
    if not job:
        return

    completed = sum(1 for r in results if r and r.get("success"))
    failed = sum(1 for r in results if r and not r.get("success"))

    job.completed_count = completed
    job.failed_count = failed
    job.completed_at = _utcnow()

    if failed == 0:
        job.status = JobStatus.COMPLETED
    elif completed == 0:
        job.status = JobStatus.FAILED
    else:
        job.status = JobStatus.PARTIALLY_COMPLETED

    db.session.commit()
    logger.info(f"[Job {job_id}] Finalized. Status: {job.status.value}")
