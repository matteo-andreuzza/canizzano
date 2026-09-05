# ── Stage 1: dipendenze ────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ───────────────────────────────────────────────────────
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=canizzano_cms.settings

# gosu serve all'entrypoint per lasciare i privilegi di root dopo aver
# sistemato i permessi del volume dei media.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# L'utente che serve le pagine ha lo stesso uid di chi possiede la cartella
# del progetto sull'host. Serve ai bind mount ./coda e ./logs, condivisi col
# container «esecutore»: con uid diversi uno dei due non riuscirebbe a
# scrivere, e i bottoni della dashboard resterebbero senza effetto.
ARG UID_APP=1000
ARG GID_APP=1000
RUN groupadd -g "$GID_APP" appuser 2>/dev/null || true \
    && useradd -m -u "$UID_APP" -g "$GID_APP" appuser \
    && mkdir -p /app /app/media /app/staticfiles /app/coda /app/logs

COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

WORKDIR /app
COPY --chown=appuser:appuser . .

RUN chmod +x /app/entrypoint.sh && chown -R appuser:appuser /app

# Niente «USER appuser» qui: l'entrypoint parte da root, aggiusta il volume
# dei media e poi si rilancia da solo come appuser. Il processo che serve le
# pagine non gira mai con i privilegi di root.
EXPOSE 8000

CMD ["/app/entrypoint.sh"]
