# Bulk Certificate Generation API

A high-performance, asynchronous REST API for bulk PDF certificate generation built with **Python**, **Flask**, **PostgreSQL**, **Celery**, and **Redis** — fully containerized with Docker Compose.

---

## 📌 Project Overview

This backend system accepts bulk certificate generation requests for large recipient lists, validates inputs, renders custom vector PDF certificates asynchronously via distributed background workers, tracks job progress in real time, and provides endpoints to stream or batch-download generated certificates.

### 🌟 Key System Capabilities
- ⚡ **Asynchronous Task Queue & Fan-Out**: Celery chord architecture dispatches certificate generation tasks in parallel across worker nodes, preventing HTTP timeouts.
- 🎯 **Sub-Millisecond Execution & High Concurrency**: Tested to handle **~3,000 requests/second** with $<1\text{ ms}$ average latency for read endpoints and **100% success rate** under concurrent write loads.
- 📜 **Dynamic Vector PDF Rendering**: High-fidelity, print-ready A4 landscape certificates generated via ReportLab with ornamental seals and styling.
- 🛡️ **Strict Schema Validation**: Marshmallow validation for payload completeness, email deduplication, and bounds checking.
- 📊 **Real-Time Progress & Observability**: Granular job status tracking, percentage completion, health/readiness probes, and Celery Flower dashboard integration.
- 📦 **100% Containerized**: Single-command startup with orchestrated Docker Compose services (Flask API, Celery Worker, PostgreSQL, Redis, Flower).

---

## 🏗️ System Architecture

```
                                +-----------------------------------------------+
                                |               DOCKER COMPOSE                  |
                                |                                               |
  Client / HTTP Traffic ------> |  [Flask API Server] (:5000)                   |
                                |     │             │                           |
                                |     │ (Writes     │ (Enqueues Job             |
                                |     │  Job & Rec) │  Task with UUID)          |
                                |     ▼             ▼                           |
                                |  [PostgreSQL]   [Redis Broker / Backend]      |
                                |    (:5432)        (:6379)                     |
                                |     ▲             ▲                           |
                                |     │ (Updates    │ (Pulls Tasks &            |
                                |     │  Status)    │  Fanned Chords)           |
                                |     │             │                           |
                                |  [Celery Worker Cluster] (ReportLab Engine)   |
                                |     │                                         |
                                |     ▼                                         |
                                |  [Generated Certificates Volume]              |
                                |                                               |
                                |  [Flower Dashboard] (:5555) ◄─ (Queue Monitor)|
                                +-----------------------------------------------+
```

---

## 📊 Performance & Concurrency Benchmark Logs

The test suite includes dedicated load testing and latency instrumentation (`tests/test_performance.py` and `tests/test_api.py`) executed using `time.perf_counter()` and `concurrent.futures.ThreadPoolExecutor`.

### 1. Single Request Execution Time (Latency)
```text
============================= test session starts ==============================
tests/test_performance.py::TestSingleRequestExecutionTime::test_health_check_execution_time 
[Metric] Single Request Execution Time (GET /health): 1.27 ms
PASSED

tests/test_performance.py::TestSingleRequestExecutionTime::test_job_creation_execution_time 
[Metric] Single Request Execution Time (POST /api/v1/certificates/jobs): 37.90 ms
PASSED

tests/test_performance.py::TestSingleRequestExecutionTime::test_job_status_retrieval_execution_time 
[Metric] Single Request Execution Time (GET /api/v1/certificates/jobs/<job_id>): 1.86 ms
PASSED

tests/test_performance.py::TestSingleRequestExecutionTime::test_pdf_generation_single_execution_time 
[Metric] Single PDF Certificate Render Time: 2.72 ms
PASSED

tests/test_performance.py::TestSingleRequestExecutionTime::test_single_request_latency_distribution 
[Metric] Single Request Latency Distribution (30 sequential runs):
         Min: 0.14 ms | Avg: 0.17 ms | P95: 0.27 ms | Max: 0.31 ms
PASSED
```

### 2. High-Concurrency Stress & Capacity Report
```text
============================================================
  CONCURRENCY PERFORMANCE REPORT (Workers=25)
============================================================
  • Total Requests Sent:         50
  • Successful Requests Handled: 50 (100.0%)
  • Failed Requests:             0
  • Total Elapsed Time:          0.0169 s
  • Throughput (Capacity):       2951.10 req/sec
  • Single Request Latency:
      - Min Latency:             0.15 ms
      - Avg Latency:             0.23 ms
      - Median (P50):            0.18 ms
      - P90 Latency:             0.37 ms
      - P95 Latency:             0.44 ms
      - P99 Latency:             0.59 ms
      - Max Latency:             0.72 ms
============================================================
PASSED

============================================================
  CONCURRENCY PERFORMANCE REPORT (Workers=10 Write/Creation)
============================================================
  • Total Requests Sent:         20
  • Successful Requests Handled: 20 (100.0%)
  • Failed Requests:             0
  • Total Elapsed Time:          0.1488 s
  • Throughput (Capacity):       134.37 req/sec
  • Single Request Latency:
      - Min Latency:             5.92 ms
      - Avg Latency:             64.69 ms
      - Median (P50):            33.30 ms
      - P90 Latency:             132.61 ms
      - P95 Latency:             133.03 ms
      - P99 Latency:             136.66 ms
      - Max Latency:             137.56 ms
============================================================
PASSED
```

### 3. Concurrency Tier Scaling Benchmark
```text
[Tier Concurrency= 5] Handled: 15/15 | Throughput: 431.28 req/s | Avg Latency:   9.93 ms
[Tier Concurrency=10] Handled: 30/30 | Throughput: 233.39 req/s | Avg Latency:  37.26 ms
[Tier Concurrency=20] Handled: 60/60 | Throughput: 329.10 req/s | Avg Latency:  51.35 ms
PASSED

============================== 8 passed in 0.94s ===============================
```

---

## 🚀 Quick Start & Container Setup

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (v20+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.x)

### 1. Clone & Configure
```bash
git clone https://github.com/akshatsrivastava11/bulk_certificate_gen.git
cd bulk_certificate_gen
cp .env.example .env
```

### 2. Start Services
```bash
docker-compose up -d --build
```

### 3. Verify Health
```bash
curl -s http://localhost:5000/health | jq
# { "status": "ok" }

curl -s http://localhost:5000/health/ready | jq
# { "status": "ok", "checks": { "database": "ok" } }
```

### 4. Monitor Distributed Workers (Flower UI)
Open [http://localhost:5555](http://localhost:5555) in your browser to view active workers, task success rates, and latency queues.

---

## 📖 API Documentation & Usage

**Base URL**: `http://localhost:5000/api/v1`

### 1. Create a Bulk Certificate Job
**Endpoint**: `POST /certificates/jobs`

```bash
curl -X POST http://localhost:5000/api/v1/certificates/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Python Developer Bootcamp 2024",
    "description": "Graduation certification batch",
    "event_name": "Developer Summit",
    "event_date": "2024-06-15",
    "issued_by": "Global Tech Institute",
    "recipients": [
      {
        "full_name": "Alice Johnson",
        "email": "alice@example.com",
        "course_name": "Advanced Backend Engineering",
        "grade": "A+"
      },
      {
        "full_name": "Bob Smith",
        "email": "bob@example.com",
        "course_name": "Advanced Backend Engineering",
        "grade": "A"
      }
    ]
  }'
```

**Response (`202 Accepted`):**
```json
{
  "message": "Certificate generation job accepted.",
  "job_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "total_recipients": 2,
  "status": "pending",
  "status_url": "/api/v1/jobs/a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"
}
```

---

### 2. Track Job Progress
**Endpoint**: `GET /jobs/<job_id>` or `GET /certificates/jobs/<job_id>`

```bash
curl http://localhost:5000/api/v1/jobs/a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
```

**Response (`200 OK`):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "title": "Python Developer Bootcamp 2024",
  "status": "completed",
  "total_recipients": 2,
  "completed_count": 2,
  "failed_count": 0,
  "progress_pct": 100.0,
  "created_at": "2026-10-07T07:00:00Z",
  "updated_at": "2026-10-07T07:00:02Z",
  "completed_at": "2026-10-07T07:00:02Z"
}
```

---

### 3. List All Jobs (with Pagination & Filters)
**Endpoint**: `GET /certificates/jobs?status=completed&page=1&per_page=10`

```bash
curl "http://localhost:5000/api/v1/certificates/jobs?status=completed&page=1&per_page=10"
```

---

### 4. Download Single Recipient Certificate
**Endpoint**: `GET /certificates/jobs/<job_id>/recipients/<recipient_id>/download`

```bash
curl -O -J "http://localhost:5000/api/v1/certificates/jobs/<job_id>/recipients/<recipient_id>/download"
```

---

### 5. Download All Certificates as ZIP
**Endpoint**: `GET /certificates/jobs/<job_id>/download-all`

```bash
curl -O -J "http://localhost:5000/api/v1/certificates/jobs/<job_id>/download-all"
```

---

## 🧪 Running Automated Tests & Benchmarks

All tests can be executed directly inside the Docker container or locally:

```bash
# Run full test suite (29 tests: Unit, Integration, Execution Time & Concurrency)
docker exec cert_api pytest tests/ -v -s

# Run dedicated performance and load benchmark tests
docker exec cert_api pytest tests/test_performance.py -v -s
```

---

## 💡 Interview & System Design Insights

### Q1: Why use an Asynchronous Task Queue (Celery + Redis) instead of synchronous generation?
- **Decoupling & Non-Blocking**: Generating hundreds or thousands of high-resolution PDF certificates requires significant CPU and memory. Processing them synchronously in an HTTP request would cause client timeouts (e.g. 504 Gateway Timeout) and tie up Web server worker threads (gunicorn/Flask).
- **Scalability**: By placing tasks on a Redis message broker, Celery workers can be scaled horizontally (`docker-compose up -d --scale worker=4`) across multiple containers or servers without touching the API layer.

### Q2: How does the Fan-Out / Chord pattern work in this system?
- The main orchestrator task (`process_certificate_job`) reads all pending recipients for a job and fans out individual lightweight tasks (`generate_single_certificate`) using Celery's `chord`.
- Once all recipient tasks finish rendering PDFs, Celery automatically fires the `finalize_job` callback, atomically updating the job status to `completed`, recording the timestamp, and logging final metrics.

### Q3: How is database concurrency and thread-safety ensured?
- **Connection Pooling**: Uses SQLAlchemy engine options with `pool_pre_ping=True`, `pool_recycle=300`, `pool_size=10`, and `max_overflow=20` to prevent connection leaks under burst traffic.
- **Atomic Commits**: Jobs and recipients are assigned UUIDs before dispatch, committing once to avoid lock contention or stale session state during high concurrent loads.

---

## 📁 Repository Structure

```
bulk_certificate_gen/
├── app/
│   ├── __init__.py                # Flask application factory & Celery init
│   ├── config.py                  # Environment-specific configuration
│   ├── models/
│   │   └── __init__.py            # CertificateJob & Recipient SQLAlchemy models
│   ├── routes/
│   │   ├── certificates.py        # Job creation, listing & download routes
│   │   ├── jobs.py                # Quick status check endpoint
│   │   └── health.py              # Liveness & readiness probes
│   ├── schemas/
│   │   └── __init__.py            # Marshmallow validation schemas
│   ├── services/
│   │   ├── certificate_generator.py # ReportLab vector PDF generator
│   │   └── tasks.py               # Celery async worker tasks & chords
│   └── utils/
│       └── init_db.py             # DB table creation utility
├── tests/
│   ├── test_api.py                # Comprehensive API & integration tests
│   └── test_performance.py        # Performance latency & concurrency load tests
├── docker-compose.yml             # Orchestration for API, Worker, DB, Redis, Flower
├── Dockerfile                     # Container definition
├── docker-entrypoint.sh           # DB readiness check & service startup
├── requirements.txt               # Dependencies
├── .env.example                   # Configuration template
└── README.md                      # Documentation & interview guide
```

---

## 📜 License
This project is open-source and available under the [MIT License](LICENSE).
