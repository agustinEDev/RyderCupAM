# 🚀 Deployment Guide - Ryder Cup Manager API

Este documento explica cómo desplegar la aplicación en diferentes entornos.

---

## 📦 **Despliegue con Docker (Recomendado)**

### **Requisitos Previos**
- Docker
- Docker Compose
- Variables de entorno configuradas

### **1. Configurar Variables de Entorno**

Crea un archivo `.env` basado en `.env.example`:

```bash
cp .env.example .env
```

Configura las variables necesarias:
```env
# Base de Datos
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=ryderclub
DATABASE_PORT=5432

# JWT
SECRET_KEY=your-super-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Documentación
DOCS_USERNAME=admin
DOCS_PASSWORD=secure-admin-password

# Aplicación
PORT=8000
ENVIRONMENT=production
```

### **2. Construir y Ejecutar**

```bash
# Construir y levantar todos los servicios
docker-compose up -d --build

# Ver logs
docker-compose logs -f app

# Parar servicios
docker-compose down

# Parar y eliminar volúmenes (⚠️ borra la BD)
docker-compose down -v
```

---

## 🐳 **Despliegue con Imágenes Pre-construidas (Docker Hub)**

### **¿Qué son las imágenes pre-construidas?**

En lugar de compilar la aplicación localmente (con `docker-compose build`), puedes usar imágenes ya construidas y optimizadas que están disponibles en Docker Hub. Esto hace el deployment **más rápido** y elimina la necesidad de tener el código fuente.

**🔗 Docker Hub Repository:** [agustinedev/rydercupam-app](https://hub.docker.com/r/agustinedev/rydercupam-app)

---

### **✨ Ventajas de Usar Imágenes Pre-construidas**

- ✅ **Deployment instantáneo** - No requiere compilación (ahorra 2-5 minutos)
- ✅ **Consistencia** - Misma imagen en dev, staging y producción
- ✅ **Sin dependencias de build** - No necesitas Docker BuildKit o compiladores
- ✅ **Rollback rápido** - Vuelve a versiones anteriores fácilmente
- ✅ **CI/CD optimizado** - Pipelines más rápidos
- ✅ **Menor consumo de recursos** - No usa CPU/RAM en build

---

### **📦 Imágenes Disponibles**

| Imagen | Descripción | Tag Recomendado |
|--------|-------------|-----------------|
| `agustinedev/rydercupam-app` | API FastAPI + Alembic | `latest` |
| `agustinedev/postgres` | PostgreSQL 15 Alpine | `15-alpine` |

**Tags disponibles:**
- `latest` - Última versión estable (recomendado para producción)
- `vX.Y.Z` - Versiones específicas (ej: `v1.0.0`, `v1.1.0`)

**Arquitecturas soportadas:** `linux/amd64`, `linux/arm64`

---

### **🔀 Dos Flujos de Trabajo: Local vs Docker Hub**

#### **Opción A: Build Local (Desarrollo)**

Construyes las imágenes en tu máquina desde el código fuente.

```bash
# ============================================
# 1. CONSTRUIR IMÁGENES (desde Dockerfile)
# ============================================
docker-compose build

# O construir y levantar en un solo comando
docker-compose up -d --build

# Construir solo el servicio app (sin base de datos)
docker-compose build app

# Construir sin caché (útil si hay problemas)
docker-compose build --no-cache

# ============================================
# 2. INICIAR SERVICIOS
# ============================================
# Iniciar en modo detached (background)
docker-compose up -d

# Iniciar y ver logs en tiempo real
docker-compose up

# Iniciar solo la base de datos
docker-compose up -d db

# ============================================
# 3. VER ESTADO Y LOGS
# ============================================
# Ver servicios corriendo
docker-compose ps

# Ver logs en tiempo real
docker-compose logs -f

# Ver logs solo del servicio app
docker-compose logs -f app

# Ver logs solo de la base de datos
docker-compose logs -f db

# Ver últimas 100 líneas de logs
docker-compose logs --tail=100 app

# ============================================
# 4. REINICIAR SERVICIOS
# ============================================
# Reiniciar todos los servicios
docker-compose restart

# Reiniciar solo app
docker-compose restart app

# Reiniciar solo base de datos
docker-compose restart db

# Reconstruir y reiniciar (tras cambios en Dockerfile)
docker-compose up -d --build

# ============================================
# 5. DETENER SERVICIOS
# ============================================
# Parar sin eliminar contenedores
docker-compose stop

# Parar y eliminar contenedores (pero conserva volúmenes/BD)
docker-compose down

# Parar, eliminar contenedores Y volúmenes (⚠️ BORRA LA BD)
docker-compose down -v

# Parar y eliminar imágenes también
docker-compose down --rmi all

# ============================================
# 6. EJECUTAR COMANDOS EN CONTENEDORES
# ============================================
# Shell interactivo en el contenedor app
docker-compose exec app bash

# Ejecutar comando específico
docker-compose exec app alembic current

# Ver variables de entorno
docker-compose exec app env

# Ejecutar tests
docker-compose exec app pytest tests/

# ============================================
# 7. LIMPIAR SISTEMA
# ============================================
# Ver espacio usado por Docker
docker system df

# Limpiar imágenes no usadas
docker image prune

# Limpiar todo (contenedores, redes, imágenes no usadas)
docker system prune

# Limpiar TODO incluyendo volúmenes (⚠️ PELIGROSO)
docker system prune -a --volumes
```

**📁 Usa el archivo:** `docker-compose.yml` (con `build: .`)

---

#### **Opción B: Docker Hub (Producción/Staging)**

Descargas imágenes pre-construidas desde Docker Hub.

```bash
# ============================================
# 1. DESCARGAR IMÁGENES (desde Docker Hub)
# ============================================
# Descargar última versión
docker pull agustinedev/rydercupam-app:latest
docker pull agustinedev/postgres:15-alpine

# Descargar versión específica
docker pull agustinedev/rydercupam-app:v1.0.0

# Descargar todas las imágenes del compose
docker-compose -f docker-compose.prod.yml pull

# ============================================
# 2. INICIAR SERVICIOS (sin build)
# ============================================
# Iniciar con archivo de producción
docker-compose -f docker-compose.prod.yml up -d

# Ver logs
docker-compose -f docker-compose.prod.yml logs -f

# ============================================
# 3. ACTUALIZAR A NUEVA VERSIÓN
# ============================================
# 1. Descargar última imagen
docker-compose -f docker-compose.prod.yml pull

# 2. Detener servicios actuales
docker-compose -f docker-compose.prod.yml down

# 3. Reiniciar con nueva imagen
docker-compose -f docker-compose.prod.yml up -d

# O todo en un comando (recomendado)
docker-compose -f docker-compose.prod.yml pull && \
docker-compose -f docker-compose.prod.yml up -d --force-recreate

# ============================================
# 4. ROLLBACK A VERSIÓN ANTERIOR
# ============================================
# Editar docker-compose.prod.yml y cambiar:
# image: agustinedev/rydercupam-app:latest
# a
# image: agustinedev/rydercupam-app:v1.0.0

# Luego reiniciar
docker-compose -f docker-compose.prod.yml up -d --force-recreate

# ============================================
# 5. DETENER SERVICIOS
# ============================================
# Parar servicios (igual que local)
docker-compose -f docker-compose.prod.yml stop

# Parar y eliminar contenedores
docker-compose -f docker-compose.prod.yml down

# Parar y eliminar volúmenes (⚠️ BORRA LA BD)
docker-compose -f docker-compose.prod.yml down -v

# ============================================
# 6. VERIFICAR IMÁGENES
# ============================================
# Ver imágenes descargadas
docker images | grep agustinedev

# Ver detalles de la imagen
docker inspect agustinedev/rydercupam-app:latest

# Ver cuándo se construyó la imagen
docker inspect agustinedev/rydercupam-app:latest | grep Created

# Ver capas de la imagen
docker history agustinedev/rydercupam-app:latest

# ============================================
# 7. LIMPIAR IMÁGENES ANTIGUAS
# ============================================
# Eliminar imágenes viejas de rydercupam-app
docker images | grep agustinedev/rydercupam-app | grep -v latest | awk '{print $3}' | xargs docker rmi

# Limpiar imágenes sin tag (<none>)
docker image prune
```

**📁 Usa el archivo:** `docker-compose.prod.yml` (con `image: agustinedev/...`)

---

### **🗄️ Comandos de Base de Datos**

#### **🔄 Migraciones (Alembic)**

```bash
# ============================================
# APLICAR MIGRACIONES (Build Local)
# ============================================
# Aplicar todas las migraciones pendientes
docker-compose exec app alembic upgrade head

# Aplicar solo la siguiente migración
docker-compose exec app alembic upgrade +1

# Ver estado actual de migraciones
docker-compose exec app alembic current

# Ver historial de migraciones
docker-compose exec app alembic history

# Ver migraciones pendientes
docker-compose exec app alembic history --verbose

# ============================================
# APLICAR MIGRACIONES (Docker Hub)
# ============================================
# Mismo comando pero con el archivo de producción
docker-compose -f docker-compose.prod.yml exec app alembic upgrade head

# Ver estado actual
docker-compose -f docker-compose.prod.yml exec app alembic current

# ============================================
# ROLLBACK DE MIGRACIONES
# ============================================
# Revertir última migración
docker-compose exec app alembic downgrade -1

# Revertir a migración específica
docker-compose exec app alembic downgrade <revision_id>

# Revertir todas las migraciones (⚠️ PELIGROSO)
docker-compose exec app alembic downgrade base

# ============================================
# CREAR NUEVAS MIGRACIONES (Solo desarrollo)
# ============================================
# Generar migración automática
docker-compose exec app alembic revision --autogenerate -m "descripcion del cambio"

# Crear migración vacía (manual)
docker-compose exec app alembic revision -m "descripcion"

# Ver SQL de una migración sin ejecutarla
docker-compose exec app alembic upgrade head --sql

# ============================================
# TROUBLESHOOTING MIGRACIONES
# ============================================
# Verificar que Alembic puede conectarse a la BD
docker-compose exec app alembic current

# Ver tabla de versiones de Alembic en la BD
docker-compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT * FROM alembic_version;"

# Marcar manualmente una migración como aplicada (⚠️ usar con cuidado)
docker-compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "INSERT INTO alembic_version VALUES ('<revision_id>');"
```

#### **🔌 Acceso Directo a PostgreSQL**

```bash
# ============================================
# CONECTARSE A POSTGRESQL (Build Local)
# ============================================
# Shell interactivo de PostgreSQL (psql)
docker-compose exec db psql -U postgres -d ryderclub

# O con variables de entorno del .env
docker-compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}

# Ejecutar query SQL directamente
docker-compose exec db psql -U postgres -d ryderclub -c "SELECT * FROM users LIMIT 5;"

# Ejecutar archivo SQL
docker-compose exec -T db psql -U postgres -d ryderclub < script.sql

# ============================================
# CONECTARSE A POSTGRESQL (Docker Hub)
# ============================================
# Mismo comando pero con archivo de producción
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d ryderclub

# ============================================
# QUERIES ÚTILES DENTRO DE PSQL
# ============================================
# Una vez dentro de psql (docker-compose exec db psql ...)

# Ver todas las tablas
\dt

# Describir estructura de una tabla
\d users

# Ver todas las bases de datos
\l

# Cambiar de base de datos
\c nombre_base_datos

# Ver usuarios de PostgreSQL
\du

# Ver índices de una tabla
\di

# Ejecutar query con formato bonito
\x
SELECT * FROM users LIMIT 1;

# Salir de psql
\q

# ============================================
# VERIFICAR ESTADO DE LA BASE DE DATOS
# ============================================
# Ver si PostgreSQL está corriendo
docker-compose exec db pg_isready -U postgres

# Ver procesos activos en PostgreSQL
docker-compose exec db psql -U postgres -d ryderclub -c "SELECT pid, usename, application_name, state, query FROM pg_stat_activity;"

# Ver tamaño de la base de datos
docker-compose exec db psql -U postgres -d ryderclub -c "SELECT pg_size_pretty(pg_database_size('ryderclub'));"

# Ver tamaño de cada tabla
docker-compose exec db psql -U postgres -d ryderclub -c "SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Ver cantidad de registros por tabla
docker-compose exec db psql -U postgres -d ryderclub -c "SELECT schemaname,relname,n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"
```

#### **💾 Backup y Restore**

```bash
# ============================================
# BACKUP DE BASE DE DATOS (Build Local)
# ============================================
# Backup completo (dump)
docker-compose exec -T db pg_dump -U postgres -d ryderclub > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup comprimido (más pequeño)
docker-compose exec -T db pg_dump -U postgres -d ryderclub | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Backup solo de schema (sin datos)
docker-compose exec -T db pg_dump -U postgres -d ryderclub --schema-only > schema_backup.sql

# Backup solo de datos (sin estructura)
docker-compose exec -T db pg_dump -U postgres -d ryderclub --data-only > data_backup.sql

# Backup de una tabla específica
docker-compose exec -T db pg_dump -U postgres -d ryderclub -t users > users_backup.sql

# ============================================
# BACKUP (Docker Hub / Producción)
# ============================================
# Mismo comando pero con archivo de producción
docker-compose -f docker-compose.prod.yml exec -T db pg_dump -U postgres -d ryderclub > backup_prod_$(date +%Y%m%d_%H%M%S).sql

# ============================================
# RESTORE DE BASE DE DATOS
# ============================================
# Restore desde backup
docker-compose exec -T db psql -U postgres -d ryderclub < backup_20250101_120000.sql

# Restore desde backup comprimido
gunzip -c backup_20250101_120000.sql.gz | docker-compose exec -T db psql -U postgres -d ryderclub

# Restore creando nueva base de datos
docker-compose exec db createdb -U postgres ryderclub_restore
docker-compose exec -T db psql -U postgres -d ryderclub_restore < backup.sql

# ============================================
# LIMPIAR Y RECREAR BASE DE DATOS
# ============================================
# ⚠️ PELIGROSO - Elimina todos los datos

# Opción 1: Eliminar y recrear desde Docker Compose
docker-compose down -v  # Elimina volumen (borra datos)
docker-compose up -d    # Levanta con BD vacía
docker-compose exec app alembic upgrade head  # Aplica migraciones

# Opción 2: Eliminar y recrear manualmente
docker-compose exec db psql -U postgres -c "DROP DATABASE ryderclub;"
docker-compose exec db psql -U postgres -c "CREATE DATABASE ryderclub;"
docker-compose exec app alembic upgrade head
```

#### **🔍 Debugging y Monitoreo de BD**

```bash
# ============================================
# LOGS DE POSTGRESQL
# ============================================
# Ver logs de la base de datos
docker-compose logs -f db

# Ver últimas 50 líneas
docker-compose logs --tail=50 db

# Buscar errores en logs
docker-compose logs db | grep ERROR

# ============================================
# PERFORMANCE Y DIAGNÓSTICO
# ============================================
# Ver queries lentas (dentro de psql)
docker-compose exec db psql -U postgres -d ryderclub -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC;"

# Ver conexiones activas
docker-compose exec db psql -U postgres -d ryderclub -c "SELECT count(*) FROM pg_stat_activity;"

# Ver locks activos
docker-compose exec db psql -U postgres -d ryderclub -c "SELECT * FROM pg_locks WHERE NOT granted;"

# Vacuum de la base de datos (optimización)
docker-compose exec db psql -U postgres -d ryderclub -c "VACUUM ANALYZE;"

# ============================================
# COPIAR DATOS ENTRE AMBIENTES
# ============================================
# Copiar BD de local a archivo
docker-compose exec -T db pg_dump -U postgres -d ryderclub > local_backup.sql

# Restaurar en producción (Docker Hub)
cat local_backup.sql | docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres -d ryderclub

# Copiar solo una tabla entre ambientes
docker-compose exec -T db pg_dump -U postgres -d ryderclub -t users | \
docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres -d ryderclub
```

#### **🛡️ Seguridad y Mantenimiento**

```bash
# ============================================
# CAMBIAR CONTRASEÑA DE POSTGRES
# ============================================
# Dentro de psql
docker-compose exec db psql -U postgres -d ryderclub -c "ALTER USER postgres WITH PASSWORD 'nueva_contraseña';"

# Luego actualizar en .env
# POSTGRES_PASSWORD=nueva_contraseña

# Recrear contenedor para aplicar cambios
docker-compose down
docker-compose up -d

# ============================================
# VERIFICAR CONFIGURACIÓN DE SEGURIDAD
# ============================================
# Ver roles y privilegios
docker-compose exec db psql -U postgres -d ryderclub -c "\du"

# Ver conexiones permitidas
docker-compose exec db cat /var/lib/postgresql/data/pg_hba.conf
```

---

### **📄 Archivo docker-compose.prod.yml**

Crea este archivo para usar las imágenes de Docker Hub:

```yaml
services:
  db:
    image: agustinedev/postgres:15-alpine  # 👈 Imagen de Docker Hub
    ports:
      - "${DATABASE_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    env_file:
      - .env
    environment:
      - POSTGRES_USER=${POSTGRES_USER:-postgres}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
      - POSTGRES_DB=${POSTGRES_DB:-ryderclub}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    image: agustinedev/rydercupam-app:latest  # 👈 Imagen de Docker Hub
    ports:
      - "${PORT:-8000}:8000"
    env_file:
      - .env
    environment:
      # Database Configuration
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@db:5432/${POSTGRES_DB:-ryderclub}
      - DATABASE_HOST=db
      - DATABASE_PORT=5432
      - POSTGRES_USER=${POSTGRES_USER:-postgres}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
      - POSTGRES_DB=${POSTGRES_DB:-ryderclub}

      # Application Configuration
      - PORT=${PORT:-8000}
      - ENVIRONMENT=${ENVIRONMENT:-production}

      # JWT Configuration
      - SECRET_KEY=${SECRET_KEY}
      - ALGORITHM=${ALGORITHM:-HS256}
      - ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES:-60}

      # Swagger/Docs Protection
      - DOCS_USERNAME=${DOCS_USERNAME}
      - DOCS_PASSWORD=${DOCS_PASSWORD}

      # Mailgun Configuration (Email Verification)
      - MAILGUN_API_KEY=${MAILGUN_API_KEY}
      - MAILGUN_DOMAIN=${MAILGUN_DOMAIN}
      - MAILGUN_FROM_EMAIL=${MAILGUN_FROM_EMAIL}
      - MAILGUN_API_URL=${MAILGUN_API_URL:-https://api.eu.mailgun.net/v3}
      - FRONTEND_URL=${FRONTEND_URL}
    depends_on:
      db:
        condition: service_healthy

volumes:
  postgres_data:
```

**🔍 Diferencias clave vs docker-compose.yml:**
- ❌ Eliminado: `build: .` → ✅ Añadido: `image: agustinedev/rydercupam-app:latest`
- ❌ Eliminado: `volumes: - .:/app` (no necesitas código fuente)
- ✅ `ENVIRONMENT=production` (en lugar de development)

---

### **📊 Comparativa de Comandos**

| Acción | Build Local | Docker Hub |
|--------|-------------|------------|
| **Construir/Descargar** | `docker-compose build` | `docker pull agustinedev/rydercupam-app:latest` |
| **Iniciar** | `docker-compose up -d` | `docker-compose -f docker-compose.prod.yml up -d` |
| **Ver logs** | `docker-compose logs -f` | `docker-compose -f docker-compose.prod.yml logs -f` |
| **Reiniciar** | `docker-compose restart` | `docker-compose -f docker-compose.prod.yml restart` |
| **Detener** | `docker-compose down` | `docker-compose -f docker-compose.prod.yml down` |
| **Actualizar** | `docker-compose up -d --build` | `docker-compose -f docker-compose.prod.yml pull && up -d` |
| **Ejecutar comando** | `docker-compose exec app bash` | `docker-compose -f docker-compose.prod.yml exec app bash` |
| **Aplicar migraciones** | `docker-compose exec app alembic upgrade head` | `docker-compose -f docker-compose.prod.yml exec app alembic upgrade head` |
| **Backup BD** | `docker-compose exec -T db pg_dump -U postgres -d ryderclub > backup.sql` | `docker-compose -f docker-compose.prod.yml exec -T db pg_dump > backup.sql` |
| **Conectar a BD** | `docker-compose exec db psql -U postgres -d ryderclub` | `docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d ryderclub` |

---

### **🎯 ¿Cuándo Usar Cada Opción?**

| Escenario | Recomendación |
|-----------|---------------|
| 🛠️ **Desarrollo local activo** | **Build Local** - Necesitas hot reload y cambios rápidos |
| 🧪 **Testing en CI/CD** | **Docker Hub** - Más rápido, sin compilación |
| 🌐 **Staging** | **Docker Hub** - Consistencia con producción |
| 🚀 **Producción** | **Docker Hub** - Imagen probada, rollback fácil |
| 🔄 **Hotfix urgente** | **Docker Hub** - Deploy inmediato sin build |
| 📦 **Sin código fuente** | **Docker Hub** - Solo necesitas .env |
| 💻 **Servidor limitado (1GB RAM)** | **Docker Hub** - No consume recursos en build |

---

### **🔄 Workflow Completo: Desarrollo → Producción**

#### **En tu máquina local (desarrollo):**
```bash
# 1. Desarrollar con hot reload
docker-compose up -d

# 2. Hacer cambios en el código
# (los cambios se reflejan automáticamente gracias a volumes)

# 3. Crear y aplicar migraciones si hay cambios en modelos
docker-compose exec app alembic revision --autogenerate -m "agregar campo X"
docker-compose exec app alembic upgrade head

# 4. Cuando estés listo, construir imagen para producción
docker-compose build

# 5. Etiquetar la imagen con versión
docker tag rydercupam-app agustinedev/rydercupam-app:v1.1.0
docker tag rydercupam-app agustinedev/rydercupam-app:latest

# 6. Subir a Docker Hub
docker push agustinedev/rydercupam-app:v1.1.0
docker push agustinedev/rydercupam-app:latest
```

#### **En servidor de producción:**
```bash
# 1. Hacer backup de la BD antes de actualizar (⚠️ IMPORTANTE)
docker-compose -f docker-compose.prod.yml exec -T db pg_dump -U postgres -d ryderclub > backup_pre_update_$(date +%Y%m%d).sql

# 2. Descargar última versión
docker-compose -f docker-compose.prod.yml pull

# 3. Aplicar cambios
docker-compose -f docker-compose.prod.yml up -d --force-recreate

# 4. Las migraciones se ejecutan automáticamente en entrypoint.sh
# Pero si quieres verificar:
docker-compose -f docker-compose.prod.yml logs -f app | grep "migr"

# 5. Verificar estado de migraciones
docker-compose -f docker-compose.prod.yml exec app alembic current

# 6. Verificar API funcionando
curl https://tu-api.com/
docker-compose -f docker-compose.prod.yml logs -f app
```

---

### **🐛 Troubleshooting Común**

#### **❌ "Error: image not found" (Docker Hub)**
```bash
# Solución: Descargar manualmente
docker pull agustinedev/rydercupam-app:latest

# Si sigue fallando, verificar conectividad
docker login
```

#### **❌ "Error: no space left on device" (Build Local)**
```bash
# Solución: Limpiar imágenes viejas
docker system prune -a
docker volume prune
```

#### **❌ La imagen no se actualiza (Docker Hub)**
```bash
# Solución: Forzar descarga y recrear contenedores
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --force-recreate
```

#### **❌ "Alembic error: can't connect to database"**
```bash
# Solución: Verificar que la BD está corriendo
docker-compose ps

# Ver logs de la BD
docker-compose logs db

# Verificar conectividad
docker-compose exec db pg_isready -U postgres

# Verificar DATABASE_URL
docker-compose exec app env | grep DATABASE_URL
```

#### **❌ "Migration conflict" o "Multiple heads detected"**
```bash
# Ver heads actuales
docker-compose exec app alembic heads

# Mergear heads (si tienes múltiples ramas de migración)
docker-compose exec app alembic merge heads -m "merge migrations"
docker-compose exec app alembic upgrade head
```

#### **❌ "Error: no matching manifest for linux/arm64"**
```bash
# Solución: Especificar plataforma
docker pull --platform linux/amd64 agustinedev/rydercupam-app:latest
```

#### **❌ Build local falla con "no space left"**
```bash
# Ver espacio usado
docker system df

# Limpiar todo excepto volúmenes
docker system prune -a

# Si necesitas espacio extremo (⚠️ borra volúmenes)
docker system prune -a --volumes
```

---

### **📚 Comandos de Referencia Rápida**

#### **Desarrollo Local**
```bash
# Start
docker-compose up -d --build

# Stop
docker-compose down

# Logs
docker-compose logs -f app

# Restart
docker-compose restart app

# Migraciones
docker-compose exec app alembic upgrade head

# BD Access
docker-compose exec db psql -U postgres -d ryderclub

# Backup
docker-compose exec -T db pg_dump -U postgres -d ryderclub > backup.sql
```

#### **Producción (Docker Hub)**
```bash
# Start
docker-compose -f docker-compose.prod.yml up -d

# Update
docker-compose -f docker-compose.prod.yml pull && \
docker-compose -f docker-compose.prod.yml up -d --force-recreate

# Stop
docker-compose -f docker-compose.prod.yml down

# Logs
docker-compose -f docker-compose.prod.yml logs -f app

# Migraciones
docker-compose -f docker-compose.prod.yml exec app alembic current

# Backup
docker-compose -f docker-compose.prod.yml exec -T db pg_dump -U postgres -d ryderclub > backup_prod.sql
```

---

## 🔧 **Cómo Funciona el Deployment Automático**

### **Script de Inicio (`entrypoint.sh`)**

El contenedor ejecuta automáticamente estos pasos:

1. ✅ **Espera a PostgreSQL**: Verifica que la BD esté lista
2. ✅ **Ejecuta Migraciones**: `alembic upgrade head`
3. ✅ **Inicia la API**: `uvicorn main:app`

### **Dockerfile**

- Instala dependencias del sistema (`netcat`, `postgresql-client`)
- Instala dependencias de Python
- Copia el código y el script de inicio
- Configura el ENTRYPOINT para ejecutar el script

### **Docker Compose**

- **Servicio DB**: PostgreSQL con healthcheck
- **Servicio APP**: Espera a que DB esté healthy antes de iniciar
- **Volúmenes**: Persistencia de datos de PostgreSQL

---

## ☁️ **Despliegue en Hosting (Render, Railway, etc.)**

### **Opción 1: Render.com** (Guía Completa Paso a Paso)

> ⚠️ **IMPORTANTE**: En Render se despliegan **DOS servicios separados**:
> 1. **PostgreSQL Database** (servicio de base de datos)
> 2. **Web Service** (contenedor Docker con la API FastAPI)
>
> Debes crear PRIMERO la base de datos y DESPUÉS el backend.

---

#### **📋 Prerequisitos**
- Cuenta en [Render.com](https://render.com)
- Repositorio en GitHub con el código
- Git push realizado (última versión en GitHub)

---

#### **🗄️ PASO 1: Crear Base de Datos PostgreSQL (PRIMERO)**

> Este servicio es independiente del backend. Render lo gestiona por separado.

1. **Ir a Render Dashboard** → `New` → `PostgreSQL`

2. **Configuración:**
   - **Name**: `rydercup-db` (o el nombre que prefieras)
   - **Database**: `ryderclub`
   - **User**: (auto-generado)
   - **Region**: `Oregon (US West)` (o el más cercano)
   - **PostgreSQL Version**: `15`
   - **Plan**: `Free` (para desarrollo)

3. **Crear** → Esperar a que esté disponible (1-2 minutos)

4. **⚠️ CRUCIAL - Copiar credenciales:**
   - En la página de la BD, ir a **"Connections"**
   - Copiar **"Internal Database URL"** (empieza con `postgresql://...`)
   - **Guardar este URL** - lo necesitarás en el PASO 3

   ```
   Ejemplo:
   postgresql://rydercup_db_user:XXXXX@dpg-xxxxx-a.oregon-postgres.render.com/rydercup_db
   ```

**✅ Base de datos lista. Ahora vamos al backend.**

---

#### **🌐 PASO 2: Crear Web Service (Backend API - SEGUNDO)**

> Este es el contenedor Docker que ejecutará tu FastAPI. Se conectará a la BD del PASO 1.

1. **Dashboard** → `New` → `Web Service`

2. **Conectar GitHub:**
   - `Build and deploy from a Git repository`
   - Seleccionar tu repositorio `RyderCupAM`
   - Branch: `main` o `develop`

3. **Configuración Básica:**
   - **Name**: `rydercup-api`
   - **Region**: `Oregon (US West)` ⚠️ **MISMO que la BD**
   - **Branch**: `main`
   - **Runtime**: `Docker` ⚠️ **IMPORTANTE - Debe ser Docker**

4. **Plan:**
   - **Instance Type**: `Free` (para desarrollo)

5. **ANTES DE CREAR** → Clic en `Advanced` (abajo) para configurar variables de entorno

---

#### **🔐 PASO 3: Configurar Variables de Entorno (CRÍTICO)**

En la sección **Environment Variables**, añadir:

```env
# ====================================
# Base de Datos - PEGAR URL DEL PASO 1
# ====================================
DATABASE_URL=postgresql+asyncpg://user:pass@host.oregon-postgres.render.com/db_name

# ⚠️ IMPORTANTE: Cambiar 'postgresql://' por 'postgresql+asyncpg://'
# Render te da: postgresql://...
# Debes usar: postgresql+asyncpg://...

# ====================================
# JWT - Generar clave segura
# ====================================
SECRET_KEY=<generar-con-comando-abajo>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# ====================================
# Documentación API
# ====================================
DOCS_USERNAME=admin
DOCS_PASSWORD=<contraseña-segura>

# ====================================
# Aplicación
# ====================================
PORT=8000
ENVIRONMENT=production

# ====================================
# Mailgun (Email Verification) - REQUERIDO desde v1.1
# ====================================
MAILGUN_API_KEY=<tu-api-key-de-mailgun>
MAILGUN_DOMAIN=rydercupfriends.com
MAILGUN_FROM_EMAIL=Ryder Cup Friends <noreply@rydercupfriends.com>
MAILGUN_API_URL=https://api.eu.mailgun.net/v3
FRONTEND_URL=https://www.rydercupfriends.com
```

**⚠️ NOTAS IMPORTANTES:**
- **DATABASE_URL**: Debe usar `postgresql+asyncpg://` (no `postgresql://`)
- **MAILGUN variables**: Obligatorias para verificación de email
- **FRONTEND_URL**: Tu dominio de producción (no localhost)

**🔑 Generar SECRET_KEY segura:**

```bash
# Opción 1: Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Opción 2: OpenSSL
openssl rand -base64 32
```

---

#### **🎯 PASO 4: Deploy del Backend**

1. **Crear Web Service** (botón abajo)

2. **Render automáticamente:**
   - ✅ Clona el repositorio
   - ✅ Detecta el `Dockerfile`
   - ✅ Construye la imagen Docker
   - ✅ Ejecuta `entrypoint.sh` que:
     - Espera a que PostgreSQL esté disponible
     - Ejecuta migraciones (`alembic upgrade head`)
     - Inicia la API FastAPI

3. **Esperar deployment** (2-5 minutos primera vez)

4. **Ver logs en tiempo real:**
   - En la página del servicio → pestaña `Logs`
   - Deberías ver:
     ```
     🚀 Iniciando Ryder Cup Manager API...
     ⏳ Esperando a que PostgreSQL esté disponible...
     ✅ PostgreSQL está disponible
     🔄 Ejecutando migraciones de base de datos...
     ✅ Migraciones completadas exitosamente
     🎯 Iniciando aplicación FastAPI en puerto 8000...
     INFO: Started server process
     INFO: Uvicorn running on http://0.0.0.0:8000
     ```

---

#### **✅ PASO 5: Verificar Deployment**

**Obtener URL de tu API:**
- Tu API estará en: `https://rydercup-api.onrender.com`

**Probar endpoints:**

```bash
# Health check
curl https://rydercup-api.onrender.com/

# Respuesta esperada:
{
  "message": "Ryder Cup Manager API",
  "version": "1.0.0",
  "status": "running"
}

# Swagger UI (requiere autenticación HTTP Basic)
https://rydercup-api.onrender.com/docs
```

---

#### **🔄 Actualizaciones Futuras (Auto-Deploy)**

Render hace **auto-deploy** cuando haces push a GitHub:

```bash
git add .
git commit -m "feat: nueva funcionalidad"
git push origin main
```

Render detecta el cambio y redeploya automáticamente.

**Manual Re-deploy:**
- Dashboard del servicio → `Manual Deploy` → `Deploy latest commit`

---

#### **🔍 Troubleshooting Específico de Render**

**❌ Error: "Failed to connect to database"**

**Causa:** DATABASE_URL incorrecta o no modificada

**Solución:**
1. Ir a PostgreSQL service → Connections
2. Copiar **Internal Database URL** (NO External)
3. **IMPORTANTE:** Cambiar `postgresql://` por `postgresql+asyncpg://`
4. Actualizar variable de entorno en Web Service
5. Re-deploy manual

**❌ Error: "Alembic migrations failed"**

**Causa:** Primera vez que se ejecutan las migraciones o error en conexión

**Solución:**
1. Verificar que la BD esté corriendo (PostgreSQL service debe estar "Available")
2. Verificar DATABASE_URL
3. Ir a Shell del Web Service (pestaña Shell)
4. Ejecutar manualmente:
   ```bash
   alembic upgrade head
   ```
5. Re-deploy

**❌ Error: "Port already in use"**

**Causa:** Variable PORT incorrecta

**Solución:**
1. Asegurar que `PORT=8000` en variables de entorno
2. Re-deploy

**⚠️ Free Plan - Cold Starts**

> El plan gratuito de Render "duerme" la app tras 15 minutos de inactividad.

**Comportamiento:**
- Primera petición después de sleep: 30-60 segundos
- Luego funciona normal

**Solución** (si es crítico):
- Upgrade a plan Starter ($7/mes)
- Mantiene app siempre activa

---

#### **💰 Costos de Render**

**Free Tier:**
- **PostgreSQL**: 1GB storage, expira tras 90 días de inactividad
- **Web Service**: Duerme tras 15min inactividad, 750 horas/mes
- **SSL**: Gratuito y automático
- **Costo total: $0**

**Starter Tier ($7/mes por servicio):**
- Sin sleep (siempre activo)
- Más recursos (CPU/RAM)
- Backups automáticos de BD

---

#### **🔐 Seguridad - Checklist para Producción en Render**

Antes de usar en producción, verificar:

- [ ] `SECRET_KEY` generada aleatoriamente (32+ caracteres)
- [ ] `DOCS_PASSWORD` cambiada del default
- [ ] `DATABASE_URL` usando **Internal URL** (no External)
- [ ] `DATABASE_URL` modificada a `postgresql+asyncpg://`
- [ ] `ENVIRONMENT=production`
- [ ] `MAILGUN_API_KEY` configurada con tu API key real
- [ ] `MAILGUN_FROM_EMAIL` con formato correcto
- [ ] `FRONTEND_URL` apuntando a tu dominio de producción
- [ ] CORS configurado solo para tu dominio frontend (verificar `main.py`)
- [ ] SSL/HTTPS activado (Render lo hace automáticamente)
- [ ] Ambos servicios (BD y API) en la **misma región**

---

#### **📊 Monitoreo en Render**

**Logs en Tiempo Real:**
- Dashboard del servicio → `Logs` → Ver output de la aplicación

**Métricas:**
- Dashboard → `Metrics` → CPU, Memoria, Requests

**Eventos:**
- Dashboard → `Events` → Historial de deploys y errores

**Shell Interactivo:**
- Dashboard → `Shell` → Ejecutar comandos en el contenedor
  ```bash
  # Verificar migración actual
  alembic current

  # Ver status de BD
  python -c "from src.config.settings import settings; print(settings.DATABASE_URL)"
  ```

---

### **Opción 2: Railway.app**

1. **New Project → Deploy from GitHub**
2. **Variables de Entorno**:
   - Configurar las mismas variables que arriba
   - Railway auto-detecta el Dockerfile

3. **PostgreSQL Plugin**:
   - Añadir PostgreSQL desde Railway
   - Auto-configura DATABASE_URL

### **Opción 3: Fly.io**

```bash
# Instalar flyctl
brew install flyctl

# Login
flyctl auth login

# Lanzar app
flyctl launch

# Añadir PostgreSQL
flyctl postgres create

# Conectar a la app
flyctl postgres attach <postgres-app-name>

# Deploy
flyctl deploy
```

---

## 🔍 **Verificación Post-Deployment**

### **Health Check**
```bash
curl https://your-domain.com/
```

Respuesta esperada:
```json
{
  "message": "Ryder Cup Manager API",
  "version": "1.0.0",
  "status": "running"
}
```

### **Verificar Migraciones**
```bash
# En Docker local
docker-compose exec app alembic current

# En producción (si tienes acceso SSH)
alembic current
```

### **Ver Logs**
```bash
# Docker Compose
docker-compose logs -f app

# Render/Railway
# Ver desde el dashboard web
```

---

## 🔒 **Seguridad - Checklist**

- [ ] **SECRET_KEY**: Generada aleatoriamente (min 32 chars)
- [ ] **DOCS_PASSWORD**: Contraseña fuerte
- [ ] **POSTGRES_PASSWORD**: Contraseña segura
- [ ] **ENVIRONMENT**: Configurado como `production`
- [ ] **HTTPS**: Activado en el hosting
- [ ] **CORS**: Configurado solo para tu dominio frontend
- [ ] **DATABASE_URL**: No exponer públicamente

---

## 🛠️ **Troubleshooting**

### **Error: Connection refused (PostgreSQL)**
- Verificar que DATABASE_HOST apunta al servicio correcto
- Verificar que PostgreSQL esté corriendo
- Revisar logs: `docker-compose logs db`

### **Error: Alembic migrations failed**
- Verificar DATABASE_URL
- Ejecutar manualmente: `docker-compose exec app alembic upgrade head`
- Revisar logs de migración

### **Error: 405 Method Not Allowed (CORS)**
- Verificar configuración CORS en `main.py`
- Añadir tu dominio frontend a `allow_origins`

### **Puerto en uso**
```bash
# Cambiar puerto en .env
PORT=8001

# Reconstruir
docker-compose up -d --build
```

---

## 📊 **Monitoreo**

### **Logs en Tiempo Real**
```bash
docker-compose logs -f app
```

### **Estado de Servicios**
```bash
docker-compose ps
```

### **Ejecutar Comandos en el Contenedor**
```bash
# Shell interactivo
docker-compose exec app bash

# Ejecutar comando específico
docker-compose exec app alembic current
```

---

## 🔄 **CI/CD con GitHub Actions**

Crear `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Render
        env:
          RENDER_API_KEY: ${{ secrets.RENDER_API_KEY }}
        run: |
          curl -X POST https://api.render.com/v1/services/${{ secrets.RENDER_SERVICE_ID }}/deploys
```

---

## 📞 **Soporte**

Si encuentras problemas:
1. Revisa los logs
2. Verifica variables de entorno
3. Consulta la documentación del hosting
4. Abre un issue en GitHub

---

**¡Tu API está lista para producción! 🚀**
