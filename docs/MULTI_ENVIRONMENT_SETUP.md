# 🌍 Configuración Multi-Entorno - RyderCupAm API

> **Guía completa para ejecutar el backend en 3 entornos diferentes**

---

## 📋 Resumen de Entornos

La API está preparada para ejecutarse en **3 modos**:

| Entorno | Descripción | Frontend URL | Uso |
|---------|-------------|--------------|-----|
| **Local (Directo)** | Desarrollo local con Vite standalone | `http://localhost:5173` | Desarrollo día a día |
| **Local (Kubernetes)** | Cluster Kind local con port-forward | `http://localhost:8080` | Testing de K8s antes de deploy |
| **Producción (Render)** | Deploy en Render.com | `https://rydercupfriends.com` | Aplicación en producción |

---

## 🔧 Entorno 1: Local (Desarrollo Directo)

### Descripción
Desarrollo local clásico con FastAPI y Vite corriendo directamente en tu máquina.

### Configuración

**Archivo `.env` (raíz del proyecto):**
```bash
# Frontend URL para enlaces de verificación
FRONTEND_URL=http://localhost:5173

# Mailgun (obtener de 1Password o .env.local)
MAILGUN_API_KEY=tu-api-key
MAILGUN_DOMAIN=rydercupfriends.com
MAILGUN_FROM_EMAIL="Ryder Cup Friends <noreply@rydercupfriends.com>"
MAILGUN_API_URL=https://api.eu.mailgun.net/v3

# Database (Docker Compose)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ryderclub

# JWT
SECRET_KEY=tu-secret-key-local
```

### Comandos

```bash
# 1. Activar entorno virtual
source .venv/bin/activate

# 2. Instalar dependencias (solo primera vez)
pip install -r requirements.txt

# 3. Levantar base de datos (Docker Compose)
docker-compose up -d db

# 4. Aplicar migraciones
alembic upgrade head

# 5. Ejecutar backend
uvicorn main:app --reload --port 8000

# 6. En otra terminal, ejecutar frontend (RyderCupWeb)
cd ../RyderCupWeb
npm run dev
```

### Verificación

✅ **Backend**: http://localhost:8000/docs
✅ **Frontend**: http://localhost:5173
✅ **Enlaces de email**: Apuntarán a `http://localhost:5173/verify-email?token=xxx`

---

## ☸️ Entorno 2: Local (Kubernetes con Kind)

### Descripción
Cluster de Kubernetes local usando Kind para simular un entorno de producción.

### Requisitos
- Docker Desktop instalado
- kubectl instalado
- Kind instalado

### Configuración

**Archivo `k8s/api-configmap.yaml` (línea 51):**
```yaml
FRONTEND_URL: "http://localhost:8080"
```

**Archivo `k8s/api-secret.yaml` (crear desde template):**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rydercup-api-secret
  namespace: rydercupfriends
type: Opaque
data:
  # Valores en Base64 (usar: echo -n "valor" | base64)
  MAILGUN_API_KEY: <tu-api-key-en-base64>
  SECRET_KEY: <tu-secret-key-en-base64>
  POSTGRES_PASSWORD: <tu-db-password-en-base64>
```

### Comandos

```bash
# 1. Crear cluster de Kind
cd k8s
./scripts/deploy-cluster.sh

# 2. Verificar que el cluster esté corriendo
kubectl get nodes

# 3. Crear namespace
kubectl apply -f namespace.yaml

# 4. Aplicar secrets (IMPORTANTE: Hazlo ANTES de los ConfigMaps)
kubectl apply -f api-secret.yaml

# 5. Aplicar ConfigMaps
kubectl apply -f api-configmap.yaml
kubectl apply -f frontend-configmap.yaml

# 6. Desplegar PostgreSQL
kubectl apply -f postgres-pvc.yaml
kubectl apply -f postgres-deployment.yaml
kubectl apply -f postgres-service.yaml

# 7. Desplegar API
kubectl apply -f api-deployment.yaml
kubectl apply -f api-service.yaml

# 8. Desplegar Frontend
kubectl apply -f frontend-deployment.yaml
kubectl apply -f frontend-service.yaml

# 9. Verificar que todos los pods estén corriendo
kubectl get pods -n rydercupfriends

# 10. Port-forward del frontend (TERMINAL 1)
kubectl port-forward svc/rydercup-frontend-service 8080:80 -n rydercupfriends

# 11. Port-forward del backend (TERMINAL 2 - solo si necesitas acceso directo)
kubectl port-forward svc/rydercup-api-service 8000:80 -n rydercupfriends
```

### Verificación

✅ **Frontend**: http://localhost:8080
✅ **Backend API docs**: http://localhost:8000/docs (si hiciste port-forward)
✅ **Enlaces de email**: Apuntarán a `http://localhost:8080/verify-email?token=xxx`

### Troubleshooting

**Problema**: Los enlaces de email siguen apuntando a `localhost:5173`

**Solución**:
```bash
# 1. Verificar que el ConfigMap esté correcto
kubectl get configmap rydercup-api-config -n rydercupfriends -o yaml | grep FRONTEND_URL

# 2. Si el valor es incorrecto, editar el ConfigMap
kubectl edit configmap rydercup-api-config -n rydercupfriends

# 3. Reiniciar el deployment para que lea la nueva configuración
kubectl rollout restart deployment rydercup-api -n rydercupfriends

# 4. Verificar que el pod se haya reiniciado
kubectl get pods -n rydercupfriends -w
```

---

## 🚀 Entorno 3: Producción (Render.com)

### Descripción
Aplicación desplegada en Render.com con PostgreSQL gestionado.

### Configuración en Render.com

**1. Backend (Web Service)**

Dashboard de Render → Servicio "rydercup-api" → Environment Variables:

```bash
# Frontend URL (CRÍTICO)
FRONTEND_URL=https://rydercupfriends.com

# Database (proporcionada automáticamente por Render)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Mailgun
MAILGUN_API_KEY=tu-api-key-produccion
MAILGUN_DOMAIN=rydercupfriends.com
MAILGUN_FROM_EMAIL="Ryder Cup Friends <noreply@rydercupfriends.com>"
MAILGUN_API_URL=https://api.eu.mailgun.net/v3

# JWT
SECRET_KEY=tu-secret-key-super-seguro-produccion
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Environment
ENVIRONMENT=production
PORT=8000

# Docs protection
DOCS_USERNAME=admin
DOCS_PASSWORD=tu-password-super-seguro
```

**2. Frontend (Static Site)**

Dashboard de Render → Servicio "rydercup-frontend" → Environment Variables:

```bash
VITE_API_BASE_URL=https://rydercup-api.onrender.com
```

### Despliegue

Render.com hace deploy automático en cada push a `main`:

```bash
# 1. Hacer cambios en tu código
git add .
git commit -m "fix: actualizar configuración de email verification"

# 2. Push a GitHub
git push origin main

# 3. Render detecta el push y hace deploy automático
# Monitorear en: https://dashboard.render.com
```

### Verificación

✅ **Frontend**: https://rydercupfriends.com
✅ **Backend API docs**: https://rydercup-api.onrender.com/docs
✅ **Enlaces de email**: Apuntarán a `https://rydercupfriends.com/verify-email?token=xxx`

### Monitoreo de Logs

```bash
# Ver logs en tiempo real desde Render Dashboard
# O usar Render CLI:
render logs -s rydercup-api
```

---

## 🔍 Verificación de Configuración

### Script de Verificación

Ejecuta este script para verificar tu configuración actual:

```bash
# Desde la raíz del proyecto
python k8s/scripts/check_config.py

# O desde el directorio k8s
cd k8s && python scripts/check_config.py
```

Esto mostrará:
- ✅ Variables de entorno cargadas
- ✅ FRONTEND_URL configurada
- ✅ Mailgun API disponible
- ✅ Base de datos accesible

### Verificación Manual

```bash
# Ver la configuración actual
python -c "from src.config.settings import settings; print(f'FRONTEND_URL: {settings.FRONTEND_URL}')"
```

---

## 🐛 Troubleshooting Común

### Problema 1: Enlaces de email apuntan a URL incorrecta

**Síntomas**: El email de verificación tiene un enlace como `http://localhost:5173/verify-email?token=xxx` pero estás en K8s o producción.

**Causa**: Variable `FRONTEND_URL` no está configurada correctamente.

**Solución**:
1. Verificar en qué entorno estás
2. Configurar `FRONTEND_URL` según la tabla del inicio
3. Reiniciar la aplicación (API backend)

### Problema 2: Emails no se envían

**Síntomas**: No llegan emails de verificación.

**Causa**: Mailgun API key incorrecta o no configurada.

**Solución**:
```bash
# Verificar que la API key esté configurada
python -c "from src.config.settings import settings; print('Mailgun configurado:', bool(settings.MAILGUN_API_KEY))"

# Verificar en logs del backend
# Deberías ver: "Email de verificación enviado correctamente"
# Si ves error: "MAILGUN_API_KEY no está configurada"
```

### Problema 3: Conflicto de puertos

**Síntomas**: Error "Address already in use" al ejecutar `uvicorn` o `kubectl port-forward`.

**Solución**:
```bash
# Ver qué proceso está usando el puerto 8000
lsof -i :8000

# Matar el proceso
kill -9 <PID>

# O cambiar el puerto
uvicorn main:app --reload --port 8001
```

---

## 📊 Resumen de Puertos

| Servicio | Local Directo | Local K8s | Producción |
|----------|---------------|-----------|------------|
| **Backend API** | 8000 | 8000 (port-forward) | 443 (HTTPS) |
| **Frontend** | 5173 | 8080 (port-forward) | 443 (HTTPS) |
| **PostgreSQL** | 5432 | 5432 (interno) | 5432 (Render) |

---

## 🔗 Referencias

- **Repositorio Backend**: `/Users/agustinestevezdominguez/Documents/RyderCupAm`
- **Repositorio Frontend**: `/Users/agustinestevezdominguez/Documents/RyderCupWeb`
- **Render Dashboard**: https://dashboard.render.com
- **Mailgun Dashboard**: https://app.mailgun.com
- **CLAUDE.md**: Documentación completa del proyecto

---

**Última actualización**: 5 Diciembre 2025
**Autor**: Agustín Estévez
