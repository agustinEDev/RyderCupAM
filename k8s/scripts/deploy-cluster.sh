#!/bin/bash

# ==========================================
# Script de Deployment Automático - Ryder Cup Manager
# ==========================================
# Este script despliega la aplicación completa en Kubernetes
#
# ⚠️  IMPORTANTE: Ejecutar con ./deploy-cluster.sh
#    NO uses: source deploy-cluster.sh
#
# Uso: ./scripts/deploy-cluster.sh
# ==========================================

# Detectar si fue ejecutado con 'source'
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Ejecutado correctamente con ./
    :
else
    echo "❌ ERROR: No ejecutes este script con 'source'"
    echo "✅ Usa: ./k8s/scripts/deploy-cluster.sh"
    return 1 2>/dev/null || exit 1
fi

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

# Manejo de interrupciones (Ctrl+C) - DESPUÉS de definir funciones
trap 'echo ""; print_warning "Script interrumpido por el usuario"; exit 130' INT TERM

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
# Determinar rutas del proyecto
# ==========================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
K8S_DIR="$PROJECT_ROOT/k8s"
KIND_CONFIG="$K8S_DIR/kind-config.yaml"

# ==========================================
# PASO 2: Crear cluster Kind (si no existe)
# ==========================================
print_step "Verificando cluster Kind..."

CLUSTER_NAME="rydercupam-cluster"

if [ ! -f "$KIND_CONFIG" ]; then
    print_error "No se encontró kind-config.yaml en: $KIND_CONFIG"
    exit 1
fi

if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    print_warning "Cluster '${CLUSTER_NAME}' ya existe"
    read -p "¿Quieres eliminarlo y crear uno nuevo? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_step "Eliminando cluster existente..."
        kind delete cluster --name ${CLUSTER_NAME}

        print_step "Creando nuevo cluster con port mappings..."
        kind create cluster --name ${CLUSTER_NAME} --config "$KIND_CONFIG"
        print_success "Cluster creado exitosamente"
    else
        print_warning "Usando cluster existente"
    fi
else
    print_step "Creando cluster '${CLUSTER_NAME}' con port mappings..."
    kind create cluster --name ${CLUSTER_NAME} --config "$KIND_CONFIG"
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
# PASO 4: Verificar directorio de manifiestos
# ==========================================
if [ ! -d "$K8S_DIR" ]; then
    print_error "No se encontró el directorio k8s en: $K8S_DIR"
    print_error "Asegúrate de ejecutar este script desde el proyecto correcto"
    exit 1
fi

print_step "Usando manifiestos de: $K8S_DIR"
echo ""

# ==========================================
# PASO 5: Crear Namespace
# ==========================================
print_step "Creando namespace rydercup..."

kubectl apply -f "$K8S_DIR/namespace.yaml"
kubectl config set-context --current --namespace=rydercupfriends

print_success "Namespace creado y configurado"
echo ""

# ==========================================
# PASO 6: Aplicar ConfigMaps y Secrets
# ==========================================
print_step "Aplicando ConfigMaps y Secrets..."

kubectl apply -f "$K8S_DIR/api-configmap.yaml"
kubectl apply -f "$K8S_DIR/frontend-configmap.yaml"

if [ -f "$K8S_DIR/api-secret.local.yaml" ]; then
    kubectl apply -f "$K8S_DIR/api-secret.local.yaml"
else
    kubectl apply -f "$K8S_DIR/api-secret.yaml"
fi

print_success "ConfigMaps y Secrets aplicados"
echo ""

# ==========================================
# PASO 7: Crear almacenamiento persistente
# ==========================================
print_step "Creando PersistentVolumeClaim para PostgreSQL..."

kubectl apply -f "$K8S_DIR/postgres-pvc.yaml"

print_success "PVC creado"
echo ""

# ==========================================
# PASO 8: Construir imágenes Docker
# ==========================================
print_step "Construyendo imágenes Docker con el código actual..."

# Directorio del frontend (asumiendo estructura: RyderCupAm/ y RyderCupWeb/)
FRONTEND_CANDIDATE="$PROJECT_ROOT/../RyderCupWeb"
BACKEND_DIR="$PROJECT_ROOT"

if [ -d "$FRONTEND_CANDIDATE" ]; then
    FRONTEND_DIR="$(cd "$FRONTEND_CANDIDATE" && pwd)"
else
    print_error "No se encontró el directorio del frontend: $FRONTEND_CANDIDATE"
    exit 1
fi

# Verificar que existen los Dockerfiles
if [ ! -f "$BACKEND_DIR/docker/Dockerfile" ]; then
    print_error "No se encontró Dockerfile en: $BACKEND_DIR/docker/"
    exit 1
fi

if [ ! -f "$FRONTEND_DIR/Dockerfile" ]; then
    print_error "No se encontró Dockerfile en: $FRONTEND_DIR"
    exit 1
fi

# Construir imagen del Backend
print_step "Construyendo imagen del Backend (FastAPI)..."
docker build --no-cache -f "$BACKEND_DIR/docker/Dockerfile" -t agustinedev/rydercupam-api:latest "$BACKEND_DIR"
print_success "Imagen del backend construida"

# Construir imagen del Frontend
print_step "Construyendo imagen del Frontend (React + Vite)..."
docker build --no-cache -t agustinedev/rydercupam-web:latest "$FRONTEND_DIR"
print_success "Imagen del frontend construida"

# Pre-pull PostgreSQL image si no existe localmente
if ! docker image inspect postgres:15 &> /dev/null; then
    print_step "Descargando imagen PostgreSQL 15..."
    docker pull postgres:15
    print_success "Imagen PostgreSQL descargada"
fi

# Cargar imágenes en el cluster de Kind
print_step "Cargando imágenes en el cluster de Kind..."
kind load docker-image agustinedev/rydercupam-api:latest --name ${CLUSTER_NAME}
kind load docker-image agustinedev/rydercupam-web:latest --name ${CLUSTER_NAME}

# postgres:15 es multi-plataforma y kind load falla con ella — usar save/import
print_step "Cargando imagen PostgreSQL en Kind (save/import)..."
docker save postgres:15 | docker exec -i ${CLUSTER_NAME}-control-plane ctr --namespace=k8s.io images import -
print_success "Imágenes cargadas en el cluster (API + Frontend + PostgreSQL)"

echo ""

# ==========================================
# PASO 9: Desplegar PostgreSQL
# ==========================================
print_step "Desplegando PostgreSQL..."

kubectl apply -f "$K8S_DIR/postgres-deployment.yaml"
kubectl apply -f "$K8S_DIR/postgres-service.yaml"

print_step "Esperando a que PostgreSQL esté listo..."
kubectl rollout status deployment/postgres --timeout=120s

print_success "PostgreSQL desplegado y listo"
echo ""

# ==========================================
# PASO 10: Desplegar Backend (FastAPI)
# ==========================================
print_step "Desplegando Backend (FastAPI)..."

kubectl apply -f "$K8S_DIR/api-deployment.yaml"
kubectl apply -f "$K8S_DIR/api-service.yaml"

print_step "Esperando a que el Backend esté listo..."
kubectl rollout status deployment/rydercup-api --timeout=120s

print_success "Backend desplegado y listo"
echo ""

# ==========================================
# PASO 11: Desplegar Frontend (React + nginx)
# ==========================================
print_step "Desplegando Frontend (React + nginx)..."

kubectl apply -f "$K8S_DIR/frontend-deployment.yaml"
kubectl apply -f "$K8S_DIR/frontend-service.yaml"

print_step "Esperando a que el Frontend esté listo..."
kubectl rollout status deployment/rydercup-frontend --timeout=120s

print_success "Frontend desplegado y listo"
echo ""

# ==========================================
# PASO 12: Verificar deployment
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
# PASO 13: Instrucciones finales
# ==========================================
print_success "🎉 ¡Deployment completado exitosamente!"
echo ""
echo "📋 Próximos pasos:"
echo ""
echo -e "✨ ${YELLOW}¡Los puertos están mapeados automáticamente gracias a kind-config.yaml!${NC}"
echo -e "   ${GREEN}NO NECESITAS ejecutar port-forward${NC} 🎉"
echo ""
echo "1. Esperar unos segundos a que los pods estén completamente listos"
echo ""
echo "2. Verificar que los services tienen los NodePorts correctos:"
echo "   kubectl get svc -l app=rydercup"
echo "   Debe mostrar: 80:30321/TCP (backend) y 80:32315/TCP (frontend)"
echo ""
echo "3. Abrir en el navegador (port mappings automáticos):"
echo -e "   ${GREEN}http://localhost:8080${NC}  → Frontend"
echo -e "   ${GREEN}http://localhost:8000${NC}  → Backend API"
echo -e "   ${GREEN}http://localhost:8000/docs${NC}  → API Documentation"
echo ""
echo "📚 Ver documentación completa:"
echo -e "   ${GREEN}cat docs/KUBERNETES_DEPLOYMENT_GUIDE.md${NC}"
echo ""
echo "🔍 Ver logs:"
echo -e "   ${GREEN}kubectl logs -f deployment/rydercup-frontend${NC}"
echo -e "   ${GREEN}kubectl logs -f deployment/rydercup-api${NC}"
echo ""
echo "🗑️  Eliminar cluster:"
echo -e "   ${GREEN}kind delete cluster --name ${CLUSTER_NAME}${NC}"
echo ""
