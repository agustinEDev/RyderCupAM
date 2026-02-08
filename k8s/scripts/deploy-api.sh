#!/bin/bash

# ==========================================
# Script de Deployment - API Backend
# ==========================================
# Este script actualiza la imagen Docker del backend
# y despliega los cambios en Kubernetes con rolling update
# Uso: ./scripts/deploy-api.sh [version]
# Ejemplo: ./scripts/deploy-api.sh v1.0.1
# ==========================================

set -e  # Exit on error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuración
DOCKER_IMAGE="agustinedev/rydercupam-api"
DEPLOYMENT_NAME="rydercup-api"
CONTAINER_NAME="fastapi"
CLUSTER_NAME="rydercupam-cluster"
NAMESPACE="rydercupfriends"
VERSION="${1:-latest}"  # Usar argumento o "latest" por defecto

# Funciones de output
print_header() {
    echo ""
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}${BOLD}  $1${NC}"
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_step() {
    echo ""
    echo -e "${BLUE}━━ $1 ━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Función para verificar prerrequisitos
check_prerequisites() {
    print_step "Verificando prerrequisitos..."

    # Verificar Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker no está instalado"
        exit 1
    fi
    print_success "Docker: OK"

    # Verificar kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl no está instalado"
        exit 1
    fi
    print_success "kubectl: OK"

    # Verificar que kubectl está conectado al cluster
    if ! kubectl cluster-info &> /dev/null; then
        print_error "kubectl no está conectado a ningún cluster"
        print_info "Ejecuta: kind create cluster --name rydercupam-cluster"
        exit 1
    fi
    print_success "Cluster: OK"

    # Verificar Kind
    if ! command -v kind &> /dev/null; then
        print_error "Kind no está instalado"
        exit 1
    fi
    print_success "Kind: OK"

    # Verificar que el cluster Kind existe
    if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
        print_error "El cluster Kind '${CLUSTER_NAME}' no existe"
        print_info "Ejecuta primero: ./scripts/deploy-cluster.sh"
        exit 1
    fi
    print_success "Cluster Kind '${CLUSTER_NAME}': OK"

    # Verificar que el deployment existe
    if ! kubectl get deployment $DEPLOYMENT_NAME -n $NAMESPACE &> /dev/null; then
        print_error "El deployment '$DEPLOYMENT_NAME' no existe en el cluster"
        print_info "Ejecuta primero: ./scripts/deploy-cluster.sh"
        exit 1
    fi
    print_success "Deployment '$DEPLOYMENT_NAME': OK"
}

# Función para construir la imagen Docker
build_docker_image() {
    print_step "Construyendo imagen Docker..."

    local tag="${DOCKER_IMAGE}:${VERSION}"

    print_info "Tag: $tag"
    print_info "Directorio: $(pwd)"

    # Construir la imagen (usando Dockerfile en docker/)
    if docker build --no-cache -f docker/Dockerfile -t "$tag" .; then
        print_success "Imagen construida exitosamente: $tag"
    else
        print_error "Error al construir la imagen Docker"
        exit 1
    fi

    # Si no es "latest", también taggear como latest
    if [ "$VERSION" != "latest" ]; then
        docker tag "$tag" "${DOCKER_IMAGE}:latest"
        print_info "También taggeada como: ${DOCKER_IMAGE}:latest"
    fi
}

# Función para cargar la imagen en el cluster Kind
load_to_kind() {
    print_step "Cargando imagen en el cluster Kind..."

    local tag="${DOCKER_IMAGE}:${VERSION}"

    print_info "Loading: $tag → ${CLUSTER_NAME}"
    if kind load docker-image "$tag" --name ${CLUSTER_NAME}; then
        print_success "Imagen cargada en Kind: $tag"
    else
        print_error "Error al cargar la imagen en Kind"
        exit 1
    fi

    # Si no es "latest", también cargar latest
    if [ "$VERSION" != "latest" ]; then
        print_info "Loading: ${DOCKER_IMAGE}:latest → ${CLUSTER_NAME}"
        if kind load docker-image "${DOCKER_IMAGE}:latest" --name ${CLUSTER_NAME}; then
            print_success "Imagen cargada en Kind: ${DOCKER_IMAGE}:latest"
        else
            print_error "Error al cargar ${DOCKER_IMAGE}:latest en Kind"
            exit 1
        fi
    fi
}

# Función para actualizar el deployment en Kubernetes
update_deployment() {
    print_step "Actualizando deployment en Kubernetes..."

    local tag="${DOCKER_IMAGE}:${VERSION}"

    # Si es "latest", usar rollout restart (fuerza a usar nueva imagen)
    if [ "$VERSION" == "latest" ]; then
        print_info "Reiniciando deployment (usando nueva imagen)..."
        kubectl rollout restart deployment/$DEPLOYMENT_NAME -n $NAMESPACE
    else
        # Si es una versión específica, actualizar la imagen
        print_info "Actualizando imagen a: $tag"
        kubectl set image deployment/$DEPLOYMENT_NAME $CONTAINER_NAME=$tag -n $NAMESPACE
    fi

    print_success "Comando de actualización ejecutado"
}

# Función para esperar y monitorear el rollout
wait_for_rollout() {
    print_step "Esperando a que se complete el rollout..."

    print_info "Estado del rollout:"

    # Esperar con timeout de 5 minutos
    if kubectl rollout status deployment/$DEPLOYMENT_NAME -n $NAMESPACE --timeout=5m; then
        print_success "Rollout completado exitosamente"
    else
        print_error "El rollout ha tardado más de 5 minutos o ha fallado"
        print_warning "Verifica los logs: kubectl logs deployment/$DEPLOYMENT_NAME -n $NAMESPACE"
        exit 1
    fi
}

# Función para verificar el estado post-deployment
verify_deployment() {
    print_step "Verificando estado del deployment..."

    echo ""
    echo "📋 Estado de los pods:"
    kubectl get pods -l component=api -n $NAMESPACE

    echo ""
    echo "🔍 Imagen actual en los pods:"
    kubectl get pods -l component=api -n $NAMESPACE -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

    echo ""
    print_info "Últimos logs del deployment:"
    kubectl logs deployment/$DEPLOYMENT_NAME -n $NAMESPACE --tail=20

    # Verificar que todos los pods están Ready
    local ready_pods=$(kubectl get pods -l component=api -n $NAMESPACE -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}')
    if [[ "$ready_pods" == *"False"* ]]; then
        print_warning "Algunos pods no están listos. Verifica los logs."
    else
        print_success "Todos los pods están listos y corriendo"
    fi
}

# Función para mostrar resumen final
print_summary() {
    print_header "🎉 DEPLOYMENT COMPLETADO"

    echo ""
    echo -e "${GREEN}✅ Imagen Docker construida: ${DOCKER_IMAGE}:${VERSION}${NC}"
    echo -e "${GREEN}✅ Imagen cargada en Kind (${CLUSTER_NAME})${NC}"
    echo -e "${GREEN}✅ Deployment actualizado en Kubernetes${NC}"
    echo -e "${GREEN}✅ Rolling update completado sin downtime${NC}"

    echo ""
    print_info "Verificar la API:"
    echo "  • Documentación: http://localhost:8000/docs"
    echo "  • Health check: http://localhost:8000/"

    echo ""
    print_info "Comandos útiles:"
    echo "  • Ver logs: kubectl logs deployment/$DEPLOYMENT_NAME -n $NAMESPACE -f"
    echo "  • Ver estado: kubectl get pods -l component=api -n $NAMESPACE"
    echo "  • Rollback: kubectl rollout undo deployment/$DEPLOYMENT_NAME -n $NAMESPACE"

    echo ""
}

# Banner principal
clear
echo ""
echo "🚀 =================================================="
echo "   Ryder Cup Manager - API Deployment"
echo "   =================================================="
echo ""
echo -e "${BOLD}Docker Image:${NC} ${DOCKER_IMAGE}:${VERSION}"
echo -e "${BOLD}Deployment:${NC}   ${DEPLOYMENT_NAME}"
echo -e "${BOLD}Container:${NC}    ${CONTAINER_NAME}"
echo ""

# Confirmar antes de proceder
read -p "¿Continuar con el deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Deployment cancelado por el usuario"
    exit 0
fi

# Ejecutar el proceso completo
print_header "🔧 INICIANDO DEPLOYMENT"

check_prerequisites

# Cambiar al directorio raíz del proyecto si no estamos allí
if [ ! -f "docker/Dockerfile" ]; then
    print_info "Cambiando al directorio raíz del proyecto..."
    cd "$(dirname "$0")/../.."
fi

build_docker_image
load_to_kind
update_deployment
wait_for_rollout
verify_deployment
print_summary

print_success "¡Deployment completado con éxito! 🎉"
echo ""
