#!/usr/bin/env python3
"""
Database initialization script.
Run inside the container or locally to create tables.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db

app = create_app(os.getenv("FLASK_ENV", "development"))

with app.app_context():
    db.create_all()
    print("✅ All database tables created successfully.")
