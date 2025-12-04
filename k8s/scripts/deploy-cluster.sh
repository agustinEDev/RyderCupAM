#!/bin/bash

# ==========================================
# Script de Deployment Automático - Ryder Cup Manager
# ==========================================
# Este script despliega la aplicación completa en Kubernetes
# Uso: ./scripts/deploy-cluster.sh
# ==========================================

set -e  # Salir si algún comando falla

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir mensajes con colores
print_step() {
    echo -e "${BLUE}==>${NC} ${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Banner
echo ""
echo "🚀 =============================================="
echo "   Ryder Cup Manager - Kubernetes Deployment"
echo "   =============================================="
echo ""

# ==========================================
# PASO 1: Verificar prerrequisitos
# ==========================================
print_step "Verificando prerrequisitos..."

if ! command -v docker &> /dev/null; then
    print_error "Docker no está instalado. Por favor instala Docker Desktop."
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    print_error "kubectl no está instalado. Por favor instala kubectl."
    exit 1
fi

if ! command -v kind &> /dev/null; then
    print_error "Kind no está instalado. Por favor instala Kind."
    exit 1
fi

if ! docker info &> /dev/null; then
    print_error "Docker no está corriendo. Por favor inicia Docker Desktop."
    exit 1
fi

print_success "Todos los prerrequisitos están instalados"
echo ""

# ==========================================
# PASO 2: Crear cluster Kind (si no existe)
# ==========================================
print_step "Verificando cluster Kind..."

CLUSTER_NAME="rydercupam-cluster"

if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    print_warning "Cluster '${CLUSTER_NAME}' ya existe"
    read -p "¿Quieres eliminarlo y crear uno nuevo? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_step "Eliminando cluster existente..."
        kind delete cluster --name ${CLUSTER_NAME}

        print_step "Creando nuevo cluster con port mappings..."
        kind create cluster --name ${CLUSTER_NAME} --config k8s/kind-config.yaml
        print_success "Cluster creado exitosamente"
    else
        print_warning "Usando cluster existente"
    fi
else
    print_step "Creando cluster '${CLUSTER_NAME}' con port mappings..."
    kind create cluster --name ${CLUSTER_NAME} --config k8s/kind-config.yaml
    print_success "Cluster creado exitosamente"
fi

echo ""

# ==========================================
# PASO 3: Verificar conexión al cluster
# ==========================================
print_step "Verificando conexión al cluster..."

if ! kubectl cluster-info --context kind-${CLUSTER_NAME} &> /dev/null; then
    print_error "No se pudo conectar al cluster"
    exit 1
fi

print_success "Conectado al cluster"
echo ""

# ==========================================
# PASO 4: Aplicar ConfigMaps y Secrets
# ==========================================
print_step "Aplicando ConfigMaps y Secrets..."

cd k8s/

kubectl apply -f api-configmap.yaml
kubectl apply -f frontend-configmap.yaml
kubectl apply -f api-secret.yaml

print_success "ConfigMaps y Secrets aplicados"
echo ""

# ==========================================
# PASO 5: Crear almacenamiento persistente
# ==========================================
print_step "Creando PersistentVolumeClaim para PostgreSQL..."

kubectl apply -f postgres-pvc.yaml

print_success "PVC creado"
echo ""

# ==========================================
# PASO 6: Desplegar PostgreSQL
# ==========================================
print_step "Desplegando PostgreSQL..."

kubectl apply -f postgres-deployment.yaml
kubectl apply -f postgres-service.yaml

print_step "Esperando a que PostgreSQL esté listo..."
kubectl wait --for=condition=ready pod -l component=database --timeout=120s

print_success "PostgreSQL desplegado y listo"
echo ""

# ==========================================
# PASO 7: Desplegar Backend (FastAPI)
# ==========================================
print_step "Desplegando Backend (FastAPI)..."

kubectl apply -f api-deployment.yaml
kubectl apply -f api-service.yaml

print_step "Esperando a que el Backend esté listo..."
kubectl wait --for=condition=ready pod -l component=api --timeout=120s

print_success "Backend desplegado y listo"
echo ""

# ==========================================
# PASO 8: Desplegar Frontend (React + nginx)
# ==========================================
print_step "Desplegando Frontend (React + nginx)..."

kubectl apply -f frontend-deployment.yaml
kubectl apply -f frontend-service.yaml

print_step "Esperando a que el Frontend esté listo..."
kubectl wait --for=condition=ready pod -l component=frontend --timeout=120s

print_success "Frontend desplegado y listo"
echo ""

# ==========================================
# PASO 9: Verificar deployment
# ==========================================
print_step "Verificando deployment completo..."

echo ""
echo "📊 Estado de los Pods:"
kubectl get pods -l app=rydercup

echo ""
echo "🌐 Estado de los Services:"
kubectl get svc -l app=rydercup

echo ""

# Verificar que todos los pods están en Running
NOT_RUNNING=$(kubectl get pods -l app=rydercup -o jsonpath='{.items[?(@.status.phase!="Running")].metadata.name}')

if [ -z "$NOT_RUNNING" ]; then
    print_success "Todos los pods están en Running"
else
    print_warning "Los siguientes pods no están en Running: $NOT_RUNNING"
    print_warning "Revisa los logs con: kubectl logs <pod-name>"
fi

echo ""

# ==========================================
# PASO 10: Instrucciones finales
# ==========================================
print_success "🎉 ¡Deployment completado exitosamente!"
echo ""
echo "📋 Próximos pasos:"
echo ""
echo "✨ ${YELLOW}¡Los puertos ya están mapeados automáticamente!${NC}"
echo "   ${GREEN}NO NECESITAS ejecutar port-forward${NC} 🎉"
echo ""
echo "1. Esperar unos segundos a que los pods estén listos"
echo ""
echo "2. Abrir en el navegador:"
echo "   ${GREEN}http://localhost:8080${NC}  → Frontend"
echo "   ${GREEN}http://localhost:8000${NC}  → Backend API"
echo ""
echo "📚 Ver documentación completa:"
echo "   ${GREEN}cat docs/KUBERNETES_DEPLOYMENT_GUIDE.md${NC}"
echo ""
echo "🔍 Ver logs:"
echo "   ${GREEN}kubectl logs -f deployment/rydercup-frontend${NC}"
echo "   ${GREEN}kubectl logs -f deployment/rydercup-api${NC}"
echo ""
echo "🗑️  Eliminar cluster:"
echo "   ${GREEN}kind delete cluster --name ${CLUSTER_NAME}${NC}"
echo ""
