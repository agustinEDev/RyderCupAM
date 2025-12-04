#!/bin/bash

# ==========================================
# Script para Detener Port-Forwards
# ==========================================
# Detiene todos los port-forwards activos
# ==========================================

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_step() {
    echo -e "${GREEN}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

echo ""
echo "🛑 Deteniendo port-forwards..."
echo ""

# ==========================================
# Intentar leer PIDs del archivo
# ==========================================
if [ -f /tmp/rydercup-port-forwards.pids ]; then
    print_step "Leyendo PIDs guardados..."

    while read pid; do
        if ps -p $pid > /dev/null 2>&1; then
            kill $pid 2>/dev/null && echo "   Detenido: PID $pid"
        fi
    done < /tmp/rydercup-port-forwards.pids

    rm /tmp/rydercup-port-forwards.pids
fi

# ==========================================
# Matar todos los port-forwards de kubectl
# ==========================================
print_step "Buscando port-forwards activos..."

PF_COUNT=$(ps aux | grep "kubectl port-forward" | grep -v grep | wc -l | tr -d ' ')

if [ "$PF_COUNT" -gt 0 ]; then
    pkill -f "kubectl port-forward"
    sleep 1
    print_success "Port-forwards detenidos ($PF_COUNT procesos)"
else
    print_warning "No hay port-forwards activos"
fi

echo ""
print_success "✨ ¡Listo!"
echo ""
