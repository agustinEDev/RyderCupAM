#!/bin/bash
set -e

echo "🚀 Iniciando Ryder Cup Manager API..."

# =============================================================================
# VALIDACIÓN DE VARIABLES DE ENTORNO REQUERIDAS
# =============================================================================
echo "🔍 Validando variables de entorno requeridas..."

REQUIRED_VARS="POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB SECRET_KEY"
ALL_VALID=true

for VAR in $REQUIRED_VARS; do
    eval VALUE=\$$VAR
    if [ -z "$VALUE" ]; then
        echo "❌ ERROR: Variable requerida '$VAR' no está configurada"
        ALL_VALID=false
    elif echo "$VALUE" | grep -q "^MISSING_"; then
        echo "❌ ERROR: Variable '$VAR' tiene valor placeholder: $VALUE"
        ALL_VALID=false
    fi
done

if [ "$ALL_VALID" = false ]; then
    echo "❌ Validación fallida. Por favor configura el archivo .env correctamente."
    exit 1
fi

echo "✅ Variables de entorno validadas"

# =============================================================================
# ESPERAR A POSTGRESQL
# =============================================================================
# Esperar a que PostgreSQL esté listo (solo si DATABASE_HOST está configurado)
if [ -n "$DATABASE_HOST" ]; then
  echo "⏳ Esperando a que PostgreSQL esté disponible en $DATABASE_HOST:${DATABASE_PORT:-5432}..."
  timeout=60
  while ! nc -z ${DATABASE_HOST} ${DATABASE_PORT:-5432}; do
    timeout=$((timeout - 1))
    if [ $timeout -le 0 ]; then
      echo "❌ Error: PostgreSQL no respondió a tiempo"
      exit 1
    fi
    sleep 1
  done
  echo "✅ PostgreSQL está disponible"
else
  echo "ℹ️  DATABASE_HOST no configurado, asumiendo base de datos externa ya disponible"
fi

# =============================================================================
# EJECUTAR MIGRACIONES DE ALEMBIC
# =============================================================================
echo "🔄 Ejecutando migraciones de base de datos..."
if alembic upgrade head; then
  echo "✅ Migraciones completadas exitosamente"
else
  echo "❌ Error al ejecutar migraciones"
  exit 1
fi

# =============================================================================
# INICIAR APLICACIÓN FASTAPI
# =============================================================================
echo "🎯 Iniciando aplicación FastAPI en puerto ${PORT:-8000}..."

# Usar --reload solo en desarrollo para hot-reload de código
if [ "$ENVIRONMENT" = "development" ]; then
  echo "🔧 Modo DESARROLLO: hot-reload habilitado"
  exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --reload
else
  echo "🚀 Modo PRODUCCIÓN: sin hot-reload"
  exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
fi
