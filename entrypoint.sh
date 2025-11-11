#!/bin/bash
set -e

echo "🚀 Iniciando Ryder Cup Manager API..."

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

# Ejecutar migraciones de Alembic
echo "🔄 Ejecutando migraciones de base de datos..."
if alembic upgrade head; then
  echo "✅ Migraciones completadas exitosamente"
else
  echo "❌ Error al ejecutar migraciones"
  exit 1
fi

# Iniciar la aplicación
echo "🎯 Iniciando aplicación FastAPI en puerto ${PORT:-8000}..."
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
