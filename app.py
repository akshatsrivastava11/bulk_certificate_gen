"""
Application entry point.
"""
import os
from app import create_app, db
from app.models import CertificateJob, Recipient

app = create_app(os.getenv("FLASK_ENV", "development"))


@app.shell_context_processor
def make_shell_context():
    """Expose models in `flask shell`."""
    return {"db": db, "CertificateJob": CertificateJob, "Recipient": Recipient}


@app.cli.command("init-db")
def init_db():
    """Create all database tables."""
    with app.app_context():
        db.create_all()
        print("✅ Database tables created.")


@app.cli.command("seed-db")
def seed_db():
    """Insert sample data for development/testing."""
    import json
    from datetime import date
    sample = CertificateJob(
        title="Sample Training Program",
        event_name="Annual Developer Bootcamp 2024",
        event_date=date(2024, 6, 15),
        issued_by="Acme Corp Learning",
        total_recipients=2,
    )
    db.session.add(sample)
    db.session.commit()
    print(f"✅ Seeded sample job: {sample.id}")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
