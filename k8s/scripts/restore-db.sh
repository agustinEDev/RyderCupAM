#!/bin/bash

# ==========================================
# Script de Restore - PostgreSQL Database
# ==========================================
# This script restores the PostgreSQL database
# from a backup file
# Usage: ./scripts/restore-db.sh
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

# List available backups
list_backups() {
    print_step "Available backups..."
    
    BACKUP_DIR="$(dirname "$0")/../backups"
    
    if ls "$BACKUP_DIR"/db_backup_*.sql &> /dev/null; then
        echo ""
        ls -lht "$BACKUP_DIR"/db_backup_*.sql | awk '{print "  " $9 " (" $5 ", " $6 " " $7 " " $8 ")"}' | sed "s|$BACKUP_DIR/|  |"
        echo ""
        return 0
    else
        print_warning "No backup files found in $BACKUP_DIR"
        return 1
    fi
}

# Get backup file from user
get_backup_file() {
    print_step "Select backup file..."
    
    BACKUP_DIR="$(dirname "$0")/../backups"
    
    echo ""
    read -p "Enter backup filename: " BACKUP_INPUT
    echo ""
    
    # If user entered just filename, prepend directory
    if [[ "$BACKUP_INPUT" != /* ]] && [[ "$BACKUP_INPUT" != ./* ]]; then
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_INPUT"
    else
        BACKUP_FILE="$BACKUP_INPUT"
    fi
    
    # Check if file exists
    if [ ! -f "$BACKUP_FILE" ]; then
        print_error "File '$BACKUP_FILE' does not exist"
        exit 1
    fi
    
    # Check if file is not empty
    if [ ! -s "$BACKUP_FILE" ]; then
        print_error "File '$BACKUP_FILE' is empty"
        exit 1
    fi
    
    print_success "Backup file: $(basename "$BACKUP_FILE")"
    print_info "Size: $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"
}

# Display warning
show_warning() {
    print_header "⚠️  DATABASE RESTORE WARNING"
    echo ""
    print_warning "This script will:"
    echo "  1. DROP the current database"
    echo "  2. Restore from backup: $BACKUP_FILE"
    echo "  3. Apply pending Alembic migrations"
    echo "  4. Restart the database and API"
    echo ""
    print_warning "Note:"
    echo "  - ALL CURRENT DATA WILL BE LOST"
    echo "  - This action CANNOT be undone"
    echo "  - Downtime: ~2-3 minutes"
    echo ""
    
    read -n 1 -p "Do you want to continue? (y/N): " -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Operation cancelled"
        exit 0
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

# Check database health
check_db_health() {
    print_step "Checking database health..."
    
    # Check if pod is running
    POD_STATUS=$(kubectl get pod "$DB_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
    
    if [ "$POD_STATUS" != "Running" ]; then
        print_error "Database pod is not running (status: $POD_STATUS)"
        exit 1
    fi
    print_success "Pod status: Running"
    
    # Check if PostgreSQL is ready
    if kubectl exec -n "$NAMESPACE" "$DB_POD" -- pg_isready -U postgres > /dev/null 2>&1; then
        print_success "PostgreSQL: Ready"
    else
        print_warning "PostgreSQL is not ready, but will proceed with restore"
    fi
}

# Copy backup to pod
copy_backup_to_pod() {
    print_step "Copying backup to database pod..."
    
    kubectl cp "$BACKUP_FILE" "$NAMESPACE/$DB_POD:/tmp/restore.sql"
    
    if [ $? -eq 0 ]; then
        print_success "Backup copied successfully"
    else
        print_error "Failed to copy backup to pod"
        exit 1
    fi
}

# Restore database from backup
restore_database() {
    print_step "Restoring database from backup..."
    
    # Get PostgreSQL credentials
    POSTGRES_USER=$(kubectl get secret rydercup-api-secret -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_USER}' | base64 -d)
    POSTGRES_DB="rcfdevdb"
    
    print_info "Database: $POSTGRES_DB"
    print_info "User: $POSTGRES_USER"
    
    # Drop and recreate database
    print_info "Dropping current database..."
    kubectl exec -n "$NAMESPACE" "$DB_POD" -- psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $POSTGRES_DB;" 2>&1 | grep -v "NOTICE"
    
    print_info "Creating new database..."
    kubectl exec -n "$NAMESPACE" "$DB_POD" -- psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;" 2>&1
    
    # Restore from backup
    print_info "Restoring from backup file..."
    if kubectl exec -n "$NAMESPACE" "$DB_POD" -- psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/restore.sql > /dev/null 2>&1; then
        print_success "Database restored successfully"
    else
        print_error "Failed to restore database"
        exit 1
    fi
    
    # Clean up backup file from pod
    kubectl exec -n "$NAMESPACE" "$DB_POD" -- rm -f /tmp/restore.sql 2>/dev/null || true
}

# Run migrations
run_migrations() {
    print_step "Running Alembic migrations..."
    
    # Get an API pod
    API_POD=$(kubectl get pods -n "$NAMESPACE" -l component=api -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$API_POD" ]; then
        print_error "No API pod found"
        exit 1
    fi
    
    print_info "Using API pod: $API_POD"
    
    # Check current migration
    print_info "Checking current migration status..."
    kubectl exec -n "$NAMESPACE" "$API_POD" -- alembic current
    
    # Run migrations
    print_info "Applying migrations..."
    if kubectl exec -n "$NAMESPACE" "$API_POD" -- alembic upgrade head; then
        print_success "Migrations applied successfully"
    else
        print_warning "Some migrations may have failed - check logs above"
    fi
    
    # Show current migration again
    echo ""
    print_info "Current migration:"
    kubectl exec -n "$NAMESPACE" "$API_POD" -- alembic current
}

# Restart API pods to refresh connections
restart_api() {
    print_step "Restarting API pods..."
    
    print_info "Rolling restart of API deployment..."
    kubectl rollout restart deployment "$API_DEPLOYMENT" -n "$NAMESPACE"
    
    print_info "Waiting for rollout to complete..."
    kubectl rollout status deployment "$API_DEPLOYMENT" -n "$NAMESPACE" --timeout=180s
    
    print_success "API restarted successfully"
}

# Verify deployment
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
        print_success "API: Ready"
    else
        print_warning "API: Not all pods ready yet"
    fi
    
    # Test database connection from API
    API_POD=$(kubectl get pods -n "$NAMESPACE" -l component=api -o jsonpath='{.items[0].metadata.name}')
    if [ -n "$API_POD" ]; then
        sleep 5  # Give connections time to establish
        if kubectl exec -n "$NAMESPACE" "$API_POD" -- python -c "from src.config.database import get_session_factory; print('✓ DB connection OK')" 2>/dev/null; then
            print_success "Database connection: OK"
        else
            print_warning "Could not verify database connection"
        fi
    fi
}

# Main execution
main() {
    print_header "🔄 Restore Database from Backup"
    
    check_prerequisites
    list_backups
    get_backup_file
    show_warning
    get_db_pod
    check_db_health
    copy_backup_to_pod
    restore_database
    run_migrations
    restart_api
    verify_deployment
    
    print_header "✅ Database Restore Complete"
    echo ""
    print_success "Database has been restored from: $BACKUP_FILE"
    print_success "Migrations have been applied"
    print_success "API has been restarted"
    echo ""
    print_info "Next steps:"
    echo "  - Check logs: kubectl logs -n $NAMESPACE -l component=database --tail=50"
    echo "  - Check API: kubectl logs -n $NAMESPACE -l component=api --tail=50"
    echo "  - Port forward: ./k8s/scripts/start-port-forwards.sh"
    echo ""
}

# Run main function
main
