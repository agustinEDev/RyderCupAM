#!/bin/sh
# validate-app-env.sh
# Validates required application environment variables before starting FastAPI

set -e

echo "🔍 Validating application environment variables..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Flag to track if all validations pass
ALL_VALID=true

# Required environment variables (critical for startup)
REQUIRED_VARS="POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB SECRET_KEY"

# Warning variables (recommended but not critical)
WARNING_VARS="MAILGUN_API_KEY DOCS_USERNAME DOCS_PASSWORD"

echo "${YELLOW}Checking REQUIRED variables:${NC}"
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

echo ""
echo "${YELLOW}Checking OPTIONAL variables:${NC}"
# Validate warning variables (non-blocking)
for VAR in $WARNING_VARS; do
    eval VALUE=\$$VAR
    if [ -z "$VALUE" ]; then
        echo "${YELLOW}⚠️  WARNING: Optional variable '$VAR' is not set${NC}"
    else
        echo "${GREEN}✓${NC} $VAR is set"
    fi
done

# Exit with error if any required validation failed
if [ "$ALL_VALID" = false ]; then
    echo ""
    echo "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
    echo "${RED}FAIL-FAST VALIDATION FAILED${NC}" >&2
    echo "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
    echo ""
    echo "One or more REQUIRED environment variables are missing." >&2
    echo ""
    echo "Please ensure your .env file exists and contains:" >&2
    echo ""
    echo "${YELLOW}Database Configuration (REQUIRED):${NC}" >&2
    echo "  POSTGRES_USER=rydercupam_adminuser" >&2
    echo "  POSTGRES_PASSWORD=your_secure_password" >&2
    echo "  POSTGRES_DB=rydercupam_db" >&2
    echo "" >&2
    echo "${YELLOW}Security Configuration (REQUIRED):${NC}" >&2
    echo "  SECRET_KEY=your_secret_key_here" >&2
    echo "" >&2
    echo "${YELLOW}Optional Configuration:${NC}" >&2
    echo "  MAILGUN_API_KEY=your_mailgun_key" >&2
    echo "  DOCS_USERNAME=admin" >&2
    echo "  DOCS_PASSWORD=secure_password" >&2
    echo "" >&2
    echo "💡 Tip: Copy .env.example to .env and fill in the values" >&2
    echo "" >&2
    echo "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
    exit 1
fi

echo "${GREEN}✅ All required environment variables validated successfully!${NC}"
echo ""

# Execute the original command (passed as arguments to this script)
exec "$@"
