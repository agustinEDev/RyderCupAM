# 🛠️ Scripts de Kubernetes - Ryder Cup Manager

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

### 2. `cluster-status.sh` - Diagnóstico Completo

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

### 3. `destroy-cluster.sh` - Eliminación del Cluster

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
# 1. Desplegar el cluster
./scripts/deploy-cluster.sh

# 2. En otra terminal, verificar estado
./scripts/cluster-status.sh

# 3. Exponer servicios (2 terminales)
kubectl port-forward svc/rydercup-api-service 8000:80     # Terminal 1
kubectl port-forward svc/rydercup-frontend-service 8080:80 # Terminal 2

# 4. Abrir navegador
open http://localhost:8080
```

### Verificación Diaria

```bash
# Ver estado rápido
./scripts/cluster-status.sh

# Ver logs
kubectl logs -f deployment/rydercup-frontend
kubectl logs -f deployment/rydercup-api
```

### Limpieza

```bash
# Eliminar cluster
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
