"""
Application Configuration
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _fix_db_url(url: str) -> str:
    """Force psycopg2 dialect: replace postgresql:// with postgresql+psycopg2://"""
    if url and url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url or ""


class BaseConfig:
    """Base configuration shared across all environments."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
    }

    # Celery
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # Certificate output directory
    CERTIFICATES_DIR = os.getenv("CERTIFICATES_DIR", str(BASE_DIR / "generated_certificates"))

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # Max recipients per job
    MAX_RECIPIENTS_PER_JOB = 1000


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.getenv("DATABASE_URL", "postgresql+psycopg2://certuser:certpassword@localhost:5432/certdb")
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.getenv("DATABASE_URL", "postgresql+psycopg2://certuser:certpassword@localhost:5432/certdb")
    )


class TestingConfig(BaseConfig):
    TESTING = True
    _test_db = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_DATABASE_URI = _fix_db_url(_test_db)
    if "sqlite" in _test_db:
        from sqlalchemy.pool import StaticPool
        SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {}
    CELERY_TASK_ALWAYS_EAGER = True  # Run tasks synchronously in tests


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
