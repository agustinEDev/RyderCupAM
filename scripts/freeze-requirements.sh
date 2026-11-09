#!/bin/bash
# ================================
# Requirements Freeze with Hashes
# ================================
# Generates requirements.lock with SHA256 hashes for dependency verification
# Complies with OWASP A08:2021 Software and Data Integrity Failures
#
# Usage: ./scripts/freeze-requirements.sh   (from the repo root, with Docker running)
#
# The lock is resolved INSIDE the production base image (same digest as
# docker/Dockerfile): resolving on a Mac with another Python could pick other
# transitive dependencies than the ones the image installs. The image installs
# it with --require-hashes, and tests/unit/config/test_dependencias_con_hash.py
# checks that it pins the same versions as requirements.txt.

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Requirements Freeze with Hashes${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${GREEN}[1/3]${NC} Reading the base image from docker/Dockerfile..."
BASE_IMAGE=$(grep -m1 -E '^FROM ' docker/Dockerfile | awk '{print $2}')
echo "   $BASE_IMAGE"

echo -e "${GREEN}[2/3]${NC} Generating requirements.lock with SHA256 hashes inside that image..."
docker run --rm -v "$PWD":/w -w /w "$BASE_IMAGE" sh -c "\
    pip install --quiet pip-tools==7.6.2 && \
    pip-compile requirements.txt \
        --output-file requirements.lock \
        --generate-hashes \
        --allow-unsafe \
        --no-emit-index-url \
        --no-emit-trusted-host \
        --strip-extras \
        --quiet"

echo -e "${GREEN}[3/3]${NC} Generating lock file metadata..."
HASH_COUNT=$(grep -c "sha256:" requirements.lock)
PKG_COUNT=$(grep -c "^[a-zA-Z0-9-]*==" requirements.lock)

cat > requirements.lock.metadata << EOF
Requirements Lock Metadata
==========================
Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Source: requirements.txt
Tool: pip-compile (pip-tools)
Hash Algorithm: SHA256

Statistics:
- Packages: $PKG_COUNT
- Total hashes: $HASH_COUNT
- Integrity verification: Enabled

OWASP Compliance:
- A08:2021 Software and Data Integrity Failures
- Protects against dependency tampering/substitution
- Enables reproducible builds

Usage:
  pip install -r requirements.lock --require-hashes

Verification:
  Lock file SHA256: $(sha256sum requirements.lock | awk '{print $1}')
EOF

echo ""
echo -e "${GREEN}✅ Requirements Lock Generated!${NC}"
echo ""
echo "📄 Output files:"
echo "   - requirements.lock ($(wc -l < requirements.lock) lines)"
echo "   - requirements.lock.metadata"
echo ""
echo "📊 Statistics:"
echo "   - Packages: $PKG_COUNT"
echo "   - Hashes: $HASH_COUNT"
echo ""
echo "🔒 Security:"
echo "   - All dependencies locked with SHA256 hashes"
echo "   - Prevents dependency substitution attacks"
echo "   - Enables reproducible builds"
echo ""
echo -e "${BLUE}========================================${NC}"
