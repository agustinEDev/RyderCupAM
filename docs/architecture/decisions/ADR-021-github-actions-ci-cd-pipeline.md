# ADR-021: GitHub Actions for CI/CD Pipeline

**Date**: November 30, 2025
**Status**: Accepted
**Decision Makers**: Development Team

## Context and Problem

The project needs a CI/CD system that automatically runs tests, validates code quality, verifies database migrations, and supports multiple Python versions. Must be easy to maintain, provide fast feedback, and be free or low-cost.

## Options Considered

1. **GitHub Actions**: Integrated with GitHub, 2000 min/month free (unlimited for public repos)
2. **GitLab CI/CD**: 400 min/month free, requires repository migration
3. **CircleCI**: 6000 min/month free, requires external integration
4. **Jenkins (self-hosted)**: Full control, requires dedicated server

## Decision

**Adopt GitHub Actions** with pipeline covering: preparation, unit_tests (Python 3.11/3.12 matrix), integration_tests (PostgreSQL service), security_scan (Gitleaks), code_quality (Ruff), type_checking (Mypy), and database_migrations (Alembic validation). Uses dependency caching and parallelization for independent jobs.

## Rationale

### Advantages:

1. **Native Integration**
   - Automatic workflow triggers (push, PR)
   - Integrated secrets management
   - Status checks visible in PRs

2. **Cost and Performance**
   - Free for public repository
   - Dependency cache reduces builds
   - Fast execution (~3 minutes)

3. **Ecosystem**
   - Pre-built actions (setup-python, gitleaks)
   - Declarative YAML configuration
   - Detailed logs

4. **Developer Experience**
   - Fast feedback in PRs
   - Re-run individual jobs
   - Zero-config for contributors

## Consequences

### Positive:
- ✅ Tests running automatically in ~3 minutes
- ✅ Early error detection (types, linting, security)
- ✅ Migration validation before merge
- ✅ Multi-version Python support

### Negative:
- ❌ Vendor lock-in with GitHub (mitigated: portable YAML)
- ❌ Shared runners (variable performance)
- ❌ Logs deleted after 90 days

### Risks Mitigated:
- **Minute limit**: Public repo = unlimited minutes
- **Performance**: Cache reduces build time
- **Secrets exposure**: Gitleaks validates commits

## Validation

Decision considered successful if:
- [x] Pipeline runs in < 5 minutes (✅ ~3 min)
- [x] Tests on Python 3.11 and 3.12 (✅ Matrix strategy)
- [x] Integration tests with PostgreSQL (✅ Service container)
- [x] Security scanning active (✅ Gitleaks)
- [x] Code quality checks (✅ Ruff + Mypy)

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Python CI/CD Best Practices](https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python)
- [Gitleaks Action](https://github.com/gitleaks/gitleaks-action)

## Implementation Notes

### Implemented (Nov 30, 2025):
Complete pipeline in `.github/workflows/ci_cd_pipeline.yml` with 7 parallel jobs, Mypy configured pragmatically for SQLAlchemy, Gitleaks with fingerprint-based whitelist, and complete test suite.

### Key Lessons:
- Use `Generic[TypeVar]` for Python 3.11/3.12 compatibility (avoid PEP 695)
- Gitleaks requires specific fingerprints, not glob patterns
- Alembic: `override=False` in `load_dotenv()` for env vars precedence

---

## Evolution: Security Enhancements (Jan 8, 2026 - v1.13.0)

### New Jobs Added:

**JOB 4: Security Tests** ⭐
- Runs 45+ security tests (CSRF, XSS, SQLi, Auth Bypass, Rate Limiting)
- OWASP Coverage: A01-A09
- PostgreSQL service (same as integration tests)
- Fail-fast policy (blocks build if fails)

**JOB 7: Trivy Container Scan** ⭐
- Scans Docker image for CVEs (OS + Python packages)
- Severity: HIGH + CRITICAL
- Output: SARIF → GitHub Security tab
- Exit code: 0 (monitoring mode, non-blocking for now)

### Complete Security Stack:
- **SCA**: Safety, pip-audit, Snyk Test (dependencies)
- **SAST**: Bandit, Snyk Code (source code)
- **Secrets**: Gitleaks (commits)
- **DAST**: Security Tests (runtime vulnerabilities) ⭐ NEW
- **Container**: Trivy (Docker image CVEs) ⭐ NEW

### Metrics Post-Enhancements:
- Jobs: 7 → **10 jobs**
- Tests: 734 → **779 tests** (+45 security tests)
- Security tools: 4 → **6 tools**
- Pipeline time: ~3 min (unchanged - parallelization)
