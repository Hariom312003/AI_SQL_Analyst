#!/bin/sh
# Runs database migrations before starting the API server. Idempotent --
# alembic tracks applied revisions in alembic_version, so this is safe to
# run on every container start (fresh DB: creates all tables; existing DB
# already at head: no-op).
set -e

echo "Waiting for Postgres to accept connections..."
python3 -c "
import time
import sqlalchemy
from backend.config import get_settings

settings = get_settings()
engine = sqlalchemy.create_engine(settings.sync_database_url)
for attempt in range(30):
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text('SELECT 1'))
        print('Postgres is ready.')
        break
    except Exception as exc:
        print(f'Attempt {attempt + 1}/30: Postgres not ready yet ({exc}); retrying...')
        time.sleep(2)
else:
    raise SystemExit('Postgres never became ready.')
"

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
exec uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
