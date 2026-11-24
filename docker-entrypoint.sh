#!/bin/sh
# docker-entrypoint.sh
# Punto de entrada unificado para el contenedor ERP Django.
# Se ejecuta en LOCAL (docker-compose) y en PRODUCCIÓN (Render).
# IMPORTANTE: este archivo debe tener finales de línea LF.
# ─────────────────────────────────────────────────────────────────
set -e   # detener si cualquier comando falla

# ── W16: si se recibe un comando, ejecutarlo tal cual ────────────────
if [ "$#" -gt 0 ]; then
    echo "==> [entrypoint] Ejecutando comando: $*"
    exec "$@"
fi

echo "==> [entrypoint] Ejecutando migraciones de base de datos..."
python manage.py migrate --noinput

echo "==> [entrypoint] Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear

echo "==> [entrypoint] Verificando la configuración de Django..."
python manage.py check --deploy 2>/dev/null || python manage.py check

# ── W16/W18: worker de Celery embebido (+ Beat opcional) ─────────────
if [ "${CELERY_EMBEDDED_WORKER:-0}" = "1" ] && [ -n "${REDIS_URL:-}" ]; then
    BEAT_FLAG=""
    if [ "${CELERY_EMBEDDED_BEAT:-0}" = "1" ]; then
        BEAT_FLAG="-B --schedule=/tmp/celerybeat-schedule"
    fi
    echo "==> [entrypoint] Iniciando worker de Celery embebido (cola erp_django) ${BEAT_FLAG}..."
    celery -A core worker $BEAT_FLAG \
        --loglevel=info \
        --queues=erp_django \
        --pool=solo \
        --without-gossip --without-mingle --without-heartbeat &
else
    echo "==> [entrypoint] Worker de Celery embebido DESACTIVADO."
fi

exec gunicorn core.wsgi \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --timeout 120 \
    --log-file - \
    --access-logfile -