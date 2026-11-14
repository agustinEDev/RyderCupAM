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
# Requirements: gpg, git; gh and GITHUB_REPOSITORY for merge and GitHub web-flow commits
#
# Merge commits and GitHub web-flow commits are not verified with the local keyring:
# GitHub signs them with its own key. They used to be skipped, but both can be forged
# locally (`git merge` without -S, or GIT_COMMITTER_EMAIL=noreply@github.com), so
# GitHub is asked whether each one is verified (audit phase 6, INF-06). No answer
# from GitHub is not a pass.

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

    if echo "$GPG_PUBLIC_KEY" | gpg --import --batch --yes 2>&1; then
        echo "✅ GPG key imported successfully"
    else
        GPG_EXIT=$?
        echo -e "${RED}❌ ERROR: Failed to import GPG key${NC}"
        echo "   Exit code: $GPG_EXIT"
        echo ""
        echo "   This usually means:"
        echo "   - GPG_PUBLIC_KEY is not a valid GPG public key"
        echo "   - GPG is not installed or not working"
        echo "   - Key format is incorrect"
        echo ""
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  No GPG_PUBLIC_KEY environment variable found${NC}"
    echo "   Using system keyring only"
fi

echo ""
echo -e "${GREEN}[2/4]${NC} Fetching commit range..."
echo "   Base: $BASE_REF"
echo "   Head: $HEAD_REF"

# Get list of commits in range (fail if git rev-list errors)
# If BASE_REF is empty, verify only HEAD_REF (first commit case)
if [ -z "$BASE_REF" ]; then
    echo "   (Verifying only HEAD_REF - no parent commit)"
    COMMIT_LIST=$(git rev-list -n 1 "$HEAD_REF" 2>&1)
else
    COMMIT_LIST=$(git rev-list "$BASE_REF..$HEAD_REF" 2>&1)
fi
REV_LIST_EXIT=$?

if [ $REV_LIST_EXIT -ne 0 ]; then
    echo -e "${RED}❌ ERROR: git rev-list failed${NC}"
    echo "   Command: git rev-list $BASE_REF..$HEAD_REF"
    echo "   Error: $COMMIT_LIST"
    echo ""
    echo "   This usually means:"
    echo "   - Base ref ($BASE_REF) doesn't exist"
    echo "   - Invalid commit range"
    echo "   - Repository is corrupted"
    echo ""
    exit 1
fi

if [ -z "$COMMIT_LIST" ]; then
    echo -e "${YELLOW}⚠️  No new commits to verify${NC}"
    echo "   This might be the initial commit"
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
GITHUB_AUTO_MERGE_COUNT=0

while IFS= read -r commit; do
    # Get commit info
    COMMIT_SHORT=$(git log -1 --format="%h" "$commit")
    COMMIT_MSG=$(git log -1 --format="%s" "$commit" | head -c 60)
    COMMIT_AUTHOR=$(git log -1 --format="%an" "$commit")
    COMMIT_EMAIL=$(git log -1 --format="%ae" "$commit")

    # Check if this is a merge commit (has 2+ parents)
    PARENT_COUNT=$(git rev-list --parents -n 1 "$commit" | wc -w)
    PARENT_COUNT=$((PARENT_COUNT - 1))  # Subtract commit itself

    # GitHub web-flow commits (merge or squash merge via GitHub UI/API). The committer
    # e-mail is only a hint (anyone can set it): GitHub is asked below
    IS_GITHUB_WEBFLOW=false
    COMMITTER_EMAIL=$(git log -1 --format="%ce" "$commit")
    if echo "$COMMITTER_EMAIL" | grep -iq "noreply@github.com"; then
        IS_GITHUB_WEBFLOW=true
    fi

    # Merge commits and GitHub web-flow commits: GitHub must say they are verified
    if [ "$PARENT_COUNT" -ge 2 ] || [ "$IS_GITHUB_WEBFLOW" = true ]; then
        TIPO="MERGE COMMIT"
        [ "$IS_GITHUB_WEBFLOW" = true ] && TIPO="GITHUB WEB-FLOW"

        # Outside CI, the repository of this clone, from gh itself
        if [ -z "${GITHUB_REPOSITORY:-}" ]; then
            GITHUB_REPOSITORY=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null) || GITHUB_REPOSITORY=""
        fi
        if [ -z "${GITHUB_REPOSITORY:-}" ]; then
            VERIFIED="no-repo"
        else
            VERIFIED=$(gh api "repos/$GITHUB_REPOSITORY/commits/$commit" \
                --jq '.commit.verification.verified' 2>/dev/null) || VERIFIED="no-answer"
        fi

        if [ "$VERIFIED" = "true" ]; then
            echo -e "🔀 ${GREEN}$COMMIT_SHORT${NC} - $COMMIT_MSG"
            echo "   Author: $COMMIT_AUTHOR"
            echo "   Type: $TIPO (verified by GitHub)"
            VALID_COUNT=$((VALID_COUNT + 1))
            MERGE_COUNT=$((MERGE_COUNT + 1))
            [ "$IS_GITHUB_WEBFLOW" = true ] && GITHUB_AUTO_MERGE_COUNT=$((GITHUB_AUTO_MERGE_COUNT + 1))
        elif [ "$VERIFIED" = "false" ]; then
            echo -e "❌ ${RED}$COMMIT_SHORT${NC} - $COMMIT_MSG"
            echo "   Author: $COMMIT_AUTHOR"
            echo "   Type: $TIPO, NOT VERIFIED by GitHub"
            UNSIGNED_COMMITS+=("$COMMIT_SHORT")
        else
            echo -e "❌ ${RED}$COMMIT_SHORT${NC} - $COMMIT_MSG"
            echo "   Author: $COMMIT_AUTHOR"
            echo "   Type: $TIPO, could not ask GitHub whether it is verified ($VERIFIED)"
            UNSIGNED_COMMITS+=("$COMMIT_SHORT")
        fi
    else
        # Regular commit (one parent): verify the signature with the local keyring
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
echo "   Merge commits (verified by GitHub): $MERGE_COUNT"
echo "      ↳ GitHub auto-merges: $GITHUB_AUTO_MERGE_COUNT"
echo "      ↳ Manual merges: $((MERGE_COUNT - GITHUB_AUTO_MERGE_COUNT))"
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
    echo "   An unverified merge commit: redo the merge with -S (git merge -S), or merge"
    echo "   through the pull request on GitHub, which signs its merges"
    echo ""
    echo "📖 Documentation:"
    echo "   See docs/ci-cd/PIPELINE_GUIDE.md section 'GPG Signature Setup' for setup instructions"
    echo ""
    echo -e "${BLUE}========================================${NC}"
    exit 1
fi
