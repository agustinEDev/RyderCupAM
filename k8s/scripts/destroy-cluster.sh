#!/bin/bash

# ==========================================
# Script de Eliminación - Ryder Cup Manager
# ==========================================
# Este script elimina el cluster de Kubernetes completamente
# Uso: ./scripts/destroy-cluster.sh
# ==========================================

set -e  # Salir si algún comando falla

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir mensajes con colores
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_step() {
    echo -e "${BLUE}==>${NC} ${GREEN}$1${NC}"
}

# Banner
echo ""
echo "🗑️  =============================================="
echo "   Ryder Cup Manager - Cluster Cleanup"
echo "   =============================================="
echo ""

CLUSTER_NAME="rydercupam-cluster"

# ==========================================
# Verificar si el cluster existe
# ==========================================
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    print_warning "El cluster '${CLUSTER_NAME}' no existe"
    exit 0
fi

# ==========================================
# Confirmación
# ==========================================
print_warning "⚠️  ADVERTENCIA: Esta acción eliminará:"
echo "   • Todos los pods"
echo "   • Todos los datos de PostgreSQL"
echo "   • Todas las configuraciones"
echo "   • El cluster completo"
echo ""

read -p "¿Estás seguro de que quieres eliminar el cluster? (y/N): " -n 1 -r
echo
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Operación cancelada"
    exit 0
fi

# ==========================================
# Eliminar cluster
# ==========================================
print_step "Eliminando cluster '${CLUSTER_NAME}'..."

kind delete cluster --name ${CLUSTER_NAME}

print_success "Cluster eliminado exitosamente"
echo ""

# ==========================================
# Limpiar imágenes (opcional)
# ==========================================
read -p "¿Quieres eliminar también las imágenes Docker de Kind? (y/N): " -n 1 -r
echo
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_step "Eliminando imágenes Docker de Kind..."

    # Buscar y eliminar imágenes kindest/node
    IMAGES=$(docker images | grep kindest/node | awk '{print $3}')

    if [ -z "$IMAGES" ]; then
        print_warning "No se encontraron imágenes de Kind"
    else
        echo "$IMAGES" | xargs -r docker rmi -f
        print_success "Imágenes de Kind eliminadas"
    fi
fi

echo ""
print_success "🎉 ¡Cleanup completado!"
echo ""
echo "📋 Para volver a crear el cluster:"
echo "   ${GREEN}./scripts/deploy-cluster.sh${NC}"
echo ""
