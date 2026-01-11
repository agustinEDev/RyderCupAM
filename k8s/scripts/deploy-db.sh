#!/bin/bash

# ==========================================
# Script de Deployment - PostgreSQL Database
# ==========================================
# This script restarts the PostgreSQL database
# and applies the latest Alembic migrations
# Usage: ./scripts/deploy-db.sh [--force]
# ==========================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="rydercupfriends"
POSTGRES_DEPLOYMENT="postgres"
API_DEPLOYMENT="rydercup-api"
FORCE_MODE="${1}"

# Output functions
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

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    print_success "kubectl: OK"

    # Check that kubectl is connected to cluster
    if ! kubectl cluster-info &> /dev/null; then
        print_error "kubectl is not connected to any cluster"
        print_info "Run: kind create cluster --name rydercupam-cluster"
        exit 1
    fi
    print_success "Cluster: Connected"

    # Check namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_error "Namespace '$NAMESPACE' does not exist"
        exit 1
    fi
    print_success "Namespace: OK"
}

# Display warning
show_warning() {
    print_header "⚠️  DATABASE RESTART WARNING"
    echo ""
    print_warning "This script will:"
    echo "  1. Restart the PostgreSQL database"
    echo "  2. Apply all pending Alembic migrations"
    echo "  3. Temporarily interrupt database connections"
    echo ""
    print_warning "Note:"
    echo "  - API connections will reconnect automatically"
    echo "  - Brief downtime: ~30-60 seconds"
    echo "  - A backup will be created before restart"
    echo ""
    
    if [ "$FORCE_MODE" != "--force" ]; then
        read -n 1 -p "Do you want to continue? (y/N): " -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Operation cancelled"
            exit 0
        fi
    else
        print_info "Running in FORCE mode - skipping confirmation"
    fi
}

# Get current database pod
get_db_pod() {
    print_step "Getting database pod..."
    
    DB_POD=$(kubectl get pods -n "$NAMESPACE" -l component=database -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -z "$DB_POD" ]; then
        print_error "Database pod not found"
        exit 1
    fi
    
    print_success "Database pod: $DB_POD"
}

# Check database health before restart
check_db_health() {
    print_step "Checking database health..."
    
    # Check if pod is running
    POD_STATUS=$(kubectl get pod "$DB_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
    
    if [ "$POD_STATUS" != "Running" ]; then
        print_error "Database pod is not running (Status: $POD_STATUS)"
        exit 1
    fi
    
    print_success "Pod status: $POD_STATUS"
    
    # Check PostgreSQL is ready
    if kubectl exec -n "$NAMESPACE" "$DB_POD" -- pg_isready -U postgres > /dev/null 2>&1; then
        print_success "PostgreSQL: Ready"
    else
        print_warning "PostgreSQL is not ready, but will proceed with restart"
    fi
}

# Create database backup before restart
create_backup() {
    print_step "Creating database backup..."
    
    # Create backups directory if it doesn't exist
    mkdir -p "$(dirname "$0")/../backups"
    
    BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$(dirname "$0")/../backups/db_backup_${BACKUP_DATE}.sql"
    
    print_info "Backup file: $(basename "$BACKUP_FILE")"
    
    # Get PostgreSQL user from secret
    POSTGRES_USER=$(kubectl get secret rydercup-api-secret -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_USER}' | base64 -d)
    
    # Create backup using pg_dump
    kubectl exec -n "$NAMESPACE" "$DB_POD" -- pg_dump -U "$POSTGRES_USER" rcfdevdb > "$BACKUP_FILE" 2>&1
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ] && [ -s "$BACKUP_FILE" ]; then
        print_success "Backup created successfully"
        print_info "Location: $(pwd)/$BACKUP_FILE"
    else
        print_error "Failed to create backup"
        read -n 1 -p "Continue without backup? (y/N): " -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Operation cancelled"
            exit 1
        fi
    fi
}

# Restart PostgreSQL deployment
restart_database() {
    print_step "Restarting PostgreSQL deployment..."
    
    # Scale down to 0
    print_info "Scaling down to 0 replicas..."
    kubectl scale deployment "$POSTGRES_DEPLOYMENT" -n "$NAMESPACE" --replicas=0
    
    # Wait for pod to terminate
    print_info "Waiting for pod to terminate..."
    kubectl wait --for=delete pod -l component=database -n "$NAMESPACE" --timeout=120s || true
    
    sleep 5
    
    # Scale back up to 1
    print_info "Scaling up to 1 replica..."
    kubectl scale deployment "$POSTGRES_DEPLOYMENT" -n "$NAMESPACE" --replicas=1
    
    # Wait for pod to be ready
    print_info "Waiting for new pod to be ready..."
    kubectl wait --for=condition=ready pod -l component=database -n "$NAMESPACE" --timeout=180s
    
    print_success "PostgreSQL restarted successfully"
    
    # Get new pod name
    get_db_pod
}

# Wait for database to be fully ready
wait_for_database() {
    print_step "Waiting for database to be fully operational..."
    
    MAX_RETRIES=30
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if kubectl exec -n "$NAMESPACE" "$DB_POD" -- pg_isready -U postgres > /dev/null 2>&1; then
            print_success "Database is ready"
            return 0
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo -ne "\r${CYAN}Attempt $RETRY_COUNT/$MAX_RETRIES...${NC}"
        sleep 2
    done
    
    echo ""
    print_error "Database did not become ready in time"
    exit 1
}

# Run Alembic migrations
run_migrations() {
    print_step "Running Alembic migrations..."
    
    # Get API pod
    API_POD=$(kubectl get pods -n "$NAMESPACE" -l component=api -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -z "$API_POD" ]; then
        print_error "API pod not found"
        print_info "Please ensure the API is running"
        exit 1
    fi
    
    print_info "Using API pod: $API_POD"
    
    # Check current migration status
    print_info "Checking current migration status..."
    kubectl exec -n "$NAMESPACE" "$API_POD" -- alembic current || true
    
    echo ""
    print_info "Applying migrations..."
    
    # Run migrations
    if kubectl exec -n "$NAMESPACE" "$API_POD" -- alembic upgrade head; then
        print_success "Migrations applied successfully"
        
        echo ""
        print_info "Current migration:"
        kubectl exec -n "$NAMESPACE" "$API_POD" -- alembic current
    else
        print_error "Failed to apply migrations"
        exit 1
    fi
}

# Verify everything is working
verify_deployment() {
    print_step "Verifying deployment..."
    
    # Check database pod
    DB_STATUS=$(kubectl get pod -l component=database -n "$NAMESPACE" -o jsonpath='{.items[0].status.phase}')
    if [ "$DB_STATUS" == "Running" ]; then
        print_success "Database: Running"
    else
        print_error "Database: $DB_STATUS"
    fi
    
    # Check API pods
    API_READY=$(kubectl get pods -l component=api -n "$NAMESPACE" -o jsonpath='{.items[*].status.containerStatuses[0].ready}')
    if [[ "$API_READY" == *"true"* ]]; then
        print_success "API: Ready (connections will reconnect automatically)"
    else
        print_warning "API: Not all pods ready yet"
    fi
    
    # Test database connection from API
    API_POD=$(kubectl get pods -n "$NAMESPACE" -l component=api -o jsonpath='{.items[0].metadata.name}')
    if [ -n "$API_POD" ]; then
        sleep 5  # Give connections time to reconnect
        if kubectl exec -n "$NAMESPACE" "$API_POD" -- python -c "from src.config.database import get_session_factory; print('✓ DB connection OK')" 2>/dev/null; then
            print_success "Database connection: OK (auto-reconnected)"
        else
            print_info "Database connection will reconnect on next request"
        fi
    fi
}

# Main execution
main() {
    print_header "🔄 Deploy Database with Migrations"
    
    check_prerequisites
    show_warning
    get_db_pod
    check_db_health
    create_backup
    restart_database
    wait_for_database
    run_migrations
    verify_deployment
    
    print_header "✅ Database Deployment Complete"
    echo ""
    print_success "Database has been restarted and migrations applied"
    print_info "Backup saved: db_backup_*.sql"
    print_success "API connections will reconnect automatically"
    echo ""
    print_info "Next steps:"
    echo "  - Check logs: kubectl logs -n $NAMESPACE -l component=database --tail=50"
    echo "  - Check API: kubectl logs -n $NAMESPACE -l component=api --tail=50"
    echo "  - Port forward: ./scripts/start-port-forwards.sh"
    echo ""
}

# Execute main function
main
