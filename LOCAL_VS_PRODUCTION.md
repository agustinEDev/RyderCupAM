# 🎯 Guía Rápida: Local vs Producción

## 🏠 **DESARROLLO LOCAL (con Docker Compose)**

### Setup:
```bash
# 1. Copiar configuración local
cp .env.local .env

# 2. Levantar servicios (BD + API)
docker-compose up -d --build

# 3. Ver logs
docker-compose logs -f app
```

### ✅ Qué hace automáticamente:
- Crea contenedor PostgreSQL
- Espera a que la BD esté lista
- Ejecuta migraciones con Alembic
- Inicia la API en http://localhost:8000

### 🛑 Para detener:
```bash
docker-compose down
```

---

## ☁️ **PRODUCCIÓN (Render, Railway, Fly.io)**

### Setup en Render.com (Ejemplo):

#### 1️⃣ Crear PostgreSQL Database
- New → PostgreSQL
- Copiar `Internal Database URL`

#### 2️⃣ Crear Web Service
- New → Web Service
- Conectar repositorio GitHub
- **Runtime**: Docker
- **Build Command**: (vacío, usa Dockerfile)
- **Start Command**: (vacío, usa entrypoint.sh)

#### 3️⃣ Variables de Entorno (Dashboard)
```env
DATABASE_URL=<pegar-internal-database-url-de-render>
SECRET_KEY=<generar-aleatorio-32-chars>
DOCS_USERNAME=admin
DOCS_PASSWORD=<contraseña-segura>
ENVIRONMENT=production
PORT=8000
```

#### 4️⃣ Deploy
- Render auto-detecta cambios en GitHub
- Ejecuta Dockerfile
- `entrypoint.sh` hace:
  ✅ Verifica BD externa (sin esperar con nc)
  ✅ Ejecuta migraciones
  ✅ Inicia API

---

## 🔄 **DIFERENCIAS CLAVE**

| Aspecto | Local (Docker Compose) | Producción (Hosting) |
|---------|------------------------|----------------------|
| **Base de Datos** | Contenedor PostgreSQL | BD Externa (managed) |
| **DATABASE_HOST** | `db` (servicio Docker) | No se usa |
| **DATABASE_URL** | Auto-generada | Proporcionada por hosting |
| **Migraciones** | Automáticas | Automáticas |
| **Archivos** | `.env.local` → `.env` | Variables en Dashboard |
| **Deployment** | `docker-compose up` | Git push → auto-deploy |

---

## 🚨 **IMPORTANTE**

### Local:
- ✅ Usa `.env.local` como plantilla
- ✅ Puedes usar contraseñas simples
- ✅ `ENVIRONMENT=development` permite CORS `*`

### Producción:
- ⚠️ Usa `.env.production` como guía
- ⚠️ Genera `SECRET_KEY` aleatoria
- ⚠️ Usa contraseñas fuertes
- ⚠️ `ENVIRONMENT=production` limita CORS
- ⚠️ **NUNCA** commitees `.env` real al repo

---

## 📝 **CHECKLIST PRE-DEPLOY**

### Antes de subir a producción:
- [ ] `SECRET_KEY` generada aleatoriamente
- [ ] `DOCS_PASSWORD` cambiada de default
- [ ] `DATABASE_URL` configurada correctamente
- [ ] `ENVIRONMENT=production`
- [ ] Variables sensibles NO en el código
- [ ] `.env` en `.gitignore`
- [ ] Migraciones testeadas localmente

---

## 🔍 **VERIFICACIÓN**

### Local:
```bash
curl http://localhost:8000/
```

### Producción:
```bash
curl https://tu-app.onrender.com/
```

Ambos deberían responder:
```json
{
  "message": "Ryder Cup Manager API",
  "version": "1.0.0",
  "status": "running"
}
```

---

## 🆘 **TROUBLESHOOTING**

### "Connection refused" en producción
- ✅ Verifica `DATABASE_URL` en variables de entorno
- ✅ Asegúrate que la BD externa esté activa
- ✅ Revisa logs del hosting

### "Migraciones fallan"
- ✅ Verifica que Alembic esté en `requirements.txt`
- ✅ Comprueba permisos de la BD
- ✅ Revisa logs: pueden mostrar error SQL específico

### "CORS error" en producción
- ✅ Configura `ENVIRONMENT=production` en variables
- ✅ Añade tu dominio frontend a `allow_origins` en `main.py`

---

**Resumen: Mismo Dockerfile funciona en ambos, solo cambian las variables de entorno! 🎉**
