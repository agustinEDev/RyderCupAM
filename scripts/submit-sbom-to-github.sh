#!/usr/bin/env bash
#
# Submit SBOM to GitHub Dependency Graph
#
# Uses GitHub REST API to upload Software Bill of Materials (SBOM)
# to the repository's dependency graph for Dependabot integration.
#
# Requirements:
#   - GitHub token with 'repo' scope (GITHUB_TOKEN)
#   - CycloneDX SBOM file in JSON format
#   - Repository information (owner, name, ref)
#
# Usage:
#   ./submit-sbom-to-github.sh <sbom-file> <repo-owner> <repo-name> <ref-sha>
#
# Example:
#   ./submit-sbom-to-github.sh sbom/sbom.json agustinEDev RyderCupAM abc123def
#
# GitHub API Reference:
#   https://docs.github.com/en/rest/dependency-graph/dependency-submission
#
# OWASP Coverage:
#   - A08: Software and Data Integrity Failures (supply chain visibility)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}" >&2
}

# ============================================================================
# Input Validation
# ============================================================================

if [ $# -ne 4 ]; then
    log_error "Invalid number of arguments"
    echo "Usage: $0 <sbom-file> <repo-owner> <repo-name> <ref-sha>"
    echo ""
    echo "Example:"
    echo "  $0 sbom/sbom.json agustinEDev RyderCupAM \$GITHUB_SHA"
    exit 1
fi

SBOM_FILE="$1"
REPO_OWNER="$2"
REPO_NAME="$3"
REF_SHA="$4"

# Validate SBOM file exists
if [ ! -f "$SBOM_FILE" ]; then
    log_error "SBOM file not found: $SBOM_FILE"
    exit 1
fi

# Validate GITHUB_TOKEN is set
if [ -z "${GITHUB_TOKEN:-}" ]; then
    log_error "GITHUB_TOKEN environment variable is not set"
    echo "Please set GITHUB_TOKEN with 'repo' scope permissions"
    exit 1
fi

# ============================================================================
# SBOM Processing
# ============================================================================

log_info "Processing SBOM file: $SBOM_FILE"

# Validate SBOM is valid JSON
if ! jq empty "$SBOM_FILE" 2>/dev/null; then
    log_error "SBOM file is not valid JSON"
    exit 1
fi

# Extract SBOM metadata
SPEC_VERSION=$(jq -r '.specVersion' "$SBOM_FILE")
COMPONENT_COUNT=$(jq '.components | length' "$SBOM_FILE")
SERIAL_NUMBER=$(jq -r '.serialNumber' "$SBOM_FILE")

log_info "SBOM Metadata:"
echo "   - Spec Version: $SPEC_VERSION"
echo "   - Components: $COMPONENT_COUNT"
echo "   - Serial Number: $SERIAL_NUMBER"

# ============================================================================
# GitHub API Submission
# ============================================================================

log_info "Submitting SBOM to GitHub Dependency Graph..."

# GitHub API endpoint
API_URL="https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/dependency-graph/snapshots"

# Prepare payload
# Reference: https://docs.github.com/en/rest/dependency-graph/dependency-submission
PAYLOAD=$(cat <<EOF
{
  "version": 0,
  "sha": "$REF_SHA",
  "ref": "refs/heads/main",
  "job": {
    "correlator": "sbom_generation_$REF_SHA",
    "id": "$GITHUB_RUN_ID"
  },
  "detector": {
    "name": "cyclonedx-py",
    "version": "$(cyclonedx-py --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')",
    "url": "https://github.com/CycloneDX/cyclonedx-python"
  },
  "scanned": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "manifests": {
    "requirements.txt": {
      "name": "requirements.txt",
      "file": {
        "source_location": "requirements.txt"
      },
      "resolved": $(jq '.components | map({
        "package_url": .purl,
        "name": .name,
        "version": .version,
        "scope": "runtime",
        "dependencies": []
      })' "$SBOM_FILE")
    }
  }
}
EOF
)

# Submit to GitHub API
HTTP_CODE=$(curl -s -o /tmp/github_sbom_response.json -w "%{http_code}" \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -d "$PAYLOAD" \
  "$API_URL")

# ============================================================================
# Response Handling
# ============================================================================

if [ "$HTTP_CODE" == "201" ]; then
    log_success "SBOM successfully submitted to GitHub Dependency Graph"

    # Extract snapshot ID from response
    SNAPSHOT_ID=$(jq -r '.id' /tmp/github_sbom_response.json 2>/dev/null || echo "N/A")
    SNAPSHOT_CREATED_AT=$(jq -r '.created_at' /tmp/github_sbom_response.json 2>/dev/null || echo "N/A")

    echo ""
    echo "📦 Snapshot Details:"
    echo "   - ID: $SNAPSHOT_ID"
    echo "   - Created: $SNAPSHOT_CREATED_AT"
    echo "   - Components: $COMPONENT_COUNT"
    echo ""
    echo "✅ Dependencies are now visible in:"
    echo "   https://github.com/$REPO_OWNER/$REPO_NAME/network/dependencies"

    exit 0
elif [ "$HTTP_CODE" == "200" ]; then
    # Some versions of the API return 200 instead of 201
    log_success "SBOM successfully submitted to GitHub Dependency Graph (HTTP 200)"
    exit 0
else
    log_error "Failed to submit SBOM to GitHub (HTTP $HTTP_CODE)"

    # Show error details if available
    if [ -f /tmp/github_sbom_response.json ]; then
        echo ""
        echo "Error Response:"
        jq '.' /tmp/github_sbom_response.json 2>/dev/null || cat /tmp/github_sbom_response.json
    fi

    exit 1
fi
