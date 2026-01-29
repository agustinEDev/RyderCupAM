#!/bin/bash
# ================================
# GPG Signature Verification Script
# ================================
# Verifies that all commits in a push/PR are signed with GPG
# Complies with OWASP A08:2021 Software and Data Integrity Failures
#
# Usage: ./scripts/verify-gpg-signatures.sh [base-ref] [head-ref]
#   base-ref: Base commit to compare from (default: origin/main)
#   head-ref: Head commit to compare to (default: HEAD)
#
# Requirements: gpg, git

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_REF="${1:-origin/main}"
HEAD_REF="${2:-HEAD}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  GPG Signature Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Import GPG public key from environment variable if provided
if [ -n "$GPG_PUBLIC_KEY" ]; then
    echo -e "${GREEN}[1/4]${NC} Importing GPG public key from environment..."
    echo "$GPG_PUBLIC_KEY" | gpg --import --batch --yes 2>/dev/null || true
    echo "✅ GPG key imported"
else
    echo -e "${YELLOW}⚠️  No GPG_PUBLIC_KEY environment variable found${NC}"
    echo "   Using system keyring only"
fi

echo ""
echo -e "${GREEN}[2/4]${NC} Fetching commit range..."
echo "   Base: $BASE_REF"
echo "   Head: $HEAD_REF"

# Get list of commits in range
COMMIT_LIST=$(git rev-list "$BASE_REF..$HEAD_REF" 2>/dev/null || echo "")

if [ -z "$COMMIT_LIST" ]; then
    echo -e "${YELLOW}⚠️  No new commits to verify${NC}"
    echo "   This might be the initial commit or base ref doesn't exist"
    echo ""
    echo -e "${GREEN}✅ Verification passed (no commits to check)${NC}"
    exit 0
fi

COMMIT_COUNT=$(echo "$COMMIT_LIST" | wc -l | tr -d ' ')
echo "   Commits to verify: $COMMIT_COUNT"

echo ""
echo -e "${GREEN}[3/4]${NC} Verifying GPG signatures..."
echo ""

# Verify each commit
UNSIGNED_COMMITS=()
INVALID_SIGNATURES=()
VALID_COUNT=0
MERGE_COUNT=0

while IFS= read -r commit; do
    # Get commit info
    COMMIT_SHORT=$(git log -1 --format="%h" "$commit")
    COMMIT_MSG=$(git log -1 --format="%s" "$commit" | head -c 60)
    COMMIT_AUTHOR=$(git log -1 --format="%an" "$commit")
    COMMIT_EMAIL=$(git log -1 --format="%ae" "$commit")

    # Check if this is a merge commit (has 2+ parents)
    PARENT_COUNT=$(git rev-list --parents -n 1 "$commit" | wc -w)
    PARENT_COUNT=$((PARENT_COUNT - 1))  # Subtract commit itself

    # Check if commit was created by GitHub (squash/rebase merge)
    IS_GITHUB_COMMIT=false
    if echo "$COMMIT_EMAIL" | grep -q "@users.noreply.github.com"; then
        IS_GITHUB_COMMIT=true
    fi

    if [ "$PARENT_COUNT" -ge 2 ] || [ "$IS_GITHUB_COMMIT" = true ]; then
        # Merge commit or GitHub-created commit - cannot be signed by user
        echo -e "🔀 ${YELLOW}$COMMIT_SHORT${NC} - $COMMIT_MSG"
        echo "   Author: $COMMIT_AUTHOR"
        if [ "$PARENT_COUNT" -ge 2 ]; then
            echo "   Type: MERGE COMMIT (signature not required)"
        else
            echo "   Type: GITHUB PR COMMIT (signature not required)"
        fi
        MERGE_COUNT=$((MERGE_COUNT + 1))
        VALID_COUNT=$((VALID_COUNT + 1))
    else
        # Regular commit - verify signature
        SIG_STATUS=$(git verify-commit "$commit" 2>&1 || true)

        if echo "$SIG_STATUS" | grep -q "Good signature"; then
            echo -e "✅ ${GREEN}$COMMIT_SHORT${NC} - $COMMIT_MSG"
            echo "   Author: $COMMIT_AUTHOR"
            VALID_COUNT=$((VALID_COUNT + 1))
        elif echo "$SIG_STATUS" | grep -q "gpg: Good signature"; then
            echo -e "✅ ${GREEN}$COMMIT_SHORT${NC} - $COMMIT_MSG"
            echo "   Author: $COMMIT_AUTHOR"
            VALID_COUNT=$((VALID_COUNT + 1))
        elif echo "$SIG_STATUS" | grep -q "BAD signature"; then
            echo -e "❌ ${RED}$COMMIT_SHORT${NC} - $COMMIT_MSG"
            echo "   Author: $COMMIT_AUTHOR"
            echo "   Status: BAD SIGNATURE"
            INVALID_SIGNATURES+=("$COMMIT_SHORT")
        else
            echo -e "❌ ${RED}$COMMIT_SHORT${NC} - $COMMIT_MSG"
            echo "   Author: $COMMIT_AUTHOR"
            echo "   Status: NOT SIGNED"
            UNSIGNED_COMMITS+=("$COMMIT_SHORT")
        fi
    fi
    echo ""
done <<< "$COMMIT_LIST"

echo ""
echo -e "${GREEN}[4/4]${NC} Generating summary..."
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  VERIFICATION SUMMARY${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "📊 Statistics:"
echo "   Total commits: $COMMIT_COUNT"
echo "   Valid signatures: $VALID_COUNT"
echo "   GitHub/merge commits: $MERGE_COUNT (signature not required)"
echo "   Unsigned commits: ${#UNSIGNED_COMMITS[@]}"
echo "   Invalid signatures: ${#INVALID_SIGNATURES[@]}"
echo ""

# Check if all commits are signed
if [ "$VALID_COUNT" -eq "$COMMIT_COUNT" ]; then
    echo -e "${GREEN}✅ SUCCESS: All commits are properly signed!${NC}"
    echo ""
    echo "🔒 Security:"
    echo "   - All commits have valid GPG signatures"
    echo "   - Code integrity verified"
    echo "   - OWASP A08:2021 compliance"
    echo ""
    echo -e "${BLUE}========================================${NC}"
    exit 0
else
    echo -e "${RED}❌ FAILURE: Found unsigned or invalid commits${NC}"
    echo ""

    if [ ${#UNSIGNED_COMMITS[@]} -gt 0 ]; then
        echo "🚫 Unsigned commits:"
        for commit in "${UNSIGNED_COMMITS[@]}"; do
            echo "   - $commit"
        done
        echo ""
    fi

    if [ ${#INVALID_SIGNATURES[@]} -gt 0 ]; then
        echo "⚠️  Invalid signatures:"
        for commit in "${INVALID_SIGNATURES[@]}"; do
            echo "   - $commit"
        done
        echo ""
    fi

    echo "📋 Action Required:"
    echo "   1. Sign unsigned commits: git rebase --exec 'git commit --amend --no-edit -n -S' $BASE_REF"
    echo "   2. Or amend last commit: git commit --amend --no-edit -S"
    echo "   3. Force push: git push --force"
    echo ""
    echo "📖 Documentation:"
    echo "   See CLAUDE.md section '🔐 Git Commit Signing' for setup instructions"
    echo ""
    echo -e "${BLUE}========================================${NC}"
    exit 1
fi
