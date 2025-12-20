# 🚀 Guía de Deployment en Kubernetes - Ryder Cup Manager

**Stack:** React + FastAPI + PostgreSQL + Kubernetes (Kind)
**Última actualización:** 3 Diciembre 2025

---

## 📊 Resumen Ejecutivo

### Componentes Desplegados

- ✅ **Frontend:** React 18 + Vite 5 + nginx (2 réplicas)
- ✅ **Backend:** FastAPI + Python 3.11 (2 réplicas)
- ✅ **Database:** PostgreSQL 15 con almacenamiento persistente (10Gi)

### Características

- Alta disponibilidad (múltiples réplicas)
- Rolling updates sin downtime
- Health checks automáticos (liveness + readiness)
- Configuración dinámica (ConfigMaps + Secrets)
- Almacenamiento persistente para BD
- Runtime configuration para multi-entorno

### Estadísticas

```
📦 Recursos Kubernetes:
   • 1 Cluster Kind
   • 3 Deployments
   • 5 Pods (1 postgres + 2 api + 2 frontend)
   • 3 Services (1 ClusterIP + 2 LoadBalancer)
   • 2 ConfigMaps + 1 Secret
   • 1 PersistentVolumeClaim (10Gi)

🐳 Imágenes Docker:
   • agustinedev/rydercupam-app:latest (Backend)
   • agustinedev/rydercupam-web:latest (Frontend)
   • postgres:15 (Database)
```

---

## 🏗️ Arquitectura

### Flujo de Datos

```
Usuario (Navegador)
    ↓ http://localhost:8080
Port-forward (Frontend)
    ↓ port 8080 → Service:80
Frontend Service (LoadBalancer)
    ↓ Load Balancing
Frontend Pods (2 réplicas)
    ↓ API calls (http://localhost:8000)
Port-forward (Backend)
    ↓ port 8000 → Service:80
Backend Service (LoadBalancer)
    ↓ Load Balancing
Backend Pods (2 réplicas)
    ↓ SQL queries (postgres-service:5432)
PostgreSQL Service (ClusterIP)
    ↓ DNS interno
PostgreSQL Pod + PersistentVolume (10Gi)
```

---

## ✅ Prerrequisitos

### Software Requerido

| Software | Versión Mínima | Verificar |
|----------|----------------|-----------|
| Docker Desktop | 24.0+ | `docker --version` |
| kubectl | 1.28+ | `kubectl version --client` |
| Kind | 0.20+ | `kind version` |
| Git | 2.30+ | `git --version` |

### Verificación Rápida

```bash
docker --version && kubectl version --client && kind version
```

---

## 🚀 Deployment Paso a Paso

### 1. Crear Cluster Kind

```bash
# Crear cluster
kind create cluster --name rydercupam-cluster

# Verificar
kind get clusters
kubectl cluster-info --context kind-rydercupam-cluster
```

### 2. Aplicar ConfigMaps y Secrets

```bash
cd k8s/

# ConfigMaps (variables públicas)
kubectl apply -f api-configmap.yaml
kubectl apply -f frontend-configmap.yaml

# Secrets (credenciales sensibles)
kubectl apply -f api-secret.yaml

# Verificar
kubectl get configmaps
kubectl get secrets
```

### 3. Crear Almacenamiento Persistente

```bash
# PersistentVolumeClaim para PostgreSQL
kubectl apply -f postgres-pvc.yaml

# Verificar
kubectl get pvc
```

### 4. Desplegar PostgreSQL

```bash
# Deployment + Service
kubectl apply -f postgres-deployment.yaml
kubectl apply -f postgres-service.yaml

# Esperar a que esté listo
kubectl wait --for=condition=ready pod -l component=database --timeout=60s

# Verificar
kubectl get pods -l component=database
```

### 5. Desplegar Backend (FastAPI)

```bash
# Deployment + Service
kubectl apply -f api-deployment.yaml
kubectl apply -f api-service.yaml

# Esperar a que esté listo (2 réplicas)
kubectl wait --for=condition=ready pod -l component=api --timeout=120s

# Verificar
kubectl get pods -l component=api
```

### 6. Desplegar Frontend (React)

```bash
# Deployment + Service
kubectl apply -f frontend-deployment.yaml
kubectl apply -f frontend-service.yaml

# Esperar a que esté listo (2 réplicas)
kubectl wait --for=condition=ready pod -l component=frontend --timeout=60s

# Verificar
kubectl get pods -l component=frontend
```

### 7. Verificar Deployment Completo

```bash
# Ver todos los recursos
kubectl get all -l app=rydercup

# Ver pods
kubectl get pods

# Ver services
kubectl get svc
```

**Resultado esperado:**
- 5 pods en estado `Running`
- 3 services activos

---

## 🌐 Acceder a la Aplicación

### Establecer Port-Forwards

```bash
# Frontend (puerto 8080)
kubectl port-forward service/rydercup-frontend-service 8080:80 &

# Backend (puerto 8000)
kubectl port-forward service/rydercup-api-service 8000:80 &

# Verificar procesos
jobs
```

### Acceso

- **Frontend:** http://localhost:8080
- **Backend API:** http://localhost:8000
- **Swagger UI:** http://localhost:8000/docs

### Detener Port-Forwards

```bash
# Listar procesos en background
jobs

# Matar proceso específico (ej: [1], [2])
kill %1 %2

# O matar todos los port-forwards
pkill -f "kubectl port-forward"
```

---

## 📋 Comandos Importantes

### Ver Estado del Cluster

| Comando | Descripción |
|---------|-------------|
| `kubectl get pods` | Ver todos los pods |
| `kubectl get svc` | Ver todos los services |
| `kubectl get all -l app=rydercup` | Ver recursos del proyecto |
| `kubectl describe pod <nombre>` | Detalles de un pod |
| `kubectl logs <nombre-pod>` | Ver logs de un pod |
| `kubectl logs -l component=api --tail=50` | Logs de todos los pods del backend |

### Gestión de Pods

```bash
# Reiniciar deployment
kubectl rollout restart deployment/rydercup-api

# Ver status de rollout
kubectl rollout status deployment/rydercup-api

# Ver historial de deploys
kubectl rollout history deployment/rydercup-api
```

### Acceso Directo a Pods

```bash
# Shell interactivo en pod del backend
kubectl exec -it <nombre-pod-api> -- bash

# Ejecutar comando específico
kubectl exec <nombre-pod-api> -- alembic current

# Shell en PostgreSQL
kubectl exec -it <nombre-pod-postgres> -- psql -U rydercupam_adminuser -d rydercupam_db
```

### Actualizar Configuración

```bash
# Editar ConfigMap
kubectl edit configmap rydercup-api-config

# Reiniciar para aplicar cambios
kubectl rollout restart deployment/rydercup-api
```

---

## 🛠️ Troubleshooting

### Problemas Comunes

| Error | Solución |
|-------|----------|
| **Pod en CrashLoopBackOff** | `kubectl logs <pod>` → Verificar errores en la aplicación |
| **ImagePullBackOff** | Verificar que las imágenes existen en Docker Hub |
| **Pending (PVC)** | Verificar que el PVC está en estado `Bound` |
| **Backend no conecta a BD** | Verificar que postgres pod está `Running` antes de desplegar backend |
| **Port-forward ya en uso** | `lsof -ti:8000 \| xargs kill -9` (matar proceso en puerto) |

### Ver Logs de Errores

```bash
# Logs de todos los pods del backend
kubectl logs -l component=api --tail=100

# Logs de un pod específico
kubectl logs <nombre-pod> --previous  # Ver logs del contenedor anterior

# Seguir logs en tiempo real
kubectl logs -f <nombre-pod>
```

### Verificar Recursos

```bash
# Ver uso de recursos
kubectl top pods

# Describir pod con problemas
kubectl describe pod <nombre-pod>

# Ver eventos del cluster
kubectl get events --sort-by='.lastTimestamp'
```

---

## 🔄 Gestión del Cluster

### Escalar Deployments

```bash
# Escalar backend a 3 réplicas
kubectl scale deployment/rydercup-api --replicas=3

# Escalar frontend a 1 réplica
kubectl scale deployment/rydercup-frontend --replicas=1

# Verificar
kubectl get pods
```

### Actualizar Imágenes

```bash
# Actualizar imagen del backend
kubectl set image deployment/rydercup-api \
  rydercup-api=agustinedev/rydercupam-app:v2.0.0

# Verificar rollout
kubectl rollout status deployment/rydercup-api

# Rollback si hay problemas
kubectl rollout undo deployment/rydercup-api
```

### Backup de Base de Datos

```bash
# Encontrar nombre del pod de PostgreSQL
kubectl get pods -l component=database

# Crear backup
kubectl exec <nombre-pod-postgres> -- \
  pg_dump -U rydercupam_adminuser rydercupam_db > backup_$(date +%Y%m%d).sql

# Restore desde backup
kubectl exec -i <nombre-pod-postgres> -- \
  psql -U rydercupam_adminuser -d rydercupam_db < backup.sql
```

---

## 🗑️ Eliminación del Cluster

### Opción 1: Eliminar Recursos (conservar cluster)

```bash
# Eliminar solo los recursos de la aplicación
kubectl delete all -l app=rydercup
kubectl delete pvc postgres-pvc
kubectl delete configmap rydercup-api-config rydercup-frontend-config
kubectl delete secret rydercup-api-secret
```

### Opción 2: Eliminar Cluster Completo

```bash
# Eliminar cluster de Kind
kind delete cluster --name rydercupam-cluster

# Verificar eliminación
kind get clusters
```

---

## 📊 Monitoreo

### Dashboard de Kubernetes (Opcional)

```bash
# Instalar dashboard
kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.7.0/aio/deploy/recommended.yaml

# Crear usuario admin
kubectl create serviceaccount dashboard-admin -n kubernetes-dashboard
kubectl create clusterrolebinding dashboard-admin --clusterrole=cluster-admin --serviceaccount=kubernetes-dashboard:dashboard-admin

# Obtener token
kubectl -n kubernetes-dashboard create token dashboard-admin

# Port-forward del dashboard
kubectl port-forward -n kubernetes-dashboard service/kubernetes-dashboard 8443:443

# Acceder: https://localhost:8443
```

### Logs Centralizados

```bash
# Ver logs de todos los componentes
kubectl logs -l app=rydercup --tail=20 --all-containers=true

# Filtrar por componente
kubectl logs -l component=api --tail=50
kubectl logs -l component=frontend --tail=50
kubectl logs -l component=database --tail=50
```

---

## 🎯 Script Automatizado de Deploy

Existe un script que automatiza todo el proceso:

```bash
# Ejecutar desde el directorio raíz del proyecto
cd k8s/
./scripts/deploy-cluster.sh
```

**El script realiza:**
1. ✅ Verifica prerrequisitos
2. ✅ Crea cluster Kind (si no existe)
3. ✅ Crea namespace
4. ✅ Aplica ConfigMaps y Secrets
5. ✅ Pregunta si construir imágenes Docker
6. ✅ Despliega PostgreSQL, Backend y Frontend
7. ✅ Verifica que todo esté corriendo

**📋 Ver script:** `k8s/scripts/deploy-cluster.sh`

---

## 🔗 Referencias

### Documentación Kubernetes
- **kubectl cheatsheet:** https://kubernetes.io/docs/reference/kubectl/cheatsheet/
- **Kind docs:** https://kind.sigs.k8s.io/docs/user/quick-start/
- **ConfigMaps:** https://kubernetes.io/docs/concepts/configuration/configmap/
- **Secrets:** https://kubernetes.io/docs/concepts/configuration/secret/

### Documentación del Proyecto
- **Multi-Environment Setup:** `docs/MULTI_ENVIRONMENT_SETUP.md`
- **Deployment (Docker):** `DEPLOYMENT.md`
- **API Reference:** `docs/API.md`

---

## 💡 Tips y Best Practices

### Desarrollo

- Usa port-forwards para desarrollo local
- Mantén ConfigMaps actualizados con valores de desarrollo
- No commitees Secrets a Git

### Producción

- Usa Ingress en lugar de port-forwards
- Configura límites de recursos apropiados
- Implementa monitoreo (Prometheus + Grafana)
- Configura backups automáticos de PostgreSQL
- Usa Secrets externos (Vault, AWS Secrets Manager)

### Debugging

- Siempre verifica logs primero: `kubectl logs`
- Usa `kubectl describe` para ver eventos y configuración
- Verifica conectividad entre pods con `kubectl exec`

---

**¡Deployment exitoso en Kubernetes! 🎉**

**Última actualización:** 3 de Diciembre de 2025
**Versión:** 1.0.0
