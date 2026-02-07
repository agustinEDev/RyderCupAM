# 🏆 Ryder Cup Amateur Manager - Backend API

> Professional REST API for managing amateur Ryder Cup golf tournaments

<div align="center">

[![Version](https://img.shields.io/badge/version-2.0.5-blue?style=for-the-badge&logo=semver)](.)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](.)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.125.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](.)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?style=for-the-badge&logo=postgresql&logoColor=white)](.)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-0096C7?style=for-the-badge&logo=kubernetes&logoColor=white)](k8s/README.md)

[![Tests](https://img.shields.io/badge/tests-1282%20passing-00C853?style=for-the-badge&logo=pytest&logoColor=white)](.)
[![Coverage](https://img.shields.io/badge/coverage-90%25-success?style=for-the-badge&logo=codecov)](.)
[![OWASP](https://img.shields.io/badge/OWASP-9.4%2F10-4CAF50?style=for-the-badge&logo=owasp)](https://owasp.org/www-project-top-ten/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-passing-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](.)

[![Clean Architecture](https://img.shields.io/badge/architecture-Clean%20Architecture-blueviolet?style=for-the-badge)](.)
[![DDD](https://img.shields.io/badge/design-Domain%20Driven-orange?style=for-the-badge)](.)
[![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)

</div>

---

## 🌟 Overview

**RyderCupAM** is a production-ready backend API designed for managing amateur Ryder Cup style golf tournaments. Built with Clean Architecture and Domain-Driven Design principles, it provides a robust foundation for tournament management, player enrollment, live scoring, and real-time leaderboards.

### 🎯 Key Highlights

- ✅ **65 REST API endpoints** fully documented (Swagger UI)
- ✅ **1,282 tests** passing (100% success rate, ~79s execution)
- ✅ **OWASP Top 10 Score: 9.4/10** - Production-grade security
- ✅ **Clean Architecture** - 3-layer separation with DDD patterns
- ✅ **RBAC Foundation** - Simplified, three-tier role system (v2.0.0)
- ✅ **Rounds, Matches & Teams** - Full tournament scheduling with WHS handicap calculation (Sprint 2)
- ✅ **Competition ↔ GolfCourse M2M** - Multi-course tournaments with ordering (v2.0.2)
- ✅ **10 CI/CD jobs** - GitHub Actions pipeline (~3min)
- ✅ **Device Fingerprinting** - Advanced session management with auto-registration
- ✅ **Email Verification** - Bilingual templates (ES/EN) via Mailgun
- ✅ **166 Countries** - Full country database with 614 border relationships

---

## 🌐 Frontend Application

This is the **backend API**. For the web frontend application, visit:

👉 **[RyderCupWeb Repository](https://github.com/agustinEDev/RyderCupWeb)**

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### Local Development (Docker Compose)

```bash
# Clone repository
git clone https://github.com/agustinEDev/RyderCupAM.git
cd RyderCupAM

# Start services (PostgreSQL + API)
cd docker
docker-compose up -d

# View logs
docker-compose logs -f app

# Access API documentation
open http://localhost:8000/docs
```

**API will be available at:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

### Local Development (Kubernetes)

For a more production-like environment, you can use Kubernetes (via Kind). This setup provides a full cluster with separate services for the API, frontend, and database.

```bash
# Navigate to the Kubernetes directory
cd k8s

# Run the deployment script
# (Make sure scripts are executable: chmod +x scripts/*.sh)
./scripts/deploy-cluster.sh
```

Once the script finishes, the application will be accessible at:
- **Frontend:** `http://localhost:8080`
- **Backend API:** `http://localhost:8000/docs`

For a complete guide on managing the Kubernetes environment, including troubleshooting and script details, see the **[Kubernetes README](k8s/README.md)**.

### Production Deployment (Render.com)

See detailed guide: [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)

**Quick setup:**
1. Create PostgreSQL Database on Render
2. Create Web Service (Docker runtime)
3. Configure environment variables (see below)
4. Push to GitHub → Auto-deploy

**Essential Environment Variables:**
```bash
DATABASE_URL=<internal-database-url>
SECRET_KEY=<random-32-chars>
ENVIRONMENT=production
FRONTEND_ORIGINS=https://www.rydercupfriends.com
MAILGUN_API_KEY=<your-api-key>
MAILGUN_DOMAIN=<your-domain>
SENTRY_DSN=<your-sentry-dsn>  # Optional but recommended
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](CLAUDE.md) | Complete project context for AI development |
| [ROADMAP.md](ROADMAP.md) | Product roadmap and version planning |
| [CHANGELOG.md](CHANGELOG.md) | Detailed version history |
| [API.md](docs/API.md) | API endpoints reference |
| [ADRs](docs/architecture/decisions/) | Architecture Decision Records (33 total) |
| [SECURITY_IMPLEMENTATION.md](docs/SECURITY_IMPLEMENTATION.md) | Security features documentation |
| [MULTI_ENVIRONMENT_SETUP.md](docs/MULTI_ENVIRONMENT_SETUP.md) | Environment configuration guide |

---

## 🛠️ Tech Stack

<div align="center">

| Category | Technologies |
|----------|-------------|
| **Language** | Python 3.11+ |
| **Framework** | FastAPI 0.125.0 |
| **Database** | PostgreSQL 15+ |
| **ORM** | SQLAlchemy 2.0 (Imperative Mapping) |
| **Migrations** | Alembic |
| **Authentication** | JWT (httpOnly cookies + headers) |
| **Email** | Mailgun (EU region) |
| **Monitoring** | Sentry (errors + APM + profiling) |
| **Cache** | Redis (planned for leaderboards) |
| **Security** | SlowAPI, secure, bcrypt |
| **Testing** | pytest, pytest-xdist, pytest-asyncio |
| **CI/CD** | GitHub Actions |
| **Deployment** | Docker, Render.com |

</div>

---

## ✨ Features

### User Management
- ✅ **RBAC Foundation (v2.0.0)**: Simplified three-tier role system (ADMIN, CREATOR, PLAYER).
- ✅ Registration with email verification (bilingual ES/EN)
- ✅ JWT authentication (httpOnly cookies + dual support)
- ✅ Profile management (personal info + security)
- ✅ Handicap system (manual + RFEG integration)
- ✅ Password reset with secure tokens (256-bit, 24h expiration)
- ✅ Device fingerprinting with auto-registration

> **Admin User Setup**: Set `ADMIN_EMAIL=admin@example.com` in `.env` before running migrations. The initial admin is auto-promoted during migration. For post-migration promotion: `UPDATE users SET is_admin = TRUE WHERE email = 'user@example.com';`

### Competition Module
- ✅ CRUD operations for tournaments
- ✅ State machine (6 states): DRAFT → ACTIVE → IN_PROGRESS → COMPLETED
- ✅ Enrollment system (invitations + approvals)
- ✅ Custom handicap override per competition
- ✅ 166 countries with multilanguage support
- ✅ **Competition ↔ GolfCourse M2M** (v2.0.2) - Multi-course tournaments with ordering
- ✅ **Rounds & Matches** (Sprint 2) - Session-based scheduling, match generation, WHS handicap calculation
- ✅ 35 endpoints (14 competition + 8 enrollment + 2 countries + 4 golf courses + 11 rounds/matches)

### Security Features (v1.13.1)
- ✅ **httpOnly Cookies** - XSS prevention for tokens
- ✅ **Session Timeout** - 15min access tokens, 7-day refresh tokens
- ✅ **Account Lockout** - 10 failed attempts, 30min auto-unlock
- ✅ **CSRF Protection** - Triple-layer (header + cookie + SameSite)
- ✅ **Password History** - Prevents reuse of last 5 passwords
- ✅ **Device Fingerprinting** - SHA256 fingerprints, device management
- ✅ **IP Spoofing Prevention** - Trusted proxy validation
- ✅ **Rate Limiting** - Per-endpoint throttling (5-100 req/min)
- ✅ **Security Headers** - HSTS, X-Frame-Options, CSP
- ✅ **Audit Logging** - 8 security event types, JSON structured
- ✅ **Correlation IDs** - Full request traceability
- ✅ **Input Sanitization** - HTML sanitization, XSS prevention
- ✅ **Sentry Integration** - Error tracking + APM + profiling

### What's New

**v2.0.5 (Sprint 2 Complete - Feb 6, 2026)**
- ✅ **Rounds & Matches System**: Full session-based scheduling (MORNING/AFTERNOON/EVENING), match generation, team assignment
- ✅ **Playing Handicap Calculator**: WHS formula with format-specific allowances (Singles, Fourball, Foursomes)
- ✅ **Snake Draft Service**: Balanced automatic team assignment (A,B,B,A serpentine pattern)
- ✅ **11 new API endpoints**: CRUD rounds, match management, team assignment, match generation
- ✅ **+80 tests** (554 total competition module tests)

**v2.0.2 (Feb 1, 2026)**
- ✅ **Competition ↔ GolfCourse M2M**: Multi-course tournaments with add/remove/reorder operations
- ✅ **Mixed UUID Types Support**: CHAR(36) and UUID(as_uuid=True) compatibility in associations

**v2.0.1 (Jan 30, 2026)**
- ✅ **Golf Course Module**: Creator requests, Admin approval workflow, Clone-based updates
- ✅ **WHS Validation**: 2-10 tees (5 categories × gender), 18 holes, stroke indices, par totals

**v2.0.0 (Jan 27, 2026)**
- ✅ **RBAC Foundation**: Simplified, table-less role system (ADMIN, CREATOR, PLAYER)

### Coming Soon (Competition Module Evolution)
- 🔄 **Invitation System** - Email invitations with secure tokens (Sprint 3)
- 🔄 **Live Scoring** - Hole-by-hole annotation with dual validation (Sprint 4)
- 🔄 **Real-time Leaderboards** - Public leaderboard with Redis cache (Sprint 5)

---

## 🏗️ Architecture

### Clean Architecture + DDD

```
src/
├── modules/
│   ├── user/
│   │   ├── domain/          # Entities, VOs, Events, Interfaces
│   │   ├── application/     # Use Cases, DTOs
│   │   └── infrastructure/  # API, DB, External Services
│   ├── competition/
│   └── ... (future modules)
├── shared/                  # Cross-cutting concerns
└── config/                  # Settings, dependencies
```

### Design Patterns
- **Repository + Unit of Work** - Data access abstraction
- **Domain Events** - Inter-aggregate communication
- **Value Objects** - Encapsulated validation logic
- **Port/Adapter (Hexagonal)** - External service interfaces
- **Dependency Injection** - FastAPI Depends()
- **Use Cases** - Single responsibility per operation

### Key Principles
- **SOLID** compliance
- **Dependency Inversion** - Domain never imports Infrastructure
- **Testability** - 90%+ coverage on business logic
- **Immutability** - Value Objects are immutable
- **Event-Driven** - Domain events for side effects

---

## 🧪 Testing

### Running Tests

```bash
# Full test suite (recommended - with parallelization)
python dev_tests.py

# Specific test categories
pytest tests/unit/              # Unit tests only (~40s)
pytest tests/integration/       # Integration tests (~20s)
pytest tests/security/          # Security tests (~5s)

# With coverage report
pytest --cov=src --cov-report=html

# Parallel execution (faster)
pytest tests/ -n auto
```

### Test Statistics (v2.0.5)

| Category | Tests | Status | Coverage |
|----------|-------|--------|----------|
| **Total** | **1,282** | ✅ 100% passing | 90%+ |
| User Module | 588 | ✅ 100% | 92% |
| Competition Module | 554 | ✅ 100% | 91% |
| Golf Course Module | 51 | ✅ 100% | 93% |
| Security Suite | 34 | ✅ 100% | 95% |
| Shared | 138 | ✅ 100% | 88% |
| Integration | 100 | ✅ 100% | - |

**Execution Time**: ~75 seconds (with pytest-xdist parallelization)

**Test Types**:
- Unit tests (domain + application logic)
- Integration tests (database + API endpoints)
- Security tests (OWASP Top 10 coverage)
- E2E tests (full user flows)

---

## 🔐 Security

### OWASP Top 10 2021 Score: 9.4/10 ⭐

<div align="center">

| Category | Score | Mitigation |
|----------|-------|------------|
| **A01: Broken Access Control** | 10/10 | JWT, refresh tokens, CSRF, RBAC, device fingerprinting |
| **A02: Cryptographic Failures** | 10/10 | bcrypt 12 rounds, httpOnly cookies, HSTS, SHA256 tokens |
| **A03: Injection** | 10/10 | SQLAlchemy ORM, Pydantic validation, HTML sanitization |
| **A04: Insecure Design** | 9/10 | Rate limiting, field limits, secure defaults |
| **A05: Security Misconfiguration** | 9.5/10 | CORS whitelist, security headers, fail-fast validation |
| **A06: Vulnerable Components** | 9/10 | Snyk scanning, dependency audit, CI/CD checks |
| **A07: ID & Auth Failures** | 9.5/10 | Password policy, account lockout, password history, session timeout |
| **A08: Software & Data Integrity** | 7/10 | GPG commit signing, code review (CI/CD SCA pending) |
| **A09: Logging Failures** | 10/10 | Audit trail, correlation IDs, Sentry monitoring |
| **A10: SSRF** | 8/10 | Input validation, URL whitelisting |

</div>

**Security Features Timeline**:
- **v1.8.0**: httpOnly cookies, session timeout, rate limiting, CORS, security headers
- **v1.11.0**: Password reset system with secure tokens
- **v1.13.0**: Account lockout, CSRF protection, password history, device fingerprinting
- **v1.13.1**: IP spoofing prevention, current device detection

See [SECURITY_IMPLEMENTATION.md](docs/SECURITY_IMPLEMENTATION.md) for complete details.

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow

10 parallel jobs executed on every push:

| Job | Description | Duration |
|-----|-------------|----------|
| **preparation** | Python setup (3.11, 3.12) + pip cache | ~30s |
| **unit_tests** | Unit tests (matrix: Python 3.11, 3.12) | ~45s |
| **integration_tests** | Integration tests with PostgreSQL service | ~60s |
| **security_checks** | Safety + pip-audit (dependency CVE scan) | ~25s |
| **linting** | Ruff linting (fast Rust-based linter) | ~20s |
| **type_checking** | Mypy static type analysis | ~30s |
| **build** | Docker build + Alembic validation | ~50s |
| **snyk_scan** | Snyk Test (SCA) + Snyk Code (SAST) | ~40s |
| **gitleaks** | Secret scanning in commits | ~15s |
| **pipeline_summary** | Aggregate results and report | ~10s |

**Total Pipeline Duration**: ~3 minutes

**Branch Protection**:
- All jobs must pass before merge
- GPG-signed commits required on `main` and `develop`
- Minimum 1 approving review for PRs

See [ADR-021](docs/architecture/decisions/ADR-021-github-actions-ci-cd-pipeline.md) for technical decisions.

---

## 📡 API Endpoints

### Available Endpoints (65 total)

<details>
<summary><b>Authentication (11 endpoints)</b></summary>

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/current-user`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/verify-email`
- `POST /api/v1/auth/resend-verification`
- `POST /api/v1/auth/refresh-token`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`
- `GET /api/v1/auth/validate-reset-token/:token`
- `POST /api/v1/auth/unlock-account`
</details>

<details>
<summary><b>User Management (4 endpoints)</b></summary>

- `GET /api/v1/users/search`
- `PATCH /api/v1/users/profile`
- `PATCH /api/v1/users/security`
- `GET /api/v1/users/me/roles/{competition_id}` (v2.0.0)
</details>

<details>
<summary><b>Device Management (2 endpoints)</b></summary>

- `GET /api/v1/users/me/devices`
- `DELETE /api/v1/users/me/devices/{id}`
</details>

<details>
<summary><b>Handicap Management (3 endpoints)</b></summary>

- `POST /api/v1/handicaps/update`
- `POST /api/v1/handicaps/update-multiple`
- `POST /api/v1/handicaps/update-manual`
</details>

<details>
<summary><b>Competition Management (10 endpoints)</b></summary>

- `POST /api/v1/competitions`
- `GET /api/v1/competitions`
- `GET /api/v1/competitions/{id}`
- `PUT /api/v1/competitions/{id}`
- `DELETE /api/v1/competitions/{id}`
- `POST /api/v1/competitions/{id}/activate`
- `POST /api/v1/competitions/{id}/close-enrollments`
- `POST /api/v1/competitions/{id}/start`
- `POST /api/v1/competitions/{id}/complete`
- `POST /api/v1/competitions/{id}/cancel`
</details>

<details>
<summary><b>Enrollment Management (8 endpoints)</b></summary>

- `POST /api/v1/competitions/{id}/enrollments`
- `POST /api/v1/competitions/{id}/enrollments/direct`
- `GET /api/v1/competitions/{id}/enrollments`
- `POST /api/v1/enrollments/{id}/approve`
- `POST /api/v1/enrollments/{id}/reject`
- `POST /api/v1/enrollments/{id}/cancel`
- `POST /api/v1/enrollments/{id}/withdraw`
- `PUT /api/v1/enrollments/{id}/handicap`
</details>

<details>
<summary><b>Golf Course Management (10 endpoints)</b></summary>

- `POST /api/v1/golf-courses/request` - Creator requests new course
- `POST /api/v1/golf-courses/admin` - Admin creates course directly (approved)
- `GET /api/v1/golf-courses/{id}` - Get course details (tees + holes)
- `GET /api/v1/golf-courses?approval_status=APPROVED` - List filtered courses
- `GET /api/v1/golf-courses/admin/pending` - Admin view pending approvals
- `PUT /api/v1/golf-courses/admin/{id}/approve` - Admin approves course
- `PUT /api/v1/golf-courses/admin/{id}/reject` - Admin rejects course
- `PUT /api/v1/golf-courses/{id}` - Creator submits update (clone-based)
- `PUT /api/v1/golf-courses/admin/updates/{id}/approve` - Admin approves update
- `PUT /api/v1/golf-courses/admin/updates/{id}/reject` - Admin rejects update
</details>

<details>
<summary><b>Rounds & Schedule (4 endpoints)</b></summary>

- `POST /api/v1/competitions/{id}/rounds` - Create round
- `PUT /api/v1/competitions/rounds/{id}` - Update round
- `DELETE /api/v1/competitions/rounds/{id}` - Delete round
- `GET /api/v1/competitions/{id}/schedule` - Get competition schedule
</details>

<details>
<summary><b>Match Management (4 endpoints)</b></summary>

- `GET /api/v1/competitions/matches/{id}` - Get match detail
- `PUT /api/v1/competitions/matches/{id}/status` - Update match status
- `POST /api/v1/competitions/matches/{id}/walkover` - Declare walkover
- `PUT /api/v1/competitions/matches/{id}/players` - Reassign match players
</details>

<details>
<summary><b>Teams & Generation (3 endpoints)</b></summary>

- `POST /api/v1/competitions/{id}/teams` - Assign teams (automatic/manual)
- `POST /api/v1/competitions/rounds/{id}/matches/generate` - Generate matches
- `POST /api/v1/competitions/{id}/schedule/configure` - Configure schedule
</details>

<details>
<summary><b>Countries (2 endpoints)</b></summary>

- `GET /api/v1/countries`
- `GET /api/v1/countries/{code}/adjacent`
</details>

**Interactive Documentation**: http://localhost:8000/docs

---

## 💻 Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/agustinEDev/RyderCupAM.git
cd RyderCupAM

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your configuration

# Start PostgreSQL (Docker)
cd docker
docker-compose up -d db

# Run migrations
alembic upgrade head

# Start development server
uvicorn main:app --reload --log-level info
```

### Common Commands

```bash
# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1

# Code quality
ruff check src/ tests/          # Linting
ruff format src/ tests/         # Formatting
mypy src/                       # Type checking

# Security scanning
gitleaks detect --verbose       # Secret detection
bandit -r src/                  # Security linting
safety check                    # Dependency vulnerabilities

# Testing
python dev_tests.py             # All tests with parallelization
pytest tests/unit/ -v           # Unit tests verbose
pytest tests/integration/ -v    # Integration tests verbose
pytest --cov=src                # Coverage report
```

### Git Workflow

**Important**: All commits must be GPG-signed on protected branches (`main`, `develop`).

```bash
# Enable GPG signing globally
git config --global commit.gpgsign true

# Create feature branch
git checkout -b feature/amazing-feature

# Make changes and commit (GPG-signed)
git commit -S -m "feat: add amazing feature"

# Push and create PR
git push origin feature/amazing-feature
```

See [CLAUDE.md](CLAUDE.md) for complete development guidelines.

---

## 📊 Project Roadmap

### Current Version: v2.0.5 (Production)

**Latest Features** (Sprint 2 Complete - Feb 6, 2026):
- **Rounds & Matches System**: Session-based scheduling, match generation, WHS handicap calculation
- **Playing Handicap Calculator**: WHS formula with format-specific allowances
- **Snake Draft Service**: Balanced automatic team assignment
- **11 new endpoints**: Round CRUD, match management, team assignment, match generation
- **+80 tests** (554 total competition module) - Total: 1,282 passing
- **Competition ↔ GolfCourse M2M** (v2.0.2): Multi-course tournaments with ordering

### Coming Next: Sprint 3-5 - Invitations, Scoring & Leaderboards

**Sprint Breakdown**:
1. ✅ **Sprint 1** (Jan 27 - Jan 31): Golf Courses - 10 endpoints (COMPLETED)
2. ✅ **Sprint 2** (Feb 3 - Feb 6): Competition-GolfCourse + Rounds + Matches - 15 endpoints (COMPLETED)
3. **Sprint 3** (Feb 2026): Invitations - 5 endpoints
4. **Sprint 4** (Mar 2026): Scoring System - 4 endpoints
5. **Sprint 5** (Mar 2026): Leaderboards - 2 endpoints

See [ROADMAP.md](ROADMAP.md) for complete version planning.

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Code Standards
- Follow **Clean Architecture** and **DDD** principles
- Write **tests** for all new features (>90% coverage)
- Use **type hints** for all functions
- Follow **PEP 8** style guide (enforced by Ruff)
- Write **docstrings** for public APIs

### Pull Request Process
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes with GPG signature: `git commit -S -m "feat: amazing feature"`
4. Write/update tests: `python dev_tests.py`
5. Push branch: `git push origin feature/amazing-feature`
6. Open Pull Request with description

### Commit Message Convention
Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `chore:` Maintenance tasks

---

## 📄 License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author & Contact

**Agustín Estévez**
- GitHub: [@agustinEDev](https://github.com/agustinEDev)
- Repository: [RyderCupAM](https://github.com/agustinEDev/RyderCupAM)
- Issues: [Report a bug](https://github.com/agustinEDev/RyderCupAM/issues)

---

## 🙏 Acknowledgments

- **FastAPI** - Modern, fast web framework for Python
- **SQLAlchemy** - Powerful ORM for database operations
- **Pydantic** - Data validation using Python type annotations
- **R&A** - Official Rules of Golf
- **USGA** - World Handicap System (WHS)

---

<div align="center">

### ⭐ Star this repository if you find it useful!


</div>
