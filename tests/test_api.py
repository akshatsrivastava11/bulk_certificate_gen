"""
Integration tests for the Certificate Generation API.
Run with: pytest tests/ -v
"""
import json
import os
import pytest

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")


@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    from app import create_app, db
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_session(app):
    from app import db
    with app.app_context():
        yield db
        db.session.rollback()


VALID_JOB_PAYLOAD = {
    "title": "Test Training Program",
    "description": "A test certificate job",
    "event_name": "Test Summit 2024",
    "event_date": "2024-06-15",
    "issued_by": "Test Corp",
    "recipients": [
        {
            "full_name": "Alice Johnson",
            "email": "alice@example.com",
            "course_name": "Python Basics",
            "grade": "A",
        },
        {
            "full_name": "Bob Smith",
            "email": "bob@example.com",
            "course_name": "Python Basics",
            "grade": "B+",
        },
    ],
}


# ─── Health checks ────────────────────────────────────────────────────────────

class TestHealth:
    def test_liveness(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"


# ─── Job creation ─────────────────────────────────────────────────────────────

class TestCreateJob:
    def test_create_job_success(self, client):
        resp = client.post(
            "/api/v1/certificates/jobs",
            data=json.dumps(VALID_JOB_PAYLOAD),
            content_type="application/json",
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "job_id" in data
        assert data["total_recipients"] == 2
        assert data["status"] == "pending"

    def test_create_job_missing_required_field(self, client):
        payload = {**VALID_JOB_PAYLOAD}
        del payload["title"]
        resp = client.post(
            "/api/v1/certificates/jobs",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_create_job_empty_recipients(self, client):
        payload = {**VALID_JOB_PAYLOAD, "recipients": []}
        resp = client.post(
            "/api/v1/certificates/jobs",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_create_job_invalid_email(self, client):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [{"full_name": "Test User", "email": "not-an-email"}],
        }
        resp = client.post(
            "/api/v1/certificates/jobs",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_create_job_duplicate_emails(self, client):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [
                {"full_name": "Alice", "email": "same@example.com"},
                {"full_name": "Bob", "email": "same@example.com"},
            ],
        }
        resp = client.post(
            "/api/v1/certificates/jobs",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_create_job_non_json_content_type(self, client):
        resp = client.post("/api/v1/certificates/jobs", data="plain text")
        assert resp.status_code == 415


# ─── Job retrieval ────────────────────────────────────────────────────────────

class TestGetJob:
    def _create_job(self, client):
        resp = client.post(
            "/api/v1/certificates/jobs",
            data=json.dumps(VALID_JOB_PAYLOAD),
            content_type="application/json",
        )
        return resp.get_json()["job_id"]

    def test_get_job_success(self, client):
        job_id = self._create_job(client)
        resp = client.get(f"/api/v1/certificates/jobs/{job_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == job_id

    def test_get_job_not_found(self, client):
        resp = client.get("/api/v1/certificates/jobs/nonexistent-id")
        assert resp.status_code == 404

    def test_list_jobs(self, client):
        resp = client.get("/api/v1/certificates/jobs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "jobs" in data
        assert "pagination" in data

    def test_list_jobs_with_status_filter(self, client):
        resp = client.get("/api/v1/certificates/jobs?status=pending")
        assert resp.status_code == 200

    def test_list_jobs_invalid_status(self, client):
        resp = client.get("/api/v1/certificates/jobs?status=invalid_status")
        assert resp.status_code == 400

    def test_get_job_with_recipients(self, client):
        job_id = self._create_job(client)
        resp = client.get(f"/api/v1/certificates/jobs/{job_id}?include_recipients=true")
        assert resp.status_code == 200
        assert "recipients" in resp.get_json()

    def test_quick_status_endpoint(self, client):
        job_id = self._create_job(client)
        resp = client.get(f"/api/v1/jobs/{job_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "progress_pct" in data


# ─── PDF Generator unit test ─────────────────────────────────────────────────

class TestCertificateGenerator:
    def test_generates_pdf_file(self, tmp_path):
        from app.services.certificate_generator import generate_certificate_pdf
        from datetime import date

        output = str(tmp_path / "test_cert.pdf")
        result = generate_certificate_pdf(
            output_path=output,
            recipient_name="Jane Doe",
            event_name="Test Event",
            issued_by="Test Org",
            course_name="Advanced Testing",
            grade="A+",
            event_date=date(2024, 6, 15),
            certificate_id="abc-123",
        )
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0
        # Check it's a valid PDF
        with open(result, "rb") as f:
            header = f.read(4)
        assert header == b"%PDF"


# ─── Execution Time & Concurrency Metrics ────────────────────────────────────

import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed


class TestExecutionTimeMetrics:
    """Metrics defining the execution time / latency for single requests."""

    def test_single_request_health_execution_time(self, client):
        start = time.perf_counter()
        resp = client.get("/health")
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\n[Execution Time Metric] GET /health: {duration_ms:.2f} ms")
        assert resp.status_code == 200
        assert duration_ms < 50.0  # Max acceptable SLA: 50ms

    def test_single_request_job_creation_execution_time(self, client):
        start = time.perf_counter()
        resp = client.post(
            "/api/v1/certificates/jobs",
            data=json.dumps(VALID_JOB_PAYLOAD),
            content_type="application/json",
        )
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\n[Execution Time Metric] POST /api/v1/certificates/jobs: {duration_ms:.2f} ms")
        assert resp.status_code == 202
        assert duration_ms < 250.0  # Max acceptable SLA: 250ms

    def test_single_request_job_status_execution_time(self, client):
        # Create a job first
        create_resp = client.post(
            "/api/v1/certificates/jobs",
            data=json.dumps(VALID_JOB_PAYLOAD),
            content_type="application/json",
        )
        job_id = create_resp.get_json()["job_id"]

        start = time.perf_counter()
        resp = client.get(f"/api/v1/certificates/jobs/{job_id}")
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\n[Execution Time Metric] GET /api/v1/certificates/jobs/{job_id}: {duration_ms:.2f} ms")
        assert resp.status_code == 200
        assert duration_ms < 100.0  # Max acceptable SLA: 100ms

    def test_single_request_pdf_rendering_execution_time(self, tmp_path):
        from app.services.certificate_generator import generate_certificate_pdf
        from datetime import date

        output = str(tmp_path / "single_metric_cert.pdf")
        start = time.perf_counter()
        generate_certificate_pdf(
            output_path=output,
            recipient_name="Performance Recipient",
            event_name="Metrics Certification",
            issued_by="API Performance Authority",
            course_name="System Optimization",
            grade="A+",
            event_date=date(2024, 6, 15),
            certificate_id="perf-single-001",
        )
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\n[Execution Time Metric] PDF Certificate Generation: {duration_ms:.2f} ms")
        assert os.path.exists(output)
        assert duration_ms < 150.0  # Max acceptable SLA: 150ms


class TestConcurrencyMetrics:
    """Metrics defining how many concurrent requests can be handled simultaneously."""

    def test_concurrent_read_requests_handling(self, app):
        """Measures concurrent handling capacity for read endpoints."""
        concurrency = 20
        total_requests = 40
        durations = []
        successes = 0

        def worker(idx):
            client = app.test_client()
            t0 = time.perf_counter()
            resp = client.get("/health")
            t1 = time.perf_counter()
            return resp.status_code == 200, (t1 - t0) * 1000

        wall_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(worker, i) for i in range(total_requests)]
            for f in as_completed(futures):
                ok, dur = f.result()
                if ok:
                    successes += 1
                durations.append(dur)

        wall_time = time.perf_counter() - wall_start
        rps = total_requests / wall_time
        avg_lat = statistics.mean(durations)
        p95_lat = sorted(durations)[int(len(durations) * 0.95)]

        print(f"\n[Concurrency Metric] Read Endpoint (Concurrency={concurrency}):")
        print(f"  • Requests Handled: {successes}/{total_requests} ({(successes/total_requests)*100:.1f}%)")
        print(f"  • Throughput:       {rps:.2f} req/sec")
        print(f"  • Avg Latency:      {avg_lat:.2f} ms | P95: {p95_lat:.2f} ms | Wall Clock: {wall_time:.4f} s")

        assert successes == total_requests
        assert rps > 30.0

    def test_concurrent_job_creation_handling(self, app):
        """Measures concurrent handling capacity for write / job creation requests."""
        concurrency = 10
        total_requests = 15
        durations = []
        successes = 0

        def worker(idx):
            client = app.test_client()
            payload = {
                **VALID_JOB_PAYLOAD,
                "title": f"Concurrent Load Job {idx}",
                "recipients": [
                    {
                        "full_name": f"Recipient {idx}_{k}",
                        "email": f"concurrent_rec_{idx}_{k}_{time.time_ns()}@test.com",
                    }
                    for k in range(2)
                ],
            }
            t0 = time.perf_counter()
            resp = client.post(
                "/api/v1/certificates/jobs",
                data=json.dumps(payload),
                content_type="application/json",
            )
            t1 = time.perf_counter()
            return resp.status_code == 202, (t1 - t0) * 1000

        wall_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(worker, i) for i in range(total_requests)]
            for f in as_completed(futures):
                ok, dur = f.result()
                if ok:
                    successes += 1
                durations.append(dur)

        wall_time = time.perf_counter() - wall_start
        rps = total_requests / wall_time
        avg_lat = statistics.mean(durations)

        print(f"\n[Concurrency Metric] Write Endpoint / Job Creation (Concurrency={concurrency}):")
        print(f"  • Requests Handled: {successes}/{total_requests} ({(successes/total_requests)*100:.1f}%)")
        print(f"  • Throughput:       {rps:.2f} req/sec")
        print(f"  • Avg Latency:      {avg_lat:.2f} ms | Wall Clock: {wall_time:.4f} s")

        assert successes == total_requests
        assert avg_lat < 500.0

