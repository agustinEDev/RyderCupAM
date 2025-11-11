Crea los prioritarios, pero sigue el formato de los que hay. Tienen que# 🚀 Deployment Guide - Ryder Cup Manager API

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

### **Opción 1: Render.com**

1. **Crear nuevo Web Service**
2. **Conectar repositorio GitHub**
3. **Configuración**:
   - **Build Command**: `docker build -t rydercup .`
   - **Start Command**: `/entrypoint.sh`
   - **Docker**: Activar

4. **Variables de Entorno** (en Render Dashboard):
   ```
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
   SECRET_KEY=your-secret-key
   DOCS_USERNAME=admin
   DOCS_PASSWORD=secure-password
   ENVIRONMENT=production
   PORT=8000
   ```

5. **PostgreSQL Database** (crear aparte):
   - Usar Render PostgreSQL o external DB
   - Copiar DATABASE_URL al Web Service

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
