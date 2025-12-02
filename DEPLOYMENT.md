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
