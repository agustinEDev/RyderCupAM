#!/bin/bash
# ================================
# SBOM Generation Script
# ================================
# Generates Software Bill of Materials (SBOM) in CycloneDX format
# Complies with OWASP A08:2021 Software and Data Integrity Failures
#
# Usage: ./scripts/generate-sbom.sh [output-format]
#   output-format: json (default), xml
#
# Requirements: cyclonedx-bom (pip install cyclonedx-bom)

set -e

# Configuration
OUTPUT_DIR="sbom"
FORMAT="${1:-json}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  SBOM Generation (CycloneDX)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo -e "${GREEN}[1/4]${NC} Checking dependencies..."
if ! command -v cyclonedx-py &> /dev/null; then
    echo -e "${YELLOW}⚠️  cyclonedx-bom not found. Installing...${NC}"
    pip install cyclonedx-bom
fi

echo -e "${GREEN}[2/4]${NC} Generating SBOM from requirements.txt..."
cyclonedx-py requirements \
    --input requirements.txt \
    --output "$OUTPUT_DIR/sbom.$FORMAT" \
    --format "$FORMAT" \
    --verbose

echo -e "${GREEN}[3/4]${NC} Generating timestamped backup..."
cp "$OUTPUT_DIR/sbom.$FORMAT" "$OUTPUT_DIR/sbom_${TIMESTAMP}.$FORMAT"

echo -e "${GREEN}[4/4]${NC} Generating SBOM metadata..."

# Extract specVersion from generated SBOM
SPEC_VERSION=$(jq -r '.specVersion // "1.6"' "$OUTPUT_DIR/sbom.$FORMAT" 2>/dev/null || echo "1.6")

cat > "$OUTPUT_DIR/sbom-metadata.txt" << EOF
SBOM Metadata
=============
Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Format: CycloneDX $FORMAT
Standard: OWASP CycloneDX $SPEC_VERSION
Source: requirements.txt
Tool: cyclonedx-py
Project: Ryder Cup Amateur Manager Backend
Version: 2.0.0

Files:
- sbom.$FORMAT (latest)
- sbom_${TIMESTAMP}.$FORMAT (timestamped)

Verification:
SHA256: $(sha256sum "$OUTPUT_DIR/sbom.$FORMAT" | awk '{print $1}')

OWASP Compliance:
- A08:2021 Software and Data Integrity Failures
- NIST SP 800-161r1 (Supply Chain Risk Management)
EOF

echo ""
echo -e "${GREEN}✅ SBOM Generated Successfully!${NC}"
echo ""
echo "📄 Output files:"
echo "   - $OUTPUT_DIR/sbom.$FORMAT"
echo "   - $OUTPUT_DIR/sbom_${TIMESTAMP}.$FORMAT"
echo "   - $OUTPUT_DIR/sbom-metadata.txt"
echo ""
echo "📊 Statistics:"
COMPONENT_COUNT=$(jq '.components | length' "$OUTPUT_DIR/sbom.$FORMAT" 2>/dev/null || echo "N/A")
echo "   - Components: $COMPONENT_COUNT"
echo "   - Format: CycloneDX 1.6 ($FORMAT)"
echo ""
echo -e "${BLUE}========================================${NC}"
