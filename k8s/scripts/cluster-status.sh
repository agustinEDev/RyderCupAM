#!/bin/bash

# ==========================================
# Script de Diagnóstico - Ryder Cup Manager
# ==========================================
# Este script muestra el estado completo del cluster
# Uso: ./scripts/cluster-status.sh
# ==========================================

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Función para imprimir títulos
print_header() {
    echo ""
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}${BOLD}  $1${NC}"
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_section() {
    echo ""
    echo -e "${BLUE}━━ $1 ━━${NC}"
    echo ""
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

# Banner
clear
echo ""
echo "🔍 =================================================="
echo "   Ryder Cup Manager - Cluster Status"
echo "   =================================================="
echo ""

CLUSTER_NAME="rydercupam-cluster"

# ==========================================
# 1. Verificar cluster existe
# ==========================================
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    print_error "El cluster '${CLUSTER_NAME}' no existe"
    echo ""
    echo "Para crear el cluster:"
    echo "  ./scripts/deploy-cluster.sh"
    echo ""
    exit 1
fi

# ==========================================
# 2. Información del cluster
# ==========================================
print_header "📊 INFORMACIÓN DEL CLUSTER"

echo "Cluster: ${GREEN}${CLUSTER_NAME}${NC}"
echo "Context: kind-${CLUSTER_NAME}"
echo ""

kubectl cluster-info --context kind-${CLUSTER_NAME} 2>/dev/null || print_error "No se pudo conectar al cluster"

# ==========================================
# 3. Nodos
# ==========================================
print_header "🖥️  NODOS"

kubectl get nodes -o wide

# ==========================================
# 4. Pods
# ==========================================
print_header "📦 PODS"

echo -e "${BOLD}Todos los pods de la aplicación:${NC}"
echo ""
kubectl get pods -l app=rydercup -o wide

echo ""
echo -e "${BOLD}Pods por componente:${NC}"

# Frontend
print_section "Frontend (nginx + React)"
FRONTEND_PODS=$(kubectl get pods -l component=frontend --no-headers 2>/dev/null | wc -l | tr -d ' ')
FRONTEND_RUNNING=$(kubectl get pods -l component=frontend --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')

if [ "$FRONTEND_PODS" -eq "$FRONTEND_RUNNING" ] && [ "$FRONTEND_PODS" -gt 0 ]; then
    print_success "Frontend: $FRONTEND_RUNNING/$FRONTEND_PODS pods Running"
else
    print_warning "Frontend: $FRONTEND_RUNNING/$FRONTEND_PODS pods Running"
fi

kubectl get pods -l component=frontend

# Backend
print_section "Backend (FastAPI)"
BACKEND_PODS=$(kubectl get pods -l component=api --no-headers 2>/dev/null | wc -l | tr -d ' ')
BACKEND_RUNNING=$(kubectl get pods -l component=api --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')

if [ "$BACKEND_PODS" -eq "$BACKEND_RUNNING" ] && [ "$BACKEND_PODS" -gt 0 ]; then
    print_success "Backend: $BACKEND_RUNNING/$BACKEND_PODS pods Running"
else
    print_warning "Backend: $BACKEND_RUNNING/$BACKEND_PODS pods Running"
fi

kubectl get pods -l component=api

# Database
print_section "Database (PostgreSQL)"
DATABASE_PODS=$(kubectl get pods -l component=database --no-headers 2>/dev/null | wc -l | tr -d ' ')
DATABASE_RUNNING=$(kubectl get pods -l component=database --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')

if [ "$DATABASE_PODS" -eq "$DATABASE_RUNNING" ] && [ "$DATABASE_PODS" -gt 0 ]; then
    print_success "Database: $DATABASE_RUNNING/$DATABASE_PODS pod Running"
else
    print_warning "Database: $DATABASE_RUNNING/$DATABASE_PODS pod Running"
fi

kubectl get pods -l component=database

# ==========================================
# 5. Services
# ==========================================
print_header "🌐 SERVICES"

kubectl get svc -l app=rydercup

# ==========================================
# 6. Deployments
# ==========================================
print_header "🚀 DEPLOYMENTS"

kubectl get deployments -l app=rydercup

# ==========================================
# 7. ConfigMaps y Secrets
# ==========================================
print_header "⚙️  CONFIGMAPS Y SECRETS"

print_section "ConfigMaps"
kubectl get configmaps -l app=rydercup

print_section "Secrets"
kubectl get secrets -l app=rydercup

# ==========================================
# 8. Almacenamiento
# ==========================================
print_header "💾 ALMACENAMIENTO PERSISTENTE"

kubectl get pvc

# ==========================================
# 9. Eventos recientes
# ==========================================
print_header "📋 EVENTOS RECIENTES (últimos 10)"

kubectl get events --sort-by=.metadata.creationTimestamp -l app=rydercup | tail -10

# ==========================================
# 10. Health checks
# ==========================================
print_header "❤️  HEALTH CHECKS"

print_section "Backend Health"
# Usar Python que está garantizado en la imagen FastAPI
HEALTH_CHECK_RESULT=$(kubectl exec deployment/rydercup-api -- python3 -c "
import urllib.request
try:
    response = urllib.request.urlopen('http://localhost:8000/', timeout=5)
    print(response.read().decode())
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)

if echo "$HEALTH_CHECK_RESULT" | grep -q '"status":"running"'; then
    print_success "Backend health check: OK"
else
    print_error "Backend health check: FAILED"
    echo "  Debug output:"
    echo "$HEALTH_CHECK_RESULT" | head -5
fi

print_section "Frontend Health"
if kubectl exec deployment/rydercup-frontend -- curl -s http://localhost/health 2>/dev/null | grep -q "healthy"; then
    print_success "Frontend health check: OK"
else
    print_error "Frontend health check: FAILED"
fi

# ==========================================
# 11. Port-forwards activos
# ==========================================
print_header "🔌 PORT-FORWARDS ACTIVOS"

PF_COUNT=$(ps aux | grep "kubectl port-forward" | grep -v grep | wc -l | tr -d ' ')

if [ "$PF_COUNT" -gt 0 ]; then
    echo "Port-forwards detectados: ${GREEN}$PF_COUNT${NC}"
    echo ""
    ps aux | grep "kubectl port-forward" | grep -v grep | awk '{print $11, $12, $13, $14}'
else
    print_warning "No hay port-forwards activos"
    echo ""
    echo "Para exponer la aplicación:"
    echo "  Terminal 1: ${GREEN}kubectl port-forward svc/rydercup-api-service 8000:80${NC}"
    echo "  Terminal 2: ${GREEN}kubectl port-forward svc/rydercup-frontend-service 8080:80${NC}"
fi

# ==========================================
# 12. Resumen final
# ==========================================
print_header "📊 RESUMEN"

TOTAL_PODS=$(kubectl get pods -l app=rydercup --no-headers 2>/dev/null | wc -l | tr -d ' ')
RUNNING_PODS=$(kubectl get pods -l app=rydercup --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')

echo "Total pods: $TOTAL_PODS"
echo "Pods Running: $RUNNING_PODS"

if [ "$TOTAL_PODS" -eq "$RUNNING_PODS" ] && [ "$TOTAL_PODS" -gt 0 ]; then
    echo ""
    print_success "✨ ¡Cluster completamente funcional!"
    echo ""
    echo "Acceder a la aplicación:"
    echo "  ${GREEN}http://localhost:8080${NC} (después de port-forward)"
else
    echo ""
    print_warning "⚠️  Algunos pods no están en Running"
    echo ""
    echo "Ver logs:"
    echo "  ${YELLOW}kubectl logs -f deployment/rydercup-frontend${NC}"
    echo "  ${YELLOW}kubectl logs -f deployment/rydercup-api${NC}"
    echo "  ${YELLOW}kubectl logs -f deployment/postgres${NC}"
fi

echo ""
echo "📚 Documentación completa: ${GREEN}docs/KUBERNETES_DEPLOYMENT_GUIDE.md${NC}"
echo ""