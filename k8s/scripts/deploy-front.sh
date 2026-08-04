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
    if docker build --no-cache -t "$tag" "$FRONTEND_DIR"; then
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

    # Imagen que el deployment tiene configurada ahora mismo
    local current_image
    current_image=$(kubectl get deployment/$DEPLOYMENT_NAME -n $NAMESPACE \
        -o jsonpath="{.spec.template.spec.containers[?(@.name=='${CONTAINER_NAME}')].image}")

    # Siempre fijamos la imagen explícitamente: si el deployment se quedó apuntando
    # a una imagen ad-hoc de alguna prueba manual, un simple 'rollout restart'
    # relanzaría esa imagen vieja en lugar de la recién construida
    if [ -n "$current_image" ] && [ "$current_image" != "$tag" ]; then
        print_warning "El deployment apuntaba a otra imagen: $current_image"
    fi

    print_info "Fijando imagen a: $tag"
    kubectl set image deployment/$DEPLOYMENT_NAME $CONTAINER_NAME=$tag -n $NAMESPACE

    # Si la imagen ya era la correcta, 'set image' no modifica el spec y no dispara
    # ningún rollout: hace falta un restart para que los pods recojan la build nueva
    if [ "$current_image" == "$tag" ]; then
        print_info "La imagen ya estaba fijada; reiniciando para recoger la nueva build..."
        kubectl rollout restart deployment/$DEPLOYMENT_NAME -n $NAMESPACE
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
    kubectl get pods -l component=frontend -n $NAMESPACE

    echo ""
    echo "🔍 Imagen actual en los pods:"
    kubectl get pods -l component=frontend -n $NAMESPACE -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

    echo ""
    print_info "Últimos logs del deployment:"
    kubectl logs deployment/$DEPLOYMENT_NAME -n $NAMESPACE --tail=20

    # Verificar que todos los pods están Ready
    local ready_pods=$(kubectl get pods -l component=frontend -n $NAMESPACE -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}')
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
    print_info "Verificar el Frontend:"
    echo "  • URL: http://localhost:8080"
    echo "  • Health check: http://localhost:8080/health"

    echo ""
    print_info "Comandos útiles:"
    echo "  • Ver logs: kubectl logs deployment/$DEPLOYMENT_NAME -n $NAMESPACE -f"
    echo "  • Ver estado: kubectl get pods -l component=frontend -n $NAMESPACE"
    echo "  • Rollback: kubectl rollout undo deployment/$DEPLOYMENT_NAME -n $NAMESPACE"

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
load_to_kind
update_deployment
wait_for_rollout
verify_deployment
print_summary

print_success "¡Deployment completado con éxito! 🎉"
echo ""
