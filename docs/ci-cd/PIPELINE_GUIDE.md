# CI/CD Pipeline Guide

**Version**: v2.0.12 (12 jobs)
**Last Updated**: February 24, 2026

---

## Overview

Automated pipeline that runs on **every push** and **pull request**.

**Purpose**: Ensure code quality, security, and integrity before deployment.

---

## Pipeline Jobs

| Job | What It Does | Time | When Fails |
| --- | --- | --- | --- |
| 🔧 **Preparation** | Setup Python + cache dependencies | ~30s | Check `requirements.txt` |
| 🧪 **Unit Tests** | 1,873 tests (Python 3.11/3.12) | ~45s | Run locally: `pytest tests/unit/` |
| 🗄️ **Integration Tests** | 252 tests + PostgreSQL | ~60s | Check migrations: `alembic upgrade head` |
| 🔐 **Security Tests** | 45+ tests (CSRF, XSS, SQLi) | ~50s | Fix security vulnerability |
| 🔒 **Security Checks** | Bandit, Safety, pip-audit, Gitleaks | ~40s | Update vulnerable dependency |
| 📝 **Linting** | Ruff code quality | ~20s | Run: `ruff format src/ tests/` |
| 🔬 **Type Checking** | Mypy static analysis | ~25s | Add type hints |
| 🐳 **Build & Scan** | Docker build + Trivy scan | ~90s | Check `Dockerfile` or base image |
| 🐍 **Snyk Scan** | SCA + SAST security | ~40s | Review Snyk report in Artifacts |
| 📦 **SBOM Generation** | Software Bill of Materials | ~35s | Only runs on `main`/`develop`/`release/*` |
| 🔏 **GPG Verification** | Verify all commits signed | ~15s | Sign commits: `git commit --amend -S` |
| 📊 **Summary** | Final report | ~5s | - |

**Total Time**: ~3 minutes

---

## Quick Fix Guide

### Tests Failing
```bash
# Run locally
pytest tests/unit/
pytest tests/integration/

# Clear cache if needed
pytest --cache-clear
```

### Linting Errors
```bash
# Auto-fix
ruff check --fix src/ tests/
ruff format src/ tests/
```

### GPG Signature Missing
```bash
# Sign all commits since main (rewrites history!)
git rebase --exec 'git commit --amend --no-edit -n -S' origin/main

# Force push with safety check (only if no one else pushed)
git push --force-with-lease
```

**⚠️ Warning**: Rewriting history requires force push. Coordinate with collaborators before using `--force-with-lease`. Never use force push to hide failures - fix issues properly instead.

### Security Vulnerability
```bash
# Update vulnerable package
pip install --upgrade <package-name>
pip freeze > requirements.txt
git commit -S -m "fix: update vulnerable dependency"
```

---

## Critical Jobs

These jobs **MUST pass** to merge:

- ✅ Unit Tests
- ✅ Integration Tests
- ✅ Security Tests
- ✅ GPG Verification
- ✅ Build

Others are warnings (don't block merge).

---

## Artifacts

Download from: `GitHub Actions → Run → Artifacts`

| Artifact                                       | Retention |
| ---------------------------------------------- | --------- |
| Coverage Reports (XML/HTML)                    | 7 days    |
| Security Reports (Bandit, Safety, pip-audit)   | 30 days   |
| Snyk Reports (SCA/SAST)                        | 30 days   |
| SBOM (CycloneDX)                               | 90 days   |
| Docker Image (tar.gz)                          | 7 days    |

---

## Best Practices

**Before pushing**:
```bash
pytest tests/              # Run tests
ruff format src/ tests/    # Format code
ruff check src/ tests/     # Check linting
git log --show-signature   # Verify GPG signatures
```

**If pipeline fails**:
1. Read the error log completely
2. Reproduce locally
3. Fix the issue
4. Commit + push solution
5. **Never force push to hide errors**

---

## GPG Signature Setup

**Required**: All commits MUST be GPG-signed.

### Quick Setup
```bash
# 1. List your GPG keys
gpg --list-secret-keys --keyid-format=long

# 2. Configure Git
git config --global user.signingkey YOUR_KEY_ID
git config --global commit.gpgsign true

# 3. Export public key for GitHub
gpg --armor --export YOUR_KEY_ID

# 4. Add to GitHub: Settings → SSH and GPG keys → New GPG key
```

### GitHub Secret Setup

**Secret Name**: `GPG_PUBLIC_KEY`

**Location**: Repo → Settings → Secrets and variables → Actions

**Value**: Your GPG public key (output from step 3 above)

---

## Configuration

**Pipeline File**: `.github/workflows/ci_cd_pipeline.yml`

**Scripts**:
- `scripts/verify-gpg-signatures.sh` - GPG verification
- `scripts/generate-sbom.sh` - SBOM generation
- `scripts/freeze-requirements.sh` - Dependency locking

---

**Maintained by**: Development Team
