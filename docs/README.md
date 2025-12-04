# 📚 Documentación - Ryder Cup Manager

Índice completo de documentación del proyecto.

---

## 🚀 Kubernetes

### Guías de Deployment

| Documento | Descripción | Audiencia |
|-----------|-------------|-----------|
| [KUBERNETES_DEPLOYMENT_GUIDE.md](./KUBERNETES_DEPLOYMENT_GUIDE.md) | Guía completa de deployment (80+ páginas) | DevOps, Developers |
| [KUBERNETES_QUICK_START.md](./KUBERNETES_QUICK_START.md) | Referencia rápida (1 página) | Todos |

### Scripts de Automatización

| Script | Descripción |
|--------|-------------|
| `scripts/deploy-cluster.sh` | Desplegar cluster automáticamente |
| `scripts/cluster-status.sh` | Diagnóstico visual del cluster |
| `scripts/destroy-cluster.sh` | Eliminar cluster completamente |

Ver: [scripts/README.md](../scripts/README.md)

---

## 📖 Contenido de las Guías

### KUBERNETES_DEPLOYMENT_GUIDE.md

**Secciones principales:**

1. **Resumen Ejecutivo**
   - ¿Qué hemos construido?
   - Estadísticas del deployment
   - Mejoras aplicadas al código

2. **Arquitectura**
   - Diagramas de arquitectura
   - Flujo de datos completo

3. **Paso a Paso**
   - Crear cluster Kind
   - Aplicar manifiestos
   - Verificación completa

4. **Comandos Importantes**
   - Ver estado del cluster
   - Ver logs
   - Ejecutar comandos en pods
   - Escalar réplicas
   - Actualizar configuración

5. **Troubleshooting**
   - Pods en Pending/CrashLoopBackOff
   - CORS errors
   - ConfigMaps no actualizan
   - PostgreSQL no arranca
   - Health checks fallan

6. **Gestión del Cluster**
   - Pausar/Reiniciar
   - Actualizar imágenes
   - Backup de PostgreSQL
   - Métricas

---

### KUBERNETES_QUICK_START.md

**Contenido:**

- ⚡ Inicio rápido (5 minutos)
- 📋 Comandos esenciales
- 🛠️ Troubleshooting rápido
- 📚 Referencias a documentación completa

**Ideal para:**
- Referencia diaria
- Quick reference card
- Onboarding de nuevos developers

---

## 🎯 ¿Por Dónde Empezar?

### Si eres nuevo en Kubernetes

1. Lee: [KUBERNETES_DEPLOYMENT_GUIDE.md](./KUBERNETES_DEPLOYMENT_GUIDE.md) - Sección "Resumen Ejecutivo"
2. Sigue: Paso a Paso completo
3. Practica: Comandos importantes
4. Referencia: [KUBERNETES_QUICK_START.md](./KUBERNETES_QUICK_START.md)

### Si ya conoces Kubernetes

1. Usa: `scripts/deploy-cluster.sh` para desplegar
2. Referencia: [KUBERNETES_QUICK_START.md](./KUBERNETES_QUICK_START.md)
3. Troubleshooting: [KUBERNETES_DEPLOYMENT_GUIDE.md](./KUBERNETES_DEPLOYMENT_GUIDE.md) - Sección "Troubleshooting"

### Si solo quieres arrancar el cluster

```bash
./scripts/deploy-cluster.sh
```

¡Listo!

---

## 🏗️ Arquitectura del Proyecto

```
RyderCupAm/
├── docs/
│   ├── KUBERNETES_DEPLOYMENT_GUIDE.md  # 📘 Guía completa
│   ├── KUBERNETES_QUICK_START.md       # ⚡ Referencia rápida
│   └── README.md                        # 📚 Este archivo
├── k8s/
│   ├── api-configmap.yaml              # ConfigMap backend
│   ├── api-secret.yaml                 # Secret backend
│   ├── api-deployment.yaml             # Deployment backend
│   ├── api-service.yaml                # Service backend
│   ├── frontend-configmap.yaml         # ConfigMap frontend
│   ├── frontend-deployment.yaml        # Deployment frontend
│   ├── frontend-service.yaml           # Service frontend
│   ├── postgres-pvc.yaml               # PersistentVolumeClaim
│   ├── postgres-deployment.yaml        # Deployment PostgreSQL
│   └── postgres-service.yaml           # Service PostgreSQL
└── scripts/
    ├── deploy-cluster.sh               # 🚀 Desplegar cluster
    ├── cluster-status.sh               # 🔍 Diagnóstico
    ├── destroy-cluster.sh              # 🗑️ Eliminar cluster
    └── README.md                        # 📖 Documentación scripts
```

---

## 📝 Convenciones

### Nomenclatura de Archivos

- **Deployment:** `<componente>-deployment.yaml`
- **Service:** `<componente>-service.yaml`
- **ConfigMap:** `<componente>-configmap.yaml`
- **Secret:** `<componente>-secret.yaml`

### Labels Kubernetes

Todos los recursos usan labels consistentes:

```yaml
labels:
  app: rydercup           # Aplicación
  component: frontend     # Componente (frontend/api/database)
  tier: presentation      # Capa (presentation/backend/data)
```

### Comandos con Labels

```bash
# Ver todos los recursos de la app
kubectl get all -l app=rydercup

# Ver solo frontend
kubectl get all -l component=frontend

# Ver solo backend
kubectl get all -l component=api

# Ver solo database
kubectl get all -l component=database
```

---

## 🔍 Búsqueda Rápida

### Encontrar un Tema

| Tema | Documento | Sección |
|------|-----------|---------|
| Crear cluster | DEPLOYMENT_GUIDE | Paso 1 |
| ConfigMaps | DEPLOYMENT_GUIDE | Paso 2 |
| PostgreSQL | DEPLOYMENT_GUIDE | Paso 3-4 |
| Port-forward | DEPLOYMENT_GUIDE | Acceder a la Aplicación |
| CORS errors | DEPLOYMENT_GUIDE | Troubleshooting |
| Health checks | DEPLOYMENT_GUIDE | Verificación |
| Escalar réplicas | DEPLOYMENT_GUIDE | Comandos Importantes |
| Backup PostgreSQL | DEPLOYMENT_GUIDE | Gestión del Cluster |

---

## 🆘 Soporte

### Problemas con el Deployment

1. Revisa: [Troubleshooting](./KUBERNETES_DEPLOYMENT_GUIDE.md#troubleshooting)
2. Ejecuta: `./scripts/cluster-status.sh` para diagnóstico
3. Verifica logs: `kubectl logs -f deployment/<nombre>`

### Documentación Adicional

- **Backend (FastAPI):** Ver [CLAUDE.md](../CLAUDE.md)
- **Frontend (React):** Ver [RyderCupWeb/README.md](../../RyderCupWeb/README.md)
- **Kubernetes Oficial:** https://kubernetes.io/docs/

---

## 📊 Estadísticas de Documentación

- **Total páginas:** ~100 páginas
- **Archivos creados:** 7 archivos
- **Scripts:** 3 scripts automatizados
- **Comandos documentados:** 50+ comandos
- **Troubleshooting entries:** 8 problemas comunes

---

## 🤝 Contribuir

Si encuentras errores o quieres mejorar la documentación:

1. Identifica el archivo correcto
2. Haz los cambios
3. Verifica que los comandos funcionan
4. Actualiza la fecha de "Última actualización"

---

**Última actualización:** 3 Diciembre 2025
**Versión:** 1.0.0
