# ==========================================
# DOCKERFILE - Solo aplicación FastAPI
# ==========================================
# Este Dockerfile funciona para:
# - Desarrollo local (con docker-compose.yml que incluye PostgreSQL)
# - Producción en Render/Railway (con base de datos externa)
# ==========================================

# 1. Imagen base: Python ligera
FROM python:3.11-slim

# 2. Instalar dependencias del sistema
# netcat-openbsd: Para verificar conexión con PostgreSQL (opcional en producción)
# postgresql-client: Para herramientas CLI de postgres si es necesario
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 3. Directorio de trabajo
WORKDIR /app

# 4. Copiar e instalar dependencias de Python
# (aprovecha cache de Docker si requirements.txt no cambia)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar código de la aplicación
COPY . .

# 6. Copiar y configurar script de inicio
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 7. Exponer puerto (configurable con ENV PORT)
EXPOSE 8000

# 8. Ejecutar script de inicio
# Este script maneja:
# - Espera a PostgreSQL (solo si DATABASE_HOST está configurado)
# - Ejecuta migraciones con Alembic
# - Inicia la aplicación FastAPI
ENTRYPOINT ["/entrypoint.sh"]