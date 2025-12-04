#!/bin/bash

# ==========================================
# Script de Port-Forwards Automáticos
# ==========================================
# Este script ejecuta ambos port-forwards en background
# Útil si el cluster NO fue creado con kind-config.yaml
# ==========================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() {
    echo -e "${BLUE}==>${NC} ${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Banner
echo ""
echo "🔌 =============================================="
echo "   Port-Forwards Manuales"
echo "   =============================================="
echo ""

# ==========================================
# Verificar que el cluster está corriendo
# ==========================================
if ! kubectl cluster-info &> /dev/null; then
    print_warning "El cluster no está corriendo"
    echo ""
    echo "Iniciar cluster:"
    echo "  docker start rydercupam-cluster-control-plane"
    echo ""
    exit 1
fi

# ==========================================
# Verificar si port mappings automáticos funcionan
# ==========================================
print_step "Verificando configuración de port mappings..."

API_NODEPORT=$(kubectl get svc rydercup-api-service -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)
FRONTEND_NODEPORT=$(kubectl get svc rydercup-frontend-service -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)

if [ "$API_NODEPORT" = "30321" ] && [ "$FRONTEND_NODEPORT" = "32315" ]; then
    echo ""
    print_warning "⚠️  Los port mappings automáticos YA están configurados"
    echo ""
    echo "Tus servicios están accesibles directamente en:"
    echo -e "  ${GREEN}http://localhost:8080${NC}  → Frontend"
    echo -e "  ${GREEN}http://localhost:8000${NC}  → Backend API"
    echo ""
    echo "NodePorts detectados:"
    echo "  Backend:  $API_NODEPORT ✅"
    echo "  Frontend: $FRONTEND_NODEPORT ✅"
    echo ""
    read -p "¿Aún así quieres iniciar port-forwards manuales? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Operación cancelada"
        echo ""
        echo "Para verificar el estado del cluster:"
        echo -e "  ${GREEN}./k8s/scripts/cluster-status.sh${NC}"
        echo ""
        exit 0
    fi
    echo ""
    print_warning "Continuando con port-forwards manuales (pueden entrar en conflicto)..."
else
    print_success "Port mappings automáticos NO configurados - port-forwards son necesarios"
    echo ""
    echo "NodePorts actuales:"
    echo "  Backend:  $API_NODEPORT (esperado: 30321)"
    echo "  Frontend: $FRONTEND_NODEPORT (esperado: 32315)"
fi

echo ""

# ==========================================
# Verificar que los Services existen
# ==========================================
if ! kubectl get svc rydercup-api-service &> /dev/null; then
    print_warning "El servicio 'rydercup-api-service' no existe"
    echo ""
    echo "Desplegar aplicación primero:"
    echo "  ./scripts/deploy-cluster.sh"
    echo ""
    exit 1
fi

# ==========================================
# Matar port-forwards existentes
# ==========================================
print_step "Buscando port-forwards existentes..."

EXISTING_PF=$(ps aux | grep "kubectl port-forward" | grep -v grep || true)

if [ -n "$EXISTING_PF" ]; then
    print_warning "Encontrados port-forwards activos. Cerrándolos..."
    pkill -f "kubectl port-forward" || true
    sleep 2
    print_success "Port-forwards anteriores cerrados"
fi

# ==========================================
# Iniciar port-forwards en background
# ==========================================
print_step "Iniciando port-forwards..."

# Backend (8000)
kubectl port-forward svc/rydercup-api-service 8000:80 > /dev/null 2>&1 &
BACKEND_PID=$!

sleep 1

# Frontend (8080)
kubectl port-forward svc/rydercup-frontend-service 8080:80 > /dev/null 2>&1 &
FRONTEND_PID=$!

sleep 2

# ==========================================
# Verificar que están corriendo
# ==========================================
if ps -p $BACKEND_PID > /dev/null && ps -p $FRONTEND_PID > /dev/null; then
    print_success "Port-forwards iniciados correctamente"
    echo ""
    echo "📋 Port-forwards activos:"
    echo "   Backend:  ${GREEN}localhost:8000${NC} → rydercup-api-service:80 (PID: $BACKEND_PID)"
    echo "   Frontend: ${GREEN}localhost:8080${NC} → rydercup-frontend-service:80 (PID: $FRONTEND_PID)"
    echo ""
    echo "🌐 Abrir en el navegador:"
    echo "   ${GREEN}http://localhost:8080${NC}"
    echo ""
    echo "🛑 Para detener los port-forwards:"
    echo "   ${YELLOW}./scripts/stop-port-forwards.sh${NC}"
    echo "   o"
    echo "   ${YELLOW}kill $BACKEND_PID $FRONTEND_PID${NC}"
    echo ""

    # Guardar PIDs en archivo temporal
    echo "$BACKEND_PID" > /tmp/rydercup-port-forwards.pids
    echo "$FRONTEND_PID" >> /tmp/rydercup-port-forwards.pids

    print_success "PIDs guardados en /tmp/rydercup-port-forwards.pids"
else
    print_warning "Error al iniciar port-forwards"
    echo ""
    echo "Verificar manualmente:"
    echo "  ps aux | grep 'kubectl port-forward'"
    exit 1
fi

echo ""
print_success "✨ ¡Listo! Los port-forwards están corriendo en background"
echo ""
