#!/bin/bash

# ==========================================
# Script de Deployment - Frontend Web
# ==========================================
# Este script actualiza la imagen Docker del frontend
# y despliega los cambios en Kubernetes con rolling update
# Uso: ./scripts/deploy-front.sh [version]
# Ejemplo: ./scripts/deploy-front.sh v1.0.2
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
DOCKER_IMAGE="agustinedev/rydercupam-web"
DEPLOYMENT_NAME="rydercup-frontend"
CONTAINER_NAME="nginx"
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

    # Verificar que el deployment existe
    if ! kubectl get deployment $DEPLOYMENT_NAME -n rydercupfriends &> /dev/null; then
        print_error "El deployment '$DEPLOYMENT_NAME' no existe en el cluster"
        print_info "Ejecuta primero: ./scripts/deploy-cluster.sh"
        exit 1
    fi
    print_success "Deployment '$DEPLOYMENT_NAME': OK"
}

# Función para construir la imagen Docker
build_docker_image() {
    print_step "Construyendo imagen Docker del Frontend..."

    local tag="${DOCKER_IMAGE}:${VERSION}"

    # Detectar directorio del frontend
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    FRONTEND_DIR="$PROJECT_ROOT/../RyderCupWeb"

    if [ ! -d "$FRONTEND_DIR" ]; then
        print_error "No se encontró el directorio del frontend en: $FRONTEND_DIR"
        print_info "Ubicación esperada: /Users/agustinestevezdominguez/Documents/RyderCupWeb"
        exit 1
    fi

    if [ ! -f "$FRONTEND_DIR/Dockerfile" ]; then
        print_error "No se encontró Dockerfile en: $FRONTEND_DIR"
        print_info "Asegúrate de que el proyecto RyderCupWeb tenga un Dockerfile"
        exit 1
    fi

    print_info "Tag: $tag"
    print_info "Directorio: $FRONTEND_DIR"

    # Construir la imagen
    if docker build -t "$tag" "$FRONTEND_DIR"; then
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

# Función para subir la imagen a Docker Hub
push_docker_image() {
    print_step "Subiendo imagen a Docker Hub..."

    local tag="${DOCKER_IMAGE}:${VERSION}"

    # Verificar login en Docker Hub
    if ! docker info | grep -q "Username:"; then
        print_warning "No estás logueado en Docker Hub"
        print_info "Ejecutando: docker login"
        docker login
    fi

    # Subir la imagen
    print_info "Pushing: $tag"
    if docker push "$tag"; then
        print_success "Imagen subida exitosamente: $tag"
    else
        print_error "Error al subir la imagen a Docker Hub"
        print_info "Verifica tus credenciales con: docker login"
        exit 1
    fi

    # Si no es "latest", también pushear latest
    if [ "$VERSION" != "latest" ]; then
        print_info "Pushing: ${DOCKER_IMAGE}:latest"
        docker push "${DOCKER_IMAGE}:latest"
    fi
}

# Función para actualizar el deployment en Kubernetes
update_deployment() {
    print_step "Actualizando deployment en Kubernetes..."

    local tag="${DOCKER_IMAGE}:${VERSION}"

    # Si es "latest", usar rollout restart (fuerza a descargar nueva imagen)
    if [ "$VERSION" == "latest" ]; then
        print_info "Reiniciando deployment (pulling latest image)..."
        kubectl rollout restart deployment/$DEPLOYMENT_NAME -n rydercupfriends
    else
        # Si es una versión específica, actualizar la imagen
        print_info "Actualizando imagen a: $tag"
        kubectl set image deployment/$DEPLOYMENT_NAME $CONTAINER_NAME=$tag -n rydercupfriends
    fi

    print_success "Comando de actualización ejecutado"
}

# Función para esperar y monitorear el rollout
wait_for_rollout() {
    print_step "Esperando a que se complete el rollout..."

    print_info "Estado del rollout:"

    # Esperar con timeout de 5 minutos
    if kubectl rollout status deployment/$DEPLOYMENT_NAME -n rydercupfriends --timeout=5m; then
        print_success "Rollout completado exitosamente"
    else
        print_error "El rollout ha tardado más de 5 minutos o ha fallado"
        print_warning "Verifica los logs: kubectl logs deployment/$DEPLOYMENT_NAME -n rydercupfriends"
        exit 1
    fi
}

# Función para verificar el estado post-deployment
verify_deployment() {
    print_step "Verificando estado del deployment..."

    echo ""
    echo "📋 Estado de los pods:"
    kubectl get pods -l component=frontend -n rydercupfriends

    echo ""
    echo "🔍 Imagen actual en los pods:"
    kubectl get pods -l component=frontend -n rydercupfriends -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

    echo ""
    print_info "Últimos logs del deployment:"
    kubectl logs deployment/$DEPLOYMENT_NAME -n rydercupfriends --tail=20

    # Verificar que todos los pods están Ready
    local ready_pods=$(kubectl get pods -l component=frontend -n rydercupfriends -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}')
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
    echo -e "${GREEN}✅ Imagen subida a Docker Hub${NC}"
    echo -e "${GREEN}✅ Deployment actualizado en Kubernetes${NC}"
    echo -e "${GREEN}✅ Rolling update completado sin downtime${NC}"

    echo ""
    print_info "Verificar el Frontend:"
    echo "  • URL: http://localhost:8080"
    echo "  • Health check: http://localhost:8080/health"

    echo ""
    print_info "Comandos útiles:"
    echo "  • Ver logs: kubectl logs deployment/$DEPLOYMENT_NAME -n rydercupfriends -f"
    echo "  • Ver estado: kubectl get pods -l component=frontend -n rydercupfriends"
    echo "  • Rollback: kubectl rollout undo deployment/$DEPLOYMENT_NAME -n rydercupfriends"

    echo ""
}

# Banner principal
clear
echo ""
echo "🚀 =================================================="
echo "   Ryder Cup Manager - Frontend Deployment"
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
build_docker_image
push_docker_image
update_deployment
wait_for_rollout
verify_deployment
print_summary

print_success "¡Deployment completado con éxito! 🎉"
echo ""
