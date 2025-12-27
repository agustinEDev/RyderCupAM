#!/bin/bash
# test-validation.sh
# Script para probar la validación de variables de entorno

set -e

echo "🧪 Testing fail-fast validation scripts..."
echo ""

# Test 1: Simular variables vacías para PostgreSQL
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 1: Missing POSTGRES_USER (should fail)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
export POSTGRES_PASSWORD="test"
export POSTGRES_DB="test"
unset POSTGRES_USER

if /bin/sh ./docker/scripts/validate-postgres-env.sh 2>&1 | head -20; then
    echo "❌ Test FAILED: Script should have exited with error"
    exit 1
else
    echo "✅ Test PASSED: Script correctly detected missing POSTGRES_USER"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 2: All variables set (should pass)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
export POSTGRES_USER="testuser"
export POSTGRES_PASSWORD="testpass"
export POSTGRES_DB="testdb"

# Mock docker-entrypoint.sh para evitar iniciar postgres real
cat > /tmp/mock-docker-entrypoint.sh << 'EOF'
#!/bin/sh
echo "Mock PostgreSQL would start here"
exit 0
EOF
chmod +x /tmp/mock-docker-entrypoint.sh

# Temporalmente reemplazar docker-entrypoint.sh
PATH="/tmp:$PATH" /bin/sh ./docker/scripts/validate-postgres-env.sh 2>&1 | tail -5

echo ""
echo "✅ All validation tests completed successfully!"
