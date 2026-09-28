# ==========================================
# DOCKERFILE - Solo aplicación FastAPI
# ==========================================
# Este Dockerfile funciona para:
# - Desarrollo local (con docker-compose.yml que incluye PostgreSQL)
# - Producción en Render/Railway (con base de datos externa)
# ==========================================

# 1. Imagen base: Python ligera
# Actualizado a 3.12-slim para resolver CVE-2026-42496 (CRITICAL) y CVE-2026-42497, CVE-2026-9538 (HIGH)
# en paquetes del OS base de la imagen debian 3.11-slim
# Fijada por digest (28 sep 2026): con la etiqueta flotante, un build con caché podía
# reutilizar una capa vieja de la imagen y quedarse sin los parches de Debian, y
# Dependabot no tenía nada que proponer. Ahora cada build usa exactamente esta
# imagen, y Dependabot (ecosistema docker) abre una PR semanal cuando cambia el
# digest de 3.12-slim, con su CI y su Trivy. Digest del índice multiplataforma:
# vale para Render (amd64) y para el Kind en un Mac (arm64).
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

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