#!/bin/bash

# ==========================================
# Script de Restart - Cluster Services
# ==========================================
# Reinicia los deployments del cluster sin reconstruir imágenes.
# Útil para recargar ConfigMaps, Secrets y variables de entorno.
# Uso: ./scripts/restart-cluster.sh [--api|--front|--db|--all]
# Default: --all (reinicia API + Frontend)
# ==========================================

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuración
CLUSTER_NAME="rydercupam-cluster"
NAMESPACE="rydercupfriends"
TARGET="${1:---all}"

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

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Verificar prerrequisitos
check_prerequisites() {
    print_step "Verificando prerrequisitos..."

    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl no está instalado"
        exit 1
    fi

    if ! command -v kind &> /dev/null; then
        print_error "Kind no está instalado"
        exit 1
    fi

    if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
        print_error "El cluster Kind '${CLUSTER_NAME}' no existe"
        exit 1
    fi

    print_success "Cluster '${CLUSTER_NAME}' encontrado"
}

# Reaplicar ConfigMaps y Secrets
apply_configs() {
    print_step "Reaplicando ConfigMaps y Secrets..."

    local k8s_dir
    k8s_dir="$(dirname "$0")/.."

    if [ -f "$k8s_dir/api-configmap.yaml" ]; then
        kubectl apply -f "$k8s_dir/api-configmap.yaml"
        print_success "api-configmap aplicado"
    fi

    if [ -f "$k8s_dir/api-secret.yaml" ]; then
        kubectl apply -f "$k8s_dir/api-secret.yaml"
        print_success "api-secret aplicado"
    fi

    if [ -f "$k8s_dir/frontend-configmap.yaml" ]; then
        kubectl apply -f "$k8s_dir/frontend-configmap.yaml"
        print_success "frontend-configmap aplicado"
    fi
}

# Reiniciar un deployment y esperar rollout
restart_deployment() {
    local name=$1
    local label=$2

    if ! kubectl get deployment "$name" -n $NAMESPACE &> /dev/null; then
        print_info "Deployment '$name' no existe, saltando..."
        return
    fi

    print_info "Reiniciando $name..."
    kubectl rollout restart deployment/"$name" -n $NAMESPACE

    if kubectl rollout status deployment/"$name" -n $NAMESPACE --timeout=3m; then
        print_success "$name reiniciado"
    else
        print_error "$name no completó el rollout en 3 minutos"
        kubectl logs deployment/"$name" -n $NAMESPACE --tail=10
        return 1
    fi

    kubectl get pods -l component="$label" -n $NAMESPACE
}

# Banner
clear
echo ""
echo "🔄 =================================================="
echo "   Ryder Cup Manager - Cluster Restart"
echo "   =================================================="
echo ""
echo -e "${BOLD}Cluster:${NC}   ${CLUSTER_NAME}"
echo -e "${BOLD}Namespace:${NC} ${NAMESPACE}"
echo -e "${BOLD}Target:${NC}    ${TARGET}"
echo ""

check_prerequisites

print_header "🔄 REINICIANDO SERVICIOS"

# Reaplicar configs antes de reiniciar
apply_configs

# Reiniciar según target
case "$TARGET" in
    --api)
        restart_deployment "rydercup-api" "api"
        ;;
    --front)
        restart_deployment "rydercup-frontend" "frontend"
        ;;
    --db)
        restart_deployment "postgres" "database"
        ;;
    --all)
        restart_deployment "rydercup-api" "api"
        restart_deployment "rydercup-frontend" "frontend"
        ;;
    *)
        print_error "Opción no válida: $TARGET"
        echo "Uso: $0 [--api|--front|--db|--all]"
        exit 1
        ;;
esac

print_header "🎉 RESTART COMPLETADO"
echo ""
print_info "Los servicios han recargado ConfigMaps y Secrets."
print_info "Comandos útiles:"
echo "  • Ver logs API:      kubectl logs deployment/rydercup-api -n $NAMESPACE -f"
echo "  • Ver logs Frontend: kubectl logs deployment/rydercup-frontend -n $NAMESPACE -f"
echo "  • Ver pods:          kubectl get pods -n $NAMESPACE"
echo ""
