# 🚀 Guía de Deployment en Kubernetes - Ryder Cup Manager

**Versión:** 1.0.0
**Última actualización:** 3 Diciembre 2025
**Stack:** React + FastAPI + PostgreSQL + Kubernetes (Kind)

---

## 📋 Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Arquitectura](#arquitectura)
3. [Prerrequisitos](#prerrequisitos)
4. [Paso a Paso: Levantar el Cluster](#paso-a-paso-levantar-el-cluster)
5. [Verificación del Deployment](#verificación-del-deployment)
6. [Acceder a la Aplicación](#acceder-a-la-aplicación)
7. [Comandos Importantes](#comandos-importantes)
8. [Troubleshooting](#troubleshooting)
9. [Gestión del Cluster](#gestión-del-cluster)
10. [Eliminación del Cluster](#eliminación-del-cluster)

---

## 📊 Resumen Ejecutivo

### ¿Qué Hemos Construido?

Hemos desplegado exitosamente la aplicación **Ryder Cup Manager** (fullstack) en un cluster de Kubernetes local usando **Kind**.

**Componentes desplegados:**
- ✅ **Frontend:** React 18 + Vite 5 + nginx (2 réplicas)
- ✅ **Backend:** FastAPI + Python 3.11 (2 réplicas)
- ✅ **Database:** PostgreSQL 15 con almacenamiento persistente (10Gi)

**Características implementadas:**
- ✅ Alta disponibilidad (múltiples réplicas)
- ✅ Rolling updates sin downtime
- ✅ Health checks automáticos (liveness + readiness)
- ✅ Configuración dinámica (ConfigMaps + Secrets)
- ✅ Almacenamiento persistente para la base de datos
- ✅ Runtime configuration para multi-entorno
- ✅ CORS configurado correctamente

### Estadísticas del Deployment

```
📦 Recursos Kubernetes:
   • 1 Cluster Kind
   • 3 Deployments
   • 5 Pods (1 postgres + 2 api + 2 frontend)
   • 3 Services (1 ClusterIP + 2 LoadBalancer)
   • 2 ConfigMaps
   • 1 Secret
   • 1 PersistentVolumeClaim (10Gi)

🐳 Imágenes Docker:
   • agustinedev/rydercupam-app:latest (Backend)
   • agustinedev/rydercupam-web:latest (Frontend)
   • postgres:15 (Database)

📂 Manifiestos:
   • 10 archivos YAML (k8s/)
```

### Mejoras Aplicadas al Código

#### Frontend (`src/services/api.js`)
```javascript
// Runtime configuration support
const API_URL = window.APP_CONFIG?.API_BASE_URL
  || import.meta.env.VITE_API_BASE_URL
  || 'http://localhost:8000';
```

**Ventaja:** Una imagen Docker funciona en múltiples entornos (dev, staging, prod) sin recompilar.

#### Backend (`main.py`)
```python
# CORS support para Kubernetes port-forward
allowed_origins.extend([
    "http://localhost:8080",   # Kubernetes port-forward
    "http://127.0.0.1:8080",
])
```

**Ventaja:** El frontend puede comunicarse con el backend mediante port-forward.

---

## 🏗️ Arquitectura

### Arquitectura de Kubernetes

```
┌─────────────────────────────────────────────────────────────┐
│                      INTERNET / LOCALHOST                   │
└─────────────────────────────────────────────────────────────┘
         ↓ port-forward 8080          ↓ port-forward 8000
┌─────────────────────────────────────────────────────────────┐
│              KUBERNETES CLUSTER (Kind)                      │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Service: rydercup-frontend-service (LoadBalancer)    │ │
│  │  ClusterIP: 10.96.235.251  Port: 80                   │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                  │
│  ┌─────────────────────┐      ┌─────────────────────┐     │
│  │ Frontend Pod 1      │      │ Frontend Pod 2      │     │
│  │ nginx + React       │      │ nginx + React       │     │
│  │ RAM: 256Mi-512Mi    │      │ RAM: 256Mi-512Mi    │     │
│  │ CPU: 250m-500m      │      │ CPU: 250m-500m      │     │
│  └─────────────────────┘      └─────────────────────┘     │
│                          ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Service: rydercup-api-service (LoadBalancer)         │ │
│  │  ClusterIP: 10.96.208.7  Port: 80                     │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                  │
│  ┌─────────────────────┐      ┌─────────────────────┐     │
│  │ Backend Pod 1       │      │ Backend Pod 2       │     │
│  │ FastAPI             │      │ FastAPI             │     │
│  │ RAM: 512Mi-1Gi      │      │ RAM: 512Mi-1Gi      │     │
│  │ CPU: 500m-1000m     │      │ CPU: 500m-1000m     │     │
│  └─────────────────────┘      └─────────────────────┘     │
│                          ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Service: postgres-service (ClusterIP - Interno)      │ │
│  │  ClusterIP: 10.96.157.225  Port: 5432                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ PostgreSQL Pod                                         │ │
│  │ RAM: 512Mi-1Gi                                         │ │
│  │ CPU: 500m-1000m                                        │ │
│  │ Volume: postgres-pvc (10Gi)                            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Flujo de Datos

```
Usuario (Navegador)
    ↓ http://localhost:8080
Port-forward (Frontend)
    ↓ port 8080 → Service:80
Frontend Service (LoadBalancer)
    ↓ Load Balancing
Frontend Pods (2 réplicas)
    ↓ fetch("http://localhost:8000/api/...")
Port-forward (Backend)
    ↓ port 8000 → Service:80
Backend Service (LoadBalancer)
    ↓ Load Balancing
Backend Pods (2 réplicas)
    ↓ SQL queries (postgres-service:5432)
PostgreSQL Service (ClusterIP)
    ↓ DNS interno
PostgreSQL Pod
    ↓ Persistent Storage
PersistentVolume (10Gi)
```

---

## ✅ Prerrequisitos

### Software Requerido

| Software | Versión Mínima | Comando de Verificación |
|----------|----------------|-------------------------|
| Docker Desktop | 24.0+ | `docker --version` |
| kubectl | 1.28+ | `kubectl version --client` |
| Kind | 0.20+ | `kind version` |
| Git | 2.30+ | `git --version` |

### Verificar Instalación

```bash
# Verificar Docker
docker --version
docker ps

# Verificar kubectl
kubectl version --client

# Verificar Kind
kind version

# Verificar que Docker Desktop está corriendo
docker info
```

### Clonar Repositorio (si no lo tienes)

```bash
git clone https://github.com/agustinedev/rydercupam.git
cd rydercupam
```

---

## 🚀 Paso a Paso: Levantar el Cluster

### Paso 1: Crear el Cluster Kind

```bash
# Crear cluster con nombre "rydercupam-cluster"
kind create cluster --name rydercupam-cluster

# Verificar que el cluster fue creado
kind get clusters

# Verificar que kubectl está conectado al cluster correcto
kubectl cluster-info --context kind-rydercupam-cluster
```

**Salida esperada:**
```
Creating cluster "rydercupam-cluster" ...
 ✓ Ensuring node image (kindest/node:v1.27.3) 🖼
 ✓ Preparing nodes 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
Set kubectl context to "kind-rydercupam-cluster"
```

---

### Paso 2: Aplicar ConfigMaps y Secrets

**IMPORTANTE:** Aplicar en este orden para evitar errores de dependencias.

```bash
# Navegar al directorio de manifiestos
cd k8s/

# 1. ConfigMaps (variables públicas)
kubectl apply -f api-configmap.yaml
kubectl apply -f frontend-configmap.yaml

# 2. Secrets (credenciales sensibles)
kubectl apply -f api-secret.yaml

# Verificar que fueron creados
kubectl get configmaps
kubectl get secrets
```

**Salida esperada:**
```
configmap/rydercup-api-config created
configmap/rydercup-frontend-config created
secret/rydercup-api-secret created
```

---

### Paso 3: Crear Almacenamiento Persistente

```bash
# Crear PersistentVolumeClaim para PostgreSQL
kubectl apply -f postgres-pvc.yaml

# Verificar que el PVC fue creado
kubectl get pvc
```

**Salida esperada:**
```
persistentvolumeclaim/postgres-pvc created

NAME           STATUS   VOLUME                                     CAPACITY   ACCESS MODES
postgres-pvc   Bound    pvc-xxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx      10Gi       RWO
```

---

### Paso 4: Desplegar PostgreSQL

```bash
# Aplicar deployment y service de PostgreSQL
kubectl apply -f postgres-deployment.yaml
kubectl apply -f postgres-service.yaml

# Verificar que el pod está corriendo
kubectl get pods -l component=database

# Ver logs de PostgreSQL (opcional)
kubectl logs -l component=database
```

**Salida esperada:**
```
deployment.apps/postgres created
service/postgres-service created

NAME                        READY   STATUS    RESTARTS   AGE
postgres-6677c9cc9-xxxxx    1/1     Running   0          30s
```

**⏳ Esperar:** El pod de PostgreSQL debe estar en estado `Running` antes de continuar.

```bash
# Esperar a que el pod esté listo (timeout 60s)
kubectl wait --for=condition=ready pod -l component=database --timeout=60s
```

---

### Paso 5: Desplegar Backend (FastAPI)

```bash
# Aplicar deployment y service del backend
kubectl apply -f api-deployment.yaml
kubectl apply -f api-service.yaml

# Verificar que los pods están corriendo
kubectl get pods -l component=api

# Ver logs del backend (opcional)
kubectl logs -l component=api --tail=20
```

**Salida esperada:**
```
deployment.apps/rydercup-api created
service/rydercup-api-service created

NAME                              READY   STATUS    RESTARTS   AGE
rydercup-api-5c56c4cb64-xxxxx     1/1     Running   0          45s
rydercup-api-5c56c4cb64-yyyyy     1/1     Running   0          45s
```

**⏳ Esperar:** Los 2 pods del backend deben estar en estado `Running`.

```bash
# Esperar a que los pods estén listos
kubectl wait --for=condition=ready pod -l component=api --timeout=120s
```

---

### Paso 6: Desplegar Frontend (React + nginx)

```bash
# Aplicar deployment y service del frontend
kubectl apply -f frontend-deployment.yaml
kubectl apply -f frontend-service.yaml

# Verificar que los pods están corriendo
kubectl get pods -l component=frontend

# Ver logs del frontend (opcional)
kubectl logs -l component=frontend --tail=20
```

**Salida esperada:**
```
deployment.apps/rydercup-frontend created
service/rydercup-frontend-service created

NAME                                   READY   STATUS    RESTARTS   AGE
rydercup-frontend-7967575569-xxxxx     1/1     Running   0          30s
rydercup-frontend-7967575569-yyyyy     1/1     Running   0          30s
```

**⏳ Esperar:** Los 2 pods del frontend deben estar en estado `Running`.

```bash
# Esperar a que los pods estén listos
kubectl wait --for=condition=ready pod -l component=frontend --timeout=60s
```

---

### Paso 7: Verificar Todo el Deployment

```bash
# Ver todos los recursos creados
kubectl get all -l app=rydercup

# Ver el estado de los pods
kubectl get pods

# Ver los services
kubectl get svc
```

**Salida esperada:**
```
NAME                                     READY   STATUS    RESTARTS   AGE
pod/postgres-6677c9cc9-xxxxx             1/1     Running   0          5m
pod/rydercup-api-5c56c4cb64-xxxxx        1/1     Running   0          3m
pod/rydercup-api-5c56c4cb64-yyyyy        1/1     Running   0          3m
pod/rydercup-frontend-7967575569-xxxxx   1/1     Running   0          2m
pod/rydercup-frontend-7967575569-yyyyy   1/1     Running   0          2m

NAME                                TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)
service/postgres-service            ClusterIP      10.96.157.225   <none>        5432/TCP
service/rydercup-api-service        LoadBalancer   10.96.208.7     <pending>     80:30321/TCP
service/rydercup-frontend-service   LoadBalancer   10.96.235.251   <pending>     80:32315/TCP

NAME                                READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/postgres            1/1     1            1           5m
deployment.apps/rydercup-api        2/2     2            2           3m
deployment.apps/rydercup-frontend   2/2     2            2           2m
```

✅ **Todos los pods deben estar en `Running` y `READY 1/1` o `2/2`**

---

## 🔍 Verificación del Deployment

### 1. Verificar Health Checks

```bash
# Health check del backend (desde dentro del pod)
kubectl exec deployment/rydercup-api -- curl -s http://localhost:8000/

# Health check del frontend
kubectl exec deployment/rydercup-frontend -- curl -s http://localhost/health
```

**Salida esperada:**

**Backend:**
```json
{
  "message": "Ryder Cup Manager API",
  "version": "1.0.0",
  "status": "running"
}
```

**Frontend:**
```
healthy
```

---

### 2. Verificar Conectividad Frontend → Backend

```bash
# Desde el pod del frontend, hacer request al backend
kubectl exec deployment/rydercup-frontend -- wget -qO- http://rydercup-api-service/
```

**Salida esperada:**
```json
{"message":"Ryder Cup Manager API","version":"1.0.0","status":"running"}
```

---

### 3. Verificar Conectividad Backend → Database

```bash
# Verificar que el backend puede conectarse a PostgreSQL
kubectl logs deployment/rydercup-api --tail=50 | grep -i "database\|postgres"
```

**Buscar líneas como:**
```
INFO:     Database connection established
INFO:     PostgreSQL version: 15.x
```

---

### 4. Verificar ConfigMaps y Secrets

```bash
# Ver variables del frontend
kubectl get configmap rydercup-frontend-config -o yaml | grep VITE_API_BASE_URL

# Ver variables del backend (sin valores sensibles)
kubectl get configmap rydercup-api-config -o yaml | grep ENVIRONMENT

# Ver que el secret existe (no mostrar valores)
kubectl get secret rydercup-api-secret
```

---

### 5. Verificar Almacenamiento Persistente

```bash
# Ver PersistentVolumeClaim
kubectl get pvc postgres-pvc

# Ver que el volumen está montado en el pod de PostgreSQL
kubectl describe pod -l component=database | grep -A 5 "Volumes:"
```

**Salida esperada:**
```
NAME           STATUS   VOLUME                                     CAPACITY   ACCESS MODES
postgres-pvc   Bound    pvc-xxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx      10Gi       RWO
```

---

## 🌐 Acceder a la Aplicación

### Exponer Servicios con Port-Forward

Para acceder a la aplicación desde tu navegador, necesitas crear **2 port-forwards**:

#### Terminal 1: Exponer Backend

```bash
kubectl port-forward svc/rydercup-api-service 8000:80
```

**Salida esperada:**
```
Forwarding from 127.0.0.1:8000 -> 80
Forwarding from [::1]:8000 -> 80
```

⚠️ **No cierres esta terminal** - debe quedar corriendo.

---

#### Terminal 2: Exponer Frontend

```bash
kubectl port-forward svc/rydercup-frontend-service 8080:80
```

**Salida esperada:**
```
Forwarding from 127.0.0.1:8080 -> 80
Forwarding from [::1]:8080 -> 80
```

⚠️ **No cierres esta terminal** - debe quedar corriendo.

---

### Abrir la Aplicación en el Navegador

1. Abre tu navegador en: **http://localhost:8080**
2. Deberías ver la landing page de Ryder Cup Manager
3. Prueba registrarte o hacer login

---

### Verificar en la Consola del Navegador (F12)

Abre la consola del navegador (F12) y busca estos logs:

```javascript
✅ Runtime configuration loaded: {
  API_BASE_URL: "http://localhost:8000",
  APP_NAME: "Ryder Cup Friends",
  ENVIRONMENT: "production"
}

🔧 API Configuration: {
  runtime: "http://localhost:8000",
  buildtime: undefined,
  using: "http://localhost:8000"
}
```

✅ **Si ves estos logs, la configuración runtime está funcionando correctamente.**

---

### Probar Funcionalidad

1. **Registrar usuario:** Crear una cuenta nueva
2. **Login:** Iniciar sesión
3. **Crear competición:** Probar el módulo de competiciones
4. **Ver perfil:** Acceder a tu perfil

Si todas estas acciones funcionan sin errores de CORS o "Failed to fetch", ¡todo está perfecto! ✅

---

## 📋 Comandos Importantes

### Ver Estado del Cluster

```bash
# Ver información general del cluster
kubectl cluster-info

# Ver todos los nodos
kubectl get nodes

# Ver todos los recursos de la app
kubectl get all -l app=rydercup

# Ver todos los pods con detalles
kubectl get pods -o wide

# Ver todos los services
kubectl get svc

# Ver ConfigMaps
kubectl get configmaps

# Ver Secrets
kubectl get secrets

# Ver PersistentVolumeClaims
kubectl get pvc
```

---

### Ver Logs

```bash
# Logs del frontend (últimas 50 líneas)
kubectl logs deployment/rydercup-frontend --tail=50

# Logs del backend (últimas 50 líneas)
kubectl logs deployment/rydercup-api --tail=50

# Logs de PostgreSQL (últimas 50 líneas)
kubectl logs deployment/postgres --tail=50

# Seguir logs en tiempo real (follow)
kubectl logs -f deployment/rydercup-frontend
kubectl logs -f deployment/rydercup-api

# Logs de un pod específico
kubectl logs pod/rydercup-api-5c56c4cb64-xxxxx
```

---

### Describir Recursos

```bash
# Detalles completos de un pod
kubectl describe pod -l component=frontend

# Detalles de un deployment
kubectl describe deployment rydercup-api

# Detalles de un service
kubectl describe svc rydercup-api-service

# Detalles de un PVC
kubectl describe pvc postgres-pvc

# Ver eventos del cluster (útil para troubleshooting)
kubectl get events --sort-by=.metadata.creationTimestamp
```

---

### Ejecutar Comandos en Pods

```bash
# Entrar a un pod (shell interactivo)
kubectl exec -it deployment/rydercup-frontend -- sh
kubectl exec -it deployment/rydercup-api -- bash
kubectl exec -it deployment/postgres -- bash

# Ejecutar un comando sin entrar al pod
kubectl exec deployment/rydercup-frontend -- ls -la /usr/share/nginx/html
kubectl exec deployment/rydercup-api -- env | grep DATABASE

# Ver archivo config.js del frontend
kubectl exec deployment/rydercup-frontend -- cat /usr/share/nginx/html/config.js
```

---

### Verificar Health Checks

```bash
# Ver configuración de health probes
kubectl get pod -l component=frontend -o yaml | grep -A 10 "livenessProbe:"
kubectl get pod -l component=api -o yaml | grep -A 10 "readinessProbe:"

# Ver últimos eventos de health checks
kubectl describe pod -l component=api | grep -A 5 "Liveness\|Readiness"
```

---

### Ver Recursos (CPU/RAM)

```bash
# Ver uso de recursos de los pods
kubectl top nodes
kubectl top pods

# Ver límites de recursos configurados
kubectl describe pod -l component=api | grep -A 5 "Limits:\|Requests:"
```

---

### Escalar Réplicas

```bash
# Escalar frontend a 3 réplicas
kubectl scale deployment rydercup-frontend --replicas=3

# Escalar backend a 4 réplicas
kubectl scale deployment rydercup-api --replicas=4

# Ver el estado del scaling
kubectl get deployment

# Volver a 2 réplicas
kubectl scale deployment rydercup-frontend --replicas=2
kubectl scale deployment rydercup-api --replicas=2
```

---

### Actualizar Configuración

```bash
# Editar ConfigMap en vivo
kubectl edit configmap rydercup-frontend-config

# Editar Secret en vivo
kubectl edit secret rydercup-api-secret

# Aplicar cambios desde archivo
kubectl apply -f k8s/frontend-configmap.yaml

# Reiniciar deployment para aplicar cambios
kubectl rollout restart deployment/rydercup-frontend
kubectl rollout restart deployment/rydercup-api

# Ver estado del rollout
kubectl rollout status deployment/rydercup-frontend
```

---

### Rollback de Deployment

```bash
# Ver historial de revisiones
kubectl rollout history deployment/rydercup-api

# Hacer rollback a la versión anterior
kubectl rollout undo deployment/rydercup-api

# Hacer rollback a una revisión específica
kubectl rollout undo deployment/rydercup-api --to-revision=2
```

---

### Port-Forward

```bash
# Exponer backend en localhost:8000
kubectl port-forward svc/rydercup-api-service 8000:80

# Exponer frontend en localhost:8080
kubectl port-forward svc/rydercup-frontend-service 8080:80

# Exponer PostgreSQL en localhost:5432 (para inspección con herramientas)
kubectl port-forward svc/postgres-service 5432:5432

# Port-forward de un pod específico
kubectl port-forward pod/rydercup-api-5c56c4cb64-xxxxx 8000:8000
```

---

### Copiar Archivos

```bash
# Copiar archivo desde pod a local
kubectl cp rydercup-frontend-xxxxx:/usr/share/nginx/html/index.html ./index.html

# Copiar archivo desde local a pod
kubectl cp ./config.js rydercup-frontend-xxxxx:/usr/share/nginx/html/config.js
```

---

## 🛠️ Troubleshooting

### Problema: Pods en estado `Pending` o `ImagePullBackOff`

```bash
# Ver detalles del pod
kubectl describe pod <pod-name>

# Ver eventos del cluster
kubectl get events --sort-by=.metadata.creationTimestamp

# Ver logs del pod (si está corriendo)
kubectl logs <pod-name>
```

**Soluciones comunes:**
- `ImagePullBackOff`: Verificar que la imagen existe en Docker Hub
- `Pending`: Verificar recursos del nodo (`kubectl top nodes`)
- `CrashLoopBackOff`: Ver logs del pod para identificar el error

---

### Problema: Pods en `CrashLoopBackOff`

```bash
# Ver logs del pod que falla
kubectl logs <pod-name> --previous

# Ver razón del crash
kubectl describe pod <pod-name> | grep -A 10 "State:"

# Ver eventos
kubectl get events --field-selector involvedObject.name=<pod-name>
```

**Soluciones comunes:**
- Error de base de datos: Verificar que PostgreSQL está corriendo
- Error de ConfigMap/Secret: Verificar que existen y tienen valores correctos
- Error de puerto: Verificar que el puerto configurado es correcto

---

### Problema: "Failed to fetch" en el navegador

```bash
# Verificar CORS en logs del backend
kubectl logs deployment/rydercup-api | grep -i cors

# Verificar que el backend está corriendo
kubectl get pods -l component=api

# Verificar port-forward del backend
ps aux | grep "port-forward.*8000"
```

**Soluciones:**
1. Verificar que el port-forward del backend está corriendo
2. Verificar CORS en logs: debe incluir `http://localhost:8080`
3. Verificar en consola del navegador (F12) que `window.APP_CONFIG.API_BASE_URL` es correcto

---

### Problema: ConfigMap no se actualiza en el pod

```bash
# Editar ConfigMap
kubectl edit configmap rydercup-frontend-config

# Reiniciar deployment para aplicar cambios
kubectl rollout restart deployment/rydercup-frontend

# Verificar que el pod tiene el nuevo config
kubectl exec deployment/rydercup-frontend -- cat /usr/share/nginx/html/config.js
```

---

### Problema: PostgreSQL no arranca

```bash
# Ver logs de PostgreSQL
kubectl logs deployment/postgres --tail=100

# Verificar PVC
kubectl get pvc postgres-pvc

# Verificar que el volumen está montado
kubectl describe pod -l component=database | grep -A 10 "Volumes:"
```

**Soluciones comunes:**
- PVC en estado `Pending`: Verificar StorageClass del cluster
- Error de permisos: Verificar que el volumen tiene permisos correctos
- Error de password: Verificar Secret tiene POSTGRES_PASSWORD

---

### Problema: Backend no conecta a PostgreSQL

```bash
# Verificar que PostgreSQL está corriendo
kubectl get pods -l component=database

# Verificar que el Service de PostgreSQL existe
kubectl get svc postgres-service

# Probar conectividad desde el pod del backend
kubectl exec deployment/rydercup-api -- nc -zv postgres-service 5432

# Ver logs del backend
kubectl logs deployment/rydercup-api | grep -i "database\|postgres"
```

**Soluciones:**
- Verificar `DATABASE_HOST` en ConfigMap = `postgres-service`
- Verificar `DATABASE_PORT` en ConfigMap = `5432`
- Verificar credenciales en Secret

---

### Problema: Health checks fallan

```bash
# Ver estado de health probes
kubectl describe pod <pod-name> | grep -A 10 "Liveness:\|Readiness:"

# Ver eventos de health checks
kubectl get events | grep -i "unhealthy\|liveness\|readiness"

# Probar health check manualmente
kubectl exec <pod-name> -- curl -v http://localhost:8000/
kubectl exec <pod-name> -- curl -v http://localhost/health
```

---

## 🔧 Gestión del Cluster

### Pausar el Cluster (sin eliminar)

```bash
# Detener el cluster
docker stop rydercupam-cluster-control-plane

# Ver clusters detenidos
docker ps -a | grep rydercupam-cluster

# Reiniciar el cluster
docker start rydercupam-cluster-control-plane

# Verificar que el cluster está corriendo
kubectl get nodes
```

---

### Reiniciar Todos los Pods

```bash
# Reiniciar frontend
kubectl rollout restart deployment/rydercup-frontend

# Reiniciar backend
kubectl rollout restart deployment/rydercup-api

# Reiniciar PostgreSQL (⚠️ cuidado con datos)
kubectl rollout restart deployment/postgres

# Ver estado de todos los rollouts
kubectl get deployments
```

---

### Actualizar Imágenes Docker

```bash
# Después de hacer push de nueva imagen a Docker Hub:

# Reiniciar deployment para descargar nueva imagen
kubectl rollout restart deployment/rydercup-frontend
kubectl rollout restart deployment/rydercup-api

# Verificar que se descargó la nueva imagen
kubectl describe pod -l component=frontend | grep Image:
```

---

### Backup de PostgreSQL

```bash
# Exportar base de datos desde el pod
kubectl exec deployment/postgres -- pg_dump -U rydercupam_adminuser ryderclub > backup.sql

# Restaurar base de datos
cat backup.sql | kubectl exec -i deployment/postgres -- psql -U rydercupam_adminuser ryderclub
```

---

### Ver Métricas del Cluster

```bash
# Ver uso de CPU/RAM de nodos
kubectl top nodes

# Ver uso de CPU/RAM de pods
kubectl top pods

# Ver uso de CPU/RAM de un pod específico
kubectl top pod <pod-name>
```

---

### Limpiar Recursos sin Eliminar el Cluster

```bash
# Eliminar todos los recursos de la app
kubectl delete all -l app=rydercup

# Eliminar ConfigMaps
kubectl delete configmap -l app=rydercup

# Eliminar Secrets
kubectl delete secret -l app=rydercup

# Eliminar PVC (⚠️ esto borra los datos de PostgreSQL)
kubectl delete pvc postgres-pvc

# Volver a aplicar todos los manifiestos
cd k8s/
kubectl apply -f .
```

---

## 🗑️ Eliminación del Cluster

### Eliminar el Cluster Completo

```bash
# Listar clusters
kind get clusters

# Eliminar el cluster
kind delete cluster --name rydercupam-cluster

# Verificar que fue eliminado
kind get clusters
docker ps -a | grep rydercupam
```

**⚠️ ADVERTENCIA:** Esto eliminará:
- Todos los pods
- Todos los datos de PostgreSQL
- Todas las configuraciones
- El cluster completo

---

### Limpiar Imágenes Docker (opcional)

```bash
# Ver imágenes Kind
docker images | grep kindest

# Eliminar imágenes Kind (libera espacio)
docker rmi kindest/node:v1.27.3

# Ver imágenes de la aplicación
docker images | grep rydercupam

# Eliminar imágenes de la aplicación (opcional)
docker rmi agustinedev/rydercupam-app:latest
docker rmi agustinedev/rydercupam-web:latest
```

---

## 📚 Recursos Adicionales

### Documentación Oficial

- [Kubernetes Documentation](https://kubernetes.io/docs/home/)
- [Kind Documentation](https://kind.sigs.k8s.io/)
- [Docker Documentation](https://docs.docker.com/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)

### Archivos Relacionados

- `k8s/` - Todos los manifiestos de Kubernetes
- `Dockerfile` (Backend) - Imagen Docker del backend
- `RyderCupWeb/Dockerfile` - Imagen Docker del frontend
- `RyderCupWeb/nginx.conf` - Configuración de nginx
- `RyderCupWeb/entrypoint.sh` - Script de runtime configuration

### Comandos Rápidos (Cheat Sheet)

```bash
# Estado general
kubectl get all -l app=rydercup
kubectl get pods -o wide
kubectl get svc

# Logs
kubectl logs -f deployment/rydercup-frontend --tail=50
kubectl logs -f deployment/rydercup-api --tail=50

# Ejecutar comandos
kubectl exec -it deployment/rydercup-api -- bash

# Port-forward
kubectl port-forward svc/rydercup-api-service 8000:80 &
kubectl port-forward svc/rydercup-frontend-service 8080:80 &

# Reiniciar
kubectl rollout restart deployment/rydercup-frontend
kubectl rollout restart deployment/rydercup-api

# Escalar
kubectl scale deployment rydercup-frontend --replicas=3

# Actualizar config
kubectl apply -f k8s/frontend-configmap.yaml
kubectl rollout restart deployment/rydercup-frontend

# Eliminar todo
kind delete cluster --name rydercupam-cluster
```

---

## 🎯 Checklist de Deployment

Usa esta checklist cada vez que levantes el cluster:

- [ ] Docker Desktop está corriendo
- [ ] Cluster Kind creado: `kind create cluster --name rydercupam-cluster`
- [ ] ConfigMaps aplicados: `kubectl apply -f *-configmap.yaml`
- [ ] Secrets aplicados: `kubectl apply -f api-secret.yaml`
- [ ] PVC creado: `kubectl apply -f postgres-pvc.yaml`
- [ ] PostgreSQL desplegado y corriendo: `kubectl get pods -l component=database`
- [ ] Backend desplegado y corriendo: `kubectl get pods -l component=api`
- [ ] Frontend desplegado y corriendo: `kubectl get pods -l component=frontend`
- [ ] Todos los pods en estado `Running`: `kubectl get pods`
- [ ] Port-forward backend corriendo: `kubectl port-forward svc/rydercup-api-service 8000:80`
- [ ] Port-forward frontend corriendo: `kubectl port-forward svc/rydercup-frontend-service 8080:80`
- [ ] Aplicación accesible en: http://localhost:8080
- [ ] Login/Registro funciona correctamente

---

## 📞 Soporte

Si encuentras problemas:

1. Revisa la sección [Troubleshooting](#troubleshooting)
2. Verifica los logs: `kubectl logs deployment/<nombre>`
3. Verifica eventos: `kubectl get events --sort-by=.metadata.creationTimestamp`
4. Consulta el [Issue Tracker](https://github.com/agustinedev/rydercupam/issues)

---

**Última actualización:** 3 Diciembre 2025
**Autor:** Equipo RyderCupAm
**Versión:** 1.0.0
