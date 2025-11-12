# 🚀 Deployment a Render.com - Paso a Paso

## 📋 **Prerequisitos**
- Cuenta en [Render.com](https://render.com)
- Repositorio en GitHub con el código
- Git push realizado (última versión en GitHub)

---

## 🗄️ **PASO 1: Crear Base de Datos PostgreSQL**

1. **Ir a Render Dashboard** → `New` → `PostgreSQL`

2. **Configuración:**
   - **Name**: `rydercup-db` (o el nombre que prefieras)
   - **Database**: `ryderclub`
   - **User**: (auto-generado)
   - **Region**: `Oregon (US West)` (o el más cercano)
   - **PostgreSQL Version**: `15`
   - **Plan**: `Free` (para desarrollo)

3. **Crear** → Esperar a que esté disponible (1-2 minutos)

4. **⚠️ IMPORTANTE - Copiar credenciales:**
   - En la página de la BD, ir a **"Connections"**
   - Copiar **"Internal Database URL"** (empieza con `postgresql://...`)
   - Este URL se usará en el paso 2

   ```
   Ejemplo:
   postgresql://rydercup_db_user:XXXXX@dpg-xxxxx-a.oregon-postgres.render.com/rydercup_db
   ```

---

## 🌐 **PASO 2: Crear Web Service (API)**

1. **Dashboard** → `New` → `Web Service`

2. **Conectar GitHub:**
   - `Build and deploy from a Git repository`
   - Seleccionar tu repositorio `RyderCupAM`
   - Branch: `main` o `develop`

3. **Configuración Básica:**
   - **Name**: `rydercup-api`
   - **Region**: `Oregon (US West)` (mismo que la BD)
   - **Branch**: `main`
   - **Runtime**: `Docker` ⚠️ IMPORTANTE

4. **Plan:**
   - **Instance Type**: `Free` (para desarrollo)

5. **ANTES DE CREAR** → Ir a `Advanced` (abajo)

---

## 🔐 **PASO 3: Configurar Variables de Entorno**

En la sección **Environment Variables**, añadir:

```env
# Base de Datos (pegar el Internal Database URL del PASO 1)
DATABASE_URL=postgresql+asyncpg://user:pass@host.oregon-postgres.render.com/db_name

# ⚠️ IMPORTANTE: Cambiar 'postgresql://' por 'postgresql+asyncpg://'
# Render te da: postgresql://...
# Debes usar: postgresql+asyncpg://...

# JWT - Generar clave segura
SECRET_KEY=<generar-con-comando-abajo>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Documentación API
DOCS_USERNAME=admin
DOCS_PASSWORD=<contraseña-segura>

# Aplicación
PORT=8000
ENVIRONMENT=production

# Mailgun (Email Verification) - REQUERIDO desde v1.1
MAILGUN_API_KEY=<tu-api-key-de-mailgun>
MAILGUN_DOMAIN=rydercupfriends.com
MAILGUN_FROM_EMAIL=Ryder Cup Friends <noreply@rydercupfriends.com>
MAILGUN_API_URL=https://api.eu.mailgun.net/v3
FRONTEND_URL=https://www.rydercupfriends.com
```

**⚠️ IMPORTANTE - Email Verification:**
- Las variables `MAILGUN_*` son **obligatorias** para el sistema de verificación de email
- `FRONTEND_URL` debe apuntar a tu dominio frontend de producción
- Sin estas variables, el registro de usuarios funcionará pero no se enviarán emails de verificación


### 🔑 **Generar SECRET_KEY segura:**

```bash
# Opción 1: Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Opción 2: OpenSSL
openssl rand -base64 32

# Opción 3: Online
# https://randomkeygen.com/ (CodeIgniter Encryption Keys)
```

---

## 🎯 **PASO 4: Deploy**

1. **Crear Web Service** (botón abajo)

2. **Render automáticamente:**
   - ✅ Clona el repositorio
   - ✅ Detecta el `Dockerfile`
   - ✅ Construye la imagen Docker
   - ✅ Ejecuta `entrypoint.sh` que:
     - Espera a PostgreSQL (automático)
     - Ejecuta migraciones (`alembic upgrade head`)
     - Inicia la API

3. **Esperar deployment** (2-5 minutos primera vez)

4. **Ver logs en tiempo real:**
   - En la página del servicio → pestaña `Logs`
   - Deberías ver:
     ```
     🚀 Iniciando Ryder Cup Manager API...
     ✅ PostgreSQL está disponible
     🔄 Ejecutando migraciones de base de datos...
     ✅ Migraciones completadas exitosamente
     🎯 Iniciando aplicación FastAPI en puerto 8000...
     INFO: Started server process
     ```

---

## ✅ **PASO 5: Verificar Deployment**

### **Obtener URL:**
Tu API estará en: `https://rydercup-api.onrender.com`

### **Probar endpoints:**

```bash
# Health check
curl https://rydercup-api.onrender.com/

# Respuesta esperada:
{
  "message": "Ryder Cup Manager API",
  "version": "1.0.0",
  "status": "running"
}

# Docs (requiere autenticación)
https://rydercup-api.onrender.com/docs
```

---

## 🔄 **Actualizaciones Futuras**

Render hace **auto-deploy** cuando haces push a GitHub:

```bash
git add .
git commit -m "feat: nueva funcionalidad"
git push origin main
```

Render detecta el cambio y redeploya automáticamente.

### **Manual Re-deploy:**
- Dashboard del servicio → `Manual Deploy` → `Deploy latest commit`

---

## 🔍 **Troubleshooting**

### ❌ **Error: "Failed to connect to database"**

**Causa:** DATABASE_URL incorrecta

**Solución:**
1. Ir a PostgreSQL service → Connections
2. Copiar **Internal Database URL**
3. **IMPORTANTE:** Cambiar `postgresql://` por `postgresql+asyncpg://`
4. Actualizar variable de entorno en Web Service
5. Re-deploy

### ❌ **Error: "Alembic migrations failed"**

**Causa:** Primera vez que se ejecutan las migraciones

**Solución:**
1. Ir a Shell del Web Service
2. Ejecutar manualmente:
   ```bash
   alembic upgrade head
   ```
3. Re-deploy

### ❌ **Error: "Port already in use"**

**Causa:** Variable PORT incorrecta

**Solución:**
1. Asegurar que `PORT=8000` en variables de entorno
2. Re-deploy

### ⚠️ **Free Plan - Cold Starts**

El plan gratuito de Render "duerme" la app tras 15 minutos de inactividad.

**Primera petición después de sleep:**
- Puede tardar 30-60 segundos
- Luego funciona normal

**Solución** (si es problema):
- Upgrade a plan Starter ($7/mes)
- Mantiene app siempre activa

---

## 📊 **Monitoreo**

### **Logs en Tiempo Real:**
Dashboard → `Logs` → Ver output de la aplicación

### **Métricas:**
Dashboard → `Metrics` → CPU, Memoria, Requests

### **Eventos:**
Dashboard → `Events` → Historial de deploys

---

## 🔐 **Seguridad - Checklist**

Antes de usar en producción:

- [ ] `SECRET_KEY` generada aleatoriamente (32+ caracteres)
- [ ] `DOCS_PASSWORD` cambiada del default
- [ ] `DATABASE_URL` usando **Internal URL** (no External)
- [ ] `ENVIRONMENT=production`
- [ ] `MAILGUN_API_KEY` configurada con tu API key real
- [ ] `MAILGUN_FROM_EMAIL` con formato correcto (entre comillas si tiene espacios)
- [ ] `FRONTEND_URL` apuntando a tu dominio de producción (no localhost)
- [ ] CORS configurado solo para tu dominio frontend
- [ ] SSL/HTTPS activado (Render lo hace automáticamente)

---

## 💰 **Costos**

### **Free Tier:**
- PostgreSQL: 1GB storage, 90 días de inactividad
- Web Service: Duerme tras 15min inactividad, 750 horas/mes
- SSL gratuito
- **Costo total: $0**

### **Starter Tier ($7/mes):**
- Sin sleep
- Más recursos
- Backups automáticos

---

## 🆘 **Soporte**

- **Render Docs**: https://render.com/docs
- **Discord de Render**: https://render.com/community
- **Logs del servicio**: Primera fuente de debugging

---

## ✨ **¡Listo!**

Tu API está desplegada en:
- **API**: `https://rydercup-api.onrender.com`
- **Docs**: `https://rydercup-api.onrender.com/docs`
- **Base de Datos**: Gestionada y separada en Render PostgreSQL

**Auto-deploy** activado → Git push = Nuevo deploy automático 🚀
