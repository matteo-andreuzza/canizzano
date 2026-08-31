#!/usr/bin/env bash
# Avvio del CMS: attende il database, allinea lo schema, prepara la redazione.
set -euo pipefail

echo "→ attendo PostgreSQL su ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}…"
python - <<'PY'
import os, sys, time
import psycopg

dsn = (
    f"host={os.environ.get('POSTGRES_HOST', 'db')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"dbname={os.environ.get('POSTGRES_DB', 'canizzano')} "
    f"user={os.environ.get('POSTGRES_USER', 'canizzano')} "
    f"password={os.environ.get('POSTGRES_PASSWORD', '')}"
)
for tentativo in range(60):
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            sys.exit(0)
    except Exception:
        time.sleep(1)
print("PostgreSQL non raggiungibile dopo 60 tentativi.", file=sys.stderr)
sys.exit(1)
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py crea_admin

if [ "${CARICA_DATI_ESEMPIO:-false}" = "true" ]; then
    python manage.py dati_esempio
fi

echo "→ CMS pronto su http://localhost:${CMS_PORT:-8000}/admin/"
exec python -m gunicorn --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-3}" \
     --access-logfile - canizzano_cms.wsgi:application
