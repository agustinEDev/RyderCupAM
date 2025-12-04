# ⚡ Kubernetes Quick Start - Ryder Cup Manager

**Guía rápida para levantar el cluster en 5 minutos**

---

## 🚀 Inicio Rápido

### 1. Crear Cluster
```bash
kind create cluster --name rydercupam-cluster
```

### 2. Aplicar Manifiestos (en orden)
```bash
cd k8s/

# ConfigMaps y Secrets
kubectl apply -f api-configmap.yaml
kubectl apply -f frontend-configmap.yaml
kubectl apply -f api-secret.yaml

# Almacenamiento
kubectl apply -f postgres-pvc.yaml

# PostgreSQL
kubectl apply -f postgres-deployment.yaml
kubectl apply -f postgres-service.yaml

# Backend
kubectl apply -f api-deployment.yaml
kubectl apply -f api-service.yaml

# Frontend
kubectl apply -f frontend-deployment.yaml
kubectl apply -f frontend-service.yaml
```

### 3. Verificar
```bash
kubectl get all -l app=rydercup
```

**Esperado:** 5 pods en `Running` (1 postgres + 2 api + 2 frontend)

### 4. Exponer Servicios

**Terminal 1:**
```bash
kubectl port-forward svc/rydercup-api-service 8000:80
```

**Terminal 2:**
```bash
kubectl port-forward svc/rydercup-frontend-service 8080:80
```

### 5. Abrir Navegador
```
http://localhost:8080
```

✅ **¡Listo!**

---

## 📋 Comandos Esenciales

### Estado
```bash
# Ver todo
kubectl get all -l app=rydercup

# Ver pods
kubectl get pods

# Ver services
kubectl get svc
```

### Logs
```bash
# Frontend
kubectl logs -f deployment/rydercup-frontend

# Backend
kubectl logs -f deployment/rydercup-api

# PostgreSQL
kubectl logs -f deployment/postgres
```

### Reiniciar
```bash
kubectl rollout restart deployment/rydercup-frontend
kubectl rollout restart deployment/rydercup-api
```

### Escalar
```bash
kubectl scale deployment rydercup-frontend --replicas=3
```

### Eliminar Cluster
```bash
kind delete cluster --name rydercupam-cluster
```

---

## 🛠️ Troubleshooting Rápido

### Pods no arrancan
```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

### CORS errors
```bash
# Ver CORS configurado
kubectl logs deployment/rydercup-api | grep CORS

# Verificar port-forwards corriendo
ps aux | grep port-forward
```

### ConfigMap no actualiza
```bash
kubectl edit configmap rydercup-frontend-config
kubectl rollout restart deployment/rydercup-frontend
```

---

## 📚 Documentación Completa

Ver: `docs/KUBERNETES_DEPLOYMENT_GUIDE.md` (guía completa con arquitectura, troubleshooting detallado, etc.)

---

**Última actualización:** 3 Diciembre 2025
