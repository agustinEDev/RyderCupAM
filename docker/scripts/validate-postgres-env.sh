#!/bin/sh
# validate-postgres-env.sh
# Validates required PostgreSQL environment variables before starting the database

set -e

echo "🔍 Validating PostgreSQL environment variables..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Flag to track if all validations pass
ALL_VALID=true

# Required PostgreSQL environment variables
REQUIRED_VARS="POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB"

# Validate each required variable
for VAR in $REQUIRED_VARS; do
    eval VALUE=\$$VAR
    if [ -z "$VALUE" ]; then
        echo "${RED}❌ ERROR: Required environment variable '$VAR' is not set or is empty${NC}" >&2
        ALL_VALID=false
    elif echo "$VALUE" | grep -q "^MISSING_"; then
        echo "${RED}❌ ERROR: Required environment variable '$VAR' has invalid placeholder value: $VALUE${NC}" >&2
        ALL_VALID=false
    else
        echo "${GREEN}✓${NC} $VAR is set"
    fi
done

# Exit with error if any validation failed
if [ "$ALL_VALID" = false ]; then
    echo ""
    echo "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
    echo "${RED}FAIL-FAST VALIDATION FAILED${NC}" >&2
    echo "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
    echo ""
    echo "One or more required PostgreSQL environment variables are missing." >&2
    echo ""
    echo "Please ensure your .env file exists and contains:" >&2
    echo "  - POSTGRES_USER" >&2
    echo "  - POSTGRES_PASSWORD" >&2
    echo "  - POSTGRES_DB" >&2
    echo ""
    echo "Example .env file:" >&2
    echo "  POSTGRES_USER=rydercupam_adminuser" >&2
    echo "  POSTGRES_PASSWORD=your_secure_password" >&2
    echo "  POSTGRES_DB=rydercupam_db" >&2
    echo ""
    echo "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
    exit 1
fi

echo "${GREEN}✅ All PostgreSQL environment variables validated successfully!${NC}"
echo ""

# Execute the original PostgreSQL entrypoint
exec docker-entrypoint.sh postgres
