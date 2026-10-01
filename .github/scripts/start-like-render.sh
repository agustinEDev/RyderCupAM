#!/usr/bin/env bash
# Arranca la imagen como lo hace Render y espera a que /health responda con la
# versión esperada.
#
# El 1 oct 2026 la v2.23.0 no arrancó en Render con todo el CI en verde: el CI
# validaba Alembic en modo offline y arrancaba la app con `--entrypoint
# uvicorn`, siempre con URLs `+asyncpg`. Nadie ejecutaba el camino de Render —
# `entrypoint.sh` → `alembic upgrade head` contra una BD real con una
# DATABASE_URL SIN driver → uvicorn—, y con SQLAlchemy 2.1 ese camino cargaba
# psycopg (v3), que no está instalado (hotfix 2.23.1). Tampoco lo hacía el Kind.
#
# Aquí se usa el entrypoint de verdad y variables con la forma de las de
# Render: URL sin driver, entorno de producción y un DSN de Sentry (ficticio:
# los envíos fallan sin más, pero se ejecuta la inicialización, que es lo que
# tumbó la v2.18.0). El entorno de Sentry sale de ENVIRONMENT.
#
# Uso: start-like-render.sh <imagen> <database_url> <versión esperada>
#   <database_url> como la de Render: postgresql://usuario:clave@host:puerto/bd
# RED=host (el CI): el contenedor usa la red del runner y llega al Postgres
#   del job por localhost; uvicorn escucha en el 8000 del runner.
# Sin RED (en local, Docker Desktop): puerto publicado y host.docker.internal.
# Salidas: 0 arrancó y responde con la versión · 1 no arrancó o no responde
set -euo pipefail

imagen="${1:?Falta la imagen}"
database_url="${2:?Falta la DATABASE_URL}"
esperada="${3:?Falta la versión esperada}"
if [ "${RED:-}" = "host" ]; then
  red=(--network host)
  puerto=8000
else
  puerto="${PUERTO_RENDER:-8010}"
  red=(--add-host=host.docker.internal:host-gateway -p "$puerto:8000")
fi
espera_max="${ESPERA_MAX_S:-120}"
nombre="start-like-render-$$"

case "$database_url" in
  postgresql://*) ;;
  *) echo "::error::La URL debe ir sin driver, como la de Render (postgresql://…)"; exit 1 ;;
esac

limpiar() { docker rm -f "$nombre" > /dev/null 2>&1 || true; }
trap limpiar EXIT

docker run -d --name "$nombre" \
  "${red[@]}" \
  -e DATABASE_URL="$database_url" \
  -e SECRET_KEY="ci-start-like-render-not-a-real-secret-0123456789" \
  -e ENVIRONMENT=production \
  -e FRONTEND_ORIGINS="https://www.rydercupfriends.com" \
  -e SENTRY_DSN="https://public@o0.ingest.sentry.io/0" \
  -e PORT=8000 \
  "$imagen" > /dev/null

fin=$((SECONDS + espera_max))
while [ "$SECONDS" -lt "$fin" ]; do
  if [ "$(docker inspect -f '{{.State.Running}}' "$nombre" 2>/dev/null)" != "true" ]; then
    echo "::error::El contenedor se paró al arrancar, como en Render. Su log:"
    docker logs "$nombre" 2>&1 | tail -60
    exit 1
  fi
  if salud=$(curl -fsS --max-time 3 "http://localhost:$puerto/health" 2>/dev/null); then
    version=$(printf '%s' "$salud" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])' 2>/dev/null) || {
      echo "::error::/health respondió sin una versión legible: $salud"
      docker logs "$nombre" 2>&1 | tail -60
      exit 1
    }
    if [ "$version" != "$esperada" ]; then
      echo "::error::/health responde la versión $version y se esperaba $esperada"
      exit 1
    fi
    echo "✅ Arrancó como en Render (entrypoint, migraciones, uvicorn): /health da $version"
    exit 0
  fi
  sleep 2
done

echo "::error::/health no respondió en ${espera_max}s. Log del contenedor:"
docker logs "$nombre" 2>&1 | tail -60
exit 1
