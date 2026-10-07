#!/bin/bash
# ============================================================
# Entrypoint script for API and Worker containers
# Waits for Postgres, runs DB migration, then starts the service
# ============================================================
set -e

echo "⏳ Waiting for PostgreSQL..."
until python3 -c "
import psycopg2, os, sys
url = os.environ.get('DATABASE_URL', '')
try:
    conn = psycopg2.connect(dsn=url)
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f'  DB not ready: {e}', flush=True)
    sys.exit(1)
"; do
    echo "   PostgreSQL not ready yet, retrying in 2s..."
    sleep 2
done
echo "✅ PostgreSQL is ready."

echo "🔧 Running database migrations..."
python3 -c "
import os
from app import create_app, db
app = create_app(os.getenv('FLASK_ENV', 'production'))
with app.app_context():
    db.create_all()
    print('✅ DB tables created/verified.')
"

echo "🚀 Starting service: $@"
exec "$@"
