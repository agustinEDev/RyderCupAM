# 🚀 Deployment Guide - Ryder Cup Manager API

Guía para desplegar la aplicación en diferentes entornos.

---

## 📦 Despliegue con Docker (Recomendado)

### Requisitos Previos
- Docker + Docker Compose
- Variables de entorno configuradas (ver `.env.example`)

### Configurar Variables de Entorno

```bash
cp .env.example .env
```

**Variables críticas:**
```env
# Base de Datos
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=ryderclub

# JWT
SECRET_KEY=your-super-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Aplicación
PORT=8000
ENVIRONMENT=production

# Mailgun (Email Verification - Requerido v1.1+)
MAILGUN_API_KEY=<tu-api-key>
MAILGUN_DOMAIN=rydercupfriends.com
MAILGUN_FROM_EMAIL=Ryder Cup Friends <noreply@rydercupfriends.com>
MAILGUN_API_URL=https://api.eu.mailgun.net/v3
FRONTEND_URL=https://www.rydercupfriends.com
```

### Comandos Esenciales

```bash
# Construir y levantar
docker-compose up -d --build

# Ver logs
docker-compose logs -f app

# Parar servicios
docker-compose down

# Parar y eliminar volúmenes (⚠️ borra la BD)
docker-compose down -v
```

---

## 🐳 Despliegue con Docker Hub (Producción)

### Ventajas
- ✅ Deployment instantáneo (no requiere compilación)
- ✅ Consistencia entre ambientes
- ✅ Rollback rápido a versiones anteriores
- ✅ Optimizado para CI/CD

### Imágenes Disponibles

| Imagen | Tag Recomendado | Arquitecturas |
|--------|-----------------|---------------|
| `agustinedev/rydercupam-app` | `latest` | linux/amd64, linux/arm64 |
| `postgres` | `15-alpine` | linux/amd64, linux/arm64 |

**🔗 Docker Hub:** [agustinedev/rydercupam-app](https://hub.docker.com/r/agustinedev/rydercupam-app)

### Flujos de Trabajo

#### Desarrollo Local (con build)
```bash
# Construir y levantar
docker-compose up -d --build

# Reiniciar tras cambios
docker-compose restart app

# Ejecutar comandos
docker-compose exec app alembic upgrade head
docker-compose exec app bash
```

#### Producción (sin build - Docker Hub)
```bash
# Descargar imágenes
docker-compose -f docker-compose.prod.yml pull

# Iniciar servicios
docker-compose -f docker-compose.prod.yml up -d

# Actualizar a nueva versión
docker-compose -f docker-compose.prod.yml pull && \
docker-compose -f docker-compose.prod.yml up -d --force-recreate

# Ver logs
docker-compose -f docker-compose.prod.yml logs -f app
```

### Archivo docker-compose.prod.yml

**Diferencias clave vs docker-compose.yml:**
- ❌ Sin `build: .` → ✅ `image: agustinedev/rydercupam-app:latest`
- ❌ Sin volumen de código (`./:/app`)
- ✅ `ENVIRONMENT=production`

**📁 Ver archivo completo:** `docker-compose.prod.yml` en el repositorio

---

## 🗄️ Comandos de Base de Datos

### Migraciones (Alembic)

| Comando | Descripción |
|---------|-------------|
| `docker-compose exec app alembic upgrade head` | Aplicar todas las migraciones |
| `docker-compose exec app alembic current` | Ver estado actual |
| `docker-compose exec app alembic history` | Ver historial |
| `docker-compose exec app alembic downgrade -1` | Revertir última migración |

### Acceso a PostgreSQL

```bash
# Shell interactivo
docker-compose exec db psql -U postgres -d ryderclub

# Ejecutar query directa
docker-compose exec db psql -U postgres -d ryderclub -c "SELECT * FROM users LIMIT 5;"
```

**Comandos útiles dentro de psql:**
- `\dt` - Ver todas las tablas
- `\d users` - Describir estructura de tabla
- `\l` - Ver bases de datos
- `\q` - Salir

### Backup y Restore

```bash
# Backup completo
docker-compose exec -T db pg_dump -U postgres -d ryderclub > backup_$(date +%Y%m%d).sql

# Backup comprimido
docker-compose exec -T db pg_dump -U postgres -d ryderclub | gzip > backup.sql.gz

# Restore
docker-compose exec -T db psql -U postgres -d ryderclub < backup.sql

# Restore desde comprimido
gunzip -c backup.sql.gz | docker-compose exec -T db psql -U postgres -d ryderclub
```

---

## 📊 Comparativa de Comandos

| Acción | Build Local | Docker Hub (Producción) |
|--------|-------------|-------------------------|
| **Iniciar** | `docker-compose up -d` | `docker-compose -f docker-compose.prod.yml up -d` |
| **Ver logs** | `docker-compose logs -f` | `docker-compose -f docker-compose.prod.yml logs -f` |
| **Reiniciar** | `docker-compose restart` | `docker-compose -f docker-compose.prod.yml restart` |
| **Detener** | `docker-compose down` | `docker-compose -f docker-compose.prod.yml down` |
| **Actualizar** | `docker-compose up -d --build` | `docker-compose -f docker-compose.prod.yml pull && up -d` |
| **Migraciones** | `docker-compose exec app alembic upgrade head` | `docker-compose -f docker-compose.prod.yml exec app alembic upgrade head` |
| **Backup BD** | `docker-compose exec -T db pg_dump -U postgres -d ryderclub > backup.sql` | `docker-compose -f docker-compose.prod.yml exec -T db pg_dump > backup.sql` |

---

## ☁️ Despliegue en Render.com (Hosting Cloud)

### Prerequisitos
- Cuenta en [Render.com](https://render.com)
- Repositorio en GitHub con el código
- Mailgun API key configurada

> ⚠️ **IMPORTANTE**: Crear PRIMERO la base de datos, DESPUÉS el backend (dos servicios separados)

---

### PASO 1: Crear PostgreSQL Database

1. **Render Dashboard** → `New` → `PostgreSQL`

2. **Configuración:**
   - **Name**: `rydercup-db`
   - **Database**: `ryderclub`
   - **Region**: `Oregon (US West)`
   - **PostgreSQL Version**: `15`
   - **Plan**: `Free` (desarrollo) o `Starter` ($7/mes producción)

3. **Copiar credenciales:**
   - Ir a **"Connections"** → Copiar **"Internal Database URL"**
   - Formato: `postgresql://user:pass@host.oregon-postgres.render.com/db`

---

### PASO 2: Crear Web Service (Backend)

1. **Dashboard** → `New` → `Web Service`

2. **Conectar GitHub:**
   - Seleccionar repositorio `RyderCupAM`
   - Branch: `main`

3. **Configuración:**
   - **Name**: `rydercup-api`
   - **Region**: `Oregon (US West)` ⚠️ **MISMO que la BD**
   - **Runtime**: `Docker`
   - **Plan**: `Free` (desarrollo)

---

### PASO 3: Variables de Entorno (CRÍTICO)

En la sección **Environment Variables**:

```env
# Base de Datos - IMPORTANTE: Cambiar postgresql:// por postgresql+asyncpg://
DATABASE_URL=postgresql+asyncpg://user:pass@host.oregon-postgres.render.com/db

# JWT - Generar clave segura con: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=<generar-aleatoriamente-32-chars>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Documentación
DOCS_USERNAME=admin
DOCS_PASSWORD=<contraseña-segura>

# Aplicación
PORT=8000
ENVIRONMENT=production

# Mailgun (REQUERIDO para email verification)
MAILGUN_API_KEY=<tu-api-key-de-mailgun>
MAILGUN_DOMAIN=rydercupfriends.com
MAILGUN_FROM_EMAIL=Ryder Cup Friends <noreply@rydercupfriends.com>
MAILGUN_API_URL=https://api.eu.mailgun.net/v3
FRONTEND_URL=https://www.rydercupfriends.com

# Sentry - Error Tracking & Performance Monitoring (v1.8.0+)
SENTRY_DSN=https://<PUBLIC_KEY>@o<ORG_ID>.ingest.de.sentry.io/<PROJECT_ID>
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.05

# Session Timeout (v1.8.0+)
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**⚠️ NOTAS CRÍTICAS:**
- DATABASE_URL debe usar `postgresql+asyncpg://` (no `postgresql://`)
- MAILGUN variables son obligatorias desde v1.1.0
- FRONTEND_URL debe ser tu dominio de producción
- **SENTRY_DSN:** Obtener tu DSN real desde https://sentry.io → Settings → Projects → [Tu Proyecto] → Client Keys (DSN). Reemplaza `<PUBLIC_KEY>`, `<ORG_ID>` y `<PROJECT_ID>` con tus valores reales.
- SENTRY_TRACES_SAMPLE_RATE: 0.1 = 10% de requests monitoreados (recomendado)
- SENTRY_PROFILES_SAMPLE_RATE: 0.05 = 5% de profiles (reduce costos en producción)

---

### PASO 4: Deploy

1. **Crear Web Service** → Render automáticamente:
   - Clona el repositorio
   - Construye imagen Docker
   - Ejecuta `entrypoint.sh` (espera PostgreSQL → migraciones → inicia API)

2. **Ver logs en tiempo real:**
   - Pestaña `Logs` → Verificar:
     ```
     ✅ PostgreSQL está disponible
     ✅ Migraciones completadas exitosamente
     🎯 Iniciando aplicación FastAPI...
     INFO: Uvicorn running on http://0.0.0.0:8000
     ```

3. **Verificar deployment:**
   - Tu API: `https://api.rydercupfriends.com`
   - Health check: `curl https://api.rydercupfriends.com/health`
   - Swagger UI: `https://api.rydercupfriends.com/docs`

   `/health` devuelve la versión y el commit realmente desplegados, que es lo
   único que permite confirmar que una release ha llegado a producción:

   ```bash
   curl -s https://api.rydercupfriends.com/health
   # {"status":"ok","version":"2.4.0","commit":"abc1234","branch":"main","environment":"production"}
   ```

   Comparar ese `commit` con el SHA de la release para saber si el deploy ya ocurrió.

---

### Actualizaciones (Auto-Deploy)

Render hace auto-deploy cuando haces push a GitHub:

```bash
git add .
git commit -m "feat: nueva funcionalidad"
git push origin main
```

**Manual Re-deploy:** Dashboard → `Manual Deploy` → `Deploy latest commit`

---

### Troubleshooting Render

| Error | Solución |
|-------|----------|
| **"Failed to connect to database"** | Verificar DATABASE_URL tiene `postgresql+asyncpg://` y es Internal URL |
| **"Alembic migrations failed"** | Ejecutar manualmente en Shell: `alembic upgrade head` |
| **"Port already in use"** | Asegurar variable `PORT` en variables de entorno (Render la asigna automáticamente) |
| **Cold Starts (Free Plan)** | App duerme tras 15 min → Primera petición: 30-60s. Upgrade a Starter ($7/mes) para mantenerla activa |

---

### Costos de Render

| Plan | PostgreSQL | Web Service | Costo |
|------|------------|-------------|-------|
| **Free** | 1GB storage, expira 90 días inactividad | Duerme tras 15min | $0 |
| **Starter** | Backups automáticos | Siempre activo | $7/mes por servicio |

---

## 🔒 Seguridad - Checklist Producción

- [ ] `SECRET_KEY` generada aleatoriamente (32+ caracteres)
- [ ] `DOCS_PASSWORD` cambiada del default
- [ ] `DATABASE_URL` usando Internal URL (no External)
- [ ] `DATABASE_URL` con prefijo `postgresql+asyncpg://`
- [ ] `ENVIRONMENT=production`
- [ ] `MAILGUN_API_KEY` configurada
- [ ] `FRONTEND_URL` apuntando a dominio de producción
- [ ] CORS configurado solo para dominio frontend (`main.py`)
- [ ] HTTPS activado (Render lo hace automáticamente)
- [ ] Ambos servicios (BD y API) en la misma región

---

## 🔄 CI/CD con GitHub Actions

El proyecto ya tiene CI/CD configurado:

**Pipeline automático (`.github/workflows/ci_cd_pipeline.yml`):**
- ✅ Unit tests (Python 3.11, 3.12)
- ✅ Integration tests (PostgreSQL)
- ✅ Security scan (Gitleaks)
- ✅ Code quality (Ruff)
- ✅ Type checking (Mypy)
- ✅ Database migrations validation

**📋 Ver detalles:** [ADR-021](docs/architecture/decisions/ADR-021-github-actions-ci-cd-pipeline.md)

---

## 🛠️ Troubleshooting General

### Error: Connection refused (PostgreSQL)
- Verificar DATABASE_HOST apunta al servicio correcto
- Verificar PostgreSQL corriendo: `docker-compose ps`
- Revisar logs: `docker-compose logs db`

### Error: Alembic migrations failed
- Verificar DATABASE_URL
- Ejecutar manualmente: `docker-compose exec app alembic upgrade head`
- Ver estado: `docker-compose exec app alembic current`

### Error: CORS (405 Method Not Allowed)
- Verificar configuración CORS en `main.py`
- Añadir dominio frontend a `allow_origins`

### Puerto en uso
```bash
# Cambiar puerto en .env
PORT=8001

# Reconstruir
docker-compose up -d --build
```

---

## 📊 Monitoreo

### Docker Local
```bash
# Logs en tiempo real
docker-compose logs -f app

# Estado de servicios
docker-compose ps

# Shell interactivo
docker-compose exec app bash
```

### Render (Producción)
- **Logs:** Dashboard → `Logs`
- **Métricas:** Dashboard → `Metrics` (CPU, Memoria, Requests)
- **Eventos:** Dashboard → `Events` (Historial deploys)
- **Shell:** Dashboard → `Shell` (Ejecutar comandos)

---

## 🔗 Alternativas de Hosting

### Railway.app
- Auto-detección de Dockerfile
- PostgreSQL como plugin
- Auto-configura DATABASE_URL

### Fly.io
```bash
# Instalar flyctl
brew install flyctl

# Deploy
flyctl launch
flyctl postgres create
flyctl postgres attach <postgres-app-name>
flyctl deploy
```

---

## 📞 Soporte

Si encuentras problemas:
1. Revisar logs (`docker-compose logs -f`)
2. Verificar variables de entorno (`.env`)
3. Consultar troubleshooting arriba
4. Abrir issue en [GitHub](https://github.com/agustinEDev/RyderCupAM/issues)

---

**¡Tu API está lista para producción! 🚀**

**Última actualización:** 18 de Diciembre de 2025
**Versión:** 1.8.0
