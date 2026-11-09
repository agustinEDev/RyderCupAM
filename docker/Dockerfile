# ==========================================
# DOCKERFILE - Solo aplicación FastAPI
# ==========================================
# Este Dockerfile funciona para:
# - Desarrollo local (con docker-compose.yml que incluye PostgreSQL)
# - Producción en Render/Railway (con base de datos externa)
# ==========================================

# 1. Imagen base: Python ligera
# 3.14-slim desde la v2.35.0 (20 oct 2026, Dependabot #423): el CI exige 3.12 y 3.14
# (#603). Antes, 3.12-slim para resolver CVE-2026-42496 (CRITICAL) y CVE-2026-42497,
# CVE-2026-9538 (HIGH) en paquetes del OS base de la imagen debian 3.11-slim
# Fijada por digest (28 sep 2026): con la etiqueta flotante, un build con caché podía
# reutilizar una capa vieja de la imagen y quedarse sin los parches de Debian, y
# Dependabot no tenía nada que proponer. Ahora cada build usa exactamente esta
# imagen, y Dependabot (ecosistema docker) abre una PR semanal cuando cambia el
# digest de la imagen, con su CI y su Trivy. Digest del índice multiplataforma:
# vale para Render (amd64) y para el Kind en un Mac (arm64).
FROM python:3.14-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d

# 2. Paquetes del sistema (BE #308)
# - upgrade en la misma capa que el update: recoge los parches de Debian publicados
#   después del digest de la imagen base, pero solo cuando se reconstruye la capa
#   (cambia el Dockerfile o el digest de la base, o --no-cache); con caché se
#   reutiliza tal cual. El digest lo renueva Dependabot (ecosistema docker)
# - netcat-openbsd: el `nc` con el que entrypoint.sh espera a PostgreSQL
# Sin postgresql-client: nada lo usa en esta imagen (todo psql, pg_dump y
# pg_isready se ejecuta en el contenedor de Postgres) y arrastraba perl, krb5,
# ldap y sasl, con la mayoría de las alertas de Trivy. psycopg2-binary trae su libpq
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# 3. Directorio de trabajo
WORKDIR /app

# 4. Copiar e instalar dependencias de Python
# (aprovecha cache de Docker si requirements.txt no cambia)
# pip al día antes que nada: el de la imagen base trae alertas (BE #308). Fijado y
# con hash desde requirements-bootstrap.lock (revisión de la fase 2): el pip que
# instala todo lo demás también se verifica. Sin setuptools: las imágenes 3.12+ no
# lo traen y requirements.txt fija su versión
# Desde requirements.lock, con un hash por paquete (OWASP A08, F-18): si alguien
# sustituye un paquete en el índice, pip se niega a instalarlo. Los dos locks se
# generan con scripts/freeze-requirements.sh, dentro de esta misma imagen y para
# linux/amd64 (Render), y un test comprueba que dicen las versiones de sus fuentes
COPY requirements.txt requirements.lock requirements-bootstrap.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements-bootstrap.lock \
    && pip install --no-cache-dir --require-hashes -r requirements.lock

# 5. Copiar código de la aplicación
COPY . .

# 6. Copiar y configurar script de inicio
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

# 6b. Sin privilegios (F-14): un fallo que ejecutara código lo haría como este
# usuario, no como root. El código sigue siendo de root, así que no puede
# cambiarlo; solo escribe en logs/ (el log de seguridad) y en /tmp.
# chmod a+rX: COPY conserva los permisos del equipo que construye, y un checkout
# local con carpetas 700 (el Kind se construye desde el árbol de trabajo) dejaba
# al usuario sin poder importar el código. Lectura para todos, escritura no
# Solo lo que no tiene ya esos bits: un chmod de todo el árbol copiaría a la capa
# nueva cada fichero aunque su modo no cambie
RUN find /app \( -type d ! -perm -a+rx -o -type f ! -perm -a+r \) -exec chmod a+rX {} + \
    && useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app/logs \
    && chown app:app /app/logs
USER app

# 7. Exponer puerto (configurable con ENV PORT)
EXPOSE 8000

# 8. Ejecutar script de inicio
# Este script maneja:
# - Espera a PostgreSQL (solo si DATABASE_HOST está configurado)
# - Ejecuta migraciones con Alembic
# - Inicia la aplicación FastAPI
ENTRYPOINT ["/entrypoint.sh"]