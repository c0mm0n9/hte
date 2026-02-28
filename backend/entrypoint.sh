#!/bin/sh
# Create PostgreSQL database if it does not exist (RDS only creates "postgres" by default), then migrate and run app.
set -e
if [ -n "$POSTGRES_HOST" ]; then
  db_name="${POSTGRES_DB:-hte}"
  echo "Ensuring database $db_name exists..."
  python -c "
import os
import re
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

db_name = (os.environ.get('POSTGRES_DB') or 'hte').strip()
if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', db_name):
    print('Invalid POSTGRES_DB', repr(db_name), file=sys.stderr)
    sys.exit(1)
try:
    conn = psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
        user=os.environ.get('POSTGRES_USER', 'postgres'),
        password=os.environ.get('POSTGRES_PASSWORD', ''),
        dbname='postgres',
        connect_timeout=10,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', (db_name,))
    if cur.fetchone() is None:
        cur.execute('CREATE DATABASE ' + db_name)
        print('Created database', db_name)
    else:
        print('Database', db_name, 'already exists')
    conn.close()
except Exception as e:
    print('Could not ensure database:', e, file=sys.stderr)
    sys.exit(1)
"
  python manage.py migrate --noinput
fi
exec "$@"
