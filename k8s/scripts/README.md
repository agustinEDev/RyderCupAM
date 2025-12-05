# 🛠️ Scripts de Kubernetes - Ryder Cup Friends

Scripts de automatización para gestionar el cluster de Kubernetes.

---

## 📜 Scripts Disponibles

### 1. `deploy-cluster.sh` - Deployment Automático

Despliega la aplicación completa en Kubernetes con un solo comando.

**Uso:**
```bash
./scripts/deploy-cluster.sh
```

**Lo que hace:**
- ✅ Verifica prerrequisitos (Docker, kubectl, Kind)
- ✅ Crea el cluster Kind (o usa uno existente)
- ✅ Aplica ConfigMaps y Secrets
- ✅ Crea almacenamiento persistente (PVC)
- ✅ Despliega PostgreSQL
- ✅ Despliega Backend (FastAPI)
- ✅ Despliega Frontend (React + nginx)
- ✅ Espera a que todos los pods estén listos
- ✅ Muestra instrucciones para acceder

**Tiempo estimado:** ~3-5 minutos

---

### 2. `deploy-api.sh` - Actualizar Backend API

Actualiza solo el backend (API) con los últimos cambios de código, reconstruyendo y desplegando la imagen Docker.

**Uso:**
```bash
# Actualizar con tag "latest"
./scripts/deploy-api.sh

# Actualizar con versión específica
./scripts/deploy-api.sh v1.0.1
```

**Lo que hace:**
- ✅ Verifica prerrequisitos (Docker, kubectl, cluster)
- ✅ Construye nueva imagen Docker del backend
- ✅ Sube la imagen a Docker Hub
- ✅ Actualiza el deployment en Kubernetes
- ✅ Realiza rolling update sin downtime
- ✅ Espera a que todos los pods estén listos
- ✅ Muestra logs y estado final

**Características:**
- 🔄 **Rolling update:** Mantiene alta disponibilidad (cero downtime)
- 🎨 **Output colorizado:** Fácil de seguir el proceso
- ✅ **Validaciones:** Verifica cada paso antes de continuar
- 📊 **Verificación post-deployment:** Muestra estado de pods y logs
- ↩️ **Rollback fácil:** Incluye comando para deshacer cambios

**Cuándo usarlo:**
- Después de hacer cambios en el código del backend
- Para desplegar correcciones de bugs
- Para actualizar dependencias de Python
- Para desplegar nuevas features del API

**Tiempo estimado:** ~2-4 minutos (depende de la conexión a Docker Hub)

**Ejemplo de output:**
```
🚀 ==================================================
   Ryder Cup Manager - API Deployment
   ==================================================

Docker Image: agustinedev/rydercupam-app:latest
Deployment:   rydercup-api
Container:    fastapi

¿Continuar con el deployment? (y/n) y

━━ Verificando prerrequisitos... ━━
✅ Docker: OK
✅ kubectl: OK
✅ Cluster: OK
✅ Deployment 'rydercup-api': OK

━━ Construyendo imagen Docker... ━━
✅ Imagen construida exitosamente

━━ Subiendo imagen a Docker Hub... ━━
✅ Imagen subida exitosamente

━━ Actualizando deployment en Kubernetes... ━━
✅ Comando de actualización ejecutado

━━ Esperando a que se complete el rollout... ━━
✅ Rollout completado exitosamente

🎉 ¡Deployment completado con éxito! 🎉
```

---

### 3. `cluster-status.sh` - Diagnóstico Completo

Muestra el estado completo del cluster de forma visual.

**Uso:**
```bash
./scripts/cluster-status.sh
```

**Lo que muestra:**
- 📊 Información del cluster
- 🖥️ Estado de los nodos
- 📦 Estado de todos los pods
- 🌐 Services y endpoints
- 🚀 Deployments y réplicas
- ⚙️ ConfigMaps y Secrets
- 💾 Almacenamiento persistente
- 📋 Eventos recientes
- ❤️ Health checks (backend + frontend)
- 🔌 Port-forwards activos
- 📊 Resumen general

**Cuándo usarlo:**
- Para verificar que todo está corriendo
- Para diagnosticar problemas
- Para ver el estado antes/después de cambios

---

### 4. `start-port-forwards.sh` - Iniciar Port-Forwards

Inicia automáticamente los port-forwards necesarios para acceder a la aplicación.

**Uso:**
```bash
./scripts/start-port-forwards.sh
```

**Lo que hace:**
- ✅ Inicia port-forward del backend (8000:80)
- ✅ Inicia port-forward del frontend (8080:80)
- ✅ Corre en background
- ✅ Guarda PIDs para poder detenerlos después

---

### 5. `stop-port-forwards.sh` - Detener Port-Forwards

Detiene todos los port-forwards activos.

**Uso:**
```bash
./scripts/stop-port-forwards.sh
```

---

### 6. `destroy-cluster.sh` - Eliminación del Cluster

Elimina completamente el cluster de Kubernetes.

**Uso:**
```bash
./scripts/destroy-cluster.sh
```

**Lo que hace:**
- ⚠️ Pide confirmación
- 🗑️ Elimina el cluster completo
- 🐳 Opcionalmente elimina imágenes Docker de Kind

**⚠️ ADVERTENCIA:** Esta acción eliminará:
- Todos los pods
- Todos los datos de PostgreSQL
- Todas las configuraciones
- El cluster completo

---

## 🚀 Flujo de Trabajo Típico

### Primer Uso

```bash
# 1. Desplegar el cluster completo
./scripts/deploy-cluster.sh

# 2. Verificar que todo está corriendo
./scripts/cluster-status.sh

# 3. Iniciar port-forwards
./scripts/start-port-forwards.sh

# 4. Abrir navegador
open http://localhost:8080
```

### Actualizar Backend (Después de Hacer Cambios en el Código)

```bash
# 1. Haz tus cambios en el código del backend
vim main.py  # o cualquier archivo

# 2. Despliega la actualización
./scripts/deploy-api.sh

# 3. Verifica que la actualización funcionó
./scripts/cluster-status.sh

# 4. Revisa los logs si es necesario
kubectl logs deployment/rydercup-api -f
```

### Verificación Diaria

```bash
# Ver estado rápido
./scripts/cluster-status.sh

# Ver logs en tiempo real
kubectl logs -f deployment/rydercup-frontend
kubectl logs -f deployment/rydercup-api

# Verificar endpoints
curl http://localhost:8000/
curl http://localhost:8080/health
```

### Rollback si Algo Sale Mal

```bash
# Ver historial de deployments
kubectl rollout history deployment/rydercup-api

# Volver a la versión anterior
kubectl rollout undo deployment/rydercup-api

# Verificar que el rollback funcionó
./scripts/cluster-status.sh
```

### Limpieza

```bash
# Detener port-forwards
./scripts/stop-port-forwards.sh

# Eliminar cluster completo
./scripts/destroy-cluster.sh
```

---

## 📚 Documentación Adicional

- **Guía Completa:** `docs/KUBERNETES_DEPLOYMENT_GUIDE.md` (80+ páginas)
- **Guía Rápida:** `docs/KUBERNETES_QUICK_START.md` (referencia de 1 página)

---

## 🛠️ Personalización

### Modificar el Nombre del Cluster

Edita la variable `CLUSTER_NAME` en cada script:

```bash
CLUSTER_NAME="mi-cluster-custom"
```

### Añadir Más Verificaciones a cluster-status.sh

El script `cluster-status.sh` es modular, puedes añadir secciones adicionales:

```bash
# ==========================================
# X. Nueva sección
# ==========================================
print_header "🆕 MI NUEVA SECCIÓN"

# Tu código aquí
```

---

## 🐛 Troubleshooting

### Script falla con "Permission denied"

```bash
# Hacer los scripts ejecutables
chmod +x scripts/*.sh
```

### Script falla con "docker: command not found"

Asegúrate de que Docker Desktop está instalado y corriendo:

```bash
docker --version
docker info
```

### Script falla con "cluster already exists"

El script `deploy-cluster.sh` detecta clusters existentes y pregunta si quieres eliminarlo.

Si quieres forzar recreación:

```bash
kind delete cluster --name rydercupam-cluster
./scripts/deploy-cluster.sh
```

---

## 📝 Notas

- Todos los scripts usan `set -e` para detenerse ante el primer error
- Los scripts colorean la salida para mejor legibilidad
- Los scripts son idempotentes (puedes ejecutarlos múltiples veces)

---

**Última actualización:** 3 Diciembre 2025
