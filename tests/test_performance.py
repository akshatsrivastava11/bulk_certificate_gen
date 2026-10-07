"""
Performance, Execution Time, and Concurrency Load Tests.

This test module measures and asserts:
1. Single request execution time / latency (in milliseconds) across all API endpoints and PDF rendering.
2. Concurrent request capacity: how many concurrent requests can be handled simultaneously,
   measuring throughput (requests/sec), latency percentiles (P50, P90, P95, P99), and success rates.

Run with:
    pytest tests/test_performance.py -v -s
"""
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any
import pytest

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")


@dataclass
class RequestMetric:
    """Metric recording execution details for a single request."""
    endpoint: str
    status_code: int
    duration_ms: float
    success: bool
    error: str = ""


@dataclass
class ConcurrencyMetricResult:
    """Aggregated metric defining concurrent request handling capacity."""
    concurrency_level: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate_pct: float
    total_duration_s: float
    requests_per_second: float
    min_latency_ms: float
    max_latency_ms: float
    avg_latency_ms: float
    median_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    metrics: List[RequestMetric] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"\n{'='*60}\n"
            f"  CONCURRENCY PERFORMANCE REPORT (Workers={self.concurrency_level})\n"
            f"{'='*60}\n"
            f"  • Total Requests Sent:         {self.total_requests}\n"
            f"  • Successful Requests Handled: {self.successful_requests} ({self.success_rate_pct:.1f}%)\n"
            f"  • Failed Requests:             {self.failed_requests}\n"
            f"  • Total Elapsed Time:          {self.total_duration_s:.4f} s\n"
            f"  • Throughput (Capacity):       {self.requests_per_second:.2f} req/sec\n"
            f"  • Single Request Latency:\n"
            f"      - Min Latency:             {self.min_latency_ms:.2f} ms\n"
            f"      - Avg Latency:             {self.avg_latency_ms:.2f} ms\n"
            f"      - Median (P50):            {self.median_latency_ms:.2f} ms\n"
            f"      - P90 Latency:             {self.p90_latency_ms:.2f} ms\n"
            f"      - P95 Latency:             {self.p95_latency_ms:.2f} ms\n"
            f"      - P99 Latency:             {self.p99_latency_ms:.2f} ms\n"
            f"      - Max Latency:             {self.max_latency_ms:.2f} ms\n"
            f"{'='*60}\n"
        )


def compute_concurrency_metrics(
    concurrency_level: int,
    metrics: List[RequestMetric],
    total_duration_s: float,
) -> ConcurrencyMetricResult:
    """Calculates all key metrics for concurrent execution load."""
    total = len(metrics)
    successful = sum(1 for m in metrics if m.success)
    failed = total - successful
    success_rate = (successful / total * 100.0) if total > 0 else 0.0
    rps = (total / total_duration_s) if total_duration_s > 0 else 0.0

    durations = [m.duration_ms for m in metrics] if metrics else [0.0]
    durations_sorted = sorted(durations)

    def percentile(p: float) -> float:
        if not durations_sorted:
            return 0.0
        k = (len(durations_sorted) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(durations_sorted) - 1)
        d = k - f
        return durations_sorted[f] + d * (durations_sorted[c] - durations_sorted[f])

    return ConcurrencyMetricResult(
        concurrency_level=concurrency_level,
        total_requests=total,
        successful_requests=successful,
        failed_requests=failed,
        success_rate_pct=round(success_rate, 2),
        total_duration_s=round(total_duration_s, 4),
        requests_per_second=round(rps, 2),
        min_latency_ms=round(min(durations), 2),
        max_latency_ms=round(max(durations), 2),
        avg_latency_ms=round(statistics.mean(durations), 2),
        median_latency_ms=round(statistics.median(durations), 2),
        p90_latency_ms=round(percentile(90), 2),
        p95_latency_ms=round(percentile(95), 2),
        p99_latency_ms=round(percentile(99), 2),
        metrics=metrics,
    )


@pytest.fixture(scope="session")
def app():
    """Create application for performance tests."""
    from app import create_app, db
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


SAMPLE_PAYLOAD = {
    "title": "Performance Test Bootcamp",
    "description": "Load benchmark certificate batch",
    "event_name": "Tech Summit 2024",
    "event_date": "2024-06-15",
    "issued_by": "Performance Benchmark Org",
    "recipients": [
        {
            "full_name": f"Recipient {i}",
            "email": f"bench_user_{i}@example.com",
            "course_name": "Distributed Systems",
            "grade": "A+",
        }
        for i in range(5)
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Single Request Execution Time Tests & Metrics
# ─────────────────────────────────────────────────────────────────────────────

class TestSingleRequestExecutionTime:
    """Measures and validates execution time for single requests."""

    def test_health_check_execution_time(self, client):
        """Measures execution time of the /health endpoint."""
        start = time.perf_counter()
        resp = client.get("/health")
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\n[Metric] Single Request Execution Time (GET /health): {duration_ms:.2f} ms")
        assert resp.status_code == 200
        # Single health check request should execute well within 50ms
        assert duration_ms < 50.0, f"Health check too slow: {duration_ms:.2f} ms"

    def test_job_creation_execution_time(self, client):
        """Measures execution time of POST /api/v1/certificates/jobs."""
        start = time.perf_counter()
        resp = client.post(
            "/api/v1/certificates/jobs",
            data=json.dumps(SAMPLE_PAYLOAD),
            content_type="application/json",
        )
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\n[Metric] Single Request Execution Time (POST /api/v1/certificates/jobs): {duration_ms:.2f} ms")
        assert resp.status_code == 202
        data = resp.get_json()
        assert "job_id" in data
        # Job creation should complete under 250ms
        assert duration_ms < 250.0, f"Job creation took too long: {duration_ms:.2f} ms"

    def test_job_status_retrieval_execution_time(self, client):
        """Measures execution time of GET /api/v1/certificates/jobs/<id>."""
        # Create job
        resp = client.post(
            "/api/v1/certificates/jobs",
            data=json.dumps(SAMPLE_PAYLOAD),
            content_type="application/json",
        )
        job_id = resp.get_json()["job_id"]

        # Measure status fetch time
        start = time.perf_counter()
        get_resp = client.get(f"/api/v1/certificates/jobs/{job_id}")
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\n[Metric] Single Request Execution Time (GET /api/v1/certificates/jobs/{job_id}): {duration_ms:.2f} ms")
        assert get_resp.status_code == 200
        assert duration_ms < 100.0, f"Status retrieval too slow: {duration_ms:.2f} ms"

    def test_pdf_generation_single_execution_time(self, tmp_path):
        """Measures raw execution time for generating a single PDF certificate."""
        from app.services.certificate_generator import generate_certificate_pdf
        from datetime import date

        output = str(tmp_path / "bench_cert.pdf")
        start = time.perf_counter()
        generate_certificate_pdf(
            output_path=output,
            recipient_name="Performance Test Subject",
            event_name="High Scale Engineering",
            issued_by="Benchmarking Authority",
            course_name="System Latency & Optimization",
            grade="A+",
            event_date=date(2024, 6, 15),
            certificate_id="perf-001",
        )
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\n[Metric] Single PDF Certificate Render Time: {duration_ms:.2f} ms")
        assert os.path.exists(output)
        assert duration_ms < 150.0, f"PDF generation took too long: {duration_ms:.2f} ms"

    def test_single_request_latency_distribution(self, client):
        """Collects execution time statistics across 30 sequential single requests."""
        durations = []
        for _ in range(30):
            t0 = time.perf_counter()
            resp = client.get("/health")
            t1 = time.perf_counter()
            assert resp.status_code == 200
            durations.append((t1 - t0) * 1000)

        avg_lat = statistics.mean(durations)
        min_lat = min(durations)
        max_lat = max(durations)
        p95_lat = sorted(durations)[int(len(durations) * 0.95)]

        print(f"\n[Metric] Single Request Latency Distribution (30 runs):")
        print(f"         Min: {min_lat:.2f} ms | Avg: {avg_lat:.2f} ms | P95: {p95_lat:.2f} ms | Max: {max_lat:.2f} ms")
        assert avg_lat < 20.0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Concurrent Request Capacity Tests & Metrics
# ─────────────────────────────────────────────────────────────────────────────

class TestConcurrentRequestsCapacity:
    """Measures and validates how many concurrent requests can be handled simultaneously."""

    def _execute_concurrently(
        self,
        app,
        req_fn: Callable[[Any, int], RequestMetric],
        total_requests: int,
        concurrency: int,
    ) -> ConcurrencyMetricResult:
        """Helper to run req_fn across concurrency threads using app.test_client()."""
        metrics: List[RequestMetric] = []
        t0 = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = []
            for i in range(total_requests):
                # Each thread creates its own test client from the shared app
                client = app.test_client()
                futures.append(executor.submit(req_fn, client, i))

            for future in as_completed(futures):
                try:
                    res = future.result()
                    metrics.append(res)
                except Exception as ex:
                    metrics.append(
                        RequestMetric(
                            endpoint="unknown",
                            status_code=500,
                            duration_ms=0.0,
                            success=False,
                            error=str(ex),
                        )
                    )

        total_duration = time.perf_counter() - t0
        return compute_concurrency_metrics(concurrency, metrics, total_duration)

    def test_concurrent_health_checks_capacity(self, app):
        """Tests handling of 50 concurrent health check requests."""
        def call_health(client, index: int) -> RequestMetric:
            t0 = time.perf_counter()
            resp = client.get("/health")
            dur = (time.perf_counter() - t0) * 1000
            return RequestMetric(
                endpoint="/health",
                status_code=resp.status_code,
                duration_ms=dur,
                success=(resp.status_code == 200),
            )

        concurrency = 25
        total_requests = 50
        result = self._execute_concurrently(app, call_health, total_requests, concurrency)
        print(result.summary())

        # Assert all concurrent requests are handled successfully (100% capacity)
        assert result.successful_requests == total_requests
        assert result.failed_requests == 0
        assert result.success_rate_pct == 100.0
        # High throughput capacity
        assert result.requests_per_second > 50.0

    def test_concurrent_job_creation_capacity(self, app):
        """Tests handling of concurrent job submission requests."""
        def call_create_job(client, index: int) -> RequestMetric:
            payload = {
                **SAMPLE_PAYLOAD,
                "title": f"Concurrent Job {index}",
                "recipients": [
                    {
                        "full_name": f"User {index}_{j}",
                        "email": f"concur_{index}_{j}_{time.time_ns()}@test.com",
                        "course_name": "Concurrency Testing",
                    }
                    for j in range(2)
                ],
            }
            t0 = time.perf_counter()
            resp = client.post(
                "/api/v1/certificates/jobs",
                data=json.dumps(payload),
                content_type="application/json",
            )
            dur = (time.perf_counter() - t0) * 1000
            return RequestMetric(
                endpoint="/api/v1/certificates/jobs",
                status_code=resp.status_code,
                duration_ms=dur,
                success=(resp.status_code == 202),
            )

        concurrency = 10
        total_requests = 20
        result = self._execute_concurrently(app, call_create_job, total_requests, concurrency)
        print(result.summary())

        assert result.successful_requests == total_requests
        assert result.failed_requests == 0
        assert result.success_rate_pct == 100.0
        assert result.avg_latency_ms < 500.0

    def test_concurrency_scaling_benchmark(self, app):
        """
        Benchmarks system capacity across multiple concurrency tiers:
        5, 10, 20 concurrent requests.
        """
        def call_get_jobs(client, index: int) -> RequestMetric:
            t0 = time.perf_counter()
            resp = client.get("/api/v1/certificates/jobs")
            dur = (time.perf_counter() - t0) * 1000
            return RequestMetric(
                endpoint="/api/v1/certificates/jobs",
                status_code=resp.status_code,
                duration_ms=dur,
                success=(resp.status_code == 200),
            )

        concurrency_levels = [5, 10, 20]
        results = []

        for c_level in concurrency_levels:
            total_reqs = c_level * 3
            res = self._execute_concurrently(app, call_get_jobs, total_reqs, c_level)
            results.append(res)
            print(f"\n[Tier Concurrency={c_level:2d}] Handled: {res.successful_requests}/{res.total_requests} "
                  f"| Throughput: {res.requests_per_second:6.2f} req/s | Avg Latency: {res.avg_latency_ms:6.2f} ms")

        # Verify all tiers maintained 100% success rate
        for res in results:
            assert res.success_rate_pct == 100.0
            assert res.successful_requests == res.total_requests
